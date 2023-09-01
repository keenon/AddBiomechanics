import unittest
from src.trial import Trial
import numpy as np
import nimblephysics as nimble
from typing import List, Dict, Tuple
import os


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
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        trial.force_plates.append(new_force_plate)

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
        for _ in range(60):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        trial.force_plates.append(new_force_plate)

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
        for _ in range(40):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
        for _ in range(20):
            forces.append(np.zeros(3))
            moments.append(np.zeros(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        trial.force_plates.append(new_force_plate)

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
        for _ in range(20):
            forces.append(np.zeros(3))
            moments.append(np.zeros(3))
        for _ in range(40):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        trial.force_plates.append(new_force_plate)

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

    def test_short_forces_gapfill(self):
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
        for _ in range(20):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
        for _ in range(20):
            forces.append(np.zeros(3))
            moments.append(np.zeros(3))
        for _ in range(20):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        trial.force_plates.append(new_force_plate)

        trial.split_segments(max_grf_gap_fill_size=25 * trial.timestep)

        self.assertEqual(1, len(trial.segments))
        self.assertEqual(0, trial.segments[0].start)
        self.assertEqual(60, trial.segments[0].end)
        self.assertEqual(True, trial.segments[0].has_markers)
        self.assertEqual(True, trial.segments[0].has_forces)

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
        for _ in range(20):
            forces.append(np.zeros(3))
            moments.append(np.zeros(3))
        for _ in range(20):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
        for _ in range(20):
            forces.append(np.zeros(3))
            moments.append(np.zeros(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        trial.force_plates.append(new_force_plate)

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
        for _ in range(60):
            forces.append(np.ones(3))
            moments.append(np.ones(3))
        new_force_plate.forces = forces
        new_force_plate.moments = moments
        trial.force_plates.append(new_force_plate)

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

    def test_load_trials(self):
        trial = Trial.load_trial('walking2', os.path.abspath('../test_data/opencap_test_original/trials/walking2'))
        self.assertEqual(False, trial.error)
        trial.split_segments()
        self.assertEqual(1, len(trial.segments))
