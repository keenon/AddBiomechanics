from src.kinematics_pass.trial import TrialSegment, Trial, ProcessingStatus
from typing import List, Dict, Tuple, Any, Optional
import json
import nimblephysics as nimble
from nimblephysics import absPath
from src.exceptions import LoadingError, TrialPreprocessingError, MarkerFitterError, DynamicsFitterError, WriteError
import numpy as np
import os
import shutil
import subprocess
import textwrap
import tempfile
import os
from src.utilities.scale_opensim_model import scale_opensim_model


# Global paths to the geometry and data folders.
GEOMETRY_FOLDER_PATH = absPath('../../Geometry')
DATA_FOLDER_PATH = absPath('../../../data')
TEMPLATES_PATH = absPath('../../templates')


# This metaclass wraps all methods in the Subject class with a try-except block, except for the __init__ method.
class ExceptionHandlingMeta(type):
    # Only the methods in this map will be wrapped with a try-except block.
    EXCEPTION_MAP = {
        'load_folder': LoadingError,
        'segment_trials': TrialPreprocessingError,
        'run_kinematics_pass': MarkerFitterError,
        'write_opensim_results': WriteError,
        'write_b3d_file': WriteError,
        'write_web_results': WriteError,
    }

    def __new__(cls, name, bases, attrs):
        for attr_name, attr_value in attrs.items():
            if attr_name not in cls.EXCEPTION_MAP:
                continue
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
                exc_type = ExceptionHandlingMeta.EXCEPTION_MAP.get(method.__name__, Exception)
                raise exc_type(msg)

        return wrapper


