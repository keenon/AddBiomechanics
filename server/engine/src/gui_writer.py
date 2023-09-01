from src.trial import TrialSegment
import nimblephysics as nimble
import numpy as np


def save_trial_segment_to_gui(path: str, segment: TrialSegment):
    """
    Write this trial segment to a file that can be read by the 3D web GUI
    """
    gui = nimble.server.GUIRecording()

    # 1. Even if we never actually loaded anything else, at a bare minimum we should render the markers
    markers = set()
    for obs in segment.marker_observations:
        for key in obs:
            markers.add(key)
    for marker in markers:
        gui.createBox('marker_'+str(marker), np.ones(3, dtype=np.float64) * 0.02, np.zeros(3, dtype=np.float64), np.zeros(3, dtype=np.float64), [0.5, 0.5, 0.5, 1.0])
        gui.setObjectTooltip('marker_'+str(marker), str(marker))

    for t in range(len(segment.marker_observations)):
        # 1. Even if we never actually loaded anything else, at a bare minimum we should render the markers
        for marker in segment.marker_observations[t]:
            gui.setObjectPosition('marker_'+str(marker), segment.marker_observations[t][marker])
        gui.saveFrame()

    gui.setFramesPerSecond(int(1.0 / segment.parent.timestep))
    gui.writeFramesJson(path)
