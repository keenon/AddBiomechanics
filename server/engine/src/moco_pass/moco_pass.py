import os
import nimblephysics as nimble
import opensim as osim
import numpy as np
from typing import List, Dict
import subprocess
import sys
import matplotlib; matplotlib.use('Agg')
from plotting import (plot_coordinate_samples, plot_path_lengths, plot_moment_arms,
                      plot_joint_moment_breakdown)
from inspect import getsourcefile

MOCO_PATH = os.path.dirname(getsourcefile(lambda:0))
TEMPLATES_PATH = os.path.join(MOCO_PATH, 'templates')
GENERIC_OSIM_NAME = 'unscaled_generic.osim'
KINEMATIC_OSIM_NAME = 'match_markers_but_ignore_physics.osim'
DYNAMICS_OSIM_NAME = 'match_markers_and_physics.osim'
MOCO_OSIM_NAME = 'match_markers_and_physics_moco.osim'


def update_model(generic_model_fpath, model_input_fpath, model_output_fpath,
                 mass, height, generic_mass, generic_height):

    # Replace locked coordinates with weld joints.
    model = osim.Model(model_input_fpath)
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
    
    # Regression equations from Handsfield et al. (2014), "Relationships of 35 lower 
    # limb muscles to height and body mass quantified using MRI."
    # Equation from Figure 5a.
    def total_muscle_volume_regression_mass_height(mass, height):
        return 47.0*mass*height + 1285.0
    
    # Equation from Figure 5b.
    def total_muscle_volume_regression_mass(mass):
        return 91.0*mass + 588.0
    
    # Rules for updating muscle max isometric force based on volume scaling.
    # 
    # v: volume fraction
    # V: total volume
    # F: max isometric force
    # l: optimal fiber length
    #
    # F = v * sigma * V / l
    #
    # *_g: generic model.
    # *_s: subject-specific model.
    #
    # F_g = v * sigma * V_g / l_g
    # F_s = v * sigma * V_s / l_s
    #
    # F_s = (F_g * l_g / V_g) * V_s / l_s
    #     = F_g * (V_s / V_g) * (l_g / l_s)
    #
    # Credit: Chris Dembia (https://github.com/chrisdembia/mrsdeviceopt)
    generic_model = osim.Model(generic_model_fpath)
    generic_model.initSystem()

    if height > 0 and generic_height > 0:
        print("Using Handsfield et al. (2014) height and mass muscle volume "
              "regression equations to scale muscle forces...")
        generic_TMV = total_muscle_volume_regression_mass_height(generic_mass, 
                                                                 generic_height)
        subject_TMV = total_muscle_volume_regression_mass_height(mass, height)
    else:
        print("Generic and/or subject height is not available or invalid. Using "
              "mass-only Handsfield et al. (2014) muscle volume regression equation "
              "to scale muscle forces...")
        generic_TMV = total_muscle_volume_regression_mass(generic_mass)
        subject_TMV = total_muscle_volume_regression_mass(mass)

    generic_mset = generic_model.getMuscles()
    subject_mset = model.getMuscles()
    for im in range(subject_mset.getSize()):
        muscle_name = subject_mset.get(im).getName()

        generic_muscle = generic_mset.get(muscle_name)
        subject_muscle = subject_mset.get(muscle_name)

        generic_OFL = generic_muscle.get_optimal_fiber_length()
        subj_OFL = subject_muscle.get_optimal_fiber_length()

        scale_factor = (subject_TMV / generic_TMV) * (generic_OFL / subj_OFL)
        print("Scaling '%s' muscle force by %f." % (muscle_name, scale_factor))

        generic_force = generic_muscle.getMaxIsometricForce()
        scaled_force = generic_force * scale_factor
        subject_muscle.setMaxIsometricForce(scaled_force)

    # Ignore tendon compliance if the tendon slack length is less than the optimal
    # fiber length.
    print("Updating muscle tendon compliance based on the ratio of tendon slack "
          "length (TSL) to optimal fiber length (OFL)...")
    for im in range(subject_mset.getSize()):
        muscle_name = subject_mset.get(im).getName()
        subject_muscle = subject_mset.get(muscle_name)
        TSL = subject_muscle.get_tendon_slack_length()
        OFL = subject_muscle.get_optimal_fiber_length()

        ratio = TSL / OFL
        if ratio >= 1.0:
            print(f'Enabling tendon compliance for {muscle_name}. '
                  f'Ratio (TSL/OFL): {ratio}')
            subject_muscle.set_ignore_tendon_compliance(False)
        else:
            print(f'Ignoring tendon compliance for {muscle_name}. '
                  f'Ratio (TSL/OFL): {ratio}')
            subject_muscle.set_ignore_tendon_compliance(True)

    # Save the updated model.
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


