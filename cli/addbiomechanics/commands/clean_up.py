import random

from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
import tempfile
from typing import List, Dict, Tuple
import itertools
import json
from addbiomechanics.bad_frames_detector.thresholds import ThresholdsDetector


class CleanUpCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        parser = subparsers.add_parser(
            'clean-up', help='This command will read a SubjectOnDisk binary file, or a folder full of them, '
                             'truncate them all back to just the kinematics passes, apply a smoothing filter, and then '
                             're-run the dynamics optimization, and then write out the result to a new binary file or folder with the '
                             'same relative paths.')
        parser.add_argument('input_path', type=str)
        parser.add_argument('output_path', type=str)
        parser.add_argument('--skip-dynamics', action='store_true', help='Skip the dynamics optimization step')
        parser.add_argument('--filter-non-dynamics-trials', action='store_true', help='Filter out trials that are not suitable for dynamics optimization')

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'clean-up':
            return False

        try:
            import nimblephysics as nimble
        except ImportError:
            print(
                "The required library 'nimblephysics' is not installed. Please install it and try this command again.")
            return True
        try:
            import numpy as np
        except ImportError:
            print("The required library 'numpy' is not installed. Please install it and try this command again.")
            return True

        input_path_raw: str = os.path.abspath(args.input_path)
        output_path_raw: str = os.path.abspath(args.output_path)
        skip_dynamics: bool = args.skip_dynamics
        filter_non_dynamics_trials: bool = args.filter_non_dynamics_trials

        input_output_pairs: List[Tuple[str, str]] = []

        if os.path.isfile(input_path_raw):
            input_output_pairs.append((input_path_raw, output_path_raw))
        elif os.path.isdir(input_path_raw):
            # Iterate over the directory structure, and append (input_path, output_path) pairs to
            # input_output_pairs for every file in the input_path_raw directory that ends with a *.bin.
            # Output_path preserves the relative path to the file, but is in the output_path_raw directory instead.
            for dirpath, dirnames, filenames in os.walk(input_path_raw):
                for filename in filenames:
                    if filename.endswith('.b3d'):
                        input_path = os.path.join(dirpath, filename)
                        # Create the output_path preserving the relative path
                        relative_path = os.path.relpath(input_path, input_path_raw)
                        if len(relative_path) == 0:
                            relative_path = filename
                        output_path = os.path.join(output_path_raw, relative_path)
                        if os.path.exists(output_path) or os.path.exists(output_path + '.error'):
                            print('Skipping ' + input_path + ' because the output file already exists at ' + output_path)
                        else:
                            # Ensure the directory structure for the output path exists
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)

                            input_output_pairs.append((input_path, output_path))

        random.shuffle(input_output_pairs)

        print('Will clean-up '+str(len(input_output_pairs))+' file' + ("s" if len(input_output_pairs) > 1 else ""))
        for file_index, (input_path, output_path) in enumerate(input_output_pairs):
            print('Reading SubjectOnDisk '+str(file_index+1)+'/'+str(len(input_output_pairs))+' at ' + input_path + '...')

            # Read all the contents from the current SubjectOnDisk
            subject: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(input_path)

            print('Reading all frames')
            subject.loadAllFrames(doNotStandardizeForcePlateData=True)

            # Truncate the subject to just the kinematics passes
            subject.getHeaderProto().trimToProcessingPasses(1)

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
                    print('DETECTED CORRUPT FILE: Skipping trial '+str(i)+' because it has no passes')
                    corrupt_file = True
                    break
                kinematics_pass = trial_proto.getPasses()[0]
                if kinematics_pass is None:
                    print('DETECTED CORRUPT FILE: Skipping trial '+str(i)+' because it has no kinematics pass')
                    corrupt_file = True
                    break
                marker_observations = trial_proto.getMarkerObservations()

                #######################################################################################################
                # Acceleration Minimization Pass
                #######################################################################################################

                print('Minimizing acceleration on trial '+str(i))

                trial_len = subject.getTrialLength(i)
                dt = subject.getTrialTimestep(i)
                pose_regularization = 1000.0
                acceleration_minimizer = nimble.utils.AccelerationMinimizer(trial_len, 1.0 / (dt * dt), pose_regularization)

                positions = kinematics_pass.getPoses()

                # Unwrap the positions to avoid discontinuities
                for t in range(1, trial_len):
                    positions[:, t] = kinematics_skeleton.unwrapPositionToNearest(positions[:, t], positions[:, t-1])

                acc_minimized_positions = np.zeros((num_dofs, trial_len))
                for dof in range(num_dofs):
                    acc_minimized_positions[dof, :] = acceleration_minimizer.minimize(positions[dof, :])
                positions = acc_minimized_positions

                velocities = np.zeros((num_dofs, trial_len))
                for t in range(1, trial_len):
                    velocities[:, t] = (positions[:, t] - positions[:, t-1]) / dt
                if trial_len > 1:
                    velocities[:, 0] = velocities[:, 1]

                accelerations = np.zeros((num_dofs, trial_len))
                for t in range(1, trial_len):
                    accelerations[:, t] = (velocities[:, t] - velocities[:, t-1]) / dt
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
                                input_cops[:input_force_start_index + first_reliable_cop_offset] = cop_matrix[j, start + first_reliable_cop_offset]

                                # Scan inwards from the end to find the first force magnitude greater than a cutoff threshold, to
                                # indicate that the CoP has started to get reliable
                                last_reliable_cop_offset = 0
                                for t in range(end - start):
                                    if np.linalg.norm(force_matrix[:, end - 1 - t]) > 50.0:
                                        last_reliable_cop_offset = t
                                        break
                                input_cops[input_force_end_index - last_reliable_cop_offset:] = cop_matrix[j, end - 1 - last_reliable_cop_offset]

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

            if corrupt_file:
                print('No good dynamics trials found')
                # os.path.dirname gets the directory portion from the full path
                directory = os.path.dirname(output_path)
                # Create the directory structure, if it doesn't exist already
                os.makedirs(directory, exist_ok=True)
                with open(output_path + '.error', 'w') as f:
                    f.write('No good dynamics trials found')
                continue

            #######################################################################################################
            # Thresholds to decide if we should do the dynamics optimization, and if so which frames to keep
            #######################################################################################################
            detector = ThresholdsDetector()
            missing_grf: List[List[nimble.biomechanics.MissingGRFReason]] = detector.estimate_missing_grfs(subject, list(range(num_trials)))
            dynamics_trials: List[int] = []
            for i in range(num_trials):
                trial_protos[i].setMissingGRFReason(missing_grf[i])
                num_not_missing = sum([missing == nimble.biomechanics.MissingGRFReason.notMissingGRF for missing in missing_grf[i]])
                print(f"Trial {i} has {num_not_missing} frames of good GRF data")
                if num_not_missing < 50:
                    print(f"Trial {i} has less than 50 frames of good GRF data. Skipping dynamics optimization.")
                    continue
                # Run the dynamics optimization
                print('Running dynamics optimization on trial '+str(i) + '/' + str(num_trials))
                dynamics_trials.append(i)

            #######################################################################################################
            # Actually run the dynamics fitting problem
            #######################################################################################################
            any_good_dynamics_trials = False
            if len(dynamics_trials) > 0 and not skip_dynamics:
                foot_bodies = [kinematics_skeleton.getBodyNode(body) for body in subject.getGroundForceBodies()]

                dynamics_fitter = nimble.biomechanics.DynamicsFitter(
                    kinematics_skeleton, foot_bodies, kinematics_osim.trackingMarkers)

                dynamics_prefit_poses = []
                dynamics_prefit_trials = []
                for trial in dynamics_trials:
                    trial_len = subject.getTrialLength(trial)
                    missing_grf = subject.getMissingGRF(trial)
                    track_indices = [missing_reason == nimble.biomechanics.MissingGRFReason.notMissingGRF for missing_reason in missing_grf]

                    num_tracked = sum(track_indices)
                    if num_tracked == 0 or trial_len < 10:
                        continue

                    print("Fitting COM acceleration on trial: " + str(trial))

                    trial_proto = trial_protos[trial]
                    smoothed_pass = trial_proto.getPasses()[1]
                    poses = smoothed_pass.getPoses()
                    root_poses = poses[3:6, :]
                    accs = smoothed_pass.getAccs()
                    root_linear_accs = accs[3:6, :]
                    com_accs = smoothed_pass.getComAccs()
                    acc_offsets = com_accs - root_linear_accs

                    total_forces = np.zeros((3, trial_len))
                    cop_torque_force_in_root = smoothed_pass.getGroundBodyCopTorqueForce()
                    num_force_plates = int(cop_torque_force_in_root.shape[0] / 9)
                    for j in range(num_force_plates):
                        total_forces += cop_torque_force_in_root[j * 9 + 6:j * 9 + 9, :]

                    # We want our root linear acceleration to offset enough to match the total forces
                    goal_com_accs = total_forces / subject.getMassKg()
                    com_acc_errors = goal_com_accs - com_accs

                    target_root_linear_accs = root_linear_accs + com_acc_errors

                    # Now we want to try to find a set of root translations that match the target root linear accs on
                    # the frames with observed forces, and otherwise revert to our classic
                    # AccelerationMinimizingSmoother.

                    dt = subject.getTrialTimestep(trial)
                    zero_unobserved_acc_weight = 1.0
                    track_observed_acc_weight = 100.0
                    regularization_weight = 1000.0
                    smooth_and_track = nimble.utils.AccelerationTrackAndMinimize(len(track_indices), track_indices, zeroUnobservedAccWeight=zero_unobserved_acc_weight, trackObservedAccWeight=track_observed_acc_weight, regularizationWeight=regularization_weight, dt=dt)

                    output_root_poses = np.zeros((3, trial_len))
                    for index in range(3):
                        root_pose = root_poses[index, :]
                        target_accs = target_root_linear_accs[index, :]
                        for t in range(trial_len):
                            if not track_indices[t]:
                                target_accs[t] = 0.0
                        output = smooth_and_track.minimize(root_pose, target_accs)
                        output_root_poses[index, :] = output.series
                        offset = output.accelerationOffset

                        input_acc = np.zeros(trial_len)
                        output_acc = np.zeros(trial_len)
                        for t in range(1, trial_len - 1):
                            input_acc[t] = (root_pose[t + 1] - 2 * root_pose[t] + root_pose[t - 1]) / (dt * dt)
                            output_acc[t] = (output.series[t + 1] - 2 * output.series[t] + output.series[t - 1]) / (dt * dt)
                        if trial_len > 2:
                            input_acc[0] = input_acc[1]
                            input_acc[trial_len - 1] = input_acc[trial_len - 2]
                            output_acc[0] = output_acc[1]
                            output_acc[trial_len - 1] = output_acc[trial_len - 2]

                    output_root_acc = np.zeros((3, trial_len))
                    for t in range(1, trial_len - 1):
                        output_root_acc[:, t] = (output_root_poses[:, t + 1] - 2 * output_root_poses[:, t] + output_root_poses[:, t - 1]) / (dt * dt)
                    if trial_len > 2:
                        output_root_acc[:, 0] = output_root_acc[:, 1]
                        output_root_acc[:, trial_len - 1] = output_root_acc[:, trial_len - 2]
                    # print("Output root linear accs: " + str(np.mean(output_root_acc, axis=1)))

                    average_root_offset_distance = np.mean(np.linalg.norm(output_root_poses - root_poses, axis=0))
                    if average_root_offset_distance < 0.03:
                        print("Average root offset distance: " + str(average_root_offset_distance))
                        updated_poses = poses.copy()
                        updated_poses[3:6, :] = output_root_poses
                        dynamics_prefit_poses.append(updated_poses)
                        dynamics_prefit_trials.append(trial)
                    else:
                        print("Average root offset distance too large, not applying dynamics to this trial: " + str(average_root_offset_distance))

                if len(dynamics_prefit_trials) > 0:
                    dynamics_trials = dynamics_prefit_trials

                    # Create new force plates, to reflect the smoothed contact data
                    # trial_foot_force_plates = []
                    # for trial in dynamics_trials:
                    #     cop_torque_force_world = trial_protos[trial].getPasses()[1].getGroundBodyCopTorqueForce()
                    #     num_plates = int(cop_torque_force_world.shape[0] / 9)
                    #     force_plate_list = []
                    #     for i in range(num_plates):
                    #         force_plate = nimble.biomechanics.ForcePlate()
                    #         forces: List[np.ndarray] = []
                    #         moments: List[np.ndarray] = []
                    #         centers_of_pressure: List[np.ndarray] = []
                    #         for t in range(subject.getTrialLength(trial)):
                    #             forces.append(cop_torque_force_world[i * 9 + 6:i * 9 + 9, t])
                    #             moments.append(cop_torque_force_world[i * 9 + 3:i * 9 + 6, t])
                    #             centers_of_pressure.append(cop_torque_force_world[i * 9:i * 9 + 3, t])
                    #         force_plate.forces = forces
                    #         force_plate.moments = moments
                    #         force_plate.centersOfPressure = centers_of_pressure
                    #         force_plate_list.append(force_plate)
                    #     trial_foot_force_plates.append(force_plate_list)

                    dynamics_fitter.setCOMHistogramClipBuckets(1)
                    dynamics_fitter.setFillInEndFramesGrfGaps(50)
                    dynamics_init: nimble.biomechanics.DynamicsInitialization = \
                        nimble.biomechanics.DynamicsFitter.createInitialization(
                            kinematics_skeleton,
                            kinematics_markers,
                            kinematics_osim.trackingMarkers,
                            foot_bodies,
                            [trial_lowpass_force_plates[trial] for trial in dynamics_trials],
                            dynamics_prefit_poses,
                            [int(1.0 / trial_protos[trial].getTimestep()) for trial in dynamics_trials],
                            [trial_protos[trial].getMarkerObservations() for trial in dynamics_trials],
                            [],
                            [[nimble.biomechanics.MissingGRFStatus.no if reason == nimble.biomechanics.MissingGRFReason.notMissingGRF else nimble.biomechanics.MissingGRFStatus.yes for reason in trial_protos[trial].getMissingGRFReason()] for trial in dynamics_trials])

                    good_frames_count = 0
                    total_frames_count = 0
                    for trialMissingGRF in dynamics_init.probablyMissingGRF:
                        good_frames_count += sum(
                            [0 if missing == nimble.biomechanics.MissingGRFStatus.yes else 1 for missing in
                             trialMissingGRF])
                        total_frames_count += len(trialMissingGRF)
                    bad_frames_count = total_frames_count - good_frames_count
                    print('Detected missing/bad GRF data on ' + str(bad_frames_count) + '/' + str(
                        total_frames_count) + ' frames',
                          flush=True)
                    if good_frames_count == 0:
                        print('ERROR: we have no good frames of GRF data left after filtering out suspicious GRF '
                              'frames. This probably means input GRF data is badly miscalibrated with respect to '
                              'marker data (maybe they are in different coordinate frames?), or there are unmeasured '
                              'external forces acting on your subject. Aborting the physics fitter!', flush=True)
                    else:
                        dynamics_pass = subject.getHeaderProto().addProcessingPass()
                        dynamics_pass.setOpenSimFileText(subject.getOpensimFileText(0))
                        dynamics_pass.setProcessingPassType(
                            nimble.biomechanics.ProcessingPassType.DYNAMICS)

                        # Run an optimization to figure out the model parameters
                        dynamics_fitter.setIterationLimit(200)
                        dynamics_fitter.setLBFGSHistoryLength(20)

                        dynamics_fitter.runIPOPTOptimization(
                            dynamics_init,
                            nimble.biomechanics.DynamicsFitProblemConfig(kinematics_skeleton)
                            .setDefaults(True)
                            .setResidualWeight(1e-2)
                            .setMaxNumTrials(4)
                            .setConstrainResidualsZero(False)
                            .setMaxNumBlocksPerTrial(20)
                            # .setIncludeInertias(True)
                            # .setIncludeCOMs(True)
                            .setIncludeBodyScales(True)
                            .setIncludeMarkerOffsets(False)
                            .setIncludePoses(True)
                            .setJointWeight(0.0)  # We have to disable this, because we don't have the joint info
                            .setMarkerWeight(50.0)
                            .setRegularizePoses(0.01)
                            .setRegularizeJointAcc(1e-6))

                        # Now re-run a position-only optimization on every trial in the dataset
                        for segment in range(len(dynamics_init.poseTrials)):
                            if len(dynamics_init.probablyMissingGRF[segment]) < 1000:
                                dynamics_fitter.setIterationLimit(200)
                                dynamics_fitter.setLBFGSHistoryLength(20)
                            elif len(dynamics_init.probablyMissingGRF[segment]) < 5000:
                                dynamics_fitter.setIterationLimit(100)
                                dynamics_fitter.setLBFGSHistoryLength(15)
                            else:
                                dynamics_fitter.setIterationLimit(50)
                                dynamics_fitter.setLBFGSHistoryLength(3)

                            dynamics_fitter.runIPOPTOptimization(
                                dynamics_init,
                                nimble.biomechanics.DynamicsFitProblemConfig(
                                    kinematics_skeleton)
                                .setDefaults(True)
                                .setOnlyOneTrial(segment)
                                .setResidualWeight(1e-2)
                                .setConstrainResidualsZero(False)
                                .setIncludePoses(True)
                                .setJointWeight(0.0)  # We have to disable this, because we don't have the joint info
                                .setMarkerWeight(50.0)
                                .setRegularizePoses(0.01)
                                .setRegularizeJointAcc(1e-6))

                            dynamics_positions = dynamics_init.poseTrials[segment]

                            dynamics_ik_error_report = nimble.biomechanics.IKErrorReport(
                                kinematics_skeleton,
                                kinematics_markers,
                                dynamics_positions,
                                marker_observations)

                            trial_proto = trial_protos[dynamics_trials[segment]]
                            marker_observations = trial_proto.getMarkerObservations()
                            trial_dynamics_data = trial_proto.addPass()
                            trial_dynamics_data.setType(nimble.biomechanics.ProcessingPassType.DYNAMICS)
                            trial_dynamics_data.setDofPositionsObserved([True for _ in range(kinematics_skeleton.getNumDofs())])
                            trial_dynamics_data.setDofVelocitiesFiniteDifferenced([True for _ in range(kinematics_skeleton.getNumDofs())])
                            trial_dynamics_data.setDofAccelerationFiniteDifferenced([True for _ in range(kinematics_skeleton.getNumDofs())])
                            trial_dynamics_data.computeValuesFromForcePlates(kinematics_skeleton,
                                                                             subject.getTrialTimestep(dynamics_trials[segment]),
                                                                             dynamics_positions,
                                                                             subject.getGroundForceBodies(),
                                                                             trial_lowpass_force_plates[dynamics_trials[segment]])
                            trial_dynamics_data.setMarkerRMS(dynamics_ik_error_report.rootMeanSquaredError)
                            trial_dynamics_data.setMarkerMax(dynamics_ik_error_report.maxError)
                            any_good_dynamics_trials = True
                        if filter_non_dynamics_trials:
                            keep_trials = []
                            for trial in range(num_trials):
                                if trial in dynamics_trials:
                                    keep_trials.append(True)
                                else:
                                    keep_trials.append(False)
                            subject.getHeaderProto().filterTrials(keep_trials)

            # os.path.dirname gets the directory portion from the full path
            directory = os.path.dirname(output_path)
            # Create the directory structure, if it doesn't exist already
            os.makedirs(directory, exist_ok=True)
            if filter_non_dynamics_trials and not any_good_dynamics_trials:
                print('No good dynamics trials found, not writing this subject to disk')
                with open(output_path+'.error', 'w') as f:
                    f.write('No good dynamics trials found')
                continue
            else:
                # Now write the output back out to the new SubjectOnDisk file
                print('Writing SubjectOnDisk to {}...'.format(output_path))
                nimble.biomechanics.SubjectOnDisk.writeB3D(output_path, subject.getHeaderProto())
                print('Done '+str(file_index+1)+'/'+str(len(input_output_pairs)))
