#!/usr/bin/python3
import sys
import nimblephysics as nimble
import os
from nimblephysics.loader import absPath
import json
import time
from typing import Any, Dict, List, Tuple
import numpy as np
import subprocess
import shutil

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

    if not os.path.exists(GEOMETRY_FOLDER_PATH):
        print('ERROR: No folder at GEOMETRY_FOLDER_PATH=' +
              str(GEOMETRY_FOLDER_PATH))
        exit(1)

    # 1. Symlink in Geometry, if it doesn't come with the folder,
    # so we can load meshes for the visualizer
    if not os.path.exists(path + 'Geometry'):
        os.symlink(GEOMETRY_FOLDER_PATH, path + 'Geometry')

    # 2. Load the main subject JSON
    requireExists(path+'_subject.json', 'subject status file')
    with open(path+'_subject.json') as subj:
        subjectJson = json.loads(subj.read())
    print(subjectJson, flush=True)

    # 2.1. Get the basic measurements from _subject.json
    if 'massKg' in subjectJson:
        massKg = float(subjectJson['massKg'])
    else:
        print('!!WARNING!! No Mass specified for subject. Defaulting to 68 kg.')
        massKg = 68.0

    if 'heightM' in subjectJson:
        heightM = float(subjectJson['heightM'])
    else:
        print('!!WARNING!! No Height specified for subject. Defaulting to 1.6 m.')
        heightM = 1.6

    # 3. Load the unscaled Osim file, which we can then scale and format
    customOsim: nimble.biomechanics.OpenSimFile = nimble.biomechanics.OpenSimParser.parseOsim(
        path + 'unscaled_generic.osim')

    # 4. Load the hand-scaled Osim file, if it exists
    goldOsim: nimble.biomechanics.OpenSimFile = None
    if os.path.exists(path + 'manually_scaled.osim'):
        goldOsim = nimble.biomechanics.OpenSimParser.parseOsim(
            path + 'manually_scaled.osim')

    trialsFolderPath = path + 'trials/'
    if not os.path.exists(trialsFolderPath):
        print('ERROR: Trials folder "'+trialsFolderPath +
              '" does not exist. Quitting.')
        exit(1)

    trialNames = []
    c3dFiles = []
    markerTrials = []
    trialProcessingResults: List[Dict[str, Any]] = []

    for trialName in os.listdir(trialsFolderPath):
        trialNames.append(trialName)
        trialPath = trialsFolderPath + trialName + '/'
        trialProcessingResult: Dict[str, Any] = {}

        # Load the markers file
        markersFilePath = trialPath + 'markers.c3d'
        requireExists(markersFilePath, 'markers file')
        c3dFile: nimble.biomechanics.C3D = nimble.biomechanics.C3DLoader.loadC3D(
            markersFilePath)
        c3dFiles.append(c3dFile)
        markerTrials.append(c3dFile.markerTimesteps)

        # Load the gold .mot file, if one exists
        if os.path.exists(trialPath + 'manual_ik.mot') and goldOsim is not None:
            goldMot: nimble.biomechanics.OpenSimMot = nimble.biomechanics.OpenSimParser.loadMot(
                goldOsim.skeleton,
                trialPath + 'manual_ik.mot')

            originalIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
                goldOsim.skeleton, goldOsim.markersMap, goldMot.poses, c3dFile.markerTimesteps)
            print('manually scaled average RMSE cm: ' +
                  str(originalIK.averageRootMeanSquaredError), flush=True)
            print('manually scaled average max cm: ' +
                  str(originalIK.averageMaxError), flush=True)
            trialProcessingResult['goldAvgRMSE'] = originalIK.averageRootMeanSquaredError
            trialProcessingResult['goldAvgMax'] = originalIK.averageMaxError

        trialProcessingResults.append(trialProcessingResult)

    print('Fitting trials '+str(trialNames), flush=True)

    # 7. Process the trial
    fitter = nimble.biomechanics.MarkerFitter(
        customOsim.skeleton, customOsim.markersMap)
    fitter.setInitialIKSatisfactoryLoss(0.05)
    fitter.setInitialIKMaxRestarts(50)
    fitter.setIterationLimit(300)
    # fitter.setInitialIKMaxRestarts(1)
    # fitter.setIterationLimit(2)

    fitter.setTriadsToTracking()
    # This is 0.7x the values in the default code
    fitter.setRegularizeAnatomicalMarkerOffsets(0.7)
    # This is 1.0x the default value
    fitter.setRegularizeTrackingMarkerOffsets(0.05)
    # These are 2x the values in the default code
    fitter.setMinSphereFitScore(3e-5 * 2)
    fitter.setMinAxisFitScore(6e-5 * 2)

    # Create an anthropometric prior
    anthropometrics: nimble.biomechanics.Anthropometrics = nimble.biomechanics.Anthropometrics.loadFromFile(
        '/data/ANSUR_metrics.xml')
    cols = anthropometrics.getMetricNames()
    cols.append('Heightin')
    cols.append('Weightlbs')
    gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
        '/data/ANSUR_II_MALE_Public.csv',
        cols,
        0.001)  # mm -> m
    observedValues = {
        'Heightin': heightM * 39.37 * 0.001,
        'Weightlbs': massKg * 0.453 * 0.001,
    }
    gauss = gauss.condition(observedValues)
    anthropometrics.setDistribution(gauss)
    fitter.setAnthropometricPrior(anthropometrics, 0.1)

    # Run the kinematics pipeline
    results: List[nimble.biomechanics.MarkerInitialization] = fitter.runMultiTrialKinematicsPipeline(
        markerTrials, nimble.biomechanics.InitialMarkerFitParams(), 50)

    customOsim.skeleton.setGroupScales(results[0].groupScales)
    fitMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode,
                                np.ndarray]] = results[0].updatedMarkerMap

    # 8.2. Write out the usable OpenSim results

    if not os.path.exists(path+'results'):
        os.mkdir(path+'results')
    print('Outputting OpenSim files', flush=True)
    # 8.2.1. Write the XML instructions for the OpenSim scaling tool
    nimble.biomechanics.OpenSimParser.saveOsimScalingXMLFile(
        customOsim.skeleton, massKg, heightM, path + 'unscaled_generic.osim', path + 'results/rescaled.osim', path + 'scaling_instructions.xml')
    # 8.2.2. Call the OpenSim scaling tool
    command = 'opensim-cmd run-tool ' + path + 'scaling_instructions.xml'
    print('Scaling OpenSim files: '+command)
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()

    for i in range(len(results)):
        result = results[i]
        trialName = trialNames[i]
        c3dFile = c3dFiles[i]
        markerTimesteps = markerTrials[i]
        trialProcessingResult = trialProcessingResults[i]
        trialPath = path + 'trials/' + trialName + '/'

        resultIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
            customOsim.skeleton, fitMarkers, result.poses, markerTimesteps)
        trialProcessingResult['autoAvgRMSE'] = resultIK.averageRootMeanSquaredError
        trialProcessingResult['autoAvgMax'] = resultIK.averageMaxError

        # 8. Write out our result files

        # 8.1. Write out the result summary JSON
        print('Writing JSON result to '+trialPath+'_results.json', flush=True)
        with open(trialPath+'_results.json', 'w') as f:
            # The frontend expects JSON in this format
            # autoAvgMax: number;
            # autoAvgRMSE: number;
            # goldAvgMax: number;
            # goldAvgRMSE: number;
            json.dump(trialProcessingResult, f)

        # Write out the .mot files
        timestamps = [i * 0.001 for i in range(result.poses.shape[1])]
        print('Writing OpenSim '+path+'results/' +
              trialName+'.mot file, shape='+str(result.poses.shape), flush=True)
        nimble.biomechanics.OpenSimParser.saveMot(
            customOsim.skeleton, path + 'results/'+trialName+'.mot', timestamps, result.poses)

        # 8.2. Write out the animation preview
        # 8.2.1. Create the raw JSON
        print('Saving trajectory and markers to a GUI log ' +
              trialPath+'preview.json', flush=True)
        fitter.saveTrajectoryAndMarkersToGUI(
            trialPath+'preview.json', result, markerTimesteps, c3dFile)
        # 8.2.2. Zip it up
        print('Zipping up '+trialPath+'preview.json', flush=True)
        subprocess.run(["zip", "-r", trialPath+'preview.json.zip', trialPath +
                        'preview.json'], capture_output=True)
        print('Finished zipping up '+trialPath+' preview.json.zip', flush=True)

    print('Zipping up OpenSim files', flush=True)
    shutil.make_archive(path + 'osim_results', 'zip', path, 'results')
    print('Finished outputting OpenSim files', flush=True)

    # Generate the overall summary result
    autoTotalLen = 0
    goldTotalLen = 0
    processingResult['autoAvgRMSE'] = 0
    processingResult['autoAvgMax'] = 0
    processingResult['goldAvgRMSE'] = 0
    processingResult['goldAvgMax'] = 0
    for i in range(len(results)):
        trialLen = len(markerTrials[i])
        trialProcessingResult = trialProcessingResults[i]
        processingResult['autoAvgRMSE'] += trialProcessingResult['autoAvgRMSE'] * trialLen
        processingResult['autoAvgMax'] += trialProcessingResult['autoAvgMax'] * trialLen
        autoTotalLen += trialLen

        if 'goldAvgRMSE' in trialProcessingResult and 'goldAvgMax' in trialProcessingResult:
            processingResult['goldAvgRMSE'] += trialProcessingResult['goldAvgRMSE'] * trialLen
            processingResult['goldAvgMax'] += trialProcessingResult['goldAvgMax'] * trialLen
            goldTotalLen += trialLen
    processingResult['autoAvgRMSE'] /= autoTotalLen
    processingResult['autoAvgMax'] /= autoTotalLen
    if goldTotalLen > 0:
        processingResult['goldAvgRMSE'] /= goldTotalLen
        processingResult['goldAvgMax'] /= goldTotalLen

    # Write out the result summary JSON
    with open(path+'_results.json', 'w') as f:
        # The frontend expects JSON in this format
        # autoAvgMax: number;
        # autoAvgRMSE: number;
        # goldAvgMax: number;
        # goldAvgRMSE: number;
        json.dump(processingResult, f)

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
    # processLocalSubjectFolder("/tmp/tmpmnf2siae/")
    # processLocalSubjectFolder("/tmp/tmp_287z04g")
    # processLocalSubjectFolder("/tmp/tmp99d3lw9v/")
    processLocalSubjectFolder(sys.argv[1])
