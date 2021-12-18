#!/usr/bin/python3
import sys
import nimblephysics as nimble
import os
from nimblephysics.loader import absPath
import json
import time
from typing import Any, Dict, Tuple
import numpy as np
import subprocess

GEOMETRY_FOLDER_PATH = absPath('Geometry')


def requireExists(path: str, reason: str):
    if not os.path.exists(path):
        print('ERROR: File "'+path+'" required as "' +
              reason+'" does not exist. Quitting.')
        exit(1)


def processLocalSubjectFolder(path: str):
    if not path.endswith('/'):
        path += '/'

    processingResult: Dict[str, Any] = {}

    # 1. Symlink in Geometry, if it doesn't come with the folder,
    # so we can load meshes for the visualizer
    if not os.path.exists(path + 'Geometry'):
        os.symlink(GEOMETRY_FOLDER_PATH, path + 'Geometry')

    # 2. Load the main subject JSON
    requireExists(path+'_subject.json', 'subject status file')
    with open(path+'_subject.json') as subj:
        subjectJson = json.loads(subj.read())
    print(subjectJson, flush=True)

    # 3. Load the unscaled Osim file, which we can then scale and format
    customOsim: nimble.biomechanics.OpenSimFile = nimble.biomechanics.OpenSimParser.parseOsim(
        path + 'unscaled_generic.osim')

    # 4. Load the hand-scaled Osim file, if it exists
    goldOsim: nimble.biomechanics.OpenSimFile = None
    if os.path.exists(path + 'manually_scaled.osim'):
        goldOsim = nimble.biomechanics.OpenSimParser.parseOsim(
            path + 'manually_scaled.osim')

    # 5. Load the markers file
    markersFilePath = path + 'markers.trc'
    requireExists(markersFilePath, 'markers file')
    markerTrajectories: nimble.biomechanics.OpenSimTRC = nimble.biomechanics.OpenSimParser.loadTRC(
        markersFilePath)

    # 6. Load the gold .mot file, if one exists
    if os.path.exists(path + 'manual_ik.mot') and goldOsim is not None:
        goldMot: nimble.biomechanics.OpenSimMot = nimble.biomechanics.OpenSimParser.loadMot(
            goldOsim.skeleton,
            path + 'manual_ik.mot')

        originalIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
            goldOsim.skeleton, goldOsim.markersMap, goldMot.poses, markerTrajectories.markerTimesteps)
        print('manually scaled average RMSE cm: ' +
              str(originalIK.averageRootMeanSquaredError), flush=True)
        print('manually scaled average max cm: ' +
              str(originalIK.averageMaxError), flush=True)
        processingResult['goldAvgRMSE'] = originalIK.averageRootMeanSquaredError
        processingResult['goldAvgMax'] = originalIK.averageMaxError

    # 7. Process the trial
    fitter = nimble.biomechanics.MarkerFitter(
        customOsim.skeleton, customOsim.markersMap)
    fitter.setInitialIKSatisfactoryLoss(0.05)
    fitter.setInitialIKMaxRestarts(50)
    fitter.setIterationLimit(300)
    result: nimble.biomechanics.MarkerInitialization = fitter.runKinematicsPipeline(
        markerTrajectories.markerTimesteps, nimble.biomechanics.InitialMarkerFitParams())
    customOsim.skeleton.setGroupScales(result.groupScales)
    fitMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode,
                                np.ndarray]] = result.updatedMarkerMap
    resultIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
        customOsim.skeleton, fitMarkers, result.poses, markerTrajectories.markerTimesteps)
    processingResult['autoAvgRMSE'] = resultIK.averageRootMeanSquaredError
    processingResult['autoAvgMax'] = resultIK.averageMaxError

    # 8. Write out our result files

    # 8.1. Write out the result summary JSON
    with open(path+'_results.json', 'w') as f:
        # The frontend expects JSON in this format
        # autoAvgMax: number;
        # autoAvgRMSE: number;
        # goldAvgMax: number;
        # goldAvgRMSE: number;
        json.dump(processingResult, f)

    # 8.2. Write out the animation preview
    # 8.2.1. Create the raw JSON
    guiRecording = nimble.server.GUIRecording()
    for timestep in range(result.poses.shape[1]):
        customOsim.skeleton.setPositions(result.poses[:, timestep])
        guiRecording.renderSkeleton(customOsim.skeleton, 'result')
        guiRecording.saveFrame()
    guiRecording.writeFramesJson(path+'preview.json')
    # 8.2.2. Zip it up
    print('Zipping up preview.json', flush=True)
    subprocess.run(["zip", "-r", path+'preview.json.zip', path +
                   'preview.json'], capture_output=True)
    print('Finished zipping up preview.json.zip', flush=True)

    # counter = 0
    # while True:
    #     print('[For live log demo] Counting to 10: '+str(counter), flush=True)
    #     counter += 1
    #     time.sleep(1)
    #     if counter > 10:
    #         break
    print('Done!', flush=True)


if __name__ == "__main__":
    print(sys.argv)
    # processLocalSubjectFolder("/tmp/tmp_287z04g")
    processLocalSubjectFolder(sys.argv[1])
