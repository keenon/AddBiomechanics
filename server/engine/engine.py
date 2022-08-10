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
import traceback

GEOMETRY_FOLDER_PATH = absPath('Geometry')


def requireExists(path: str, reason: str):
    if not os.path.exists(path):
        print('ERROR: File "'+path+'" required as "' +
              reason+'" does not exist. Quitting.')
        exit(1)


def processLocalSubjectFolder(path: str, outputName: str = None):
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

    # 3. Load the unscaled Osim file, which we can then scale and format

    # 3.0. Check for if we're using a preset OpenSim model, and if so, then copy that in
    if skeletonPreset == 'vicon':
        shutil.copy('/data/PresetSkeletons/Rajagopal2015_ViconPlugInGait.osim',
                    path + 'unscaled_generic.osim')
    elif skeletonPreset == 'cmu':
        shutil.copy('/data/PresetSkeletons/Rajagopal2015_CMUMarkerSet.osim',
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
    fitter = nimble.biomechanics.MarkerFitter(
        customOsim.skeleton, customOsim.markersMap)
    fitter.setInitialIKSatisfactoryLoss(0.05)
    fitter.setInitialIKMaxRestarts(50)
    fitter.setIterationLimit(500)
    # fitter.setIterationLimit(20)
    # fitter.setInitialIKMaxRestarts(10)

    guessedTrackingMarkers = False
    if len(customOsim.anatomicalMarkers) > 10:
        fitter.setTrackingMarkers(customOsim.trackingMarkers)
    else:
        print('NOTE: The input *.osim file specified suspiciously few ('+str(len(customOsim.anatomicalMarkers)) +
              ', less than the minimum 10) anatomical landmark markers (with <fixed>true</fixed>), so we will default to treating all markers as anatomical except triad markers with the suffix "1", "2", or "3"', flush=True)
        fitter.setTriadsToTracking()
        guessedTrackingMarkers = True
    # This is 1.0x the values in the default code
    fitter.setRegularizeAnatomicalMarkerOffsets(10.0)
    # This is 1.0x the default value
    fitter.setRegularizeTrackingMarkerOffsets(0.05)
    # These are 2x the values in the default code
    # fitter.setMinSphereFitScore(3e-5 * 2)
    # fitter.setMinAxisFitScore(6e-5 * 2)
    fitter.setMinSphereFitScore(0.01)
    fitter.setMinAxisFitScore(0.001)
    # Default max joint weight is 0.5, so this is 2x the default value
    fitter.setMaxJointWeight(1.0)

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
            fitter.autorotateC3D(c3dFile)
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
                    grfFilePath)
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
        trialErrorReport = fitter.generateDataErrorsReport(markerTrials[i])
        markerTrials[i] = trialErrorReport.markerObservationsAttemptedFixed
        trialErrorReports.append(trialErrorReport)
        hasEnoughMarkers = fitter.checkForEnoughMarkers(markerTrials[i])
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
        '/data/ANSUR_metrics.xml')
    cols = anthropometrics.getMetricNames()
    cols.append('Heightin')
    cols.append('Weightlbs')
    if sex == 'male':
        gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
            '/data/ANSUR_II_MALE_Public.csv',
            cols,
            0.001)  # mm -> m
    elif sex == 'female':
        gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
            '/data/ANSUR_II_FEMALE_Public.csv',
            cols,
            0.001)  # mm -> m
    else:
        gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
            '/data/ANSUR_II_BOTH_Public.csv',
            cols,
            0.001)  # mm -> m
    observedValues = {
        'Heightin': heightM * 39.37 * 0.001,
        'Weightlbs': massKg * 2.204 * 0.001,
    }
    gauss = gauss.condition(observedValues)
    anthropometrics.setDistribution(gauss)
    fitter.setAnthropometricPrior(anthropometrics, 0.1)

    # Run the kinematics pipeline
    results: List[nimble.biomechanics.MarkerInitialization] = fitter.runMultiTrialKinematicsPipeline(
        markerTrials,
        nimble.biomechanics.InitialMarkerFitParams()
        .setMaxTrialsToUseForMultiTrialScaling(5)
        .setMaxTimestepsToUseForMultiTrialScaling(4000),
        150)

    # Check for any flipped markers, now that we've done a first pass
    anySwapped = False
    for i in range(len(trialNames)):
        if fitter.checkForFlippedMarkers(markerTrials[i], results[i], trialErrorReports[i]):
            anySwapped = True
            markerTrials[i] = trialErrorReports[i].markerObservationsAttemptedFixed

    if anySwapped:
        print("******** Unfortunately, it looks like some markers were swapped in the uploaded data, so we have to run the whole pipeline again with unswapped markers. ********")
        results = fitter.runMultiTrialKinematicsPipeline(
            markerTrials,
            nimble.biomechanics.InitialMarkerFitParams()
            .setMaxTrialsToUseForMultiTrialScaling(5)
            .setMaxTimestepsToUseForMultiTrialScaling(4000),
            150)

    customOsim.skeleton.setGroupScales(results[0].groupScales)
    fitMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode,
                                np.ndarray]] = results[0].updatedMarkerMap

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
    for i in range(customOsim.skeleton.getNumBodyNodes()):
        bodyNode: nimble.dynamics.BodyNode = customOsim.skeleton.getBodyNode(i)
        # Now that we adjust the markers BEFORE we rescale the body, we don't want to rescale the marker locations at all
        bodyScalesMap[bodyNode.getName()] = [1, 1, 1]  # bodyNode.getScale()
    markerOffsetsMap: Dict[str, Tuple[str, np.ndarray]] = {}
    markerNames: List[str] = []
    for k in fitMarkers:
        v = fitMarkers[k]
        markerOffsetsMap[k] = (v[0].getName(), v[1])
        markerNames.append(k)
    nimble.biomechanics.OpenSimParser.moveOsimMarkers(
        path + 'unscaled_generic.osim', bodyScalesMap, markerOffsetsMap, path + 'results/Models/unscaled_but_with_optimized_markers.osim')

    # 8.2.2. Write the XML instructions for the OpenSim scaling tool
    nimble.biomechanics.OpenSimParser.saveOsimScalingXMLFile(
        'optimized_scale_and_markers', customOsim.skeleton, massKg, heightM, 'Models/unscaled_but_with_optimized_markers.osim', 'Unassigned', 'Models/optimized_scale_and_markers.osim', path + 'results/Models/rescaling_setup.xml')
    # 8.2.3. Call the OpenSim scaling tool
    command = 'cd '+path+'results && opensim-cmd run-tool ' + \
        path + 'results/Models/rescaling_setup.xml'
    print('Scaling OpenSim files: '+command, flush=True)
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()

    # Delete the OpenSim log from running the scale tool
    if os.path.exists(path + 'results/opensim.log'):
        os.remove(path + 'results/opensim.log')

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

        if exportSDF:
            print('Writing an SDF version of the skeleton', flush=True)
            nimble.utils.SdfParser.writeSkeleton(
                path + 'results/SDF/model.sdf', simplified)
            sdfSkeleton = nimble.utils.SdfParser.readSkeleton(
                path + 'results/SDF/model.sdf')
            sdfConverter: nimble.biomechanics.SkeletonConverter = nimble.biomechanics.SkeletonConverter(
                sdfSkeleton, customOsim.skeleton)
            # Set the root orientation to be the same
            for i in range(6):
                sdfSkeleton.setPosition(i, customOsim.skeleton.getPosition(i))
            # Link joints
            for i in range(sdfSkeleton.getNumJoints()):
                sourceJoint = sdfSkeleton.getJoint(i)
                if customOsim.skeleton.getJoint(sourceJoint.getName()) is not None:
                    sdfConverter.linkJoints(
                        sourceJoint, customOsim.skeleton.getJoint(sourceJoint.getName()))
            sdfConverter.createVirtualMarkers()

        if exportMJCF:
            print('Writing a MuJoCo version of the skeleton', flush=True)
            nimble.utils.MJCFExporter.writeSkeleton(
                path + 'results/MuJoCo/model.xml', simplified)
            mujocoConverter: nimble.biomechanics.SkeletonConverter = nimble.biomechanics.SkeletonConverter(
                simplified, customOsim.skeleton)
            # Set the root orientation to be the same
            for i in range(6):
                simplified.setPosition(i, customOsim.skeleton.getPosition(i))
            # Link joints
            for i in range(simplified.getNumJoints()):
                sourceJoint = simplified.getJoint(i)
                if customOsim.skeleton.getJoint(sourceJoint.getName()) is not None:
                    mujocoConverter.linkJoints(
                        sourceJoint, customOsim.skeleton.getJoint(sourceJoint.getName()))
            mujocoConverter.createVirtualMarkers()

    # Get ready to count the number of times we run up against joint limits during the IK
    dofNames: List[str] = []
    jointLimitsHits: Dict[str, int] = {}
    for i in range(customOsim.skeleton.getNumDofs()):
        dofNames.append(customOsim.skeleton.getDofByIndex(i).getName())
        jointLimitsHits[customOsim.skeleton.getDofByIndex(i).getName()] = 0
    trialJointWarnings: Dict[str, List[str]] = {}

    for i in range(len(results)):
        result = results[i]
        trialName = trialNames[i]
        c3dFile = c3dFiles[trialName] if trialName in c3dFiles else None
        forcePlates = trialForcePlates[i]
        framesPerSecond = trialFramesPerSecond[i]
        timestamps = trialTimestamps[i]
        markerTimesteps = markerTrials[i]
        trialProcessingResult = trialProcessingResults[i]
        trialPath = path + 'trials/' + trialName + '/'

        resultIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
            customOsim.skeleton, fitMarkers, result.poses, markerTimesteps)
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
                trialName, markerNames, "Models/manually_scaled.osim", '../MarkerData/'+trialName+'.trc', trialName+'_ik_on_manual_scaling_by_opensim.mot', path + 'results/IK/'+trialName+'_ik_on_manually_scaled_setup.xml')

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

        # Write out the .mot files
        print('Writing OpenSim '+path+'results/IK/' +
              trialName+'.mot file, shape='+str(result.poses.shape), flush=True)
        nimble.biomechanics.OpenSimParser.saveMot(
            customOsim.skeleton, path + 'results/IK/'+trialName+'_ik.mot', timestamps, result.poses)
        resultIK.saveCSVMarkerErrorReport(
            path + 'results/IK/'+trialName+'_ik_per_marker_error_report.csv')
        nimble.biomechanics.OpenSimParser.saveGRFMot(
            path + 'results/ID/'+trialName+'_grf.mot', timestamps, forcePlates)
        nimble.biomechanics.OpenSimParser.saveTRC(
            path + 'results/MarkerData/'+trialName+'.trc', timestamps, markerTimesteps)
        if c3dFile is not None:
            shutil.copyfile(trialPath + 'markers.c3d', path +
                            'results/C3D/' + trialName + '.c3d')
        # Save OpenSim setup files to make it easy to (re)run IK and ID on the results in OpenSim
        nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
            trialName, markerNames, "Models/optimized_scale_and_markers.osim", '../MarkerData/'+trialName+'.trc', trialName+'_ik_by_opensim.mot', path + 'results/IK/'+trialName+'_ik_setup.xml')
        nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsForcesXMLFile(
            trialName, customOsim.skeleton, result.poses, forcePlates, trialName+'_grf.mot', path + 'results/ID/'+trialName+'_external_forces.xml')
        nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
            trialName, 'Models/optimized_scale_and_markers.osim', '../IK/'+trialName+'_ik.mot', trialName+'_external_forces.xml', trialName+'_id.sto', trialName+'_id_body_forces.sto', path + 'results/ID/'+trialName+'_id_setup.xml')

        # 8.2. Write out the animation preview
        # 8.2.1. Create the raw JSON
        if (goldOsim is not None) and (goldMot is not None):
            print('Saving trajectory, markers, and the manual IK to a GUI log ' +
                  trialPath+'preview.bin', flush=True)
            print('goldOsim: '+str(goldOsim), flush=True)
            print('goldMot.poses.shape: '+str(goldMot.poses.shape), flush=True)
            fitter.saveTrajectoryAndMarkersToGUI(
                trialPath+'preview.bin', result, markerTimesteps, framesPerSecond, forcePlates, goldOsim, goldMot.poses)
        else:
            print('Saving trajectory and markers to a GUI log ' +
                  trialPath+'preview.bin', flush=True)
            fitter.saveTrajectoryAndMarkersToGUI(
                trialPath+'preview.bin', result, markerTimesteps, framesPerSecond, forcePlates)
        # 8.2.2. Zip it up
        print('Zipping up '+trialPath+'preview.bin', flush=True)
        subprocess.run(["zip", "-r", 'preview.bin.zip',
                       'preview.bin'], cwd=trialPath, capture_output=True)
        print('Finished zipping up '+trialPath+'preview.bin.zip', flush=True)

        # 8.3. Count up the number of times we hit against joint limits

        trialJointLimitHits: Dict[str, int] = {}
        jointLimitsFrames: Dict[str, List[int]] = {}
        jointLimitsFramesUpperBound: Dict[str, List[bool]] = {}
        for i in range(customOsim.skeleton.getNumDofs()):
            dofName = customOsim.skeleton.getDofByIndex(i).getName()
            trialJointLimitHits[dofName] = 0
            jointLimitsFrames[dofName] = []
            jointLimitsFramesUpperBound[dofName] = []

        tol = 0.001
        for t in range(result.poses.shape[1]):
            thisTimestepPos = result.poses[:, t]
            for i in range(customOsim.skeleton.getNumDofs()):
                dof = customOsim.skeleton.getDofByIndex(i)
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

        # 8.3.1. Sort for trial joint limits

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

        if exportSDF:
            # 8.4. Convert to SDF, and write that out
            print('Converting '+trialName+' to SDF skeleton', flush=True)
            convertedPoses = sdfConverter.convertMotion(
                result.poses, convergenceThreshold=1e-9, maxStepCount=1000)
            print('Finished converting '+trialName +
                  ' to SDF. Writing out .mot file...', flush=True)
            nimble.biomechanics.OpenSimParser.saveMot(
                sdfSkeleton, path + 'results/SDF/'+trialName+'_ik.mot', timestamps, convertedPoses)

        if exportMJCF:
            # 8.4. Convert to MuJoCo, and write that out
            print('Converting '+trialName+' to MuJoCo skeleton', flush=True)
            convertedPoses = mujocoConverter.convertMotion(
                result.poses, convergenceThreshold=1e-9, maxStepCount=1000)
            print('Finished converting '+trialName +
                  ' to MuJoCo. Writing out .mot file...', flush=True)
            nimble.biomechanics.OpenSimParser.saveMot(
                simplified, path + 'results/MuJoCo/'+trialName+'_ik.mot', timestamps, convertedPoses)

        print('Success! Done with '+trialName+'.', flush=True)

    if os.path.exists(path + 'manually_scaled.osim'):
        shutil.copyfile(path + 'manually_scaled.osim', path +
                        'results/Models/manually_scaled.osim')

    # Copy over the geometry files, so the model can be loaded directly in OpenSim without chasing down Geometry files somewhere else
    shutil.copytree('/data/Geometry', path +
                    'results/Models/Geometry')
    # Copy over the geometry files (in a MuJoCo specific file format), so the model can be loaded directly in MuJoCo without chasing down Geometry files somewhere else
    if exportMJCF:
        shutil.copytree('/data/MuJoCoGeometry', path +
                        'results/MuJoCo/Geometry')
    # Copy over the geometry files (in a SDF specific file format), so the model can be loaded directly in PyBullet without chasing down Geometry files somewhere else
    if exportSDF:
        shutil.copytree('/data/SDFGeometry', path +
                        'results/SDF/Geometry')

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
    processingResult['guessedTrackingMarkers'] = guessedTrackingMarkers
    processingResult['trialMarkerSets'] = trialMarkerSet
    processingResult['osimMarkers'] = list(customOsim.markersMap.keys())

    trialWarnings: Dict[str, List[str]] = {}
    trialInfo: Dict[str, List[str]] = {}
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
            "AddBiomechanics was written by Keenon Werling <keenon@cs.stanford.edu>\n")
        f.write("\n")
        f.write(textwrap.fill(
            "Automatic processing achieved the following marker errors (averaged over all frames of all trials):"))
        f.write("\n\n")
        f.write(" - RMSE: "+('%.2f' %
                (processingResult['autoAvgRMSE'] * 100))+'cm, Max: '+('%.2f' % (processingResult['autoAvgMax'] * 100))+'cm')
        f.write("\n\n")
        f.write(textwrap.fill(
            "The following trials were processed to perform automatic body scaling and marker registration:"))
        f.write("\n\n")
        for i in range(len(results)):
            trialName = trialNames[i]
            f.write(" - MarkerData/" + trialName+'.trc (RMSE: '+('%.2f' % (trialProcessingResults[i]['autoAvgRMSE'] * 100))+'cm, Max: '+('%.2f' %
                                                                                                                                         (trialProcessingResults[i]['autoAvgMax']*100))+'cm)\n')
            for j in range(min(len(trialProcessingResults[i]['markerErrors']), 5)):
                markerName, markerRMSE = trialProcessingResults[i]['markerErrors'][j]
                f.write("     " + str(j+1)+" Worst Marker \"")
                f.write(markerName)
                f.write("\" (RMSE: "+('%.2f' % (markerRMSE * 100))+'cm)')
                f.write('\n')
            for warn in trialWarnings[trialName]:
                f.write("     >> MARKER WARNING: ")
                f.write(warn)
                f.write('\n')
            for warn in trialJointWarnings[trialName]:
                f.write("     >> JOINT WARNING: ")
                f.write(warn)
                f.write('\n')
            for info in trialInfo[trialName]:
                f.write("     >> INFO: ")
                f.write(info)
                f.write('\n')
        f.write("\n")
        f.write(textwrap.fill(
            "The model file containing optimal body scaling and marker offsets is:"))
        f.write("\n\n")
        f.write("Models/optimized_scale_and_markers.osim")
        f.write("\n\n")
        f.write(textwrap.fill(
            "This tool works by finding an optimal scaling and an optimal marker offsets at the same time."))
        f.write("\n\n")
        f.write(textwrap.fill("If you want to manually edit the marker offsets, you can modify the <MarkerSet> in \"Models/unscaled_but_with_optimized_markers.osim\" (by default this file contains the marker offsets found by the optimizer). If you want to tweak the Scaling, you can edit \"Models/rescaling_setup.xml\". If you change either of these files, then run (FROM THIS FOLDER, and not including the leading \"> \"):"))
        f.write("\n\n")
        f.write(" > opensim-cmd run-tool Models/rescaling_setup.xml\n")
        f.write(
            '           # This will re-generate Models/optimized_scale_and_markers.osim\n')
        f.write("\n\n")
        f.write(textwrap.fill("You do not need to re-run Inverse Kinematics unless you change scaling, because the output motion files are already generated for you as \"*_ik.mot\" files for each trial, but you are welcome to confirm our results using OpenSim. To re-run Inverse Kinematics with OpenSim, to verify the results of AddBiomechanics, you can use the automatically generated XML configuration files. Here are the command-line commands you can run (FROM THIS FOLDER, and not including the leading \"> \") to verify IK results for each trial:"))
        f.write("\n\n")
        for i in range(len(results)):
            trialName = trialNames[i]
            f.write(" > opensim-cmd run-tool IK/" +
                    trialName+'_ik_setup.xml\n')
            f.write("           # This will create a results file IK/" +
                    trialName+'_ik_by_opensim.mot\n')
        f.write("\n\n")

        if os.path.exists(path + 'manually_scaled.osim'):
            f.write(textwrap.fill("You included a manually scaled model to compare against. That model has been copied into this folder as \"manually_scaled.osim\". You can use the automatically generated XML configuration files to run IK using your manual scaling as well. Here are the command-line commands you can run (FROM THIS FOLDER, and not including the leading \"> \") to compare IK results for each trial:"))
            f.write("\n\n")
            for i in range(len(results)):
                trialName = trialNames[i]
                f.write(" > opensim-cmd run-tool IK/" + trialName +
                        '_ik_on_manually_scaled_setup.xml\n')
                f.write("           # This will create a results file IK/" +
                        trialName+'_ik_on_manual_scaling_by_opensim.mot\n')
            f.write("\n\n")

        f.write(textwrap.fill("To run Inverse Dynamics with OpenSim, you can also use automatically generated XML configuration files. WARNING: Inverse Dynamics is not yet fully supported by AddBiomechanics, and so the mapping of force-plates to feet is not perfect. The default XML files assign each force plate to the `calcn_*` body that gets closest to it during the motion trial. THIS MAY NOT BE CORRECT! That said, hopefully this is at least a useful starting point for you to edit from. The following commands should work (FROM THIS FOLDER, and not including the leading \"> \"):\n"))
        f.write("\n\n")
        for i in range(len(results)):
            trialName = trialNames[i]
            f.write(" > opensim-cmd run-tool ID/" +
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
        f.write("\n\n")
        f.write(textwrap.fill(
            "If you encounter errors, please contact Keenon Werling at keenon@cs.stanford.edu, and I will do my best to help :)"))

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
    print(sys.argv)
    # processLocalSubjectFolder("/tmp/tmpa4sqewbz", "some_user_name_results")
    # processLocalSubjectFolder("/tmp/tmpqg3u6hdr", "some_user_name_results")
    # processLocalSubjectFolder("/tmp/tmpa0c7p0na")
    # processLocalSubjectFolder("/tmp/tmp_287z04g")
    # processLocalSubjectFolder("/tmp/tmp99d3lw9v/")
    processLocalSubjectFolder(
        sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
