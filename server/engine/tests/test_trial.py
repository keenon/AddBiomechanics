import json
import unittest
from kinematics_pass.trial import Trial, TrialSegment
import numpy as np
import nimblephysics as nimble
from typing import List, Dict, Any
import os
from inspect import getsourcefile

TESTS_PATH = os.path.dirname(getsourcefile(lambda:0))
TEST_DATA_PATH = os.path.join(TESTS_PATH, 'data')

class TestTrial(unittest.TestCase):
    def test_trivial_split(self):
        trial = Trial()
        trial.marker_observations = [
            {
                'a': np.zeros(3),
                'b': np.zeros(3),
            }
        ]

        new_force_plate = nimble.biomechanics.ForcePlate()
        forces = [np.ones(3)]
        moments = [np.ones(3)]
        cops = [np.ones(3)]
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        new_force_plate.centersOfPressure = cops
        new_force_plate.timestamps = [0.0]
        trial.set_force_plates([new_force_plate])

        trial.split_segments()

        self.assertEqual(1, len(trial.segments))
        self.assertEqual(trial.segments[0].start, 0)
        self.assertEqual(trial.segments[0].end, len(trial.marker_observations))
        self.assertEqual(trial.segments[0].has_markers, True)
        self.assertEqual(trial.segments[0].has_forces, True)

    def test_markerless_split(self):
        trial = Trial()
        trial.marker_observations = [
                                        {
                                            'a': np.zeros(3),
                                            'b': np.zeros(3),
                                        }
                                    ] * 40 + [{}] * 20

        new_force_plate = nimble.biomechanics.ForcePlate()
        forces = []
        moments = []
        cops = []
        for _ in range(60):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
            cops.append(np.ones(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        new_force_plate.centersOfPressure = cops
        new_force_plate.timestamps = range(60)
        trial.set_force_plates([new_force_plate])

        trial.split_segments()

        self.assertEqual(2, len(trial.segments))
        self.assertEqual(trial.segments[0].start, 0)
        self.assertEqual(trial.segments[0].end, 40)
        self.assertEqual(trial.segments[0].has_markers, True)
        self.assertEqual(trial.segments[0].has_forces, True)
        self.assertEqual(trial.segments[1].start, 40)
        self.assertEqual(trial.segments[1].end, 60)
        self.assertEqual(trial.segments[1].has_markers, False)
        self.assertEqual(trial.segments[1].has_forces, True)

    def test_forceless_split(self):
        trial = Trial()
        trial.marker_observations = [
                                        {
                                            'a': np.zeros(3),
                                            'b': np.zeros(3),
                                        }
                                    ] * 60

        new_force_plate = nimble.biomechanics.ForcePlate()
        forces: List[np.ndarray] = []
        moments: List[np.ndarray] = []
        cops: List[np.ndarray] = []
        for _ in range(40):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
            cops.append(np.zeros(3))
        for _ in range(20):
            forces.append(np.zeros(3))
            moments.append(np.zeros(3))
            cops.append(np.zeros(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        new_force_plate.centersOfPressure = cops
        new_force_plate.timestamps = range(60)
        trial.set_force_plates([new_force_plate])

        trial.split_segments(max_grf_gap_fill_size=0.0)

        self.assertEqual(2, len(trial.segments))
        self.assertEqual(trial.segments[0].start, 0)
        self.assertEqual(trial.segments[0].end, 40)
        self.assertEqual(trial.segments[0].has_markers, True)
        self.assertEqual(trial.segments[0].has_forces, True)
        self.assertEqual(trial.segments[1].start, 40)
        self.assertEqual(trial.segments[1].end, 60)
        self.assertEqual(trial.segments[1].has_markers, True)
        self.assertEqual(trial.segments[1].has_forces, False)

    def test_forces_markerless_split(self):
        trial = Trial()
        trial.marker_observations = [
                                        {
                                            'a': np.zeros(3),
                                            'b': np.zeros(3),
                                        }
                                    ] * 40 + [{}] * 20

        new_force_plate = nimble.biomechanics.ForcePlate()
        forces = []
        moments = []
        cops = []
        for _ in range(20):
            forces.append(np.zeros(3))
            moments.append(np.zeros(3))
            cops.append(np.zeros(3))
        for _ in range(40):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
            cops.append(np.zeros(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        new_force_plate.centersOfPressure = cops
        new_force_plate.timestamps = range(60)
        trial.set_force_plates([new_force_plate])

        trial.split_segments(max_grf_gap_fill_size=0.0)

        self.assertEqual(3, len(trial.segments))
        self.assertEqual(0, trial.segments[0].start)
        self.assertEqual(20, trial.segments[0].end)
        self.assertEqual(True, trial.segments[0].has_markers)
        self.assertEqual(False, trial.segments[0].has_forces)
        self.assertEqual(20, trial.segments[1].start)
        self.assertEqual(40, trial.segments[1].end)
        self.assertEqual(True, trial.segments[1].has_markers)
        self.assertEqual(True, trial.segments[1].has_forces)
        self.assertEqual(40, trial.segments[2].start)
        self.assertEqual(60, trial.segments[2].end)
        self.assertEqual(False, trial.segments[2].has_markers)
        self.assertEqual(True, trial.segments[2].has_forces)

    # TODO this test segfaults

    # def test_short_forces_gapfill(self):   

    #     trial = Trial()
    #     trial.marker_observations = [
    #                                     {
    #                                         'a': np.zeros(3),
    #                                         'b': np.zeros(3),
    #                                     }
    #                                 ] * 60

    #     new_force_plate = nimble.biomechanics.ForcePlate()
    #     forces = []
    #     moments = []
    #     for _ in range(20):
    #         forces.append(np.ones(3))
    #         moments.append(np.ones(3))
    #     for _ in range(20):
    #         forces.append(np.zeros(3))
    #         moments.append(np.zeros(3))
    #     for _ in range(20):
    #         forces.append(np.ones(3))
    #         moments.append(np.ones(3))
    #     new_force_plate.forces = forces
    #     new_force_plate.moments = moments
    #     trial.set_force_plates([new_force_plate])

    #     trial.split_segments(max_grf_gap_fill_size=25 * trial.timestep)

    #     self.assertEqual(1, len(trial.segments))
    #     self.assertEqual(0, trial.segments[0].start)
    #     self.assertEqual(60, trial.segments[0].end)
    #     self.assertEqual(True, trial.segments[0].has_markers)
    #     self.assertEqual(True, trial.segments[0].has_forces)

    def test_short_forces_gapfill_ends(self):
        trial = Trial()
        trial.marker_observations = [
                                        {
                                            'a': np.zeros(3),
                                            'b': np.zeros(3),
                                        }
                                    ] * 60

        new_force_plate = nimble.biomechanics.ForcePlate()
        forces = []
        moments = []
        cops = []
        for _ in range(20):
            forces.append(np.zeros(3))
            moments.append(np.zeros(3))
            cops.append(np.zeros(3))
        for _ in range(20):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
            cops.append(np.ones(3))
        for _ in range(20):
            forces.append(np.zeros(3))
            moments.append(np.zeros(3))
            cops.append(np.zeros(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        new_force_plate.centersOfPressure = cops
        trial.set_force_plates([new_force_plate])

        trial.split_segments(max_grf_gap_fill_size=25 * trial.timestep)

        self.assertEqual(1, len(trial.segments))
        self.assertEqual(0, trial.segments[0].start)
        self.assertEqual(60, trial.segments[0].end)
        self.assertEqual(True, trial.segments[0].has_markers)
        self.assertEqual(True, trial.segments[0].has_forces)

    def test_split_long_trial(self):
        trial = Trial()
        trial.marker_observations = [
                                        {
                                            'a': np.zeros(3),
                                            'b': np.zeros(3),
                                        }
                                    ] * 60

        new_force_plate = nimble.biomechanics.ForcePlate()
        forces = []
        moments = []
        cops = []
        for _ in range(60):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
            cops.append(np.ones(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        new_force_plate.centersOfPressure = cops
        new_force_plate.timestamps = range(60)
        trial.set_force_plates([new_force_plate])

        trial.split_segments(max_segment_frames=25)

        self.assertEqual(3, len(trial.segments))
        self.assertEqual(0, trial.segments[0].start)
        self.assertEqual(25, trial.segments[0].end)
        self.assertEqual(True, trial.segments[0].has_markers)
        self.assertEqual(True, trial.segments[0].has_forces)
        self.assertEqual(25, trial.segments[1].start)
        self.assertEqual(50, trial.segments[1].end)
        self.assertEqual(True, trial.segments[1].has_markers)
        self.assertEqual(True, trial.segments[1].has_forces)
        self.assertEqual(50, trial.segments[2].start)
        self.assertEqual(60, trial.segments[2].end)
        self.assertEqual(True, trial.segments[2].has_markers)
        self.assertEqual(True, trial.segments[2].has_forces)

    # TODO: This test fails because only one segment is created. Likely due to something
    # related to changes in how force plate data thresholds are calculated (almost all
    # time points are detected to have non-zero force plate data).

    # def test_split_initial_off_treadmill(self):
    #     trial_index = 0
    #     trial = Trial.load_trial('initial_off_treadmill', os.path.join(TESTS_PATH, 'data', 'initial_off_treadmill'), trial_index)
    #     trial.split_segments()
    #     self.assertGreater(len(trial.segments), 1)
    #     self.assertTrue(trial.segments[0].has_markers)
    #     self.assertFalse(trial.segments[0].has_forces)
    #     self.assertTrue(trial.segments[1].has_markers)
    #     self.assertTrue(trial.segments[1].has_forces)
    #     pass

    def test_load_trials(self):
        trial_index = 0
        trial = Trial.load_trial('walking1', os.path.join(TEST_DATA_PATH, 'opencap_test_original' ,'trials', 'walking1'), trial_index)
        self.assertEqual(False, trial.error)
        trial.split_segments()
        self.assertEqual(1, len(trial.segments))