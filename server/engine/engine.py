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

        trialProcessingResults.append(trialProcessingResult)

    print('Fitting trials '+str(trialNames), flush=True)

    # 7. Process the trial
    fitter = nimble.biomechanics.MarkerFitter(
        customOsim.skeleton, customOsim.markersMap)
    fitter.setInitialIKSatisfactoryLoss(0.05)
    fitter.setInitialIKMaxRestarts(50)
    fitter.setIterationLimit(500)
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
    if not os.path.exists(path+'results/ForceData'):
        os.mkdir(path+'results/ForceData')
    if not os.path.exists(path+'results/MarkerData'):
        os.mkdir(path+'results/MarkerData')
    print('Outputting OpenSim files', flush=True)
    # 8.2.1. Write the XML instructions for the OpenSim scaling tool
    nimble.biomechanics.OpenSimParser.saveOsimScalingXMLFile(
        'Autoscaled', customOsim.skeleton, massKg, heightM, path + 'unscaled_generic.osim', path + 'rescaled.osim', path + 'scaling_instructions.xml')
    # 8.2.2. Call the OpenSim scaling tool
    command = 'opensim-cmd run-tool ' + path + 'scaling_instructions.xml'
    print('Scaling OpenSim files: '+command)
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE)
    process.wait()

    # 8.2.3. Adjusting marker locations
    print('Adjusting marker locations on scaled OpenSim file', flush=True)
    bodyScalesMap: Dict[str, np.ndarray] = {}
    for i in range(customOsim.skeleton.getNumBodyNodes()):
        bodyNode: nimble.dynamics.BodyNode = customOsim.skeleton.getBodyNode(i)
        bodyScalesMap[bodyNode.getName()] = bodyNode.getScale()
    markerOffsetsMap: Dict[str, Tuple[str, np.ndarray]] = {}
    markerNames: List[str] = []
    for k in fitMarkers:
        v = fitMarkers[k]
        markerOffsetsMap[k] = (v[0].getName(), v[1])
        markerNames.append(k)
    nimble.biomechanics.OpenSimParser.moveOsimMarkers(
        path + 'rescaled.osim', bodyScalesMap, markerOffsetsMap, path + 'results/Models/autoscaled.osim')

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

        print('Saving trial '+str(trialName)+' results', flush=True)

        print('auto scaled average RMSE m: ' +
              str(resultIK.averageRootMeanSquaredError), flush=True)
        print('auto scaled average max m: ' +
              str(resultIK.averageMaxError), flush=True)

        # Load the gold .mot file, if one exists
        goldMot: nimble.biomechanics.OpenSimMot = None
        if os.path.exists(trialPath + 'manual_ik.mot') and goldOsim is not None:
            goldMot = nimble.biomechanics.OpenSimParser.loadMot(
                goldOsim.skeleton, trialPath + 'manual_ik.mot')

            shutil.copyfile(trialPath + 'manual_ik.mot', path +
                            'results/IK/' + trialName + '_manual_scaling_ik.mot')
            nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                trialName, markerNames, "Models/manually_scaled.osim", '../MarkerData/'+trialName+'.trc', trialName+'_ik_on_manual_scaling_by_opensim.mot', path + 'results/IK/'+trialName+'_ik_on_manually_scaled_setup.xml')

            originalIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
                goldOsim.skeleton, goldOsim.markersMap, goldMot.poses, c3dFile.markerTimesteps)
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
            customOsim.skeleton, path + 'results/IK/'+trialName+'_ik.mot', c3dFile.timestamps, result.poses)
        nimble.biomechanics.OpenSimParser.saveGRFMot(
            path + 'results/ForceData/'+trialName+'_grf.mot', c3dFile.timestamps, c3dFile.forcePlates)
        nimble.biomechanics.OpenSimParser.saveTRC(
            path + 'results/MarkerData/'+trialName+'.trc', c3dFile.timestamps, c3dFile.markerTimesteps)
        shutil.copyfile(trialPath + 'markers.c3d', path +
                        'results/C3D/' + trialName + '.c3d')
        # Save OpenSim setup files to make it easy to (re)run IK and ID on the results in OpenSim
        nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
            trialName, markerNames, "Models/autoscaled.osim", '../MarkerData/'+trialName+'.trc', trialName+'_ik_by_opensim.mot', path + 'results/IK/'+trialName+'_ik_setup.xml')
        nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsForcesXMLFile(
            trialName, customOsim.skeleton, result.poses, c3dFile.forcePlates, '../ForceData/'+trialName+'_grf.mot', path + 'results/ID/'+trialName+'_external_forces.xml')
        nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
            trialName, 'Models/autoscaled.osim', '../IK/'+trialName+'_ik.mot', trialName+'_external_forces.xml', trialName+'_id.sto', trialName+'_id_body_forces.sto', path + 'results/ID/'+trialName+'_id_setup.xml')

        # 8.2. Write out the animation preview
        # 8.2.1. Create the raw JSON
        if (goldOsim is not None) and (goldMot is not None):
            print('Saving trajectory, markers, and the manual IK to a GUI log ' +
                  trialPath+'preview.json', flush=True)
            print('goldOsim: '+str(goldOsim), flush=True)
            print('goldMot.poses.shape: '+str(goldMot.poses.shape), flush=True)
            fitter.saveTrajectoryAndMarkersToGUI(
                trialPath+'preview.json', result, markerTimesteps, c3dFile, goldOsim, goldMot.poses)
        else:
            print('Saving trajectory and markers to a GUI log ' +
                  trialPath+'preview.json', flush=True)
            fitter.saveTrajectoryAndMarkersToGUI(
                trialPath+'preview.json', result, markerTimesteps, c3dFile)
        # 8.2.2. Zip it up
        print('Zipping up '+trialPath+'preview.json', flush=True)
        subprocess.run(["zip", "-r", trialPath+'preview.json.zip', trialPath +
                        'preview.json'], capture_output=True)
        print('Finished zipping up '+trialPath+' preview.json.zip', flush=True)

    if os.path.exists(path + 'manually_scaled.osim'):
        shutil.copyfile(path + 'manually_scaled.osim', path +
                        'results/Models/manually_scaled.osim')

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

    # Write out the README for the data
    with open(path + 'results/README.txt', 'w') as f:
        f.write(
            "*** This data was generated with BiomechNet (www.biomechnet.org) ***\n")
        f.write("BiomechNet was written by Keenon Werling <keenon@cs.stanford.edu>\n")
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
            f.write(" - C3D/" + trialName+'.c3d (RMSE: '+('%.2f' % (trialProcessingResults[i]['autoAvgRMSE'] * 100))+'cm, Max: '+('%.2f' %
                                                                                                                                  (trialProcessingResults[i]['autoAvgRMSE']*100))+'cm)\n')
        f.write("\n")
        f.write(textwrap.fill(
            "The model file containing optimal body scaling and marker offsets is:"))
        f.write("\n\n")
        f.write("Models/autoscaled.osim")
        f.write("\n\n")
        f.write(textwrap.fill("You do not need to re-run Inverse Kinematics, because the output motion files are already generated for you as \"*_ik.mot\" files for each trial, but you are welcome to confirm our results using OpenSim. To re-run Inverse Kinematics with OpenSim, to verify the results of BiomechNet, you can use the automatically generated XML configuration files. Here are the command-line commands you can run (FROM THIS FOLDER, and not including the leading \"> \") to verify IK results for each trial:"))
        f.write("\n\n")
        for i in range(len(results)):
            trialName = trialNames[i]
            f.write(" > opensim-cmd run-tool IK/" +
                    trialName+'_ik_setup.xml\n')
            f.write("           This will create a results file IK/" +
                    trialName+'_ik_by_opensim.mot\n')
        f.write("\n\n")

        if os.path.exists(path + 'manually_scaled.osim'):
            f.write(textwrap.fill("You included a manually scaled model to compare against. That model has been copied into this folder as \"manually_scaled.osim\". You can use the automatically generated XML configuration files to run IK using your manual scaling as well. Here are the command-line commands you can run (FROM THIS FOLDER, and not including the leading \"> \") to compare IK results for each trial:"))
            f.write("\n\n")
            for i in range(len(results)):
                trialName = trialNames[i]
                f.write(" > opensim-cmd run-tool IK/" + trialName +
                        '_ik_on_manually_scaled_setup.xml\n')
                f.write("           This will create a results file IK/" +
                        trialName+'_ik_on_manual_scaling_by_opensim.mot\n')
            f.write("\n\n")

        f.write(textwrap.fill("To run Inverse Dynamics with OpenSim, you can also use automatically generated XML configuration files. WARNING: Inverse Dynamics is not yet fully supported by BiomechNet, and so the mapping of force-plates to feet is not perfect. The default XML files assign each force plate to the `calcn_*` body that gets closest to it during the motion trial. THIS MAY NOT BE CORRECT! That said, hopefully this is at least a useful starting point for you to edit from. The following commands should work (FROM THIS FOLDER, and not including the leading \"> \"):\n"))
        f.write("\n\n")
        for i in range(len(results)):
            trialName = trialNames[i]
            f.write(" > opensim-cmd run-tool ID/" +
                    trialName+'_id_setup.xml\n')
            f.write("           This will create a results file ID/" +
                    trialName+'_id.sto\n')
        f.write("\n\n")
        f.write(textwrap.fill(
            "If you encounter errors, please contact Keenon Werling at keenon@cs.stanford.edu, and I will do my best to help :)"))

    print('Zipping up OpenSim files', flush=True)
    shutil.make_archive(path + 'osim_results', 'zip', path, 'results')
    print('Finished outputting OpenSim files', flush=True)

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
    # processLocalSubjectFolder("/tmp/tmpa0c7p0na")
    # processLocalSubjectFolder("/tmp/tmp_287z04g")
    # processLocalSubjectFolder("/tmp/tmp99d3lw9v/")
    processLocalSubjectFolder(sys.argv[1])
