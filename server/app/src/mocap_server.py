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
import boto3
import threading
import argparse
from typing import Tuple


def absPath(path: str):
    root_file_path = os.path.join(os.getcwd(), sys.argv[0])
    absolute_path = os.path.join(os.path.dirname(root_file_path), path)
    return absolute_path


class TrialToProcess:
    index: ReactiveS3Index

    trialName: str
    trialPath: str

    # Trial files
    c3dFile: str
    trcFile: str
    grfFile: str
    goldIKFile: str
    resultsFile: str
    previewBinFile: str
    plotCSVFile: str

    def __init__(self, index: ReactiveS3Index, subjectPath: str, trialName: str) -> None:
        self.index = index
        if not subjectPath.endswith('/'):
            subjectPath += '/'
        self.trialName = trialName
        if not self.trialName.endswith('/'):
            self.trialName += '/'
        self.trialPath = subjectPath + 'trials/' + self.trialName

        # Trial files
        self.c3dFile = self.trialPath + 'markers.c3d'
        self.trcFile = self.trialPath + 'markers.trc'
        self.grfFile = self.trialPath + 'grf.mot'
        self.goldIKFile = self.trialPath + 'manual_ik.mot'
        self.previewBinFile = self.trialPath + 'preview.bin.zip'
        self.plotCSVFile = self.trialPath + 'plot.csv'

    def download(self, trialsFolderPath: str):
        trialPath = trialsFolderPath + self.trialName
        os.mkdir(trialPath)

        if self.index.exists(self.c3dFile):
            self.index.download(self.c3dFile, trialPath+'markers.c3d')
        if self.index.exists(self.trcFile):
            self.index.download(self.trcFile, trialPath+'markers.trc')
        if self.index.exists(self.grfFile):
            self.index.download(self.grfFile, trialPath+'grf.mot')
        if self.index.exists(self.goldIKFile):
            self.index.download(self.goldIKFile, trialPath+'manual_ik.mot')

    def upload(self, trialsFolderPath: str):
        trialPath = trialsFolderPath + self.trialName
        # Recursively list all the files in the trial folder, and upload them
        for root, dirs, files in os.walk(trialPath):
            for file in files:
                # Skip the files we've already uploaded
                if file in ['_results.json', 'preview.bin.zip', 'plot.csv']:
                    continue
                # Skip the files we don't want to upload
                if file.endswith('.c3d') or file.endswith('.trc') or file.endswith('.mot'):
                    continue
                file_path = os.path.join(root, file)
                relative_path = file_path.replace(trialPath, '')
                if relative_path.startswith('/'):
                    relative_path = relative_path[1:]
                self.index.uploadFile(self.trialPath + relative_path, file_path)

    def hasMarkers(self) -> bool:
        return self.index.exists(self.c3dFile) or self.index.exists(self.trcFile)

    def latestInputTimestamp(self) -> int:
        if self.index.exists(self.c3dFile):
            uploadedTimestamp = self.index.getMetadata(
                self.c3dFile).lastModified
            if self.index.exists(self.goldIKFile):
                uploadedTimestamp = max(
                    uploadedTimestamp, self.index.getMetadata(self.goldIKFile).lastModified)
            return uploadedTimestamp
        elif self.index.exists(self.trcFile):
            uploadedTimestamp = self.index.getMetadata(
                self.trcFile).lastModified
            if self.index.exists(self.grfFile):
                uploadedTimestamp = max(
                    uploadedTimestamp, self.index.getMetadata(self.grfFile).lastModified)
            if self.index.exists(self.goldIKFile):
                uploadedTimestamp = max(
                    uploadedTimestamp, self.index.getMetadata(self.goldIKFile).lastModified)
            return uploadedTimestamp
        else:
            return 0


