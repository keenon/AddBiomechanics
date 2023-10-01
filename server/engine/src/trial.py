import nimblephysics as nimble
from typing import List, Dict, Tuple, Any, Set, Optional
import numpy as np
import os
import enum
import json
from memory_utils import deep_copy_marker_observations


class ProcessingStatus(enum.Enum):
    NOT_STARTED = 0
    IN_PROGRESS = 1
    FINISHED = 2
    ERROR = 3


class Trial:
    def __init__(self):
        # Input data
        self.trial_path = ''
        self.trial_name = ''
        self.tags: List[str] = []
        self.marker_observations: List[Dict[str, np.ndarray]] = []
        self.force_plates: List[nimble.biomechanics.ForcePlate] = []
        self.timestamps: List[float] = []
        self.timestep: float = 0.01
        self.c3d_file: Optional[nimble.biomechanics.C3D] = None
        # This is optional input data, and can be used by users who have been doing their own manual scaling, but would
        # like to run comparison tests with AddBiomechanics.
        self.manually_scaled_ik: Optional[np.ndarray] = None
        # Error states
        self.error: bool = False
        self.error_loading_files: str = ''
        # Output data
        self.segments: List['TrialSegment'] = []

    @staticmethod
    def load_trial(trial_name: str,
                   trial_path: str,
                   manually_scaled_opensim: Optional[nimble.biomechanics.OpenSimFile] = None) -> 'Trial':
        """
        Load a trial from a folder. This assumes that the folder either contains `markers.c3d`,
        or `markers.trc` and (optionally) `grf.mot`.
        """
        if not trial_path.endswith('/'):
            trial_path += '/'
        c3d_file_path = trial_path + 'markers.c3d'
        trc_file_path = trial_path + 'markers.trc'
        json_file_path = trial_path + '_trial.json'
        gold_mot_file_path = trial_path + 'manual_ik.mot'
        trial = Trial()
        trial.trial_path = trial_path
        trial.trial_name = trial_name
        if os.path.exists(c3d_file_path):
            trial.c3d_file = nimble.biomechanics.C3DLoader.loadC3D(
                c3d_file_path)

            # Do a deep copy of the marker observations, to avoid potential memory issues on the PyBind interface
            file_marker_observations = trial.c3d_file.markerTimesteps
            trial.marker_observations = deep_copy_marker_observations(file_marker_observations)

            any_have_markers = False
            for markerTimestep in trial.marker_observations:
                if len(markerTimestep.keys()) > 0:
                    any_have_markers = True
                    break
            if not any_have_markers:
                trial.error = True
                trial.error_loading_files = (f'Trial {trial_name} has no markers on any timestep. Check that the C3D '
                                             f'file is not corrupted.')
            # nimble.biomechanics.C3DLoader.fixupMarkerFlips(trial.c3d_file)
            # TODO: autorotateC3D should be factored out into a separate function that can be called on both C3D
            #  and TRC data.
            # marker_fitter.autorotateC3D(trial.c3d_file)
            trial.force_plates = trial.c3d_file.forcePlates
            trial.timestamps = trial.c3d_file.timestamps
            if len(trial.timestamps) > 1:
                trial.timestep = trial.timestamps[1] - trial.timestamps[0]
            trial.frames_per_second = trial.c3d_file.framesPerSecond
            trial.marker_set = trial.c3d_file.markers
        elif os.path.exists(trc_file_path):
            trc_file: nimble.biomechanics.OpenSimTRC = nimble.biomechanics.OpenSimParser.loadTRC(
                trc_file_path)
            # Do a deep copy of the marker observations, to avoid potential memory issues on the PyBind interface
            file_marker_observations = trc_file.markerTimesteps
            trial.marker_observations = deep_copy_marker_observations(file_marker_observations)
            any_have_markers = False
            for markerTimestep in trial.marker_observations:
                if len(markerTimestep.keys()) > 0:
                    any_have_markers = True
                    break
            if not any_have_markers:
                trial.error = True
                trial.error_loading_files = ('Trial {trial_name} has no markers on any timestep. Check that the TRC '
                                             'file is not corrupted.')
            trial.timestamps = trc_file.timestamps
            if len(trial.timestamps) > 1:
                trial.timestep = trial.timestamps[1] - trial.timestamps[0]
            trial.frames_per_second = trc_file.framesPerSecond
            trial.marker_set = list(trc_file.markerLines.keys())
            grf_file_path = trial_path + 'grf.mot'
            trial.ignore_foot_not_over_force_plate = True  # .mot files do not contain force plate geometry
            if os.path.exists(grf_file_path):
                force_plates: List[nimble.biomechanics.ForcePlate] = nimble.biomechanics.OpenSimParser.loadGRF(
                    grf_file_path, trc_file.timestamps)
                trial.force_plates = force_plates
            else:
                print('Warning: No ground reaction forces specified for ' + trial_name)
                trial.force_plates = []
        else:
            trial.error = True
            trial.error_loading_files = ('No marker files exist for trial ' + trial_name + '. Checked both ' +
                                         c3d_file_path + ' and ' + trc_file_path + ', neither exist.')

        # Load the IK for the manually scaled OpenSim model, if it exists
        if os.path.exists(gold_mot_file_path) and manually_scaled_opensim is not None:
            if trial.c3d_file is not None:
                manually_scaled_mot: nimble.biomechanics.OpenSimMot = (
                    nimble.biomechanics.OpenSimParser.loadMotAtLowestMarkerRMSERotation(
                        manually_scaled_opensim, gold_mot_file_path, trial.c3d_file))
                trial.manually_scaled_ik = manually_scaled_mot.poses
            else:
                manually_scaled_mot = nimble.biomechanics.OpenSimParser.loadMot(
                    manually_scaled_opensim.skeleton, gold_mot_file_path)
                trial.manually_scaled_ik = manually_scaled_mot.poses

        # Read in the tags
        if os.path.exists(json_file_path):
            with open(json_file_path, 'r') as f:
                trial_json = json.load(f)
            if 'tags' in trial_json:
                trial.tags = trial_json['tags']

        # Set an error if there are no marker data frames
        if len(trial.marker_observations) == 0 and not trial.error:
            trial.error = True
            trial.error_loading_files = ('No marker data frames found for trial ' + trial_name + '.')
            print(trial.error_loading_files)

        # Set an error if there are any NaNs or suspiciously large values in the marker data
        for t in range(len(trial.marker_observations)):
            for marker in trial.marker_observations[t]:
                if np.any(np.isnan(trial.marker_observations[t][marker])):
                    trial.error = True
                    trial.error_loading_files = (f'Trial {trial_name} has NaNs in marker data. Check that the marker '
                                                 f'file is not corrupted.')
                    break  # Exit inner loop
                elif np.any(np.abs(trial.marker_observations[t][marker]) > 1e6):
                    trial.error = True
                    trial.error_loading_files = (f'Trial {trial_name} has suspiciously large values ({trial.marker_observations[t][marker]}) in marker data. '
                                                 f'Check that the marker file is accurate.')
                    break  # Exit inner loop

        return trial

    def split_segments(self, max_grf_gap_fill_size=1.0, max_segment_frames=3000):
        """
        Split the trial into segments based on the marker and force plate data.
        """
        if self.error:
            return

        self.segments = []
        split_points = [0, len(self.marker_observations)]

        # If we transition from no markers to markers, or vice versa, we want to split
        # the trial at that point.
        has_markers: List[bool] = [len(obs) > 0 for obs in self.marker_observations]
        for i in range(1, len(has_markers)):
            if has_markers[i] != has_markers[i - 1]:
                split_points.append(i)

        # Forces is a trickier case, because we want to split the trial on sections of zero GRF that last longer than a
        # threshold, but allow short sections to be contained in a normal GRF segment without splitting.
        total_forces: List[float] = [0.0] * len(self.marker_observations)
        for force_plate in self.force_plates:
            forces = force_plate.forces
            moments = force_plate.moments
            assert (len(forces) == len(total_forces))
            assert (len(moments) == len(total_forces))
            for i in range(len(total_forces)):
                total_forces[i] += np.linalg.norm(forces[i]) + np.linalg.norm(moments[i])
        has_forces = [f > 1e-3 for f in total_forces]
        # Now we need to go through and fill in the "short gaps" in the has_forces array.
        last_transition_off = 0
        for i in range(len(has_forces) - 1):
            if has_forces[i] and not has_forces[i + 1]:
                last_transition_off = i + 1
            elif not has_forces[i] and has_forces[i + 1]:
                if i - last_transition_off < int(max_grf_gap_fill_size / self.timestep):
                    for j in range(last_transition_off, i + 1):
                        has_forces[j] = True
        if not has_forces[-1] and len(has_forces) - last_transition_off < int(max_grf_gap_fill_size / self.timestep):
            for j in range(last_transition_off, len(has_forces)):
                has_forces[j] = True
        # Now we can split the trial on the has_forces array, just like we did for markers.
        for i in range(1, len(has_forces)):
            if has_forces[i] != has_forces[i - 1]:
                split_points.append(i)
        # Next, we need to sort the split points and remove duplicates.
        split_points = sorted(list(set(split_points)))
        # Finally, we need to make sure that no segment is longer than max_segment_frames
        # frames. If it is, we need to split it.
        length_split_points = []
        for i in range(len(split_points) - 1):
            segment_length = split_points[i + 1] - split_points[i]
            if segment_length > max_segment_frames:
                for j in range(max_segment_frames, segment_length, max_segment_frames):
                    length_split_points.append(split_points[i] + j)
        split_points += length_split_points
        split_points = sorted(list(set(split_points)))

        for i in range(len(split_points) - 1):
            assert(split_points[i] < split_points[i + 1])
            self.segments.append(TrialSegment(self, split_points[i], split_points[i + 1]))
            self.segments[-1].has_markers = has_markers[split_points[i]]
            self.segments[-1].has_forces = any(has_forces[split_points[i]:split_points[i + 1]])


