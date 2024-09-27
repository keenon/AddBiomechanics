import nimblephysics as nimble
import unittest
import os
from inspect import getsourcefile
import shutil
from passes.missing_grf_detection import missing_grf_detection
import tempfile

TESTS_PATH = os.path.dirname(getsourcefile(lambda:0))
TEST_DATA_PATH = os.path.join(TESTS_PATH, 'data')


class TestMissingGRFDetection(unittest.TestCase):
    def test_missing_grf_detection(self):
        path = os.path.join(TEST_DATA_PATH, 'b3ds', 'falisse2017_small.b3d')
        subject = nimble.biomechanics.SubjectOnDisk(path)
        subject.loadAllFrames(doNotStandardizeForcePlateData=True)

        # output_folder = os.path.join(TEST_DATA_PATH, 'temp_opensim_results')
        # write_opensim_results(subject, output_folder)

        num_passes = subject.getNumProcessingPasses()
        missing_grf_detection(subject)
        num_passes_after = subject.getNumProcessingPasses()

        # This shouldn't add a pass
        self.assertEqual(num_passes, num_passes_after)