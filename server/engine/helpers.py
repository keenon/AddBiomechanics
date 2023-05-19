import os
def detectNonZeroForceSegments(timestamps, totalLoad):
    # Scan through the timestamps in the force data and find segments longer than a certain threshold that
    # have zero forces.
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
                    (nonzeroForceSegmentStart, timestamps[itime]))
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


def getConsecutiveValues(data):
    from operator import itemgetter
    from itertools import groupby
    ranges = []
    for key, group in groupby(enumerate(data), lambda x: x[0]-x[1]):
        group = list(map(itemgetter(1), group))
        ranges.append((group[0], group[-1]))

    return ranges