def create_residuals_force_set(output_folder, trial_name, residual_strengths):
    residuals = osim.ForceSet()
    for key, value in residual_strengths.items():
        key_split = key.split('_')
        coordinate_name = f'{key_split[0]}_{key_split[1]}'
        residual = osim.CoordinateActuator(coordinate_name)
        residual.setName(f'residual_{key}')
        residual.setOptimalForce(value)
        residuals.append(residual)

    residuals_fpath = os.path.join(output_folder, 'Moco', f'{trial_name}_residuals.xml')
    residuals.printToXML(residuals_fpath)


def fill_moco_template(moco_template_fpath, script_fpath, model_name, trial_name, 
                       reserve_strength, max_isometric_force_scale, initial_time, 
                       final_time, excitation_effort, activation_effort):
    with open(moco_template_fpath) as ft:
        content = ft.read()
        content = content.replace('@TRIAL@', trial_name)
        content = content.replace('@MODEL_NAME@', model_name)
        content = content.replace('@INITIAL_TIME@', str(initial_time))
        content = content.replace('@FINAL_TIME@', str(final_time))
        content = content.replace('@RESERVE_STRENGTH@', str(reserve_strength))
        content = content.replace('@MAX_ISOMETRIC_FORCE_SCALE@', 
                                  str(max_isometric_force_scale))
        content = content.replace('@EXCITATION_EFFORT@', str(excitation_effort))
        content = content.replace('@ACTIVATION_EFFORT@', str(activation_effort))

    with open(script_fpath, 'w') as f:
        f.write(content)


