from typing import Dict, List
from reactive_s3 import ReactiveS3Index, FileMetadata
import time
import tempfile
import os
import sys
import subprocess
import uuid
import json


def absPath(path: str):
    root_file_path = os.path.join(os.getcwd(), sys.argv[0])
    absolute_path = os.path.join(os.path.dirname(root_file_path), path)
    return absolute_path


class TrialToProcess:
    index: ReactiveS3Index

    subjectPath: str
    trialName: str
    trialPath: str

    # Subject files
    subjectStatusFile: str
    opensimFile: str
    goldscalesFile: str

    # Trial files
    markersFile: str
    goldIKFile: str
    readyFlagFile: str
    processingFlagFile: str
    resultsFile: str
    previewJsonFile: str
    logfile: str

    def __init__(self, index: ReactiveS3Index, subjectPath: str, trialName: str) -> None:
        self.index = index
        self.subjectPath = subjectPath
        if not self.subjectPath.endswith('/'):
            self.subjectPath += '/'
        self.trialName = trialName
        if not self.trialName.endswith('/'):
            self.trialName += '/'
        self.trialPath = self.subjectPath + 'trials/' + self.trialName

        # Subject files
        self.subjectStatusFile = self.subjectPath + '_subject.json'
        self.opensimFile = self.subjectPath + 'unscaled_generic.osim'
        self.goldscalesFile = self.subjectPath + 'manually_scaled.osim'

        # Trial files
        self.markersFile = self.trialPath + 'markers.trc'
        self.goldIKFile = self.trialPath + 'manual_ik.mot'
        self.readyFlagFile = self.trialPath + 'READY_TO_PROCESS'
        self.processingFlagFile = self.trialPath + 'PROCESSING'
        self.resultsFile = self.trialPath + '_results.json'
        self.previewJsonFile = self.trialPath + 'preview.json.zip'
        self.logfile = self.trialPath + 'log.txt'

    def process(self):
        """
        This tries to download the whole set of necessary files, launch the processor, and re-upload the results,
        while also managing the processing flag age.
        """
        print('Processing '+str(self))

        procLogTopic = str(uuid.uuid4())

        # 1. Update the processing flag, to let people know that we're working on this. This isn't a guarantee
        # that no other competing servers will process this at the same time (which would be harmless but
        # inefficient), but hopefully it reduces collisions.
        self.pushProcessingFlag(procLogTopic)

        # 2. Download the files to a tmp folder
        path = tempfile.mkdtemp()
        if not path.endswith('/'):
            path += '/'
        self.index.download(self.subjectStatusFile, path+'_subject.json')
        self.index.download(self.markersFile, path+'markers.trc')
        self.index.download(self.opensimFile, path+'unscaled_generic.osim')
        if self.index.exists(self.goldIKFile):
            self.index.download(self.goldIKFile, path+'manual_ik.mot')
        if self.index.exists(self.goldscalesFile):
            self.index.download(self.goldscalesFile,
                                path+'manually_scaled.osim')

        # 3. That download can take a while, so re-up our processing soft-lock
        self.pushProcessingFlag(procLogTopic)

        # 4. Launch a processing process
        enginePath = absPath('../engine/engine.py')
        print('Calling Command:\n'+enginePath+' '+path)
        with open(path + 'log.txt', 'wb+') as logFile:
            with subprocess.Popen([enginePath, path], stdout=subprocess.PIPE) as proc:
                print('Process created: '+str(proc.pid))
                for lineBytes in iter(proc.stdout.readline, b''):
                    if lineBytes is None and proc.poll() is not None:
                        break
                    line = lineBytes.decode("utf-8")
                    print('>>> '+str(line).strip())
                    # Send to the log
                    logFile.write(lineBytes)
                    # Send to PubSub
                    logLine: Dict[str, str] = {}
                    logLine['line'] = line
                    logLine['timestamp'] = time.time() * 1000
                    self.index.pubSub.sendMessage(
                        '/LOG/'+procLogTopic, logLine)

        # 5. Upload the results back to S3
        self.index.uploadFile(self.logfile, path + 'log.txt')
        if os.path.exists(path + 'preview.json.zip'):
            self.index.uploadFile(self.previewJsonFile,
                                  path + 'preview.json.zip')
        # 5.1. Upload the _results.json file last, since that marks the trial as DONE on the frontend,
        # and it starts to be able
        if os.path.exists(path + '_results.json'):
            self.index.uploadFile(self.resultsFile, path + '_results.json')

        # 6. Clean up after ourselves
        # os.rmdir(path)

    def pushProcessingFlag(self, procLogTopic: str):
        procData: Dict[str, str] = {}
        procData['logTopic'] = procLogTopic
        procData['timestamp'] = time.time() * 1000
        self.index.uploadText(self.processingFlagFile, json.dumps(procData))

    def shouldProcess(self) -> bool:
        # If this isn't ready, or it's already done, ignore it
        if not self.readyToProcess() or self.alreadyProcessed():
            return False
        # If nobody else has claimed this, it's a great bet
        if not self.index.exists(self.processingFlagFile):
            return True
        # If there's already a processing flag, we need to check how old it is. Servers are
        # allowed to crash without finishing processing, so they're supposed to re-up their lock
        # on the PROCESSING file every minute or so. If they don't, then this is once again up for
        # grabs, and other servers can take it.
        processLockTimestamp = self.index.getMetadata(
            self.processingFlagFile).lastModified
        currentTimestamp = time.time() * 1000
        lockAge = currentTimestamp - processLockTimestamp
        # If the lock is older than 60 seconds, this is probably good to go
        return lockAge > 60000

    def readyToProcess(self) -> bool:
        """
        If we've got both the markers file (at a minimum) and a 'READY_TO_PROCESS' flag, we could process this
        """
        return self.index.exists(self.readyFlagFile) and self.index.exists(self.markersFile)

    def alreadyProcessed(self) -> bool:
        """
        If there's already results files, and they're newer than the input files, we're already processed
        """
        if not self.index.exists(self.resultsFile):
            return False

        # TODO: this doesn't seem to quite match up, since S3 maybe doesn't sync lastModified properly
        # Maybe we need a better way to handle this than looking at lastModified times...

        # # Get the earliest output timestamp
        # processedTimestamp = self.index.getMetadata(
        #     self.resultsFile).lastModified

        # # Get the latest input timestamp
        # if not self.index.exists(self.markersFile):
        #     return True
        # uploadedTimestamp = self.latestInputTimestamp()

        # processingTime = processedTimestamp - uploadedTimestamp

        # # If the output is older than the input, then it's out of date and we need could replace it
        # return processingTime < 0

        return True

    def latestInputTimestamp(self) -> int:
        if not self.index.exists(self.markersFile):
            return 0
        uploadedTimestamp = self.index.getMetadata(
            self.markersFile).lastModified
        if self.index.exists(self.goldIKFile):
            uploadedTimestamp = max(
                uploadedTimestamp, self.index.getMetadata(self.goldIKFile).lastModified)
        return uploadedTimestamp

    def __repr__(self) -> str:
        return self.subjectPath + "::" + self.trialName + " uploaded @" + str(self.latestInputTimestamp())

    def __str__(self) -> str:
        return self.subjectPath + "::" + self.trialName + " uploaded @" + str(self.latestInputTimestamp())


