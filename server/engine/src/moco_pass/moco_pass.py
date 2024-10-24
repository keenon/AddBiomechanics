import os
import nimblephysics as nimble
import numpy as np
from typing import List, Tuple

GENERIC_OSIM_NAME = 'unscaled_generic.osim'
KINEMATIC_OSIM_NAME = 'match_markers_but_ignore_physics.osim'
DYNAMICS_OSIM_NAME = 'match_markers_and_physics.osim'


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


def run_moco_problem(model_fpath, kinematics_fpath, extloads_fpath, 
                     initial_time, final_time, solution_fpath, report_fpath):
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
    modelProcessor.append(osim.ModOpIgnoreActivationDynamics())
    modelProcessor.append(osim.ModOpReplaceMusclesWithDeGrooteFregly2016())
    modelProcessor.append(osim.ModOpIgnorePassiveFiberForcesDGF())
    modelProcessor.append(osim.ModOpScaleMaxIsometricForce(1.5))
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


def moco_pass(subject: nimble.biomechanics.SubjectOnDisk,
              path: str, output_name: str):
    """
    This function is responsible for running the Moco pass on the subject.
    """

    output_folder = path + output_name
    if not output_folder.endswith('/'):
        output_folder += '/'

    if not os.path.exists(output_folder + 'Moco'):
        os.mkdir(output_folder + 'Moco')

    header_proto = subject.getHeaderProto()
    trial_protos = header_proto.getTrials()
    num_trials = subject.getNumTrials()

    moco_trials: List[int] = []
    for i in range(subject.getNumTrials()):
        if trial_protos[i].getPasses()[-1].getType() == nimble.biomechanics.ProcessingPassType.DYNAMICS:
            print('Solving the muscle redundancy problem using OpenSim Moco on trial ' 
                  + str(i) + '/' + str(num_trials))
            moco_trials.append(i)

    for trial in moco_trials:
        trial_name = trial_protos[trial].getName()
        model_fpath = os.path.join(output_folder, 'Models', DYNAMICS_OSIM_NAME)
        kinematics_fpath = os.path.join(output_folder, 'IK', f'{trial_name}_ik.mot')
        extloads_fpath = os.path.join(output_folder, 'ID', f'{trial_name}_external_forces.xml')
        solution_fpath = os.path.join(output_folder, 'Moco', f'{trial_name}_moco.sto')
        report_fpath = os.path.join(output_folder, 'Moco', f'{trial_name}_moco_report.pdf')

        start_time = trial_protos[trial].getOriginalTrialStartTime()
        dt = trial_protos[trial].getTimestep()
        num_steps = trial_protos[trial].getTrialLength()
        end_time = trial_protos[trial].getOriginalTrialEndTime()
        missing_grf_reasons = trial_protos[trial].getMissingGRFReason()
        import pdb; pdb.set_trace()

        initial_time = start_time
        final_time = end_time
        found_initial_time = False
        for itime in range(num_steps):
            time = start_time + itime * dt

            if missing_grf_reasons[itime] == nimble.biomechanics.MissingGRFReason.notMissingGRF:
                initial_time = time
                found_initial_time = True

            if found_initial_time and missing_grf_reasons[itime] != nimble.biomechanics.MissingGRFReason.notMissingGRF:
                final_time = time
                break

        run_moco_problem(model_fpath, kinematics_fpath, extloads_fpath, 
                         initial_time, final_time, solution_fpath, report_fpath)

    # 11.5.2. Muscle redundancy problem (with Moco) results.
    # if self.runMoco:
    #     with open(f'{self.path}/results/Moco/{trialName}_moco_summary.txt', 'w') as f:
    #         f.write('-' * len(trialName) + '-------------------------------------------\n')
    #         f.write(f"Trial '{trialName}': Muscle Redundancy Problem Summary\n")
    #         f.write('-' * len(trialName) + '-------------------------------------------\n')
    #         f.write('\n')

    #         mocoSuccess = trialProcessingResult['mocoSuccess']
    #         if mocoSuccess:
    #             f.write(textwrap.fill(
    #                 "Automatic processing successfully ran the muscle redundancy problem using OpenSim Moco! "
    #                 "The problem converged with the following statistics: "))
    #             f.write('\n\n')

    #             objective = trialProcessingResult['mocoObjective']
    #             num_iterations = trialProcessingResult['mocoNumIterations']
    #             duration = trialProcessingResult['mocoSolverDuration']
    #             f.write(f'  - Final objective value = {objective:.2f} \n')
    #             f.write(f'  - Number of iterations  = {num_iterations} \n')
    #             f.write(f'  - Solver duration       = {duration:.2f} s \n')
    #             f.write('\n')
    #             f.write(textwrap.fill("The objective value is the sum of squared muscle excitations squared. "
    #                                     "Note that these values (especially the solver duration) may differ when "
    #                                     "running the problem on your own computer."))
    #             f.write('\n\n')

    #             if trialProcessingResult['mocoLimitedDuration']:
    #                 initial_time = trialProcessingResult['mocoInitialTime']
    #                 final_time = trialProcessingResult['mocoFinalTime']
    #                 f.write(textwrap.fill(f"The problem duration was limited to the time range "
    #                                         f"[{initial_time:.2f}, {final_time:.2f}] to keep the Moco problem "
    #                                         f"tractable."))
    #                 f.write('\n\n')

    #             f.write(textwrap.fill(f'To further customize this problem, modify and run the script '
    #                                     f'{trialName}_moco.py, located in this directory.'))
    #             f.write('\n\n')

    #             f.write(textwrap.fill(
    #                 "For additional assistance, please submit a post on the OpenSim Moco user forum on "
    #                 "SimTK.org:"))
    #             f.write('\n\n')
    #             f.write('   https://simtk.org/projects/opensim-moco')

    #         else:
    #             f.write(textwrap.fill(
    #                 "Unfortunately, the muscle redundancy problem in OpenSim Moco did not succeed."))
    #             f.write('\n\n')
    #             f.write(textwrap.fill(f'If you would like to modify the problem and try again, see the script '
    #                                     f'{trialName}_moco.py, located in this directory.'))
    #             f.write('\n\n')
    #             f.write(textwrap.fill(
    #                 "For additional assistance, please submit a post on the OpenSim Moco user forum on "
    #                 "SimTK.org:"))
    #             f.write('\n\n')
    #             f.write('   https://simtk.org/projects/opensim-moco')