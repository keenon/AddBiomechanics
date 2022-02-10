from typing import Dict, List
from reactive_s3 import ReactiveS3Index, FileMetadata
import time
import tempfile
import os
import sys
import subprocess
import uuid
import json
import shutil


def absPath(path: str):
    root_file_path = os.path.join(os.getcwd(), sys.argv[0])
    absolute_path = os.path.join(os.path.dirname(root_file_path), path)
    return absolute_path


class TrialToProcess:
    index: ReactiveS3Index

    trialName: str
    trialPath: str

    # Trial files
    markersFile: str
    goldIKFile: str
    resultsFile: str
    previewJsonFile: str

    def __init__(self, index: ReactiveS3Index, subjectPath: str, trialName: str) -> None:
        self.index = index
        if not subjectPath.endswith('/'):
            subjectPath += '/'
        self.trialName = trialName
        if not self.trialName.endswith('/'):
            self.trialName += '/'
        self.trialPath = subjectPath + 'trials/' + self.trialName

        # Trial files
        self.markersFile = self.trialPath + 'markers.trc'
        self.goldIKFile = self.trialPath + 'manual_ik.mot'
        self.resultsFile = self.trialPath + '_results.json'
        self.previewJsonFile = self.trialPath + 'preview.json.zip'

    def download(self, trialsFolderPath: str):
        trialPath = trialsFolderPath + self.trialName
        os.mkdir(trialPath)

        self.index.download(self.markersFile, trialPath+'markers.trc')
        if self.index.exists(self.goldIKFile):
            self.index.download(self.goldIKFile, trialPath+'manual_ik.mot')

    def upload(self, trialsFolderPath: str):
        trialPath = trialsFolderPath + self.trialName
        if os.path.exists(trialPath + '_results.json'):
            self.index.uploadFile(
                self.resultsFile, trialPath + '_results.json')
        else:
            print('WARNING! FILE NOT UPLOADED BECAUSE FILE NOT FOUND! ' +
                  trialPath + '_results.json', flush=True)
        if os.path.exists(trialPath + 'preview.json.zip'):
            self.index.uploadFile(self.previewJsonFile,
                                  trialPath + 'preview.json.zip')
        else:
            print('WARNING! FILE NOT UPLOADED BECAUSE FILE NOT FOUND! ' +
                  trialPath + 'preview.json.zip', flush=True)

    def hasMarkers(self) -> bool:
        return self.index.exists(self.markersFile)

    def latestInputTimestamp(self) -> int:
        if not self.index.exists(self.markersFile):
            return 0
        uploadedTimestamp = self.index.getMetadata(
            self.markersFile).lastModified
        if self.index.exists(self.goldIKFile):
            uploadedTimestamp = max(
                uploadedTimestamp, self.index.getMetadata(self.goldIKFile).lastModified)
        return uploadedTimestamp