class MocapServer:
    index: ReactiveS3Index
    queue: List[TrialToProcess]

    def __init__(self) -> None:
        self.index = ReactiveS3Index()
        self.index.addChangeListener(self.onChange)
        self.index.refreshIndex()
        self.index.registerPubSub()

    def onChange(self):
        print('CHANGED!')

        shouldProcessTrials: List[TrialToProcess] = []

        # 1. Collect all Trials
        for folder in self.index.listAllFolders():
            if self.index.hasChildren(folder, ['trials/', '_subject.json']):
                if not folder.endswith('/'):
                    folder += '/'
                print('SUBJECT: '+str(folder))
                trials: Dict[str, FileMetadata] = self.index.getImmediateChildren(
                    folder+'trials/')
                for trialName in trials:
                    print('TRIAL: '+str(trialName))
                    trial = TrialToProcess(self.index, folder, trialName)
                    if trial.shouldProcess():
                        shouldProcessTrials.append(trial)

        # 2. Sort Trials oldest to newest
        shouldProcessTrials.sort(key=lambda x: x.latestInputTimestamp())

        # 3. Update the queue. There's another thread that busy-waits on the queue changing, that can then grab a queue entry and continue
        self.queue = shouldProcessTrials

    def processQueueForever(self):
        """
        This busy-waits on the queue updating, and will process the head of the queue one at a time when it becomes available.

        While processing, this blocks, so even though the queue is updating in the background, that shouldn't change the outcome of this process.
        """
        while True:
            if len(self.queue) > 0:
                nextUp = self.queue[0]
                # This will update the state of S3, which will in turn update and remove this element from our queue automatically.
                # If it doesn't, then perhaps something went wrong and it's actually fine to process again. So the key idea is DON'T
                # MANUALLY MANAGE THE WORK QUEUE! That happens in self.onChange()
                nextUp.process()
                # We need to avoid race conditions with S3 by not immediately processing the next item. Give S3 a chance to update.
                print(
                    'Sleeping for 10 seconds before attempting to process the next item...')
                time.sleep(10)
                print('Done sleeping')
            else:
                time.sleep(1)


if __name__ == "__main__":
    # 1. Launch a processing server
    server = MocapServer()

    # 2. Run forever
    server.processQueueForever()
