import nimblephysics as nimble
from typing import List, Dict, Tuple, Any, Set, Optional
import numpy as np
import os
import enum
import json
from memory_utils import deep_copy_marker_observations
from scipy.signal import butter, filtfilt, resample_poly
import mmap


def fast_count_lines(path: str) -> int:
    with open(path, 'r+b') as file:
        mm = mmap.mmap(file.fileno(), 0)
        line_count = 0
        while mm.readline():
            line_count += 1
    return line_count

class ProcessingStatus(enum.Enum):
    NOT_STARTED = 0
    IN_PROGRESS = 1
    FINISHED = 2
    ERROR = 3


class Trial:
    def __init__(self):
        # Input data
        self.trial_index = 0
        self.trial_path = ''
        self.trial_name = ''
        self.tags: List[str] = []
        self.marker_observations: List[Dict[str, np.ndarray]] = []
        self.force_plates: List[nimble.biomechanics.ForcePlate] = []
        self.force_plate_raw_cops: List[List[np.ndarray]] = []
        self.force_plate_raw_forces: List[List[np.ndarray]] = []
        self.force_plate_raw_moments: List[List[np.ndarray]] = []
        self.force_plate_thresholds: List[float] = []
        self.timestamps: List[float] = []
        self.timestep: float = 0.01
        self.missing_grf_manual_review: List[nimble.biomechanics.MissingGRFStatus] = []
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
                   trial_index: int,
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
            trial.set_force_plates(trial.c3d_file.forcePlates)
            trial.timestamps = trial.c3d_file.timestamps
            if len(trial.timestamps) > 1:
                trial.timestep = (trial.timestamps[-1] - trial.timestamps[0]) / len(trial.timestamps)
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
                trial.timestep = (trial.timestamps[-1] - trial.timestamps[0]) / len(trial.timestamps)
            trial.frames_per_second = trc_file.framesPerSecond
            trial.marker_set = list(trc_file.markerLines.keys())
            grf_file_path = trial_path + 'grf.mot'
            trial.ignore_foot_not_over_force_plate = True  # .mot files do not contain force plate geometry
            if os.path.exists(grf_file_path):
                force_plates: List[nimble.biomechanics.ForcePlate] = nimble.biomechanics.OpenSimParser.loadGRF(
                    grf_file_path, trc_file.timestamps)
                trial.set_force_plates(force_plates)
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

        # Load in any manual segment reviews for this trial
        print(f'Checking for existing trial segments at {trial_path}...')
        for subdir in os.listdir(trial_path):
            full_path = os.path.join(trial_path, subdir)
            if os.path.isdir(full_path):
                print(f'--> Found sub-directory {subdir}')

        segment_paths = list()
        segment_indexes = list()
        current_index = 1
        while True:
            segment_path = os.path.join(trial_path, f'segment_{current_index}')
            if os.path.exists(segment_path):
                segment_paths.append(segment_path)
                segment_indexes.append(current_index)
                print(f'--> Found segment {current_index} at {segment_path}')
                current_index += 1
            else:
                break

        pre_loaded_review_frames: List[nimble.biomechanics.MissingGRFStatus] = []
        for segment_path, segment_index in zip(segment_paths, segment_indexes):
            print(f"Checking manual GRF reviews in trial segment '{segment_path}'...")
            data_path = os.path.join(segment_path, 'data.csv')
            reviewed_path = os.path.join(segment_path, 'REVIEWED')
            segment_json_path = os.path.join(segment_path, 'review.json')

            if not os.path.exists(data_path):
                print(f' --> Segment {segment_index} has no file {data_path}. Skipping...')
                break

            # Number of rows in data_path - 1 is the length of this segment
            segment_length = fast_count_lines(data_path) - 1

            if os.path.exists(reviewed_path) and os.path.exists(segment_json_path):
                with open(segment_json_path, 'r') as f:
                    segment_json = json.load(f)
                if 'missing_grf_data' in segment_json:
                    # Some early versions of the annotator would (harmlessly) tack on extra frames to the end of the
                    # segment, so we need to make sure we don't read in too many frames.
                    assert(len(segment_json['missing_grf_data']) == segment_length)
                    print(f' --> Found review data in segment {segment_index}!.')
                    pre_loaded_review_frames += [
                        nimble.biomechanics.MissingGRFStatus.yes if missing else nimble.biomechanics.MissingGRFStatus.no
                        for missing in segment_json['missing_grf_data'][0:segment_length]
                    ]
                else:
                    pre_loaded_review_frames += [nimble.biomechanics.MissingGRFStatus.unknown] * segment_length
            else:
                if os.path.exists(reviewed_path):
                    print(f' --> Segment {segment_index} has no review data, but it has a REVIEWED flag.')
                elif os.path.exists(segment_json_path):
                    print(f' --> Segment {segment_index} has no REVIEWED flag, but it has a review.json file.')
                else:
                    print(f' --> Segment {segment_index} has no review data.')
                pre_loaded_review_frames += [nimble.biomechanics.MissingGRFStatus.unknown] * segment_length

        # Pad with unknown, if necessary
        if len(pre_loaded_review_frames) < len(trial.marker_observations):
            pre_loaded_review_frames += [nimble.biomechanics.MissingGRFStatus.unknown] * (len(trial.marker_observations) - len(pre_loaded_review_frames))
        assert(len(pre_loaded_review_frames) == len(trial.marker_observations))
        trial.missing_grf_manual_review = pre_loaded_review_frames
        print(f'Manually reviewed frames for trial {trial_name}: ', 
              trial.missing_grf_manual_review)

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

    def set_force_plates(self, plates: List[nimble.biomechanics.ForcePlate]):
        print('Setting force plates: '+str(len(plates))+' plates, trial index: '+str(self.trial_index))

        # Copy the raw force plate data to Python memory, so we don't have to copy back and forth every time we access
        # it.
        self.force_plates = plates
        for i, plate in enumerate(self.force_plates):
            if len(plate.forces) > 0:
                assert(len(plate.forces) == len(self.marker_observations))
            print('Processing force plate '+str(i))
            print('Number of non-zero forces: '+str(len([force for force in plate.forces if np.linalg.norm(force) > 1e-3])))
            print('Autodetecting noise threshold for force plate '+str(i))
            plate.autodetectNoiseThresholdAndClip(
                percentOfMaxToDetectThumb=0.25,
                percentOfMaxToCheckThumbRightEdge=0.35
            )
            # print([np.linalg.norm(force) for force in plate.forces])
            print('Detecting and fixing cop moment convention for force plate '+str(i))
            plate.detectAndFixCopMomentConvention(trial=self.trial_index, i=i)
            self.force_plate_raw_cops.append(plate.centersOfPressure)
            self.force_plate_raw_forces.append(plate.forces)
            print('Number of non-zero forces: '+str(len([force for force in plate.forces if np.linalg.norm(force) > 1e-3])))
            self.force_plate_raw_moments.append(plate.moments)
            self.force_plate_thresholds.append(0)

    def zero_force_plate(self, index: int, every_n_steps: int = 3):
        # Zero out the force plate data for a given force plate index. This is useful for running ablation studies.
        start = -1
        step = 0
        for t in range(len(self.force_plate_raw_forces[index])):
            # print(str(t) + ': '+ str(np.linalg.norm(self.force_plate_raw_forces[index][t])))
            if np.linalg.norm(self.force_plate_raw_forces[index][t]) > 1e-3:
                if start == -1:
                    start = t
                    step += 1
                    if step > every_n_steps:
                        step = 0
                if step == every_n_steps:
                    self.missing_grf_manual_review[t] = nimble.biomechanics.MissingGRFStatus.yes
                    self.force_plate_raw_forces[index][t] = np.zeros(3)
                    self.force_plate_raw_cops[index][t] = np.zeros(3)
                    self.force_plate_raw_moments[index][t] = np.zeros(3)
                else:
                    self.missing_grf_manual_review[t] = nimble.biomechanics.MissingGRFStatus.no
            else:
                # Don't mark any other frames as missing, regardless of heuristics
                self.missing_grf_manual_review[t] = nimble.biomechanics.MissingGRFStatus.no
                if start != -1:
                    if step == every_n_steps:
                        print('Zeroing out force plate '+str(index)+' from '+str(start)+' to '+str(t))
                    start = -1
        self.force_plate_thresholds[index] = 0

        if start != -1:
            print('Zeroing out force plate ' + str(index) + ' from ' + str(start) + ' to ' + str(len(self.force_plate_raw_forces[index])))

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
        for i in range(len(self.force_plates)):
            if len(self.force_plate_raw_forces) > i and len(self.force_plate_raw_forces[i]) > 0:
                forces = self.force_plate_raw_forces[i]
                moments = self.force_plate_raw_moments[i]
                if len(forces) != len(total_forces):
                    print('Force plate '+str(i)+' has '+str(len(forces))+' frames of force_plate_raw_forces, but trial has '+str(len(total_forces))+' frames of total_forces')
                assert (len(forces) == len(total_forces))
                if len(moments) != len(total_forces):
                    print('Force plate ' + str(i) + ' has ' + str(len(moments)) + ' frames of force_plate_raw_moments, but trial has ' + str(len(total_forces)) + ' frames of total_forces')
                assert (len(moments) == len(total_forces))
                for t in range(len(total_forces)):
                    total_forces[t] += np.linalg.norm(forces[t]) + np.linalg.norm(moments[t])
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
        self.error: bool = False
        self.error_msg = ''
        self.original_marker_observations: List[Dict[str, np.ndarray]] = []
        self.missing_grf_manual_review: List[nimble.biomechanics.MissingGRFStatus] = self.parent.missing_grf_manual_review[self.start:self.end]
        self.missing_grf_reason: List[nimble.biomechanics.MissingGRFReason] = [nimble.biomechanics.MissingGRFReason.notMissingGRF for _ in range(self.end - self.start)]
        for i in range(len(self.missing_grf_manual_review)):
            if self.missing_grf_manual_review[i] == nimble.biomechanics.MissingGRFStatus.yes:
                self.missing_grf_reason[i] = nimble.biomechanics.MissingGRFReason.manualReview
        # Make a deep copy of the marker observations, so we can modify them without affecting the parent trial
        for obs in self.parent.marker_observations[self.start:self.end]:
            obs_copy = {}
            for marker in obs:
                obs_copy[marker] = obs[marker].copy()
            self.original_marker_observations.append(obs_copy)
        self.force_plates: List[nimble.biomechanics.ForcePlate] = []
        self.force_plate_raw_cops: List[List[np.ndarray]] = []
        self.force_plate_raw_forces: List[List[np.ndarray]] = []
        self.force_plate_raw_moments: List[List[np.ndarray]] = []
        print('Segmenting trial segment '+str(self.start)+' to '+str(self.end))
        for i, plate in enumerate(self.parent.force_plates):
            new_plate = nimble.biomechanics.ForcePlate.copyForcePlate(plate)
            print('Copying force plate '+str(i))
            if len(new_plate.forces) > 0:
                assert(len(new_plate.forces) == len(self.parent.marker_observations))
                new_plate.trimToIndexes(self.start, self.end)
                assert(len(new_plate.forces) == len(self.original_marker_observations))
            raw_cops = self.parent.force_plate_raw_cops[i][self.start:self.end]
            raw_forces = self.parent.force_plate_raw_forces[i][self.start:self.end]
            print('Num non-zero forces: '+str(len([force for force in raw_forces if np.linalg.norm(force) > 1e-3])))
            raw_moments = self.parent.force_plate_raw_moments[i][self.start:self.end]
            self.force_plates.append(new_plate)
            new_plate.forces = raw_forces
            self.force_plate_raw_forces.append(raw_forces)
            new_plate.centersOfPressure = raw_cops
            self.force_plate_raw_cops.append(raw_cops)
            new_plate.moments = raw_moments
            self.force_plate_raw_moments.append(raw_moments)
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

        # Set an error if there are no marker data frames
        if len(self.marker_observations) == 0:
            self.error = True
            self.error_msg = 'No marker data frames found'

        # Set an error if there are any NaNs in the marker data
        for t in range(len(self.marker_observations)):
            for marker in self.marker_observations[t]:
                if np.any(np.isnan(self.marker_observations[t][marker])):
                    self.error = True
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