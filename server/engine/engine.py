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
import textwrap
import glob
import traceback
from plotting import plotIKResults, plotIDResults, plotMarkerErrors, plotGRFData

GEOMETRY_FOLDER_PATH = absPath('Geometry')
DATA_FOLDER_PATH = absPath('../data')


def requireExists(path: str, reason: str):
    if not os.path.exists(path):
        print('ERROR: File "'+path+'" required as "' +
              reason+'" does not exist. Quitting.')
        exit(1)


def processLocalSubjectFolder(path: str, outputName: str = None, href: str = ''):
    if not path.endswith('/'):
        path += '/'

    if outputName is None:
        outputName = 'osim_results'

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

    if 'sex' in subjectJson:
        sex = subjectJson['sex']
    else:
        print('!!WARNING!! No sex specified for subject. Defaulting to "unknown".')
        sex = 'unknown'

    if 'skeletonPreset' in subjectJson:
        skeletonPreset = subjectJson['skeletonPreset']
    else:
        print(
            '!!WARNING!! No skeletonPreset specified for subject. Defaulting to "custom".')
        skeletonPreset = 'custom'

    if 'exportSDF' in subjectJson:
        exportSDF = subjectJson['exportSDF']
    else:
        exportSDF = False

    if 'exportMJCF' in subjectJson:
        exportMJCF = subjectJson['exportMJCF']
    else:
        exportMJCF = False

    # Only export OpenSim files if we're not exporting MJCF or SDF files, since they use incompatible skeletons
    exportOSIM = not (exportMJCF or exportSDF)

    if 'ignoreJointLimits' in subjectJson:
        ignoreJointLimits = subjectJson['ignoreJointLimits']
    else:
        ignoreJointLimits = False

    if 'fitDynamics' in subjectJson:
        fitDynamics = subjectJson['fitDynamics']
    else:
        fitDynamics = False

    if 'residualsToZero' in subjectJson:
        residualsToZero = subjectJson['residualsToZero']
    else:
        residualsToZero = False

    if 'useReactionWheels' in subjectJson:
        useReactionWheels = subjectJson['useReactionWheels']
    else:
        useReactionWheels = False

    if 'tuneResidualLoss' in subjectJson:
        tuneResidualLoss = subjectJson['tuneResidualLoss']
    else:
        tuneResidualLoss = 1.0

    if 'shiftGRF' in subjectJson:
        shiftGRF = subjectJson['shiftGRF']
    else:
        shiftGRF = False

    if 'maxTrialsToSolveMassOver' in subjectJson:
        maxTrialsToSolveMassOver = subjectJson['maxTrialsToSolveMassOver']
    else:
        maxTrialsToSolveMassOver = 4

    if 'regularizeJointAcc' in subjectJson:
        regularizeJointAcc = subjectJson['regularizeJointAcc']
    else:
        regularizeJointAcc = 0

    if skeletonPreset == 'vicon' or skeletonPreset == 'cmu' or skeletonPreset == 'complete':
        footBodyNames = ['calcn_l', 'calcn_r']
    else:
        if 'footBodyNames' in subjectJson:
            footBodyNames = subjectJson['footBodyNames']
        else:
            footBodyNames = []

    # 3. Load the unscaled Osim file, which we can then scale and format

    # 3.0. Check for if we're using a preset OpenSim model, and if so, then copy that in
    if skeletonPreset == 'vicon':
        shutil.copy(DATA_FOLDER_PATH + '/PresetSkeletons/Rajagopal2015_ViconPlugInGait.osim',
                    path + 'unscaled_generic.osim')
    elif skeletonPreset == 'cmu':
        shutil.copy(DATA_FOLDER_PATH + '/PresetSkeletons/Rajagopal2015_CMUMarkerSet.osim',
                    path + 'unscaled_generic.osim')
    elif skeletonPreset == 'complete':
        shutil.copy(DATA_FOLDER_PATH + '/PresetSkeletons/CompleteHumanModel.osim',
                    path + 'unscaled_generic.osim')
    else:
        if skeletonPreset != 'custom':
            print('Unrecognized skeleton preset "'+str(skeletonPreset) +
                  '"! Behaving as though this is "custom"')
        if not os.path.exists(path + 'unscaled_generic.osim'):
            print('We are using a custom OpenSim skeleton, and yet there is no unscaled_generic.osim file present. Quitting.')
            exit(1)

    # 3.1. Rationalize CustomJoint's in the osim file
    shutil.move(path + 'unscaled_generic.osim',
                path + 'unscaled_generic_raw.osim')
    nimble.biomechanics.OpenSimParser.rationalizeJoints(
        path + 'unscaled_generic_raw.osim',
        path + 'unscaled_generic.osim')
    # 3.2. load the rational file
    customOsim: nimble.biomechanics.OpenSimFile = nimble.biomechanics.OpenSimParser.parseOsim(
        path + 'unscaled_generic.osim')
    customOsim.skeleton.autogroupSymmetricSuffixes()
    if customOsim.skeleton.getBodyNode("hand_r") is not None:
        customOsim.skeleton.setScaleGroupUniformScaling(
            customOsim.skeleton.getBodyNode("hand_r"))
    customOsim.skeleton.autogroupSymmetricPrefixes("ulna", "radius")

    skeleton = customOsim.skeleton
    markerSet = customOsim.markersMap

    # Output both SDF and MJCF versions of the skeleton, so folks in AI/graphics can use the results in packages they're familiar with
    if exportSDF or exportMJCF:
        print('Simplifying OpenSim skeleton to prepare for writing other skeleton formats', flush=True)
        mergeBodiesInto: Dict[str, str] = {}
        mergeBodiesInto['ulna_r'] = 'radius_r'
        mergeBodiesInto['ulna_l'] = 'radius_l'
        customOsim.skeleton.setPositions(
            np.zeros(customOsim.skeleton.getNumDofs()))
        simplified = customOsim.skeleton.simplifySkeleton(
            customOsim.skeleton.getName(), mergeBodiesInto)
        simplified.setPositions(np.zeros(simplified.getNumDofs()))
        skeleton = simplified

        simplifiedMarkers = {}
        for key in markerSet:
            simplifiedMarkers[key] = (simplified.getBodyNode(
                markerSet[key][0].getName()), markerSet[key][1])
        markerSet = simplifiedMarkers

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

    # 7. Process the trial
    markerFitter = nimble.biomechanics.MarkerFitter(
        skeleton, markerSet)
    markerFitter.setInitialIKSatisfactoryLoss(0.005)
    markerFitter.setInitialIKMaxRestarts(50)
    # markerFitter.setIterationLimit(40)
    markerFitter.setIterationLimit(500)
    markerFitter.setIgnoreJointLimits(ignoreJointLimits)

    guessedTrackingMarkers = False
    if len(customOsim.anatomicalMarkers) > 10:
        markerFitter.setTrackingMarkers(customOsim.trackingMarkers)
    else:
        print('NOTE: The input *.osim file specified suspiciously few ('+str(len(customOsim.anatomicalMarkers)) +
              ', less than the minimum 10) anatomical landmark markers (with <fixed>true</fixed>), so we will default to treating all markers as anatomical except triad markers with the suffix "1", "2", or "3"', flush=True)
        markerFitter.setTriadsToTracking()
        guessedTrackingMarkers = True
    # This is 1.0x the values in the default code
    markerFitter.setRegularizeAnatomicalMarkerOffsets(10.0)
    # This is 1.0x the default value
    markerFitter.setRegularizeTrackingMarkerOffsets(0.05)
    # These are 2x the values in the default code
    # fitter.setMinSphereFitScore(3e-5 * 2)
    # fitter.setMinAxisFitScore(6e-5 * 2)
    markerFitter.setMinSphereFitScore(0.01)
    markerFitter.setMinAxisFitScore(0.001)
    # Default max joint weight is 0.5, so this is 2x the default value
    markerFitter.setMaxJointWeight(1.0)

    trialNames = []
    c3dFiles: Dict[str, nimble.biomechanics.C3D] = {}
    trialForcePlates: List[List[nimble.biomechanics.ForcePlate]] = []
    trialTimestamps: List[List[float]] = []
    trialFramesPerSecond: List[int] = []
    trialMarkerSet: Dict[str, List[str]] = {}
    markerTrials = []
    trialProcessingResults: List[Dict[str, Any]] = []

    for trialName in os.listdir(trialsFolderPath):
        trialNames.append(trialName)
        trialPath = trialsFolderPath + trialName + '/'
        trialProcessingResult: Dict[str, Any] = {}

        # Load the markers file
        c3dFilePath = trialPath + 'markers.c3d'
        trcFilePath = trialPath + 'markers.trc'

        if os.path.exists(c3dFilePath):
            c3dFile: nimble.biomechanics.C3D = nimble.biomechanics.C3DLoader.loadC3D(
                c3dFilePath)
            nimble.biomechanics.C3DLoader.fixupMarkerFlips(c3dFile)
            markerFitter.autorotateC3D(c3dFile)
            c3dFiles[trialName] = c3dFile
            trialForcePlates.append(c3dFile.forcePlates)
            trialTimestamps.append(c3dFile.timestamps)
            trialFramesPerSecond.append(c3dFile.framesPerSecond)
            trialMarkerSet[trialName] = c3dFile.markers
            markerTrials.append(c3dFile.markerTimesteps)
        elif os.path.exists(trcFilePath):
            trcFile: nimble.biomechanics.OpenSimTRC = nimble.biomechanics.OpenSimParser.loadTRC(
                trcFilePath)
            markerTrials.append(trcFile.markerTimesteps)
            trialTimestamps.append(trcFile.timestamps)
            trialFramesPerSecond.append(trcFile.framesPerSecond)
            trialMarkerSet[trialName] = list(trcFile.markerLines.keys())
            grfFilePath = trialPath + 'grf.mot'
            if os.path.exists(grfFilePath):
                forcePlates: List[nimble.biomechanics.ForcePlate] = nimble.biomechanics.OpenSimParser.loadGRF(
                    grfFilePath, trcFile.framesPerSecond)
                trialForcePlates.append(forcePlates)
            else:
                print('Warning: No ground reaction forces specified for '+trialName)
                trialForcePlates.append([])
        else:
            print('ERROR: No marker files exist for trial '+trialName+'. Checked both ' +
                  c3dFilePath+' and '+trcFilePath+', neither exist. Quitting.')
            exit(1)

        trialProcessingResults.append(trialProcessingResult)

    print('Fitting trials '+str(trialNames), flush=True)

    trialErrorReports: List[str, nimble.biomechanics.MarkersErrorReport] = []
    anyHasTooFewMarkers = False
    totalFrames = 0
    for i in range(len(trialNames)):
        print('Checking and repairing marker data quality on trial ' +
              str(trialNames[i])+'. This can take a while, depending on trial length...', flush=True)
        trialErrorReport = markerFitter.generateDataErrorsReport(
            markerTrials[i], 1.0 / trialFramesPerSecond[i])
        markerTrials[i] = trialErrorReport.markerObservationsAttemptedFixed
        trialErrorReports.append(trialErrorReport)
        hasEnoughMarkers = markerFitter.checkForEnoughMarkers(markerTrials[i])
        totalFrames += len(markerTrials[i])
        if not hasEnoughMarkers:
            print("There are fewer than 8 markers that show up in the OpenSim model and in trial " +
                  trialNames[i], flush=True)
            print("The markers in this trial are: " +
                  str(trialMarkerSet[trialNames[i]]), flush=True)
            anyHasTooFewMarkers = True
    if anyHasTooFewMarkers:
        print(
            "Some trials don't match the OpenSim model's marker set. Quitting.", flush=True)
        exit(1)
    print('All trial markers have been cleaned up!', flush=True)

    # Create an anthropometric prior
    anthropometrics: nimble.biomechanics.Anthropometrics = nimble.biomechanics.Anthropometrics.loadFromFile(
        DATA_FOLDER_PATH + '/ANSUR_metrics.xml')
    cols = anthropometrics.getMetricNames()
    cols.append('Heightin')
    cols.append('Weightlbs')
    if sex == 'male':
        gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
            DATA_FOLDER_PATH + '/ANSUR_II_MALE_Public.csv',
            cols,
            0.001)  # mm -> m
    elif sex == 'female':
        gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
            DATA_FOLDER_PATH + '/ANSUR_II_FEMALE_Public.csv',
            cols,
            0.001)  # mm -> m
    else:
        gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
            DATA_FOLDER_PATH + '/ANSUR_II_BOTH_Public.csv',
            cols,
            0.001)  # mm -> m
    observedValues = {
        'Heightin': heightM * 39.37 * 0.001,
        'Weightlbs': massKg * 2.204 * 0.001,
    }
    gauss = gauss.condition(observedValues)
    anthropometrics.setDistribution(gauss)
    markerFitter.setAnthropometricPrior(anthropometrics, 0.1)

    # Run the kinematics pipeline
    results: List[nimble.biomechanics.MarkerInitialization] = markerFitter.runMultiTrialKinematicsPipeline(
        markerTrials,
        nimble.biomechanics.InitialMarkerFitParams()
        .setMaxTrialsToUseForMultiTrialScaling(5)
        .setMaxTimestepsToUseForMultiTrialScaling(4000),
        150)

    # Set the masses based on the change in mass of the model
    unscaledSkeletonMass = skeleton.getMass()
    massScaleFactor = massKg / unscaledSkeletonMass
    print(f'Unscaled skeleton mass: {unscaledSkeletonMass}')
    print(f'Mass scale factor: {massScaleFactor}')
    for ibody in range(skeleton.getNumBodyNodes()):
        body = skeleton.getBodyNode(ibody)
        body.setMass(body.getMass() * massScaleFactor)

    err_msg = (f'ERROR: expected final skeleton mass to equal {massKg} kg after scaling, '
               f'but the final mass is {skeleton.getMass()}')
    np.testing.assert_almost_equal(skeleton.getMass(), massKg, err_msg=err_msg, decimal=1e-3)

    # Check for any flipped markers, now that we've done a first pass
    anySwapped = False
    for i in range(len(trialNames)):
        if markerFitter.checkForFlippedMarkers(markerTrials[i], results[i], trialErrorReports[i]):
            anySwapped = True
            markerTrials[i] = trialErrorReports[i].markerObservationsAttemptedFixed

    if anySwapped:
        print("******** Unfortunately, it looks like some markers were swapped in the uploaded data, so we have to run the whole pipeline again with unswapped markers. ********", flush=True)
        results = markerFitter.runMultiTrialKinematicsPipeline(
            markerTrials,
            nimble.biomechanics.InitialMarkerFitParams()
            .setMaxTrialsToUseForMultiTrialScaling(5)
            .setMaxTimestepsToUseForMultiTrialScaling(4000),
            150)

    skeleton.setGroupScales(results[0].groupScales)
    fitMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode,
                                np.ndarray]] = results[0].updatedMarkerMap

    # Set up some interchangeable data structures, so that we can write out the results using the same code, regardless of whether we used dynamics or not
    finalSkeleton = skeleton
    finalPoses = [result.poses for result in results]
    finalMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode,
                                  np.ndarray]] = fitMarkers
    finalInverseDynamics = []

    # If we've got ground reaction force data, and we enabled dynamics, then run the dynamics pipeline
    if fitDynamics:
        print('******** EXPERIMENTAL! Attempting to fit dynamics... ********', flush=True)
        totalForce = 0.0
        for forcePlateList in trialForcePlates:
            for forcePlate in forcePlateList:
                totalForce += sum([np.linalg.norm(f)
                                  for f in forcePlate.forces])

        if len(footBodyNames) == 0:
            print(
                'ERROR: No foot bodies were specified, so we have to quit dynamics fitter early', flush=True)
            fitDynamics = False
        elif len(trialForcePlates) == 0:
            print(
                'ERROR: No force plates were specified, so we have to quit dynamics fitter early', flush=True)
            fitDynamics = False
        elif abs(totalForce) < 1e-10:
            print(
                'ERROR: force plate data has zero forces, so we have to quit dynamics fitter early', flush=True)
            fitDynamics = False
        else:
            footBodies = []
            for name in footBodyNames:
                foot = finalSkeleton.getBodyNode(name)
                if foot is None:
                    print('ERROR: foot "' + str(name) +
                          '" not found in skeleton! Dynamics fitter will break as a result.', flush=True)
                footBodies.append(finalSkeleton.getBodyNode(name))

            finalSkeleton.setGravity([0, -9.81, 0])
            dynamicsFitter = nimble.biomechanics.DynamicsFitter(
                finalSkeleton, footBodies, customOsim.trackingMarkers)
            dynamicsInit: nimble.biomechanics.DynamicsInitialization = nimble.biomechanics.DynamicsFitter.createInitialization(
                finalSkeleton,
                results,
                customOsim.trackingMarkers,
                footBodies,
                trialForcePlates,
                trialFramesPerSecond,
                markerTrials)
            dynamicsFitter.estimateFootGroundContacts(dynamicsInit)

            print("Initial mass: " +
                  str(finalSkeleton.getMass()) + " kg", flush=True)
            print("What we'd expect average ~GRF to be (Mass * 9.8): " +
                  str(finalSkeleton.getMass() * 9.8) + " N", flush=True)
            secondPair = dynamicsFitter.computeAverageRealForce(dynamicsInit)
            print("Avg Force: " + str(secondPair[0]) + " N", flush=True)
            print("Avg Torque: " + str(secondPair[1]) + " Nm", flush=True)

            dynamicsFitter.boundPush(dynamicsInit)
            dynamicsFitter.smoothAccelerations(dynamicsInit)
            initializeSuccess = dynamicsFitter.timeSyncAndInitializePipeline(
                dynamicsInit,
                useReactionWheels=useReactionWheels,
                shiftGRF=shiftGRF,
                maxTrialsToSolveMassOver=maxTrialsToSolveMassOver
            )

            # If initialization succeeded, we will proceed with the kitchen sink optimization.
            # If not, we will re-run timeSyncAndInitializePipeline() with reaction wheels.
            if initializeSuccess:
                goodFramesCount = 0
                totalFramesCount = 0
                for trialMissingGRF in dynamicsInit.probablyMissingGRF:
                    goodFramesCount += sum(
                        [0 if missing else 1 for missing in trialMissingGRF])
                    totalFramesCount += len(trialMissingGRF)
                print('Detected missing/bad GRF data on '+str(totalFramesCount -
                      goodFramesCount)+'/'+str(totalFramesCount)+' frames', flush=True)
                if goodFramesCount == 0:
                    print('ERROR: we have no good frames of GRF data left after filtering out suspicious GRF frames. This '
                          'probably means input GRF data is badly miscalibrated with respect to marker data (maybe they '
                          'are in different coordinate frames?), or there are unmeasured external forces acting on your '
                          'subject. Aborting the physics fitter!', flush=True)
                    fitDynamics = False
                else:
                    # Run an optimization to figure out the model parameters
                    dynamicsFitter.setIterationLimit(200)
                    dynamicsFitter.setLBFGSHistoryLength(300)
                    dynamicsFitter.runIPOPTOptimization(
                        dynamicsInit,
                        nimble.biomechanics.DynamicsFitProblemConfig(
                            finalSkeleton)
                        .setDefaults(True)
                        .setResidualWeight(4e-2 * tuneResidualLoss)
                        .setMaxNumTrials(3)
                        .setConstrainResidualsZero(False)
                        .setIncludeMasses(True)
                        .setMaxNumBlocksPerTrial(20)
                        # .setIncludeInertias(True)
                        # .setIncludeCOMs(True)
                        # .setIncludeBodyScales(True)
                        .setIncludeMarkerOffsets(True)
                        .setIncludePoses(True)
                        .setRegularizeJointAcc(regularizeJointAcc))

                    # Now re-run a position-only optimization on every trial in the dataset
                    for trial in range(len(dynamicsInit.poseTrials)):
                        if len(dynamicsInit.probablyMissingGRF[i]) < 1000:
                            dynamicsFitter.setIterationLimit(200)
                            dynamicsFitter.setLBFGSHistoryLength(100)
                        elif len(dynamicsInit.probablyMissingGRF[i]) < 5000:
                            dynamicsFitter.setIterationLimit(100)
                            dynamicsFitter.setLBFGSHistoryLength(30)
                        else:
                            dynamicsFitter.setIterationLimit(50)
                            dynamicsFitter.setLBFGSHistoryLength(3)
                        dynamicsFitter.runIPOPTOptimization(
                            dynamicsInit,
                            nimble.biomechanics.DynamicsFitProblemConfig(
                                finalSkeleton)
                            .setDefaults(True)
                            .setOnlyOneTrial(trial)
                            .setResidualWeight(4e-2 * tuneResidualLoss)
                            .setConstrainResidualsZero(False)
                            .setIncludePoses(True))

                    # Specifically optimize to 0-ish residuals, if user requests it
                    if residualsToZero:
                        for trial in range(len(dynamicsInit.poseTrials)):
                            originalTrajectory = dynamicsInit.poseTrials[trial].copy()
                            previousTotalResidual = np.inf
                            for i in range(100):
                                # this holds the mass constant, and re-jigs the trajectory to try to get
                                # the angular ACC's to match more closely what was actually observed
                                pair = dynamicsFitter.zeroLinearResidualsAndOptimizeAngular(
                                    dynamicsInit,
                                    trial,
                                    originalTrajectory,
                                    previousTotalResidual,
                                    i,
                                    useReactionWheels=useReactionWheels,
                                    weightLinear=1.0,
                                    weightAngular=0.5,
                                    regularizeLinearResiduals=0.1,
                                    regularizeAngularResiduals=0.1,
                                    regularizeCopDriftCompensation=1.0,
                                    maxBuckets=150)
                                previousTotalResidual = pair[1]

                            dynamicsFitter.recalibrateForcePlates(
                                dynamicsInit, trial)

            else:
                print('WARNING: Unable to minimize residual moments below the desired threshold. Skipping '
                      'body mass optimization and re-running dynamics initialization while allowing large '
                      'residual moments.', flush=True)
                initializeSuccess = dynamicsFitter.timeSyncAndInitializePipeline(
                    dynamicsInit,
                    useReactionWheels=True,
                    shiftGRF=shiftGRF,
                    maxTrialsToSolveMassOver=maxTrialsToSolveMassOver
                )
                # TODO re-run position only optimization here?

            dynamicsFitter.applyInitToSkeleton(finalSkeleton, dynamicsInit)

            dynamicsFitter.computePerfectGRFs(dynamicsInit)

            consistent = dynamicsFitter.checkPhysicalConsistency(
                dynamicsInit, maxAcceptableErrors=1e-3, maxTimestepsToTest=25)

            print("Avg Marker RMSE: " +
                  str(dynamicsFitter.computeAverageMarkerRMSE(dynamicsInit) * 100) + "cm", flush=True)
            pair = dynamicsFitter.computeAverageResidualForce(dynamicsInit)
            print("Avg Residual Force: " + str(pair[0]) + " N (" + str((pair[0] /
                  secondPair[0]) * 100) + "% of original " + str(secondPair[0]) + " N)", flush=True)
            print("Avg Residual Torque: " + str(pair[1]) + " Nm (" + str((pair[1] /
                  secondPair[1]) * 100) + "% of original " + str(secondPair[1]) + " Nm)", flush=True)
            print("Avg CoP movement in 'perfect' GRFs: " +
                  str(dynamicsFitter.computeAverageCOPChange(dynamicsInit)) + " m", flush=True)
            print("Avg force change in 'perfect' GRFs: " +
                  str(dynamicsFitter.computeAverageForceMagnitudeChange(dynamicsInit)) + " N", flush=True)

            # Write all the results back
            trialBadDynamicsFrames: List[Dict[str, List[int]]] = []
            for trial in range(len(dynamicsInit.poseTrials)):
                finalInverseDynamics.append(
                    dynamicsFitter.computeInverseDynamics(dynamicsInit, trial))
                pair = dynamicsFitter.computeAverageTrialResidualForce(
                    dynamicsInit, trial)
                trialProcessingResults[trial]['linearResidual'] = pair[0]
                trialProcessingResults[trial]['angularResidual'] = pair[1]

                badDynamicsFrames: Dict[str, List[int]] = {}
                numBadDynamicsFrames = 0
                for iframe, reason in enumerate(dynamicsInit.missingGRFReason[trial]):
                    if not reason.name in badDynamicsFrames: badDynamicsFrames[reason.name] = []
                    badDynamicsFrames[reason.name].append(iframe)
                    if not reason.name == 'notMissingGRF':
                        numBadDynamicsFrames += 1

                trialProcessingResults[trial]['numBadDynamicsFrames'] = numBadDynamicsFrames
                trialBadDynamicsFrames.append(badDynamicsFrames)

            finalPoses = dynamicsInit.poseTrials
            finalMarkers = dynamicsInit.updatedMarkerMap
            trialForcePlates = dynamicsInit.forcePlateTrials


    # 8.2. Write out the usable OpenSim results

    if not os.path.exists(path+'results'):
        os.mkdir(path+'results')
    if not os.path.exists(path+'results/IK'):
        os.mkdir(path+'results/IK')
    if not os.path.exists(path+'results/ID'):
        os.mkdir(path+'results/ID')
    if not os.path.exists(path+'results/C3D'):
        os.mkdir(path+'results/C3D')
    if not os.path.exists(path+'results/Models'):
        os.mkdir(path+'results/Models')
    if exportMJCF and not os.path.exists(path+'results/MuJoCo'):
        os.mkdir(path+'results/MuJoCo')
    if exportSDF and not os.path.exists(path+'results/SDF'):
        os.mkdir(path+'results/SDF')
    if not os.path.exists(path+'results/MarkerData'):
        os.mkdir(path+'results/MarkerData')
    print('Outputting OpenSim files', flush=True)

    shutil.copyfile(path + 'unscaled_generic.osim', path +
                    'results/Models/unscaled_generic.osim')

    # 8.2.1. Adjusting marker locations
    print('Adjusting marker locations on scaled OpenSim file', flush=True)
    bodyScalesMap: Dict[str, np.ndarray] = {}
    for i in range(finalSkeleton.getNumBodyNodes()):
        bodyNode: nimble.dynamics.BodyNode = finalSkeleton.getBodyNode(i)
        # Now that we adjust the markers BEFORE we rescale the body, we don't want to rescale the marker locations at all
        bodyScalesMap[bodyNode.getName()] = [1, 1, 1]
    markerOffsetsMap: Dict[str, Tuple[str, np.ndarray]] = {}
    markerNames: List[str] = []
    for k in finalMarkers:
        v = finalMarkers[k]
        markerOffsetsMap[k] = (v[0].getName(), v[1])
        markerNames.append(k)
    nimble.biomechanics.OpenSimParser.moveOsimMarkers(
        path + 'unscaled_generic.osim', bodyScalesMap, markerOffsetsMap, path + 'results/Models/unscaled_but_with_optimized_markers.osim')

    # 8.2.2. Write the XML instructions for the OpenSim scaling tool
    nimble.biomechanics.OpenSimParser.saveOsimScalingXMLFile(
        'optimized_scale_and_markers', finalSkeleton, massKg, heightM, 'Models/unscaled_but_with_optimized_markers.osim', 'Unassigned', 'Models/optimized_scale_and_markers.osim', path + 'results/Models/rescaling_setup.xml')
    # 8.2.3. Call the OpenSim scaling tool
    command = 'cd '+path+'results && opensim-cmd run-tool ' + \
        path + 'results/Models/rescaling_setup.xml'
    print('Scaling OpenSim files: '+command, flush=True)
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()

    # Delete the OpenSim log from running the scale tool
    if os.path.exists(path + 'results/opensim.log'):
        os.remove(path + 'results/opensim.log')

    # 8.2.4. Overwrite the inertia properties of the resulting OpenSim skeleton file
    nimble.biomechanics.OpenSimParser.replaceOsimInertia(
        path + 'results/Models/optimized_scale_and_markers.osim', finalSkeleton, path + 'results/Models/final.osim')

    # Get ready to count the number of times we run up against joint limits during the IK
    dofNames: List[str] = []
    jointLimitsHits: Dict[str, int] = {}
    for i in range(finalSkeleton.getNumDofs()):
        dofNames.append(finalSkeleton.getDofByIndex(i).getName())
        jointLimitsHits[finalSkeleton.getDofByIndex(i).getName()] = 0
    trialJointWarnings: Dict[str, List[str]] = {}

    if fitDynamics and dynamicsInit is not None:
        notes: str = 'Generated by AddBiomechanics'
        outputPath: str = path+'subject.bin'
        if outputName is not None:
            outputPath: str = path+outputName+'.bin'
        dynamicsFitter.writeSubjectOnDisk(
            outputPath, path + 'results/Models/final.osim', dynamicsInit, False, trialNames, href, notes)

    if exportSDF or exportMJCF:
        print('Deleting OpenSim model outputs, since we cannot export OpenSim models when using a simplified skeleton')
        # Get a list of all the file paths that ends with .osim from the Models
        modelList = glob.glob(path + 'results/Models/*')
        # Iterate over the list of filepaths and remove each file.
        for filePath in modelList:
            try:
                os.remove(filePath)
            except:
                print("Error while deleting Model file: ", filePath)

        if exportSDF:
            print('Writing an SDF version of the skeleton', flush=True)
            nimble.utils.SdfParser.writeSkeleton(
                path + 'results/SDF/model.sdf', simplified)
        if exportMJCF:
            print('Writing a MuJoCo version of the skeleton', flush=True)
            nimble.utils.MJCFExporter.writeSkeleton(
                path + 'results/MuJoCo/model.xml', simplified)

    trialDynamicsSegments: List[List[Tuple[int, int]]] = []
    for i in range(len(trialNames)):
        poses = finalPoses[i]
        forces = finalInverseDynamics[i] if i < len(
            finalInverseDynamics) else None
        trialName = trialNames[i]
        c3dFile = c3dFiles[trialName] if trialName in c3dFiles else None
        forcePlates = trialForcePlates[i]
        framesPerSecond = trialFramesPerSecond[i]
        timestamps = trialTimestamps[i]
        markerTimesteps = markerTrials[i]
        trialProcessingResult = trialProcessingResults[i]
        trialPath = path + 'trials/' + trialName + '/'

        resultIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
            finalSkeleton, fitMarkers, poses, markerTimesteps)
        trialProcessingResult['autoAvgRMSE'] = resultIK.averageRootMeanSquaredError
        trialProcessingResult['autoAvgMax'] = resultIK.averageMaxError
        trialProcessingResult['markerErrors'] = resultIK.getSortedMarkerRMSE()

        print('Saving trial '+str(trialName)+' results', flush=True)

        print('auto scaled average RMSE m: ' +
              str(resultIK.averageRootMeanSquaredError), flush=True)
        print('auto scaled average max m: ' +
              str(resultIK.averageMaxError), flush=True)

        # Load the gold .mot file, if one exists
        goldMot: nimble.biomechanics.OpenSimMot = None
        if os.path.exists(trialPath + 'manual_ik.mot') and goldOsim is not None:
            if c3dFile is not None:
                goldMot = nimble.biomechanics.OpenSimParser.loadMotAtLowestMarkerRMSERotation(
                    goldOsim, trialPath + 'manual_ik.mot', c3dFile)
            else:
                goldMot = nimble.biomechanics.OpenSimParser.loadMot(
                    goldOsim.skeleton, trialPath + 'manual_ik.mot')

            shutil.copyfile(trialPath + 'manual_ik.mot', path +
                            'results/IK/' + trialName + '_manual_scaling_ik.mot')
            nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                trialName, markerNames, "../Models/manually_scaled.osim", '../MarkerData/'+trialName+'.trc', trialName+'_ik_on_manual_scaling_by_opensim.mot', path + 'results/IK/'+trialName+'_ik_on_manually_scaled_setup.xml')

            originalIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
                goldOsim.skeleton, goldOsim.markersMap, goldMot.poses, markerTimesteps)
            print('manually scaled average RMSE cm: ' +
                  str(originalIK.averageRootMeanSquaredError), flush=True)
            print('manually scaled average max cm: ' +
                  str(originalIK.averageMaxError), flush=True)
            trialProcessingResult['goldAvgRMSE'] = originalIK.averageRootMeanSquaredError
            trialProcessingResult['goldAvgMax'] = originalIK.averageMaxError

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

        # 8.2. Write out the kinematics and kinetics data files.

        # 8.2.1. Write out the inverse kinematics results,
        ik_fpath = f'{path}/results/IK/{trialName}_ik.mot'
        print(f'Writing OpenSim {ik_fpath} file, shape={str(poses.shape)}', flush=True)
        nimble.biomechanics.OpenSimParser.saveMot(finalSkeleton, ik_fpath, timestamps, poses)

        # 8.2.2. Write the inverse dynamics results.
        id_fpath = f'{path}/results/ID/{trialName}_id.sto'
        if forces is not None:
            nimble.biomechanics.OpenSimParser.saveIDMot(
                finalSkeleton, id_fpath, timestamps, forces)

        # 8.2.3. Write out the marker errors.
        marker_errors_fpath = f'{path}/results/IK/{trialName}_marker_errors.csv'
        resultIK.saveCSVMarkerErrorReport(marker_errors_fpath)

        # 8.2.4. Write out the marker trajectories.
        markers_fpath = f'{path}/results/MarkerData/{trialName}.trc'
        nimble.biomechanics.OpenSimParser.saveTRC(
            markers_fpath, timestamps, markerTimesteps)

        # 8.2.5. Write out the C3D file.
        c3d_fpath = f'{path}/results/C3D/{trialName}.c3d'
        if c3dFile is not None:
            shutil.copyfile(trialPath + 'markers.c3d', c3d_fpath)

        # 8.2.6. Export setup files for OpenSim InverseKinematics.
        if exportOSIM:
            # Save OpenSim setup files to make it easy to (re)run IK and ID on the results in OpenSim
            nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                trialName, markerNames, "../Models/optimized_scale_and_markers.osim", '../MarkerData/'+trialName+'.trc', trialName+'_ik_by_opensim.mot', path + 'results/IK/'+trialName+'_ik_setup.xml')

        # 8.2.7. Write out the inverse dynamics files.
        grf_fpath = f'{path}/results/ID/{trialName}_grf.mot'
        grf_raw_fpath = f'{path}/results/ID/{trialName}_grf_raw.mot'
        if fitDynamics and dynamicsInit is not None:
            # Run through the list of timesteps, looking for windows of time where we have GRF data. Trim the leading and trailing frames from these windows, because those don't fit by AddBiomechanics finite differencing.
            dynamicsSegments: List[Tuple[int, int]] = []
            lastUnobservedTimestep = -1
            lastWasObserved = False
            for t in range(len(dynamicsInit.probablyMissingGRF[i])):
                if dynamicsInit.probablyMissingGRF[i][t]:
                    if lastWasObserved:
                        if lastUnobservedTimestep + 2 < t - 1:
                            dynamicsSegments.append(
                                (lastUnobservedTimestep + 2, t - 1))
                    lastWasObserved = False
                    lastUnobservedTimestep = t
                else:
                    lastWasObserved = True
            if lastWasObserved:
                if lastUnobservedTimestep + 2 < len(dynamicsInit.probablyMissingGRF[i]) - 2:
                    dynamicsSegments.append(
                        (lastUnobservedTimestep + 2, len(dynamicsInit.probablyMissingGRF[i]) - 2))
            print('Trial ' + trialName + ' detected GRF data present on ranges: ' +
                  str(dynamicsSegments), flush=True)
            trialDynamicsSegments.append(dynamicsSegments)

            nimble.biomechanics.OpenSimParser.saveProcessedGRFMot(grf_fpath, timestamps, dynamicsInit.grfBodyNodes,
                dynamicsInit.groundHeight[i], dynamicsInit.grfTrials[i])
            nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsProcessedForcesXMLFile(
                trialName, dynamicsInit.grfBodyNodes, trialName+'_grf.mot', path + 'results/ID/'+trialName+'_external_forces.xml')

            if exportOSIM:
                if len(dynamicsSegments) > 1:
                    for seg in range(len(dynamicsSegments)):
                        begin, end = dynamicsSegments[seg]
                        nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                            trialName, '../Models/final.osim', '../IK/'+trialName+'_ik.mot', trialName+'_external_forces.xml', trialName+'_osim_segment_'+str(seg)+'_id.sto', trialName+'_osim_segment_'+str(seg)+'_id_body_forces.sto', path + 'results/ID/'+trialName+'_id_setup_segment_'+str(seg)+'.xml', timestamps[begin], timestamps[end])
                elif len(dynamicsSegments) == 1:
                    begin, end = dynamicsSegments[0]
                    nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                        trialName, '../Models/final.osim', '../IK/'+trialName+'_ik.mot', trialName+'_external_forces.xml', trialName+'_osim_id.sto', trialName+'_osim_id_body_forces.sto', path + 'results/ID/'+trialName+'_id_setup.xml', timestamps[begin], timestamps[end])
            # Still save the raw version, just call it that
            nimble.biomechanics.OpenSimParser.saveRawGRFMot(grf_raw_fpath, timestamps, forcePlates)
            nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsRawForcesXMLFile(
                trialName, finalSkeleton, poses, forcePlates, trialName+'_grf_raw.mot', path + 'results/ID/'+trialName+'_external_forces_raw.xml')
            if exportOSIM:
                nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                    trialName, '../Models/final.osim', '../IK/'+trialName+'_ik.mot', trialName+'_external_forces_raw.xml', trialName+'_osim_id_raw.sto', trialName+'_id_body_forces_raw.sto', path + 'results/ID/'+trialName+'_id_setup_raw.xml', min(timestamps), max(timestamps))
        else:
            nimble.biomechanics.OpenSimParser.saveRawGRFMot(grf_fpath, timestamps, forcePlates)
            nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsRawForcesXMLFile(
                trialName, finalSkeleton, poses, forcePlates, trialName+'_grf.mot', path + 'results/ID/'+trialName+'_external_forces.xml')
            if exportOSIM:
                nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                    trialName, '../Models/optimized_scale_and_markers.osim', '../IK/'+trialName+'_ik.mot', trialName+'_external_forces.xml', trialName+'_id.sto', trialName+'_id_body_forces.sto', path + 'results/ID/'+trialName+'_id_setup.xml', min(timestamps), max(timestamps))

        # 8.3. Write out the animation preview
        # 8.3.1. Create the raw binary
        if fitDynamics and dynamicsInit is not None:
            print('Saving trajectory, markers, and dynamics to a GUI log ' +
                  trialPath+'preview.bin', flush=True)
            print("FPS: " + str(round(1.0 / dynamicsInit.trialTimesteps[0])))
            dynamicsFitter.saveDynamicsToGUI(
                trialPath+'preview.bin',
                dynamicsInit,
                i,
                round(1.0 / dynamicsInit.trialTimesteps[i]))

            dynamicsFitter.writeCSVData(
                trialPath+'plot.csv', dynamicsInit, i, False, timestamps)
            dynamicsFitter.writeCSVData(
                path + 'results/ID/'+trialName+'_full.csv', dynamicsInit, i, False, timestamps)
        else:
            if (goldOsim is not None) and (goldMot is not None):
                print('Saving trajectory, markers, and the manual IK to a GUI log ' +
                      trialPath+'preview.bin', flush=True)
                print('goldOsim: '+str(goldOsim), flush=True)
                print('goldMot.poses.shape: ' +
                      str(goldMot.poses.shape), flush=True)
                markerFitter.saveTrajectoryAndMarkersToGUI(
                    trialPath+'preview.bin', results[i], markerTimesteps, framesPerSecond, forcePlates, goldOsim, goldMot.poses)
            else:
                print('Saving trajectory and markers to a GUI log ' +
                      trialPath+'preview.bin', flush=True)
                markerFitter.saveTrajectoryAndMarkersToGUI(
                    trialPath+'preview.bin', results[i], markerTimesteps, framesPerSecond, forcePlates)
        # 8.3.2. Zip it up
        print('Zipping up '+trialPath+'preview.bin', flush=True)
        subprocess.run(["zip", "-r", 'preview.bin.zip',
                       'preview.bin'], cwd=trialPath, capture_output=True)
        print('Finished zipping up '+trialPath+'preview.bin.zip', flush=True)

        # 8.4. Count up the number of times we hit against joint limits

        trialJointLimitHits: Dict[str, int] = {}
        jointLimitsFrames: Dict[str, List[int]] = {}
        jointLimitsFramesUpperBound: Dict[str, List[bool]] = {}
        for i in range(finalSkeleton.getNumDofs()):
            dofName = finalSkeleton.getDofByIndex(i).getName()
            trialJointLimitHits[dofName] = 0
            jointLimitsFrames[dofName] = []
            jointLimitsFramesUpperBound[dofName] = []

        tol = 0.001
        for t in range(poses.shape[1]):
            thisTimestepPos = poses[:, t]
            for i in range(finalSkeleton.getNumDofs()):
                dof = finalSkeleton.getDofByIndex(i)
                dofPos = thisTimestepPos[i]
                # If the joints are at least 2*tol apart
                if dof.getPositionUpperLimit() > dof.getPositionLowerLimit() + 2 * tol:
                    if dofPos > dof.getPositionUpperLimit() - tol:
                        jointLimitsHits[dof.getName()] += 1
                        trialJointLimitHits[dof.getName()] += 1
                        jointLimitsFrames[dof.getName()].append(t)
                        jointLimitsFramesUpperBound[dof.getName()].append(True)
                    if dofPos < dof.getPositionLowerLimit() + tol:
                        jointLimitsHits[dof.getName()] += 1
                        trialJointLimitHits[dof.getName()] += 1
                        jointLimitsFrames[dof.getName()].append(t)
                        jointLimitsFramesUpperBound[dof.getName()].append(
                            False)

        # 8.4.1. Sort for trial joint limits

        print('Computing details about joint limit hits for the README')
        try:
            trialJointWarnings[trialName] = []
            for dof in sorted(trialJointLimitHits, key=trialJointLimitHits.get, reverse=True):
                jointHits: List[int] = jointLimitsFrames[dof]
                jointHitsUpperBound: List[bool] = jointLimitsFramesUpperBound[dof]
                if len(jointHits) == 0:
                    continue
                startBlock = jointHits[0]
                lastBlock = jointHits[0]
                lastUpperBound = jointHitsUpperBound[0]
                for i in range(len(jointHits)):
                    frame = jointHits[i]
                    upperBound = jointHitsUpperBound[i]

                    if (frame - lastBlock) <= 1 and lastUpperBound == upperBound:
                        # If this is part of a continuous sequence of frames, we want to compress the message
                        lastBlock = frame
                    else:
                        # We jumped to a new block of frames, so emit the last block
                        if startBlock == lastBlock:  # single frame
                            trialJointWarnings[trialName].append(
                                dof+' hit '+('upper' if lastUpperBound else 'lower')+' bound on frame '+str(startBlock))
                        else:
                            trialJointWarnings[trialName].append(
                                dof+' hit '+('upper' if lastUpperBound else 'lower')+' bound on frames '+str(startBlock)+'-'+str(lastBlock))
                        lastBlock = frame
                        startBlock = frame
        except e:
            print('Caught an error when computing trial joint limits:')
            traceback.print_exc()
            print('Continuing...')
        print('Finished computing details about joint limit hits for the README')

        # 8.5. Plot results.
        print(f'Plotting results for trial {trialName}')
        plotIKResults(ik_fpath)
        plotMarkerErrors(marker_errors_fpath, ik_fpath)
        if os.path.exists(id_fpath):
           plotIDResults(id_fpath)

        if os.path.exists(grf_fpath):
            plotGRFData(grf_fpath)

        if os.path.exists(grf_raw_fpath):
            plotGRFData(grf_raw_fpath)

        print('Success! Done with '+trialName+'.', flush=True)

    if os.path.exists(path + 'manually_scaled.osim'):
        shutil.copyfile(path + 'manually_scaled.osim', path +
                        'results/Models/manually_scaled.osim')

    # Copy over the geometry files, so the model can be loaded directly in OpenSim without chasing down Geometry files somewhere else
    shutil.copytree(DATA_FOLDER_PATH + '/Geometry', path +
                    'results/Models/Geometry')
    # Copy over the geometry files (in a MuJoCo specific file format), so the model can be loaded directly in MuJoCo without chasing down Geometry files somewhere else
    if exportMJCF:
        shutil.copytree(DATA_FOLDER_PATH + '/MuJoCoGeometry', path +
                        'results/MuJoCo/Geometry')
    # Copy over the geometry files (in a SDF specific file format), so the model can be loaded directly in PyBullet without chasing down Geometry files somewhere else
    if exportSDF:
        shutil.copytree(DATA_FOLDER_PATH + '/SDFGeometry', path +
                        'results/SDF/Geometry')

    # Generate the overall summary result
    autoTotalLen = 0
    goldTotalLen = 0
    processingResult['autoAvgRMSE'] = 0
    processingResult['autoAvgMax'] = 0
    if fitDynamics and dynamicsInit is not None:
        processingResult['linearResidual'] = 0
        processingResult['angularResidual'] = 0
    processingResult['goldAvgRMSE'] = 0
    processingResult['goldAvgMax'] = 0
    for i in range(len(trialNames)):
        trialLen = len(markerTrials[i])
        trialProcessingResult = trialProcessingResults[i]
        processingResult['autoAvgRMSE'] += trialProcessingResult['autoAvgRMSE'] * trialLen
        processingResult['autoAvgMax'] += trialProcessingResult['autoAvgMax'] * trialLen
        if fitDynamics and dynamicsInit is not None:
            processingResult['linearResidual'] += trialProcessingResult['linearResidual'] * trialLen
            processingResult['angularResidual'] += trialProcessingResult['angularResidual'] * trialLen
        autoTotalLen += trialLen

        if 'goldAvgRMSE' in trialProcessingResult and 'goldAvgMax' in trialProcessingResult:
            processingResult['goldAvgRMSE'] += trialProcessingResult['goldAvgRMSE'] * trialLen
            processingResult['goldAvgMax'] += trialProcessingResult['goldAvgMax'] * trialLen
            goldTotalLen += trialLen
    processingResult['autoAvgRMSE'] /= autoTotalLen
    processingResult['autoAvgMax'] /= autoTotalLen
    if fitDynamics and dynamicsInit is not None:
        processingResult['linearResidual'] /= autoTotalLen
        processingResult['angularResidual'] /= autoTotalLen
    if goldTotalLen > 0:
        processingResult['goldAvgRMSE'] /= goldTotalLen
        processingResult['goldAvgMax'] /= goldTotalLen
    processingResult['guessedTrackingMarkers'] = guessedTrackingMarkers
    processingResult['trialMarkerSets'] = trialMarkerSet
    processingResult['osimMarkers'] = list(finalMarkers.keys())

    trialWarnings: Dict[str, List[str]] = {}
    trialInfo: Dict[str, List[str]] = {}
    badMarkerThreshold = 4  # cm
    trialBadMarkers: Dict[str, int] = {}
    markerCleanupWarnings: List[str] = []
    for i in range(len(trialErrorReports)):
        trialWarnings[trialNames[i]] = trialErrorReports[i].warnings
        trialInfo[trialNames[i]] = trialErrorReports[i].info
    processingResult['trialWarnings'] = trialWarnings
    processingResult['trialInfo'] = trialInfo
    processingResult["fewFramesWarning"] = totalFrames < 300
    processingResult['jointLimitsHits'] = jointLimitsHits

    # Write out the README for the data
    with open(path + 'results/README.txt', 'w') as f:
        f.write(
            "*** This data was generated with AddBiomechanics (www.addbiomechanics.org) ***\n")
        f.write(
            "AddBiomechanics was written by Keenon Werling.\n")
        f.write("\n")
        f.write(textwrap.fill(
            "Automatic processing achieved the following marker errors (averaged over all frames of all trials):"))
        f.write("\n\n")
        totalMarkerRMSE = processingResult['autoAvgRMSE'] * 100
        totalMarkerMax = processingResult['autoAvgMax'] * 100
        f.write(f'- Avg. Marker RMSE: {totalMarkerRMSE:1.2f} cm\n')
        f.write(f'- Avg. Max Marker Error: {totalMarkerMax:.2f} cm\n')
        f.write("\n")
        if fitDynamics and dynamicsInit is not None:
            f.write(textwrap.fill(
                "Automatic processing reduced the residual loads needed for dynamic consistency to the following magnitudes "
                "(averaged over all frames of all trials):"))
            f.write("\n\n")
            residualForce =  processingResult['linearResidual']
            residualTorque = processingResult['angularResidual']
            f.write(f'- Avg. Residual Force: {residualForce:1.2f} N\n')
            f.write(f'- Avg. Residual Torque: {residualTorque:1.2f} N-m\n')
            f.write("\n")
        if fitDynamics and dynamicsInit is not None:
            f.write(textwrap.fill(
                "The following trials were processed to perform automatic body scaling, marker registration, "
                "and residual reduction:"))
        else:
            f.write(textwrap.fill(
                "The following trials were processed to perform automatic body scaling and marker registration:"))
        f.write("\n\n")
        for i in range(len(trialNames)):
            trialProcessingResult = trialProcessingResults[i]
            # Main trial results summary.
            trialName = trialNames[i]
            f.write(f'trial: {trialName}\n')

            markerRMSE = trialProcessingResult['autoAvgRMSE'] * 100
            markerMax = trialProcessingResult['autoAvgMax'] * 100
            f.write(f'  - Avg. Marker RMSE      = {markerRMSE:1.2f} cm\n')
            f.write(f'  - Avg. Marker Max Error = {markerMax:.2f} cm\n')

            residualForce = trialProcessingResult['linearResidual']
            residualTorque = trialProcessingResult['angularResidual']
            f.write(f'  - Avg. Residual Force   = {residualForce:1.2f} N\n')
            f.write(f'  - Avg. Residual Torque  = {residualTorque:1.2f} N-m\n')

            # Warning and error reporting.
            if len(trialJointWarnings[trialName]) > 0:
                f.write(f'  - WARNING: {len(trialJointWarnings[trialName])} joints hit joint limits!\n')

            numBadMarkers = 0
            for markerError in trialProcessingResult['markerErrors']:
                if 100*markerError[1] > badMarkerThreshold: numBadMarkers += 1

            trialBadMarkers[trialName] = numBadMarkers
            if numBadMarkers > 0:
                f.write(f'  - WARNING: {numBadMarkers} marker(s) with RMSE greater than {badMarkerThreshold} cm!\n')

            if len(trialWarnings[trialName]) > 0:
                f.write(f'  - WARNING: Automatic data processing required modifying TRC data from '
                        f'{len(trialWarnings[trialName])} marker(s)!\n')

            if fitDynamics and dynamicsInit is not None:
                numBadFrames = trialProcessingResult['numBadDynamicsFrames']
                if numBadFrames:
                    f.write(f'  - WARNING: {numBadFrames} frame(s) with ground reaction force inconsistencies detected!\n')
                
            if fitDynamics and dynamicsInit is not None:
                f.write(f'  --> See IK/{trialName}_ik_summary.txt and ID/{trialName}_id_summary.txt for more details.\n')
            else:
                f.write(f'  --> See IK/{trialName}_ik_summary.txt for more details.\n')
            f.write(f'\n')

        f.write('\n')
        f.write(textwrap.fill(
            "The model file containing optimal body scaling and marker offsets is:"))
        f.write("\n\n")
        if exportOSIM:
            f.write("Models/optimized_scale_and_markers.osim")
            f.write("\n\n")
        if exportMJCF:
            f.write("MuJoCo/model.xml")
            f.write("\n\n")
        if exportSDF:
            f.write("SDF/model.sdf")
            f.write("\n\n")
        f.write(textwrap.fill(
            "This tool works by finding an optimal scaling and an optimal marker offsets at the same time."))
        f.write("\n\n")
        if exportOSIM:
            f.write(textwrap.fill("If you want to manually edit the marker offsets, you can modify the <MarkerSet> in \"Models/unscaled_but_with_optimized_markers.osim\" (by default this file contains the marker offsets found by the optimizer). If you want to tweak the Scaling, you can edit \"Models/rescaling_setup.xml\". If you change either of these files, then run (FROM THE \"Models\" FOLDER, and not including the leading \"> \"):"))
            f.write("\n\n")
            f.write(" > opensim-cmd run-tool rescaling_setup.xml\n")
            f.write(
                '           # This will re-generate Models/optimized_scale_and_markers.osim\n')
            f.write("\n\n")
            f.write(textwrap.fill("You do not need to re-run Inverse Kinematics unless you change scaling, because the output motion files are already generated for you as \"*_ik.mot\" files for each trial, but you are welcome to confirm our results using OpenSim. To re-run Inverse Kinematics with OpenSim, to verify the results of AddBiomechanics, you can use the automatically generated XML configuration files. Here are the command-line commands you can run (FROM THE \"IK\" FOLDER, and not including the leading \"> \") to verify IK results for each trial:"))
            f.write("\n\n")
            for i in range(len(trialNames)):
                trialName = trialNames[i]
                f.write(" > opensim-cmd run-tool " +
                        trialName+'_ik_setup.xml\n')
                f.write("           # This will create a results file IK/" +
                        trialName+'_ik_by_opensim.mot\n')
            f.write("\n\n")

            if os.path.exists(path + 'manually_scaled.osim'):
                f.write(textwrap.fill("You included a manually scaled model to compare against. That model has been copied into this folder as \"manually_scaled.osim\". You can use the automatically generated XML configuration files to run IK using your manual scaling as well. Here are the command-line commands you can run (FROM THE \"IK\" FOLDER, and not including the leading \"> \") to compare IK results for each trial:"))
                f.write("\n\n")
                for i in range(len(trialNames)):
                    trialName = trialNames[i]
                    f.write(" > opensim-cmd run-tool " + trialName +
                            '_ik_on_manually_scaled_setup.xml\n')
                    f.write("           # This will create a results file IK/" +
                            trialName+'_ik_on_manual_scaling_by_opensim.mot\n')
                f.write("\n\n")

            if fitDynamics and dynamicsInit is not None:
                f.write(textwrap.fill("To re-run Inverse Dynamics using OpenSim, you can also use automatically generated XML configuration files. WARNING: Inverse Dynamics in OpenSim uses a different time-step definition to the one used in AddBiomechanics (AddBiomechanics uses semi-implicit Euler, OpenSim uses splines). This means that your OpenSim inverse dynamics results WILL NOT MATCH your AddBiomechanics results, and YOU SHOULD NOT EXPECT THEM TO. The following commands should work (FROM THE \"ID\" FOLDER, and not including the leading \"> \"):\n"))
                f.write("\n\n")
                for i in range(len(trialNames)):
                    trialName = trialNames[i]
                    timestamps = trialTimestamps[i]
                    if len(trialDynamicsSegments[i]) > 1:
                        for seg in range(len(trialDynamicsSegments[i])):
                            begin, end = trialDynamicsSegments[i][seg]
                            f.write(" > opensim-cmd run-tool " +
                                    trialName+'_id_setup_segment_'+str(seg)+'.xml\n')
                            f.write("           # This will create results on time range ("+str(timestamps[begin])+"s to "+str(timestamps[end])+"s) in file ID/" +
                                    trialName+'_osim_segment_'+str(seg)+'_id.sto\n')
                    elif len(trialDynamicsSegments[i]) == 1:
                        begin, end = trialDynamicsSegments[i][0]
                        f.write(" > opensim-cmd run-tool " +
                                trialName+'_id_setup.xml\n')
                        f.write("           # This will create results on time range ("+str(timestamps[begin])+"s to "+str(timestamps[end])+"s) in file ID/" +
                                trialName+'_osim_id.sto\n')
            else:
                f.write(textwrap.fill("To run Inverse Dynamics with OpenSim, you can also use automatically generated XML configuration files. WARNING: This AddBiomechanics run did not attempt to fit dynamics (you need to have GRF data and enable physics fitting in the web app), so the residuals will not be small and YOU SHOULD NOT EXPECT THEM TO BE. That being said, to run inverse dynamics the following commands should work (FROM THE \"ID\" FOLDER, and not including the leading \"> \"):\n"))
                f.write("\n\n")
                for i in range(len(trialNames)):
                    trialName = trialNames[i]
                    f.write(" > opensim-cmd run-tool " +
                            trialName+'_id_setup.xml\n')
                    f.write("           # This will create a results file ID/" +
                            trialName+'_id.sto\n')
            f.write("\n\n")
            f.write(textwrap.fill(
                "The original unscaled model file is present in:"))
            f.write("\n\n")
            f.write("Models/unscaled_generic.osim")
            f.write("\n\n")
            f.write(textwrap.fill(
                "There is also an unscaled model, with markers moved to spots found by this tool, at:"))
            f.write("\n\n")
            f.write("Models/unscaled_but_with_optimized_markers.osim")
        else:
            f.write(textwrap.fill("Because you chose to export MuJoCo and/or SDF files, we had to simplify the OpenSim skeleton we started out with (replacing <CustomJoint> objects with simpler joint types, etc). This means that the output is no longer compatible with OpenSim, and so the normal OpenSim files are not present. If you want the OpenSim files, please re-run AddBiomechanics with those options turned off"))
        f.write("\n\n")
        f.write(textwrap.fill(
            "If you encounter errors, please submit a post to the AddBiomechanics user forum on SimTK.org\n:"))
        f.write('\n\n')
        f.write('   https://simtk.org/projects/addbiomechanics')

    if exportMJCF:
        with open(path + 'results/MuJoCo/README.txt', 'w') as f:
            f.write(
                "*** This data was generated with AddBiomechanics (www.addbiomechanics.org) ***\n")
            f.write(
                "AddBiomechanics was written by Keenon Werling <keenon@cs.stanford.edu>\n")
            f.write("\n")
            f.write(textwrap.fill(
                "Our automatic conversion to MuJoCo is in early beta! Bug reports are welcome at keenon@cs.stanford.edu."))
            f.write("\n\n")
            f.write(textwrap.fill(
                "This folder contains a MuJoCo skeleton (with simplified joints from the original OpenSim), and the joint positions over time for the skeleton."))
            f.write("\n\n")
            f.write(textwrap.fill(
                "The MuJoCo skeleton DOES NOT HAVE ANY COLLIDERS! It will fall straight through the ground. It's actually an open research question to approximate realistic foot-ground contact in physics engines. Instead of giving you pre-made foot colliders, you'll instead find the ground-reaction-force data, with the center-of-pressure, force direction, and torque between the feet and the ground throughout the trial in ID/*_grf.mot files. You can use that information in combination with the joint positions over time to develop your own foot colliders. Good luck!"))

    if exportSDF:
        with open(path + 'results/SDF/README.txt', 'w') as f:
            f.write(
                "*** This data was generated with AddBiomechanics (www.addbiomechanics.org) ***\n")
            f.write(
                "AddBiomechanics was written by Keenon Werling <keenon@cs.stanford.edu>\n")
            f.write("\n")
            f.write(textwrap.fill(
                "Our automatic conversion to SDF is in early beta! Bug reports are welcome at keenon@cs.stanford.edu."))
            f.write("\n\n")
            f.write(textwrap.fill(
                "This folder contains a SDF skeleton that is compatible with PyBullet (with simplified joints from the original OpenSim), and the joint positions over time for the skeleton."))
            f.write("\n\n")
            f.write(textwrap.fill(
                "The SDF skeleton DOES NOT HAVE ANY COLLIDERS! It will fall straight through the ground. It's actually an open research question to approximate realistic foot-ground contact in physics engines. Instead of giving you pre-made foot colliders, you'll instead find the ground-reaction-force data, with the center-of-pressure, force direction, and torque between the feet and the ground throughout the trial in ID/*_grf.mot files. You can use that information in combination with the joint positions over time to develop your own foot colliders. Good luck!"))

    # Write out summary files for individual trials.
    for itrial, trialName in enumerate(trialNames):
        timestamps = trialTimestamps[itrial]
        trialProcessingResult = trialProcessingResults[i]
        with open(f'{path}/results/IK/{trialName}_ik_summary.txt', 'w') as f:
            f.write('-'*len(trialName) + '--------------------------------------\n')
            f.write(f'Trial {trialName}: Inverse Kinematics Summary\n')
            f.write('-'*len(trialName) + '--------------------------------------\n')
            f.write('\n')

            f.write(textwrap.fill(
                "Automatic processing achieved the following marker errors, averaged over all frames of this trial:"))
            f.write('\n\n')
            markerRMSE = trialProcessingResult['autoAvgRMSE'] * 100
            markerMax = trialProcessingResult['autoAvgMax'] * 100
            f.write(f'  - Avg. Marker RMSE      = {markerRMSE:1.2f} cm\n')
            f.write(f'  - Avg. Marker Max Error = {markerMax:.2f} cm\n')

            if trialBadMarkers[trialName] > 0:
                f.write('\n')
                f.write('Markers with large root-mean-square error:\n')
                f.write('\n')
                for markerName, markerRMSE in trialProcessingResult['markerErrors']:
                    if 100 * markerRMSE > badMarkerThreshold:
                        f.write(f'  - WARNING: Marker {markerName} has RMSE = {100*markerRMSE:.2f} cm!\n')

            if len(trialWarnings[trialName]) > 0:
                f.write('\n')
                f.write(textwrap.fill('The input data for the following markers were modified to enable automatic processing:'))
                f.write('\n\n')
                for warn in trialWarnings[trialName]:
                    f.write(f'  - WARNING: {warn}.\n')

            if len(trialJointWarnings[trialName]):
                f.write('\n')
                f.write(textwrap.fill('The following model coordinates that hit joint limits during inverse kinematics:'))
                f.write('\n\n')
                for warn in trialJointWarnings[trialName]:
                    f.write(f'  - WARNING: {warn}.\n')

            if len(trialInfo[trialName]) > 0:
                f.write('\n')
                f.write(f'Additional information:\n')
                f.write('\n')
                for info in trialInfo[trialName]:
                    f.write(f'  - INFO: {info}.\n')

        if fitDynamics and dynamicsInit is not None:
            badDynamicsFrames = trialBadDynamicsFrames[itrial]
            with open(f'{path}/results/ID/{trialName}_id_summary.txt', 'w') as f:
                f.write('-' * len(trialName) + '--------------------------------\n')
                f.write(f'Trial {trialName}: Inverse Dynamics Summary\n')
                f.write('-' * len(trialName) + '--------------------------------\n')
                f.write('\n')

                f.write(textwrap.fill(
                    "Automatic processing reduced the residual loads needed for dynamic consistency to the following "
                    "magnitudes, averaged over all frames of this trial:"))
                f.write('\n\n')
                residualForce = trialProcessingResult['linearResidual']
                residualTorque = trialProcessingResult['angularResidual']
                f.write(f'  - Avg. Residual Force   = {residualForce:1.2f} N\n')
                f.write(f'  - Avg. Residual Torque  = {residualTorque:1.2f} N-m\n')
                f.write('\n\n')

                numTotalFrames = len(dynamicsInit.missingGRFReason[itrial])
                numBadFrames = trialProcessingResult['numBadDynamicsFrames']
                if numBadFrames:
                    f.write('Ground reaction force inconsistencies\n')
                    f.write('=====================================\n')
                    f.write(textwrap.fill(f'Ground reaction force inconsistencies were detected in {numBadFrames} out '
                                          f'of {numTotalFrames} frames in this trial. See below for a breakdown of why '
                                          f'these "bad" frames were detected.'))
                    f.write('\n')

                    reasonNumber = 1
                    if 'measuredGrfZeroWhenAccelerationNonZero' in badDynamicsFrames:
                        f.write('\n')
                        f.write(f'{reasonNumber}. "Zero GRF, but non-zero acceleration."\n')
                        f.write(f'   --------------------------------------\n')
                        f.write(textwrap.indent(textwrap.fill(
                            'No external ground reaction forces was present, but a non-zero whole-body acceleration '
                            'was detected in the following frames:'), '   '))
                        f.write('\n')
                        for frame in badDynamicsFrames['measuredGrfZeroWhenAccelerationNonZero']:
                            f.write(f'     - frame {frame} (time = {timestamps[frame]:.3f})\n')
                        reasonNumber += 1

                    if 'unmeasuredExternalForceDetected' in badDynamicsFrames:
                        f.write('\n')
                        f.write(f'{reasonNumber}. "Zero acceleration, but non-zero GRF."\n')
                        f.write(f'   --------------------------------------\n')
                        f.write(textwrap.indent(textwrap.fill(
                            'External ground reaction forces were present, but the whole-body acceleration was zero '
                            'in the following frames:'), '   '))
                        f.write('\n')
                        for frame in badDynamicsFrames['unmeasuredExternalForceDetected']:
                            f.write(f'     - frame {frame} (time = {timestamps[frame]:.3f})\n')
                        reasonNumber += 1

                    if 'forceDiscrepancy' in badDynamicsFrames:
                        f.write('\n')
                        f.write(f'{reasonNumber}. "Foot not over a force plate."\n')
                        f.write(f'   ------------------------------\n')
                        f.write(textwrap.indent(textwrap.fill(
                            'After optimizing the center-of-mass kinematics to match the observed ground reaction '
                            'data, an unmeasured external force was still detected in the following frames:'), '   '))
                        f.write('\n')
                        for frame in badDynamicsFrames['forceDiscrepancy']:
                            f.write(f'     - frame {frame} (time = {timestamps[frame]:.3f})\n')
                        reasonNumber += 1

                    if 'torqueDiscrepancy' in badDynamicsFrames:
                        f.write('\n')
                        f.write(f'{reasonNumber}. "Unmeasured external torque."\n')
                        f.write(f'   -----------------------------\n')
                        f.write(textwrap.indent(textwrap.fill(
                            'After optimizing the center-of-mass kinematics to match the observed ground reaction '
                            'data, an unmeasured external torque was still detected in the following frames:'), '   '))
                        f.write('\n')
                        for frame in badDynamicsFrames['torqueDiscrepancy']:
                            f.write(f'     - frame {frame} (time = {timestamps[frame]:.3f})\n')
                        reasonNumber += 1

                    if 'notOverForcePlate' in badDynamicsFrames:
                        f.write('\n')
                        f.write(f'{reasonNumber}. "Foot not over a force plate."\n')
                        f.write(f'   ------------------------------\n')
                        f.write(textwrap.indent(textwrap.fill(
                            'External ground reaction forces were present and the foot was detected '
                            'to be penetrating the ground, but the foot was not located over any '
                            'known force plate in the following frames:'), '   '))
                        f.write('\n')
                        for frame in badDynamicsFrames['notOverForcePlate']:
                            f.write(f'     - frame {frame} (time = {timestamps[frame]:.3f})\n')
                        reasonNumber += 1

                    if 'missingImpact' in badDynamicsFrames:
                        f.write('\n')
                        f.write(f'{reasonNumber}. "Missing foot-ground impact detected."\n')
                        f.write(f'   --------------------------------------\n')
                        f.write(textwrap.indent(textwrap.fill(
                            'TODO...in the following frames:'), '   '))
                        f.write('\n')
                        for frame in badDynamicsFrames['missingImpact']:
                            f.write(f'     - frame {frame} (time = {timestamps[frame]:.3f})\n')
                        reasonNumber += 1

                    if 'missingBlip' in badDynamicsFrames:
                        f.write('\n')
                        f.write(f'{reasonNumber}. "Missing ground reaction force \'blip\' detected."\n')
                        f.write(f'   ------------------------------------------------\n')
                        f.write(textwrap.indent(textwrap.fill(
                            'TODO...in the following frames:'), '   '))
                        f.write('\n')
                        for frame in badDynamicsFrames['missingBlip']:
                            f.write(f'     - frame {frame} (time = {timestamps[frame]:.3f})\n')
                        reasonNumber += 1

                    if 'shiftGRF' in badDynamicsFrames:
                        f.write('\n')
                        f.write(f'{reasonNumber}. "Shifted ground reaction force data."\n')
                        f.write(f'   -------------------------------------\n')
                        f.write(textwrap.indent(textwrap.fill(
                            'The following frames were marked as having missing ground reaction force data due to '
                            'shifting the force data to better match marker data. If you receive this message, then '
                            'an error has occurred. '), '   '))
                        f.write('\n')
                        for frame in badDynamicsFrames['shiftGRF']:
                            f.write(f'     - frame {frame} (time = {timestamps[frame]:.3f})\n')
                        reasonNumber += 1

    shutil.move(path + 'results', path + outputName)
    print('Zipping up OpenSim files', flush=True)
    shutil.make_archive(path + outputName, 'zip', path, outputName)
    print('Finished outputting OpenSim files', flush=True)

    # Write out the result summary JSON
    try:
        with open(path+'_results.json', 'w') as f:
            json.dump(processingResult, f)
    except Exception as e:
        print('Had an error writing _results.json:', flush=True)
        print(e, flush=True)

    print('Generated a final zip file at '+path+outputName+'.zip')
    # counter = 0
    # while True:
    #     print('[For live log demo] Counting to 10: '+str(counter), flush=True)
    #     counter += 1
    #     time.sleep(1)
    #     if counter > 10:
    #         break
    print('Done!', flush=True)


if __name__ == "__main__":
    print(sys.argv, flush=True)
    # processLocalSubjectFolder("/tmp/tmpa4sqewbz", "some_user_name_results")
    # processLocalSubjectFolder("/tmp/tmpqg3u6hdr", "some_user_name_results")
    # processLocalSubjectFolder("/tmp/tmpa0c7p0na")
    # processLocalSubjectFolder("/tmp/tmp_287z04g")
    # processLocalSubjectFolder("/tmp/tmp99d3lw9v/")
    processLocalSubjectFolder(
        sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None, sys.argv[3] if len(sys.argv) > 3 else '')