class SubjectToProcess:
    index: ReactiveS3Index

    subjectPath: str
    subjectName: str

    # Subject files
    subjectStatusFile: str
    opensimFile: str
    goldscalesFile: str
    readyFlagFile: str
    processingFlagFile: str
    resultsFile: str
    errorsFile: str
    logfile: str

    # Trial objects
    trials: Dict[str, TrialToProcess]

    def __init__(self, index: ReactiveS3Index, subjectPath: str) -> None:
        self.index = index
        self.subjectPath = subjectPath
        if not self.subjectPath.endswith('/'):
            self.subjectPath += '/'

        parts = self.subjectPath.split('/')
        self.subjectName = parts[-2]

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
        self.dynamicsFlagFile = self.subjectPath + 'DYNAMICS'
        self.queuedOnSlurmFlagFile = self.subjectPath + 'SLURM'
        self.processingFlagFile = self.subjectPath + 'PROCESSING'
        self.errorFlagFile = self.subjectPath + 'ERROR'
        self.resultsFile = self.subjectPath + '_results.json'
        self.errorsFile = self.subjectPath + '_errors.json'
        self.osimResults = self.subjectPath + self.subjectName + '.zip'
        self.pytorchResults = self.subjectPath + self.subjectName + '.b3d'
        self.logfile = self.subjectPath + 'log.txt'

    def sendNotificationEmail(self, email: str, name: str, path: str):
        ses_client = boto3.client("ses", region_name="us-west-2")
        CHARSET = "UTF-8"

        response = ses_client.send_email(
            Destination={
                "ToAddresses": [
                    email,
                ],
            },
            Message={
                "Body": {
                    "Text": {
                        "Charset": CHARSET,
                        "Data":  "Your subject \"{0}\" has finished processing. Visit https://addbiomechanics.org/my_data/{1} to view and download. You can view in-browser visualizations of the uploaded trial data by clicking on each trial name.\n\nThank you for using AddBiomechanics!\n-AddBiomechanics team\n\nP.S: Do not reply to this email. To give feedback on AddBiomechanics or if you have questions, please visit the AddBiomechanics forum on SimTK: https://simtk.org/plugins/phpBB/indexPhpbb.php?group_id=2402&pluginname=phpBB".format(name, path)
                    }
                },
                "Subject": {
                    "Charset": CHARSET,
                    "Data": "AddBiomechanics: \"{0}\" Finished Processing".format(name),
                },
            },
            Source="noreply@addbiomechanics.org",
        )

    def getHref(self):
        # and example self.subjectPath, for reference:
        #
        # protected/us-west-2:35e1c7ca-cc58-457e-bfc5-f6161cc7278b/data/SprinterTest/
        if self.subjectPath.startswith('private'):
            return '<private_file>'

        filteredPath = self.subjectPath.replace('protected/us-west-2:', '')
        parts = filteredPath.split('/')
        if len(parts) < 3:
            return '<error>'

        userId = parts[0]
        filePath = '/'.join(parts[2:])

        if self.index.deployment == 'DEV':
            return 'https://dev.addbiomechanics.org/data/'+userId+'/'+filePath
        else:
            return 'https://app.addbiomechanics.org/data/'+userId+'/'+filePath

    def markAsQueuedOnSlurm(self):
        """
        This marks a subject as having been queued for processing on a slurm cluster
        """
        self.index.uploadText(self.queuedOnSlurmFlagFile, '')

    def markAsNotQueuedOnSlurm(self):
        """
        This un-marks a subject that was previously queued on the slurm cluster, because something went wrong
        """
        self.index.delete(self.queuedOnSlurmFlagFile)

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
            if self.index.exists(self.opensimFile):
                self.index.download(self.opensimFile, path +
                                    'unscaled_generic.osim')
            if self.index.exists(self.goldscalesFile):
                self.index.download(self.goldscalesFile,
                                    path+'manually_scaled.osim')
            trialsFolderPath = path + 'trials/'
            os.mkdir(trialsFolderPath)
            for trialName in self.trials:
                self.trials[trialName].download(trialsFolderPath)

            print('Done downloading, ready to process', flush=True)

            # 3. That download can take a while, so re-up our processing soft-lock
            self.pushProcessingFlag(procLogTopic)

            # 4. Launch a processing process
            enginePath = absPath('../../engine/src/engine.py')
            print('Calling Command:\n'+enginePath+' ' +
                  path+' '+self.subjectName+' '+self.getHref(), flush=True)
            with open(path + 'log.txt', 'wb+') as logFile:
                with subprocess.Popen([enginePath, path, self.subjectName, self.getHref()], stdout=subprocess.PIPE) as proc:
                    print('Process created: '+str(proc.pid), flush=True)

                    unflushedLines: List[str] = []
                    lastFlushed = time.time()
                    for lineBytes in iter(proc.stdout.readline, b''):
                        if lineBytes is None and proc.poll() is not None:
                            break
                        line = lineBytes.decode("utf-8")
                        print('>>> '+str(line).strip(), flush=True)
                        # Send to the log
                        logFile.write(lineBytes)
                        # Add it to the queue
                        unflushedLines.append(line)

                        now = time.time()
                        elapsedSeconds = now - lastFlushed

                        # Only flush in bulk, and only every 3 seconds
                        if elapsedSeconds > 3.0 and len(unflushedLines) > 0:
                            # Send to PubSub, in packets of at most 20 lines at a time
                            if len(unflushedLines) > 20:
                                toSend = unflushedLines[:20]
                                logLine: Dict[str, str] = {}
                                logLine['lines'] = toSend
                                logLine['timestamp'] = now * 1000
                                try:
                                    self.index.pubSub.sendMessage(
                                        '/LOG/'+procLogTopic, logLine)
                                except e:
                                    print(
                                        'Failed to send live log message: '+str(e), flush=True)
                                unflushedLines = unflushedLines[20:]
                                # Explicitly do NOT reset lastFlushed on this branch, because we want to immediately send the next batch of lines, until we've exhausted the queue.
                            else:
                                logLine: Dict[str, str] = {}
                                logLine['lines'] = unflushedLines
                                logLine['timestamp'] = now * 1000
                                try:
                                    self.index.pubSub.sendMessage(
                                        '/LOG/'+procLogTopic, logLine)
                                except e:
                                    print(
                                        'Failed to send live log message: '+str(e), flush=True)
                                unflushedLines = []
                                # Reset lastFlushed, because we've sent everything, and we want to wait 3 seconds before sending again.
                                lastFlushed = now
                    # Wait for the process to exit
                    exitCode = 'Failed to exit after 60 seconds'
                    for i in range(20):
                        try:
                            exitCode = proc.wait(timeout=3)
                            break
                        except e:
                            line = 'Process has not exited!! Waiting another 3 seconds for the process to exit.'
                            logFile.write(line)
                            print('>>> '+line)
                            # Send to PubSub
                            logLine: Dict[str, str] = {}
                            logLine['line'] = line
                            logLine['timestamp'] = time.time() * 1000
                            try:
                                self.index.pubSub.sendMessage(
                                    '/LOG/'+procLogTopic, logLine)
                            except e:
                                print('Failed to send live log message: ' +
                                      str(e), flush=True)
                    line = 'exit: '+str(exitCode)
                    # Send to the log
                    logFile.write(line.encode("utf-8"))
                    # Send to PubSub
                    logLine: Dict[str, str] = {}
                    logLine['line'] = line
                    logLine['timestamp'] = time.time() * 1000
                    try:
                        self.index.pubSub.sendMessage(
                            '/LOG/'+procLogTopic, logLine)
                    except e:
                        print('Failed to send live log message: ' +
                              str(e), flush=True)
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
                # 5.1. Upload the downloadable {self.subjectName}.zip file
                if os.path.exists(path + self.subjectName + '.zip'):
                    self.index.uploadFile(
                        self.osimResults, path + self.subjectName + '.zip')
                else:
                    print('WARNING! FILE NOT UPLOADED BECAUSE FILE NOT FOUND! ' +
                          path + self.subjectName + '.zip', flush=True)
                # 5.1.2. Upload the downloadable {self.subjectName}.b3d file, which can be loaded into PyTorch loaders
                if os.path.exists(path + self.subjectName + '.b3d'):
                    self.index.uploadFile(
                        self.pytorchResults, path + self.subjectName + '.b3d')

                # 5.2. Upload the _results.json file last, since that marks the trial as DONE on the frontend,
                # and it starts to be able
                if os.path.exists(path + '_results.json'):
                    self.index.uploadFile(
                        self.resultsFile, path + '_results.json')
                    # Load the results file, and look for the 'linearResidual' field to indicate that there was dynamics
                    # in the model. If there was, then we need to upload a DYNAMICS flag to the frontend to make it
                    # easier to sort datasets by whether they have dynamics or not.
                    with open(path + '_results.json') as results:
                        resultsJson = json.loads(results.read())
                        if 'linearResidual' in resultsJson:
                            self.index.uploadText(self.dynamicsFlagFile, '')
                else:
                    print('WARNING! FILE NOT UPLOADED BECAUSE FILE NOT FOUND! ' +
                          path + '_results.json', flush=True)

                with open(path+'_subject.json') as subj:
                    subjectJson = json.loads(subj.read())
                    if 'email' in subjectJson:
                        email = subjectJson['email']
                        if self.subjectPath.startswith('protected/') or self.subjectPath.startswith('private/'):
                            print('sending notification email to '+str(email))
                            print('subject path: '+str(self.subjectPath))
                            parts = self.subjectPath.split('/')
                            print('path parts: '+str(parts))
                            name = parts[-1]
                            if parts[-1] == '':
                                name = parts[-2]
                            print('name: '+str(name))
                            emailPath = '/'.join(parts[3:-1]
                                                 if parts[-1] == '' else parts[3:])
                            print('email path: '+str(emailPath))
                            emailPath = emailPath.replace(' ', '%20')
                            self.sendNotificationEmail(email, name, emailPath)
                        else:
                            print('Not sending notification email because subject path does not start with "protected/"'
                                  ' or "private/"')

                # 6. Clean up after ourselves
                shutil.rmtree(path, ignore_errors=True)
            else:
                if os.path.exists(path + '_errors.json'):
                    self.index.uploadFile(
                        self.errorsFile, path + '_errors.json')

                # TODO: We should probably re-upload a copy of the whole setup that led to the error
                # Let's upload a unique copy of the log to S3, so that we have it in case the user re-processes
                if os.path.exists(path + 'log.txt'):
                    self.index.uploadFile(self.subjectPath +
                                          'log_error_copy_' + str(time.time()) + '.txt', path + 'log.txt')
                else:
                    print('WARNING! FILE NOT UPLOADED BECAUSE FILE NOT FOUND! ' +
                          self.logfile, flush=True)

                # This uploads the ERROR flag
                self.pushError(exitCode)
            print('Finished processing, returning from process() method.', flush=True)
        except Exception as e:
            print('Caught exception in process(): {}'.format(e))

            # TODO: We should probably re-upload a copy of the whole setup that led to the error
            # Let's upload a unique copy of the log to S3, so that we have it in case the user re-processes
            if os.path.exists(path + 'log.txt'):
                self.index.uploadFile(self.subjectPath +
                                      'log_error_copy_' + str(time.time()) + '.txt', path + 'log.txt')

            # This uploads the ERROR flag
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
        if not self.index.exists(self.processingFlagFile) and not self.index.exists(self.queuedOnSlurmFlagFile):
            return True
        # If there's already a processing flag, we need to check how old it is. Servers are
        # allowed to crash without finishing processing, so they're supposed to re-up their lock
        # on the PROCESSING file every minute or so. If they don't, then this is once again up for
        # grabs, and other servers can take it.
        # processLockTimestamp = self.index.getMetadata(
        #     self.processingFlagFile).lastModified
        # currentTimestamp = time.time() * 1000
        # lockAge = currentTimestamp - processLockTimestamp
        # # If the lock is older than 60 seconds, this is probably good to go
        # return lockAge > 60000

        # Don't pick up a file that already has a processing flag, cause timesteps are too unreliable
        return False

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
    currentlyProcessing: SubjectToProcess
    queue: List[SubjectToProcess]
    bucket: str
    deployment: str
    singularity_image_path: str

    # Status reporting quantities
    serverId: str
    lastUploadedStatusStr: str
    lastUploadedStatusTimestamp: float
    lastSeenPong: Dict[str, float]

    def __init__(self, bucket: str, deployment: str, singularity_image_path: str) -> None:
        self.bucket = bucket
        self.deployment = deployment
        self.singularity_image_path = singularity_image_path
        self.queue = []
        self.currentlyProcessing = None

        # Set up for status reporting
        self.serverId = str(uuid.uuid4())
        print('Booting as server ID: '+self.serverId)
        self.lastUploadedStatusStr = ''
        self.lastUploadedStatusTimestamp = 0
        self.lastSeenPong = {}

        # Set up index
        self.index = ReactiveS3Index(bucket, deployment)
        self.index.addChangeListener(self.onChange)
        self.index.refreshIndex()
        self.index.registerPubSub()
        # Subscribe to pings on the index
        self.index.pubSub.subscribe(
            "/PING/"+self.serverId, self.onPingReceived)
        self.index.pubSub.subscribe("/PONG/#", self.onPongReceived)

        cleanUpThread = threading.Thread(
            target=self.cleanUpOtherDeadServersForever, daemon=True)
        cleanUpThread.start()

        periodicRefreshThread = threading.Thread(
            target=self.periodicallyRefreshForever, daemon=True)
        periodicRefreshThread.start()

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

        # 2. Sort Trials. First we prioritize subjects that are not just copies in the "standardized" bucket, then
        # we sort oldest to newest. The sort method gets passed a Tuple, which goes left to right, True before False,
        # and low to high.
        shouldProcessSubjects.sort(key=lambda x: (
            x.subjectPath.startswith("standardized"), x.latestInputTimestamp()))

        # 3. Update the queue. There's another thread that busy-waits on the queue changing, that can then grab a queue entry and continue
        self.queue = shouldProcessSubjects

        for subject in self.queue:
            print('- should process: ' + str(subject.subjectPath))

        # 4. Update status file. Do this on another thread, to avoid deadlocking with the pubsub service when this is being called
        # inside a callback from a message, and then wants to send its own message out about updating the status file.
        t = threading.Thread(
            target=self.updateStatusFile, daemon=True)
        t.start()

    def onPingReceived(self, topic: str, payload: bytes):
        """
        This responds to liveness requests
        """
        print('Received liveness ping as '+self.serverId)
        # Reply with a pong on another thread, to avoid deadlocking the MQTT service (it doesn't like if you send a message from inside
        # a message callback)
        t = threading.Thread(
            target=self.sendPong, daemon=True)
        t.start()

    def sendPong(self):
        print('Sending liveness pong as '+self.serverId)
        try:
            self.index.pubSub.sendMessage(
                '/PONG/'+self.serverId, {})
        except e:
            print('Failed to send liveness pong: '+str(e))

    def onPongReceived(self, topic: str, payload: bytes):
        """
        This observes liveness responses, and notes the time so we can see how long it's been since a response
        """
        serverReporting: str = topic.replace(
            '/PONG/', '').replace('/DEV', '').replace('/PROD', '')
        print('Got pong from '+serverReporting)
        self.lastSeenPong[serverReporting] = time.time()

    def updateStatusFile(self):
        """
        This writes an updated version of our status file to S3, if anything has changed since our last write
        """
        status: Dict[str, Any] = {}
        if self.currentlyProcessing is not None:
            status['currently_processing'] = self.currentlyProcessing.subjectPath
        else:
            status['currently_processing'] = 'none'
        status['job_queue'] = [x.subjectPath for x in self.queue]
        statusStr: str = json.dumps(status)

        currentTimestamp = time.time()
        elapsedSinceUpload = currentTimestamp - self.lastUploadedStatusTimestamp

        if (statusStr != self.lastUploadedStatusStr) or (elapsedSinceUpload > 60):
            self.lastUploadedStatusStr = statusStr
            self.lastUploadedStatusTimestamp = currentTimestamp
            self.index.uploadText(
                'protected/server_status/'+self.serverId, statusStr)
            print('Uploaded updated status file: \n' + statusStr)

    def cleanUpOtherDeadServersForever(self):
        """
        This will spin, pinging anyone else whose server status files are still online at intervals, 
        and cleaning up servers that haven't responded for more than a configured timeout.
        """
        pingIntervalSeconds = 30
        deathIntervalSeconds = 60

        while True:
            statusFiles: Dict[str, FileMetadata] = self.index.getImmediateChildren(
                "protected/server_status/")

            # Send out pings
            for k in statusFiles:
                if k == self.serverId:
                    pass
                else:
                    # Send a ping, which will get an asynchronous response which will eventually update self.lastSeenPong[k]
                    try:
                        self.index.pubSub.sendMessage('/PING/'+k, {})
                    except e:
                        print('Failed to send ping to ' +
                              k+': '+str(e), flush=True)

            # Check for death
            for k in statusFiles:
                if k == self.serverId:
                    pass
                else:
                    if k not in self.lastSeenPong:
                        self.lastSeenPong[k] = time.time()
                    timeSincePong = time.time() - self.lastSeenPong[k]
                    if timeSincePong > deathIntervalSeconds:
                        print('Detected dead server: '+str(k), flush=True)
                        self.index.delete('protected/server_status/'+k)
                        print('Cleaned up status file for: '+str(k), flush=True)
                    else:
                        print('Server '+str(k)+' seen within '+str(timeSincePong) +
                              's < death interval '+str(deathIntervalSeconds)+'s, so still alive', flush=True)

            time.sleep(pingIntervalSeconds)

    def periodicallyRefreshForever(self):
        """
        This periodically refreshes the S3 index (every 30 minutes) just in case we missed anything
        """
        while True:
            time.sleep(30 * 60 * 60)
            print('Cueing an every ten minutes refresh', flush=True)
            self.index.refreshIndex()

    def getSlurmJobQueueLen(self) -> Tuple[int, int]:
        """
        This uses the `squeue` command to check how many jobs we currently have pending in the queue, if we're on the SLURM cluster.
        """
        if len(self.singularity_image_path) == 0:
            return 0, 0
        # Fetch all jobs for the user
        try:
            cmd_all_jobs = f"squeue -u $USER"
            all_jobs_output = subprocess.check_output(cmd_all_jobs, shell=True)
            all_jobs_output_str = all_jobs_output.decode(
                'utf-8')  # decode bytes to string
            all_lines = all_jobs_output_str.strip().splitlines()
            new_jobs = len([
                line for line in all_lines if self.deployment+'_new' in line])
            reprocessing_jobs = len([
                line for line in all_lines if self.deployment+'_re' in line])
            return new_jobs, reprocessing_jobs
        except Exception as e:
            print('Failed to get SLURM job queue length: '+str(e))
            return 0, 0

    def processQueueForever(self):
        """
        This busy-waits on the queue updating, and will process the head of the queue one at a time when it becomes available.

        While processing, this blocks, so even though the queue is updating in the background, that shouldn't change the outcome of this process.
        """
        while True:
            try:
                if len(self.queue) > 0:
                    self.currentlyProcessing = self.queue[0]
                    self.updateStatusFile()

                    # This will update the state of S3, which will in turn update and remove this element from our queue automatically.
                    # If it doesn't, then perhaps something went wrong and it's actually fine to process again. So the key idea is DON'T
                    # MANUALLY MANAGE THE WORK QUEUE! That happens in self.onChange()

                    if len(self.singularity_image_path) > 0:
                        reprocessing_job: bool = self.currentlyProcessing.subjectPath.startswith('standardized')

                        # SLURM has resource limits, and will fail to queue our job with sbatch if we're too greedy. So we need to check
                        # the queue length before we queue up a new job, and not queue up more than 15 jobs at a time (though the precise limit
                        # isn't documented anywhere, I figure 15 concurrent jobs per deployment (so 30 total between dev and prod) is probably a reasonable limit).
                        slurm_new_jobs, slurm_reprocessing_jobs = self.getSlurmJobQueueLen()
                        slurm_total_jobs = slurm_new_jobs + slurm_reprocessing_jobs
                        print('Queueing subject for processing on SLURM: ' +
                              self.currentlyProcessing.subjectPath)
                        # We always leave a few slots open for new jobs, since they're more important than reprocessing
                        if (reprocessing_job and slurm_reprocessing_jobs < 10) or \
                                (not reprocessing_job and slurm_total_jobs < 50):
                            # Mark the subject as having been queued in SLURM, so that we don't try to process it again
                            self.currentlyProcessing.markAsQueuedOnSlurm()
                            print('Queueing subject for processing on SLURM: ' +
                                  self.currentlyProcessing.subjectPath)
                            # Now launch a SLURM job to process this subject
                            # In an ideal world, we'd like to be able to use "--cpus 8 --memory 8G", but that throws
                            # an error on Sherlock.
                            raw_command = 'singularity run --env PROCESS_SUBJECT_S3_PATH="' + \
                                self.currentlyProcessing.subjectPath+'" '+self.singularity_image_path

                            job_name: str = self.deployment
                            if reprocessing_job:
                                job_name += '_re'
                            else:
                                job_name += '_new'

                            sbatch_command = 'sbatch -p owners --job-name ' + job_name + ' --cpus-per-task=8 --mem=64000M --time=4:00:00 --wrap="' + \
                                raw_command.replace('"', '\\"')+'"'
                            print('Running command: '+sbatch_command)
                            try:
                                subprocess.run(
                                    sbatch_command, shell=True, check=True)
                            except Exception as e:
                                # If we fail to queue, then we need to mark the subject as not queued, so that we can try again later
                                print('Failed to queue SLURM job: '+str(e))
                                self.currentlyProcessing.markAsNotQueuedOnSlurm()
                        else:
                            print(
                                'Not queueing subject for processing on SLURM, because the queue is too long. Waiting for some jobs to finish')
                    else:
                        # Launch the subject as a normal process on this local machine
                        self.currentlyProcessing.process()

                    # This helps our status thread to keep track of what we're doing
                    self.currentlyProcessing = None
                    self.updateStatusFile()

                    # We need to avoid race conditions with S3 by not immediately processing the next item. Give S3 a chance to update.
                    print(
                        'Sleeping for 10 seconds before attempting to process the next item...')
                    time.sleep(10)
                    print('Done sleeping')
                    self.onChange()
                else:
                    time.sleep(1)
            except Exception as e:
                print(
                    'Encountered an error!!! Sleeping for 10 seconds, then re-entering the processing loop')
                print(e)
                time.sleep(10)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run a mocap processing server.')
    parser.add_argument('--bucket', type=str, default="biomechanics-uploads161949-dev",
                        help='The S3 bucket to access user data in')
    parser.add_argument('--deployment', type=str,
                        default='DEV',
                        help='The deployment to target (must be DEV or PROD)')
    parser.add_argument('--singularity_image_path', type=str,
                        default='',
                        help='If set, this assumes we are running as a SLURM job, and will process subjects by launching child SLURM jobs that use a singularity image to run the processing server.')
    args = parser.parse_args()

    subjectPath = os.getenv('PROCESS_SUBJECT_S3_PATH', '')
    if len(subjectPath) > 0:
        # If we're launched with PROCESS_SUBJECT_S3_PATH set, then we'll only process the subject we're given, and then immediately exit.

        # 1. Set up the connection to S3 and PubSub
        index = ReactiveS3Index(args.bucket, args.deployment)
        index.refreshIndex()
        subject = SubjectToProcess(index, subjectPath)

        # 2. Process the subject, and then exit
        subject.process()
    else:
        # If PROCESS_SUBJECT_S3_PATH is not set, then launch the regular processing server

        # 1. Launch a processing server
        server = MocapServer(args.bucket, args.deployment,
                             args.singularity_image_path)

        # 2. Run forever
        server.processQueueForever()
