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


# Global paths to the geometry and data folders.
GEOMETRY_FOLDER_PATH = absPath('../../Geometry')
DATA_FOLDER_PATH = absPath('../../../data')
TEMPLATES_PATH = absPath('../../templates')


class Subject:
    def __init__(self):
        # 0. Initialize the engine.
        # -------------------------
        self.subject_path = ''
        self.processingResult: Dict[str, Any] = {}

        # 0.2. Subject pipeline parameters.
        self.massKg = 68.0
        self.heightM = 1.6
        self.sex = 'unknown'
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

        # 0.3. Shared data structures.
        self.trials: List[Trial] = []
        self.skeleton: nimble.dynamics.Skeleton = None
        self.markerSet: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
        self.customOsim: nimble.biomechanics.OpenSimFile = None
        self.goldOsim: nimble.biomechanics.OpenSimFile = None
        self.simplified: nimble.dynamics.Skeleton = None
        self.finalSkeleton: nimble.dynamics.Skeleton = None
        self.fitMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
        self.finalMarkers: Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]] = {}
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
            self.ageYears = float(subject_json['ageYears'])

        if 'subjectTags' in subject_json:
            self.subjectTags = subject_json['subjectTags']

        if 'sex' in subject_json:
            self.sex = subject_json['sex']

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
                        trial_segment.marker_observations, trial.timestep)
                    trial_segment.marker_observations = trial_error_report.markerObservationsAttemptedFixed
                    trial_segment.marker_error_report = trial_error_report
                    # Set an error if there are any NaNs in the marker data
                    for t in range(len(trial_segment.marker_observations)):
                        for marker in trial_segment.marker_observations[t]:
                            if np.any(np.isnan(trial_segment.marker_observations[t][marker])):
                                trial_segment.has_error = True
                                trial_segment.error_msg = 'Trial had NaNs in the data after running MarkerFixer.'
                                break
                            if np.any(np.abs(trial_segment.marker_observations[t][marker]) > 1e+6):
                                trial_segment.has_error = True
                                trial_segment.error_msg = ('Trial had suspiciously large marker values after running '
                                                           'MarkerFixer.')
                                break

        print('All trial markers have been cleaned up!', flush=True)

        # 2.2. Create an anthropometric prior.
        anthropometrics: nimble.biomechanics.Anthropometrics = nimble.biomechanics.Anthropometrics.loadFromFile(
            data_folder_path + '/ANSUR_metrics.xml')
        cols = anthropometrics.getMetricNames()
        cols.append('weightkg')
        if self.sex == 'male':
            gauss: nimble.math.MultivariateGaussian = nimble.math.MultivariateGaussian.loadFromCSV(
                data_folder_path + '/ANSUR_II_MALE_Public.csv',
                cols,
                0.001)  # mm -> m
        elif self.sex == 'female':
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

        # 2.3. Run the kinematics pipeline.
        trial_segments: List[TrialSegment] = []
        for trial in self.trials:
            if not trial.error:
                for segment in trial.segments:
                    if segment.has_markers and not segment.has_error:
                        trial_segments.append(segment)
                        segment.kinematics_status = ProcessingStatus.IN_PROGRESS
                    else:
                        segment.kinematics_status = ProcessingStatus.ERROR
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

        # 2.5. Check for any flipped markers, now that we've done a first pass
        any_swapped = False
        for i in range(len(trial_segments)):
            if marker_fitter.checkForFlippedMarkers(trial_segments[i].marker_observations, marker_fitter_results[i],
                                                    trial_segments[i].marker_error_report):
                any_swapped = True
                trial_segments[i].marker_observations = trial_segments[i].marker_error_report.markerObservationsAttemptedFixed

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
        self.finalSkeleton = self.skeleton
        self.finalMarkers = self.fitMarkers
        for i in range(len(trial_segments)):
            trial_segments[i].kinematics_status = ProcessingStatus.FINISHED
            trial_segments[i].kinematics_poses = marker_fitter_results[i].poses
            trial_segments[i].marker_fitter_result = marker_fitter_results[i]
            trial_segments[i].kinematics_ik_error_report = nimble.biomechanics.IKErrorReport(
                self.finalSkeleton,
                self.finalMarkers,
                trial_segments[i].kinematics_poses,
                trial_segments[i].marker_observations)

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
        if len(trial_segments) == 0:
            print('No trial segments to fit dynamics on. Skipping dynamics fitting...', flush=True)
            return

        # 8. Run dynamics fitting.
        # ------------------------
        print('Fitting dynamics on ' + str(len(trial_segments)) + ' trial segments...', flush=True)

        # 8.1. Construct a DynamicsFitter object.
        foot_bodies = []
        for name in self.footBodyNames:
            foot = self.finalSkeleton.getBodyNode(name)
            if foot is None:
                raise RuntimeError(f'Foot "{str(name)}" not found in skeleton! Cannot run dynamics fitting.')
            foot_bodies.append(self.finalSkeleton.getBodyNode(name))
        print('Using feet: ' + str(self.footBodyNames), flush=True)

        self.finalSkeleton.setGravity([0.0, -9.81, 0.0])
        dynamics_fitter = nimble.biomechanics.DynamicsFitter(
            self.finalSkeleton, foot_bodies, self.customOsim.trackingMarkers)
        print('Created DynamicsFitter', flush=True)

        # Sanity check the force plate data sizes match the kinematics data sizes
        for trial_segment in trial_segments:
            for force_plate in trial_segment.force_plates:
                print('poses cols: '+str(trial_segment.kinematics_poses.shape[1]))
                print('force len: '+str(len(force_plate.forces)))
                assert(trial_segment.kinematics_poses.shape[1] == len(force_plate.forces))
                assert(len(force_plate.forces) == len(force_plate.centersOfPressure))
                assert(len(force_plate.forces) == len(force_plate.moments))

        # 8.2. Initialize the dynamics fitting problem.
        dynamics_init: nimble.biomechanics.DynamicsInitialization = \
            nimble.biomechanics.DynamicsFitter.createInitialization(
                self.finalSkeleton,
                [trial.marker_fitter_result for trial in trial_segments],
                self.customOsim.trackingMarkers,
                foot_bodies,
                [trial.force_plates for trial in trial_segments],
                [int(1.0 / trial.parent.timestep) for trial in trial_segments],
                [trial.marker_observations for trial in trial_segments])
        print('Created DynamicsInitialization', flush=True)

        dynamics_fitter.estimateFootGroundContacts(dynamics_init,
                                                   ignoreFootNotOverForcePlate=self.ignoreFootNotOverForcePlate)
        print("Initial mass: " +
              str(self.finalSkeleton.getMass()) + " kg", flush=True)
        print("What we'd expect average ~GRF to be (Mass * 9.8): " +
              str(self.finalSkeleton.getMass() * 9.8) + " N", flush=True)
        second_pair = dynamics_fitter.computeAverageRealForce(dynamics_init)
        print("Avg Force: " + str(second_pair[0]) + " N", flush=True)
        print("Avg Torque: " + str(second_pair[1]) + " Nm", flush=True)

        dynamics_fitter.addJointBoundSlack(self.finalSkeleton, 0.1)

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
            detectUnmeasuredTorque=detect_unmeasured_torque
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
                    dynamics_fitter.runIPOPTOptimization(
                        dynamics_init,
                        nimble.biomechanics.DynamicsFitProblemConfig(
                            self.finalSkeleton)
                        .setDefaults(True)
                        .setOnlyOneTrial(segment)
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
        dynamics_fitter.applyInitToSkeleton(self.finalSkeleton, dynamics_init)
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

        # 8.6. Store the dynamics fitting results in the shared data structures.
        for i in range(len(trial_segments)):
            trial_segments[i].dynamics_taus = dynamics_fitter.computeInverseDynamics(dynamics_init, i)
            pair = dynamics_fitter.computeAverageTrialResidualForce(dynamics_init, i)
            trial_segments[i].linear_residuals = pair[0]
            trial_segments[i].angular_residuals = pair[1]
            trial_segments[i].ground_height = dynamics_init.groundHeight[i]
            trial_segments[i].foot_body_wrenches = dynamics_init.grfTrials[i]

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
                self.finalSkeleton,
                self.finalMarkers,
                trial_segments[i].dynamics_poses,
                trial_segments[i].marker_observations)

        self.finalMarkers = dynamics_init.updatedMarkerMap

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

    def write_opensim_results(self, results_path: str, data_folder_path: str):
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

        # 9.2. Adjust marker locations.
        marker_names: List[str] = []
        if self.finalSkeleton is not None:
            print('Adjusting marker locations on scaled OpenSim file', flush=True)
            body_scales_map: Dict[str, np.ndarray] = {}
            for i in range(self.finalSkeleton.getNumBodyNodes()):
                body_node: nimble.dynamics.BodyNode = self.finalSkeleton.getBodyNode(i)
                # Now that we adjust the markers BEFORE we rescale the body, we don't want to rescale the marker locations
                # at all.
                body_scales_map[body_node.getName()] = np.ones(3)
            marker_offsets_map: Dict[str, Tuple[str, np.ndarray]] = {}
            for k in self.finalMarkers:
                v = self.finalMarkers[k]
                marker_offsets_map[k] = (v[0].getName(), v[1])
                marker_names.append(k)
            nimble.biomechanics.OpenSimParser.moveOsimMarkers(
                data_folder_path + 'unscaled_generic.osim',
                body_scales_map,
                marker_offsets_map,
                results_path + 'Models/unscaled_but_with_optimized_markers.osim')

            # 9.3. Write the XML instructions for the OpenSim scaling tool
            nimble.biomechanics.OpenSimParser.saveOsimScalingXMLFile(
                'optimized_scale_and_markers',
                self.finalSkeleton,
                self.massKg,
                self.heightM,
                'Models/unscaled_but_with_optimized_markers.osim',
                'Unassigned',
                'Models/optimized_scale_and_markers.osim',
                results_path + 'Models/rescaling_setup.xml')

            # 9.4. Call the OpenSim scaling tool
            command = f'cd {results_path} && opensim-cmd run-tool {results_path}Models/rescaling_setup.xml'
            print('Scaling OpenSim files: ' + command, flush=True)
            with subprocess.Popen(command, shell=True, stdout=subprocess.PIPE) as p:
                for line in iter(p.stdout.readline, b''):
                    print(line.decode(), end='', flush=True)
                p.wait()

            # Delete the OpenSim log from running the scale tool
            if os.path.exists(results_path + 'opensim.log'):
                os.remove(results_path + 'opensim.log')

            # 9.5. Overwrite the inertia properties of the resulting OpenSim skeleton file
            any_trial_has_dynamics = False
            for trial in self.trials:
                for segment in trial.segments:
                    if segment.has_forces:
                        any_trial_has_dynamics = True
                        break
            if any_trial_has_dynamics:
                nimble.biomechanics.OpenSimParser.replaceOsimInertia(
                    results_path + 'Models/optimized_scale_and_markers.osim',
                    self.finalSkeleton,
                    results_path + 'Models/final.osim')
            else:
                shutil.copyfile(results_path + 'Models/optimized_scale_and_markers.osim',
                                results_path + 'Models/final.osim')

        # Copy over the manually scaled model file, if it exists.
        if os.path.exists(self.subject_path + 'manually_scaled.osim'):
            shutil.copyfile(self.subject_path + 'manually_scaled.osim', results_path + 'Models/manually_scaled.osim')

        # Copy over the geometry files, so the model can be loaded directly in OpenSim without chasing down
        # Geometry files somewhere else.
        shutil.copytree(data_folder_path + 'Geometry', results_path + 'Models/Geometry')

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
                    nimble.biomechanics.OpenSimParser.saveMot(self.finalSkeleton, ik_fpath, segment.timestamps, segment.dynamics_poses)
                    # Write the inverse dynamics results.
                    id_fpath = f'{results_path}ID/{segment_name}_id.sto'
                    nimble.biomechanics.OpenSimParser.saveIDMot(self.finalSkeleton, id_fpath, segment.timestamps, segment.dynamics_taus)
                    # Create the IK error report for this segment
                    result_ik = nimble.biomechanics.IKErrorReport(
                        self.finalSkeleton, self.fitMarkers, segment.dynamics_poses, segment.marker_observations)
                    # Write out the OpenSim ID files:
                    grf_fpath = f'{results_path}ID/{segment_name}_grf.mot'
                    grf_raw_fpath = f'{results_path}ID/{segment_name}_grf_raw.mot'

                    nimble.biomechanics.OpenSimParser.saveProcessedGRFMot(
                        grf_fpath,
                        segment.timestamps,
                        [self.finalSkeleton.getBodyNode(name) for name in self.footBodyNames],
                        segment.ground_height,
                        segment.foot_body_wrenches)
                    nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsProcessedForcesXMLFile(
                        segment_name,
                        [self.finalSkeleton.getBodyNode(name) for name in self.footBodyNames],
                        segment_name + '_grf.mot',
                        results_path + 'ID/' + segment_name + '_external_forces.xml')
                    nimble.biomechanics.OpenSimParser.saveRawGRFMot(grf_fpath, segment.timestamps, segment.force_plates)
                    nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsRawForcesXMLFile(
                        segment_name,
                        self.finalSkeleton,
                        segment.dynamics_poses,
                        segment.force_plates,
                        segment_name + '_grf.mot',
                        results_path + 'ID/' + segment_name + '_external_forces.xml')
                    nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                        segment_name,
                        '../Models/final.osim',
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
                    nimble.biomechanics.OpenSimParser.saveMot(self.finalSkeleton, ik_fpath, segment.timestamps, segment.kinematics_poses)
                    # Create the IK error report for this segment
                    result_ik = nimble.biomechanics.IKErrorReport(
                        self.finalSkeleton, self.fitMarkers, segment.kinematics_poses, segment.marker_observations)

                if result_ik is not None:
                    # Save OpenSim setup files to make it easy to (re)run IK on the results in OpenSim
                    nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                        segment_name,
                        marker_names,
                        '../Models/optimized_scale_and_markers.osim',
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

    def write_bin_file(self, file_path: str):
        pass

    def write_web_results(self, results_path: str):
        if not results_path.endswith('/'):
            results_path += '/'
            if not os.path.exists(results_path):
                os.mkdir(results_path)

            overall_results = self.get_overall_results_json()
            with open(results_path + '_results.json', 'w') as f:
                json.dump(overall_results, f, indent=4)

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
                                                self.finalSkeleton,
                                                self.fitMarkers,
                                                self.goldOsim)
                    # Write out the data CSV for the plotting software to synchronize on the frontend
                    segment.save_segment_csv(segment_path + 'data.csv', self.finalSkeleton)