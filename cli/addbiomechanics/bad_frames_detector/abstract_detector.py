import nimblephysics as nimble
from typing import List


class AbstractDetector:
    def __init__(self):
        pass

    def estimate_missing_grfs(self, subject: nimble.biomechanics.SubjectOnDisk, trials: List[int]) -> List[List[bool]]:
        result: List[List[bool]] = []
        for trial in trials:
            trial_len = subject.getTrialLength(trial)
            all_missing = [True] * trial_len
            result.append(all_missing)
        return result