from addbiomechanics.commands.abstract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
import tempfile
from typing import List, Dict, Tuple
import itertools
import json


class PostProcessCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        parser = subparsers.add_parser(
            'post-process', help='This command will read a SubjectOnDisk binary file, or a folder full of them, '
                                 'do some processing (e.g. lowpass filter the values and/or standardize the sample '
                                 'rates), and then write out the result to a new binary file or folder with the '
                                 'same relative paths.')
        parser.add_argument('input_path', type=str)
        parser.add_argument('output_path', type=str)
        parser.add_argument('--geometry-folder', type=str, default=None)
        parser.add_argument(
            '--only-reviewed',
            help='Filter to only trial segments with reviews',
            type=bool,
            default=False)
        parser.add_argument(
            '--only-dynamics',
            help='Filter to only trial segments with dynamics',
            type=bool,
            default=False)
        parser.add_argument('--clean-up-noise', help='Smooth the finite-differenced quantities to have a similar frequency profile to the original signals. Also clean up CoP data to only include physically plausible CoPs (near the feet).', type=bool, default=False)
        parser.add_argument(
            '--recompute-values',
            help='Load skeletons and recompute all values, which will fill any new fields in B3D that have been added '
                 'since the original files were generated',
            type=bool,
            default=False)
        parser.add_argument(
            '--root-history-len',
            help='The number of frames to use when recomputing the root position and rotation history, in the root '
                 'frame. This is ignored unless --recompute-values is specified.',
            type=int,
            default=5
        )
        parser.add_argument(
            '--root-history-stride',
            help='The stride to use when recomputing the root position and rotation history, in the root '
                 'frame. This is ignored unless --recompute-values is specified.',
            type=int,
            default=1
        )
        parser.add_argument(
            '--sample-rate',
            help='The new sample rate to enforce on all the data, if specified, either by up-sampling or down-sampling',
            type=int,
            default=None)
        parser.add_argument(
            '--allowed-contact-bodies',
            nargs='+',
            help='The only contact bodies which are allowed non-zero contact forces in included trials. If specified '
                 'we will mark frames with forces on other bodies as missing GRF.',
            type=str,
            default=[])

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'post-process':
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
        try:
            from scipy.signal import butter, filtfilt, resample_poly, resample, welch
            from scipy.interpolate import interp1d
        except ImportError:
            print("The required library 'scipy' is not installed. Please install it and try this command again.")
            return True

        # Handy little utility for resampling a discrete signal
        def resample_discrete(signal, new_length: int):
            # Get an array of indices for the new signal
            indices = np.round(np.linspace(0, len(signal) - 1, new_length)).astype(int)
            # Limit indices to the valid range
            indices = np.clip(indices, 0, len(signal) - 1)
            # Use advanced indexing to get the corresponding values
            resampled_signal = np.array(signal)[indices]
            return resampled_signal.tolist()

        dropped_trials_log = open('dropped_trials.txt', 'w')

        input_path_raw: str = os.path.abspath(args.input_path)
        output_path_raw: str = os.path.abspath(args.output_path)
        sample_rate: int = args.sample_rate
        recompute_values: bool = args.recompute_values
        only_dynamics: bool = args.only_dynamics
        root_history_len: int = args.root_history_len
        root_history_stride: int = args.root_history_stride
        geometry_folder: str = args.geometry_folder
        clean_up_noise: bool = args.clean_up_noise
        allowed_contact_bodies: List[str] = args.allowed_contact_bodies
        if geometry_folder is not None:
            geometry_folder = os.path.abspath(geometry_folder) + '/'
        else:
            geometry_folder = os.path.abspath(os.path.join(os.path.dirname(input_path_raw), 'Geometry')) + '/'
        print('Geometry folder: ' + geometry_folder)

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
                        output_path = os.path.join(output_path_raw, relative_path)
                        if os.path.exists(output_path):
                            print('Skipping ' + input_path + ' because the output file already exists at ' + output_path)
                        else:
                            # Ensure the directory structure for the output path exists
                            os.makedirs(os.path.dirname(output_path), exist_ok=True)

                            input_output_pairs.append((input_path, output_path))

        print('Will post-process '+str(len(input_output_pairs))+' file' + ("s" if len(input_output_pairs) > 1 else ""))
        for file_index, (input_path, output_path) in enumerate(input_output_pairs):
            print('Reading SubjectOnDisk '+str(file_index+1)+'/'+str(len(input_output_pairs))+' at ' + input_path + '...')

            # Read all the contents from the current SubjectOnDisk
            subject: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(input_path)

            drop_trials: List[int] = []
            if only_dynamics:
                has_dynamics_pass = False
                for pass_num in range(subject.getNumProcessingPasses()):
                    if subject.getProcessingPassType(pass_num) == nimble.biomechanics.ProcessingPassType.DYNAMICS:
                        has_dynamics_pass = True
                        break
                if not has_dynamics_pass:
                    print('Skipping ' + input_path + ' because it does not have any dynamics processing passes.')
                    continue

                for trial in range(subject.getNumTrials()):
                    has_dynamics_pass = False
                    for pass_num in range(subject.getTrialNumProcessingPasses(trial)):
                        if subject.getProcessingPassType(pass_num) == nimble.biomechanics.ProcessingPassType.DYNAMICS:
                            has_dynamics_pass = True
                            break
                    if not has_dynamics_pass:
                        dropped_trials_log.write(f'{input_path} trial {trial} has no dynamics pass\n')
                        dropped_trials_log.flush()
                        drop_trials.append(trial)
                    else:
                        missing_grf_reason: List[nimble.biomechanics.MissingGRFReason] = subject.getHeaderProto().getTrials()[trial].getMissingGRFReason()
                        num_steps_not_missing_grf = len([reason for reason in missing_grf_reason if reason == nimble.biomechanics.MissingGRFReason.notMissingGRF])
                        if num_steps_not_missing_grf == 0:
                            dropped_trials_log.write(f'{input_path} trial {trial} has no steps with non-missing GRF, even though it has a dynamics pass\n')
                            dropped_trials_log.flush()
                            drop_trials.append(trial)

            print('Reading all frames')
            subject.loadAllFrames(doNotStandardizeForcePlateData=True)

            trial_folder_path = os.path.join(os.path.dirname(input_path), 'trials')
            if os.path.exists(trial_folder_path) and os.path.isdir(trial_folder_path):
                trial_protos = subject.getHeaderProto().getTrials()
                for trial_index in range(subject.getNumTrials()):
                    original_name = trial_protos[trial_index].getOriginalTrialName()
                    split_index = trial_protos[trial_index].getSplitIndex()
                    review_flag_path = os.path.join(trial_folder_path, original_name, 'segment_'+str(split_index+1), 'REVIEWED')
                    review_path = os.path.join(trial_folder_path, original_name, 'segment_'+str(split_index+1), 'review.json')
                    missing_grf_reason: List[nimble.biomechanics.MissingGRFReason] = trial_protos[
                        trial_index].getMissingGRFReason()
                    user_reviewed = False
                    if os.path.exists(review_path):
                        review_json = json.load(open(review_path, 'r'))
                        if 'missing_grf_data' not in review_json:
                            print(
                                f'Warning! Review file {review_path} missing the key "missing_grf_data". Skipping review file.')
                        else:
                            missing_flags: List[bool] = review_json['missing_grf_data']
                            # There was a bug in the old UI which would add extra boolean onto the end of the
                            # missing_grf_data file. These are harmless, and we should just ignore them.
                            if len(missing_flags) >= len(missing_grf_reason):
                                for i in range(len(missing_grf_reason)):
                                    if missing_flags[i]:
                                        missing_grf_reason[i] = nimble.biomechanics.MissingGRFReason.manualReview
                                    else:
                                        # TODO: is this a good idea? This data will not have correct torques, angular
                                        #  residuals, etc.
                                        # missing_grf_reason[i] = nimble.biomechanics.MissingGRFReason.notMissingGRF
                                        pass
                                user_reviewed = True
                                print('User reviews incorporated from ' + review_path)
                            else:
                                print(f'Warning! Review file {review_path} has a smaller number of missing GRF flags ({len(missing_flags)}) than the B3D file ({len(missing_grf_reason)}). Skipping review file.')
                    elif os.path.exists(review_flag_path):
                        user_reviewed = True
                    if not user_reviewed:
                        missing_grf_reason = [
                            nimble.biomechanics.MissingGRFReason.manualReview for _ in range(len(missing_grf_reason))
                        ]
                    trial_protos[trial_index].setMissingGRFReason(missing_grf_reason)

            allowed_contact_bodies = sorted(allowed_contact_bodies)
            if len(allowed_contact_bodies) > 0:
                subject_bodies: List[str] = subject.getGroundForceBodies()
                subject_bodies = sorted(subject_bodies)
                # If the lists are order-independent identical, then we can skip this filtering step
                if len(subject_bodies) != len(allowed_contact_bodies) or \
                        any([subject_bodies[i] != allowed_contact_bodies[i] for i in range(len(subject_bodies))]):

                    print('Filtering out contact forces on bodies other than ' + str(allowed_contact_bodies))
                    banned_indices: List[int] = []
                    for i in range(len(subject_bodies)):
                        if subject_bodies[i] not in allowed_contact_bodies:
                            banned_indices.append(i)

                    trial_protos = subject.getHeaderProto().getTrials()
                    for trial_index in range(subject.getNumTrials()):
                        filtered_timesteps = 0
                        missing_grf_reason: List[nimble.biomechanics.MissingGRFReason] = trial_protos[trial_index].getMissingGRFReason()
                        first_pass_proto = trial_protos[trial_index].getPasses()[0]
                        grf: np.ndarray = first_pass_proto.getGroundBodyCopTorqueForce()
                        for t in range(grf.shape[1]):
                            for i in banned_indices:
                                if np.linalg.norm(grf[9*i+6:9*i+9, t]) > 5:
                                    filtered_timesteps += 1
                                    missing_grf_reason[t] = nimble.biomechanics.MissingGRFReason.unmeasuredExternalForceDetected
                                    break
                        trial_protos[trial_index].setMissingGRFReason(missing_grf_reason)

                        print(f'Contact forces filtered {filtered_timesteps} timesteps on trial {subject.getTrialName(trial_index)}')


            resampled = False
            if sample_rate is not None:
                print('Re-sampling kinematics + kinetics data at {} Hz...'.format(sample_rate))
                print('Warning! Re-sampling input source data (IMU, EMG) is not yet supported, so those will '
                      'be zeroed out')
                resampled = True

                trial_protos = subject.getHeaderProto().getTrials()
                for trial in range(subject.getNumTrials()):
                    trial_pass_protos = trial_protos[trial].getPasses()
                    if len(trial_pass_protos) == 0:
                        print(f'Warning! Dropping trial {trial} because it has no processing passes')
                        dropped_trials_log.write(f'ERROR {input_path} trial {trial} has no processing passes\n')
                        dropped_trials_log.flush()
                        drop_trials.append(trial)
                        continue

                    # Overwrite the force plates with the version from the feet
                    print(f'Overwriting force plates for trial {trial} with the version from the feet')
                    num_contact_bodies = len(subject.getGroundForceBodies())
                    cop_torque_force: np.ndarray = trial_pass_protos[-1].getGroundBodyCopTorqueForce()
                    assert(cop_torque_force.shape[0] == 9 * num_contact_bodies)
                    new_force_plates: List[nimble.biomechanics.ForcePlate] = []
                    for i in range(num_contact_bodies):
                        new_plate: nimble.biomechanics.ForcePlate = nimble.biomechanics.ForcePlate()
                        raw_cops: List[np.ndarray] = []
                        raw_torques: List[np.ndarray] = []
                        raw_forces: List[np.ndarray] = []
                        for t in range(cop_torque_force.shape[1]):
                            raw_cops.append(cop_torque_force[9 * i:9 * i + 3, t])
                            raw_torques.append(cop_torque_force[9 * i + 3:9 * i + 6, t])
                            raw_forces.append(cop_torque_force[9 * i + 6:9 * i + 9, t])
                        new_plate.forces = raw_forces
                        new_plate.moments = raw_torques
                        new_plate.centersOfPressure = raw_cops
                        new_force_plates.append(new_plate)
                    trial_protos[trial].setForcePlates(new_force_plates)

                    # Set the timestep
                    original_sample_rate = int(1.0 / subject.getTrialTimestep(trial))
                    if original_sample_rate != int(sample_rate):
                        trial_protos[trial].setTimestep(1.0 / sample_rate)

                        raw_force_plates: List[nimble.biomechanics.ForcePlate] = trial_protos[trial].getForcePlates()
                        for force_plate in raw_force_plates:
                            resampling_matrix, ground_heights = force_plate.getResamplingMatrixAndGroundHeights()
                            resampling_matrix = resample_poly(resampling_matrix, sample_rate, original_sample_rate, axis=1, padtype='line')
                            ground_heights = resample_discrete(ground_heights, resampling_matrix.shape[1])
                            force_plate.setResamplingMatrixAndGroundHeights(resampling_matrix, ground_heights)
                        trial_protos[trial].setForcePlates(raw_force_plates)

                        trial_len = subject.getTrialLength(trial)
                        for processing_pass in range(subject.getTrialNumProcessingPasses(trial)):
                            resampling_matrix = trial_pass_protos[processing_pass].getResamplingMatrix()
                            resampling_matrix = resample_poly(resampling_matrix, sample_rate, original_sample_rate, axis=1, padtype='line')
                            trial_pass_protos[processing_pass].setResamplingMatrix(resampling_matrix)
                            trial_len = resampling_matrix.shape[1]

                        resampled_markers = resample_discrete(trial_protos[trial].getMarkerObservations(), trial_len)
                        print(f'Resampled markers on trial {trial} from {len(trial_protos[trial].getMarkerObservations())} frames to {len(resampled_markers)} frames')
                        assert(len(resampled_markers) == trial_len)
                        trial_protos[trial].setMarkerObservations(resampled_markers)
                        # Re-sample the discrete values
                        trial_protos[trial].setMissingGRFReason(
                            resample_discrete(trial_protos[trial].getMissingGRFReason(),
                                              trial_len))

            if clean_up_noise or recompute_values or resampled:
                pass_skels: List[nimble.dynamics.Skeleton] = []
                for processing_pass in range(subject.getNumProcessingPasses()):
                    print('Reading skeleton for processing pass ' + str(processing_pass) + '...')
                    skel = subject.readSkel(processing_pass, geometryFolder=geometry_folder)
                    print('Pass type: ' + str(subject.getProcessingPassType(processing_pass)))
                    pass_skels.append(skel)

                for i in range(len(pass_skels)):
                    if pass_skels[i] is None and i > 0:
                        subject.getHeaderProto().getProcessingPasses()[i].setOpenSimFileText(
                            subject.getHeaderProto().getProcessingPasses()[i - 1].getOpenSimFileText())
                        pass_skels[i] = pass_skels[i - 1]

            if clean_up_noise:
                print('Cleaning up data')

                def find_cutoff_frequency(signal, fs=100) -> float:
                    frequencies, psd = welch(signal, fs, nperseg=min(1024, len(signal)))
                    cumulative_power = np.cumsum(psd)
                    total_power = np.sum(psd)
                    cutoff_power = 0.99 * total_power
                    cutoff_frequency_index = np.where(cumulative_power >= cutoff_power)[0][0]
                    return frequencies[cutoff_frequency_index]

                trial_protos = subject.getHeaderProto().getTrials()
                new_overall_pass = subject.getHeaderProto().addProcessingPass()
                new_overall_pass.setProcessingPassType(nimble.biomechanics.ProcessingPassType.LOW_PASS_FILTER)
                new_overall_pass.setOpenSimFileText(subject.getHeaderProto().getProcessingPasses()[-2].getOpenSimFileText())
                pass_skels.append(pass_skels[-1])

                use_lowpass = False

                for trial in range(subject.getNumTrials()):
                    if trial in drop_trials:
                        continue
                    # Add a lowpass filter pass to the end of the trial
                    trial_pass_protos = trial_protos[trial].getPasses()
                    last_pass_proto = trial_pass_protos[-1]
                    poses = last_pass_proto.getPoses()

                    # Skip short trials, add them to the drop list
                    if poses.shape[1] <= 12:
                        drop_trials.append(trial)
                        dropped_trials_log.write(f'{input_path} trial {trial} shorter than 12 frames\n')
                        dropped_trials_log.flush()
                        continue

                    dt = trial_protos[trial].getTimestep()
                    fs = int(1.0 / dt)
                    if use_lowpass:
                        # Use a lowpass filter to clean up the data
                        cutoff_frequencies: List[float] = [find_cutoff_frequency(poses[i, :], fs) for i in range(poses.shape[0])]
                        cutoff = max(max(cutoff_frequencies), 1.0)
                        print(f"Cutoff Frequency to preserve 99% of signal power: {cutoff} Hz")
                        nyq = 0.5 * fs
                        normal_cutoff = cutoff / nyq
                        if cutoff >= nyq:
                            print('Warning! Cutoff frequency is at or above Nyquist frequency. This suggests some funny business with the data. Dropping this trial to be on the safe side.')
                            # dropped_trials_log.write(f'ERROR {input_path} trial {trial} cutoff frequency above Nyquist frequency\n')
                            # dropped_trials_log.flush()
                            # drop_trials.append(trial)
                        else:
                            b, a = butter(3, normal_cutoff, btype='low', analog=False)
                            new_pass = trial_protos[trial].addPass()
                            new_pass.copyValuesFrom(last_pass_proto)
                            new_pass.setType(nimble.biomechanics.ProcessingPassType.LOW_PASS_FILTER)
                            new_pass.setLowpassFilterOrder(3)
                            new_pass.setLowpassCutoffFrequency(cutoff)
                            accs = new_pass.getAccs()
                            if accs.shape[1] > 1:
                                accs[:, 0] = accs[:, 1]
                                accs[:, -1] = accs[:, -2]
                                new_pass.setAccs(accs)
                            vels = new_pass.getVels()
                            if vels.shape[1] > 1:
                                vels[:, 0] = vels[:, 1]
                                vels[:, -1] = vels[:, -2]
                                new_pass.setVels(vels)
                            if poses.shape[1] > 12:
                                new_pass.setResamplingMatrix(filtfilt(b, a, new_pass.getResamplingMatrix(), axis=1, padtype='constant'))

                            # Copy force plate data to Python
                            raw_force_plates = trial_protos[trial].getForcePlates()
                            cops = [force_plate.centersOfPressure for force_plate in raw_force_plates]
                            force_plate_raw_forces = [force_plate.forces for force_plate in raw_force_plates]

                            print('Fixing COM acceleration for trial ' + str(trial))
                            skel = pass_skels[-1]
                            new_poses = new_pass.getPoses()
                            new_vels = new_pass.getVels()
                            new_accs = new_pass.getAccs()
                            for t in range(new_poses.shape[1]):
                                pass_skels[-1].setPositions(new_poses[:, t])
                                pass_skels[-1].setVelocities(new_vels[:, t])
                                pass_skels[-1].setAccelerations(new_accs[:, t])
                                com_acc = pass_skels[-1].getCOMLinearAcceleration() - pass_skels[-1].getGravity()
                                total_acc = np.sum(np.row_stack([force_plate_raw_forces[f][t] for f in range(len(raw_force_plates))]), axis=0) / pass_skels[-1].getMass()
                                # print('Expected acc: '+str(total_acc))
                                # print('Got acc: '+str(com_acc))
                                root_acc_correction = total_acc - com_acc
                                # print('Correcting root acc: '+str(root_acc_correction))
                                new_accs[3:6, t] += root_acc_correction
                            trial_protos[trial].getPasses()[-1].setAccs(new_accs)


                            # Check the CoP data to ensure it is physically plausible
                            print('Cleaning up CoP data for trial ' + str(trial))
                            foot_bodies = [skel.getBodyNode(name) for name in subject.getGroundForceBodies()]
                            dist_threshold_m = 0.35  # A bit more than 1 foot

                            num_timesteps_cop_wrong = 0
                            cutoff_threshold_to_drop_trial = 10
                            missing_grf_reason = trial_protos[trial].getMissingGRFReason()
                            for t in range(new_poses.shape[1]):
                                if missing_grf_reason[t] != nimble.biomechanics.MissingGRFReason.notMissingGRF:
                                    continue
                                skel.setPositions(new_poses[:, t])
                                foot_body_locations = [body.getWorldTransform().translation() for body in foot_bodies]
                                for f in range(len(raw_force_plates)):
                                    force = force_plate_raw_forces[f][t]
                                    cop = cops[f][t]
                                    dist_to_feet = [np.linalg.norm(cop - foot_body_location) for foot_body_location in
                                                    foot_body_locations]
                                    if np.linalg.norm(force) > 5:
                                        if min(dist_to_feet) > dist_threshold_m:
                                            closest_foot = np.argmin(dist_to_feet)
                                            num_timesteps_cop_wrong += 1
                                            if num_timesteps_cop_wrong < cutoff_threshold_to_drop_trial:
                                                print(f"Warning! Trial {trial}, CoP for plate {f} is not near a foot at time {t}. Bringing it within {dist_threshold_m}m of the closest foot.")
                                                print(f"  Force: {force}")
                                                print(f"  CoP: {cop}")
                                                print(f"  Dist to feet: {dist_to_feet}")
                                            cop = foot_body_locations[closest_foot] + dist_threshold_m * (cop - foot_body_locations[closest_foot]) / np.linalg.norm(cop - foot_body_locations[closest_foot])
                                            cops[f][t] = cop
                                            if num_timesteps_cop_wrong < cutoff_threshold_to_drop_trial:
                                                print(f"  Updated CoP: {cop}")
                                                dist_to_feet = [np.linalg.norm(cop - foot_body_location) for foot_body_location in foot_body_locations]
                                                print(f"  Updated Dist to feet: {dist_to_feet}")
                                    else:
                                        force_plate_raw_forces[f][t] = np.zeros(3)
                                        closest_foot = np.argmin(dist_to_feet)
                                        cops[f][t] = foot_body_locations[closest_foot]

                            if num_timesteps_cop_wrong >= cutoff_threshold_to_drop_trial:
                                print(f"Warning! Trial {trial} has {num_timesteps_cop_wrong} timesteps with CoP not near a foot. Dropping trial.")
                                dropped_trials_log.write(f'ERROR {input_path} trial {trial} has {num_timesteps_cop_wrong} timesteps with CoP not near a foot\n')
                                dropped_trials_log.flush()
                                drop_trials.append(trial)
                                continue

                            for f in range(len(raw_force_plates)):
                                raw_force_plates[f].centersOfPressure = cops[f]
                                raw_force_plates[f].forces = force_plate_raw_forces[f]
                            trial_protos[trial].setForcePlates(raw_force_plates)
                    else:
                        # Use an acceleration minimizer to clean up the data
                        dt = trial_protos[trial].getTimestep()
                        acc_weight = 1.0 / (dt * dt)
                        regularization_weight = 1000.0

                        new_pass = trial_protos[trial].addPass()
                        new_pass.copyValuesFrom(last_pass_proto)
                        new_pass.setType(nimble.biomechanics.ProcessingPassType.LOW_PASS_FILTER)
                        new_pass.setLowpassFilterOrder(-1)
                        new_pass.setLowpassCutoffFrequency(regularization_weight)

                        poses = new_pass.getPoses().copy()

                        acc_minimizer = nimble.utils.AccelerationMinimizer(poses.shape[1], acc_weight,
                                                                           regularization_weight)
                        for i in range(poses.shape[0]):
                            poses[i, :] = acc_minimizer.minimize(poses[i, :])
                        new_pass.setPoses(poses)

                        # Get velocities and accelerations as finite differences
                        vels = np.zeros_like(poses)
                        for i in range(1, poses.shape[1]):
                            vels[:, i] = (poses[:, i] - poses[:, i - 1]) / dt
                        vels[:, 0] = vels[:, 1]
                        new_pass.setVels(vels)
                        accs = np.zeros_like(poses)
                        for i in range(1, poses.shape[1]):
                            accs[:, i] = (vels[:, i] - vels[:, i - 1]) / dt
                        accs[:, 0] = accs[:, 1]
                        new_pass.setAccs(accs)

                        print('Minimized accelerations for trial ' + str(trial))
                        print('Max acc: ' + str(np.max(accs)))
                        print('Min acc: ' + str(np.min(accs)))

                        # Copy force plate data to Python
                        raw_force_plates = trial_protos[trial].getForcePlates()
                        force_plate_raw_forces: List[List[np.ndarray]] = [force_plate.forces for force_plate in raw_force_plates]
                        force_plate_raw_cops: List[List[np.ndarray]] = [force_plate.centersOfPressure for force_plate in raw_force_plates]
                        force_plate_raw_moments: List[List[np.ndarray]] = [force_plate.moments for force_plate in raw_force_plates]

                        trial_len = poses.shape[1]
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
                                    acc_minimizer = nimble.utils.AccelerationMinimizer(end - start, acc_weight,
                                                                                       regularization_weight,
                                                                                       startPositionZeroWeight=start_weight,
                                                                                       endPositionZeroWeight=end_weight,
                                                                                       startVelocityZeroWeight=start_weight,
                                                                                       endVelocityZeroWeight=end_weight)
                                    cop_acc_minimizer = nimble.utils.AccelerationMinimizer(end - start, acc_weight,
                                                                                           regularization_weight)
                                    for j in range(3):
                                        smoothed_force = acc_minimizer.minimize(force_matrix[j, start:end])
                                        if np.sum(smoothed_force) != 0:
                                            smoothed_force *= np.sum(force_matrix[j, start:end]) / np.sum(smoothed_force)
                                        force_matrix[j, start:end] = smoothed_force
                                        cop_matrix[j, start:end] = cop_acc_minimizer.minimize(cop_matrix[j, start:end])
                                        smoothed_moment = acc_minimizer.minimize(moment_matrix[j, start:end])
                                        if np.sum(smoothed_moment) != 0:
                                            smoothed_moment *= np.sum(moment_matrix[j, start:end]) / np.sum(smoothed_moment)
                                        moment_matrix[j, start:end] = smoothed_moment
                                    for t in range(start, end):
                                        force_plate_raw_forces[i][t] = force_matrix[:, t]
                                        force_plate_raw_cops[i][t] = cop_matrix[:, t]
                                        force_plate_raw_moments[i][t] = moment_matrix[:, t]

                            # 4.3. Create a new lowpass filtered force plate
                            force_plate_copy = nimble.biomechanics.ForcePlate.copyForcePlate(raw_force_plates[i])
                            force_plate_copy.forces = force_plate_raw_forces[i]
                            force_plate_copy.centersOfPressure = force_plate_raw_cops[i]
                            force_plate_copy.moments = force_plate_raw_moments[i]
                            lowpass_force_plates.append(force_plate_copy)
                        trial_protos[trial].setForcePlates(lowpass_force_plates)

                        print('Fixing COM acceleration for trial ' + str(trial))
                        skel = pass_skels[-1]
                        new_poses = new_pass.getPoses()
                        new_vels = new_pass.getVels()
                        new_accs = new_pass.getAccs()
                        for t in range(new_poses.shape[1]):
                            pass_skels[-1].setPositions(new_poses[:, t])
                            pass_skels[-1].setVelocities(new_vels[:, t])
                            pass_skels[-1].setAccelerations(new_accs[:, t])
                            com_acc = pass_skels[-1].getCOMLinearAcceleration() - pass_skels[-1].getGravity()
                            total_acc = np.sum(np.row_stack([force_plate_raw_forces[f][t] for f in range(len(raw_force_plates))]),
                                               axis=0) / pass_skels[-1].getMass()
                            # print('Expected acc: '+str(total_acc))
                            # print('Got acc: '+str(com_acc))
                            root_acc_correction = total_acc - com_acc
                            # print('Correcting root acc: '+str(root_acc_correction))
                            new_accs[3:6, t] += root_acc_correction
                        trial_protos[trial].getPasses()[-1].setAccs(new_accs)

            if recompute_values or resampled or clean_up_noise:
                print('Recomputing values in the raw B3D')

                subject.getHeaderProto().setNumJoints(pass_skels[0].getNumJoints())

                trial_protos = subject.getHeaderProto().getTrials()
                for trial in range(subject.getNumTrials()):
                    timestep = subject.getTrialTimestep(trial)
                    raw_force_plates = trial_protos[trial].getForcePlates()
                    trial_pass_protos = trial_protos[trial].getPasses()
                    print('##########')
                    print('Trial '+str(trial)+':')
                    for processing_pass in range(subject.getTrialNumProcessingPasses(trial)):
                        poses = np.copy(trial_pass_protos[processing_pass].getPoses())
                        explicit_vel = np.copy(trial_pass_protos[processing_pass].getVels())
                        explicit_acc = np.copy(trial_pass_protos[processing_pass].getAccs())
                        # Check for NaNs in explicit_vel and explicit_acc
                        if np.any(np.isnan(explicit_vel)):
                            print('Warning! NaNs in explicit_vel for trial ' + str(trial) + ' pass ' + str(processing_pass))
                            dropped_trials_log.write(f'ERROR {input_path} trial {trial} has NaNs in the explicit_vel array\n')
                            dropped_trials_log.flush()
                            drop_trials.append(trial)
                            continue
                        if np.any(np.isnan(explicit_acc)):
                            print('Warning! NaNs in explicit_acc for trial ' + str(trial) + ' pass ' + str(processing_pass))
                            dropped_trials_log.write(f'ERROR {input_path} trial {trial} has NaNs in the explicit_acc array\n')
                            dropped_trials_log.flush()
                            drop_trials.append(trial)
                            continue
                        assert(poses.shape == explicit_vel.shape)
                        assert(poses.shape == explicit_acc.shape)
                        trial_pass_protos[processing_pass].computeValuesFromForcePlates(pass_skels[processing_pass], timestep, poses, subject.getGroundForceBodies(), raw_force_plates, rootHistoryLen=root_history_len, rootHistoryStride=root_history_stride, explicitVels=explicit_vel, explicitAccs=explicit_acc)
                        if not np.all(trial_pass_protos[processing_pass].getAccs() == explicit_acc):
                            print('WARNING! Explicit accs do not match computed accs!')
                            print('Explicit accs: '+str(explicit_acc))
                            print('Computed accs: '+str(trial_pass_protos[processing_pass].getAccs()))
                        assert(np.all(trial_pass_protos[processing_pass].getAccs() == explicit_acc))
                        assert(np.all(trial_pass_protos[processing_pass].getVels() == explicit_vel))
                        print('Pass '+str(processing_pass)+' of ' + str(subject.getTrialNumProcessingPasses(trial)) +' type: '+str(subject.getProcessingPassType(processing_pass)))
                        print('Range on joint accelerations: '+str(np.min(trial_pass_protos[processing_pass].getAccs()))+' to '+str(np.max(trial_pass_protos[processing_pass].getAccs())))
                        print('Range on joint torques: '+str(np.min(trial_pass_protos[processing_pass].getTaus()))+' to '+str(np.max(trial_pass_protos[processing_pass].getTaus())))
                        print('Linear Residuals: '+str(np.mean(trial_pass_protos[processing_pass].getLinearResidual())))
                        print('Angular Residuals: '+str(np.mean(trial_pass_protos[processing_pass].getAngularResidual())))

            if len(drop_trials) > 0:
                print('Dropping trials: '+str(drop_trials))
                filtered_trials = [trial for i, trial in enumerate(subject.getHeaderProto().getTrials()) if i not in drop_trials]
                subject.getHeaderProto().setTrials(filtered_trials)

            # os.path.dirname gets the directory portion from the full path
            directory = os.path.dirname(output_path)
            # Create the directory structure, if it doesn't exist already
            os.makedirs(directory, exist_ok=True)
            # Now write the output back out to the new SubjectOnDisk file
            print('Writing SubjectOnDisk to {}...'.format(output_path))
            nimble.biomechanics.SubjectOnDisk.writeB3D(output_path, subject.getHeaderProto())
            print('Done '+str(file_index+1)+'/'+str(len(input_output_pairs)))

        dropped_trials_log.close()
        print('Post-processing finished!')

        return True
