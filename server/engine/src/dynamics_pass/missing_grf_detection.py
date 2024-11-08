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
    header_proto = subject.getHeaderProto()
    trial_protos = header_proto.getTrials()

    trials_to_evaluate: List[int] = []
    for i in range(subject.getNumTrials()):
        missing_reasons = trial_protos[i].getMissingGRFReason()
        has_any_manual_review = any([reason == nimble.biomechanics.MissingGRFReason.manualReview for reason in missing_reasons])
        if not has_any_manual_review:
            trials_to_evaluate.append(i)
        else:
            print(f"Trial {i} has been manually reviewed, skipping missing GRF detection...")

    missing_grf: List[List[nimble.biomechanics.MissingGRFReason]] = detector.estimate_missing_grfs(subject, trials_to_evaluate)
    assert len(missing_grf) == len(trials_to_evaluate)
    for i in range(len(missing_grf)):
        trial_protos[trials_to_evaluate[i]].setMissingGRFReason(missing_grf[i])
