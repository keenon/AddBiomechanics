import shutil
import unittest
from src.kinematics_pass.subject import Subject
from src.kinematics_pass.trial import TrialSegment, Trial
from typing import Dict, List, Any
import os
import nimblephysics as nimble
from inspect import getsourcefile
from src.utilities.scale_opensim_model import scale_opensim_model

TESTS_PATH = os.path.dirname(getsourcefile(lambda:0))
DATA_FOLDER_PATH = os.path.join(TESTS_PATH, '..', '..', 'data')
TEST_DATA_PATH = os.path.join(TESTS_PATH, 'data')

def reset_test_data(name: str):
    original_path = os.path.join(TEST_DATA_PATH, f'{name}_original')
    live_path = os.path.join(TEST_DATA_PATH, name)
    if os.path.exists(live_path):
        shutil.rmtree(live_path)
    shutil.copytree(original_path, live_path)


class TestScaleOsim(unittest.TestCase):
    def test_rescale_osim_model(self):
        subject = Subject()
        reset_test_data('opencap_test')
        subject.load_folder(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_FOLDER_PATH)
        subject.kinematics_skeleton = subject.skeleton
        print(os.path.join(TEST_DATA_PATH, 'opencap_test', 'unscaled_generic.osim'))
        self.assertTrue(os.path.exists(os.path.join(TEST_DATA_PATH, 'opencap_test', 'unscaled_generic.osim')))
        mass_kg = subject.skeleton.getMass()
        height_m = 1.65
        with open(os.path.join(TEST_DATA_PATH, 'opencap_test', 'unscaled_generic.osim'), 'r') as f:
            unscaled_generic_osim_text = f.read()
        new_xml = scale_opensim_model(unscaled_generic_osim_text, subject.skeleton, mass_kg, height_m, subject.markerSet)
        self.assertTrue(new_xml is not None)
        self.assertTrue(len(new_xml) > 0)
