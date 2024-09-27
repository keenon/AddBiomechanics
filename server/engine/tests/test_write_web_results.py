import nimblephysics as nimble
import unittest
import os
from inspect import getsourcefile
import shutil
from outputs.web_results_writer import write_web_results
import tempfile

TESTS_PATH = os.path.dirname(getsourcefile(lambda:0))
TEST_DATA_PATH = os.path.join(TESTS_PATH, 'data')
GEOMETRY_PATH = os.path.join(TESTS_PATH, '..', 'Geometry') + '/'


class TestWriteWebResults(unittest.TestCase):
    def test_write_web_results(self):
        path = os.path.join(TEST_DATA_PATH, 'b3ds', 'falisse2017_small.b3d')
        subject = nimble.biomechanics.SubjectOnDisk(path)
        subject.loadAllFrames(doNotStandardizeForcePlateData=True)

        # Create a temporary directory to store the web results
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"Temporary directory created: {temp_dir}")

            write_web_results(subject, GEOMETRY_PATH, temp_dir)