class Subject(metaclass=ExceptionHandlingMeta):
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
        self.regularizeJointAcc = 1e-6
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
        self.skippedDynamicsReason = None
        self.runMoco = False
        self.skippedMocoReason = None
        self.lowpass_hz = 30
        # self.lowpass_filter_type: str = 'lowpass'
        self.lowpass_filter_type: str = 'acc-min'

        # self.ablation_grf_test = False
        # self.ablation_no_initialization = False

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
            trial: Trial = Trial.load_trial(
                trial_name,
                trials_folder_path + trial_name + '/',
                trial_index=len(self.trials)
            )
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
                # Ablation #1: Remove the right force plate
                # trial.zero_force_plate(0)
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

    def run_kinematics_pass(self, data_folder_path: str):
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
                    trial_segment.error = True
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
                                trial_segment.error = True
                                trial_segment.error_msg = 'Trial had NaNs in the data after running MarkerFixer.'
                                print(trial_segment.error_msg, flush=True)
                                break
                            if np.any(np.abs(trial_segment.marker_observations[t][marker]) > 1e+6):
                                trial_segment.error = True
                                trial_segment.error_msg = ('Trial had suspiciously large marker values after running '
                                                           'MarkerFixer.')
                                print(trial_segment.error_msg, flush=True)
                                break
                        if trial_segment.error:
                            break

        print('All trial markers have been cleaned up!', flush=True)

        trial_segments: List[TrialSegment] = []
        for trial in self.trials:
            if not trial.error:
                for segment in trial.segments:
                    if segment.has_markers and not segment.error:
                        trial_segments.append(segment)
                        segment.kinematics_status = ProcessingStatus.IN_PROGRESS
                    else:
                        segment.kinematics_status = ProcessingStatus.ERROR
                        if segment.error:
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
        any_swapped = False
        for i in range(len(trial_segments)):
            if marker_fitter.checkForFlippedMarkers(trial_segments[i].marker_observations, marker_fitter_results[i],
                                                    trial_segments[i].marker_error_report):
                any_swapped = True
                new_marker_observations: List[Dict[str, np.ndarray]] = []
                for t in range(trial_segments[i].marker_error_report.getNumTimesteps()):
                    new_marker_observations.append({})
                    for marker_name in trial_segments[i].marker_error_report.getMarkerNamesOnTimestep(t):
                        new_marker_observations[t][marker_name] = trial_segments[i].marker_error_report.getMarkerPositionOnTimestep(t, marker_name)
                trial_segments[i].marker_observations = new_marker_observations

        if any_swapped:
            print("******** Unfortunately, it looks like some markers were swapped in the uploaded data, "
                  "so we have to run the whole pipeline again with unswapped markers. ********",
                  flush=True)
            marker_fitter_results = marker_fitter.runMultiTrialKinematicsPipeline(
                [trial.marker_observations for trial in trial_segments],
                nimble.biomechanics.InitialMarkerFitParams()
                .setMaxTrialsToUseForMultiTrialScaling(5)
                .setMaxTimestepsToUseForMultiTrialScaling(4000),
                150)

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
                trial_segments[i].kinematics_poses = np.copy(marker_fitter_results[i].poses)
                trial_segments[i].marker_fitter_result = marker_fitter_results[i]
                trial_segments[i].kinematics_ik_error_report = nimble.biomechanics.IKErrorReport(
                    self.kinematics_skeleton,
                    self.kinematics_markers,
                    trial_segments[i].kinematics_poses,
                    trial_segments[i].marker_observations)

    ###################################################################################################################
    # Writing out results
    ###################################################################################################################

    def create_subject_on_disk(self, href: str) -> nimble.biomechanics.SubjectOnDisk:
        # 1. Create the SubjectOnDisk Header object, which will be used to write out the header of the B3D file.
        subject_header: nimble.biomechanics.SubjectOnDiskHeader = nimble.biomechanics.SubjectOnDiskHeader()

        kinematic_pass = subject_header.addProcessingPass()
        kinematic_pass.setProcessingPassType(nimble.biomechanics.ProcessingPassType.KINEMATICS)

        with open(self.subject_path + 'unscaled_generic.osim', 'r') as f:
            original_file_text = '\n'.join(f.readlines())

        osim_file_xml = scale_opensim_model(
            original_file_text,
            self.kinematics_skeleton,
            self.massKg,
            self.heightM,
            self.kinematics_markers)
        kinematic_pass.setOpenSimFileText(osim_file_xml)

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
            print('Creating B3D output for trial ' + trial.trial_name, flush=True)
            for i in range(len(trial.segments)):
                # 3. Create the passes, based on what we saw in the trials
                segment = trial.segments[i]
                if segment.kinematics_status == ProcessingStatus.FINISHED:
                    print('Creating B3D output for trial ' + trial.trial_name + ' segment ' + str(i) + ' of ' + str(len(trial.segments)), flush=True)

                    trial_data = subject_header.addTrial()
                    trial_data.setTimestep(trial.timestep)
                    trial_data.setTrialLength(len(segment.marker_observations))
                    trial_data.setOriginalTrialName(trial.trial_name)
                    trial_data.setName(trial.trial_name + '_segment_' + str(i))
                    trial_data.setSplitIndex(i)
                    trial_data.setOriginalTrialStartFrame(segment.start)
                    trial_data.setOriginalTrialStartTime(segment.timestamps[0] if len(segment.timestamps) > 0 else 0)
                    trial_data.setOriginalTrialEndFrame(segment.end)
                    trial_data.setOriginalTrialEndTime(segment.timestamps[-1] if len(segment.timestamps) > 0 else 0)
                    trial_data.setMarkerNamesGuessed(False)
                    trial_data.setMarkerObservations(segment.marker_observations)
                    # TODO: Acc, Gyro, EMG, Exo
                    trial_data.setMissingGRFReason(segment.missing_grf_reason)
                    trial_data.setTrialTags(trial.tags)
                    trial_data.setForcePlates(segment.force_plates)

                    print('Kinematics succeeded for trial ' + trial.trial_name + ' segment ' + str(i) + '. Writing kinematics data to B3D file.', flush=True)
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

        return nimble.biomechanics.SubjectOnDisk(subject_header)