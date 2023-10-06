"""
helpers.py
----------
Description: Helper functions used by the AddBiomechanics processing engine.
Author(s): Nicholas Bianco
"""
from typing import List, Tuple, Dict, Any
import numpy as np

def get_consecutive_values(data):
    from operator import itemgetter
    from itertools import groupby
    ranges = []
    for key, group in groupby(enumerate(data), lambda x: x[0]-x[1]):
        group = list(map(itemgetter(1), group))
        ranges.append((group[0], group[-1]))

    return ranges


def detect_nonzero_segments(data: np.ndarray, threshold: float = 0.0) -> List[Tuple[int, int]]:
    # Scan through the data and find segments longer than a certain threshold that
    # have non-zero values.
    nonzero_segments: List[Tuple[int, int]] = []
    nonzero_segment_start: int = -1
    for itime in range(len(data)):
        if data[itime] > threshold:
            if nonzero_segment_start == -1:
                nonzero_segment_start = itime
            elif nonzero_segment_start != -1 and itime == len(data) - 1:
                nonzero_segments.append(
                    (nonzero_segment_start, itime))
                nonzero_segment_start = -1
        else:
            if nonzero_segment_start != -1:
                nonzero_segments.append(
                    (nonzero_segment_start, itime-1))
                nonzero_segment_start = -1
    return nonzero_segments


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


def detect_marker_segments(marker_timesteps: List[Dict[str, Any]]) -> List[Tuple[int, int]]:
    # Scan through the timestamps in the marker data and find segments longer than a certain threshold that
    # have zero forces.
    marker_segments: List[Tuple[int, int]] = []
    marker_segment_start: int = -1
    for itime in range(len(marker_timesteps)):
        if len(marker_timesteps[itime]) > 0:
            if marker_segment_start == -1:
                marker_segment_start = itime
            elif marker_segment_start != -1 and itime == len(marker_timesteps) - 1:
                marker_segments.append(
                    (marker_segment_start, itime))
                marker_segment_start = -1
        else:
            if marker_segment_start != -1:
                marker_segments.append(
                    (marker_segment_start, itime-1))
                marker_segment_start = -1
    return marker_segments


def reconcile_markered_and_nonzero_force_segments(timestamps, markered_segments, nonzero_force_segments):
    import numpy as np

    # Create boolean arrays of length timestamps that is True if the timestamp is in a markered or nonzero force
    # segment.
    markeredTimestamps = np.zeros(len(timestamps), dtype=bool)
    nonzeroForceTimestamps = np.zeros(len(timestamps), dtype=bool)
    for itime in range(len(timestamps)):
        for markeredSegment in markered_segments:
            if markeredSegment[0] <= timestamps[itime] <= markeredSegment[-1]:
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


def update_model_for_moco(model_input_fpath, model_output_fpath):
    import opensim as osim
    # Replace locked coordinates with weld joints.
    model = osim.Model(model_input_fpath)
    model.initSystem()
    coordinates = model.getCoordinateSet()
    locked_joints = list()
    locked_coordinates = list()
    for icoord in range(coordinates.getSize()):
        coord = coordinates.get(icoord)
        if coord.get_locked():
            locked_coordinates.append(coord.getName())
            locked_joints.append(coord.getJoint().getName())

    # Remove actuators associated with removed coordinates.
    for coordinate in locked_coordinates:
        forceSet = model.updForceSet()
        for iforce in range(forceSet.getSize()):
            force = forceSet.get(iforce)
            if force.getConcreteClassName().endswith('CoordinateActuator'):
                actu = osim.CoordinateActuator.safeDownCast(force)
                if actu.get_coordinate() == coordinate:
                    forceSet.remove(iforce)
                    break

    # Print new model to file.
    model.finalizeConnections()
    model.initSystem()
    model.printToXML(model_output_fpath)


def update_kinematics_for_moco(ik_fpath, model_output_fpath, kinematics_fpath):
    import opensim as osim
    table = osim.TimeSeriesTable(ik_fpath)
    table.appendColumn('knee_angle_r_beta', table.getDependentColumn('knee_angle_r'))
    table.appendColumn('knee_angle_l_beta', table.getDependentColumn('knee_angle_l'))
    tableProcessor = osim.TableProcessor(table)
    tableProcessor.append(osim.TabOpUseAbsoluteStateNames())
    model = osim.Model(model_output_fpath)
    model.initSystem()
    newTable = tableProcessor.process(model)
    sto = osim.STOFileAdapter()
    sto.write(newTable, kinematics_fpath)

    time = newTable.getIndependentColumn()
    initial_time = time[0]
    final_time = time[-1]

    return initial_time, final_time


