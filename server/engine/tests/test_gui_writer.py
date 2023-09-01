import unittest
from src.gui_writer import save_trial_segment_to_gui
from src.trial import TrialSegment, Trial
import os

class TestGuiWriter(unittest.TestCase):
    def test_gui_simple(self):
        trial = Trial.load_trial('walking2', os.path.abspath('../test_data/opencap_test_original/trials/walking2'))
        self.assertEqual(False, trial.error)
        trial.split_segments()
        # save_trial_segment_to_gui('test.bin', trial.segments[0])
        save_trial_segment_to_gui(os.path.abspath('../../../../nimblephysics/javascript/src/data/movement2.bin'), trial.segments[0])
