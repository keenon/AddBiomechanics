import os
import unittest
import nimblephysics as nimble
from typing import List
import numpy as np
from nimblephysics.loader import absPath
from helpers import detectNonZeroForceSegments, filterNonZeroForceSegments

DATA_FOLDER_PATH = absPath('../data')


class TestTrialSegmentation(unittest.TestCase):
    def test_detectNonZeroForceSegments(self):
        # Create force plate data with intermittent loads.
        timestamps = np.linspace(0, 6.0, 601)
        totalLoad = np.zeros(len(timestamps))

        # Add a legimate load segment.
        totalLoad[50:100] = 1.0
        # Add a load segment that is too short.
        totalLoad[250:254] = 1.0
        # Add two load segments that should be merged together.
        totalLoad[300:340] = 1.0
        totalLoad[360:400] = 1.0
        # Add a segment that has load up until the final time point.
        totalLoad[550:601] = 1.0

        # Detect the non-zero force segments.
        nonzeroForceSegments = detectNonZeroForceSegments(timestamps, totalLoad)

        # Check that the correct segments were detected, before filtering.
        self.assertEqual(len(nonzeroForceSegments), 5)
        self.assertEqual(nonzeroForceSegments[0], (0.5, 1.0))
        self.assertEqual(nonzeroForceSegments[1][0], 2.5)
        self.assertAlmostEqual(nonzeroForceSegments[1][1], 2.54, places=5)
        self.assertEqual(nonzeroForceSegments[2], (3.0, 3.4))
        self.assertEqual(nonzeroForceSegments[3], (3.6, 4.0))
        self.assertEqual(nonzeroForceSegments[4], (5.5, 6.0))

        # Now filter the segments.
        nonzeroForceSegments = filterNonZeroForceSegments(nonzeroForceSegments, 0.05, 1.0)

        # Check that the correct segments were detected, after filtering.
        self.assertEqual(len(nonzeroForceSegments), 3)
        self.assertEqual(nonzeroForceSegments[0], (0.5, 1.0))
        self.assertEqual(nonzeroForceSegments[1], (3.0, 4.0))
        self.assertEqual(nonzeroForceSegments[2], (5.5, 6.0))

    def test_Camargo2021(self):
        # Load the data.
        trcFilePath = DATA_FOLDER_PATH + '/Camargo2021/levelground_ccw_fast_01_01.trc'
        grfFilePath = DATA_FOLDER_PATH + '/Camargo2021/levelground_ccw_fast_01_01_grf.mot'
        trcFile: nimble.biomechanics.OpenSimTRC = nimble.biomechanics.OpenSimParser.loadTRC(trcFilePath)
        forcePlates: List[nimble.biomechanics.ForcePlate] = nimble.biomechanics.OpenSimParser.loadGRF(
            grfFilePath, trcFile.framesPerSecond)

        # Compute the total load.
        totalLoad = np.zeros(len(forcePlates[0].timestamps))
        for itime in range(len(totalLoad)):
            totalForce = 0
            totalMoment = 0
            for forcePlate in forcePlates:
                totalForce += np.linalg.norm(forcePlate.forces[itime])
                totalMoment += np.linalg.norm(forcePlate.moments[itime])
            totalLoad[itime] = totalForce + totalMoment

        # Detect the non-zero force segments.
        nonzeroForceSegments = detectNonZeroForceSegments(forcePlates[0].timestamps, totalLoad)

        # Filter the segments.
        nonzeroForceSegments = filterNonZeroForceSegments(nonzeroForceSegments, 0.05, 1.0)

        # Check that the correct segments were detected.
        self.assertEqual(len(nonzeroForceSegments), 3)
        self.assertEqual(nonzeroForceSegments[0], (0.005, 5.92))
        self.assertEqual(nonzeroForceSegments[1], (7.365, 8.455))
        self.assertEqual(nonzeroForceSegments[2], (11.895, 15.335))


if __name__ == '__main__':
    unittest.main()