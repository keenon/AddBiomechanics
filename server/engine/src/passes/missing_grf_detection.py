import nimblephysics as nimble
import numpy as np
from typing import List, Tuple
from bad_frames_detector.thresholds import ThresholdsDetector


def missing_grf_detection(subject: nimble.biomechanics.SubjectOnDisk):
    detector = ThresholdsDetector()
    missing_grf: List[List[nimble.biomechanics.MissingGRFReason]] = detector.estimate_missing_grfs(subject, list(
        range(subject.getNumTrials())))
    header_proto = subject.getHeaderProto()
    trial_protos = header_proto.getTrials()
    for i in range(subject.getNumTrials()):
        trial_protos[i].setMissingGRFReason(missing_grf[i])