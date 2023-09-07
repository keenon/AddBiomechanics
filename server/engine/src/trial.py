import nimblephysics as nimble
from typing import List, Dict, Tuple, Any, Set, Optional
import numpy as np
import os
import enum
import json


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
        gold_mot_file_path = trial_path + 'manual_ik.mot'
        trial = Trial()
        trial.trial_path = trial_path
        trial.trial_name = trial_name
        if os.path.exists(c3d_file_path):
            trial.c3d_file = nimble.biomechanics.C3DLoader.loadC3D(
                c3d_file_path)

            any_have_markers = False
            for markerTimestep in trial.c3d_file.markerTimesteps:
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
            trial.marker_timesteps = trial.c3d_file.markerTimesteps
        elif os.path.exists(trc_file_path):
            trc_file: nimble.biomechanics.OpenSimTRC = nimble.biomechanics.OpenSimParser.loadTRC(
                trc_file_path)

            any_have_markers = False
            for markerTimestep in trc_file.markerTimesteps:
                if len(markerTimestep.keys()) > 0:
                    any_have_markers = True
                    break
            if not any_have_markers:
                trial.error = True
                trial.error_loading_files = ('Trial {trial_name} has no markers on any timestep. Check that the TRC '
                                             'file is not corrupted.')
            trial.marker_observations = trc_file.markerTimesteps
            trial.timestamps = trc_file.timestamps
            if len(trial.timestamps) > 1:
                trial.timestep = trial.timestamps[1] - trial.timestamps[0]
            trial.frames_per_second = trc_file.framesPerSecond
            trial.marker_set = list(trc_file.markerLines.keys())
            trial.marker_timesteps = trc_file.markerTimesteps
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
                                         c3d_file_path + ' and ' + trc_file_path + ', neither exist. Quitting.')

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

        return trial

    def split_segments(self, max_grf_gap_fill_size=1.0, max_segment_frames=3000):
        """
        Split the trial into segments based on the marker and force plate data.
        """
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
        self.original_marker_observations: List[Dict[str, np.ndarray]] = self.parent.marker_observations[self.start:self.end]
        self.force_plates: List[nimble.biomechanics.ForcePlate] = []
        for plate in self.parent.force_plates:
            new_plate = nimble.biomechanics.ForcePlate.copyForcePlate(plate)
            if len(new_plate.forces) > 0:
                assert(len(new_plate.forces) == len(self.parent.marker_observations))
                new_plate.trimToIndexes(self.start, self.end)
                print(len(new_plate.forces))
                print(len(self.original_marker_observations))
                assert(len(new_plate.forces) == len(self.original_marker_observations))
            self.force_plates.append(new_plate)
        # Manually scaled comparison data, to render visual comparisons if the user uploaded it
        self.manually_scaled_ik_poses: Optional[np.ndarray] = None
        if self.parent.manually_scaled_ik is not None and self.parent.manually_scaled_ik.shape[1] >= self.end:
            self.manually_scaled_ik_poses = self.parent.manually_scaled_ik[:, self.start:self.end]
        # General output data
        self.linear_residuals: float = 0.0
        self.angular_residuals: float = 0.0
        # Kinematics output data
        self.marker_error_report: Optional[nimble.biomechanics.MarkersErrorReport] = None
        self.marker_observations: List[Dict[str, np.ndarray]] = self.original_marker_observations
        self.kinematics_status: ProcessingStatus = ProcessingStatus.NOT_STARTED
        self.kinematics_poses: Optional[np.ndarray] = None
        self.marker_fitter_result: Optional[nimble.biomechanics.MarkerInitialization] = None
        # Dynamics output data
        self.dynamics_status: ProcessingStatus = ProcessingStatus.NOT_STARTED
        self.dynamics_poses: Optional[np.ndarray] = None
        self.dynamics_taus: Optional[np.ndarray] = None
        self.bad_dynamics_frames: List[int] = []
        self.ground_height: float = 0.0
        self.foot_body_wrenches: Optional[np.ndarray] = None
        # Rendering state
        self.render_markers_set: Set[str] = set()
        self.render_markers_renamed_set: Set[Tuple[str, str]] = set()

    def save_segment_results_to_json(self,
                                     json_file_path: str,
                                     final_skeleton: Optional[nimble.dynamics.Skeleton] = None,
                                     fit_markers: Optional[Dict[str, Tuple[nimble.dynamics.BodyNode, np.ndarray]]] = None,
                                     manually_scaled_osim: Optional[nimble.biomechanics.OpenSimFile] = None):
        with open(json_file_path, 'w') as f:
            has_marker_warnings: bool = False
            if self.marker_error_report is not None:
                if len(self.marker_error_report.droppedMarkerWarnings) > 0:
                    has_marker_warnings = True
                if len(self.marker_error_report.markersRenamedFromTo) > 0:
                    has_marker_warnings = True

            manually_scaled_ik: Optional[nimble.biomechanics.IKErrorReport] = None
            if self.manually_scaled_ik_poses is not None:
                manually_scaled_ik = nimble.biomechanics.IKErrorReport(
                    manually_scaled_osim.skeleton,
                    manually_scaled_osim.markersMap,
                    self.manually_scaled_ik_poses,
                    self.marker_observations)
                print('manually scaled average RMSE cm: ' +
                      str(manually_scaled_ik.averageRootMeanSquaredError), flush=True)
                print('manually scaled average max cm: ' +
                      str(manually_scaled_ik.averageMaxError), flush=True)

            # Store the marker errors.
            result_kinematics: Optional[nimble.biomechanics.IKErrorReport] = None
            if self.kinematics_poses is not None and final_skeleton is not None and fit_markers is not None:
                result_kinematics = nimble.biomechanics.IKErrorReport(
                    final_skeleton, fit_markers, self.kinematics_poses, self.marker_observations)

            result_dynamics: Optional[nimble.biomechanics.IKErrorReport] = None
            if self.dynamics_poses is not None and final_skeleton is not None and fit_markers is not None:
                result_dynamics = nimble.biomechanics.IKErrorReport(
                    final_skeleton, fit_markers, self.dynamics_poses, self.marker_observations)

            results: Dict[str, Any] = {
                'trialName': self.parent.trial_name,
                'start': self.start,
                'end': self.end,
                # Kinematics fit marker error results, if present
                'kinematicsStatus': self.kinematics_status.name,
                'kinematicsAvgRMSE': result_kinematics.averageRootMeanSquaredError if result_kinematics is not None else None,
                'kinematicsAvgMax': result_kinematics.averageMaxError if result_kinematics is not None else None,
                'kinematicsPerMarkerRMSE': result_kinematics.getSortedMarkerRMSE() if result_kinematics is not None else None,
                # Dynamics fit results, if present
                'dynamicsStatus': self.dynamics_status.name,
                'dynanimcsAvgRMSE': result_dynamics.averageRootMeanSquaredError if result_dynamics is not None else None,
                'dynanimcsAvgMax': result_dynamics.averageMaxError if result_dynamics is not None else None,
                'dynanimcsPerMarkerRMSE': result_dynamics.getSortedMarkerRMSE() if result_dynamics is not None else None,
                'linearResiduals': self.linear_residuals,
                'angularResiduals': self.angular_residuals,
                # Hand scaled marker error results, if present
                'goldAvgRMSE': manually_scaled_ik.averageRootMeanSquaredError if manually_scaled_ik is not None else None,
                'goldAvgMax': manually_scaled_ik.averageMaxError if manually_scaled_ik is not None else None,
                'goldPerMarkerRMSE': manually_scaled_ik.getSortedMarkerRMSE() if manually_scaled_ik is not None else None,
                'hasMarkers': self.has_markers,
                'hasForces': self.has_forces,
                'hasMarkerWarnings': has_marker_warnings
            }
            json.dump(results, f)

    def save_segment_to_gui(self, gui_file_path: str):
        """
        Write this trial segment to a file that can be read by the 3D web GUI
        """
        gui = nimble.server.GUIRecording()

        for t in range(len(self.marker_observations)):
            self.render_markers_frame(gui, t)
            gui.saveFrame()

        gui.setFramesPerSecond(int(1.0 / self.parent.timestep))
        gui.writeFramesJson(gui_file_path)

    def save_segment_csv(self, csv_file_path: str):
        with open(csv_file_path, 'w') as f:
            f.write('timestamp,')
            # TODO

    def render_markers_frame(self, gui: nimble.server.GUIRecording, t: int):
        # On the first frame, we want to create all the markers for subsequent frames
        markers_layer_name: str = 'Markers'
        marker_warnings_layer_name: str = 'Marker Warnings'
        if t == 0:
            # Create the data structures we'll re-use when rendering other frames
            self.render_markers_set = set()
            for obs in self.marker_observations:
                for key in obs:
                    self.render_markers_set.add(key)
            self.render_markers_renamed_set = set()
            if self.marker_error_report is not None:
                for renamedFrame in self.marker_error_report.markersRenamedFromTo:
                    for from_marker, to_marker in renamedFrame:
                        self.render_markers_renamed_set.add((from_marker, to_marker))

            gui.createLayer(markers_layer_name, [0.5, 0.5, 0.5, 1.0], defaultShow=True)
            if self.marker_error_report is not None:
                gui.createLayer(marker_warnings_layer_name, [1.0, 0.0, 0.0, 1.0], defaultShow=False)
            for marker in self.render_markers_set:
                gui.createBox('marker_' + str(marker),
                              np.ones(3, dtype=np.float64) * 0.02,
                              np.zeros(3, dtype=np.float64),
                              np.zeros(3, dtype=np.float64),
                              [0.5, 0.5, 0.5, 1.0],
                              layer=markers_layer_name)
                gui.setObjectTooltip('marker_' + str(marker), str(marker))

        # Now we can render the markers for this frame
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
                        gui.createLine('marker_renamed_' + str(from_marker) + '_to_' + str(to_marker), [to_marker_location, from_marker_location], [1.0, 0.0, 0.0, 1.0], layer=marker_warnings_layer_name)
                    gui.setObjectWarning('marker_'+str(to_marker), 'warning_marker_renamed_' + str(from_marker) + '_to_' + str(to_marker), 'Marker ' + str(to_marker) + ' was originally named ' + str(from_marker))
                for from_marker, to_marker in self.render_markers_renamed_set:
                    if (from_marker, to_marker) not in renamed_from_to:
                        gui.deleteObject('marker_renamed_' + str(from_marker) + '_to_' + str(to_marker))
                    gui.deleteObjectWarning('marker_'+str(to_marker), 'warning_marker_renamed_' + str(from_marker) + '_to_' + str(to_marker))
