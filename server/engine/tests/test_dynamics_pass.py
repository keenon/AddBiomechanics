import nimblephysics as nimble
import unittest
import os
from inspect import getsourcefile
from dynamics_pass.dynamics_pass import dynamics_pass
from dynamics_pass.classification_pass import classification_pass
from dynamics_pass.missing_grf_detection import missing_grf_detection
from dynamics_pass.acceleration_minimizing_pass import add_acceleration_minimizing_pass
import numpy as np

TESTS_PATH = os.path.dirname(getsourcefile(lambda:0))
TEST_DATA_PATH = os.path.join(TESTS_PATH, 'data')


class TestDynamicsPass(unittest.TestCase):
    def test_acceleration_minimizing_pass(self):
        path = os.path.join(TEST_DATA_PATH, 'b3ds', 'falisse2017_small.b3d')
        subject = nimble.biomechanics.SubjectOnDisk(path)
        subject.loadAllFrames(doNotStandardizeForcePlateData=True)
        subject.getHeaderProto().trimToProcessingPasses(1)

        num_passes = subject.getNumProcessingPasses()
        add_acceleration_minimizing_pass(subject)
        num_passes_after = subject.getNumProcessingPasses()

        self.assertEqual(num_passes + 1, num_passes_after)

        trial_protos = subject.getHeaderProto().getTrials()

        for i in range(len(trial_protos)):
            trial_proto = trial_protos[i]
            passes = trial_proto.getPasses()
            acc_norm_before = np.linalg.norm(passes[num_passes-1].getAccs())
            acc_norm_after = np.linalg.norm(passes[num_passes_after-1].getAccs())
            self.assertLessEqual(acc_norm_after, acc_norm_before)

    def test_classification(self):
        path = os.path.join(TEST_DATA_PATH, 'b3ds', 'falisse2017_small.b3d')
        subject = nimble.biomechanics.SubjectOnDisk(path)
        subject.loadAllFrames(doNotStandardizeForcePlateData=True)

        num_passes = subject.getNumProcessingPasses()
        classification_pass(subject)
        num_passes_after = subject.getNumProcessingPasses()

        # This shouldn't add a pass
        self.assertEqual(num_passes, num_passes_after)

        self.assertEqual(subject.getHeaderProto().getTrials()[0].getBasicTrialType(), nimble.biomechanics.BasicTrialType.OVERGROUND)

    def test_missing_grf_detection(self):
        path = os.path.join(TEST_DATA_PATH, 'b3ds', 'falisse2017_small.b3d')
        subject = nimble.biomechanics.SubjectOnDisk(path)
        subject.loadAllFrames(doNotStandardizeForcePlateData=True)

        num_passes = subject.getNumProcessingPasses()
        missing_grf_detection(subject)
        num_passes_after = subject.getNumProcessingPasses()

        # This shouldn't add a pass
        self.assertEqual(num_passes, num_passes_after)

        # TODO: It would be nice to have a more elaborate test here for which GRFs are missing.

    def test_dynamics_pass(self):
        path = os.path.join(TEST_DATA_PATH, 'b3ds', 'falisse2017_small.b3d')
        subject = nimble.biomechanics.SubjectOnDisk(path)
        subject.loadAllFrames(doNotStandardizeForcePlateData=True)

        num_passes = subject.getNumProcessingPasses()
        dynamics_pass(subject)
        num_passes_after = subject.getNumProcessingPasses()

        self.assertEqual(num_passes + 1, num_passes_after)

        # TODO: It would be nice to have a more elaborate test here for what the dynamics pass does.
