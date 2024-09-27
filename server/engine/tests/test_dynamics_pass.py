import nimblephysics as nimble
import unittest
import os
from inspect import getsourcefile
import shutil
from passes.dynamics_pass import dynamics_pass
import tempfile

TESTS_PATH = os.path.dirname(getsourcefile(lambda:0))
TEST_DATA_PATH = os.path.join(TESTS_PATH, 'data')


class TestDynamicsPass(unittest.TestCase):
    def test_dynamics_pass(self):
        path = os.path.join(TEST_DATA_PATH, 'b3ds', 'falisse2017_small.b3d')
        subject = nimble.biomechanics.SubjectOnDisk(path)
        subject.loadAllFrames(doNotStandardizeForcePlateData=True)

        # output_folder = os.path.join(TEST_DATA_PATH, 'temp_opensim_results')
        # write_opensim_results(subject, output_folder)

        num_passes = subject.getNumProcessingPasses()
        dynamics_pass(subject)
        num_passes_after = subject.getNumProcessingPasses()

        self.assertEqual(num_passes + 1, num_passes_after)