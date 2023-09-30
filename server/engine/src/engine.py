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
                    reconcile_markered_and_nonzero_force_segments, \
                    fill_moco_template, run_moco_problem
from exceptions import Error, PathError, SubjectConfigurationError, ModelFileError, TrialPreprocessingError, \
                       MarkerFitterError, DynamicsFitterError, MocoError, WriteError
from subject import Subject

# Global paths to the geometry and data folders.
GEOMETRY_FOLDER_PATH = absPath('Geometry')
DATA_FOLDER_PATH = absPath('../../data')
TEMPLATES_PATH = absPath('templates')


# This metaclass wraps all methods in the Engine class with a try-except block, except for the __init__ method.
class ExceptionHandlingMeta(type):
    def __new__(cls, name, bases, attrs):
        for attr_name, attr_value in attrs.items():
            if attr_name == '__init__':
                continue  # Skip __init__ method
            if callable(attr_value):
                attrs[attr_name] = cls.wrap_method(attr_value)
        return super().__new__(cls, name, bases, attrs)

    @staticmethod
    def wrap_method(method):
        def wrapper(*args, **kwargs):
            try:
                method(*args, **kwargs)
            except Exception as e:
                msg = f"Exception caught in {method.__name__}: {e}"
                if method.__name__ == 'validate_paths':
                    raise PathError(msg)
                elif method.__name__ == 'parse_subject_json':
                    raise SubjectConfigurationError(msg)
                elif method.__name__ == 'load_model_files':
                    raise ModelFileError(msg)
                elif method.__name__ == 'configure_marker_fitter':
                    raise MarkerFitterError(msg)
                elif method.__name__ == 'preprocess_trials':
                    raise TrialPreprocessingError(msg)
                elif method.__name__ == 'run_marker_fitting':
                    raise MarkerFitterError(msg)
                elif method.__name__ == 'run_dynamics_fitting':
                    raise DynamicsFitterError(msg)
                elif method.__name__ == 'write_result_files':
                    raise WriteError(msg)
                elif method.__name__ == 'run_moco':
                    raise MocoError(msg)
                elif method.__name__ == 'generate_readme':
                    raise WriteError(msg)
                elif method.__name__ == 'create_output_folder':
                    raise WriteError(msg)

        return wrapper


