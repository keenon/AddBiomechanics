import boto3
from live_s3 import LiveS3
from mocap_s3 import Mocap, MocapSubject
import os


class Processor:
  def __init__(self):
    self.mocap = Mocap()
    subjects = self.mocap.rebuildIndex()
    print(subjects)
    for subject in subjects:
      print(subject.trialNames())
      # subject.processAllTrials()
    self.mocap.processAtRandom()
    """
    self.backing_folder = LiveS3()
    self.backing_folder.registerListeners()
    self.backing_folder.refreshIndex()
    # self.backing_folder.debug()
    # result = self.backing_folder.rootFolder.ensureChild(['public', 'data', 'Calibration', 'Subject1', '_status.json'])
    trialFolder = self.backing_folder.rootFolder.ensureChild(
        ['public', 'data', 'Calibration', 'Subject1', 'trials', '1'])
    statusFile = trialFolder.ensureChild(['_trial.json'])
    statusJson = statusFile.getJSON()
    print(statusJson)
    if statusJson['state'] == 'pending':
      statusJson['state'] = 'success'
    else:
      statusJson['state'] = 'pending'
    statusFile.uploadJSON(statusJson)
    """
    """
    with trialFolder.openLocally() as path:
      print(path)
      files = os.listdir(path)
      print(files)
      with open(path+'/_trial.json') as f:
        text = f.read()
        print(text)
      trialJson = trialFolder.ensureChild(['output.txt'])
      trialJson.uploadFile(path+'/_trial.json')
    """
    pass

  def findRandomUnprocessed(self):
    """
    This finds a random unprocessed subject off the list. The randomness is to attempt to avoid collisions, 
    if we have multiple processing servers running at once, but if collisions happen it's no big deal. If a
    server crashes while attempting to process the data, we don't want that to choke the system. The last 
    processor to finish processing data will overwrite the previous versions.
    """
    pass

  def processSubject(self, path: str):
    """
    This processes a subject, by downloading their data and running local processing code against it.
    """
    pass


proc = Processor()
proc.findRandomUnprocessed()
