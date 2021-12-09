#!/usr/bin/python3
import sys
import nimblephysics as nimble
import os
from nimblephysics.loader import absPath
import json
import time

GEOMETRY_FOLDER_PATH = absPath('Geometry')


def requireExists(path: str, reason: str):
  if not os.path.exists(path):
    print('ERROR: File "'+path+'" required as "'+reason+'" does not exist. Quitting.')
    exit(1)


def processLocalSubjectFolder(path: str):
  # 1. Symlink in Geometry, if it doesn't come with the folder,
  # so we can load meshes for the visualizer
  if not os.path.exists(path + '/Geometry'):
    os.symlink(GEOMETRY_FOLDER_PATH, path + '/Geometry')

  # 2. Load the main subject JSON
  requireExists(path+'/_subject.json', 'subject status file')
  with open(path+'/_subject.json') as subj:
    subjectJson = json.loads(subj.read())
  print(subjectJson)

  # 3. Load the unscaled Osim file, which we can then scale and format
  customOsim: nimble.biomechanics.OpenSimFile = None
  if subjectJson['genericOsimFile'] == 'custom':
    requireExists(path + '/' + (subjectJson['customGenericOsimFile']), 'custom unscaled .osim file')
    customOsim = nimble.biomechanics.OpenSimParser.parseOsim(
        path + '/' + (subjectJson['customGenericOsimFile']))
  elif subjectJson['genericOsimFile'] == 'rajagopal':
    customOsim = nimble.models.RajagopalHumanBodyModel()

  # TODO: for now, we assume the markers come bundled with the Osim file. Eventually,
  # it would be nice to provide the option to break those markers out as a separate XML

  # 4. Load the hand-scaled Osim file, if it exists
  goldOsim: nimble.biomechanics.OpenSimFile = None
  if 'manuallyScaledOsimFile' in subjectJson:
    requireExists(
        path + '/' + subjectJson['manuallyScaledOsimFile'],
        'manually scaled .osim file')
    goldOsim = nimble.biomechanics.OpenSimParser.parseOsim(
        path + '/' + (subjectJson['manuallyScaledOsimFile']))

  # 5. Load all the trials
  requireExists(path + '/trials', 'trials folder')
  for trialFolderName in os.listdir(path + '/trials'):
    trialFolderPath = path + '/trials/' + trialFolderName
    print(trialFolderPath)

    # 5.1. Load the trial JSON
    requireExists(trialFolderPath+'/_trial.json', 'trial status file')
    with open(trialFolderPath+'/_trial.json') as tri:
      trialJson = json.loads(tri.read())
    print(trialJson)

    # 5.2. Load the markers file
    markersFilePath = trialFolderPath + '/' + (trialJson['markersFile'])
    requireExists(markersFilePath, 'markers file')
    if markersFilePath.endswith('.trc'):
      markerTrajectories: nimble.biomechanics.OpenSimTRC = nimble.biomechanics.OpenSimParser.loadTRC(
          markersFilePath)

    # 5.3. Load the gold .mot file, if one exists
    if 'manualIKFile' in trialJson:
      requireExists(
          trialFolderPath + '/' + trialJson['manualIKFile'],
          'manually scaled .mot file')
      goldMot: nimble.biomechanics.OpenSimMot = nimble.biomechanics.OpenSimParser.loadMot(
          goldOsim.skeleton,
          trialFolderPath + '/' + trialJson['manualIKFile'])

      originalIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
          goldOsim.skeleton, goldOsim.markersMap, goldMot.poses, markerTrajectories.markerTimesteps)
      print('average RMSE: '+str(originalIK.averageRootMeanSquaredError))
      trialJson['goldAvgRMSE'] = originalIK.averageRootMeanSquaredError

    """ This is slow, so we skip this for now in setting up processing
    # 5.4. Process each trial separately
    fitter = nimble.biomechanics.MarkerFitter(customOsim.skeleton, customOsim.markersMap)
    fitter.setInitialIKSatisfactoryLoss(0.05)
    fitter.setInitialIKMaxRestarts(50)
    fitter.setIterationLimit(10)
    result: nimble.biomechanics.MarkerInitialization = fitter.runKinematicsPipeline(
        markerTrajectories.markerTimesteps, nimble.biomechanics.InitialMarkerFitParams())
    """

    # 5.5. Mark this trial as done processing
    trialJson['state'] = 'success'
    trialJson['lastProcessedMillis'] = round(time.clock_gettime_ns(time.CLOCK_REALTIME) / 1000000)
    with open(trialFolderPath+'/_trial.json', 'w') as f:
      json.dump(trialJson, f)


if __name__ == "__main__":
  print(sys.argv)
  # processLocalSubjectFolder("/tmp/tmp_287z04g")
  processLocalSubjectFolder(sys.argv[1])
