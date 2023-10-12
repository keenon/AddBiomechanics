from trial import TrialSegment, Trial, ProcessingStatus
from typing import List, Dict, Tuple, Any, Optional
import json
import nimblephysics as nimble
from nimblephysics import absPath
import numpy as np
import os
import shutil
import subprocess
import textwrap
import tempfile
import os


# Global paths to the geometry and data folders.
GEOMETRY_FOLDER_PATH = absPath('../../Geometry')
DATA_FOLDER_PATH = absPath('../../../data')
TEMPLATES_PATH = absPath('../../templates')

KINEMATIC_OSIM_NAME = 'match_markers_but_ignore_physics.osim'
DYNAMICS_OSIM_NAME = 'match_markers_and_physics.osim'


class Subject:
    def __init__(self):
        # 0. Initialize the engine.
        # -------------------------
        self.subject_path = ''
        self.processingResult: Dict[str, Any] = {}

        # 0.2. Subject pipeline parameters.
        self.massKg = 68.0
        self.heightM = 1.6
        self.biologicalSex = 'unknown'
        self.ageYears = -1
        self.subjectTags = []
        self.skeletonPreset = 'vicon'
        self.exportSDF = False
        self.exportMJCF = False
        self.exportOSIM = True
        self.exportMoco = False
        self.kinematicsIterations = 500
        self.initialIKRestarts = 150
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
        self.segmentTrials = False
        self.trialRanges = dict()
        self.mergeZeroForceSegmentsThreshold = 1.0
        self.footBodyNames = ['calcn_l', 'calcn_r']
        self.totalForce = 0.0
        self.fitDynamics = False
        self.skippedDynamicsReason = None
        self.runMoco = False
        self.skippedMocoReason = None
        self.lowpass_hz = 25

        # 0.3. Shared data structures.
        self.trials: List[Trial] = []
        self.skeleton: nimble.dynamics.Skeleton = None
        self.fitMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
        self.markerSet: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
        self.customOsim: nimble.biomechanics.OpenSimFile = None
        self.goldOsim: nimble.biomechanics.OpenSimFile = None
        self.simplified: nimble.dynamics.Skeleton = None
        self.kinematics_skeleton: nimble.dynamics.Skeleton = None
        self.kinematics_markers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
        self.dynamics_skeleton: nimble.dynamics.Skeleton = None
        self.dynamics_markers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
        # self.fitMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
        # self.finalMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
        self.bodyMasses = []

        # 0.4. Outputs.
        self.guessedTrackingMarkers = False
        self.totalFrames = 0
        self.totalJointLimitsHits: Dict[str, int] = {}
        self.totalJointWarnings: List[str] = []

    ###################################################################################################################
    # Loading the Subject from a folder
    ###################################################################################################################

    def load_subject_json(self, subject_json_path: str):
        # 2. Read the subject parameters from the JSON dictionary, which is saved as a file.
        # --------------------------------------------------
        with open(subject_json_path) as subj:
            subject_json = json.loads(subj.read())
            self.parse_subject_json(subject_json)

    def parse_subject_json(self, subject_json: Dict[str, Any]):
        # 2. Read the subject parameters from the JSON dictionary
        # --------------------------------------------------
        if 'massKg' in subject_json:
            self.massKg = float(subject_json['massKg'])

        if 'heightM' in subject_json:
            self.heightM = float(subject_json['heightM'])

        if 'ageYears' in subject_json:
            self.ageYears = int(subject_json['ageYears'])

        if 'subjectTags' in subject_json:
            self.subjectTags = subject_json['subjectTags']

        if 'sex' in subject_json:
            self.biologicalSex = subject_json['sex']

        if 'skeletonPreset' in subject_json:
            self.skeletonPreset = subject_json['skeletonPreset']

        if 'exportSDF' in subject_json:
            self.exportSDF = subject_json['exportSDF']

        if 'exportMJCF' in subject_json:
            self.exportMJCF = subject_json['exportMJCF']

        # Only export OpenSim files if we're not exporting MJCF or SDF files, since they use incompatible skeletons.
        self.exportOSIM = not (self.exportMJCF or self.exportSDF)

        if 'exportMoco' in subject_json:
            self.exportMoco = subject_json['exportMoco']

        if 'runMoco' in subject_json:
            self.runMoco = subject_json['runMoco']
            self.exportMoco = True if self.runMoco else self.exportMoco

        if 'ignoreJointLimits' in subject_json:
            self.ignoreJointLimits = subject_json['ignoreJointLimits']

        if 'residualsToZero' in subject_json:
            self.residualsToZero = subject_json['residualsToZero']

        if 'useReactionWheels' in subject_json:
            self.useReactionWheels = subject_json['useReactionWheels']

        if 'tuneResidualLoss' in subject_json:
            self.tuneResidualLoss = subject_json['tuneResidualLoss']

        if 'shiftGRF' in subject_json:
            self.shiftGRF = subject_json['shiftGRF']

        if 'maxTrialsToSolveMassOver' in subject_json:
            self.maxTrialsToSolveMassOver = subject_json['maxTrialsToSolveMassOver']

        if 'regularizeJointAcc' in subject_json:
            self.regularizeJointAcc = subject_json['regularizeJointAcc']

        if 'dynamicsMarkerOffsets' in subject_json:
            self.dynamicsMarkerOffsets = subject_json['dynamicsMarkerOffsets']

        if 'dynamicsMarkerWeight' in subject_json:
            self.dynamicsMarkerWeight = subject_json['dynamicsMarkerWeight']

        if 'dynamicsJointWeight' in subject_json:
            self.dynamicsJointWeight = subject_json['dynamicsJointWeight']

        if 'dynamicsRegularizePoses' in subject_json:
            self.dynamicsRegularizePoses = subject_json['dynamicsRegularizePoses']

        if 'ignoreFootNotOverForcePlate' in subject_json:
            self.ignoreFootNotOverForcePlate = subject_json['ignoreFootNotOverForcePlate']

        if 'disableDynamics' in subject_json:
            self.disableDynamics = subject_json['disableDynamics']

        if 'segmentTrials' in subject_json:
            self.segmentTrials = subject_json['segmentTrials']

        if 'mergeZeroForceSegmentsThreshold' in subject_json:
            self.mergeZeroForceSegmentsThreshold = subject_json['mergeZeroForceSegmentsThreshold']

        if self.skeletonPreset == 'vicon' or self.skeletonPreset == 'cmu' or self.skeletonPreset == 'complete':
            self.footBodyNames = ['calcn_l', 'calcn_r']
        elif 'footBodyNames' in subject_json:
            self.footBodyNames = subject_json['footBodyNames']

        if 'trialRanges' in subject_json:
            self.trialRanges = subject_json['trialRanges']

    def load_model_files(self, subject_path: str, data_folder_path: str):
        if not subject_path.endswith('/'):
            subject_path += '/'
        self.subject_path = subject_path

        geometry_folder_path = os.path.join(data_folder_path, 'Geometry')

        # 1.1. Check that the Geometry folder exists.
        if not os.path.exists(geometry_folder_path):
            raise IsADirectoryError('Geometry folder "' + geometry_folder_path + '" does not exist.')

        # 1.2. Symlink in Geometry, if it doesn't come with the folder, so we can load meshes for the visualizer and for priors
        if not os.path.exists(subject_path + 'Geometry'):
            os.symlink(geometry_folder_path, subject_path + 'Geometry')

        # 3. Load the unscaled OSIM file.
        # -------------------------------
        # 3.0. Check for if we're using a preset OpenSim model. Otherwise, use the custom one provided by the user.
        if self.skeletonPreset == 'vicon':
            shutil.copy(data_folder_path + '/PresetSkeletons/Rajagopal2015_ViconPlugInGait.osim',
                        subject_path + 'unscaled_generic.osim')
        elif self.skeletonPreset == 'cmu':
            shutil.copy(data_folder_path + '/PresetSkeletons/Rajagopal2015_CMUMarkerSet.osim',
                        subject_path + 'unscaled_generic.osim')
        elif self.skeletonPreset == 'complete':
            shutil.copy(data_folder_path + '/PresetSkeletons/CompleteHumanModel.osim',
                        subject_path + 'unscaled_generic.osim')
        else:
            if self.skeletonPreset != 'custom':
                print('Unrecognized skeleton preset "' + str(self.skeletonPreset) +
                      '"! Behaving as though this is "custom"')
            if not os.path.exists(subject_path + 'unscaled_generic.osim'):
                raise FileNotFoundError('We are using a custom OpenSim skeleton, but there is no unscaled_generic.osim '
                                        'file present.')

        # 3.1. Rationalize CustomJoint's in the OSIM file.
        shutil.move(subject_path + 'unscaled_generic.osim',
                    subject_path + 'unscaled_generic_raw.osim')
        nimble.biomechanics.OpenSimParser.rationalizeJoints(subject_path + 'unscaled_generic_raw.osim',
                                                            subject_path + 'unscaled_generic.osim')

        # 3.2. Load the rational file.
        self.customOsim: nimble.biomechanics.OpenSimFile = nimble.biomechanics.OpenSimParser.parseOsim(
            subject_path + 'unscaled_generic.osim')
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

        # Allow pretty much unconstrained root translation
        self.skeleton.setPositionUpperLimit(3, 1000)
        self.skeleton.setPositionLowerLimit(3, -1000)
        self.skeleton.setPositionUpperLimit(4, 1000)
        self.skeleton.setPositionLowerLimit(4, -1000)
        self.skeleton.setPositionUpperLimit(5, 1000)
        self.skeleton.setPositionLowerLimit(5, -1000)

        # 3.4. Load the hand-scaled OSIM file, if it exists.
        self.goldOsim: nimble.biomechanics.OpenSimFile = None
        if os.path.exists(subject_path + 'manually_scaled.osim'):
            self.goldOsim = nimble.biomechanics.OpenSimParser.parseOsim(
                subject_path + 'manually_scaled.osim')

    def load_trials(self, trials_folder_path: str):
        if not trials_folder_path.endswith('/'):
            trials_folder_path += '/'

        # This loads all the trials in the subject folder.
        for trial_name in os.listdir(trials_folder_path):
            # We only want to load folders, not files
            if not os.path.isdir(trials_folder_path + trial_name):
                continue
            trial: Trial = Trial.load_trial(trial_name, trials_folder_path + trial_name + '/')
            self.trials.append(trial)

    def load_folder(self, subject_folder: str, data_folder_path: str):
        # This is just a convenience wrapper to load a subject folder in a standard format.
        if not subject_folder.endswith('/'):
            subject_folder += '/'
        self.load_subject_json(subject_folder + '_subject.json')
        self.load_model_files(subject_folder, data_folder_path)
        self.load_trials(subject_folder + 'trials/')

    ###################################################################################################################
    # Processing the Subject
    ###################################################################################################################

    def segment_trials(self):
        """
        This function splits the trials into segments based on when the GRF is zero, and also based on a maximum length
        per trial, to allow the kinematics and dynamics pipelines to run more efficiently.
        """
        for trial in self.trials:
            if not trial.error:
                trial.split_segments(max_grf_gap_fill_size=1.0, max_segment_frames=2000)

    def evaluate_manually_scaled_error(self):
        """
        This function computes the error between the manually scaled skeleton and the marker data, if present.
        """
        if self.goldOsim is None:
            return
        for trial in self.trials:
            for segment in trial.segments:
                segment.compute_manually_scaled_ik_error(self.goldOsim)

    def run_kinematics_fit(self, data_folder_path: str):
        """
        This will optimize for body scales, marker offsets, and joint positions over time to minimize marker error. It
        ignores the dynamics information at this stage, even if it was provided.
        """

        # Set up the MarkerFitter
        marker_fitter = nimble.biomechanics.MarkerFitter(
            self.skeleton, self.markerSet)
        marker_fitter.setInitialIKSatisfactoryLoss(1e-5)
        marker_fitter.setInitialIKMaxRestarts(self.initialIKRestarts)
        marker_fitter.setIterationLimit(self.kinematicsIterations)
        marker_fitter.setIgnoreJointLimits(self.ignoreJointLimits)

        # 1.1. Set the tracking markers.
        num_anatomical_markers = len(self.customOsim.anatomicalMarkers)
        if num_anatomical_markers > 10:
            marker_fitter.setTrackingMarkers(self.customOsim.trackingMarkers)
        else:
            print(f'NOTE: The input *.osim file specified suspiciously few ({num_anatomical_markers} less than the '
                  f'minimum 10) anatomical landmark markers (with <fixed>true</fixed>), so we will default '
                  f'to treating all markers as anatomical except triad markers with the suffix "1", "2", or "3"',
                  flush=True)
            marker_fitter.setTriadsToTracking()
            self.guessedTrackingMarkers = True

        # 1.2. Set default cost function weights.
        marker_fitter.setRegularizeAnatomicalMarkerOffsets(10.0)
        marker_fitter.setRegularizeTrackingMarkerOffsets(0.05)
        marker_fitter.setMinSphereFitScore(0.01)
        marker_fitter.setMinAxisFitScore(0.001)
        marker_fitter.setMaxJointWeight(1.0)

        # 2. Run marker fitting.
        # ----------------------
        print('Fitting trials:', flush=True)
        for i_trial, trial in enumerate(self.trials):
            print(f' --> {trial.trial_name}', flush=True)

        # 2.1. Clean up the marker data.
        for i in range(len(self.trials)):
            trial: Trial = self.trials[i]
            for j in range(len(trial.segments)):
                trial_segment: TrialSegment = trial.segments[j]
                print('Checking and repairing marker data quality on trial ' +
                      trial.trial_name + ' segment ' + str(j+1) + '/' + str(len(trial.segments)) + '. This can take a '
                      'while, depending on trial length...', flush=True)
                has_enough_markers = marker_fitter.checkForEnoughMarkers(trial_segment.marker_observations)
                if not has_enough_markers:
                    marker_set = set()
                    for obs in trial_segment.marker_observations:
                        for key in obs:
                            marker_set.add(key)
                    trial_segment.has_error = True
                    trial_segment.error_msg = (f'There are fewer than 8 markers that show up in the OpenSim model and '
                                               f'in trial {trial.trial_name} segment {str(j+1)}/'
                                               f'{str(len(trial.segments))}. The markers in this trial are: '
                                               f'{str(marker_set)}')
                    trial_segment.kinematics_status = ProcessingStatus.ERROR
                    print(trial_segment.error_msg, flush=True)
                else:
                    self.totalFrames += len(trial_segment.marker_observations)
                    # NOTE: When this was passed trial_segment.original_marker_observations, we got weird crashes with
                    # data corruption, but only on builds of Nimble coming from CI. Passing
                    # trial_segment.marker_observations instead seems to fix it. This is scary.
                    trial_error_report = marker_fitter.generateDataErrorsReport(
                        trial_segment.marker_observations,
                        trial.timestep,
                        rippleReduce=True,
                        rippleReduceUseSparse=True,
                        rippleReduceUseIterativeSolver=True,
                        rippleReduceSolverIterations=int(1e5))
                    # Set up the new marker observations
                    new_marker_observations: List[Dict[str, np.ndarray]] = []
                    for t in range(trial_error_report.getNumTimesteps()):
                        new_marker_observations.append({})
                        for marker_name in trial_error_report.getMarkerNamesOnTimestep(t):
                            new_marker_observations[t][marker_name] = trial_error_report.getMarkerPositionOnTimestep(t, marker_name)
                    trial_segment.marker_observations = new_marker_observations
                    trial_segment.marker_error_report = trial_error_report
                    # Set an error if there are any NaNs in the marker data
                    for t in range(len(trial_segment.marker_observations)):
                        for marker in trial_segment.marker_observations[t]:
                            if np.any(np.isnan(trial_segment.marker_observations[t][marker])):
                                trial_segment.has_error = True
                                trial_segment.error_msg = 'Trial had NaNs in the data after running MarkerFixer.'
                                print(trial_segment.error_msg, flush=True)
                                break
                            if np.any(np.abs(trial_segment.marker_observations[t][marker]) > 1e+6):
                                trial_segment.has_error = True
                                trial_segment.error_msg = ('Trial had suspiciously large marker values after running '
                                                           'MarkerFixer.')
                                print(trial_segment.error_msg, flush=True)
                                break
                        if trial_segment.has_error:
                            break

        print('All trial markers have been cleaned up!', flush=True)

        trial_segments: List[TrialSegment] = []
        for trial in self.trials:
            if not trial.error:
                for segment in trial.segments:
                    if segment.has_markers and not segment.has_error:
                        trial_segments.append(segment)
                        segment.kinematics_status = ProcessingStatus.IN_PROGRESS
                    else:
                        segment.kinematics_status = ProcessingStatus.ERROR
                        if segment.has_error:
                            print('Skipping kinematics fit of segment starting at ' + str(segment.start) + ' of trial ' + str(trial.trial_name) + ' due to error: ' + str(segment.error_msg), flush=True)
            else:
                # If the whole trial is an error condition, then bail on all the segments as well
                for segment in trial.segments:
                    segment.kinematics_status = ProcessingStatus.ERROR
        # If there are no segments left that aren't in error, quit
        if len(trial_segments) == 0:
            print('ERROR: No trial segments left (after filtering out errors) to fit kinematics on. Skipping kinematics fitting...', flush=True)
            return

        # 2.2. Create an anthropometric prior.
        anthropometrics: nimble.biomechanics.Anthropometrics = nimble.biomechanics.Anthropometrics.loadFromFile(
            data_folder_path + '/ANSUR_metrics.xml')
        cols = anthropometrics.getMetricNames()
        cols.append('weightkg')
        if self.biologicalSex == 'male':
            gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
                data_folder_path + '/ANSUR_II_MALE_Public.csv',
                cols,
                0.001)  # mm -> m
        elif self.biologicalSex == 'female':
            gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
                data_folder_path + '/ANSUR_II_FEMALE_Public.csv',
                cols,
                0.001)  # mm -> m
        else:
            gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
                data_folder_path + '/ANSUR_II_BOTH_Public.csv',
                cols,
                0.001)  # mm -> m
        observed_values = {
            'stature': self.heightM,
            'weightkg': self.massKg * 0.01,
        }
        gauss = gauss.condition(observed_values)
        anthropometrics.setDistribution(gauss)
        marker_fitter.setAnthropometricPrior(anthropometrics, 0.1)
        marker_fitter.setExplicitHeightPrior(self.heightM, 0.1)

        marker_fitter.setRegularizePelvisJointsWithVirtualSpring(0.1)

        # # TODO: Remove me
        # marker_fitter.setIterationLimit(20)

        # 2.3. Run the kinematics pipeline.

        marker_fitter_results: List[
            nimble.biomechanics.MarkerInitialization] = marker_fitter.runMultiTrialKinematicsPipeline(
            [segment.marker_observations for segment in trial_segments],
            nimble.biomechanics.InitialMarkerFitParams()
            .setMaxTrialsToUseForMultiTrialScaling(5)
            .setMaxTimestepsToUseForMultiTrialScaling(4000),
            150)

        # 2.4. Set the masses based on the change in mass of the model.
        unscaled_skeleton_mass = self.skeleton.getMass()
        mass_scale_factor = self.massKg / unscaled_skeleton_mass
        print(f'Unscaled skeleton mass: {unscaled_skeleton_mass}')
        print(f'Mass scale factor: {mass_scale_factor}')
        self.bodyMasses = dict()
        for i_body in range(self.skeleton.getNumBodyNodes()):
            body = self.skeleton.getBodyNode(i_body)
            body.setMass(body.getMass() * mass_scale_factor)
            self.bodyMasses[body.getName()] = body.getMass()

        err_msg = (f'ERROR: expected final skeleton mass to equal {self.massKg} kg after scaling, '
                   f'but the final mass is {self.skeleton.getMass()}')
        np.testing.assert_almost_equal(self.skeleton.getMass(), self.massKg, err_msg=err_msg, decimal=4)

        # # 2.5. Check for any flipped markers, now that we've done a first pass
        # TODO: re-enable this section
        # any_swapped = False
        # for i in range(len(trial_segments)):
        #     if marker_fitter.checkForFlippedMarkers(trial_segments[i].marker_observations, marker_fitter_results[i],
        #                                             trial_segments[i].marker_error_report):
        #         any_swapped = True
        #         new_marker_observations: List[Dict[str, np.ndarray]] = []
        #         for t in range(trial_segments[i].marker_error_report.getNumTimesteps()):
        #             new_marker_observations.append({})
        #             for marker_name in trial_segments[i].marker_error_report.getMarkerNamesOnTimestep(t):
        #                 new_marker_observations[t][marker_name] = trial_segments[i].marker_error_report.getMarkerPositionOnTimestep(t, marker_name)
        #         trial_segments[i].marker_observations = new_marker_observations
        #
        # if any_swapped:
        #     print("******** Unfortunately, it looks like some markers were swapped in the uploaded data, "
        #           "so we have to run the whole pipeline again with unswapped markers. ********",
        #           flush=True)
        #     marker_fitter_results = marker_fitter.runMultiTrialKinematicsPipeline(
        #         [trial.marker_observations for trial in trial_segments],
        #         nimble.biomechanics.InitialMarkerFitParams()
        #         .setMaxTrialsToUseForMultiTrialScaling(5)
        #         .setMaxTimestepsToUseForMultiTrialScaling(4000),
        #         150)

        self.skeleton.setGroupScales(marker_fitter_results[0].groupScales)
        self.fitMarkers = marker_fitter_results[0].updatedMarkerMap

        # 2.6. Set up some interchangeable data structures, so that we can write out the results using the same code,
        # regardless of whether we used dynamics or not
        self.kinematics_skeleton = self.skeleton.clone()
        self.kinematics_markers = {key: (self.kinematics_skeleton.getBodyNode(body.getName()), offset) for key, (body, offset) in self.fitMarkers.items()}
        for i in range(len(trial_segments)):
            if marker_fitter_results[i].error:
                trial_segments[i].kinematics_status = ProcessingStatus.ERROR
                trial_segments[i].error_msg = marker_fitter_results[i].errorMsg
            else:
                trial_segments[i].kinematics_status = ProcessingStatus.FINISHED
                trial_segments[i].kinematics_poses = marker_fitter_results[i].poses
                trial_segments[i].marker_fitter_result = marker_fitter_results[i]
                trial_segments[i].kinematics_ik_error_report = nimble.biomechanics.IKErrorReport(
                    self.kinematics_skeleton,
                    self.kinematics_markers,
                    trial_segments[i].kinematics_poses,
                    trial_segments[i].marker_observations)

    def lowpass_filter(self):
        """
        This will lowpass filter the results poses to smooth them out. It will also try to clean up the GRF data, by
        setting a threshold for background noise, and cutting off appropriately.
        """
        trial_segments: List[TrialSegment] = []
        for trial in self.trials:
            if not trial.error:
                for segment in trial.segments:
                    if (segment.has_markers and
                            segment.kinematics_status == ProcessingStatus.FINISHED and not segment.has_error):
                        trial_segments.append(segment)
                        segment.lowpass_status = ProcessingStatus.IN_PROGRESS
                    elif segment.has_error:
                        print('Skipping lowpass filtering of segment starting at ' + str(segment.start) + ' of trial ' + str(
                            trial.trial_name) + ' due to error: ' + str(segment.error_msg), flush=True)
        # If there are no segments left that aren't in error, quit
        if len(trial_segments) == 0:
            print('ERROR: No trial segments left (after filtering out errors) to lowpass filter. Skipping lowpass filter...', flush=True)
            return
        # Actually do the lowpass filtering
        for trial_segment in trial_segments:
            success = trial_segment.lowpass_filter(self.lowpass_hz)
            if success:
                trial_segment.lowpass_ik_error_report = nimble.biomechanics.IKErrorReport(
                    self.kinematics_skeleton,
                    self.kinematics_markers,
                    trial_segment.lowpass_poses,
                    trial_segment.marker_observations)
                trial_segment.lowpass_status = ProcessingStatus.FINISHED
            else:
                trial_segment.lowpass_status = ProcessingStatus.ERROR

    def run_dynamics_fit(self):
        """
        This will optimize for body masses, body scales, marker offsets, and joint positions over time to try to
        minimize the error with both marker data and force plate data simultaneously.
        """
        trial_segments: List[TrialSegment] = []
        for trial in self.trials:
            if not trial.error:
                for segment in trial.segments:
                    if (segment.has_markers and segment.has_forces
                            and segment.kinematics_status == ProcessingStatus.FINISHED and not segment.has_error):
                        trial_segments.append(segment)
                        segment.dynamics_status = ProcessingStatus.IN_PROGRESS
                    elif segment.has_error:
                        print('Skipping dynamics fit of segment starting at ' + str(segment.start) + ' of trial ' + str(
                            trial.trial_name) + ' due to error: ' + str(segment.error_msg), flush=True)
        # If there are no segments left that aren't in error, quit
        if len(trial_segments) == 0:
            print('ERROR: No trial segments left (after filtering out errors) to fit dynamics on. Skipping dynamics fitting...', flush=True)
            return

        # 8. Run dynamics fitting.
        # ------------------------
        print('Fitting dynamics on ' + str(len(trial_segments)) + ' trial segments...', flush=True)

        # 8.1. Construct a DynamicsFitter object.
        foot_bodies = []
        for name in self.footBodyNames:
            foot = self.skeleton.getBodyNode(name)
            if foot is None:
                raise RuntimeError(f'Foot "{str(name)}" not found in skeleton! Cannot run dynamics fitting.')
            foot_bodies.append(self.skeleton.getBodyNode(name))
        print('Using feet: ' + str(self.footBodyNames), flush=True)

        self.skeleton.setGravity([0.0, -9.81, 0.0])
        dynamics_fitter = nimble.biomechanics.DynamicsFitter(
            self.skeleton, foot_bodies, self.customOsim.trackingMarkers)
        print('Created DynamicsFitter', flush=True)

        # Sanity check the force plate data sizes match the kinematics data sizes
        for trial_segment in trial_segments:
            # print('Trial name: ' + str(trial_segment.parent.trial_name))
            # print('Trial start: ' + str(trial_segment.start))
            # print('Trial poses: ' + str(trial_segment.kinematics_poses.shape))
            # print('Trial poses head: ' + str(trial_segment.kinematics_poses[:, :5]))
            # print('Trial poses tail: ' + str(trial_segment.kinematics_poses[:, -5:]))
            # print('Trial force plates: ' + str(trial_segment.force_plates))
            # print('Poses cols: ' + str(trial_segment.kinematics_poses.shape[1]))
            # results: nimble.biomechanics.MarkerInitialization = trial_segment.marker_fitter_result
            # print('Group scales: ' + str(results.groupScales))
            # print('Updated marker map: ' + str(results.updatedMarkerMap))
            # print('Joints: ' + str(results.joints))
            # print('Joints adjacent markers: ' + str(results.jointsAdjacentMarkers))
            # print('Joint weights shape: ' + str(results.jointWeights.shape))
            # print('Axis weights shape: ' + str(results.axisWeights.shape))
            # print('Joint axis shape: ' + str(results.jointAxis.shape))
            # print('Joint centers shape: ' + str(results.jointCenters.shape))
            for force_plate in trial_segment.force_plates:
                print('force len: '+str(len(force_plate.forces)))
                assert(trial_segment.kinematics_poses.shape[1] == len(force_plate.forces))
                assert(len(force_plate.forces) == len(force_plate.centersOfPressure))
                assert(len(force_plate.forces) == len(force_plate.moments))

        # 8.2. Initialize the dynamics fitting problem.
        dynamics_init: nimble.biomechanics.DynamicsInitialization = \
            nimble.biomechanics.DynamicsFitter.createInitialization(
                self.skeleton,
                [segment.marker_fitter_result for segment in trial_segments],
                self.customOsim.trackingMarkers,
                foot_bodies,
                [segment.lowpass_force_plates if segment.lowpass_status == ProcessingStatus.FINISHED else segment.force_plates for segment in trial_segments],
                [int(1.0 / segment.parent.timestep) for segment in trial_segments],
                [segment.marker_observations for segment in trial_segments])
        print('Created DynamicsInitialization', flush=True)

        dynamics_fitter.estimateFootGroundContacts(dynamics_init,
                                                   ignoreFootNotOverForcePlate=self.ignoreFootNotOverForcePlate)
        print("Initial mass: " +
              str(self.skeleton.getMass()) + " kg", flush=True)
        print("What we'd expect average ~GRF to be (Mass * 9.8): " +
              str(self.skeleton.getMass() * 9.8) + " N", flush=True)
        second_pair = dynamics_fitter.computeAverageRealForce(dynamics_init)
        print("Avg Force: " + str(second_pair[0]) + " N", flush=True)
        print("Avg Torque: " + str(second_pair[1]) + " Nm", flush=True)

        dynamics_fitter.addJointBoundSlack(self.skeleton, 0.1)

        # We don't actually want to do this. This pushes the state away from the initial state
        # if it near bounds, on the theory that this will lead to easier initialization with
        # an interior-point solver (since we won't be pushed so far in early iterations). The
        # cost seems to be greater than the reward, though.
        # dynamicsFitter.boundPush(dynamicsInit)

        dynamics_fitter.smoothAccelerations(dynamics_init)
        detect_unmeasured_torque = not self.useReactionWheels
        initialize_success = dynamics_fitter.timeSyncAndInitializePipeline(
            dynamics_init,
            useReactionWheels=self.useReactionWheels,
            shiftGRF=self.shiftGRF,
            maxShiftGRF=4,
            iterationsPerShift=20,
            maxTrialsToSolveMassOver=self.maxTrialsToSolveMassOver,
            avgPositionChangeThreshold=0.20,
            avgAngularChangeThreshold=0.20,
            reoptimizeTrackingMarkers=True,
            reoptimizeAnatomicalMarkers=self.dynamicsMarkerOffsets,
            detectUnmeasuredTorque=detect_unmeasured_torque,
            tuneLinkMasses=False
        )

        # 8.3. If initialization succeeded, we will proceed with the full "kitchen sink" optimization.
        if initialize_success:
            good_frames_count = 0
            total_frames_count = 0
            for trialMissingGRF in dynamics_init.probablyMissingGRF:
                good_frames_count += sum(
                    [0 if missing else 1 for missing in trialMissingGRF])
                total_frames_count += len(trialMissingGRF)
            bad_frames_count = total_frames_count - good_frames_count
            print('Detected missing/bad GRF data on ' + str(bad_frames_count) + '/' + str(
                total_frames_count) + ' frames',
                  flush=True)
            if good_frames_count == 0:
                print('ERROR: we have no good frames of GRF data left after filtering out suspicious GRF '
                      'frames. This probably means input GRF data is badly miscalibrated with respect to '
                      'marker data (maybe they are in different coordinate frames?), or there are unmeasured '
                      'external forces acting on your subject. Aborting the physics fitter!', flush=True)
                self.fitDynamics = False
            else:
                # Run an optimization to figure out the model parameters
                dynamics_fitter.setIterationLimit(200)
                dynamics_fitter.setLBFGSHistoryLength(20)

                dynamics_fitter.runIPOPTOptimization(
                    dynamics_init,
                    nimble.biomechanics.DynamicsFitProblemConfig(
                        self.skeleton)
                    .setDefaults(True)
                    .setResidualWeight(1e-2 * self.tuneResidualLoss)
                    .setMaxNumTrials(self.maxTrialsToSolveMassOver)
                    .setConstrainResidualsZero(False)
                    # .setIncludeMasses(True)
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
                for segment in range(len(dynamics_init.poseTrials)):
                    if len(dynamics_init.probablyMissingGRF[segment]) < 1000:
                        dynamics_fitter.setIterationLimit(200)
                        dynamics_fitter.setLBFGSHistoryLength(20)
                    elif len(dynamics_init.probablyMissingGRF[segment]) < 5000:
                        dynamics_fitter.setIterationLimit(100)
                        dynamics_fitter.setLBFGSHistoryLength(15)
                    else:
                        dynamics_fitter.setIterationLimit(50)
                        dynamics_fitter.setLBFGSHistoryLength(3)
                    #
                    # print('Running runIPOPTOptimization() for trial '+str(segment)+'...')
                    # dynamics_fitter.setIterationLimit(10)
                    #
                    # trial_segment = trial_segments[segment]
                    # print('Trial name: ' + str(trial_segment.parent.trial_name))
                    # print('Trial start: ' + str(trial_segment.start))
                    # print('Trial poses: ' + str(trial_segment.kinematics_poses.shape))
                    # print('Trial poses head: ' + str(trial_segment.kinematics_poses[:, :5]))
                    # print('Trial poses tail: ' + str(trial_segment.kinematics_poses[:, -5:]))
                    # print('Trial force plates: ' + str(trial_segment.force_plates))
                    # print('Poses cols: ' + str(trial_segment.kinematics_poses.shape[1]))
                    # results: nimble.biomechanics.MarkerInitialization = trial_segment.marker_fitter_result
                    # print('Group scales: ' + str(results.groupScales))
                    # print('Updated marker map: ' + str(results.updatedMarkerMap))
                    # print('Joints: ' + str(results.joints))
                    # print('Joints adjacent markers: ' + str(results.jointsAdjacentMarkers))
                    # print('Joint weights shape: ' + str(results.jointWeights.shape))
                    # print('Axis weights shape: ' + str(results.axisWeights.shape))
                    # print('Joint axis shape: ' + str(results.jointAxis.shape))
                    # print('Joint centers shape: ' + str(results.jointCenters.shape))
                    # for force_plate in trial_segment.force_plates:
                    #     print('force len: ' + str(len(force_plate.forces)))

                    dynamics_fitter.runIPOPTOptimization(
                        dynamics_init,
                        nimble.biomechanics.DynamicsFitProblemConfig(
                            self.skeleton)
                        .setDefaults(True)
                        .setOnlyOneTrial(segment)
                        .setResidualWeight(1e-2 * self.tuneResidualLoss)
                        .setConstrainResidualsZero(False)
                        .setIncludePoses(True)
                        .setJointWeight(self.dynamicsJointWeight)
                        .setMarkerWeight(self.dynamicsMarkerWeight)
                        .setRegularizePoses(self.dynamicsRegularizePoses)
                        .setRegularizeJointAcc(self.regularizeJointAcc))

                # Specifically optimize to 0-ish residuals, if user requests it
                if self.residualsToZero:
                    for segment in range(len(dynamics_init.poseTrials)):
                        original_trajectory = dynamics_init.poseTrials[segment].copy()
                        previous_total_residual = np.inf
                        for i in range(100):
                            # this holds the mass constant, and re-jigs the trajectory to try to get
                            # the angular ACC's to match more closely what was actually observed
                            pair = dynamics_fitter.zeroLinearResidualsAndOptimizeAngular(
                                dynamics_init,
                                segment,
                                original_trajectory,
                                previous_total_residual,
                                i,
                                useReactionWheels=self.useReactionWheels,
                                weightLinear=1.0,
                                weightAngular=0.5,
                                regularizeLinearResiduals=0.1,
                                regularizeAngularResiduals=0.1,
                                regularizeCopDriftCompensation=1.0,
                                maxBuckets=150)
                            previous_total_residual = pair[1]

                        dynamics_fitter.recalibrateForcePlates(
                            dynamics_init, segment)

        else:
            print('WARNING: Unable to minimize residual moments below the desired threshold. Skipping '
                  'body mass optimization and final bilevel optimization problem.', flush=True)

        # 8.4. Apply results to skeleton and check physical consistency.
        dynamics_fitter.applyInitToSkeleton(self.skeleton, dynamics_init)
        dynamics_fitter.computePerfectGRFs(dynamics_init)
        dynamics_fitter.checkPhysicalConsistency(
            dynamics_init, maxAcceptableErrors=1e-3, maxTimestepsToTest=25)

        # 8.5. Report the dynamics fitting results.
        print("Avg Marker RMSE: " +
              str(dynamics_fitter.computeAverageMarkerRMSE(dynamics_init) * 100) + "cm", flush=True)
        pair = dynamics_fitter.computeAverageResidualForce(dynamics_init)
        print(f'Avg Residual Force: {pair[0]} N ({(pair[0] / second_pair[0] if second_pair[0] != 0 else 1.0) * 100}% of original {second_pair[0]} N)',
              flush=True)
        print(f'Avg Residual Torque: {pair[1]} Nm ({(pair[1] / second_pair[1] if second_pair[1] != 0 else 1.0) * 100}% of original {second_pair[1]} Nm)',
              flush=True)
        print("Avg CoP movement in 'perfect' GRFs: " +
              str(dynamics_fitter.computeAverageCOPChange(dynamics_init)) + " m", flush=True)
        print("Avg force change in 'perfect' GRFs: " +
              str(dynamics_fitter.computeAverageForceMagnitudeChange(dynamics_init)) + " N", flush=True)

        self.fitMarkers = dynamics_init.updatedMarkerMap
        self.dynamics_skeleton = self.skeleton.clone()
        self.dynamics_markers = {key: (self.dynamics_skeleton.getBodyNode(body.getName()), offset) for key, (body, offset) in self.fitMarkers.items()}

        # 8.6. Store the dynamics fitting results in the shared data structures.
        for i in range(len(trial_segments)):
            trial_segments[i].dynamics_taus = dynamics_fitter.computeInverseDynamics(dynamics_init, i)
            pair = dynamics_fitter.computeAverageTrialResidualForce(dynamics_init, i)
            trial_segments[i].linear_residuals = pair[0]
            trial_segments[i].angular_residuals = pair[1]
            trial_segments[i].ground_height = dynamics_init.groundHeight[i]
            trial_segments[i].foot_body_wrenches = dynamics_init.grfTrials[i]
            trial_segments[i].missing_grf_reason = dynamics_init.missingGRFReason[i]

            bad_dynamics_frames: Dict[str, List[int]] = {}
            num_bad_dynamics_frames = 0
            for iframe, reason in enumerate(dynamics_init.missingGRFReason[i]):
                if reason.name not in bad_dynamics_frames:
                    bad_dynamics_frames[reason.name] = []
                bad_dynamics_frames[reason.name].append(iframe)
                if not reason.name == 'notMissingGRF':
                    num_bad_dynamics_frames += 1

            trial_segments[i].bad_dynamics_frames = bad_dynamics_frames
            trial_segments[i].dynamics_poses = dynamics_init.poseTrials[i]
            trial_segments[i].output_force_plates = dynamics_init.forcePlateTrials[i]
            trial_segments[i].dynamics_status = ProcessingStatus.FINISHED
            trial_segments[i].dynamics_ik_error_report = nimble.biomechanics.IKErrorReport(
                self.dynamics_skeleton,
                self.dynamics_markers,
                trial_segments[i].dynamics_poses,
                trial_segments[i].marker_observations)

    ###################################################################################################################
    # Writing out results
    ###################################################################################################################

    def get_overall_results_json(self) -> Dict[str, Any]:
        overall_results: Dict[str, Any] = {}
        for trial in self.trials:
            trial_results: Dict[str, Any] = {}
            segment_results: List[Dict[str, Any]] = [segment.get_segment_results_json() for segment in trial.segments]
            trial_results['segments'] = segment_results
            overall_results[trial.trial_name] = trial_results
        return overall_results

    def generate_readme(self) -> str:
        # 11. Generate the README file.
        # -----------------------------
        print('Generating README file...')

        text = ''
        text += "*** This data was generated with AddBiomechanics (www.addbiomechanics.org) ***\n"
        text += "AddBiomechanics was written by Keenon Werling.\n"
        text += "\n"
        text += textwrap.fill(
            "Please visit our forums on SimTK for help using the tool: "
            "https://simtk.org/plugins/phpBB/indexPhpbb.php?group_id=2402&pluginname=phpBB")

        # TODO: Add the rest of the autogenerated README file

        return text

    def scale_osim(self,
                   unscaled_generic_osim_path: str,
                   output_osim_path: str,
                   skel: nimble.dynamics.Skeleton,
                   markers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]]):
        marker_names: List[str] = []
        if skel is not None:
            print('Adjusting marker locations on scaled OpenSim file', flush=True)
            body_scales_map: Dict[str, np.ndarray] = {}
            for i in range(skel.getNumBodyNodes()):
                body_node: nimble.dynamics.BodyNode = skel.getBodyNode(i)
                # Now that we adjust the markers BEFORE we rescale the body, we don't want to rescale the marker locations
                # at all.
                body_scales_map[body_node.getName()] = np.ones(3)
            marker_offsets_map: Dict[str, Tuple[str, np.ndarray]] = {}
            for k in markers:
                v = markers[k]
                marker_offsets_map[k] = (v[0].getName(), v[1])
                marker_names.append(k)

        # Create a temporary directory
        with tempfile.TemporaryDirectory() as tmpdirname:
            if not tmpdirname.endswith('/'):
                tmpdirname += '/'

            nimble.biomechanics.OpenSimParser.moveOsimMarkers(
                unscaled_generic_osim_path,
                body_scales_map,
                marker_offsets_map,
                tmpdirname + 'unscaled_but_with_optimized_markers.osim')

            # 9.3. Write the XML instructions for the OpenSim scaling tool
            nimble.biomechanics.OpenSimParser.saveOsimScalingXMLFile(
                'optimized_scale_and_markers',
                skel,
                self.massKg,
                self.heightM,
                'unscaled_but_with_optimized_markers.osim',
                'Unassigned',
                'optimized_scale_and_markers.osim',
                tmpdirname + 'rescaling_setup.xml')

            # 9.4. Call the OpenSim scaling tool
            command = f'cd {tmpdirname} && opensim-cmd run-tool {tmpdirname}rescaling_setup.xml'
            print('Scaling OpenSim files: ' + command, flush=True)
            with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE) as p:
                for line in iter(p.stdout.readline, b''):
                    print(line.decode(), end='', flush=True)
                p.wait()

            # 9.5. Overwrite the inertia properties of the resulting OpenSim skeleton file
            any_trial_has_dynamics = False
            for trial in self.trials:
                for segment in trial.segments:
                    if segment.has_forces:
                        any_trial_has_dynamics = True
                        break
            if any_trial_has_dynamics:
                nimble.biomechanics.OpenSimParser.replaceOsimInertia(
                    tmpdirname + 'optimized_scale_and_markers.osim',
                    skel,
                    output_osim_path)
            else:
                shutil.copyfile(tmpdirname + 'optimized_scale_and_markers.osim',
                                output_osim_path)

    def write_opensim_results(self,
                              results_path: str,
                              data_folder_path: str):
        if not results_path.endswith('/'):
            results_path += '/'
        if not data_folder_path.endswith('/'):
            data_folder_path += '/'

        print('Writing the OpenSim result files...', flush=True)

        # 9.1. Create result directories.
        if not os.path.exists(results_path):
            os.mkdir(results_path)
        if not os.path.exists(results_path + 'IK'):
            os.mkdir(results_path + 'IK')
        if not os.path.exists(results_path + 'ID'):
            os.mkdir(results_path + 'ID')
        if not os.path.exists(results_path + 'C3D'):
            os.mkdir(results_path + 'C3D')
        if not os.path.exists(results_path + 'Models'):
            os.mkdir(results_path + 'Models')
        if self.exportMJCF and not os.path.exists(results_path + 'MuJoCo'):
            os.mkdir(results_path + 'MuJoCo')
        if self.exportSDF and not os.path.exists(results_path + 'SDF'):
            os.mkdir(results_path + 'SDF')
        if not os.path.exists(results_path + 'MarkerData'):
            os.mkdir(results_path + 'MarkerData')
        if os.path.exists(self.subject_path + 'unscaled_generic.osim'):
            shutil.copyfile(self.subject_path + 'unscaled_generic.osim', results_path +
                            'Models/unscaled_generic.osim')

        osim_path: str = 'Models/' + KINEMATIC_OSIM_NAME

        # Create the kinematics model file
        if self.kinematics_skeleton is not None:
            osim_path = 'Models/' + KINEMATIC_OSIM_NAME
            self.scale_osim(
                self.subject_path + 'unscaled_generic.osim',
                results_path + osim_path,
                self.kinematics_skeleton,
                self.kinematics_markers)

        # Create the dynamics model file
        if self.dynamics_skeleton is not None:
            osim_path = 'Models/' + DYNAMICS_OSIM_NAME
            self.scale_osim(
                self.subject_path + 'unscaled_generic.osim',
                results_path + osim_path,
                self.dynamics_skeleton,
                self.dynamics_markers)

        # Copy over the manually scaled model file, if it exists.
        if os.path.exists(self.subject_path + 'manually_scaled.osim'):
            shutil.copyfile(self.subject_path + 'manually_scaled.osim', results_path + 'Models/manually_scaled.osim')

        # Copy over the geometry files, so the model can be loaded directly in OpenSim without chasing down
        # Geometry files somewhere else.
        shutil.copytree(data_folder_path + 'OriginalGeometry', results_path + 'Models/Geometry')

        marker_names: List[str] = []
        for k in self.kinematics_markers:
            marker_names.append(k)

        # 9.9. Write the results to disk.
        for trial in self.trials:
            print('Writing OpenSim output for trial '+trial.trial_name, flush=True)

            # Write out the original C3D file, if present
            print('Copying original C3D file for trial '+trial.trial_name+'...', flush=True)
            c3d_fpath = f'{results_path}C3D/{trial.trial_name}.c3d'
            if trial.c3d_file is not None:
                shutil.copyfile(trial.trial_path + 'markers.c3d', c3d_fpath)
            print('Copied', flush=True)

            # Write out all the data from the trial segments
            for i in range(len(trial.segments)):
                print('Writing OpenSim output for trial ' + trial.trial_name + ' segment ' + str(i) + ' of ' + str(len(trial.segments)), flush=True)
                segment = trial.segments[i]
                segment_name = trial.trial_name + '_segment_' + str(i)
                # Write out the IK for the manually scaled skeleton, if appropriate
                if segment.manually_scaled_ik_poses is not None and self.goldOsim is not None:
                    nimble.biomechanics.OpenSimParser.saveMot(
                        self.goldOsim.skeleton,
                        results_path + 'IK/' + segment_name + '_manual_ik.mot',
                        segment.timestamps,
                        segment.manually_scaled_ik_poses)
                    nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                        trial.trial_name,
                        marker_names,
                        '../Models/manually_scaled.osim',
                        f'../MarkerData/{segment_name}.trc',
                        f'{segment_name}_ik_on_manual_scaling_by_opensim.mot',
                        f'{results_path}IK/{segment_name}_ik_on_manually_scaled_setup.xml')

                # Write out the result data files.
                result_ik: Optional[nimble.biomechanics.IKErrorReport] = None
                if segment.dynamics_status == ProcessingStatus.FINISHED:
                    assert(segment.dynamics_poses is not None)
                    assert(segment.dynamics_taus is not None)
                    # Write out the inverse kinematics results,
                    ik_fpath = f'{results_path}IK/{segment_name}_ik.mot'
                    print(f'Writing OpenSim {ik_fpath} file, shape={str(segment.dynamics_poses.shape)}', flush=True)
                    nimble.biomechanics.OpenSimParser.saveMot(self.skeleton, ik_fpath, segment.timestamps, segment.dynamics_poses)
                    # Write the inverse dynamics results.
                    id_fpath = f'{results_path}ID/{segment_name}_id.sto'
                    nimble.biomechanics.OpenSimParser.saveIDMot(self.skeleton, id_fpath, segment.timestamps, segment.dynamics_taus)
                    # Create the IK error report for this segment
                    result_ik = nimble.biomechanics.IKErrorReport(
                        self.skeleton, self.fitMarkers, segment.dynamics_poses, segment.marker_observations)
                    # Write out the OpenSim ID files:
                    grf_fpath = f'{results_path}ID/{segment_name}_grf.mot'
                    grf_raw_fpath = f'{results_path}ID/{segment_name}_grf_raw.mot'

                    nimble.biomechanics.OpenSimParser.saveProcessedGRFMot(
                        grf_fpath,
                        segment.timestamps,
                        [self.skeleton.getBodyNode(name) for name in self.footBodyNames],
                        segment.ground_height,
                        segment.foot_body_wrenches)
                    nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsProcessedForcesXMLFile(
                        segment_name,
                        [self.skeleton.getBodyNode(name) for name in self.footBodyNames],
                        segment_name + '_grf.mot',
                        results_path + 'ID/' + segment_name + '_external_forces.xml')
                    nimble.biomechanics.OpenSimParser.saveRawGRFMot(grf_fpath, segment.timestamps, segment.force_plates)
                    nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsRawForcesXMLFile(
                        segment_name,
                        self.skeleton,
                        segment.dynamics_poses,
                        segment.force_plates,
                        segment_name + '_grf.mot',
                        results_path + 'ID/' + segment_name + '_external_forces.xml')
                    nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                        segment_name,
                        '../Models/' + DYNAMICS_OSIM_NAME,
                        '../IK/' + segment_name + '_ik.mot',
                        segment_name + '_external_forces.xml',
                        segment_name + '_id.sto',
                        segment_name + '_id_body_forces.sto',
                        results_path + 'ID/' + segment_name + '_id_setup.xml',
                        min(segment.timestamps), max(segment.timestamps))

                elif segment.kinematics_status == ProcessingStatus.FINISHED:
                    assert(segment.kinematics_poses is not None)
                    # Write out the inverse kinematics results,
                    ik_fpath = f'{results_path}IK/{segment_name}_ik.mot'
                    print(f'Writing OpenSim {ik_fpath} file, shape={str(segment.kinematics_poses.shape)}', flush=True)
                    nimble.biomechanics.OpenSimParser.saveMot(self.skeleton, ik_fpath, segment.timestamps, segment.kinematics_poses)
                    # Create the IK error report for this segment
                    result_ik = nimble.biomechanics.IKErrorReport(
                        self.skeleton, self.fitMarkers, segment.kinematics_poses, segment.marker_observations)

                if result_ik is not None:
                    # Save OpenSim setup files to make it easy to (re)run IK on the results in OpenSim
                    nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                        segment_name,
                        marker_names,
                        f'../{osim_path}',
                        f'../MarkerData/{segment_name}.trc',
                        f'{segment_name}_ik_by_opensim.mot',
                        f'{results_path}IK/{segment_name}_ik_setup.xml')

                if segment.marker_observations is not None:
                    # Write out the marker trajectories.
                    markers_fpath = f'{results_path}MarkerData/{segment_name}.trc'
                    print('Saving TRC for trial ' + trial.trial_name + ' segment ' + str(i), flush=True)
                    print(len(segment.marker_observations))
                    print(len(segment.timestamps))
                    nimble.biomechanics.OpenSimParser.saveTRC(
                        markers_fpath, segment.timestamps, segment.marker_observations)
                    print('Saved', flush=True)

                # Write out the marker errors.
                if result_ik is not None:
                    marker_errors_fpath = f'{results_path}IK/{segment_name}_marker_errors.csv'
                    result_ik.saveCSVMarkerErrorReport(marker_errors_fpath)
        print('Zipping up OpenSim files...', flush=True)
        shutil.make_archive(results_path, 'zip', results_path, results_path)
        print('Finished outputting OpenSim files.', flush=True)

    def write_b3d_file(self, file_path: str, osim_results_folder: str, href: str):
        if not osim_results_folder.endswith('/'):
            osim_results_folder += '/'

        # 1. Create the SubjectOnDisk Header object, which will be used to write out the header of the B3D file.
        subject_header: nimble.biomechanics.SubjectOnDiskHeader = nimble.biomechanics.SubjectOnDiskHeader()

        kinematic_pass = subject_header.addProcessingPass()
        kinematic_pass.setProcessingPassType(nimble.biomechanics.ProcessingPassType.KINEMATICS)
        if os.path.exists(osim_results_folder + 'Models/' + KINEMATIC_OSIM_NAME):
            with open(osim_results_folder + 'Models/' + KINEMATIC_OSIM_NAME, 'r') as f:
                kinematic_pass.setOpenSimFileText(f.read())
        else:
            print('WARNING: No '+ KINEMATIC_OSIM_NAME + ' file found in ' + osim_results_folder + 'Models/' + KINEMATIC_OSIM_NAME + '. '
                  'This is probably because the kinematics pass did not succeed on a single trial. '
                  'Leaving that model empty in the B3D file.', flush=True)

        lowpass_pass = subject_header.addProcessingPass()
        lowpass_pass.setProcessingPassType(nimble.biomechanics.ProcessingPassType.LOW_PASS_FILTER)

        if not self.disableDynamics:
            dynamics_pass = subject_header.addProcessingPass()
            dynamics_pass.setProcessingPassType(nimble.biomechanics.ProcessingPassType.DYNAMICS)
            if os.path.exists(osim_results_folder + 'Models/' + DYNAMICS_OSIM_NAME):
                with open(osim_results_folder + 'Models/' + DYNAMICS_OSIM_NAME, 'r') as f:
                    dynamics_pass.setOpenSimFileText(f.read())
            else:
                print('WARNING: No ' + DYNAMICS_OSIM_NAME +' file found in ' + osim_results_folder + 'Models/' + DYNAMICS_OSIM_NAME + '. '
                      'This is probably because the dynamics pass did not succeed on a single trial. '
                      'Leaving that model empty in the B3D file.', flush=True)

        # header.setNumDofs(dofs);
        subject_header.setNumDofs(self.skeleton.getNumDofs())
        # header.setGroundForceBodies(groundForceBodies);
        subject_header.setGroundForceBodies(self.footBodyNames)
        # header.setHref(originalHref);
        subject_header.setHref(href)
        # header.setNotes(originalNotes);
        subject_header.setNotes("Generated by AddBiomechanics")
        # header.setBiologicalSex(biologicalSex);
        subject_header.setBiologicalSex(self.biologicalSex)
        # header.setHeightM(heightM);
        subject_header.setHeightM(self.heightM)
        # header.setMassKg(massKg);
        subject_header.setMassKg(self.massKg)
        # header.setAgeYears(age);
        subject_header.setAgeYears(self.ageYears)
        # header.setSubjectTags(subjectTags);
        subject_header.setSubjectTags(self.subjectTags)

        # 2. Create the trials
        for trial in self.trials:
            # Write out all the data from the trial segments
            for i in range(len(trial.segments)):
                segment = trial.segments[i]

                trial_data = subject_header.addTrial()
                trial_data.setTimestep(trial.timestep)
                trial_data.setOriginalTrialName(trial.trial_name)
                trial_data.setName(trial.trial_name + '_segment_' + str(i))
                trial_data.setSplitIndex(i)
                trial_data.setMarkerNamesGuessed(False)
                trial_data.setMarkerObservations(segment.marker_observations)
                # TODO: Acc, Gyro, EMG, Exo
                trial_data.setMissingGRFReason(segment.missing_grf_reason)
                trial_data.setTrialTags(trial.tags)
                trial_data.setForcePlates(trial.force_plates)

                # 3. Create the passes, based on what we saw in the trials
                if segment.kinematics_status == ProcessingStatus.FINISHED:
                    trial_kinematic_data = trial_data.addPass()
                    trial_kinematic_data.setType(nimble.biomechanics.ProcessingPassType.KINEMATICS)
                    trial_kinematic_data.setDofPositionsObserved([True for _ in range(self.skeleton.getNumDofs())])
                    trial_kinematic_data.setDofVelocitiesFiniteDifferenced([True for _ in range(self.skeleton.getNumDofs())])
                    trial_kinematic_data.setDofAccelerationFiniteDifferenced([True for _ in range(self.skeleton.getNumDofs())])
                    trial_kinematic_data.setMarkerRMS(segment.kinematics_ik_error_report.rootMeanSquaredError)
                    trial_kinematic_data.setMarkerMax(segment.kinematics_ik_error_report.maxError)
                    trial_kinematic_data.computeValuesFromForcePlates(self.kinematics_skeleton, trial.timestep, segment.kinematics_poses, self.footBodyNames, segment.force_plates)
                    trial_kinematic_data.setForcePlateCutoffs(segment.parent.force_plate_thresholds)
                else:
                    print('Not including trial ' + trial.trial_name + ' segment ' + str(i) + ' in B3D file, because kinematics failed.', flush=True)
                    print('  Kinematics Status: ' + segment.kinematics_status.name, flush=True)

                if segment.lowpass_status == ProcessingStatus.FINISHED:
                    trial_lowpass_data = trial_data.addPass()
                    trial_lowpass_data.setType(nimble.biomechanics.ProcessingPassType.LOW_PASS_FILTER)
                    trial_lowpass_data.setDofPositionsObserved([True for _ in range(self.skeleton.getNumDofs())])
                    trial_lowpass_data.setDofVelocitiesFiniteDifferenced([True for _ in range(self.skeleton.getNumDofs())])
                    trial_lowpass_data.setDofAccelerationFiniteDifferenced([True for _ in range(self.skeleton.getNumDofs())])
                    trial_lowpass_data.setMarkerRMS(segment.lowpass_ik_error_report.rootMeanSquaredError)
                    trial_lowpass_data.setMarkerMax(segment.lowpass_ik_error_report.maxError)
                    trial_lowpass_data.computeValuesFromForcePlates(self.kinematics_skeleton, trial.timestep, segment.lowpass_poses, self.footBodyNames, segment.lowpass_force_plates)
                    trial_lowpass_data.setForcePlateCutoffs(segment.parent.force_plate_thresholds)

                if segment.dynamics_status == ProcessingStatus.FINISHED:
                    trial_dynamics_data = trial_data.addPass()
                    trial_dynamics_data.setType(nimble.biomechanics.ProcessingPassType.DYNAMICS)
                    trial_dynamics_data.setDofPositionsObserved([True for _ in range(self.skeleton.getNumDofs())])
                    trial_dynamics_data.setDofVelocitiesFiniteDifferenced([True for _ in range(self.skeleton.getNumDofs())])
                    trial_dynamics_data.setDofAccelerationFiniteDifferenced([True for _ in range(self.skeleton.getNumDofs())])
                    trial_dynamics_data.setMarkerRMS(segment.dynamics_ik_error_report.rootMeanSquaredError)
                    trial_dynamics_data.setMarkerMax(segment.dynamics_ik_error_report.maxError)
                    trial_dynamics_data.computeValuesFromForcePlates(self.dynamics_skeleton, trial.timestep, segment.dynamics_poses, self.footBodyNames, segment.lowpass_force_plates if segment.lowpass_status == ProcessingStatus.FINISHED else segment.force_plates)
                    trial_dynamics_data.setForcePlateCutoffs(segment.parent.force_plate_thresholds)
                else:
                    print('Not including trial ' + trial.trial_name + ' segment ' + str(i) + ' in B3D file, because dynamics failed.', flush=True)
                    print('  Dynamics Status: ' + segment.dynamics_status.name, flush=True)

        # 4. Actually write the output file
        nimble.biomechanics.SubjectOnDisk.writeB3D(file_path, subject_header)

        # 5. Read the file back in, and print out some summary stats
        print('B3D Summary Statistics:', flush=True)
        read_back: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(file_path)
        print('  Num Trials: ' + str(read_back.getNumTrials()), flush=True)
        print('  Num Processing Passes: ' + str(read_back.getNumProcessingPasses()), flush=True)
        print('  Num Dofs: ' + str(read_back.getNumDofs()), flush=True)
        for t in range(read_back.getNumTrials()):
            print('  Trial '+str(t)+':', flush=True)
            print('    Name: ' + read_back.getTrialName(t), flush=True)
            for p in range(read_back.getTrialNumProcessingPasses(t)):
                print('    Processing pass '+str(p)+':', flush=True)
                print('      Marker RMS: ' + str(np.mean(read_back.getTrialMarkerRMSs(t, p))), flush=True)
                print('      Marker Max: ' + str(np.mean(read_back.getTrialMarkerMaxs(t, p))), flush=True)
                print('      Linear Residual: ' + str(np.mean(read_back.getTrialLinearResidualNorms(t, p))), flush=True)
                print('      Angular Residual: ' + str(np.mean(read_back.getTrialAngularResidualNorms(t, p))), flush=True)

    def write_web_results(self, results_path: str):
        if not results_path.endswith('/'):
            results_path += '/'
        if not os.path.exists(results_path):
            os.mkdir(results_path)

        overall_results = self.get_overall_results_json()
        with open(results_path + '_results.json', 'w') as f:
            json.dump(overall_results, f, indent=4)
            print('Wrote JSON results to ' + results_path + '_results.json', flush=True)

        trials_folder_path = results_path + 'trials/'
        if not os.path.exists(trials_folder_path):
            os.mkdir(trials_folder_path)

        for trial in self.trials:
            trial_path = results_path + 'trials/' + trial.trial_name + '/'
            if not os.path.exists(trial_path):
                os.mkdir(trial_path)

            for i in range(len(trial.segments)):
                segment = trial.segments[i]
                segment_path = trial_path + 'segment_' + str(i + 1) + '/'
                if not os.path.exists(segment_path):
                    os.mkdir(segment_path)
                # Write out the result summary JSON
                print('Writing JSON result to ' + segment_path + '_results.json', flush=True)
                segment_json = segment.get_segment_results_json()
                with open(segment_path + '_results.json', 'w') as f:
                    json.dump(segment_json, f, indent=4)
                # Write out the animation preview binary
                segment.save_segment_to_gui(segment_path + 'preview.bin',
                                            self.skeleton,
                                            self.fitMarkers,
                                            self.goldOsim)
                # Write out the data CSV for the plotting software to synchronize on the frontend
                segment.save_segment_csv(segment_path + 'data.csv', self.skeleton)