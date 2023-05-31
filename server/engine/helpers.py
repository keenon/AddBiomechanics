"""
helpers.py
----------
Description: Helper functions used by the AddBiomechanics processing engine.
Author(s): Nicholas Bianco
"""


def get_consecutive_values(data):
    from operator import itemgetter
    from itertools import groupby
    ranges = []
    for key, group in groupby(enumerate(data), lambda x: x[0]-x[1]):
        group = list(map(itemgetter(1), group))
        ranges.append((group[0], group[-1]))

    return ranges


def detect_nonzero_force_segments(timestamps, total_load):
    # Scan through the timestamps in the force data and find segments longer than a certain threshold that
    # have non-zero forces.
    nonzeroForceSegments = []
    nonzeroForceSegmentStart = None
    for itime in range(len(timestamps)):
        if total_load[itime] > 1e-3:
            if nonzeroForceSegmentStart is None:
                nonzeroForceSegmentStart = timestamps[itime]
            elif nonzeroForceSegmentStart is not None and itime == len(timestamps) - 1:
                nonzeroForceSegments.append(
                    (nonzeroForceSegmentStart, timestamps[itime]))
                nonzeroForceSegmentStart = None
        else:
            if nonzeroForceSegmentStart is not None:
                nonzeroForceSegments.append(
                    (nonzeroForceSegmentStart, timestamps[itime-1]))
                nonzeroForceSegmentStart = None

    return nonzeroForceSegments


def filter_nonzero_force_segments(nonzero_force_segments, min_segment_duration, merge_zero_force_segments_threshold):
    # Remove segments that are too short.
    nonzero_force_segments = [seg for seg in nonzero_force_segments if seg[1] - seg[0] > min_segment_duration]

    # Merge adjacent non-zero force segments that are within a certain time threshold.
    mergedNonzeroForceSegments = [nonzero_force_segments[0]]
    for iseg in range(1, len(nonzero_force_segments)):
        zeroForceSegment = nonzero_force_segments[iseg][0] - nonzero_force_segments[iseg - 1][1]
        if zeroForceSegment < merge_zero_force_segments_threshold:
            mergedNonzeroForceSegments[-1] = (
                mergedNonzeroForceSegments[-1][0], nonzero_force_segments[iseg][1])
        else:
            mergedNonzeroForceSegments.append(
                nonzero_force_segments[iseg])

    return mergedNonzeroForceSegments


def detect_markered_segments(timestamps, markers):
    # Scan through the timestamps in the marker data and find segments longer than a certain threshold that
    # have zero forces.
    markeredSegments = []
    markeredSegmentStart = None
    for itime in range(len(timestamps)):
        if len(markers[itime]) > 0:
            if markeredSegmentStart is None:
                markeredSegmentStart = timestamps[itime]
            elif markeredSegmentStart is not None and itime == len(timestamps) - 1:
                markeredSegments.append(
                    (markeredSegmentStart, timestamps[itime]))
                markeredSegmentStart = None
        else:
            if markeredSegmentStart is not None:
                markeredSegments.append(
                    (markeredSegmentStart, timestamps[itime-1]))
                markeredSegmentStart = None

    return markeredSegments


def reconcile_markered_and_nonzero_force_segments(timestamps, markered_segments, nonzero_force_segments):
    import numpy as np

    # Create boolean arrays of length timestamps that is True if the timestamp is in a markered or nonzero force
    # segment.
    markeredTimestamps = np.zeros(len(timestamps), dtype=bool)
    nonzeroForceTimestamps = np.zeros(len(timestamps), dtype=bool)
    for itime in range(len(timestamps)):
        for markeredSegment in markered_segments:
            if markeredSegment[0] <= timestamps[itime] <= markeredSegment[-1]:
                timestampToCheck = itime
                markeredTimestamps[itime] = True
                break

        for nonzeroForceSegment in nonzero_force_segments:
            if nonzeroForceSegment[0] <= timestamps[itime] <= nonzeroForceSegment[-1]:
                nonzeroForceTimestamps[itime] = True
                break

    # Find the intersection between the markered timestamps and the non-zero force timestamps.
    reconciledTimestamps = np.logical_and(markeredTimestamps, nonzeroForceTimestamps)

    # Create a new set of segments from the reconciled timestamps.
    reconciledSegments = []
    reconciledSegmentStart = None
    for itime in range(len(timestamps)):
        if reconciledTimestamps[itime]:
            if reconciledSegmentStart is None:
                reconciledSegmentStart = timestamps[itime]
            elif reconciledSegmentStart is not None and itime == len(timestamps) - 1:
                reconciledSegments.append(
                    (reconciledSegmentStart, timestamps[itime]))
                reconciledSegmentStart = None
        else:
            if reconciledSegmentStart is not None:
                reconciledSegments.append(
                    (reconciledSegmentStart, timestamps[itime-1]))
                reconciledSegmentStart = None

    return reconciledSegments
