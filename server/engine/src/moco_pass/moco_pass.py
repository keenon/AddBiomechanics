import os
import nimblephysics as nimble
import opensim as osim
import numpy as np
from typing import List
import subprocess
import sys
import matplotlib; matplotlib.use('Agg')
from src.moco_pass.plotting import (plot_coordinate_samples, plot_path_lengths,
                                    plot_moment_arms)
from inspect import getsourcefile

MOCO_PATH = os.path.dirname(getsourcefile(lambda:0))
TEMPLATES_PATH = os.path.join(MOCO_PATH, 'templates')
GENERIC_OSIM_NAME = 'unscaled_generic.osim'
KINEMATIC_OSIM_NAME = 'match_markers_but_ignore_physics.osim'
DYNAMICS_OSIM_NAME = 'match_markers_and_physics.osim'
MOCO_OSIM_NAME = 'match_markers_and_physics_moco.osim'


def update_model(model_input_fpath, model_output_fpath):

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

    model.finalizeConnections()
    modelProcessor = osim.ModelProcessor(model)
    modelProcessor.append(osim.ModOpReplaceJointsWithWelds(locked_joints))
    model = modelProcessor.process()
    model.initSystem()
    model.printToXML(model_output_fpath)


def fit_function_based_paths(model, coordinate_values, results_dir):
    fitter = osim.PolynomialPathFitter()
    fitter.setModel(osim.ModelProcessor(model))
    table_processor = osim.TableProcessor(coordinate_values)
    table_processor.append(osim.TabOpUseAbsoluteStateNames())
    table_processor.append(osim.TabOpAppendCoupledCoordinateValues())
    fitter.setCoordinateValues(table_processor)
    fitter.setOutputDirectory(results_dir)
    fitter.setMaximumPolynomialOrder(5)
    fitter.setNumSamplesPerFrame(10)
    fitter.setGlobalCoordinateSamplingBounds(osim.Vec2(-45, 45))
    fitter.setUseStepwiseRegression(True)
    # Fitted path lengths and moment arms must be within 1mm RMSE.
    fitter.setPathLengthTolerance(1e-3)
    fitter.setMomentArmTolerance(1e-3)
    fitter.run()

    plot_coordinate_samples(results_dir, model.getName())
    plot_path_lengths(results_dir, model.getName())
    plot_moment_arms(results_dir, model.getName())


def fill_moco_template(moco_template_fpath, script_fpath, model_name, trial_name, 
                       initial_time, final_time):
    with open(moco_template_fpath) as ft:
        content = ft.read()
        content = content.replace('@TRIAL@', trial_name)
        content = content.replace('@MODEL_NAME@', model_name)
        content = content.replace('@INITIAL_TIME@', str(initial_time))
        content = content.replace('@FINAL_TIME@', str(final_time))

    with open(script_fpath, 'w') as f:
        f.write(content)


