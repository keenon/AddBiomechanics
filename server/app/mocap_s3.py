from __future__ import annotations
from live_s3 import LiveS3, LiveS3File
from typing import List, Dict
import os
import random
import subprocess
from nimblephysics.loader import absPath
import inotify.adapters
import inotify.constants


class MocapTrial:
  """
  This is meant to be a short-lived object, which is created and then discarded as part of working with the data.

  It makes ZERO EFFORT to stay in sync with the underlying S3 data.
  """
  folder: LiveS3File
  statusFile: LiveS3File

  def __init__(self, folder: LiveS3File):
    self.folder = folder
    self.statusFile = self.folder.getChild("_trial.json")

  def setState(self, state: str):
    statusJson = self.statusFile.getJSON()
    statusJson['state'] = state
    self.statusFile.uploadJSON(statusJson)

  def getState(self) -> str:
    statusJson = self.statusFile.getJSON()
    return statusJson['state']

  def process(self):
    self.setState('processing')
    with self.folder.openLocally() as path:
      print(os.listdir(path))
    self.setState('done')

  def couldProcess(self) -> bool:
    # TODO: check that result.mot is older than markers.trc
    return not self.folder.hasChild("result.mot")


class MocapSubject:
  """
  This is meant to be a short-lived object, which is created and then discarded as part of working with the data.

  It makes ZERO EFFORT to stay in sync with the underlying S3 data.
  """
  root: Mocap
  folder: LiveS3File
  statusFile: LiveS3File
  trialsFolder: LiveS3File

  def __init__(self, root: Mocap, folder: LiveS3File):
    self.root = root
    self.folder = folder
    self.statusFile = self.folder.getChild("_subject.json")
    self.trialsFolder = self.folder.getChild("trials")

  def setState(self, state: str):
    statusJson = self.statusFile.getJSON()
    statusJson['state'] = state
    self.statusFile.uploadJSON(statusJson)

  def getState(self) -> str:
    statusJson = self.statusFile.getJSON()
    return statusJson['state']

  def getTrial(self, trialName: str):
    return MocapTrial(self.folder.getChild("trials").getChild(trialName))

  def trialNames(self) -> List[str]:
    return self.folder.getChild("trials").children.keys()

  def process(self):
    with self.folder.openLocally() as path:
      enginePath = absPath('../engine/engine.py')
      with open(path + '/log.txt', 'wb+') as logFile:
        i = inotify.adapters.InotifyTree(
            path, mask=inotify.constants.IN_CLOSE_WRITE, block_duration_s=0.01)  # IN_ALL_EVENTS

        with subprocess.Popen([enginePath, path], stdout=subprocess.PIPE) as proc:
          for line in iter(proc.stdout.readline, b''):
            print('>>> '+str(line))
            logFile.write(line)

            # If this process isn't closed
            if proc.poll() == None:
              for event in i.event_gen(yield_nones=False, timeout_s=0.01):
                (_, type_names, folder_path, filename) = event
                pathParts = (folder_path[len(path):] + '/' + filename).split('/')
                if len(pathParts) > 0 and pathParts[0] == '':
                  pathParts.pop(0)
                print(pathParts)
                print(self.folder.children)
                child = self.folder.ensureChild(pathParts, createIfNotExists=False)
                print(child)
                fullPath = folder_path + '/' + filename
                child.uploadFile(fullPath)

  def couldProcess(self) -> bool:
    if len(self.trialNames()) == 0:
      return False
    for trial in self.trialNames():
      if self.getTrial(trial).couldProcess():
        return True
    return False

  def processTrial(self, trialName: str):
    trial = self.getTrial(trialName)
    trial.process()

  def download(self):
    self.folder.download()


class Mocap:
  backing_folder: LiveS3

  def __init__(self):
    self.backing_folder = LiveS3()
    self.backing_folder.registerListeners()
    self.backing_folder.refreshIndex()

  def rebuildIndex(self) -> List[MocapSubject]:
    subjects = []
    for f in self.backing_folder.allFiles():
      if f.hasChild("_subject.json"):
        subjects.append(MocapSubject(self, f))
    return subjects

  def processAtRandom(self):
    subjects = self.rebuildIndex()
    filtered = [sub for sub in subjects if sub.couldProcess()]
    print(filtered)
    if len(filtered) > 0:
      filtered[random.randint(0, len(filtered)-1)].process()
