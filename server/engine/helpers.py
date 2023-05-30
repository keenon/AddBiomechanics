def getConsecutiveValues(data):
    from operator import itemgetter
    from itertools import groupby
    ranges = []
    for key, group in groupby(enumerate(data), lambda x: x[0]-x[1]):
        group = list(map(itemgetter(1), group))
        ranges.append((group[0], group[-1]))

    return ranges


def detectNonZeroForceSegments(timestamps, totalLoad):
    # Scan through the timestamps in the force data and find segments longer than a certain threshold that
    # have non-zero forces.
    nonzeroForceSegments = []
    nonzeroForceSegmentStart = None
    for itime in range(len(timestamps)):
        if totalLoad[itime] > 1e-3:
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


def filterNonZeroForceSegments(nonzeroForceSegments, minSegmentDuration, mergeZeroForceSegmentsThreshold):
    # Remove segments that are too short.
    nonzeroForceSegments = [seg for seg in nonzeroForceSegments if seg[1] - seg[0] > minSegmentDuration]

    # Merge adjacent non-zero force segments that are within a certain time threshold.
    mergedNonzeroForceSegments = []
    mergedNonzeroForceSegments.append(nonzeroForceSegments[0])
    for iseg in range(1, len(nonzeroForceSegments)):
        zeroForceSegment = nonzeroForceSegments[iseg][0] - nonzeroForceSegments[iseg - 1][1]
        if zeroForceSegment < mergeZeroForceSegmentsThreshold:
            mergedNonzeroForceSegments[-1] = (
                mergedNonzeroForceSegments[-1][0], nonzeroForceSegments[iseg][1])
        else:
            mergedNonzeroForceSegments.append(
                nonzeroForceSegments[iseg])

    return mergedNonzeroForceSegments


def detectMarkeredSegments(timestamps, markers):
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


def reconcileMarkeredAndNonzeroForceSegments(timestamps, markeredSegments, nonzeroForceSegments):
    import numpy as np

    # Create boolean arrays of length timestamps that is True if the timestamp is in a markered or nonzero force segment.
    markeredTimestamps = np.zeros(len(timestamps), dtype=bool)
    nonzeroForceTimestamps = np.zeros(len(timestamps), dtype=bool)
    for itime in range(len(timestamps)):
        for markeredSegment in markeredSegments:
            if markeredSegment[0] <= timestamps[itime] <= markeredSegment[-1]:
                markeredTimestamps[itime] = True
                break

        for nonzeroForceSegment in nonzeroForceSegments:
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