def moco_pass(subject: nimble.biomechanics.SubjectOnDisk,
              path: str, output_name: str, 
              generic_mass: float, generic_height: float):
    """
    This function is responsible for running the Moco pass on the subject.
    """

    # TODOs
    # ----
    # 1. Assumes that muscles are in the ForceSet.

    # Global settings.
    # ----------------
    # The output folder.
    output_folder = path + output_name
    if not output_folder.endswith('/'):
        output_folder += '/'
    if not os.path.exists(output_folder + 'Moco'):
        os.mkdir(output_folder + 'Moco')
    # The total number of coordinate pose samples used during function-based path fitting.
    total_samples = 150
    # The maximum length of a trial, in seconds, to be solved by Moco.
    max_trial_length = 3.0 
    # The directory to save the function-based paths.
    fbpaths_dir = os.path.join(output_folder, 'Moco', 'function_based_paths')
    # The strength of the reserve actuators. Weaker reserves are penalized more heavily
    # during the MocoInverse problem.
    reserve_strength = 5.0
    # The global scaling factor applied to muscle max isometric force.
    max_isometric_force_scale = 1.0
    # The weight on the muscle excitation effort in the MocoInverse problem.
    excitation_effort = 0.1
    # The weight on the activation effort in the MocoInverse problem.
    activation_effort = 1.0

    # Load the subject.
    header_proto = subject.getHeaderProto()
    trial_protos = header_proto.getTrials()
    num_trials = subject.getNumTrials()

    # Update the model.
    # -----------------
    generic_model_fpath = os.path.join(output_folder, 'Models', GENERIC_OSIM_NAME)
    dynamics_model_fpath = os.path.join(output_folder, 'Models', DYNAMICS_OSIM_NAME)
    moco_model_fpath = os.path.join(output_folder, 'Models', MOCO_OSIM_NAME)
    mass = subject.getMassKg()
    height = subject.getHeightM()
    update_model(generic_model_fpath, dynamics_model_fpath, moco_model_fpath, 
                 mass, height, generic_mass, generic_height)
    model = osim.Model(moco_model_fpath)
    model.initSystem()

    # Get the coordinate names.
    coordinate_names = osim.ArrayStr()
    coordinate_set = model.getCoordinateSet()
    coordinate_set.getNames(coordinate_names)
    coordinate_names = [coordinate_names.get(i) for i in range(coordinate_names.getSize())]

    # Remove coupled or undefined coordinates from the list of coordinate names.
    for icoord in range(coordinate_set.getSize()):
        coord = coordinate_set.get(icoord)
        motion_type = coord.getMotionType()
        if not motion_type == 1 and not motion_type == 2:
            coordinate_names.remove(coord.getName())

    # Find the ground-to-root (usually pelvis) joint coordinates and initialize a 
    # dictionary to store the residual strengths. Also, remove the root joint
    # coordinates from the list of coordinate names.
    jointset = model.getJointSet()
    residual_strengths = dict()
    for ijoint in range(jointset.getSize()):
        joint = jointset.get(ijoint)
        base_frame = joint.getParentFrame().findBaseFrame()
        if base_frame.getName() == 'ground':
            for icoord in range(joint.numCoordinates()):
                coord = joint.get_coordinates(icoord)
                coordinate_names.remove(coord.getName())
                motion_type = coord.getMotionType()
                if motion_type == 1:
                    residual_strengths[f'{coord.getName()}_moment'] = 0.0
                elif motion_type == 2:
                    residual_strengths[f'{coord.getName()}_force'] = 0.0
                else:
                    invalid_type = 'undefined' if motion_type == 0 else 'coupled'
                    raise Exception(f'Root joint has a coordinate with invalid '
                                    f'motion type "{invalid_type}".')                
            break

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
        for irow in range(min(samples_per_trial, ik.getNumRows())):
            coordinate_values.appendRow(curr_row, ik.getRowAtIndex(irow))
            curr_row += 1
            
    coordinate_values.setColumnLabels(ik.getColumnLabels())
    coordinate_values.addTableMetaDataString('inDegrees', 
                                             ik.getTableMetaDataAsString('inDegrees'))
    fit_function_based_paths(model, coordinate_values, fbpaths_dir)

    # Filter trials.
    # --------------
    # Find the trials that have dynamics passes.
    moco_trials: List[int] = []
    for i in range(num_trials):
        pass_type = trial_protos[i].getPasses()[-1].getType()
        if pass_type == nimble.biomechanics.ProcessingPassType.DYNAMICS:
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

            if not found_initial_time and missing_grf_reasons[itime] == not_missing_grf:
                initial_time = time
                found_initial_time = True
                continue

            if found_initial_time:
                if time - initial_time >= max_trial_length:
                    final_time = time
                    break

                if missing_grf_reasons[itime] != not_missing_grf:
                    final_time = time
                    break

        # Detect the needed residual strengths based on the trial ID moments.
        id_fpath = os.path.join(output_folder, 'ID', f'{trial_name}_id.sto')
        id = osim.TimeSeriesTable(id_fpath)
        id.trim(initial_time-0.1, final_time+0.1)
        for key in residual_strengths.keys():
            max_gen_force = max(abs(id.getDependentColumn(key).to_numpy()))
            residual_strengths[key] = np.ceil(max_gen_force)
        create_residuals_force_set(output_folder, trial_name, residual_strengths)

        # Fill the MocoInverse problem template.
        script_fpath = os.path.join(output_folder, 'Moco', f'{trial_name}_moco.py')
        template_fpath = os.path.join(TEMPLATES_PATH, 'template_moco.py.txt')
        fill_moco_template(template_fpath, script_fpath, model.getName(), trial_name, 
                           reserve_strength, max_isometric_force_scale, initial_time, 
                           final_time, excitation_effort, activation_effort)
                            
        # Run the MocoInverse problem.
        moco_dir = os.path.join(output_folder, 'Moco')
        subprocess.run([sys.executable, script_fpath], stdout=sys.stdout, 
                       stderr=sys.stderr, cwd=moco_dir)
        solution_fpath = os.path.join(moco_dir, f'{trial_name}_moco.sto')
        model_fpath = os.path.join(moco_dir, f'{trial_name}_moco.osim')

        # Load the model.
        model_moco = osim.Model(model_fpath)
        # Point the ExternalLoads component in the model to the location of the 
        # ground reaction forces, so we can initialize the model's system.
        extloads = osim.ExternalLoads.safeDownCast(
                model_moco.updComponent('/componentset/externalloads'))
        extloads.setDataFileName(
                os.path.join(output_folder, 'ID', f'{trial_name}_grf.mot'))
        model_moco.initSystem()
        
        # Plot the joint moment breakdown.
        tendon_forces_fpath = os.path.join(moco_dir, f'{trial_name}_tendon_forces.sto')
        output_fpath = os.path.join(moco_dir, f'{trial_name}_joint_moment_breakdown.pdf')
        plot_joint_moment_breakdown(model_moco, solution_fpath, 
                                    tendon_forces_fpath, id_fpath, coordinate_names, 
                                    reserve_strength, output_fpath)



