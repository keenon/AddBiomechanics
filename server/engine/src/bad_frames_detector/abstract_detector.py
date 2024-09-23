import nimblephysics as nimble
from typing import List
from subject import Subject
from trial import TrialSegment


class AbstractDetector:
    def __init__(self):
        pass

    def estimate_missing_grfs(self, subject: Subject, trial_segments: List[TrialSegment]) -> List[List[nimble.biomechanics.MissingGRFReason]]:
        result: List[List[nimble.biomechanics.MissingGRFReason]] = []
        for trial in trial_segments:
            trial_len = len(trial.marker_observations)
            all_missing = [nimble.biomechanics.MissingGRFReason.manualReview] * trial_len
            result.append(all_missing)
        return result
