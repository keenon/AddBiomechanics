import nimblephysics as nimble
import numpy as np
from typing import List, Tuple
from bad_frames_detector.thresholds import ThresholdsDetector


def missing_grf_detection(subject: nimble.biomechanics.SubjectOnDisk):
    """
    Detects missing GRFs in the subject and sets the missing GRF reason in the trial proto. This then allows the
    dynamics fitter to know that certain frames should be excluded from the dynamics fitting, because they have bad or
    missing ground reaction force numbers, and if we used them to try to fit the dynamics, we would get weird center of
    mass trajectories (probably ones that want to fall through the floor, because we are missing the ground reaction
    forces that are supposed to be holding the body up).
    """
    detector = ThresholdsDetector()
    missing_grf: List[List[nimble.biomechanics.MissingGRFReason]] = detector.estimate_missing_grfs(subject, list(
        range(subject.getNumTrials())))
    header_proto = subject.getHeaderProto()
    trial_protos = header_proto.getTrials()
    for i in range(subject.getNumTrials()):
        trial_protos[i].setMissingGRFReason(missing_grf[i])