class TrialSegment:
    def __init__(self, parent: 'Trial', start: int, end: int):
        # Input data
        self.parent: 'Trial' = parent
        self.start: int = start
        self.end: int = end
        self.timestamps: List[float] = self.parent.timestamps[self.start:self.end] if (
                self.parent.timestamps is not None and len(self.parent.timestamps) >= self.end
        ) else []
        self.has_markers: bool = False
        self.has_forces: bool = False
        self.has_error: bool = False
        self.error_msg = ''
        self.original_marker_observations: List[Dict[str, np.ndarray]] = []
        self.missing_grf_reason: List[nimble.biomechanics.MissingGRFReason] = [nimble.biomechanics.MissingGRFReason.notMissingGRF for _ in range(self.end - self.start)]
        # Make a deep copy of the marker observations, so we can modify them without affecting the parent trial
        for obs in self.parent.marker_observations[self.start:self.end]:
            obs_copy = {}
            for marker in obs:
                obs_copy[marker] = obs[marker].copy()
            self.original_marker_observations.append(obs_copy)
        self.force_plates: List[nimble.biomechanics.ForcePlate] = []
        for plate in self.parent.force_plates:
            new_plate = nimble.biomechanics.ForcePlate.copyForcePlate(plate)
            if len(new_plate.forces) > 0:
                assert(len(new_plate.forces) == len(self.parent.marker_observations))
                new_plate.trimToIndexes(self.start, self.end)
                assert(len(new_plate.forces) == len(self.original_marker_observations))
            self.force_plates.append(new_plate)
        # Manually scaled comparison data, to render visual comparisons if the user uploaded it
        self.manually_scaled_ik_poses: Optional[np.ndarray] = None
        if self.parent.manually_scaled_ik is not None and self.parent.manually_scaled_ik.shape[1] >= self.end:
            self.manually_scaled_ik_poses = self.parent.manually_scaled_ik[:, self.start:self.end]
        self.manually_scaled_ik_error_report: Optional[nimble.biomechanics.IKErrorReport] = None
        # Kinematics output data
        self.marker_error_report: Optional[nimble.biomechanics.MarkersErrorReport] = None
        self.marker_observations: List[Dict[str, np.ndarray]] = self.original_marker_observations
        self.kinematics_status: ProcessingStatus = ProcessingStatus.NOT_STARTED
        self.kinematics_poses: Optional[np.ndarray] = None
        self.marker_fitter_result: Optional[nimble.biomechanics.MarkerInitialization] = None
        self.kinematics_ik_error_report: Optional[nimble.biomechanics.IKErrorReport] = None
        # Dynamics output data
        self.dynamics_status: ProcessingStatus = ProcessingStatus.NOT_STARTED
        self.dynamics_poses: Optional[np.ndarray] = None
        self.dynamics_taus: Optional[np.ndarray] = None
        self.bad_dynamics_frames: List[int] = []
        self.ground_height: float = 0.0
        self.foot_body_wrenches: Optional[np.ndarray] = None
        self.output_force_plates: List[nimble.biomechanics.ForcePlate] = []
        self.linear_residuals: float = 0.0
        self.angular_residuals: float = 0.0
        self.dynamics_ik_error_report: Optional[nimble.biomechanics.IKErrorReport] = None
        # Rendering state
        self.render_markers_set: Set[str] = set()
        self.render_markers_renamed_set: Set[Tuple[str, str]] = set()

        # Set an error if there are no marker data frames
        if len(self.marker_observations) == 0:
            self.has_error = True
            self.error_msg = 'No marker data frames found'

        # Set an error if there are any NaNs in the marker data
        for t in range(len(self.marker_observations)):
            for marker in self.marker_observations[t]:
                if np.any(np.isnan(self.marker_observations[t][marker])):
                    self.has_error = True
                    self.error_msg = 'Trial segment has NaNs in marker data.'
                elif np.any(np.abs(self.marker_observations[t][marker]) > 1e6):
                    self.error = True
                    self.error_msg = (f'Trial segment has suspiciously large values ({self.marker_observations[t][marker]}) in marker data. '
                                     f'Check that the marker file is accurate.')
                    break  # Exit inner loop

    def compute_manually_scaled_ik_error(self, manually_scaled_osim: nimble.biomechanics.OpenSimFile):
        self.manually_scaled_ik_error_report = nimble.biomechanics.IKErrorReport(
            manually_scaled_osim.skeleton,
            manually_scaled_osim.markersMap,
            self.manually_scaled_ik_poses,
            self.marker_observations)

    def get_segment_results_json(self) -> Dict[str, Any]:
        has_marker_warnings: bool = False
        if self.marker_error_report is not None:
            if len(self.marker_error_report.droppedMarkerWarnings) > 0:
                has_marker_warnings = True
            if len(self.marker_error_report.markersRenamedFromTo) > 0:
                has_marker_warnings = True

        results: Dict[str, Any] = {
            'trialName': self.parent.trial_name,
            'start_frame': self.start,
            'start': self.timestamps[0],
            'end_frame': self.end,
            'end': self.timestamps[-1],
            # Kinematics fit marker error results, if present
            'kinematicsStatus': self.kinematics_status.name,
            'kinematicsAvgRMSE': self.kinematics_ik_error_report.averageRootMeanSquaredError if self.kinematics_ik_error_report is not None else None,
            'kinematicsAvgMax': self.kinematics_ik_error_report.averageMaxError if self.kinematics_ik_error_report is not None else None,
            'kinematicsPerMarkerRMSE': self.kinematics_ik_error_report.getSortedMarkerRMSE() if self.kinematics_ik_error_report is not None else None,
            # Dynamics fit results, if present
            'dynamicsStatus': self.dynamics_status.name,
            'dynanimcsAvgRMSE': self.dynamics_ik_error_report.averageRootMeanSquaredError if self.dynamics_ik_error_report is not None else None,
            'dynanimcsAvgMax': self.dynamics_ik_error_report.averageMaxError if self.dynamics_ik_error_report is not None else None,
            'dynanimcsPerMarkerRMSE': self.dynamics_ik_error_report.getSortedMarkerRMSE() if self.dynamics_ik_error_report is not None else None,
            'linearResiduals': self.linear_residuals,
            'angularResiduals': self.angular_residuals,
            # Hand scaled marker error results, if present
            'goldAvgRMSE': self.manually_scaled_ik_error_report.averageRootMeanSquaredError if self.manually_scaled_ik_error_report is not None else None,
            'goldAvgMax': self.manually_scaled_ik_error_report.averageMaxError if self.manually_scaled_ik_error_report is not None else None,
            'goldPerMarkerRMSE': self.manually_scaled_ik_error_report.getSortedMarkerRMSE() if self.manually_scaled_ik_error_report is not None else None,
            'hasMarkers': self.has_markers,
            'hasForces': self.has_forces,
            'hasMarkerWarnings': has_marker_warnings
        }
        return results

    def save_segment_to_gui(self,
                            gui_file_path: str,
                            final_skeleton: Optional[nimble.dynamics.Skeleton] = None,
                            final_markers: Optional[Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]]] = None,
                            manually_scaled_skeleton: Optional[nimble.biomechanics.OpenSimFile] = None):
        """
        Write this trial segment to a file that can be read by the 3D web GUI
        """
        gui = nimble.server.GUIRecording()

        for t in range(len(self.marker_observations)):
            if t % 50 == 0:
                print(f'> Rendering frame {t} of {len(self.marker_observations)}')
            self.render_frame(gui, t, final_skeleton, final_markers, manually_scaled_skeleton)
            gui.saveFrame()

        gui.setFramesPerSecond(int(1.0 / self.parent.timestep))
        gui.writeFramesJson(gui_file_path)

    def save_segment_csv(self, csv_file_path: str, final_skeleton: Optional[nimble.dynamics.Skeleton] = None):
        # Finite difference out the joint quantities we care about
        poses: np.ndarray = np.zeros((0, 0))
        if self.dynamics_status == ProcessingStatus.FINISHED and self.dynamics_poses is not None:
            poses = self.dynamics_poses
        elif self.kinematics_status == ProcessingStatus.FINISHED and self.kinematics_poses is not None:
            poses = self.kinematics_poses
        
        vels: np.ndarray = np.zeros_like(poses)
        accs: np.ndarray = np.zeros_like(poses)
        for i in range(1, poses.shape[1]):
            vels[:, i] = (poses[:, i] - poses[:, i - 1]) / self.parent.timestep
        if vels.shape[1] > 0:
            vels[:, 0] = vels[:, 1]
        for i in range(1, vels.shape[1]):
            accs[:, i] = (vels[:, i] - vels[:, i - 1]) / self.parent.timestep
        if accs.shape[1] > 0:
            accs[:, 0] = accs[:, 1]

        # Write the CSV file
        with open(csv_file_path, 'w') as f:
            f.write('timestamp')
            if final_skeleton is not None:
                if self.kinematics_status == ProcessingStatus.FINISHED:
                    # Joint positions
                    for i in range(final_skeleton.getNumDofs()):
                        f.write(',' + final_skeleton.getDofByIndex(i).getName()+'_pos')
                    # Joint velocities
                    for i in range(final_skeleton.getNumDofs()):
                        f.write(',' + final_skeleton.getDofByIndex(i).getName()+'_vel')
                    # Joint accelerations
                    for i in range(final_skeleton.getNumDofs()):
                        f.write(',' + final_skeleton.getDofByIndex(i).getName()+'_acc')
                if self.dynamics_status == ProcessingStatus.FINISHED:
                    # Joint torques
                    for i in range(final_skeleton.getNumDofs()):
                        f.write(',' + final_skeleton.getDofByIndex(i).getName()+'_tau')
            f.write('\n')

            for t in range(len(self.marker_observations)):
                f.write(str(self.timestamps[t]))
                if final_skeleton is not None:
                    if self.kinematics_status == ProcessingStatus.FINISHED:
                        # Joint positions
                        for i in range(final_skeleton.getNumDofs()):
                            f.write(',' + str(poses[i, t]))
                        # Joint velocities
                        for i in range(final_skeleton.getNumDofs()):
                            f.write(',' + str(vels[i, t]))
                        # Joint accelerations
                        for i in range(final_skeleton.getNumDofs()):
                            f.write(',' + str(accs[i, t]))
                    if self.dynamics_status == ProcessingStatus.FINISHED:
                        # Joint torques
                        for i in range(final_skeleton.getNumDofs()):
                            f.write(',' + str(self.dynamics_taus[i, t]))
                f.write('\n')

    def render_frame(self,
                     gui: nimble.server.GUIRecording,
                     t: int,
                     final_skeleton: Optional[nimble.dynamics.Skeleton] = None,
                     final_markers: Optional[Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]]] = None,
                     manually_scaled_skeleton: Optional[nimble.biomechanics.OpenSimFile] = None):
        markers_layer_name: str = 'Markers'
        warnings_layer_name: str = 'Warnings'
        force_plate_layer_name: str = 'Force Plates'
        manually_fit_layer_name: str = 'Manually Fit'
        kinematics_fit_layer_name: str = 'Kinematics Fit'
        dynamics_fit_layer_name: str = 'Dynamics Fit'

        # 1. On the first frame, we want to create all the markers for subsequent frames
        if t == 0:
            # 1.1. Set up the layers
            gui.createLayer(markers_layer_name, [0.5, 0.5, 0.5, 1.0], defaultShow=False)
            gui.createLayer(warnings_layer_name, [1.0, 0.0, 0.0, 1.0], defaultShow=False)
            gui.createLayer(force_plate_layer_name, [1.0, 0.0, 0.0, 1.0], defaultShow=True)

            if manually_scaled_skeleton is not None:
                gui.createLayer(manually_fit_layer_name, [0.0, 0.0, 1.0, 1.0], defaultShow=False)
            if self.kinematics_status == ProcessingStatus.FINISHED and final_skeleton is not None:
                # Default to showing kinematics only if dynamics didn't finish
                gui.createLayer(kinematics_fit_layer_name,
                                defaultShow=(self.dynamics_status != ProcessingStatus.FINISHED))
            if self.dynamics_status == ProcessingStatus.FINISHED and final_skeleton is not None:
                # Default to showing dynamics if it finished
                gui.createLayer(dynamics_fit_layer_name, defaultShow=True)

            # 1.2. Create the marker set objects, so we don't recreate them every frame
            self.render_markers_set = set()
            for obs in self.marker_observations:
                for key in obs:
                    self.render_markers_set.add(key)
            self.render_markers_renamed_set = set()
            if self.marker_error_report is not None:
                for renamedFrame in self.marker_error_report.markersRenamedFromTo:
                    for from_marker, to_marker in renamedFrame:
                        self.render_markers_renamed_set.add((from_marker, to_marker))
            for marker in self.render_markers_set:
                gui.createBox('marker_' + str(marker),
                              np.ones(3, dtype=np.float64) * 0.02,
                              np.zeros(3, dtype=np.float64),
                              np.zeros(3, dtype=np.float64),
                              [0.5, 0.5, 0.5, 1.0],
                              layer=markers_layer_name)
                gui.setObjectTooltip('marker_' + str(marker), str(marker))

        # 2. Always render the markers, even if we don't have kinematics or dynamics
        for marker in self.render_markers_set:
            if marker in self.marker_observations[t]:
                # Render all the marker observations
                gui.createBox('marker_' + str(marker),
                              np.ones(3, dtype=np.float64) * 0.02,
                              self.marker_observations[t][marker],
                              np.zeros(3, dtype=np.float64),
                              [0.5, 0.5, 0.5, 1.0],
                              layer=markers_layer_name)
            else:
                gui.deleteObject('marker_' + str(marker))

            # Render any marker warnings
            if self.marker_error_report is not None:
                renamed_from_to: Set[Tuple[str, str]] = set(self.marker_error_report.markersRenamedFromTo[t])
                for from_marker, to_marker in renamed_from_to:
                    from_marker_location = None
                    if from_marker in self.marker_observations[t]:
                        from_marker_location = self.marker_observations[t][from_marker]
                    to_marker_location = None
                    if to_marker in self.marker_observations[t]:
                        to_marker_location = self.marker_observations[t][to_marker]

                    if to_marker_location is not None and from_marker_location is not None:
                        gui.createLine('marker_renamed_' + str(from_marker) + '_to_' + str(to_marker), [to_marker_location, from_marker_location], [1.0, 0.0, 0.0, 1.0], layer=warnings_layer_name)
                    gui.setObjectWarning('marker_'+str(to_marker), 'warning_marker_renamed_' + str(from_marker) + '_to_' + str(to_marker), 'Marker ' + str(to_marker) + ' was originally named ' + str(from_marker), warnings_layer_name)
                for from_marker, to_marker in self.render_markers_renamed_set:
                    if (from_marker, to_marker) not in renamed_from_to:
                        gui.deleteObject('marker_renamed_' + str(from_marker) + '_to_' + str(to_marker))
                    gui.deleteObjectWarning('marker_'+str(to_marker), 'warning_marker_renamed_' + str(from_marker) + '_to_' + str(to_marker))

        # 3. Always render the force plates if we've got them, even if we don't have kinematics or dynamics
        for i, force_plate in enumerate(self.force_plates):
            if len(force_plate.centersOfPressure) > t and len(force_plate.forces) > t and len(force_plate.moments) > t:
                cop = force_plate.centersOfPressure[t]
                force = force_plate.forces[t]
                moment = force_plate.moments[t]
                line = [cop, cop + force * 0.001]
                gui.createLine('force_plate_' + str(i), line, [1.0, 0.0, 0.0, 1.0], layer=force_plate_layer_name, width=[2.0, 1.0])

        # 4. Render the kinematics skeleton, if we have it
        if self.kinematics_status == ProcessingStatus.FINISHED and final_skeleton is not None:
            final_skeleton.setPositions(self.kinematics_poses[:, t])
            gui.renderSkeleton(final_skeleton, prefix='kinematics_', layer=kinematics_fit_layer_name)

        # 5. Render the dynamics skeleton, if we have it
        if self.dynamics_status == ProcessingStatus.FINISHED and final_skeleton is not None:
            final_skeleton.setPositions(self.dynamics_poses[:, t])
            gui.renderSkeleton(final_skeleton, prefix='dynamics_', layer=dynamics_fit_layer_name)