def moco_pass(subject: nimble.biomechanics.SubjectOnDisk,
              path: str, output_name: str):
    """
    This function is responsible for running the Moco pass on the subject.
    """

    # Create the output folder.
    output_folder = path + output_name
    if not output_folder.endswith('/'):
        output_folder += '/'
    if not os.path.exists(output_folder + 'Moco'):
        os.mkdir(output_folder + 'Moco')

    # Load the subject.
    header_proto = subject.getHeaderProto()
    trial_protos = header_proto.getTrials()
    num_trials = subject.getNumTrials()

    # Update the model.
    # -----------------
    dynamics_model_fpath = os.path.join(output_folder, 'Models', DYNAMICS_OSIM_NAME)
    moco_model_fpath = os.path.join(output_folder, 'Models', MOCO_OSIM_NAME)
    update_model(dynamics_model_fpath, moco_model_fpath)
    model = osim.Model(moco_model_fpath)
    model.initSystem()

    # Global settings.
    # ----------------
    # The total number of coordinate pose samples used during function-based path fitting.
    total_samples = 150
    # The maximum length of a trial, in seconds, to be solved by Moco.
    max_trial_length = 3.0 
    # The directory to save the function-based paths.
    fbpaths_dir = os.path.join(output_folder, 'Moco', 'function_based_paths')

    # Function-based paths.
    # ---------------------
    # Fit a set of function-based paths to the model. Grab the coordinate samples from 
    # all trials in this subject.
    samples_per_trial = total_samples // num_trials
    coordinate_values = osim.TimeSeriesTable()
    curr_row = 0
    for itrial in range(num_trials):
        trial_name = trial_protos[itrial].getName()
        ik = osim.TimeSeriesTable(os.path.join(output_folder, 'IK', f'{trial_name}_ik.mot'))
        num_rows = ik.getNumRows()
        for irow in range(0, num_rows, int(np.ceil(num_rows / samples_per_trial))):
            coordinate_values.appendRow(curr_row, ik.getRowAtIndex(irow))
            curr_row += 1
            
    coordinate_values.setColumnLabels(ik.getColumnLabels())
    coordinate_values.addTableMetaDataString('inDegrees', 
                                             ik.getTableMetaDataAsString('inDegrees'))
    fit_function_based_paths(model, coordinate_values, fbpaths_dir)
    fbpaths_fpath = os.path.join(fbpaths_dir, f'{model.getName()}_FunctionBasedPathSet.xml')

    # Filter trials.
    # --------------
    # Find the trials that have dynamics passes.
    moco_trials: List[int] = []
    for i in range(num_trials):
        if trial_protos[i].getPasses()[-1].getType() == nimble.biomechanics.ProcessingPassType.DYNAMICS:
            print('Solving the muscle redundancy problem using OpenSim Moco on trial ' 
                  + str(i) + '/' + str(num_trials))
            moco_trials.append(i)

    # Run Moco.
    # ---------
    # We will limit the time range of the trial based on where the GRF is valid and the 
    # maximum allowed trial length.
    sto = osim.STOFileAdapter()
    not_missing_grf = nimble.biomechanics.MissingGRFReason.notMissingGRF
    for trial in moco_trials:
        trial_name = trial_protos[trial].getName()
        ik_fpath = os.path.join(output_folder, 'IK', f'{trial_name}_ik.mot')
        extloads_fpath = os.path.join(output_folder, 'ID', f'{trial_name}_external_forces.xml')
        solution_fpath = os.path.join(output_folder, 'Moco', f'{trial_name}_moco.sto')
        report_fpath = os.path.join(output_folder, 'Moco', f'{trial_name}_moco_report.pdf')

        start_time = trial_protos[trial].getOriginalTrialStartTime()
        dt = trial_protos[trial].getTimestep()
        num_steps = trial_protos[trial].getTrialLength()
        end_time = trial_protos[trial].getOriginalTrialEndTime()
        missing_grf_reasons = trial_protos[trial].getMissingGRFReason()

        initial_time = start_time
        final_time = end_time
        found_initial_time = False
        for itime in range(num_steps):
            time = start_time + itime * dt

            # Find the first time step in the trial with valid GRF data.
            if not found_initial_time and missing_grf_reasons[itime] == not_missing_grf:
                initial_time = time
                found_initial_time = True
                continue

            # Set the final time step if:
            # - The current time range is greater than the max trial length.
            # - The current time step has missing GRF data.
            if found_initial_time:
                if time - initial_time >= max_trial_length:
                    final_time = time
                    break

                if missing_grf_reasons[itime] != not_missing_grf:
                    final_time = time
                    break

        table_processor = osim.TableProcessor(ik_fpath)
        table_processor.append(osim.TabOpUseAbsoluteStateNames())
        table_processor.append(osim.TabOpAppendCoupledCoordinateValues())
        kinematics = table_processor.process(model)
        kinematics.trim(initial_time-0.05, final_time+0.05)
        kinematics_fpath = os.path.join(output_folder, 'Moco', f'{trial_name}_moco_kinematics.sto')
        sto.write(kinematics, kinematics_fpath)

        script_fpath = os.path.join(output_folder, 'Moco', f'{trial_name}_moco.py')
        template_fpath = os.path.join(TEMPLATES_PATH, 'template_moco.py')
        fill_moco_template(template_fpath, script_fpath, model.getName(), trial_name, 
                           initial_time, final_time)
                
        moco_dir = os.path.join(output_folder, 'Moco')
        subprocess.run([sys.executable, script_fpath], stdout=sys.stdout, 
                       stderr=sys.stderr, cwd=moco_dir)

