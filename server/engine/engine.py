#!/usr/bin/python3
"""
engine.py
---------
Description: The main pipeline that servers as the "engine" for the AddBiomechanics data processing software.
Author(s): Keenon Werling, Nicholas Bianco
"""

import sys
import nimblephysics as nimble
import os
from nimblephysics.loader import absPath
import json
from typing import Any, Dict, List, Tuple
import numpy as np
import subprocess
import shutil
import textwrap
import glob
import traceback
from plotting import plot_ik_results, plot_id_results, plot_marker_errors, plot_grf_data
from helpers import detect_nonzero_force_segments, filter_nonzero_force_segments, get_consecutive_values, \
    reconcile_markered_and_nonzero_force_segments, detect_markered_segments


GEOMETRY_FOLDER_PATH = absPath('Geometry')
DATA_FOLDER_PATH = absPath('../data')


class Engine(object):  # metaclass=ExceptionHandlingMeta):
    def __init__(self,
                 path: str,
                 output_name: str,
                 href: str):

        # 0. Initialize the engine.
        # -------------------------

        # 0.1. Basic inputs.
        self.path = path
        self.trialsFolderPath = self.path + 'trials/'
        self.subject_json_path = self.path + '_subject.json'
        self.geometry_symlink_path = self.path + 'Geometry'
        self.output_name = output_name
        self.href = href
        self.processingResult: Dict[str, Any] = {}

        # 0.2. Subject pipeline parameters.
        self.massKg = 68.0
        self.heightM = 1.6
        self.sex = 'unknown'
        self.skeletonPreset = 'custom'
        self.exportSDF = False
        self.exportMJCF = False
        self.exportOSIM = True
        self.ignoreJointLimits = False
        self.residualsToZero = False
        self.useReactionWheels = False
        self.tuneResidualLoss = 1.0
        self.shiftGRF = False
        self.maxTrialsToSolveMassOver = 4
        self.regularizeJointAcc = 0
        self.dynamicsMarkerOffsets = False
        self.dynamicsMarkerWeight = 50.0
        self.dynamicsJointWeight = 0.01
        self.dynamicsRegularizePoses = 0.01
        self.ignoreFootNotOverForcePlate = False
        self.disableDynamics = False
        self.segmentTrials = True
        self.minSegmentDuration = 0.05
        self.mergeZeroForceSegmentsThreshold = 1.0
        self.footBodyNames = ['calcn_l', 'calcn_r']
        self.totalForce = 0.0
        self.fitDynamics = False
        self.skippedDynamicsReason = None

        # 0.3. Shared data structures.
        self.skeleton = None
        self.markerSet = None
        self.customOsim = None
        self.goldOsim = None
        self.simplified = None
        self.trialNames = []
        self.c3dFiles: Dict[str, nimble.biomechanics.C3D] = {}
        self.trialForcePlates: List[List[nimble.biomechanics.ForcePlate]] = []
        self.trialTimestamps: List[List[float]] = []
        self.trialFramesPerSecond: List[int] = []
        self.trialMarkerSet: Dict[str, List[str]] = {}
        self.markerTrials = []
        self.trialProcessingResults: List[Dict[str, Any]] = []
        self.finalSkeleton = None
        self.finalPoses = []
        self.fitMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
        self.finalMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
        self.finalInverseDynamics = []
        self.bodyMasses = []

        # 0.4. Solvers.
        self.markerFitter = None
        self.dynamicsFitter = None
        self.dynamicsInit = None

        # 0.5. Outputs.
        self.guessedTrackingMarkers = False
        self.markerFitterResults = None
        self.totalFrames = 0
        self.trialErrorReports: List[str, nimble.biomechanics.MarkersErrorReport] = []
        self.trialBadDynamicsFrames: List[Dict[str, List[int]]] = []
        self.jointLimitsHits: Dict[str, int] = {}
        self.trialJointWarnings: Dict[str, List[str]] = {}
        self.trialDynamicsSegments: List[List[Tuple[int, int]]] = []

    def validate_paths(self):

        # 1. Validate all data input paths.
        # ---------------------------------
        # 1.1. Check that the Geometry folder exists.
        if not os.path.exists(GEOMETRY_FOLDER_PATH):
            raise Exception('Geometry folder "' + GEOMETRY_FOLDER_PATH + '" does not exist. Quitting...')

        # 1.2. Symlink in Geometry, if it doesn't come with the folder, so we can load meshes for the visualizer.
        if not os.path.exists(self.geometry_symlink_path):
            os.symlink(GEOMETRY_FOLDER_PATH, self.geometry_symlink_path)

        # 1.3. Get the subject JSON file path.
        if not os.path.exists(self.subject_json_path):
            raise Exception('Subject JSON file "' + self.subject_json_path + '" does not exist. Quitting...')

        # 1.4. Check that the trials folder exists.
        if not os.path.exists(self.trialsFolderPath):
            raise Exception('Trials folder "' + self.trialsFolderPath + '" does not exist. Quitting...')

    def parse_subject_json(self):

        # 2. Read the subject parameters from the JSON file.
        # --------------------------------------------------
        with open(self.subject_json_path) as subj:
            subjectJson = json.loads(subj.read())

        if 'massKg' in subjectJson:
            self.massKg = float(subjectJson['massKg'])
        else:
            print('ERROR: No mass specified for subject. Exiting...')
            exit(1)

        if 'heightM' in subjectJson:
            self.heightM = float(subjectJson['heightM'])
        else:
            print('ERROR: No height specified for subject. Exiting...')
            exit(1)

        if 'sex' in subjectJson:
            self.sex = subjectJson['sex']
        else:
            print('WARNING: No sex specified for subject. Defaulting to "unknown".')

        if 'skeletonPreset' in subjectJson:
            self.skeletonPreset = subjectJson['skeletonPreset']
        else:
            print('WARNING: No skeletonPreset specified for subject. Defaulting to "custom".')

        if 'exportSDF' in subjectJson:
            self.exportSDF = subjectJson['exportSDF']

        if 'exportMJCF' in subjectJson:
            self.exportMJCF = subjectJson['exportMJCF']

        # Only export OpenSim files if we're not exporting MJCF or SDF files, since they use incompatible skeletons.
        self.exportOSIM = not (self.exportMJCF or self.exportSDF)

        if 'ignoreJointLimits' in subjectJson:
            self.ignoreJointLimits = subjectJson['ignoreJointLimits']

        if 'residualsToZero' in subjectJson:
            self.residualsToZero = subjectJson['residualsToZero']

        if 'useReactionWheels' in subjectJson:
            self.useReactionWheels = subjectJson['useReactionWheels']

        if 'tuneResidualLoss' in subjectJson:
            self.tuneResidualLoss = subjectJson['tuneResidualLoss']

        if 'shiftGRF' in subjectJson:
            self.shiftGRF = subjectJson['shiftGRF']

        if 'maxTrialsToSolveMassOver' in subjectJson:
            self.maxTrialsToSolveMassOver = subjectJson['maxTrialsToSolveMassOver']

        if 'regularizeJointAcc' in subjectJson:
            self.regularizeJointAcc = subjectJson['regularizeJointAcc']

        if 'dynamicsMarkerOffsets' in subjectJson:
            self.dynamicsMarkerOffsets = subjectJson['dynamicsMarkerOffsets']

        if 'dynamicsMarkerWeight' in subjectJson:
            self.dynamicsMarkerWeight = subjectJson['dynamicsMarkerWeight']

        if 'dynamicsJointWeight' in subjectJson:
            self.dynamicsJointWeight = subjectJson['dynamicsJointWeight']

        if 'dynamicsRegularizePoses' in subjectJson:
            self.dynamicsRegularizePoses = subjectJson['dynamicsRegularizePoses']

        if 'ignoreFootNotOverForcePlate' in subjectJson:
            self.ignoreFootNotOverForcePlate = subjectJson['ignoreFootNotOverForcePlate']

        if 'disableDynamics' in subjectJson:
            self.disableDynamics = subjectJson['disableDynamics']

        if 'segmentTrials' in subjectJson:
            self.segmentTrials = subjectJson['segmentTrials']

        if 'minSegmentDuration' in subjectJson:
            self.minSegmentDuration = subjectJson['minSegmentDuration']

        if 'mergeZeroForceSegmentsThreshold' in subjectJson:
            self.mergeZeroForceSegmentsThreshold = subjectJson['mergeZeroForceSegmentsThreshold']

        if self.skeletonPreset == 'vicon' or self.skeletonPreset == 'cmu' or self.skeletonPreset == 'complete':
            self.footBodyNames = ['calcn_l', 'calcn_r']
        elif 'footBodyNames' in subjectJson:
            self.footBodyNames = subjectJson['footBodyNames']

    def load_model_files(self):

        # 3. Load the unscaled OSIM file.
        # -------------------------------
        # 3.0. Check for if we're using a preset OpenSim model. Otherwise, use the custom one provided by the user.
        if self.skeletonPreset == 'vicon':
            shutil.copy(DATA_FOLDER_PATH + '/PresetSkeletons/Rajagopal2015_ViconPlugInGait.osim',
                        self.path + 'unscaled_generic.osim')
        elif self.skeletonPreset == 'cmu':
            shutil.copy(DATA_FOLDER_PATH + '/PresetSkeletons/Rajagopal2015_CMUMarkerSet.osim',
                        self.path + 'unscaled_generic.osim')
        elif self.skeletonPreset == 'complete':
            shutil.copy(DATA_FOLDER_PATH + '/PresetSkeletons/CompleteHumanModel.osim',
                        self.path + 'unscaled_generic.osim')
        else:
            if self.skeletonPreset != 'custom':
                print('Unrecognized skeleton preset "' + str(self.skeletonPreset) +
                      '"! Behaving as though this is "custom"')
            if not os.path.exists(self.path + 'unscaled_generic.osim'):
                raise Exception('We are using a custom OpenSim skeleton, but there is no unscaled_generic.osim '
                                'file present. Quitting...')

        # 3.1. Rationalize CustomJoint's in the OSIM file.
        shutil.move(self.path + 'unscaled_generic.osim',
                    self.path + 'unscaled_generic_raw.osim')
        nimble.biomechanics.OpenSimParser.rationalizeJoints(self.path + 'unscaled_generic_raw.osim',
                                                            self.path + 'unscaled_generic.osim')

        # 3.2. Load the rational file.
        self.customOsim: nimble.biomechanics.OpenSimFile = nimble.biomechanics.OpenSimParser.parseOsim(
            self.path + 'unscaled_generic.osim')
        self.customOsim.skeleton.autogroupSymmetricSuffixes()
        if self.customOsim.skeleton.getBodyNode("hand_r") is not None:
            self.customOsim.skeleton.setScaleGroupUniformScaling(
                self.customOsim.skeleton.getBodyNode("hand_r"))
        self.customOsim.skeleton.autogroupSymmetricPrefixes("ulna", "radius")

        self.skeleton = self.customOsim.skeleton
        self.markerSet = self.customOsim.markersMap

        # 3.3. Output both SDF and MJCF versions of the skeleton.
        if self.exportSDF or self.exportMJCF:
            print('Simplifying OpenSim skeleton to prepare for writing other skeleton formats', flush=True)
            mergeBodiesInto: Dict[str, str] = {'ulna_r': 'radius_r', 'ulna_l': 'radius_l'}
            self.customOsim.skeleton.setPositions(
                np.zeros(self.customOsim.skeleton.getNumDofs()))
            self.simplified = self.customOsim.skeleton.simplifySkeleton(
                self.customOsim.skeleton.getName(), mergeBodiesInto)
            self.simplified.setPositions(np.zeros(self.simplified.getNumDofs()))
            self.skeleton = self.simplified

            simplifiedMarkers = {}
            for key in self.markerSet:
                simplifiedMarkers[key] = (self.simplified.getBodyNode(
                    self.markerSet[key][0].getName()), self.markerSet[key][1])
            self.markerSet = simplifiedMarkers

        # 3.4. Load the hand-scaled OSIM file, if it exists.
        self.goldOsim: nimble.biomechanics.OpenSimFile = None
        if os.path.exists(self.path + 'manually_scaled.osim'):
            self.goldOsim = nimble.biomechanics.OpenSimParser.parseOsim(
                self.path + 'manually_scaled.osim')

    def configure_marker_fitter(self):

        # 5. Configure the MarkerFitter object.
        # -------------------------------------
        self.markerFitter = nimble.biomechanics.MarkerFitter(
            self.skeleton, self.markerSet)
        self.markerFitter.setInitialIKSatisfactoryLoss(1e-5)
        self.markerFitter.setInitialIKMaxRestarts(150)
        self.markerFitter.setIterationLimit(500)
        self.markerFitter.setIgnoreJointLimits(self.ignoreJointLimits)

        # 5.1. Set the tracking markers.
        numAnatomicalMarkers = len(self.customOsim.anatomicalMarkers)
        if numAnatomicalMarkers > 10:
            self.markerFitter.setTrackingMarkers(self.customOsim.trackingMarkers)
        else:
            print(f'NOTE: The input *.osim file specified suspiciously few ({numAnatomicalMarkers} less than the '
                  f'minimum 10) anatomical landmark markers (with <fixed>true</fixed>), so we will default '
                  f'to treating all markers as anatomical except triad markers with the suffix "1", "2", or "3"',
                  flush=True)
            self.markerFitter.setTriadsToTracking()
            self.guessedTrackingMarkers = True

        # 5.2. Set default cost function weights.
        self.markerFitter.setRegularizeAnatomicalMarkerOffsets(10.0)
        self.markerFitter.setRegularizeTrackingMarkerOffsets(0.05)
        self.markerFitter.setMinSphereFitScore(0.01)
        self.markerFitter.setMinAxisFitScore(0.001)
        self.markerFitter.setMaxJointWeight(1.0)

    def segment_trials(self):

        # 6. Segment the trials.
        # ----------------------
        # 6.1. Get the static trial, if it exists.
        for trialName in os.listdir(self.trialsFolderPath):
            if trialName == 'static':
                staticMarkers = dict()
                c3dFilePath = os.path.join(self.trialsFolderPath, 'static', 'markers.c3d')
                trcFilePath = os.path.join(self.trialsFolderPath, 'static', 'markers.trc')
                if os.path.exists(c3dFilePath):
                    c3dFile: nimble.biomechanics.C3D = nimble.biomechanics.C3DLoader.loadC3D(
                        c3dFilePath)
                    nimble.biomechanics.C3DLoader.fixupMarkerFlips(c3dFile)
                    self.markerFitter.autorotateC3D(c3dFile)
                    staticMarkers.update(c3dFile.markerTimesteps[0])

                elif os.path.exists(trcFilePath):
                    trcFile: nimble.biomechanics.OpenSimTRC = nimble.biomechanics.OpenSimParser.loadTRC(
                        trcFilePath)
                    staticMarkers.update(trcFile.markerTimesteps[0])

                # 6.1.1. Remove the upper arm markers.
                # TODO include other upper body names
                upperArmBodies = ['humerus', 'radius', 'ulna', 'hand']
                markersToRemove = list()
                for marker in staticMarkers.keys():
                    if marker in self.markerSet:
                        bodyName = self.markerSet[marker][0].getName()
                        for upperArmBody in upperArmBodies:
                            if upperArmBody in bodyName:
                                markersToRemove.append(marker)

                print('Removing upper arm markers from the static pose...')
                for marker in markersToRemove:
                    print(f'  --> {marker}')
                    staticMarkers.pop(marker)

                # 6.1.2. Set the static pose.
                zeroPose = np.zeros(self.skeleton.getNumDofs())
                self.markerFitter.setStaticTrial(staticMarkers, zeroPose)
                self.markerFitter.setStaticTrialWeight(50.0)
            else:
                self.trialNames.append(trialName)

        # 6.2. Process the non-"static" trials in the subject folder
        itrial = 0
        while itrial < len(self.trialNames):
            numSegments = 1
            trialName = self.trialNames[itrial]
            trialPath = self.trialsFolderPath + trialName + '/'
            trialProcessingResult: Dict[str, Any] = {}

            # 6.2.1. Load the markers file.
            c3dFilePath = trialPath + 'markers.c3d'
            trcFilePath = trialPath + 'markers.trc'
            if os.path.exists(c3dFilePath):
                c3dFile: nimble.biomechanics.C3D = nimble.biomechanics.C3DLoader.loadC3D(
                    c3dFilePath)
                nimble.biomechanics.C3DLoader.fixupMarkerFlips(c3dFile)
                self.markerFitter.autorotateC3D(c3dFile)
                self.c3dFiles[trialName] = c3dFile
                self.trialForcePlates.append(c3dFile.forcePlates)
                self.trialTimestamps.append(c3dFile.timestamps)
                self.trialFramesPerSecond.append(c3dFile.framesPerSecond)
                self.trialMarkerSet[trialName] = c3dFile.markers
                self.markerTrials.append(c3dFile.markerTimesteps)
            elif os.path.exists(trcFilePath):
                trcFile: nimble.biomechanics.OpenSimTRC = nimble.biomechanics.OpenSimParser.loadTRC(
                    trcFilePath)
                self.markerTrials.append(trcFile.markerTimesteps)
                self.trialTimestamps.append(trcFile.timestamps)
                self.trialFramesPerSecond.append(trcFile.framesPerSecond)
                self.trialMarkerSet[trialName] = list(trcFile.markerLines.keys())
                grfFilePath = trialPath + 'grf.mot'
                self.ignoreFootNotOverForcePlate = True  # .mot files do not contain force plate geometry
                if os.path.exists(grfFilePath):
                    forcePlates: List[nimble.biomechanics.ForcePlate] = nimble.biomechanics.OpenSimParser.loadGRF(
                        grfFilePath, trcFile.timestamps)
                    self.trialForcePlates.append(forcePlates)
                else:
                    print('Warning: No ground reaction forces specified for ' + trialName)
                    self.trialForcePlates.append([])
            else:
                print('ERROR: No marker files exist for trial ' + trialName + '. Checked both ' +
                      c3dFilePath + ' and ' + trcFilePath + ', neither exist. Quitting.')
                exit(1)

            self.trialProcessingResults.append(trialProcessingResult)

            # 6.2.2. If ground reaction forces were provided, trim the marker and force data to the
            # intersection of the time ranges between the two.
            if len(self.trialForcePlates[itrial]) > 0 and not self.disableDynamics:
                # Find the intersection of the time ranges between the marker and force data.
                if self.trialTimestamps[itrial][0] <= self.trialForcePlates[itrial][0].timestamps[0]:
                    newStartTime = self.trialForcePlates[itrial][0].timestamps[0]
                else:
                    newStartTime = self.trialTimestamps[itrial][0]

                if self.trialTimestamps[itrial][-1] >= self.trialForcePlates[itrial][0].timestamps[-1]:
                    newEndTime = self.trialForcePlates[itrial][0].timestamps[-1]
                else:
                    newEndTime = self.trialTimestamps[itrial][-1]

                # Trim the force data.
                for forcePlate in self.trialForcePlates[itrial]:
                    forcePlate.trim(newStartTime, newEndTime)

                # Trim the marker data.
                numForceTimestamps = len(self.trialForcePlates[itrial][0].timestamps)
                timestamps = np.array(self.trialTimestamps[itrial])
                startTimeIndex = np.argmin(np.abs(timestamps - newStartTime))
                endTimeIndex = startTimeIndex + numForceTimestamps
                self.markerTrials[itrial] = self.markerTrials[itrial][startTimeIndex:endTimeIndex]
                self.trialTimestamps[itrial] = self.trialTimestamps[itrial][startTimeIndex:endTimeIndex]

                # Check that the marker and force data have the same length.
                if len(self.trialTimestamps[itrial]) != len(self.trialForcePlates[itrial][0].timestamps):
                    raise Exception(
                        'ERROR: Marker and force plate data have different lengths after trimming. Quitting...')

            # 6.2.3. Split the trial into individual segments where there is marker data and, if applicable, non-zero
            # forces.
            if self.segmentTrials:
                print(f'Checking trial "{trialName}" for non-zero segments...')

                # Find the markered segments.
                markeredSegments = detect_markered_segments(self.trialTimestamps[itrial], self.markerTrials[itrial])

                # Find the segments of the trial where there are non-zero forces.
                nonzeroForceSegments = [[self.trialTimestamps[itrial][0], self.trialTimestamps[itrial][-1]]]
                if len(self.trialForcePlates[itrial]) > 0 and not self.disableDynamics:
                    totalLoad = np.zeros(len(self.trialForcePlates[itrial][0].timestamps))
                    for itime in range(len(totalLoad)):
                        totalForce = 0
                        totalMoment = 0
                        for forcePlate in self.trialForcePlates[itrial]:
                            totalForce += np.linalg.norm(forcePlate.forces[itime])
                            totalMoment += np.linalg.norm(forcePlate.moments[itime])
                        totalLoad[itime] = totalForce + totalMoment

                    nonzeroForceSegments = detect_nonzero_force_segments(self.trialForcePlates[itrial][0].timestamps,
                                                                         totalLoad)
                    if len(nonzeroForceSegments) == 0:
                        print(f'WARNING: No non-zero force segments detected for trial "{self.trialNames[itrial]}". '
                              f'We must now skip dynamics fitting for all trials...')
                        self.disableDynamics = True
                        self.fitDynamics = False
                        self.skippedDynamicsReason = f'Force plates were provided and trial segmentation was ' \
                                                     f'enabled, but trial "{self.trialNames[itrial]}" had zero ' \
                                                     f'forces at all time points. '
                        nonzeroForceSegments = [[self.trialTimestamps[itrial][0], self.trialTimestamps[itrial][-1]]]

                    nonzeroForceSegments = filter_nonzero_force_segments(nonzeroForceSegments,
                                                                         self.minSegmentDuration,
                                                                         self.mergeZeroForceSegmentsThreshold)
                    if len(nonzeroForceSegments) == 0:
                        print(f'WARNING: No non-zero force segments left in trial "{self.trialNames[itrial]}"q after '
                              f'filtering out segments shorter than {self.minSegmentDuration} seconds. '
                              f'We must now skip dynamics fitting for all trials...')
                        self.disableDynamics = True
                        self.fitDynamics = False
                        self.skippedDynamicsReason = f'Force plates were provided and trial segmentation was ' \
                                                     f'enabled, but trial "{self.trialNames[itrial]}" had no ' \
                                                     f'non-zero force segments longer than {self.minSegmentDuration} ' \
                                                     f'seconds. '
                        nonzeroForceSegments = [[self.trialTimestamps[itrial][0], self.trialTimestamps[itrial][-1]]]

                # Find the intersection of the markered and non-zero force segments.
                segments = reconcile_markered_and_nonzero_force_segments(self.trialTimestamps[itrial],
                                                                         markeredSegments, nonzeroForceSegments)
                numSegments = len(segments)

                # Segment the trial.
                print(f' --> {len(segments)} markered and non-zero force segment(s) found!')
                if len(segments) > 1:
                    print(f' --> Splitting trial "{trialName}" into {len(segments)} separate trials.')
                else:
                    print(f' --> Trimming trial "{trialName}" to markered and non-zero force range.')

                baseTrialName = self.trialNames.pop(itrial)
                baseForcePlates = self.trialForcePlates.pop(itrial)
                baseTimestamps = self.trialTimestamps.pop(itrial)
                baseFramesPerSecond = self.trialFramesPerSecond.pop(itrial)
                baseMarkerSet = self.trialMarkerSet.pop(trialName)
                baseMarkerTrial = self.markerTrials.pop(itrial)
                segmentTrialNames = []
                segmentForcePlates = []
                segmentTimestamps = []
                segmentFramesPerSecond = []
                segmentMarkerTrials = []
                for iseg, segment in enumerate(segments):
                    # Segment time range.
                    if len(segments) > 1:
                        print(f' --> Segment {iseg + 1}: {segment[0]:1.2f} to {segment[1]:1.2f} s')
                        trialSegmentName = f'{baseTrialName}_{iseg + 1}'
                    else:
                        print(f' --> Trimmed time range: {segment[0]:1.2f} to {segment[1]:1.2f} s')
                        trialSegmentName = baseTrialName

                    # Create a new trial name for this segment.
                    segmentTrialNames.append(trialSegmentName)

                    # Create a new set of force plates for this segment.
                    forcePlates = []
                    for forcePlate in baseForcePlates:
                        forcePlateCopy = nimble.biomechanics.ForcePlate.copyForcePlate(forcePlate)
                        forcePlateCopy.trim(segment[0], segment[1])
                        forcePlates.append(forcePlateCopy)
                    segmentForcePlates.append(forcePlates)

                    # Create a new set of timestamps for this segment.
                    timestamps = []
                    for timestamp in baseTimestamps:
                        if segment[0] <= timestamp <= segment[1]:
                            timestamps.append(timestamp)
                    segmentTimestamps.append(timestamps)

                    # Create a new set of frames per second for this segment.
                    segmentFramesPerSecond.append(baseFramesPerSecond)

                    # Create a new marker set for this segment.
                    self.trialMarkerSet[trialSegmentName] = baseMarkerSet

                    # Create a new marker trial for this segment.
                    markerTrial = []
                    for itime, timestamp in enumerate(baseTimestamps):
                        if segment[0] <= timestamp <= segment[1]:
                            markerTrial.append(baseMarkerTrial[itime])
                    segmentMarkerTrials.append(markerTrial)

                # Insert the new segments into the list of trials.
                self.trialNames[itrial:itrial] = segmentTrialNames
                self.trialForcePlates[itrial:itrial] = segmentForcePlates
                self.trialTimestamps[itrial:itrial] = segmentTimestamps
                self.trialFramesPerSecond[itrial:itrial] = segmentFramesPerSecond
                self.markerTrials[itrial:itrial] = segmentMarkerTrials

                # If this trial is from a c3d file, then assign the original c3d file to the segments.
                if os.path.exists(c3dFilePath):
                    baseC3DFile = self.c3dFiles.pop(trialName)
                    for iseg, segment in enumerate(nonzeroForceSegments):
                        if len(nonzeroForceSegments) > 1:
                            self.c3dFiles[f'{baseTrialName}_{iseg + 1}'] = baseC3DFile
                        else:
                            self.c3dFiles[baseTrialName] = baseC3DFile

            # 6.2.4. If we didn't segment anything, numSegments is 1. Otherwise, we need to skip over the new "trials"
            # that are actually just segments of the current trial.
            itrial += numSegments

        # 6.3. Check to see if any ground reaction forces are present in the loaded data. If so, we will attempt to
        # fit dynamics later on in the pipeline. If not, we will skip dynamics fitting.
        if not self.disableDynamics:
            if len(self.trialForcePlates) == 0:
                self.fitDynamics = False
                print('ERROR: No force plate data provided! Dynamics fitting will be skipped...', flush=True)
                self.skippedDynamicsReason = 'No force plate data was provided.'
            else:
                for forcePlateList in self.trialForcePlates:
                    for forcePlate in forcePlateList:
                        self.totalForce += sum([np.linalg.norm(f)
                                                for f in forcePlate.forces])
                self.fitDynamics = self.totalForce > 1e-10
                if not self.fitDynamics:
                    print('ERROR: Force plates had zero force data across all time stemps! '
                          'Dynamics fitting will be skipped...', flush=True)
                    self.skippedDynamicsReason = 'Force plates had zero force data across all time steps.'

            if len(self.footBodyNames) == 0:
                print('ERROR: No foot bodies were specified! Dynamics fitting will be skipped...', flush=True)
                self.fitDynamics = False
                self.skippedDynamicsReason = 'No foot bodies were specified.'

    def run_marker_fitting(self):

        # 7. Run marker fitting.
        # ----------------------
        print('Fitting trials ' + str(self.trialNames), flush=True)

        # 7.1. Clean up the marker data.
        anyHasTooFewMarkers = False
        for i in range(len(self.trialNames)):
            print('Checking and repairing marker data quality on trial ' +
                  str(self.trialNames[i]) + '. This can take a while, depending on trial length...', flush=True)
            trialErrorReport = self.markerFitter.generateDataErrorsReport(
                self.markerTrials[i], 1.0 / self.trialFramesPerSecond[i])
            self.markerTrials[i] = trialErrorReport.markerObservationsAttemptedFixed
            self.trialErrorReports.append(trialErrorReport)
            hasEnoughMarkers = self.markerFitter.checkForEnoughMarkers(self.markerTrials[i])
            self.totalFrames += len(self.markerTrials[i])
            if not hasEnoughMarkers:
                print("There are fewer than 8 markers that show up in the OpenSim model and in trial " +
                      self.trialNames[i], flush=True)
                print("The markers in this trial are: " +
                      str(self.trialMarkerSet[self.trialNames[i]]), flush=True)
                anyHasTooFewMarkers = True
        if anyHasTooFewMarkers:
            print("Some trials don't match the OpenSim model's marker set. Quitting.", flush=True)
            exit(1)
        print('All trial markers have been cleaned up!', flush=True)

        # 7.2. Create an anthropometric prior.
        anthropometrics: nimble.biomechanics.Anthropometrics = nimble.biomechanics.Anthropometrics.loadFromFile(
            DATA_FOLDER_PATH + '/ANSUR_metrics.xml')
        cols = anthropometrics.getMetricNames()
        cols.append('weightkg')
        if self.sex == 'male':
            gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
                DATA_FOLDER_PATH + '/ANSUR_II_MALE_Public.csv',
                cols,
                0.001)  # mm -> m
        elif self.sex == 'female':
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
            'stature': self.heightM,
            'weightkg': self.massKg * 0.01,
        }
        gauss = gauss.condition(observedValues)
        anthropometrics.setDistribution(gauss)
        self.markerFitter.setAnthropometricPrior(anthropometrics, 0.1)
        self.markerFitter.setExplicitHeightPrior(self.heightM, 0.1)
        self.markerFitter.setRegularizePelvisJointsWithVirtualSpring(0.1)

        # 7.3. Run the kinematics pipeline.
        self.markerFitterResults: List[
            nimble.biomechanics.MarkerInitialization] = self.markerFitter.runMultiTrialKinematicsPipeline(
            self.markerTrials,
            nimble.biomechanics.InitialMarkerFitParams()
            .setMaxTrialsToUseForMultiTrialScaling(5)
            .setMaxTimestepsToUseForMultiTrialScaling(4000),
            150)

        # 7.4. Set the masses based on the change in mass of the model.
        unscaledSkeletonMass = self.skeleton.getMass()
        massScaleFactor = self.massKg / unscaledSkeletonMass
        print(f'Unscaled skeleton mass: {unscaledSkeletonMass}')
        print(f'Mass scale factor: {massScaleFactor}')
        self.bodyMasses = dict()
        for ibody in range(self.skeleton.getNumBodyNodes()):
            body = self.skeleton.getBodyNode(ibody)
            body.setMass(body.getMass() * massScaleFactor)
            self.bodyMasses[body.getName()] = body.getMass()

        err_msg = (f'ERROR: expected final skeleton mass to equal {self.massKg} kg after scaling, '
                   f'but the final mass is {self.skeleton.getMass()}')
        np.testing.assert_almost_equal(self.skeleton.getMass(), self.massKg, err_msg=err_msg, decimal=4)

        # 7.5. Check for any flipped markers, now that we've done a first pass
        anySwapped = False
        for i in range(len(self.trialNames)):
            if self.markerFitter.checkForFlippedMarkers(self.markerTrials[i], self.markerFitterResults[i],
                                                        self.trialErrorReports[i]):
                anySwapped = True
                self.markerTrials[i] = self.trialErrorReports[i].markerObservationsAttemptedFixed

        if anySwapped:
            print("******** Unfortunately, it looks like some markers were swapped in the uploaded data, "
                  "so we have to run the whole pipeline again with unswapped markers. ********",
                  flush=True)
            self.markerFitterResults = self.markerFitter.runMultiTrialKinematicsPipeline(
                self.markerTrials,
                nimble.biomechanics.InitialMarkerFitParams()
                .setMaxTrialsToUseForMultiTrialScaling(5)
                .setMaxTimestepsToUseForMultiTrialScaling(4000),
                150)

        self.skeleton.setGroupScales(self.markerFitterResults[0].groupScales)
        self.fitMarkers = self.markerFitterResults[0].updatedMarkerMap

        # 7.6. Set up some interchangeable data structures, so that we can write out the results using the same code,
        # regardless of whether we used dynamics or not
        self.finalSkeleton = self.skeleton
        self.finalPoses = [result.poses for result in self.markerFitterResults]
        self.finalMarkers = self.fitMarkers

    def run_dynamics_fitting(self):

        # 8. Run dynamics fitting.
        # ------------------------
        print('Fitting dynamics...', flush=True)

        # 8.1. Construct a DynamicsFitter object.
        footBodies = []
        for name in self.footBodyNames:
            foot = self.finalSkeleton.getBodyNode(name)
            if foot is None:
                raise Exception(f'ERROR: foot "{str(name)}" not found in skeleton! Dynamics fitter will break as a '
                                f'result.')
            footBodies.append(self.finalSkeleton.getBodyNode(name))

        self.finalSkeleton.setGravity([0, -9.81, 0])
        self.dynamicsFitter = nimble.biomechanics.DynamicsFitter(
            self.finalSkeleton, footBodies, self.customOsim.trackingMarkers)

        # 8.2. Initialize the dynamics fitting problem.
        self.dynamicsInit: nimble.biomechanics.DynamicsInitialization = \
            nimble.biomechanics.DynamicsFitter.createInitialization(
                self.finalSkeleton,
                self.markerFitterResults,
                self.customOsim.trackingMarkers,
                footBodies,
                self.trialForcePlates,
                self.trialFramesPerSecond,
                self.markerTrials)
        self.dynamicsFitter.estimateFootGroundContacts(self.dynamicsInit,
                                                       ignoreFootNotOverForcePlate=self.ignoreFootNotOverForcePlate)
        print("Initial mass: " +
              str(self.finalSkeleton.getMass()) + " kg", flush=True)
        print("What we'd expect average ~GRF to be (Mass * 9.8): " +
              str(self.finalSkeleton.getMass() * 9.8) + " N", flush=True)
        secondPair = self.dynamicsFitter.computeAverageRealForce(self.dynamicsInit)
        print("Avg Force: " + str(secondPair[0]) + " N", flush=True)
        print("Avg Torque: " + str(secondPair[1]) + " Nm", flush=True)

        self.dynamicsFitter.addJointBoundSlack(self.finalSkeleton, 0.1)

        # We don't actually want to do this. This pushes the state away from the initial state
        # if it near bounds, on the theory that this will lead to easier initialization with
        # an interior-point solver (since we won't be pushed so far in early iterations). The
        # cost seems to be greater than the reward, though.
        # dynamicsFitter.boundPush(dynamicsInit)

        self.dynamicsFitter.smoothAccelerations(self.dynamicsInit)
        initializeSuccess = self.dynamicsFitter.timeSyncAndInitializePipeline(
            self.dynamicsInit,
            useReactionWheels=self.useReactionWheels,
            shiftGRF=self.shiftGRF,
            maxShiftGRF=4,
            iterationsPerShift=20,
            maxTrialsToSolveMassOver=self.maxTrialsToSolveMassOver,
            avgPositionChangeThreshold=0.08,
            avgAngularChangeThreshold=0.08,
            reoptimizeTrackingMarkers=True,
            reoptimizeAnatomicalMarkers=self.dynamicsMarkerOffsets
        )

        # 8.3. If initialization succeeded, we will proceed with the bilevel optimization.
        if initializeSuccess:
            goodFramesCount = 0
            totalFramesCount = 0
            for trialMissingGRF in self.dynamicsInit.probablyMissingGRF:
                goodFramesCount += sum(
                    [0 if missing else 1 for missing in trialMissingGRF])
                totalFramesCount += len(trialMissingGRF)
            badFramesCount = totalFramesCount - goodFramesCount
            print('Detected missing/bad GRF data on ' + str(badFramesCount) + '/' + str(
                totalFramesCount) + ' frames',
                  flush=True)
            if goodFramesCount == 0:
                print('ERROR: we have no good frames of GRF data left after filtering out suspicious GRF '
                      'frames. This probably means input GRF data is badly miscalibrated with respect to '
                      'marker data (maybe they are in different coordinate frames?), or there are unmeasured '
                      'external forces acting on your subject. Aborting the physics fitter!', flush=True)
                self.fitDynamics = False
            else:
                # Run an optimization to figure out the model parameters
                self.dynamicsFitter.setIterationLimit(200)
                self.dynamicsFitter.setLBFGSHistoryLength(20)
                self.dynamicsFitter.runIPOPTOptimization(
                    self.dynamicsInit,
                    nimble.biomechanics.DynamicsFitProblemConfig(
                        self.finalSkeleton)
                    .setDefaults(True)
                    .setResidualWeight(1e-2 * self.tuneResidualLoss)
                    .setMaxNumTrials(self.maxTrialsToSolveMassOver)
                    .setConstrainResidualsZero(False)
                    .setIncludeMasses(True)
                    .setMaxNumBlocksPerTrial(20)
                    # .setIncludeInertias(True)
                    # .setIncludeCOMs(True)
                    # .setIncludeBodyScales(True)
                    .setIncludeMarkerOffsets(self.dynamicsMarkerOffsets)
                    .setIncludePoses(True)
                    .setJointWeight(self.dynamicsJointWeight)
                    .setMarkerWeight(self.dynamicsMarkerWeight)
                    .setRegularizePoses(self.dynamicsRegularizePoses)
                    .setRegularizeJointAcc(self.regularizeJointAcc))

                # Now re-run a position-only optimization on every trial in the dataset
                for trial in range(len(self.dynamicsInit.poseTrials)):
                    if len(self.dynamicsInit.probablyMissingGRF[trial]) < 1000:
                        self.dynamicsFitter.setIterationLimit(200)
                        self.dynamicsFitter.setLBFGSHistoryLength(20)
                    elif len(self.dynamicsInit.probablyMissingGRF[trial]) < 5000:
                        self.dynamicsFitter.setIterationLimit(100)
                        self.dynamicsFitter.setLBFGSHistoryLength(15)
                    else:
                        self.dynamicsFitter.setIterationLimit(50)
                        self.dynamicsFitter.setLBFGSHistoryLength(3)
                    self.dynamicsFitter.runIPOPTOptimization(
                        self.dynamicsInit,
                        nimble.biomechanics.DynamicsFitProblemConfig(
                            self.finalSkeleton)
                        .setDefaults(True)
                        .setOnlyOneTrial(trial)
                        .setResidualWeight(1e-2 * self.tuneResidualLoss)
                        .setConstrainResidualsZero(False)
                        .setIncludeMarkerOffsets(self.dynamicsMarkerOffsets)
                        .setIncludePoses(True)
                        .setJointWeight(self.dynamicsJointWeight)
                        .setMarkerWeight(self.dynamicsMarkerWeight)
                        .setRegularizePoses(self.dynamicsRegularizePoses)
                        .setRegularizeJointAcc(self.regularizeJointAcc))

                # Specifically optimize to 0-ish residuals, if user requests it
                if self.residualsToZero:
                    for trial in range(len(self.dynamicsInit.poseTrials)):
                        originalTrajectory = self.dynamicsInit.poseTrials[trial].copy()
                        previousTotalResidual = np.inf
                        for i in range(100):
                            # this holds the mass constant, and re-jigs the trajectory to try to get
                            # the angular ACC's to match more closely what was actually observed
                            pair = self.dynamicsFitter.zeroLinearResidualsAndOptimizeAngular(
                                self.dynamicsInit,
                                trial,
                                originalTrajectory,
                                previousTotalResidual,
                                i,
                                useReactionWheels=self.useReactionWheels,
                                weightLinear=1.0,
                                weightAngular=0.5,
                                regularizeLinearResiduals=0.1,
                                regularizeAngularResiduals=0.1,
                                regularizeCopDriftCompensation=1.0,
                                maxBuckets=150)
                            previousTotalResidual = pair[1]

                        self.dynamicsFitter.recalibrateForcePlates(
                            self.dynamicsInit, trial)

        else:
            print('WARNING: Unable to minimize residual moments below the desired threshold. Skipping '
                  'body mass optimization and final bilevel optimization problem.', flush=True)

        # 8.4. Apply results to skeleton and check physical consistency.
        self.dynamicsFitter.applyInitToSkeleton(self.finalSkeleton, self.dynamicsInit)
        self.dynamicsFitter.computePerfectGRFs(self.dynamicsInit)
        self.dynamicsFitter.checkPhysicalConsistency(
            self.dynamicsInit, maxAcceptableErrors=1e-3, maxTimestepsToTest=25)

        # 8.5. Report the dynamics fitting results.
        print("Avg Marker RMSE: " +
              str(self.dynamicsFitter.computeAverageMarkerRMSE(self.dynamicsInit) * 100) + "cm", flush=True)
        pair = self.dynamicsFitter.computeAverageResidualForce(self.dynamicsInit)
        print(f'Avg Residual Force: {pair[0]} N ({(pair[0] / secondPair[0]) * 100}% of original {secondPair[0]} N)',
              flush=True)
        print(f'Avg Residual Torque: {pair[1]} Nm ({(pair[1] / secondPair[1]) * 100}% of original {secondPair[1]} Nm)',
              flush=True)
        print("Avg CoP movement in 'perfect' GRFs: " +
              str(self.dynamicsFitter.computeAverageCOPChange(self.dynamicsInit)) + " m", flush=True)
        print("Avg force change in 'perfect' GRFs: " +
              str(self.dynamicsFitter.computeAverageForceMagnitudeChange(self.dynamicsInit)) + " N", flush=True)

        # 8.6. Store the dynamics fitting results in the shared data structures.
        for trial in range(len(self.dynamicsInit.poseTrials)):
            self.finalInverseDynamics.append(
                self.dynamicsFitter.computeInverseDynamics(self.dynamicsInit, trial))
            pair = self.dynamicsFitter.computeAverageTrialResidualForce(
                self.dynamicsInit, trial)
            self.trialProcessingResults[trial]['linearResidual'] = pair[0]
            self.trialProcessingResults[trial]['angularResidual'] = pair[1]

            badDynamicsFrames: Dict[str, List[int]] = {}
            numBadDynamicsFrames = 0
            for iframe, reason in enumerate(self.dynamicsInit.missingGRFReason[trial]):
                if reason.name not in badDynamicsFrames:
                    badDynamicsFrames[reason.name] = []
                badDynamicsFrames[reason.name].append(iframe)
                if not reason.name == 'notMissingGRF':
                    numBadDynamicsFrames += 1

            self.trialProcessingResults[trial]['numBadDynamicsFrames'] = numBadDynamicsFrames
            self.trialBadDynamicsFrames.append(badDynamicsFrames)

        self.finalPoses = self.dynamicsInit.poseTrials
        self.finalMarkers = self.dynamicsInit.updatedMarkerMap
        self.trialForcePlates = self.dynamicsInit.forcePlateTrials

    def write_result_files(self):

        # 9. Write out the result files.
        # -----------------------------
        print('Writing the result files...', flush=True)

        # 9.1. Create result directories.
        if not os.path.exists(self.path + 'results'):
            os.mkdir(self.path + 'results')
        if not os.path.exists(self.path + 'results/IK'):
            os.mkdir(self.path + 'results/IK')
        if not os.path.exists(self.path + 'results/ID'):
            os.mkdir(self.path + 'results/ID')
        if not os.path.exists(self.path + 'results/C3D'):
            os.mkdir(self.path + 'results/C3D')
        if not os.path.exists(self.path + 'results/Models'):
            os.mkdir(self.path + 'results/Models')
        if self.exportMJCF and not os.path.exists(self.path + 'results/MuJoCo'):
            os.mkdir(self.path + 'results/MuJoCo')
        if self.exportSDF and not os.path.exists(self.path + 'results/SDF'):
            os.mkdir(self.path + 'results/SDF')
        if not os.path.exists(self.path + 'results/MarkerData'):
            os.mkdir(self.path + 'results/MarkerData')
        shutil.copyfile(self.path + 'unscaled_generic.osim', self.path +
                        'results/Models/unscaled_generic.osim')

        # 9.2. Adjust marker locations.
        print('Adjusting marker locations on scaled OpenSim file', flush=True)
        bodyScalesMap: Dict[str, np.ndarray] = {}
        for i in range(self.finalSkeleton.getNumBodyNodes()):
            bodyNode: nimble.dynamics.BodyNode = self.finalSkeleton.getBodyNode(i)
            # Now that we adjust the markers BEFORE we rescale the body, we don't want to rescale the marker locations
            # at all.
            bodyScalesMap[bodyNode.getName()] = [1, 1, 1]
        markerOffsetsMap: Dict[str, Tuple[str, np.ndarray]] = {}
        markerNames: List[str] = []
        for k in self.finalMarkers:
            v = self.finalMarkers[k]
            markerOffsetsMap[k] = (v[0].getName(), v[1])
            markerNames.append(k)
        nimble.biomechanics.OpenSimParser.moveOsimMarkers(
            self.path + 'unscaled_generic.osim', bodyScalesMap, markerOffsetsMap,
            self.path + 'results/Models/unscaled_but_with_optimized_markers.osim')

        # 9.3. Write the XML instructions for the OpenSim scaling tool
        nimble.biomechanics.OpenSimParser.saveOsimScalingXMLFile(
            'optimized_scale_and_markers',
            self.finalSkeleton,
            self.massKg,
            self.heightM,
            'Models/unscaled_but_with_optimized_markers.osim',
            'Unassigned',
            'Models/optimized_scale_and_markers.osim',
            self.path + 'results/Models/rescaling_setup.xml')

        # 9.4. Call the OpenSim scaling tool
        command = f'cd {self.path}results && opensim-cmd run-tool {self.path}results/Models/rescaling_setup.xml'
        print('Scaling OpenSim files: ' + command, flush=True)
        with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE) as p:
            p.wait()
        # Delete the OpenSim log from running the scale tool
        if os.path.exists(self.path + 'results/opensim.log'):
            os.remove(self.path + 'results/opensim.log')

        # 9.5. Overwrite the inertia properties of the resulting OpenSim skeleton file
        if self.fitDynamics and self.dynamicsInit is not None:
            nimble.biomechanics.OpenSimParser.replaceOsimInertia(
                self.path + 'results/Models/optimized_scale_and_markers.osim',
                self.finalSkeleton,
                self.path + 'results/Models/final.osim')
        else:
            shutil.copyfile(self.path + 'results/Models/optimized_scale_and_markers.osim',
                            self.path + 'results/Models/final.osim')

        # 9.6. Initialize dictionaries for storing the joint limits hits.
        dofNames: List[str] = []
        for i in range(self.finalSkeleton.getNumDofs()):
            dofNames.append(self.finalSkeleton.getDofByIndex(i).getName())
            self.jointLimitsHits[self.finalSkeleton.getDofByIndex(i).getName()] = 0

        # 9.7. If we ran dynamics fitting, write the subject to disk.
        if self.fitDynamics and self.dynamicsInit is not None:
            notes: str = 'Generated by AddBiomechanics'
            outputPath: str = self.path + 'subject.bin'
            if self.output_name is not None:
                outputPath: str = self.path + self.output_name + '.bin'
            self.dynamicsFitter.writeSubjectOnDisk(
                outputPath,
                self.path + 'results/Models/final.osim',
                self.dynamicsInit,
                False,
                self.trialNames,
                self.href,
                notes)

        # 9.8. If requested, export the skeleton to MuJoCo and/or SDF.
        if self.exportSDF or self.exportMJCF:
            print('Deleting OpenSim model outputs, since we cannot export OpenSim models when using a simplified '
                  'skeleton.', flush=True)
            # Get a list of all the file paths that ends with .osim from the Models
            modelList = glob.glob(self.path + 'results/Models/*')
            # Iterate over the list of filepaths and remove each file.
            for filePath in modelList:
                try:
                    os.remove(filePath)
                except RuntimeError:
                    print("Error while deleting Model file: ", filePath)

            if self.exportSDF:
                print('Writing an SDF version of the skeleton', flush=True)
                nimble.utils.SdfParser.writeSkeleton(
                    self.path + 'results/SDF/model.sdf', self.simplified)
            if self.exportMJCF:
                print('Writing a MuJoCo version of the skeleton', flush=True)
                nimble.utils.MJCFExporter.writeSkeleton(
                    self.path + 'results/MuJoCo/model.xml', self.simplified)

        # 9.9. Write the results to disk.
        for i in range(len(self.trialNames)):
            # 9.9.1. Get the data for the current trial.
            poses = self.finalPoses[i]
            forces = self.finalInverseDynamics[i] if i < len(
                self.finalInverseDynamics) else None
            trialName = self.trialNames[i]
            c3dFile = self.c3dFiles[trialName] if trialName in self.c3dFiles else None
            forcePlates = self.trialForcePlates[i]
            framesPerSecond = self.trialFramesPerSecond[i]
            timestamps = self.trialTimestamps[i]
            markerTimesteps = self.markerTrials[i]
            trialProcessingResult = self.trialProcessingResults[i]
            trialPath = self.path + 'trials/' + trialName + '/'

            # 9.9.2. Store the marker errors.
            resultIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
                self.finalSkeleton, self.fitMarkers, poses, markerTimesteps)
            trialProcessingResult['autoAvgRMSE'] = resultIK.averageRootMeanSquaredError
            trialProcessingResult['autoAvgMax'] = resultIK.averageMaxError
            trialProcessingResult['markerErrors'] = resultIK.getSortedMarkerRMSE()

            print('Saving trial ' + str(trialName) + ' results', flush=True)
            print('auto scaled average RMSE m: ' +
                  str(resultIK.averageRootMeanSquaredError), flush=True)
            print('auto scaled average max m: ' +
                  str(resultIK.averageMaxError), flush=True)

            # 9.9.3. Load the gold standard inverse kinematics solution, if it exists.
            goldMot: nimble.biomechanics.OpenSimMot = None
            if os.path.exists(trialPath + 'manual_ik.mot') and self.goldOsim is not None:
                if c3dFile is not None:
                    goldMot = nimble.biomechanics.OpenSimParser.loadMotAtLowestMarkerRMSERotation(
                        self.goldOsim, trialPath + 'manual_ik.mot', c3dFile)
                else:
                    goldMot = nimble.biomechanics.OpenSimParser.loadMot(
                        self.goldOsim.skeleton, trialPath + 'manual_ik.mot')

                shutil.copyfile(trialPath + 'manual_ik.mot', self.path +
                                'results/IK/' + trialName + '_manual_scaling_ik.mot')
                nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                    trialName,
                    markerNames,
                    '../Models/manually_scaled.osim',
                    f'../MarkerData/{trialName}.trc',
                    f'{trialName}_ik_on_manual_scaling_by_opensim.mot',
                    f'{self.path}results/IK/{trialName}_ik_on_manually_scaled_setup.xml')

                originalIK: nimble.biomechanics.IKErrorReport = nimble.biomechanics.IKErrorReport(
                    self.goldOsim.skeleton, self.goldOsim.markersMap, goldMot.poses, markerTimesteps)
                print('manually scaled average RMSE cm: ' +
                      str(originalIK.averageRootMeanSquaredError), flush=True)
                print('manually scaled average max cm: ' +
                      str(originalIK.averageMaxError), flush=True)
                trialProcessingResult['goldAvgRMSE'] = originalIK.averageRootMeanSquaredError
                trialProcessingResult['goldAvgMax'] = originalIK.averageMaxError

            # 9.9.4. Write out the result summary JSON
            print('Writing JSON result to ' + trialPath + '_results.json', flush=True)
            with open(trialPath + '_results.json', 'w') as f:
                json.dump(trialProcessingResult, f)

            # 9.9.5. Write out the result data files.
            # Write out the inverse kinematics results,
            ik_fpath = f'{self.path}/results/IK/{trialName}_ik.mot'
            print(f'Writing OpenSim {ik_fpath} file, shape={str(poses.shape)}', flush=True)
            nimble.biomechanics.OpenSimParser.saveMot(self.finalSkeleton, ik_fpath, timestamps, poses)

            # Write the inverse dynamics results.
            id_fpath = f'{self.path}/results/ID/{trialName}_id.sto'
            if forces is not None:
                nimble.biomechanics.OpenSimParser.saveIDMot(
                    self.finalSkeleton, id_fpath, timestamps, forces)

            # Write out the marker errors.
            marker_errors_fpath = f'{self.path}/results/IK/{trialName}_marker_errors.csv'
            resultIK.saveCSVMarkerErrorReport(marker_errors_fpath)

            # Write out the marker trajectories.
            markers_fpath = f'{self.path}/results/MarkerData/{trialName}.trc'
            nimble.biomechanics.OpenSimParser.saveTRC(
                markers_fpath, timestamps, markerTimesteps)

            # Write out the C3D file.
            c3d_fpath = f'{self.path}/results/C3D/{trialName}.c3d'
            if c3dFile is not None:
                shutil.copyfile(trialPath + 'markers.c3d', c3d_fpath)

            # 9.9.6. Export setup files for OpenSim InverseKinematics.
            if self.exportOSIM:
                # Save OpenSim setup files to make it easy to (re)run IK and ID on the results in OpenSim
                nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                    trialName,
                    markerNames,
                    '../Models/optimized_scale_and_markers.osim',
                    f'../MarkerData/{trialName}.trc',
                    f'{trialName}_ik_by_opensim.mot',
                    f'{self.path}results/IK/{trialName}_ik_setup.xml')

            # 9.9.7. Write out the inverse dynamics files.
            grf_fpath = f'{self.path}/results/ID/{trialName}_grf.mot'
            grf_raw_fpath = f'{self.path}/results/ID/{trialName}_grf_raw.mot'
            if self.fitDynamics and self.dynamicsInit is not None:
                # Run through the list of timesteps, looking for windows of time where we have GRF data.
                # Trim the leading and trailing frames from these windows, because those don't fit by
                # AddBiomechanics finite differencing.
                dynamicsSegments: List[Tuple[int, int]] = []
                lastUnobservedTimestep = -1
                lastWasObserved = False
                for t in range(len(self.dynamicsInit.probablyMissingGRF[i])):
                    if self.dynamicsInit.probablyMissingGRF[i][t]:
                        if lastWasObserved:
                            if lastUnobservedTimestep + 2 < t - 1:
                                dynamicsSegments.append(
                                    (lastUnobservedTimestep + 2, t - 1))
                        lastWasObserved = False
                        lastUnobservedTimestep = t
                    else:
                        lastWasObserved = True
                if lastWasObserved:
                    if lastUnobservedTimestep + 2 < len(self.dynamicsInit.probablyMissingGRF[i]) - 2:
                        dynamicsSegments.append(
                            (lastUnobservedTimestep + 2, len(self.dynamicsInit.probablyMissingGRF[i]) - 2))
                print('Trial ' + trialName + ' detected GRF data present on ranges: ' +
                      str(dynamicsSegments), flush=True)
                self.trialDynamicsSegments.append(dynamicsSegments)

                nimble.biomechanics.OpenSimParser.saveProcessedGRFMot(
                    grf_fpath,
                    timestamps,
                    self.dynamicsInit.grfBodyNodes,
                    self.dynamicsInit.groundHeight[i],
                    self.dynamicsInit.grfTrials[i])
                nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsProcessedForcesXMLFile(
                    trialName,
                    self.dynamicsInit.grfBodyNodes,
                    trialName + '_grf.mot',
                    self.path + 'results/ID/' + trialName + '_external_forces.xml')

                if self.exportOSIM:
                    if len(dynamicsSegments) > 1:
                        for seg in range(len(dynamicsSegments)):
                            begin, end = dynamicsSegments[seg]
                            nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                                trialName,
                                '../Models/final.osim',
                                '../IK/' + trialName + '_ik.mot',
                                trialName + '_external_forces.xml',
                                trialName + '_osim_segment_' + str(seg) + '_id.sto',
                                trialName + '_osim_segment_' + str(seg) + '_id_body_forces.sto',
                                self.path + 'results/ID/' + trialName + '_id_setup_segment_' + str(seg) + '.xml',
                                timestamps[begin], timestamps[end])
                    elif len(dynamicsSegments) == 1:
                        begin, end = dynamicsSegments[0]
                        nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                            trialName,
                            '../Models/final.osim',
                            '../IK/' + trialName + '_ik.mot',
                            trialName + '_external_forces.xml',
                            trialName + '_osim_id.sto',
                            trialName + '_osim_id_body_forces.sto',
                            self.path + 'results/ID/' + trialName + '_id_setup.xml',
                            timestamps[begin], timestamps[end])

                # Still save the raw version.
                nimble.biomechanics.OpenSimParser.saveRawGRFMot(grf_raw_fpath, timestamps, forcePlates)
                nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsRawForcesXMLFile(
                    trialName,
                    self.finalSkeleton,
                    poses,
                    forcePlates,
                    trialName + '_grf_raw.mot',
                    self.path + 'results/ID/' + trialName + '_external_forces_raw.xml')

                if self.exportOSIM:
                    nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                        trialName,
                        '../Models/final.osim',
                        '../IK/' + trialName + '_ik.mot',
                        trialName + '_external_forces_raw.xml',
                        trialName + '_osim_id_raw.sto',
                        trialName + '_id_body_forces_raw.sto',
                        self.path + 'results/ID/' + trialName + '_id_setup_raw.xml',
                        min(timestamps), max(timestamps))
            else:
                nimble.biomechanics.OpenSimParser.saveRawGRFMot(grf_fpath, timestamps, forcePlates)
                nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsRawForcesXMLFile(
                    trialName,
                    self.finalSkeleton,
                    poses,
                    forcePlates,
                    trialName + '_grf.mot',
                    self.path + 'results/ID/' + trialName + '_external_forces.xml')
                if self.exportOSIM:
                    nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                        trialName,
                        '../Models/optimized_scale_and_markers.osim',
                        '../IK/' + trialName + '_ik.mot',
                        trialName + '_external_forces.xml',
                        trialName + '_id.sto',
                        trialName + '_id_body_forces.sto',
                        self.path + 'results/ID/' + trialName + '_id_setup.xml',
                        min(timestamps), max(timestamps))

            # 9.9.8. Write out the animation preview
            if self.fitDynamics and self.dynamicsInit is not None:
                print('Saving trajectory, markers, and dynamics to a GUI log ' +
                      trialPath + 'preview.bin', flush=True)
                print("FPS: " + str(round(1.0 / self.dynamicsInit.trialTimesteps[0])))
                self.dynamicsFitter.saveDynamicsToGUI(
                    trialPath + 'preview.bin',
                    self.dynamicsInit,
                    i,
                    round(1.0 / self.dynamicsInit.trialTimesteps[i]))

                self.dynamicsFitter.writeCSVData(
                    trialPath + 'plot.csv', self.dynamicsInit, i, False, timestamps)
                self.dynamicsFitter.writeCSVData(
                    self.path + f'results/ID/{trialName}_full.csv', self.dynamicsInit, i, False, timestamps)
            else:
                self.markerFitter.writeCSVData(
                    trialPath + 'plot.csv', self.markerFitterResults[i], resultIK.rootMeanSquaredError,
                    resultIK.maxError, timestamps)
                self.markerFitter.writeCSVData(
                    self.path + f'results/IK/{trialName}_full.csv',
                    self.markerFitterResults[i],
                    resultIK.rootMeanSquaredError,
                    resultIK.maxError,
                    timestamps)

                # TODO: someday we'll support loading IMU data. Once available, we'll want to pass it in to the GUI here
                accObservations = []
                gyroObservations = []
                if (self.goldOsim is not None) and (goldMot is not None):
                    print('Saving trajectory, markers, and the manual IK to a GUI log ' +
                          trialPath + 'preview.bin', flush=True)
                    print('goldOsim: ' + str(self.goldOsim), flush=True)
                    print('goldMot.poses.shape: ' +
                          str(goldMot.poses.shape), flush=True)
                    self.markerFitter.saveTrajectoryAndMarkersToGUI(
                        trialPath + 'preview.bin',
                        self.markerFitterResults[i],
                        markerTimesteps,
                        accObservations,
                        gyroObservations,
                        framesPerSecond,
                        forcePlates,
                        self.goldOsim,
                        goldMot.poses)
                else:
                    print('Saving trajectory and markers to a GUI log ' +
                          trialPath + 'preview.bin', flush=True)
                    accObservations: List[Dict[str, np.ndarray[np.float64[3, 1]]]] = []
                    gyroObservations: List[Dict[str, np.ndarray[np.float64[3, 1]]]] = []
                    self.markerFitter.saveTrajectoryAndMarkersToGUI(
                        trialPath + 'preview.bin',
                        self.markerFitterResults[i],
                        markerTimesteps,
                        accObservations,
                        gyroObservations,
                        framesPerSecond,
                        forcePlates)

            # Zip up the animation preview binary.
            print('Zipping up ' + trialPath + 'preview.bin', flush=True)
            subprocess.run(["zip", "-r", 'preview.bin.zip',
                            'preview.bin'], cwd=trialPath, capture_output=True)
            print('Finished zipping up ' + trialPath + 'preview.bin.zip', flush=True)

            # 9.9.9. Count up the number of times we hit against joint limits
            trialJointLimitHits: Dict[str, int] = {}
            jointLimitsFrames: Dict[str, List[int]] = {}
            jointLimitsFramesUpperBound: Dict[str, List[bool]] = {}
            for idof in range(self.finalSkeleton.getNumDofs()):
                dofName = self.finalSkeleton.getDofByIndex(idof).getName()
                trialJointLimitHits[dofName] = 0
                jointLimitsFrames[dofName] = []
                jointLimitsFramesUpperBound[dofName] = []

            tol = 0.001
            for t in range(poses.shape[1]):
                thisTimestepPos = poses[:, t]
                for idof in range(self.finalSkeleton.getNumDofs()):
                    dof = self.finalSkeleton.getDofByIndex(idof)
                    dofPos = thisTimestepPos[idof]
                    # If the joints are at least 2*tol apart
                    if dof.getPositionUpperLimit() > dof.getPositionLowerLimit() + 2 * tol:
                        if dofPos > dof.getPositionUpperLimit() - tol:
                            self.jointLimitsHits[dof.getName()] += 1
                            trialJointLimitHits[dof.getName()] += 1
                            jointLimitsFrames[dof.getName()].append(t)
                            jointLimitsFramesUpperBound[dof.getName()].append(True)
                        if dofPos < dof.getPositionLowerLimit() + tol:
                            self.jointLimitsHits[dof.getName()] += 1
                            trialJointLimitHits[dof.getName()] += 1
                            jointLimitsFrames[dof.getName()].append(t)
                            jointLimitsFramesUpperBound[dof.getName()].append(
                                False)

            # 9.9.10. Sort for trial joint limits
            print('Computing details about joint limit hits for the README')
            try:
                self.trialJointWarnings[trialName] = []
                for dof in sorted(trialJointLimitHits, key=trialJointLimitHits.get, reverse=True):
                    jointHits: List[int] = jointLimitsFrames[dof]
                    jointHitsUpperBound: List[bool] = jointLimitsFramesUpperBound[dof]
                    if len(jointHits) == 0:
                        continue
                    startBlock = jointHits[0]
                    lastBlock = jointHits[0]
                    lastUpperBound = jointHitsUpperBound[0]
                    for ijoint in range(len(jointHits)):
                        frame = jointHits[ijoint]
                        upperBound = jointHitsUpperBound[ijoint]

                        if (frame - lastBlock) <= 1 and lastUpperBound == upperBound:
                            # If this is part of a continuous sequence of frames, we want to compress the message
                            lastBlock = frame
                        else:
                            # We jumped to a new block of frames, so emit the last block
                            if startBlock == lastBlock:  # single frame
                                warning = f'{dof} hit {("upper" if lastUpperBound else "lower")} bound on frame ' \
                                          f'{startBlock}'
                                self.trialJointWarnings[trialName].append(warning)
                            else:
                                warning = f'{dof} hit {("upper" if lastUpperBound else "lower")} bound on frames ' \
                                          f'{startBlock}-{lastBlock}'
                                self.trialJointWarnings[trialName].append(warning)
                            lastBlock = frame
                            startBlock = frame
            except RuntimeError:
                print('Caught an error when computing trial joint limits:')
                traceback.print_exc()
                print('Continuing...')
            print('Finished computing details about joint limit hits for the README.')

            # 9.9.11. Plot results.
            print(f'Plotting results for trial {trialName}')
            plot_ik_results(ik_fpath)
            plot_marker_errors(marker_errors_fpath, ik_fpath)
            if os.path.exists(id_fpath):
                plot_id_results(id_fpath)

            if os.path.exists(grf_fpath):
                plot_grf_data(grf_fpath)

            if os.path.exists(grf_raw_fpath):
                plot_grf_data(grf_raw_fpath)

            print('Success! Done with ' + trialName + '.', flush=True)

        # 9.10. Copy over the manually scaled model file, if it exists.
        if os.path.exists(self.path + 'manually_scaled.osim'):
            shutil.copyfile(self.path + 'manually_scaled.osim', self.path +
                            'results/Models/manually_scaled.osim')

        # 9.11. Copy over the geometry files, so the model can be loaded directly in OpenSim without chasing down
        # Geometry files somewhere else.
        shutil.copytree(DATA_FOLDER_PATH + '/Geometry', self.path +
                        'results/Models/Geometry')

        # 9.12. Copy over the geometry files (in a MuJoCo specific file format), so the model can be loaded directly in
        # MuJoCo without chasing down Geometry files somewhere else.
        if self.exportMJCF:
            shutil.copytree(DATA_FOLDER_PATH + '/MuJoCoGeometry', self.path +
                            'results/MuJoCo/Geometry')

        # 9.13. Copy over the geometry files (in a SDF specific file format), so the model can be loaded directly
        # in PyBullet without chasing down Geometry files somewhere else.
        if self.exportSDF:
            shutil.copytree(DATA_FOLDER_PATH + '/SDFGeometry', self.path +
                            'results/SDF/Geometry')

    def generate_readme(self):

        # 10. Generate the README file.
        # -----------------------------
        print('Generating README file...')

        # 10.1. Fill out the results dictionary.
        autoTotalLen = 0
        goldTotalLen = 0
        self.processingResult['autoAvgRMSE'] = 0
        self.processingResult['autoAvgMax'] = 0
        if self.fitDynamics and self.dynamicsInit is not None:
            self.processingResult['linearResidual'] = 0
            self.processingResult['angularResidual'] = 0
        self.processingResult['goldAvgRMSE'] = 0
        self.processingResult['goldAvgMax'] = 0
        for i in range(len(self.trialNames)):
            trialLen = len(self.markerTrials[i])
            trialProcessingResult = self.trialProcessingResults[i]
            self.processingResult['autoAvgRMSE'] += trialProcessingResult['autoAvgRMSE'] * trialLen
            self.processingResult['autoAvgMax'] += trialProcessingResult['autoAvgMax'] * trialLen
            if self.fitDynamics and self.dynamicsInit is not None:
                self.processingResult['linearResidual'] += trialProcessingResult['linearResidual'] * trialLen
                self.processingResult['angularResidual'] += trialProcessingResult['angularResidual'] * trialLen
            autoTotalLen += trialLen
            if 'goldAvgRMSE' in trialProcessingResult and 'goldAvgMax' in trialProcessingResult:
                self.processingResult['goldAvgRMSE'] += trialProcessingResult['goldAvgRMSE'] * trialLen
                self.processingResult['goldAvgMax'] += trialProcessingResult['goldAvgMax'] * trialLen
                goldTotalLen += trialLen
        self.processingResult['autoAvgRMSE'] /= autoTotalLen
        self.processingResult['autoAvgMax'] /= autoTotalLen
        if self.fitDynamics and self.dynamicsInit is not None:
            self.processingResult['linearResidual'] /= autoTotalLen
            self.processingResult['angularResidual'] /= autoTotalLen
        if goldTotalLen > 0:
            self.processingResult['goldAvgRMSE'] /= goldTotalLen
            self.processingResult['goldAvgMax'] /= goldTotalLen
        self.processingResult['guessedTrackingMarkers'] = self.guessedTrackingMarkers
        self.processingResult['trialMarkerSets'] = self.trialMarkerSet
        self.processingResult['osimMarkers'] = list(self.finalMarkers.keys())
        trialWarnings: Dict[str, List[str]] = {}
        trialInfo: Dict[str, List[str]] = {}
        badMarkerThreshold = 4  # cm
        trialBadMarkers: Dict[str, int] = {}
        for i in range(len(self.trialErrorReports)):
            trialWarnings[self.trialNames[i]] = self.trialErrorReports[i].warnings
            trialInfo[self.trialNames[i]] = self.trialErrorReports[i].info
        self.processingResult['trialWarnings'] = trialWarnings
        self.processingResult['trialInfo'] = trialInfo
        self.processingResult["fewFramesWarning"] = self.totalFrames < 300
        self.processingResult['jointLimitsHits'] = self.jointLimitsHits

        # 10.2. Create the README file for this subject.
        with open(self.path + 'results/README.txt', 'w') as f:
            # 10.2.1. Write out the header and summary results across all trials.
            f.write("*** This data was generated with AddBiomechanics (www.addbiomechanics.org) ***\n")
            f.write("AddBiomechanics was written by Keenon Werling.\n")
            f.write("\n")
            f.write(textwrap.fill(
                "Automatic processing achieved the following marker errors (averaged over all frames of all trials):"))
            f.write("\n\n")
            totalMarkerRMSE = self.processingResult['autoAvgRMSE'] * 100
            totalMarkerMax = self.processingResult['autoAvgMax'] * 100
            f.write(f'- Avg. Marker RMSE      = {totalMarkerRMSE:1.2f} cm\n')
            f.write(f'- Avg. Max Marker Error = {totalMarkerMax:1.2f} cm\n')
            f.write("\n")
            if self.fitDynamics and self.dynamicsInit is not None:
                f.write(textwrap.fill(
                    "Automatic processing reduced the residual loads needed for dynamic consistency to the following "
                    "magnitudes (averaged over all frames of all trials):"))
                f.write("\n\n")
                residualForce = self.processingResult['linearResidual']
                residualTorque = self.processingResult['angularResidual']
                f.write(f'- Avg. Residual Force  = {residualForce:1.2f} N\n')
                f.write(f'- Avg. Residual Torque = {residualTorque:1.2f} N-m\n')
                f.write("\n")
                f.write(textwrap.fill(
                    "Automatic processing found a new model mass to achieve dynamic consistency:"))
                f.write("\n\n")
                finalMass = self.finalSkeleton.getMass()
                percentMassChange = 100 * (finalMass - self.massKg) / self.massKg
                f.write(f'  - Total mass = {finalMass:1.2f} kg '
                        f'({percentMassChange:+1.2f}% change from original {self.massKg} kg)\n')
                f.write("\n")
                f.write(textwrap.fill(
                    "Individual body mass changes:"))
                f.write("\n\n")
                maxBodyNameLen = 0
                for ibody in range(self.skeleton.getNumBodyNodes()):
                    body = self.skeleton.getBodyNode(ibody)
                    bodyName = body.getName()
                    maxBodyNameLen = max(maxBodyNameLen, len(bodyName))
                for ibody in range(self.skeleton.getNumBodyNodes()):
                    body = self.skeleton.getBodyNode(ibody)
                    bodyName = body.getName()
                    bodyMass = body.getMass()
                    bodyMassChange = bodyMass - self.bodyMasses[bodyName]
                    percentMassChange = 100 * bodyMassChange / self.bodyMasses[bodyName]
                    bodyNameLen = len(bodyName)
                    nameLenDiff = maxBodyNameLen - bodyNameLen
                    prefix = f'  - {bodyName}' + ' ' * nameLenDiff
                    f.write(f'{prefix} mass = {bodyMass:1.2f} kg '
                            f'({percentMassChange:+1.2f}% change from original {self.bodyMasses[bodyName]:1.2f} kg)\n')
                f.write("\n")
            elif self.skippedDynamicsReason is not None:
                f.write(textwrap.fill(
                    "WARNING! Dynamics fitting was skipped for the following reason:"))
                f.write("\n\n")
                f.write(textwrap.indent(textwrap.fill(self.skippedDynamicsReason), '  '))
                f.write("\n\n")

            # 10.2.2. Write out the results for each trial.
            if self.fitDynamics and self.dynamicsInit is not None:
                f.write(textwrap.fill(
                    "The following trials were processed to perform automatic body scaling, marker registration, "
                    "and residual reduction:"))
            else:
                f.write(textwrap.fill(
                    "The following trials were processed to perform automatic body scaling and marker registration:"))
            f.write("\n\n")
            for i in range(len(self.trialNames)):
                trialProcessingResult = self.trialProcessingResults[i]
                # Main trial results summary.
                trialName = self.trialNames[i]
                f.write(f'trial: {trialName}\n')

                markerRMSE = trialProcessingResult['autoAvgRMSE'] * 100
                markerMax = trialProcessingResult['autoAvgMax'] * 100
                f.write(f'  - Avg. Marker RMSE      = {markerRMSE:1.2f} cm\n')
                f.write(f'  - Avg. Marker Max Error = {markerMax:.2f} cm\n')

                if self.fitDynamics and self.dynamicsInit is not None:
                    residualForce = trialProcessingResult['linearResidual']
                    residualTorque = trialProcessingResult['angularResidual']
                    f.write(f'  - Avg. Residual Force   = {residualForce:1.2f} N\n')
                    f.write(f'  - Avg. Residual Torque  = {residualTorque:1.2f} N-m\n')

                # Warning and error reporting.
                if len(self.trialJointWarnings[trialName]) > 0:
                    f.write(f'  - WARNING: {len(self.trialJointWarnings[trialName])} joints hit joint limits!\n')

                numBadMarkers = 0
                for markerError in trialProcessingResult['markerErrors']:
                    if 100 * markerError[1] > badMarkerThreshold:
                        numBadMarkers += 1

                trialBadMarkers[trialName] = numBadMarkers
                if numBadMarkers > 0:
                    f.write(f'  - WARNING: {numBadMarkers} marker(s) with RMSE greater than {badMarkerThreshold} cm!\n')

                if len(trialWarnings[trialName]) > 0:
                    f.write(f'  - WARNING: Automatic data processing required modifying TRC data from '
                            f'{len(trialWarnings[trialName])} marker(s)!\n')

                if self.fitDynamics and self.dynamicsInit is not None:
                    numBadFrames = trialProcessingResult['numBadDynamicsFrames']
                    if numBadFrames:
                        f.write(f'  - WARNING: {numBadFrames} frame(s) with ground reaction force inconsistencies '
                                f'detected!\n')

                if self.fitDynamics and self.dynamicsInit is not None:
                    f.write(f'  --> See IK/{trialName}_ik_summary.txt and ID/{trialName}_id_summary.txt for more '
                            f'details.\n')
                else:
                    f.write(f'  --> See IK/{trialName}_ik_summary.txt for more details.\n')
                f.write(f'\n')

            # 10.2.3. Write out the final model information.
            f.write('\n')
            if self.fitDynamics and self.dynamicsInit is not None:
                f.write(textwrap.fill(
                    "The model file containing optimal body scaling, marker offsets, and mass parameters is:"))
            else:
                f.write(textwrap.fill(
                    "The model file containing optimal body scaling and marker offsets is:"))
            f.write("\n\n")
            if self.exportOSIM:
                f.write("Models/final.osim")
                f.write("\n\n")
            if self.exportMJCF:
                f.write("MuJoCo/model.xml")
                f.write("\n\n")
            if self.exportSDF:
                f.write("SDF/model.sdf")
                f.write("\n\n")
            f.write(textwrap.fill(
                "This tool works by finding optimal scale factors and marker offsets at the same time. If specified, "
                "it also runs a second optimization to find mass parameters to fit the model dynamics to the ground "
                "reaction force data."))
            f.write("\n\n")
            if self.fitDynamics and self.dynamicsInit is not None:
                f.write(textwrap.fill(
                    "The model containing the optimal body scaling and marker offsets found prior to the dynamics "
                    "fitting step is:"))
                f.write("\n\n")
                f.write("Models/optimized_scale_and_markers.osim")
            else:
                f.write(textwrap.fill(
                    "Since you did not choose to run the dynamics fitting step, "
                    "Models/optimized_scale_and_markers.osim contains the same model as Models/final.osim."))
            f.write("\n\n")
            if self.exportOSIM:
                f.write(textwrap.fill(
                    "If you want to manually edit the marker offsets, you can modify the <MarkerSet> in "
                    "\"Models/unscaled_but_with_optimized_markers.osim\" (by default this file contains the marker "
                    "offsets found by the optimizer). If you want to tweak the Scaling, you can edit "
                    "\"Models/rescaling_setup.xml\". If you change either of these files, then run "
                    "(FROM THE \"Models\" FOLDER, and not including the leading \"> \"):"))
                f.write("\n\n")
                f.write(" > opensim-cmd run-tool rescaling_setup.xml\n")
                f.write(
                    '           # This will re-generate Models/optimized_scale_and_markers.osim\n')
                f.write("\n\n")
                f.write(textwrap.fill(
                    "You do not need to re-run Inverse Kinematics unless you change scaling, because the output "
                    "motion files are already generated for you as \"*_ik.mot\" files for each trial, but you are "
                    "welcome to confirm our results using OpenSim. To re-run Inverse Kinematics with OpenSim, to "
                    "verify the results of AddBiomechanics, you can use the automatically generated XML configuration "
                    "files. Here are the command-line commands you can run (FROM THE \"IK\" FOLDER, and not including "
                    "the leading \"> \") to verify IK results for each trial:"))
                f.write("\n\n")
                for i in range(len(self.trialNames)):
                    trialName = self.trialNames[i]
                    f.write(" > opensim-cmd run-tool " +
                            trialName + '_ik_setup.xml\n')
                    f.write("           # This will create a results file IK/" +
                            trialName + '_ik_by_opensim.mot\n')
                f.write("\n\n")

                if os.path.exists(self.path + 'manually_scaled.osim'):
                    f.write(textwrap.fill(
                        "You included a manually scaled model to compare against. That model has been copied into "
                        "this folder as \"manually_scaled.osim\". You can use the automatically generated XML "
                        "configuration files to run IK using your manual scaling as well. Here are the command-line "
                        "commands you can run (FROM THE \"IK\" FOLDER, and not including the leading \"> \") to "
                        "compare IK results for each trial:"))
                    f.write("\n\n")
                    for i in range(len(self.trialNames)):
                        trialName = self.trialNames[i]
                        f.write(" > opensim-cmd run-tool " + trialName +
                                '_ik_on_manually_scaled_setup.xml\n')
                        f.write("           # This will create a results file IK/" +
                                trialName + '_ik_on_manual_scaling_by_opensim.mot\n')
                    f.write("\n\n")

                if self.fitDynamics and self.dynamicsInit is not None:
                    f.write(textwrap.fill(
                        "To re-run Inverse Dynamics using OpenSim, you can also use automatically generated XML "
                        "configuration files. WARNING: Inverse Dynamics in OpenSim uses a different time-step "
                        "definition to the one used in AddBiomechanics (AddBiomechanics uses semi-implicit Euler, "
                        "OpenSim uses splines). This means that your OpenSim inverse dynamics results WILL NOT MATCH "
                        "your AddBiomechanics results, and YOU SHOULD NOT EXPECT THEM TO. The following commands "
                        "should work (FROM THE \"ID\" FOLDER, and not including the leading \"> \"):\n"))
                    f.write("\n\n")
                    for i in range(len(self.trialNames)):
                        trialName = self.trialNames[i]
                        timestamps = self.trialTimestamps[i]
                        if len(self.trialDynamicsSegments[i]) > 1:
                            for seg in range(len(self.trialDynamicsSegments[i])):
                                begin, end = self.trialDynamicsSegments[i][seg]
                                f.write(" > opensim-cmd run-tool " +
                                        trialName + '_id_setup_segment_' + str(seg) + '.xml\n')
                                f.write("           # This will create results on time range (" + str(
                                    timestamps[begin]) + "s to " + str(timestamps[end]) + "s) in file ID/" +
                                        trialName + '_osim_segment_' + str(seg) + '_id.sto\n')
                        elif len(self.trialDynamicsSegments[i]) == 1:
                            begin, end = self.trialDynamicsSegments[i][0]
                            f.write(" > opensim-cmd run-tool " +
                                    trialName + '_id_setup.xml\n')
                            f.write("           # This will create results on time range (" + str(
                                timestamps[begin]) + "s to " + str(timestamps[end]) + "s) in file ID/" +
                                    trialName + '_osim_id.sto\n')
                else:
                    f.write(textwrap.fill(
                        "To run Inverse Dynamics with OpenSim, you can also use automatically generated XML "
                        "configuration files. WARNING: This AddBiomechanics run did not attempt to fit dynamics "
                        "(you need to have GRF data and enable physics fitting in the web app), so the residuals will "
                        "not be small and YOU SHOULD NOT EXPECT THEM TO BE. That being said, to run inverse dynamics "
                        "the following commands should work (FROM THE \"ID\" FOLDER, and not including the "
                        "leading \"> \"):\n"))
                    f.write("\n\n")
                    for i in range(len(self.trialNames)):
                        trialName = self.trialNames[i]
                        f.write(" > opensim-cmd run-tool " +
                                trialName + '_id_setup.xml\n')
                        f.write("           # This will create a results file ID/" +
                                trialName + '_id.sto\n')
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
                f.write(textwrap.fill(
                    "Because you chose to export MuJoCo and/or SDF files, we had to simplify the OpenSim skeleton we "
                    "started out with (replacing <CustomJoint> objects with simpler joint types, etc). This means "
                    "that the output is no longer compatible with OpenSim, and so the normal OpenSim files are not "
                    "present. If you want the OpenSim files, please re-run AddBiomechanics with those options "
                    "turned off"))
            f.write("\n\n")
            f.write(textwrap.fill(
                "If you encounter errors, please submit a post to the AddBiomechanics user forum on SimTK.org\n:"))
            f.write('\n\n')
            f.write('   https://simtk.org/projects/addbiomechanics')

        # 10.3. If requested, create the MuJoCo README file.
        if self.exportMJCF:
            with open(self.path + 'results/MuJoCo/README.txt', 'w') as f:
                f.write(
                    "*** This data was generated with AddBiomechanics (www.addbiomechanics.org) ***\n")
                f.write(
                    "AddBiomechanics was written by Keenon Werling <keenon@cs.stanford.edu>\n")
                f.write("\n")
                f.write(textwrap.fill(
                    "Our automatic conversion to MuJoCo is in early beta! Bug reports are welcome at "
                    "keenon@cs.stanford.edu."))
                f.write("\n\n")
                f.write(textwrap.fill(
                    "This folder contains a MuJoCo skeleton (with simplified joints from the original OpenSim), "
                    "and the joint positions over time for the skeleton."))
                f.write("\n\n")
                f.write(textwrap.fill(
                    "The MuJoCo skeleton DOES NOT HAVE ANY COLLIDERS! It will fall straight through the ground. "
                    "It's actually an open research question to approximate realistic foot-ground contact in physics "
                    "engines. Instead of giving you pre-made foot colliders, you'll instead find the "
                    "ground-reaction-force data, with the center-of-pressure, force direction, and torque between the "
                    "feet and the ground throughout the trial in ID/*_grf.mot files. You can use that information in "
                    "combination with the joint positions over time to develop your own foot colliders. Good luck!"))

        # 10.4. If requested, create the SDF README file.
        if self.exportSDF:
            with open(self.path + 'results/SDF/README.txt', 'w') as f:
                f.write(
                    "*** This data was generated with AddBiomechanics (www.addbiomechanics.org) ***\n")
                f.write(
                    "AddBiomechanics was written by Keenon Werling <keenon@cs.stanford.edu>\n")
                f.write("\n")
                f.write(textwrap.fill(
                    "Our automatic conversion to SDF is in early beta! Bug reports are welcome at "
                    "keenon@cs.stanford.edu."))
                f.write("\n\n")
                f.write(textwrap.fill(
                    "This folder contains a SDF skeleton that is compatible with PyBullet (with simplified joints "
                    "from the original OpenSim), and the joint positions over time for the skeleton."))
                f.write("\n\n")
                f.write(textwrap.fill(
                    "The SDF skeleton DOES NOT HAVE ANY COLLIDERS! It will fall straight through the ground. It's "
                    "actually an open research question to approximate realistic foot-ground contact in physics "
                    "engines. Instead of giving you pre-made foot colliders, you'll instead find the "
                    "ground-reaction-force data, with the center-of-pressure, force direction, and torque between the "
                    "feet and the ground throughout the trial in ID/*_grf.mot files. You can use that information in "
                    "combination with the joint positions over time to develop your own foot colliders. Good luck!"))

        # 10.5. Write out summary README files for individual trials.
        for itrial, trialName in enumerate(self.trialNames):
            timestamps = self.trialTimestamps[itrial]
            trialProcessingResult = self.trialProcessingResults[i]
            # 10.5.1. Marker fitting and inverse kinematics results.
            with open(f'{self.path}/results/IK/{trialName}_ik_summary.txt', 'w') as f:
                f.write('-' * len(trialName) + '--------------------------------------\n')
                f.write(f'Trial {trialName}: Inverse Kinematics Summary\n')
                f.write('-' * len(trialName) + '--------------------------------------\n')
                f.write('\n')

                f.write(textwrap.fill(
                    "Automatic processing achieved the following marker errors, averaged over all frames of this "
                    "trial:"))
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
                            f.write(f'  - WARNING: Marker {markerName} has RMSE = {100 * markerRMSE:.2f} cm!\n')

                if len(trialWarnings[trialName]) > 0:
                    f.write('\n')
                    f.write(textwrap.fill(
                        'The input data for the following markers were modified to enable automatic processing:'))
                    f.write('\n\n')
                    for warn in trialWarnings[trialName]:
                        f.write(f'  - WARNING: {warn}.\n')

                if len(self.trialJointWarnings[trialName]):
                    f.write('\n')
                    f.write(textwrap.fill(
                        'The following model coordinates that hit joint limits during inverse kinematics:'))
                    f.write('\n\n')
                    for warn in self.trialJointWarnings[trialName]:
                        f.write(f'  - WARNING: {warn}.\n')

                if len(trialInfo[trialName]) > 0:
                    f.write('\n')
                    f.write(f'Additional information:\n')
                    f.write('\n')
                    for info in trialInfo[trialName]:
                        f.write(f'  - INFO: {info}.\n')

            # 10.5.1. Dynamics fitting and inverse dynamics results.
            if self.fitDynamics and self.dynamicsInit is not None:
                badDynamicsFrames = self.trialBadDynamicsFrames[itrial]
                with open(f'{self.path}/results/ID/{trialName}_id_summary.txt', 'w') as f:
                    f.write('-' * len(trialName) + '--------------------------------\n')
                    f.write(f'Trial {trialName}: Inverse Dynamics Summary\n')
                    f.write('-' * len(trialName) + '--------------------------------\n')
                    f.write('\n')

                    f.write(textwrap.fill(
                        "Automatic processing reduced the residual loads needed for dynamic consistency to the "
                        "following magnitudes, averaged over all frames of this trial:"))
                    f.write('\n\n')
                    residualForce = trialProcessingResult['linearResidual']
                    residualTorque = trialProcessingResult['angularResidual']
                    f.write(f'  - Avg. Residual Force   = {residualForce:1.2f} N\n')
                    f.write(f'  - Avg. Residual Torque  = {residualTorque:1.2f} N-m\n')
                    f.write('\n\n')

                    numTotalFrames = len(self.dynamicsInit.missingGRFReason[itrial])
                    numBadFrames = trialProcessingResult['numBadDynamicsFrames']
                    if numBadFrames:
                        f.write('Ground reaction force inconsistencies\n')
                        f.write('=====================================\n')
                        f.write(
                            textwrap.fill(f'Ground reaction force inconsistencies were detected in {numBadFrames} out '
                                          f'of {numTotalFrames} frames in this trial. See below for a breakdown of why '
                                          f'these "bad" frames were detected.'))
                        f.write('\n')

                        reasonNumber = 1
                        if 'measuredGrfZeroWhenAccelerationNonZero' in badDynamicsFrames:
                            f.write('\n')
                            f.write(f'{reasonNumber}. "Zero GRF, but non-zero acceleration."\n')
                            f.write(f'   --------------------------------------\n')
                            f.write(textwrap.indent(textwrap.fill(
                                'No external ground reaction forces was present, but a non-zero whole-body '
                                'acceleration was detected in the following frames:'), '   '))
                            f.write('\n')
                            frameRanges = get_consecutive_values(
                                badDynamicsFrames['measuredGrfZeroWhenAccelerationNonZero'])
                            for frames in frameRanges:
                                if frames[0] is frames[-1]:
                                    f.write(f'     - frame {frames[0]} (time = {timestamps[frames[0]]:.3f} s)\n')
                                else:
                                    f.write(f'     - frames {frames[0]}-{frames[-1]} '
                                            f'(times = {timestamps[frames[0]]:.3f}-{timestamps[frames[-1]]:.3f} s)\n')
                            reasonNumber += 1

                        if 'unmeasuredExternalForceDetected' in badDynamicsFrames:
                            f.write('\n')
                            f.write(f'{reasonNumber}. "Zero acceleration, but non-zero GRF."\n')
                            f.write(f'   --------------------------------------\n')
                            f.write(textwrap.indent(textwrap.fill(
                                'External ground reaction forces were present, but the whole-body acceleration was '
                                'zero in the following frames:'), '   '))
                            f.write('\n')
                            frameRanges = get_consecutive_values(badDynamicsFrames['unmeasuredExternalForceDetected'])
                            for frames in frameRanges:
                                if frames[0] is frames[-1]:
                                    f.write(f'     - frame {frames[0]} (time = {timestamps[frames[0]]:.3f} s)\n')
                                else:
                                    f.write(f'     - frames {frames[0]}-{frames[-1]} '
                                            f'(times = {timestamps[frames[0]]:.3f}-{timestamps[frames[-1]]:.3f} s)\n')
                            reasonNumber += 1

                        if 'forceDiscrepancy' in badDynamicsFrames:
                            f.write('\n')
                            f.write(f'{reasonNumber}. "Foot not over a force plate."\n')
                            f.write(f'   ------------------------------\n')
                            f.write(textwrap.indent(textwrap.fill(
                                'After optimizing the center-of-mass kinematics to match the observed ground reaction '
                                'data, an unmeasured external force was still detected in the following frames:'),
                                '   '))
                            f.write('\n')
                            frameRanges = get_consecutive_values(badDynamicsFrames['forceDiscrepancy'])
                            for frames in frameRanges:
                                if frames[0] is frames[-1]:
                                    f.write(f'     - frame {frames[0]} (time = {timestamps[frames[0]]:.3f} s)\n')
                                else:
                                    f.write(f'     - frames {frames[0]}-{frames[-1]} '
                                            f'(times = {timestamps[frames[0]]:.3f}-{timestamps[frames[-1]]:.3f} s)\n')
                            reasonNumber += 1

                        if 'torqueDiscrepancy' in badDynamicsFrames:
                            f.write('\n')
                            f.write(f'{reasonNumber}. "Unmeasured external torque."\n')
                            f.write(f'   -----------------------------\n')
                            f.write(textwrap.indent(textwrap.fill(
                                'After optimizing the center-of-mass kinematics to match the observed ground reaction '
                                'data, an unmeasured external torque was still detected in the following frames:'),
                                '   '))
                            f.write('\n')
                            frameRanges = get_consecutive_values(badDynamicsFrames['torqueDiscrepancy'])
                            for frames in frameRanges:
                                if frames[0] is frames[-1]:
                                    f.write(f'     - frame {frames[0]} (time = {timestamps[frames[0]]:.3f} s)\n')
                                else:
                                    f.write(f'     - frames {frames[0]}-{frames[-1]} '
                                            f'(times = {timestamps[frames[0]]:.3f}-{timestamps[frames[-1]]:.3f} s)\n')
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
                            frameRanges = get_consecutive_values(badDynamicsFrames['notOverForcePlate'])
                            for frames in frameRanges:
                                if frames[0] is frames[-1]:
                                    f.write(f'     - frame {frames[0]} (time = {timestamps[frames[0]]:.3f} s)\n')
                                else:
                                    f.write(f'     - frames {frames[0]}-{frames[-1]} '
                                            f'(times = {timestamps[frames[0]]:.3f}-{timestamps[frames[-1]]:.3f} s)\n')
                            reasonNumber += 1

                        if 'missingImpact' in badDynamicsFrames:
                            f.write('\n')
                            f.write(f'{reasonNumber}. "Missing foot-ground impact detected."\n')
                            f.write(f'   --------------------------------------\n')
                            f.write(textwrap.indent(textwrap.fill(
                                'EXPERIMENTAL: The following frames had ground reaction force data removed using an '
                                'impact detection algorithm in nimblephysics. If you receive this message, then we '
                                'assume that you know what you are doing.'), '   '))
                            f.write('\n')
                            frameRanges = get_consecutive_values(badDynamicsFrames['missingImpact'])
                            for frames in frameRanges:
                                if frames[0] is frames[-1]:
                                    f.write(f'     - frame {frames[0]} (time = {timestamps[frames[0]]:.3f} s)\n')
                                else:
                                    f.write(f'     - frames {frames[0]}-{frames[-1]} '
                                            f'(times = {timestamps[frames[0]]:.3f}-{timestamps[frames[-1]]:.3f} s)\n')
                            reasonNumber += 1

                        if 'missingBlip' in badDynamicsFrames:
                            f.write('\n')
                            f.write(f'{reasonNumber}. "Missing ground reaction force \'blip\' detected."\n')
                            f.write(f'   ------------------------------------------------\n')
                            f.write(textwrap.indent(textwrap.fill(
                                'Ground reaction forces were detected the following frames were preceded and followed '
                                'by several frames of zero force data. Therefore, these \'blips\' in the data were '
                                'removed:'), '   '))
                            f.write('\n')
                            frameRanges = get_consecutive_values(badDynamicsFrames['missingBlip'])
                            for frames in frameRanges:
                                if frames[0] is frames[-1]:
                                    f.write(f'     - frame {frames[0]} (time = {timestamps[frames[0]]:.3f} s)\n')
                                else:
                                    f.write(f'     - frames {frames[0]}-{frames[-1]} '
                                            f'(times = {timestamps[frames[0]]:.3f}-{timestamps[frames[-1]]:.3f} s)\n')
                            reasonNumber += 1

                        if 'shiftGRF' in badDynamicsFrames:
                            f.write('\n')
                            f.write(f'{reasonNumber}. "Shifted ground reaction force data."\n')
                            f.write(f'   -------------------------------------\n')
                            f.write(textwrap.indent(textwrap.fill(
                                'The following frames were marked as having missing ground reaction force data due to '
                                'shifting the force data to better match marker data. If you receive this message, '
                                'then an error has occurred. '), '   '))
                            f.write('\n')
                            frameRanges = get_consecutive_values(badDynamicsFrames['shiftGRF'])
                            for frames in frameRanges:
                                if frames[0] is frames[-1]:
                                    f.write(f'     - frame {frames[0]} (time = {timestamps[frames[0]]:.3f} s)\n')
                                else:
                                    f.write(f'     - frames {frames[0]}-{frames[-1]} '
                                            f'(times = {timestamps[frames[0]]:.3f}-{timestamps[frames[-1]]:.3f} s)\n')
                            reasonNumber += 1

    def create_output_folder(self):

        # 11. Create the output folder.
        # -----------------------------

        # 11.1. Move the results to the output folder.
        shutil.move(self.path + 'results', self.path + self.output_name)
        print('Zipping up OpenSim files...', flush=True)
        shutil.make_archive(self.path + self.output_name, 'zip', self.path, self.output_name)
        print('Finished outputting OpenSim files.', flush=True)

        # 11.2. Write out the result summary JSON file.
        print('Writing the _results.json file...', flush=True)
        try:
            with open(self.path + '_results.json', 'w') as f:
                json.dump(self.processingResult, f)
        except Exception as e:
            print('Had an error writing _results.json:', flush=True)
            print(e, flush=True)

        # 11.3. Generate final zip file.
        print('Generated a final zip file at ' + self.path + self.output_name + '.zip.')
        print('Done!', flush=True)


def main():
    # Process input arguments.
    # ------------------------
    print(sys.argv, flush=True)
    if len(sys.argv) < 2:
        print('ERROR: Must provide a path to a subject folder. Exiting...')
        exit(1)

    # Subject folder path.
    path = sys.argv[1]
    if not path.endswith('/'):
        path += '/'

    # Output name.
    output_name = sys.argv[2] if len(sys.argv) > 2 else 'osim_results'

    # Subject href.
    href = sys.argv[3] if len(sys.argv) > 3 else ''

    # Construct the engine.
    # ---------------------
    engine = Engine(path=path,
                    output_name=output_name,
                    href=href)

    # Run the pipeline.
    # -----------------
    engine.validate_paths()
    engine.parse_subject_json()
    engine.load_model_files()
    engine.configure_marker_fitter()
    engine.segment_trials()
    engine.run_marker_fitting()
    if engine.fitDynamics:
        engine.run_dynamics_fitting()
    engine.write_result_files()
    engine.generate_readme()
    engine.create_output_folder()


if __name__ == "__main__":
    main()
