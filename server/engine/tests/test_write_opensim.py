import nimblephysics as nimble
import unittest
import os
from inspect import getsourcefile
import shutil
from outputs.opensim_writer import write_opensim_results
import tempfile

TESTS_PATH = os.path.dirname(getsourcefile(lambda:0))
TEST_DATA_PATH = os.path.join(TESTS_PATH, 'data')


class TestWriteOpenSim(unittest.TestCase):
    def test_write_opensim(self):
        path = os.path.join(TEST_DATA_PATH, 'b3ds', 'falisse2017_small.b3d')
        subject = nimble.biomechanics.SubjectOnDisk(path)
        subject.loadAllFrames(doNotStandardizeForcePlateData=True)

        # output_folder = os.path.join(TEST_DATA_PATH, 'temp_opensim_results')
        # write_opensim_results(subject, output_folder)

        # Create a temporary directory to store the OpenSim results
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"Temporary directory created: {temp_dir}")

            write_opensim_results(subject, temp_dir)
