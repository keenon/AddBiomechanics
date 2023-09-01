import nimblephysics as nimble
from typing import List, Dict, Tuple, Any
import numpy as np
import os
import enum


class ProcessingStatus(enum.Enum):
    NOT_STARTED = 0
    IN_PROGRESS = 1
    FINISHED = 2
    ERROR = 3


class Trial:
    def __init__(self):
        # Input data
        self.trial_name = ''
        self.marker_observations: List[Dict[str, np.ndarray]] = []
        self.force_plates: List[nimble.biomechanics.ForcePlate] = []
        self.timestep: float = 0.01
        # Error states
        self.error: bool = False
        self.error_loading_files: str = ''
        # Output data
        self.segments: List['TrialSegment'] = []

    @staticmethod
    def load_trial(trial_name: str, trial_path: str) -> 'Trial':
        """
        Load a trial from a folder. This assumes that the folder either contains `markers.c3d`,
        or `markers.trc` and (optionally) `grf.mot`.
        """
        if not trial_path.endswith('/'):
            trial_path += '/'
        c3d_file_path = trial_path + 'markers.c3d'
        trc_file_path = trial_path + 'markers.trc'
        trial = Trial()
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
        self.has_markers: bool = False
        self.has_forces: bool = False
        self.has_error: bool = False
        self.error_msg = ''
        self.original_marker_observations: List[Dict[str, np.ndarray]] = self.parent.marker_observations[self.start:self.end]
        self.force_plates: List[nimble.biomechanics.ForcePlate] = []
        for plate in self.parent.force_plates:
            new_plate = nimble.biomechanics.ForcePlate.copyForcePlate(plate)
            new_plate.trim(self.start * self.parent.timestep, (self.end - 1) * self.parent.timestep)
            assert(len(new_plate.forces) == len(self.original_marker_observations))
            self.force_plates.append(new_plate)
        # General output data
        self.result_json: Dict[str, Any] = {}
        # Kinematics output data
        self.marker_error_report: nimble.biomechanics.MarkersErrorReport = None
        self.marker_observations: List[Dict[str, np.ndarray]] = []
        self.kinematics_status: ProcessingStatus = ProcessingStatus.NOT_STARTED
        self.kinematics_poses: np.ndarray = None
        self.marker_fitter_result: nimble.biomechanics.MarkerInitialization = None
        # Dynamics output data
        self.dynamics_status: ProcessingStatus = ProcessingStatus.NOT_STARTED
        self.dynamics_poses: np.ndarray = None
        self.dynamics_taus: np.ndarray = None
        self.bad_dynamics_frames: List[int] = []
