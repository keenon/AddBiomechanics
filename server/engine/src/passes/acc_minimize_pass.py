import nimblephysics as nimble
import numpy as np
from typing import List, Tuple


def add_acc_minimize_pass(subject: nimble.biomechanics.SubjectOnDisk):
    # Apply an acceleration minimizing filter pass
    acc_minimizing_pass = subject.getHeaderProto().addProcessingPass()
    acc_minimizing_pass.setOpenSimFileText(subject.getOpensimFileText(0))
    acc_minimizing_pass.setProcessingPassType(nimble.biomechanics.ProcessingPassType.ACC_MINIMIZING_FILTER)

    num_dofs = subject.getNumDofs()

    # Read the kinematics opensim
    kinematics_osim = subject.readOpenSimFile(0, ignoreGeometry=True)
    kinematics_skeleton = kinematics_osim.skeleton
    kinematics_markers = kinematics_osim.markersMap

    # Go through and actually minimize the acceleration on each trial
    trial_protos = subject.getHeaderProto().getTrials()
    trial_lowpass_force_plates: List[List[nimble.biomechanics.ForcePlate]] = []
    num_trials = subject.getNumTrials()
    # num_trials = min(num_trials, 5)

    corrupt_file = False
    for i in range(num_trials):
        trial_proto = trial_protos[i]
        if len(trial_proto.getPasses()) == 0:
            print('DETECTED CORRUPT FILE: Skipping trial ' + str(i) + ' because it has no passes')
            corrupt_file = True
            break
        kinematics_pass = trial_proto.getPasses()[0]
        if kinematics_pass is None:
            print('DETECTED CORRUPT FILE: Skipping trial ' + str(i) + ' because it has no kinematics pass')
            corrupt_file = True
            break
        marker_observations = trial_proto.getMarkerObservations()

        #######################################################################################################
        # Acceleration Minimization Pass
        #######################################################################################################

        print('Minimizing acceleration on trial ' + str(i))

        trial_len = subject.getTrialLength(i)
        dt = subject.getTrialTimestep(i)
        pose_regularization = 1000.0
        acceleration_minimizer = nimble.utils.AccelerationMinimizer(trial_len, 1.0 / (dt * dt), pose_regularization)

        positions = kinematics_pass.getPoses()

        # Unwrap the positions to avoid discontinuities
        for t in range(1, trial_len):
            positions[:, t] = kinematics_skeleton.unwrapPositionToNearest(positions[:, t], positions[:, t - 1])

        acc_minimized_positions = np.zeros((num_dofs, trial_len))
        for dof in range(num_dofs):
            acc_minimized_positions[dof, :] = acceleration_minimizer.minimize(positions[dof, :])
        positions = acc_minimized_positions

        velocities = np.zeros((num_dofs, trial_len))
        for t in range(1, trial_len):
            velocities[:, t] = (positions[:, t] - positions[:, t - 1]) / dt
        if trial_len > 1:
            velocities[:, 0] = velocities[:, 1]

        accelerations = np.zeros((num_dofs, trial_len))
        for t in range(1, trial_len):
            accelerations[:, t] = (velocities[:, t] - velocities[:, t - 1]) / dt
        if trial_len > 1:
            accelerations[:, 0] = accelerations[:, 1]

        # Copy force plate data to Python
        raw_force_plates = trial_proto.getForcePlates()
        force_plate_raw_forces: List[List[np.ndarray]] = [force_plate.forces for force_plate in raw_force_plates]
        force_plate_raw_cops: List[List[np.ndarray]] = [force_plate.centersOfPressure for force_plate in raw_force_plates]
        force_plate_raw_moments: List[List[np.ndarray]] = [force_plate.moments for force_plate in raw_force_plates]

        force_plate_norms: List[np.ndarray] = [np.zeros(trial_len) for _ in
                                               range(len(raw_force_plates))]
        for i in range(len(raw_force_plates)):
            force_norms = force_plate_norms[i]
            for t in range(trial_len):
                force_norms[t] = np.linalg.norm(force_plate_raw_forces[i][t])
        # 4. Next, low-pass filter the GRF data for each non-zero section
        lowpass_force_plates: List[nimble.biomechanics.ForcePlate] = []
        for i in range(len(raw_force_plates)):
            force_matrix = np.zeros((3, trial_len))
            cop_matrix = np.zeros((3, trial_len))
            moment_matrix = np.zeros((3, trial_len))
            force_norms = force_plate_norms[i]
            non_zero_segments: List[Tuple[int, int]] = []
            last_nonzero = -1
            # 4.1. Find the non-zero segments
            for t in range(trial_len):
                if force_norms[t] > 0.0:
                    if last_nonzero < 0:
                        last_nonzero = t
                else:
                    if last_nonzero >= 0:
                        non_zero_segments.append((last_nonzero, t))
                        last_nonzero = -1
                force_matrix[:, t] = force_plate_raw_forces[i][t]
                cop_matrix[:, t] = force_plate_raw_cops[i][t]
                moment_matrix[:, t] = force_plate_raw_moments[i][t]
            if last_nonzero >= 0:
                non_zero_segments.append((last_nonzero, trial_len))

            # 4.2. Lowpass filter each non-zero segment
            for start, end in non_zero_segments:
                # print(f"Filtering force plate {i} on non-zero range [{start}, {end}]")
                if end - start < 10:
                    # print(" - Skipping non-zero segment because it's too short. Zeroing instead")
                    for t in range(start, end):
                        force_plate_raw_forces[i][t] = np.zeros(3)
                        force_plate_raw_cops[i][t] = np.zeros(3)
                        force_plate_raw_moments[i][t] = np.zeros(3)
                        force_norms[t] = 0.0
                else:
                    start_weight = 1e5 if start > 0 else 0.0
                    end_weight = 1e5 if end < trial_len else 0.0
                    input_force_dim = end - start
                    input_force_start_index = 0
                    input_force_end_index = input_force_dim

                    padded_start = start
                    if start_weight > 0:
                        pad_steps = min(5, start)
                        padded_start -= pad_steps
                        input_force_dim += pad_steps
                        input_force_start_index += pad_steps
                        input_force_end_index += pad_steps
                    assert padded_start >= 0

                    padded_end = end
                    if end_weight > 0:
                        pad_steps = min(5, trial_len - end)
                        padded_end += pad_steps
                        input_force_dim += pad_steps
                    assert padded_end <= trial_len

                    acc_minimizer = nimble.utils.AccelerationMinimizer(input_force_dim,
                                                                       1.0 / (dt * dt),
                                                                       pose_regularization,
                                                                       startPositionZeroWeight=start_weight,
                                                                       endPositionZeroWeight=end_weight,
                                                                       startVelocityZeroWeight=start_weight,
                                                                       endVelocityZeroWeight=end_weight)
                    cop_acc_minimizer = nimble.utils.AccelerationMinimizer(input_force_dim,
                                                                           1.0 / (dt * dt),
                                                                           pose_regularization)

                    for j in range(3):
                        input_force = np.zeros(input_force_dim)
                        input_force[input_force_start_index:input_force_end_index] = force_matrix[j, start:end]
                        input_moment = np.zeros(input_force_dim)
                        input_moment[input_force_start_index:input_force_end_index] = moment_matrix[j, start:end]
                        input_cops = np.zeros(input_force_dim)
                        input_cops[input_force_start_index:input_force_end_index] = cop_matrix[j, start:end]

                        # Pad the edges of the input_cops with a constant extension of the edge value
                        # Scan inwards to find the first force magnitude greater than a cutoff threshold, to
                        # indicate that the CoP has started to get reliable
                        first_reliable_cop_offset = 0
                        for t in range(end - start):
                            if np.linalg.norm(force_matrix[:, start + t]) > 50.0:
                                first_reliable_cop_offset = t
                                break
                        input_cops[:input_force_start_index + first_reliable_cop_offset] = cop_matrix[
                            j, start + first_reliable_cop_offset]

                        # Scan inwards from the end to find the first force magnitude greater than a cutoff threshold, to
                        # indicate that the CoP has started to get reliable
                        last_reliable_cop_offset = 0
                        for t in range(end - start):
                            if np.linalg.norm(force_matrix[:, end - 1 - t]) > 50.0:
                                last_reliable_cop_offset = t
                                break
                        input_cops[input_force_end_index - last_reliable_cop_offset:] = cop_matrix[
                            j, end - 1 - last_reliable_cop_offset]

                        smoothed_force = acc_minimizer.minimize(input_force)
                        if np.sum(np.abs(smoothed_force)) != 0:
                            smoothed_force *= np.sum(np.abs(force_matrix[j, start:end])) / np.sum(np.abs(smoothed_force))

                        force_matrix[j, padded_start:padded_end] = smoothed_force

                        smoothed_moment = acc_minimizer.minimize(input_moment)
                        if np.sum(np.abs(smoothed_moment)) != 0:
                            smoothed_moment *= np.sum(np.abs(moment_matrix[j, start:end])) / np.sum(np.abs(smoothed_moment))
                        moment_matrix[j, padded_start:padded_end] = smoothed_moment

                        # We don't restrict the CoP dynamics at the beginning or end of a stride, so we don't
                        # need to pad the input to account for ramping up or down to zero.
                        cop_matrix[j, padded_start:padded_end] = cop_acc_minimizer.minimize(input_cops)

                    # import matplotlib.pyplot as plt
                    # fig, axs = plt.subplots(3, 1)
                    # fig.suptitle('Force Plate: '+str(i))
                    # plottable_force_plate_raw_forces = np.array(force_plate_raw_forces[i]).transpose()
                    # axs[0].plot(range(trial_len), plottable_force_plate_raw_forces[0, :], label='original x')
                    # axs[0].plot(range(trial_len), plottable_force_plate_raw_forces[1, :], label='original y')
                    # axs[0].plot(range(trial_len), plottable_force_plate_raw_forces[2, :], label='original z')
                    # axs[0].plot(range(trial_len), force_matrix[0, :], label='new x')
                    # axs[0].plot(range(trial_len), force_matrix[1, :], label='new y')
                    # axs[0].plot(range(trial_len), force_matrix[2, :], label='new z')
                    # axs[0].set_title('Force')
                    # axs[0].legend()
                    # axs[0].set(xlabel='Time (s)', ylabel='Force (N)')
                    #
                    # plottable_cop_plate_raw_cops = np.array(force_plate_raw_cops[i]).transpose()
                    # axs[1].plot(range(trial_len), plottable_cop_plate_raw_cops[0, :], label='original x')
                    # axs[1].plot(range(trial_len), plottable_cop_plate_raw_cops[1, :], label='original y')
                    # axs[1].plot(range(trial_len), plottable_cop_plate_raw_cops[2, :], label='original z')
                    # axs[1].plot(range(trial_len), cop_matrix[0, :], label='new x')
                    # axs[1].plot(range(trial_len), cop_matrix[1, :], label='new y')
                    # axs[1].plot(range(trial_len), cop_matrix[2, :], label='new z')
                    # axs[1].set_title('CoP')
                    # axs[1].legend()
                    # axs[1].set(xlabel='Time (s)', ylabel='CoP (m)')
                    #
                    # plottable_raw_moment_matrix = np.array(force_plate_raw_moments[i]).transpose()
                    # axs[2].plot(range(trial_len), plottable_raw_moment_matrix[0, :], label='original x')
                    # axs[2].plot(range(trial_len), plottable_raw_moment_matrix[1, :], label='original y')
                    # axs[2].plot(range(trial_len), plottable_raw_moment_matrix[2, :], label='original z')
                    # axs[2].plot(range(trial_len), moment_matrix[0, :], label='new x')
                    # axs[2].plot(range(trial_len), moment_matrix[1, :], label='new y')
                    # axs[2].plot(range(trial_len), moment_matrix[2, :], label='new z')
                    # axs[2].set_title('Moment')
                    # axs[2].legend()
                    # axs[2].set(xlabel='Time (s)', ylabel='Moment (Nm)')
                    #
                    # plt.show()

                    for t in range(padded_start, padded_end):
                        force_plate_raw_forces[i][t] = force_matrix[:, t]
                        force_plate_raw_cops[i][t] = cop_matrix[:, t]
                        force_plate_raw_moments[i][t] = moment_matrix[:, t]

            # 4.3. Create a new lowpass filtered force plate
            force_plate_copy = nimble.biomechanics.ForcePlate.copyForcePlate(raw_force_plates[i])
            force_plate_copy.forces = force_plate_raw_forces[i]
            force_plate_copy.centersOfPressure = force_plate_raw_cops[i]
            force_plate_copy.moments = force_plate_raw_moments[i]
            lowpass_force_plates.append(force_plate_copy)
        trial_lowpass_force_plates.append(lowpass_force_plates)

        acc_minimizer_ik_error_report = nimble.biomechanics.IKErrorReport(
            kinematics_skeleton,
            kinematics_markers,
            positions,
            marker_observations)

        acc_min_pass_proto = trial_proto.addPass()
        acc_min_pass_proto.setType(nimble.biomechanics.ProcessingPassType.ACC_MINIMIZING_FILTER)
        acc_min_pass_proto.setDofPositionsObserved([True for _ in range(num_dofs)])
        acc_min_pass_proto.setDofVelocitiesFiniteDifferenced([True for _ in range(num_dofs)])
        acc_min_pass_proto.setDofAccelerationFiniteDifferenced([True for _ in range(num_dofs)])
        acc_min_pass_proto.setMarkerRMS(acc_minimizer_ik_error_report.rootMeanSquaredError)
        acc_min_pass_proto.setMarkerMax(acc_minimizer_ik_error_report.maxError)
        acc_min_pass_proto.computeValuesFromForcePlates(kinematics_skeleton,
                                                        dt,
                                                        positions,
                                                        subject.getGroundForceBodies(),
                                                        lowpass_force_plates)
        acc_min_pass_proto.setAccelerationMinimizingRegularization(pose_regularization)
        acc_min_pass_proto.setAccelerationMinimizingForceRegularization(pose_regularization)