def fill_moco_template(moco_template_fpath, output_fpath, trial_name, initial_time, final_time):
    with open(moco_template_fpath) as ft:
        content = ft.read()
        content = content.replace('@TRIAL@', trial_name)
        content = content.replace('@INITIAL_TIME@', str(initial_time))
        content = content.replace('@FINAL_TIME@', str(final_time))

    with open(output_fpath, 'w') as f:
        f.write(content)


def run_moco_problem(model_fpath, kinematics_fpath, extloads_fpath, initial_time, final_time, solution_fpath,
                     report_fpath):
    import opensim as osim
    import matplotlib
    matplotlib.use('Agg')

    # Update the model.
    # -----------------
    # Replace locked coordinates with weld joints.
    model = osim.Model(model_fpath)
    model.initSystem()
    coordinates = model.getCoordinateSet()
    locked_joints = list()
    locked_coordinates = list()
    for icoord in range(coordinates.getSize()):
        coord = coordinates.get(icoord)
        if coord.get_locked():
            locked_coordinates.append(coord.getName())
            locked_joints.append(coord.getJoint().getName())

    # Remove actuators associated with locked coordinates.
    for coordinate in locked_coordinates:
        forceSet = model.updForceSet()
        for iforce in range(forceSet.getSize()):
            force = forceSet.get(iforce)
            if force.getConcreteClassName().endswith('CoordinateActuator'):
                actu = osim.CoordinateActuator.safeDownCast(force)
                if actu.get_coordinate() == coordinate:
                    forceSet.remove(iforce)
                    break

    model.finalizeConnections()
    model.initSystem()

    # Construct a ModelProcessor. The default muscles in the model are replaced with
    # optimization-friendly DeGrooteFregly2016Muscles, and adjustments are made to the
    # default muscle parameters. We also add reserve actuators to the model and apply
    # the external loads.
    modelProcessor = osim.ModelProcessor(model)
    modelProcessor.append(osim.ModOpReplaceJointsWithWelds(locked_joints))
    modelProcessor.append(osim.ModOpAddExternalLoads(extloads_fpath))
    modelProcessor.append(osim.ModOpIgnoreTendonCompliance())
    modelProcessor.append(osim.ModOpReplaceMusclesWithDeGrooteFregly2016())
    modelProcessor.append(osim.ModOpIgnorePassiveFiberForcesDGF())
    modelProcessor.append(osim.ModOpAddReserves(50.0))

    # Construct the MocoInverse tool.
    # -------------------------------
    inverse = osim.MocoInverse()

    # Set the model processor and time bounds.
    inverse.setModel(modelProcessor)
    inverse.set_initial_time(initial_time)
    inverse.set_final_time(final_time)

    # Load the kinematics data source.
    # Add in the Rajagopal2015 patella coordinates to the kinematics table, if missing.
    table = osim.TimeSeriesTable(kinematics_fpath)
    labels = table.getColumnLabels()
    if 'knee_angle_r' in labels and 'knee_angle_r_beta' not in labels:
        table.appendColumn('knee_angle_r_beta', table.getDependentColumn('knee_angle_r'))
    if 'knee_angle_l' in labels and 'knee_angle_l_beta' not in labels:
        table.appendColumn('knee_angle_l_beta', table.getDependentColumn('knee_angle_l'))

    # Construct a TableProcessor to update the kinematics table labels to use absolute path names.
    # Add the kinematics to the MocoInverse tool.
    tableProcessor = osim.TableProcessor(table)
    tableProcessor.append(osim.TabOpUseAbsoluteStateNames())
    inverse.setKinematics(tableProcessor)

    # Configure additional settings for the MocoInverse problem including the mesh
    # interval, convergence tolerance, constraint tolerance, and max number of iterations.
    inverse.set_mesh_interval(0.02)
    inverse.set_convergence_tolerance(1e-5)
    inverse.set_constraint_tolerance(1e-5)
    inverse.set_max_iterations(2000)
    # Skip any extra columns in the kinematics data source.
    inverse.set_kinematics_allow_extra_columns(True)

    # Solve the problem.
    # ------------------
    # Solve the problem and write the solution to a Storage file.
    solution = inverse.solve()
    mocoSolution = solution.getMocoSolution()
    mocoSolution.unseal()
    mocoSolution.write(solution_fpath)

    # Generate a PDF with plots for the solution trajectory.
    model = modelProcessor.process()
    report = osim.report.Report(model,
                                solution_fpath,
                                output=report_fpath,
                                bilateral=True)
    # The PDF is saved to the working directory.
    report.generate()

    # Save dictionary of results to print to README.
    results = dict()
    results['mocoSuccess'] = mocoSolution.success()
    results['mocoObjective'] = mocoSolution.getObjective()
    results['mocoNumIterations'] = mocoSolution.getNumIterations()
    results['mocoSolverDuration'] = mocoSolution.getSolverDuration()

    return results
