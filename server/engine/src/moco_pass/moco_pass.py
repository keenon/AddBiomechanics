import nimblephysics as nimble
import numpy as np
from typing import List, Tuple


def moco_pass(subject: nimble.biomechanics.SubjectOnDisk):
    """
    This function is responsible for running the Moco pass on the subject.
    """

    header_proto = subject.getHeaderProto()
    trial_protos = header_proto.getTrials()
    num_trials = subject.getNumTrials()

    osim = subject.readOpenSimFile(subject.getNumProcessingPasses()-1, ignoreGeometry=True)
    skel = osim.skeleton
    markers_map = osim.markersMap

    # Filter 
    # moco_trials: List[int] = []
    # for i in range(subject.getNumTrials()):
    #     missing_grf = trial_protos[i].getMissingGRFReason()
    #     num_not_missing = sum(
    #         [missing == nimble.biomechanics.MissingGRFReason.notMissingGRF for missing in missing_grf])
    #     print(f"Trial {i} has {num_not_missing} frames of good GRF data")
    #     if num_not_missing < 50:
    #         print(f"Trial {i} has less than 50 frames of good GRF data. Skipping dynamics optimization.")
    #         continue
    #     # Run the dynamics optimization
    #     print('Running dynamics optimization on trial ' + str(i) + '/' + str(num_trials))
    #     dynamics_trials.append(i)