class SubjectToProcess:
    index: ReactiveS3Index

    subjectPath: str

    # Subject files
    subjectStatusFile: str
    opensimFile: str
    goldscalesFile: str
    readyFlagFile: str
    processingFlagFile: str
    resultsFile: str
    logfile: str

    # Trial objects
    trials: Dict[str, TrialToProcess]

    def __init__(self, index: ReactiveS3Index, subjectPath: str) -> None:
        self.index = index
        self.subjectPath = subjectPath
        if not self.subjectPath.endswith('/'):
            self.subjectPath += '/'

        # Subject files
        self.subjectStatusFile = self.subjectPath + '_subject.json'
        self.opensimFile = self.subjectPath + 'unscaled_generic.osim'
        self.goldscalesFile = self.subjectPath + 'manually_scaled.osim'

        self.trials = {}
        trialFiles: Dict[str, FileMetadata] = self.index.getImmediateChildren(
            self.subjectPath+'trials/')
        for trialName in trialFiles:
            self.trials[trialName] = TrialToProcess(
                self.index, self.subjectPath, trialName)

        # Trial files
        self.readyFlagFile = self.subjectPath + 'READY_TO_PROCESS'
        self.processingFlagFile = self.subjectPath + 'PROCESSING'
        self.errorFlagFile = self.subjectPath + 'ERROR'
        self.resultsFile = self.subjectPath + '_results.json'
        self.osimResults = self.subjectPath + 'osim_results.zip'
        self.logfile = self.subjectPath + 'log.txt'

    def process(self):
        """
        This tries to download the whole set of necessary files, launch the processor, and re-upload the results,
        while also managing the processing flag age.
        """
        print('Processing Subject '+str(self.subjectPath), flush=True)

        try:
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
            self.index.download(self.opensimFile, path+'unscaled_generic.osim')
            if self.index.exists(self.goldscalesFile):
                self.index.download(self.goldscalesFile,
                                    path+'manually_scaled.osim')
            trialsFolderPath = path + 'trials/'
            os.mkdir(trialsFolderPath)
            for trialName in self.trials:
                self.trials[trialName].download(trialsFolderPath)

            # 3. That download can take a while, so re-up our processing soft-lock
            self.pushProcessingFlag(procLogTopic)

            # 4. Launch a processing process
            enginePath = absPath('../engine/engine.py')
            print('Calling Command:\n'+enginePath+' '+path, flush=True)
            with open(path + 'log.txt', 'wb+') as logFile:
                with subprocess.Popen([enginePath, path], stdout=subprocess.PIPE) as proc:
                    print('Process created: '+str(proc.pid), flush=True)
                    for lineBytes in iter(proc.stdout.readline, b''):
                        if lineBytes is None and proc.poll() is not None:
                            break
                        line = lineBytes.decode("utf-8")
                        print('>>> '+str(line).strip(), flush=True)
                        # Send to the log
                        logFile.write(lineBytes)
                        # Send to PubSub
                        logLine: Dict[str, str] = {}
                        logLine['line'] = line
                        logLine['timestamp'] = time.time() * 1000
                        self.index.pubSub.sendMessage(
                            '/LOG/'+procLogTopic, logLine)
                    exitCode = proc.poll()
                    line = 'exit: '+str(exitCode)
                    # Send to the log
                    logFile.write(line.encode("utf-8"))
                    # Send to PubSub
                    logLine: Dict[str, str] = {}
                    logLine['line'] = line
                    logLine['timestamp'] = time.time() * 1000
                    self.index.pubSub.sendMessage(
                        '/LOG/'+procLogTopic, logLine)
                    print('Process return code: '+str(exitCode), flush=True)

            # 5. Upload the results back to S3
            if os.path.exists(path + 'log.txt'):
                self.index.uploadFile(self.logfile, path + 'log.txt')
            else:
                print('WARNING! FILE NOT UPLOADED BECAUSE FILE NOT FOUND! ' +
                      self.logfile, flush=True)

            if exitCode == 0:
                for trialName in self.trials:
                    self.trials[trialName].upload(trialsFolderPath)
                # 5.1. Upload the downloadable osim_results.zip file
                if os.path.exists(path + 'osim_results.zip'):
                    self.index.uploadFile(
                        self.osimResults, path + 'osim_results.zip')
                else:
                    print('WARNING! FILE NOT UPLOADED BECAUSE FILE NOT FOUND! ' +
                          path + 'osim_results.zip', flush=True)
                # 5.2. Upload the _results.json file last, since that marks the trial as DONE on the frontend,
                # and it starts to be able
                if os.path.exists(path + '_results.json'):
                    self.index.uploadFile(
                        self.resultsFile, path + '_results.json')
                else:
                    print('WARNING! FILE NOT UPLOADED BECAUSE FILE NOT FOUND! ' +
                          path + '_results.json', flush=True)

                # 6. Clean up after ourselves
                shutil.rmtree(path, ignore_errors=True)
            else:
                # TODO: We should probably re-upload a copy of the whole setup that led to the error
                # Let's upload a unique copy of the log to S3, so that we have it in case the user re-processes
                if os.path.exists(path + 'log.txt'):
                    self.index.uploadFile(self.subjectPath +
                                          'log_error_copy_' + str(time.time()) + '.txt', path + 'log.txt')
                else:
                    print('WARNING! FILE NOT UPLOADED BECAUSE FILE NOT FOUND! ' +
                          self.logfile, flush=True)

                self.pushError(exitCode)
        except Exception as e:
            print('Caught exception in process(): {}'.format(e))

            # TODO: We should probably re-upload a copy of the whole setup that led to the error
            # Let's upload a unique copy of the log to S3, so that we have it in case the user re-processes
            if os.path.exists(path + 'log.txt'):
                self.index.uploadFile(self.subjectPath +
                                      'log_error_copy_' + str(time.time()) + '.txt', path + 'log.txt')

            self.pushError(1)

    def pushProcessingFlag(self, procLogTopic: str):
        procData: Dict[str, str] = {}
        procData['logTopic'] = procLogTopic
        procData['timestamp'] = time.time() * 1000
        self.index.uploadText(self.processingFlagFile, json.dumps(procData))

    def pushError(self, exitCode: int):
        procData: Dict[str, str] = {}
        procData['exitCode'] = str(exitCode)
        procData['timestamp'] = time.time() * 1000
        self.index.uploadText(self.errorFlagFile, json.dumps(procData))

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
        If we've got both the markers file (at a minimum) and a 'READY_TO_PROCESS' flag, and no 'ERROR' flag, we could process this
        """
        allHaveMarkers = True
        for trialName in self.trials:
            if not self.trials[trialName].hasMarkers():
                allHaveMarkers = False
                break
        return self.index.exists(self.readyFlagFile) and allHaveMarkers and not self.index.exists(self.errorFlagFile)

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
        uploadedTimestamp = 0
        for trialName in self.trials:
            uploadedTimestamp = max(
                uploadedTimestamp, self.trials[trialName].latestInputTimestamp())
        return uploadedTimestamp

    def __repr__(self) -> str:
        return self.subjectPath + "::" + self.trialName + " uploaded @" + str(self.latestInputTimestamp())

    def __str__(self) -> str:
        return self.subjectPath + "::" + self.trialName + " uploaded @" + str(self.latestInputTimestamp())


class MocapServer:
    index: ReactiveS3Index
    queue: List[SubjectToProcess]

    def __init__(self) -> None:
        self.index = ReactiveS3Index()
        self.index.addChangeListener(self.onChange)
        self.index.refreshIndex()
        self.index.registerPubSub()

    def onChange(self):
        print('S3 CHANGED!')

        shouldProcessSubjects: List[SubjectToProcess] = []

        # 1. Collect all Trials
        for folder in self.index.listAllFolders():
            if self.index.hasChildren(folder, ['trials/', '_subject.json']):
                if not folder.endswith('/'):
                    folder += '/'
                subject = SubjectToProcess(self.index, folder)
                if subject.shouldProcess():
                    shouldProcessSubjects.append(subject)

        # 2. Sort Trials oldest to newest
        shouldProcessSubjects.sort(key=lambda x: x.latestInputTimestamp())

        # 3. Update the queue. There's another thread that busy-waits on the queue changing, that can then grab a queue entry and continue
        self.queue = shouldProcessSubjects

    def processQueueForever(self):
        """
        This busy-waits on the queue updating, and will process the head of the queue one at a time when it becomes available.

        While processing, this blocks, so even though the queue is updating in the background, that shouldn't change the outcome of this process.
        """
        while True:
            try:
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
            except Exception as e:
                print(
                    'Encountered an error!!! Sleeping for 10 seconds, then re-entering the processing loop')
                print(e)
                time.sleep(10)


if __name__ == "__main__":
    # 1. Launch a processing server
    server = MocapServer()

    # 2. Run forever
    server.processQueueForever()