class Engine(metaclass=ExceptionHandlingMeta):
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
        self.errors_json_path = self.path + '_errors.json'
        self.geometry_symlink_path = self.path + 'Geometry'
        self.output_name = output_name
        self.href = href
        self.processingResult: Dict[str, Any] = {}

        # 0.2. Subject pipeline parameters.
        self.massKg = 68.0
        self.heightM = 1.6
        self.sex = 'unknown'
        self.ageYears = -1
        self.subjectTags = []
        # TODO: load trial tags from trial.json files
        self.trialTags = []
        self.skeletonPreset = 'vicon'
        self.exportSDF = False
        self.exportMJCF = False
        self.exportOSIM = True
        self.exportMoco = False
        self.ignoreJointLimits = False
        self.residualsToZero = False
        self.useReactionWheels = True
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
        self.segmentedTrials = []
        self.trialRanges = dict()
        self.minSegmentDuration = 0.05
        self.mergeZeroForceSegmentsThreshold = 1.0
        self.footBodyNames = ['calcn_l', 'calcn_r']
        self.totalForce = 0.0
        self.fitDynamics = False
        self.skippedDynamicsReason = None
        self.runMoco = False
        self.skippedMocoReason = None

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
            raise IsADirectoryError('Geometry folder "' + GEOMETRY_FOLDER_PATH + '" does not exist.')

        # 1.2. Symlink in Geometry, if it doesn't come with the folder, so we can load meshes for the visualizer.
        if not os.path.exists(self.geometry_symlink_path):
            os.symlink(GEOMETRY_FOLDER_PATH, self.geometry_symlink_path)

        # 1.3. Get the subject JSON file path.
        if not os.path.exists(self.subject_json_path):
            raise FileNotFoundError('Subject JSON file "' + self.subject_json_path + '" does not exist.')

        # 1.4. Check that the trials folder exists.
        if not os.path.exists(self.trialsFolderPath):
            raise IsADirectoryError('Trials folder "' + self.trialsFolderPath + '" does not exist.')

    def parse_subject_json(self):

        # 2. Read the subject parameters from the JSON file.
        # --------------------------------------------------
        with open(self.subject_json_path) as subj:
            subjectJson = json.loads(subj.read())

        if 'massKg' in subjectJson:
            self.massKg = float(subjectJson['massKg'])

        if 'heightM' in subjectJson:
            self.heightM = float(subjectJson['heightM'])

        if 'ageYears' in subjectJson:
            self.ageYears = float(subjectJson['ageYears'])

        if 'subjectTags' in subjectJson:
            self.subjectTags = subjectJson['subjectTags']

        if 'sex' in subjectJson:
            self.sex = subjectJson['sex']

        if 'skeletonPreset' in subjectJson:
            self.skeletonPreset = subjectJson['skeletonPreset']

        if 'exportSDF' in subjectJson:
            self.exportSDF = subjectJson['exportSDF']

        if 'exportMJCF' in subjectJson:
            self.exportMJCF = subjectJson['exportMJCF']

        # Only export OpenSim files if we're not exporting MJCF or SDF files, since they use incompatible skeletons.
        self.exportOSIM = not (self.exportMJCF or self.exportSDF)

        if 'exportMoco' in subjectJson:
            self.exportMoco = subjectJson['exportMoco']

        if 'runMoco' in subjectJson:
            self.runMoco = subjectJson['runMoco']
            self.exportMoco = True if self.runMoco else self.exportMoco

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

        if 'segmentedTrials' in subjectJson:
            self.segmentedTrials = subjectJson['segmentedTrials']

        if 'minSegmentDuration' in subjectJson:
            self.minSegmentDuration = subjectJson['minSegmentDuration']

        if 'mergeZeroForceSegmentsThreshold' in subjectJson:
            self.mergeZeroForceSegmentsThreshold = subjectJson['mergeZeroForceSegmentsThreshold']

        if self.skeletonPreset == 'vicon' or self.skeletonPreset == 'cmu' or self.skeletonPreset == 'complete':
            self.footBodyNames = ['calcn_l', 'calcn_r']
        elif 'footBodyNames' in subjectJson:
            self.footBodyNames = subjectJson['footBodyNames']

        if 'trialRanges' in subjectJson:
            self.trialRanges = subjectJson['trialRanges']

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
                raise FileNotFoundError('We are using a custom OpenSim skeleton, but there is no unscaled_generic.osim '
                                        'file present.')

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

    def preprocess_trials(self):

        # 6. Preprocess the trials.
        # -------------------------
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

                any_have_markers = False
                for markerTimestep in c3dFile.markerTimesteps:
                    if len(markerTimestep.keys()) > 0:
                        any_have_markers = True
                        break
                if not any_have_markers:
                    raise RuntimeError(f'Trial {trialName} has no markers on any timestep. Check that the C3D file is '
                                       f'not corrupted.')

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

                any_have_markers = False
                for markerTimestep in trcFile.markerTimesteps:
                    if len(markerTimestep.keys()) > 0:
                        any_have_markers = True
                        break
                if not any_have_markers:
                    raise RuntimeError(f'Trial {trialName} has no markers on any timestep. Check that the TRC file is '
                                       f'not corrupted.')

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
                raise RuntimeError(f'No marker files exist for trial {trialName}. '
                                   f'Checked both {c3dFilePath} and {trcFilePath}, but neither exist.')

            self.trialProcessingResults.append(trialProcessingResult)

            # 6.2.2. If ground reaction forces were provided, trim the marker and force data to the
            # intersection of the time ranges between the two.
            if len(self.trialForcePlates[itrial]) > 0 and not self.disableDynamics:
                dataTrimmed = False
                # Find the intersection of the time ranges between the marker and force data.
                if self.trialTimestamps[itrial][0] <= self.trialForcePlates[itrial][0].timestamps[0]:
                    newStartTime = self.trialForcePlates[itrial][0].timestamps[0]
                    dataTrimmed = True
                else:
                    newStartTime = self.trialTimestamps[itrial][0]

                if self.trialTimestamps[itrial][-1] >= self.trialForcePlates[itrial][0].timestamps[-1]:
                    newEndTime = self.trialForcePlates[itrial][0].timestamps[-1]
                    dataTrimmed = True
                else:
                    newEndTime = self.trialTimestamps[itrial][-1]

                if dataTrimmed:
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
                        raise RuntimeError('Marker and force plate data have different lengths after trimming.')

                    # Save warning if we had to trim the data.
                    self.trialProcessingResults[itrial]['dataIntersectionTrimWarning'] = f'Trial {trialName} ' \
                        f'was trimmed to the intersection of the marker and force plate data, ' \
                        f'([{newStartTime}, {newEndTime}]), since the time ranges in the uploaded files did not match.'

            # 6.2.3. If specified by the user, trim the trial to the specified start and end times.
            trialAlreadyTrimmed = False
            if trialName in self.trialRanges:
                trialAlreadyTrimmed = True
                trialStart = self.trialRanges[trialName][0]
                trialEnd = self.trialRanges[trialName][1]
                timestamps = np.array(self.trialTimestamps[itrial])

                # Check that the trial start and end times are within the range of the trial.
                if trialStart < timestamps[0]:
                    raise RuntimeError(f'The new trial start time specified ({trialStart} s) is before the start of '
                                       f'the trial.')
                if trialEnd > timestamps[-1]:
                    raise RuntimeError(f'The new trial end time specified ({trialEnd} s) is after the end of the '
                                       f'trial.')

                # Trim the force data.
                print(f'Trimming trial {trialName} to [{trialStart}, {trialEnd}] s...')
                for forcePlate in self.trialForcePlates[itrial]:
                    forcePlate.trim(trialStart, trialEnd)

                # Trim the marker data.
                numForceTimestamps = len(self.trialForcePlates[itrial][0].timestamps)
                startTimeIndex = np.argmin(np.abs(timestamps - trialStart))
                endTimeIndex = startTimeIndex + numForceTimestamps
                self.markerTrials[itrial] = self.markerTrials[itrial][startTimeIndex:endTimeIndex]
                self.trialTimestamps[itrial] = self.trialTimestamps[itrial][startTimeIndex:endTimeIndex]

                # Check that the marker and force data have the same length.
                if len(self.trialTimestamps[itrial]) != len(self.trialForcePlates[itrial][0].timestamps):
                    raise RuntimeError('Marker and force plate data have different lengths after trimming.')

            # 6.2.4. Split the trial into individual segments where there is marker data and, if applicable, non-zero
            # forces.
            if not trialAlreadyTrimmed:
                print(f'Checking trial "{trialName}" for non-zero segments...')

                # Find the markered segments.
                markeredSegments = detect_markered_segments(self.trialTimestamps[itrial], self.markerTrials[itrial])
                if len(markeredSegments) == 0:
                    raise RuntimeError(f'No markered segments were found in trial {trialName}. ')

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
                        nonzeroForceSegments = [[self.trialTimestamps[itrial][0], self.trialTimestamps[itrial][-1]]]
                        if trialName in self.segmentedTrials:
                            print(f'WARNING: No non-zero force segments detected for trial '
                                  f'"{self.trialNames[itrial]}". We must now skip dynamics fitting for all trials...')
                            self.disableDynamics = True
                            self.fitDynamics = False
                            self.skippedDynamicsReason = f'Force plates were provided and trial segmentation was ' \
                                                         f'enabled, but trial "{self.trialNames[itrial]}" had zero ' \
                                                         f'forces at all time points. '

                    nonzeroForceSegments = filter_nonzero_force_segments(nonzeroForceSegments,
                                                                         self.minSegmentDuration,
                                                                         self.mergeZeroForceSegmentsThreshold)
                    if len(nonzeroForceSegments) == 0:
                        nonzeroForceSegments = [[self.trialTimestamps[itrial][0], self.trialTimestamps[itrial][-1]]]
                        if trialName in self.segmentedTrials:
                            print(f'WARNING: No non-zero force segments left in trial "{self.trialNames[itrial]}" ' 
                                  f'after filtering out segments shorter than {self.minSegmentDuration} seconds. '
                                  f'We must now skip dynamics fitting for all trials...')
                            self.disableDynamics = True
                            self.fitDynamics = False
                            self.skippedDynamicsReason = f'Force plates were provided and trial segmentation was ' \
                                                         f'enabled, but trial "{self.trialNames[itrial]}" had no ' \
                                                         f'non-zero force segments longer than ' \
                                                         f'{self.minSegmentDuration} seconds.'

                # Find the intersection of the markered and non-zero force segments.
                segments = reconcile_markered_and_nonzero_force_segments(self.trialTimestamps[itrial],
                                                                         markeredSegments, nonzeroForceSegments)
                numSegments = len(segments)

                # Segment the trial.
                if trialName in self.segmentedTrials:
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
                    baseTrialProcessingResults = self.trialProcessingResults.pop(itrial)
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

                        # Append the trial processing results for this segment.
                        self.trialProcessingResults.append(baseTrialProcessingResults)

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
                else:
                    # If the user did not select trial segmentation, but the segment(s) we detected are not equal to the
                    # original full time range, then issue a warning recommending that the user enable trial
                    # segmentation.
                    if not segments == [[self.trialTimestamps[itrial][0], self.trialTimestamps[itrial][-1]]]:
                        if len(segments) > 1:
                            self.trialProcessingResults[itrial]['dataSegmentationWarning'] = \
                                f'Trial segmentation was not enabled, but {len(segments)} markered and non-zero ' \
                                f'time segments were found in trial "{trialName}". We recommend enabling trial ' \
                                f'segmentation to split this trial into {len(segments)} separate trials.'
                        else:
                            self.trialProcessingResults[itrial]['dataSegmentationWarning'] = \
                                f'Trial segmentation was not enabled, but the time range of trial "{trialName}" ' \
                                f'where markers are present and force was non-zero is not equal to the full time ' \
                                f'range of the trial. We recommend enabling trial segmentation, which will trim this ' \
                                f'trial to the time range [{segments[0][0]}, {segments[0][1]}].'

            # 6.2.4. If we didn't segment anything, numSegments is 1. Otherwise, we need to skip over the new "trials"
            # that are actually just segments of the current trial.
            itrial += numSegments

        # 6.3. Save the time ranges for each trial.
        timeRanges = dict()
        for itrial, trialName in enumerate(self.trialNames):
            timestamps = self.trialTimestamps[itrial]
            self.trialProcessingResults[itrial]['timeRange'] = [timestamps[0], timestamps[-1]]
            timeRanges[trialName] = [timestamps[0], timestamps[-1]]
        self.processingResult['timeRanges'] = timeRanges

        # 6.4. Check to see if any ground reaction forces are present in the loaded data. If so, we will attempt to
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

        if self.runMoco:
            if not self.fitDynamics:
                print('ERROR: Moco requires dynamics fitting! Running Moco will be skipped...', flush=True)
                self.runMoco = False
                self.skippedMocoReason = 'Dynamics fitting was not performed.'

    def run_marker_fitting(self):

        # 7. Run marker fitting.
        # ----------------------
        print('Fitting trials ' + str(self.trialNames), flush=True)

        # 7.1. Clean up the marker data.
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
                msg = f'There are fewer than 8 markers that show up in the OpenSim model and in trial ' \
                      f'{self.trialNames[i]}. The markers in this trial are: ' \
                      f'{str(self.trialMarkerSet[self.trialNames[i]])}'
                raise RuntimeError(msg)

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
                raise RuntimeError(f'Foot "{str(name)}" not found in skeleton! Cannot run dynamics fitting.')
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
        detectUnmeasuredTorque = not self.useReactionWheels
        initializeSuccess = self.dynamicsFitter.timeSyncAndInitializePipeline(
            self.dynamicsInit,
            useReactionWheels=self.useReactionWheels,
            shiftGRF=self.shiftGRF,
            maxShiftGRF=4,
            iterationsPerShift=20,
            maxTrialsToSolveMassOver=self.maxTrialsToSolveMassOver,
            avgPositionChangeThreshold=0.20,
            avgAngularChangeThreshold=0.20,
            reoptimizeTrackingMarkers=True,
            reoptimizeAnatomicalMarkers=self.dynamicsMarkerOffsets,
            detectUnmeasuredTorque=detectUnmeasuredTorque
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
        print(f'Avg Residual Force: {pair[0]} N ({(pair[0] / secondPair[0] if secondPair[0] != 0 else 1.0) * 100}% of original {secondPair[0]} N)',
              flush=True)
        print(f'Avg Residual Torque: {pair[1]} Nm ({(pair[1] / secondPair[1] if secondPair[1] != 0 else 1.0) * 100}% of original {secondPair[1]} Nm)',
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
            for line in iter(p.stdout.readline, b''):
                print(line.decode(), end='')
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
                self.sex,
                self.massKg,
                self.heightM,
                self.ageYears,
                False,
                self.trialNames,
                self.subjectTags,
                self.trialTags,
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

    def run_moco(self):

        # 10. Run a MocoProblem for each trial.
        # -------------------------------------
        import opensim as osim

        # 10.1. Create the Moco results directory.
        if not os.path.exists(self.path + 'results/Moco'):
            os.mkdir(self.path + 'results/Moco')

        # 10.2. Check the model to see if it is appropriate for MocoInverse.
        model_fpath = self.path + f'results/Models/final.osim'
        model = osim.Model(model_fpath)
        model.initSystem()
        forceSet = model.getForceSet()
        numMuscles = 0
        numContacts = 0
        for iforce in range(forceSet.getSize()):
            force = forceSet.get(iforce)
            if force.getConcreteClassName().endswith('Muscle'):
                numMuscles += 1
            elif force.getConcreteClassName().endswith('SmoothSphereHalfSpaceForce'):
                numContacts += 1
            elif force.getConcreteClassName().endswith('HuntCrossleyForce'):
                numContacts += 1
            elif force.getConcreteClassName().endswith('ElasticFoundationForce'):
                numContacts += 1

        if numMuscles == 0:
            self.runMoco = False
            print(f'WARNING: The model has no muscles! Skipping MocoInverse...')
            self.skippedMocoReason = 'The model contains no muscles.'

        if numContacts > 0:
            self.runMoco = False
            print(f'WARNING: The model has contact forces! Skipping MocoInverse...')
            self.skippedMocoReason = 'The model contains contact force models, which typically do not work well with ' \
                                     'MocoInverse. Try removing the contact force models and re-running the problem ' \
                                     f'using the script(s) located in the directory results/Moco.'

        for itrial in range(len(self.trialNames)):
            # 10.3. Get the initial and final times for this trial.
            ik_table = osim.TimeSeriesTable(self.path + f'results/IK/{self.trialNames[itrial]}_ik.mot')
            initial_time = ik_table.getIndependentColumn()[0]
            final_time = ik_table.getIndependentColumn()[-1]
            duration = final_time - initial_time
            # Limit the duration to avoid very large MocoInverse problems.
            max_duration = 3.0  # seconds
            self.trialProcessingResults[itrial]['mocoInitialTime'] = initial_time
            self.trialProcessingResults[itrial]['mocoFinalTime'] = final_time
            self.trialProcessingResults[itrial]['mocoLimitedDuration'] = False
            if duration > max_duration:
                final_time = initial_time + duration
                self.trialProcessingResults[itrial]['mocoFinalTime'] = final_time
                self.trialProcessingResults[itrial]['mocoLimitedDuration'] = True
                print(f'WARNING: Trial {self.trialNames[itrial]} is too long for Moco! Limiting the time range to '
                      f'[{initial_time}, {final_time}].')

            # 10.4. Fill the template MocoInverse problems for this trial.
            moco_template_fpath = os.path.join(TEMPLATES_PATH, 'template_moco.py')
            moco_inverse_fpath = self.path + f'results/Moco/{self.trialNames[itrial]}_moco.py'
            fill_moco_template(moco_template_fpath, moco_inverse_fpath, self.trialNames[itrial],
                               initial_time, final_time)

            moco_template_fpath = os.path.join(TEMPLATES_PATH, 'template_moco.m')
            moco_inverse_fpath = self.path + f'results/Moco/{self.trialNames[itrial]}_moco.m'
            fill_moco_template(moco_template_fpath, moco_inverse_fpath, self.trialNames[itrial],
                               initial_time, final_time)

            # 10.5. Run the MocoInverse problem for this trial.
            if self.runMoco:
                print(f'Running MocoInverse for trial {self.trialNames[itrial]}')
                kinematics_fpath = self.path + f'results/IK/{self.trialNames[itrial]}_ik.mot'
                extloads_fpath = self.path + f'results/ID/{self.trialNames[itrial]}_external_forces.xml'
                solution_fpath = self.path + f'results/Moco/{self.trialNames[itrial]}_moco.sto'
                report_fpath = self.path + f'results/Moco/{self.trialNames[itrial]}_moco.pdf'
                mocoResults = run_moco_problem(model_fpath, kinematics_fpath, extloads_fpath, initial_time, final_time,
                                               solution_fpath, report_fpath)

                # 10.5. Store the MocoInverse results.
                if not os.path.exists(solution_fpath):
                    self.trialProcessingResults[itrial]['mocoSuccess'] = False
                else:
                    for k, v in mocoResults.items():
                        self.trialProcessingResults[itrial][k] = v

                # 10.6. Update the plot.csv file with the MocoInverse results.
                trialPath = self.path + 'trials/' + self.trialNames[itrial] + '/'
                plotCSVFile = trialPath + 'plot.csv'
                # Copy 'plot.csv' to a temporary file, so we don't overwrite it while modifying it.
                tempPlotCSVFile = trialPath + 'temp_plot.csv'
                shutil.copyfile(plotCSVFile, tempPlotCSVFile)
                # Load the MocoInverse results.
                mocoTrajectory: nimble.biomechanics.OpenSimMocoTrajectory = \
                    nimble.biomechanics.OpenSimParser.loadMocoTrajectory(solution_fpath)
                # Load the temporary file, append the MocoInverse results, and save the new 'plot.csv' file.
                nimble.biomechanics.OpenSimParser.appendMocoTrajectoryAndSaveCSV(
                    tempPlotCSVFile, mocoTrajectory, plotCSVFile)
                # Remove the temporary file.
                os.remove(tempPlotCSVFile)


    def create_output_folder(self):

        # 12. Create the output folder.
        # -----------------------------

        # 12.1. Move the results to the output folder.
        shutil.move(self.path + 'results', self.path + self.output_name)
        print('Zipping up OpenSim files...', flush=True)
        shutil.make_archive(self.path + self.output_name, 'zip', self.path, self.output_name)
        print('Finished outputting OpenSim files.', flush=True)

        # 12.2. Write out the result summary JSON file.
        print('Writing the _results.json file...', flush=True)
        try:
            with open(self.path + '_results.json', 'w') as f:
                json.dump(self.processingResult, f)
        except RuntimeError as e:
            print('Had an error writing _results.json:', flush=True)
            print(e, flush=True)

        # 12.3. Generate final zip file.
        print('Generated a final zip file at ' + self.path + self.output_name + '.zip.')
        print('Done!', flush=True)


def main():
    # Process input arguments.
    # ------------------------
    print(sys.argv, flush=True)
    if len(sys.argv) < 2:
        raise RuntimeError('Must provide a path to a subject folder.')

    # Subject folder path.
    path = sys.argv[1]
    if not path.endswith('/'):
        path += '/'

    # Output name.
    output_name = sys.argv[2] if len(sys.argv) > 2 else 'osim_results'

    # Subject href.
    href = sys.argv[3] if len(sys.argv) > 3 else ''

    # Construct the subject
    # ---------------------
    subject = Subject()
    try:
        subject.load_folder(os.path.abspath(path), DATA_FOLDER_PATH)
        # This auto-segments the trials, without throwing away any segments. The segments are split based on which parts
        # of the trial have GRF data, and also based on ensuring that the segments don't get beyond a certain length.
        subject.segment_trials()
        # The kinematics fit will fit the body scales, marker offsets, and motion of the subject, to all the trial
        # segments that have not yet thrown an error during loading.
        subject.run_kinematics_fit(DATA_FOLDER_PATH)
        # The dynamics fit will fit the dynamics parameters of the subject, to all the trial segments that have not yet
        # thrown an error during loading or kinematics fitting.
        if not subject.disableDynamics:
            subject.run_dynamics_fit()
        # This will write out a folder of OpenSim results files.
        subject.write_opensim_results(os.path.abspath(path + '/osim_results'),
                                      DATA_FOLDER_PATH)
        # This will write out all the results to display in the web UI back into the existing folder structure
        subject.write_web_results(os.path.abspath(path))
        # This will write out a B3D file
        subject.write_b3d_file(os.path.abspath(path + '/results.b3d'), os.path.abspath(path + '/osim_results'), href)
    except Error as e:
        # If we failed, write a JSON file with the error information.
        json_data = json.dumps(e.get_error_dict(), indent=4)
        print(json_data)
        # with open(engine.errors_json_path, "w") as json_file:
        #     json_file.write(json_data)
        # Return a non-zero exit code to tell the `mocap_server.py` that we failed, so it can write an ERROR flag
        exit(1)

    # engine = Engine(path=path,
    #                 output_name=output_name,
    #                 href=href)
    #
    # # Run the pipeline.
    # # -----------------
    # try:
    #     # Each method is automatically wrapped in a try-catch block so
    #     # that the pipeline will continue running if an error occurs.
    #     engine.validate_paths()
    #     engine.parse_subject_json()
    #     engine.load_model_files()
    #     engine.configure_marker_fitter()
    #     engine.preprocess_trials()
    #     engine.run_marker_fitting()
    #     if engine.fitDynamics:
    #         engine.run_dynamics_fitting()
    #     engine.write_result_files()
    #     if engine.exportMoco:
    #         engine.run_moco()
    #     engine.generate_readme()
    #     engine.create_output_folder()
    # except Error as e:
    #     # If we failed, write a JSON file with the error information.
    #     json_data = json.dumps(e.get_error_dict(), indent=4)
    #     with open(engine.errors_json_path, "w") as json_file:
    #         json_file.write(json_data)
    #     # Return a non-zero exit code to tell the `mocap_server.py` that we failed, so it can write an ERROR flag
    #     exit(1)


if __name__ == "__main__":
    main()