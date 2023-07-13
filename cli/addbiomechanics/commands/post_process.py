import scipy.signal
from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
import tempfile
from typing import List, Dict, Tuple

class PostProcessCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        parser = subparsers.add_parser(
            'post-process', help='This command will read a SubjectOnDisk binary file, or a folder full of them, '
                                 'do some processing (e.g. lowpass filter the values and/or standardize the sample '
                                 'rates), and then write out the result to a new binary file or folder with the '
                                 'same relative paths.')
        parser.add_argument('input_path', type=str)
        parser.add_argument('output_path', type=str)
        parser.add_argument(
            '--lowpass-hz',
            help='The frequency to lowpass filter all the position, velocity, acceleration, and torque values',
            type=int,
            default=None)
        parser.add_argument(
            '--sample-rate',
            help='The new sample rate to enforce on all the data, if specified, either by up-sampling or down-sampling',
            type=int,
            default=None)

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
            from scipy.signal import butter, filtfilt, resample_poly
            from scipy.interpolate import interp1d
        except ImportError:
            print("The required library 'scipy' is not installed. Please install it and try this command again.")
            return True


        input_path_raw: str = os.path.abspath(args.input_path)
        output_path_raw: str = os.path.abspath(args.output_path)
        lowpass_hz: int = args.lowpass_hz
        sample_rate: int = args.sample_rate

        input_output_pairs: List[Tuple[str, str]] = []

        if os.path.isfile(input_path_raw):
            input_output_pairs.append((input_path_raw, output_path_raw))
        elif os.path.isdir(input_path_raw):
            # Iterate over the directory structure, and append (input_path, output_path) pairs to
            # input_output_pairs for every file in the input_path_raw directory that ends with a *.bin.
            # Output_path preserves the relative path to the file, but is in the output_path_raw directory instead.
            for dirpath, dirnames, filenames in os.walk(input_path_raw):
                for filename in filenames:
                    if filename.endswith('.bin'):
                        input_path = os.path.join(dirpath, filename)
                        # Create the output_path preserving the relative path
                        relative_path = os.path.relpath(input_path, input_path_raw)
                        output_path = os.path.join(output_path_raw, relative_path)

                        # Ensure the directory structure for the output path exists
                        os.makedirs(os.path.dirname(output_path), exist_ok=True)

                        input_output_pairs.append((input_path, output_path))

        print('Will post-process '+str(len(input_output_pairs))+' file' + ("s" if len(input_output_pairs) > 1 else ""))
        for file_index, (input_path, output_path) in enumerate(input_output_pairs):
            print('Reading SubjectOnDisk '+str(file_index+1)+'/'+str(len(input_output_pairs))+' at ' + input_path + '...')

            # Read all the contents from the current SubjectOnDisk
            subject: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(input_path)

            temp = tempfile.NamedTemporaryFile(mode='w+t', delete=False, suffix='.osim')
            opensim_file_path = temp.name
            try:
                temp.write(subject.readRawOsimFileText())
            finally:
                temp.close()

            dofs = subject.getNumDofs()
            trial_timesteps = [subject.getTrialTimestep(trial) for trial in range(subject.getNumTrials())]
            trial_lengths = [subject.getTrialLength(trial) for trial in range(subject.getNumTrials())]
            trial_poses: List[np.ndarray] = [np.zeros((dofs, trial_lengths[trial])) for trial in
                                             range(subject.getNumTrials())]
            trial_vels: List[np.ndarray] = [np.zeros((dofs, trial_lengths[trial])) for trial in
                                            range(subject.getNumTrials())]
            trial_accs: List[np.ndarray] = [np.zeros((dofs, trial_lengths[trial])) for trial in
                                            range(subject.getNumTrials())]
            probably_missing_grf: List[List[bool]] = [subject.getProbablyMissingGRF(trial) for trial in
                                                      range(subject.getNumTrials())]
            missing_grf_reason: List[List[nimble.biomechanics.MissingGRFReason]] = [
                subject.getMissingGRFReason(trial) for trial in
                range(subject.getNumTrials())]
            dof_positions_observed: List[List[bool]] = [[True for _ in range(dofs)] for _ in range(subject.getNumTrials())]
            dof_velocity_finite_differenced: List[List[bool]] = [[True for _ in range(dofs)] for _ in range(subject.getNumTrials())]
            dof_acc_finite_differenced: List[List[bool]] = [[True for _ in range(dofs)] for _ in range(subject.getNumTrials())]
            trial_taus: List[np.ndarray] = [np.zeros((dofs, trial_lengths[trial])) for trial in
                                            range(subject.getNumTrials())]
            trial_com_poses: List[np.ndarray] = [np.zeros((3, trial_lengths[trial])) for trial in
                                                range(subject.getNumTrials())]
            trial_com_vels: List[np.ndarray] = [np.zeros((3, trial_lengths[trial])) for trial in
                                                 range(subject.getNumTrials())]
            trial_com_accs: List[np.ndarray] = [np.zeros((3, trial_lengths[trial])) for trial in
                                                range(subject.getNumTrials())]
            trial_residual_norms: List[List[float]] = [subject.getTrialResidualNorms(trial) for trial in
                                                       range(subject.getNumTrials())]
            ground_force_bodies: List[str] = subject.getContactBodies()
            trial_ground_body_wrenches: List[np.ndarray] = [np.zeros((6 * len(ground_force_bodies), trial_lengths[trial])) for trial in
                                                            range(subject.getNumTrials())]
            trial_ground_body_cop_torque_force: List[np.ndarray] = [np.zeros((9 * len(ground_force_bodies), trial_lengths[trial])) for trial in
                                                            range(subject.getNumTrials())]
            custom_value_names = subject.getCustomValues()
            custom_values: List[List[np.ndarray]] = [[np.zeros((len(custom_value_names), trial_lengths[trial])) for _ in range(trial_lengths[trial])] for trial in range(subject.getNumTrials())]
            marker_observations: List[List[Dict[str, np.ndarray]]] = [[{} for _ in range(trial_lengths[trial])] for trial in range(subject.getNumTrials())]
            acc_observations: List[List[Dict[str, np.ndarray]]] = [[{} for _ in range(trial_lengths[trial])] for trial in range(subject.getNumTrials())]
            gyro_observations: List[List[Dict[str, np.ndarray]]] = [[{} for _ in range(trial_lengths[trial])] for trial in range(subject.getNumTrials())]
            emg_observations: List[List[Dict[str, np.ndarray]]] = [[{} for _ in range(trial_lengths[trial])] for trial in range(subject.getNumTrials())]
            force_plates: List[List[nimble.biomechanics.ForcePlate]] = [[nimble.biomechanics.ForcePlate() for _ in range(subject.getNumForcePlates(trial))] for trial in range(subject.getNumTrials())]
            biological_sex: str = subject.getBiologicalSex()
            height_m: float = subject.getHeightM()
            mass_kg: float = subject.getMassKg()
            age_years: int = subject.getAgeYears()
            trial_names: List[str] = [subject.getTrialName(trial) for trial in range(subject.getNumTrials())]
            subject_tags: List[str] = subject.getSubjectTags()
            trial_tags: List[List[str]] = [subject.getTrialTags(trial) for trial in range(subject.getNumTrials())]
            source_href: str = subject.getHref()
            notes: str = subject.getNotes()

            force_plate_forces: List[List[List[np.ndarray]]] = [[[] for _ in range(subject.getNumForcePlates(trial))] for trial in range(subject.getNumTrials())]
            force_plate_cops: List[List[List[np.ndarray]]] = [[[] for _ in range(subject.getNumForcePlates(trial))] for trial in range(subject.getNumTrials())]
            force_plate_moments: List[List[List[np.ndarray]]] = [[[] for _ in range(subject.getNumForcePlates(trial))] for trial in range(subject.getNumTrials())]

            for trial in range(len(trial_lengths)):
                for t in range(trial_lengths[trial]):
                    frame: nimble.biomechanics.Frame = subject.readFrames(trial, t, 1)[0]
                    trial_poses[trial][:, t] = frame.pos
                    trial_vels[trial][:, t] = frame.vel
                    trial_accs[trial][:, t] = frame.acc
                    trial_taus[trial][:, t] = frame.tau
                    trial_com_poses[trial][:, t] = frame.comPos
                    trial_com_vels[trial][:, t] = frame.comVel
                    trial_com_accs[trial][:, t] = frame.comAcc
                    trial_ground_body_wrenches[trial][:, t] = frame.groundContactWrenches

                    cops = frame.groundContactCenterOfPressure
                    torques = frame.groundContactTorque
                    forces = frame.groundContactForce
                    for i in range(len(ground_force_bodies)):
                        trial_ground_body_cop_torque_force[trial][i*9:i*9+3, t] = cops[i*3:i*3+3]
                        trial_ground_body_cop_torque_force[trial][i*9+3:i*9+6, t] = torques[i*3:i*3+3]
                        trial_ground_body_cop_torque_force[trial][i*9+6:i*9+9, t] = forces[i*3:i*3+3]

                    for i in range(len(custom_value_names)):
                        custom_values[trial][t][i] = frame.customValues[i]

                    for i in range(len(force_plates[trial])):
                        force_plate_forces[trial][i].append(frame.rawForcePlateForces[i])
                        force_plate_cops[trial][i].append(frame.rawForcePlateCenterOfPressures[i])
                        force_plate_moments[trial][i].append(frame.rawForcePlateTorques[i])

                    marker_observations[trial][t] = dict(frame.markerObservations)
                    acc_observations[trial][t] = dict(frame.accObservations)
                    gyro_observations[trial][t] = dict(frame.gyroObservations)
                    emg_observations[trial][t] = dict(frame.emgSignals)

                for i in range(len(force_plates[trial])):
                    force_plates[trial][i].forces = force_plate_forces[trial][i]
                    force_plates[trial][i].centersOfPressure = force_plate_cops[trial][i]
                    force_plates[trial][i].moments = force_plate_moments[trial][i]

            print('Done reading SubjectOnDisk.')

            # Do any post-processing of the data we just read

            if lowpass_hz is not None:
                print('Low-pass filtering kinematics + kinetics data at {} Hz...'.format(lowpass_hz))

                skel = subject.readSkel(geometryFolder='No_Geometry')

                for trial in range(subject.getNumTrials()):
                    nyquist = 0.5 / subject.getTrialTimestep(trial)
                    if lowpass_hz > nyquist:
                        print('Sample rate on trial '+str(trial)+' of '+str(nyquist * 2)+' is too low to filter at '
                              +str(lowpass_hz)+'. Highest frequency allowed is '+str(nyquist)+', so we will not '
                              +'low-pass filter this example')
                    else:
                        b, a = butter(2, lowpass_hz, 'low', fs=1 / subject.getTrialTimestep(trial))
                        trial_poses[trial] = filtfilt(b, a, trial_poses[trial], axis=1)
                        trial_vels[trial] = filtfilt(b, a, trial_vels[trial], axis=1)
                        trial_accs[trial] = filtfilt(b, a, trial_accs[trial], axis=1)
                        trial_taus[trial] = filtfilt(b, a, trial_taus[trial], axis=1)
                        trial_com_poses[trial] = filtfilt(b, a, trial_com_poses[trial], axis=1)
                        trial_com_vels[trial] = filtfilt(b, a, trial_com_vels[trial], axis=1)
                        trial_com_accs[trial] = filtfilt(b, a, trial_com_accs[trial], axis=1)

                        contact_body_world_positions = [np.zeros((3, trial_lengths[trial])) for _ in range(len(ground_force_bodies))]
                        for t in range(trial_lengths[trial]):
                            skel.setPositions(trial_poses[trial][:, t])
                            for i in range(len(ground_force_bodies)):
                                contact_body_world_positions[i][:, t] = skel.getBodyNode(ground_force_bodies[i]).getWorldTransform().translation()

                        # First, ensure that the GRF data has proper zeros
                        force_plate_norms: List[np.ndarray] = [np.zeros(trial_lengths[trial]) for _ in range(len(force_plates[trial]))]
                        for i in range(len(force_plates[trial])):
                            force_norms = force_plate_norms[i]
                            for t in range(trial_lengths[trial]):
                                force_norms[t] = np.linalg.norm(force_plate_forces[trial][i][t])

                            num_bins = 200
                            hist, bin_edges = np.histogram(force_norms, bins=num_bins)
                            avg_bin_value = trial_lengths[trial] / num_bins
                            hist_max_index = np.argmax(hist)
                            # If the largest bin is in the bottom 25% of the distribution
                            if hist_max_index < num_bins / 4:
                                # Expand out from that bin in both directions until we find a bin that is below the
                                # average bin value.
                                right_bound = hist_max_index
                                for j in range(hist_max_index, num_bins):
                                    if hist[j] < avg_bin_value:
                                        right_bound = j
                                        break
                                # Now we have the boundary of the "big thumb" region. This generally corresponds to the
                                # zero point of the treadmill. If it is exactly at zero, then all is well. But if it is
                                # not, then we've found a cutoff threshold which we should use to zero the GRF data.
                                if right_bound > num_bins / 2:
                                    # We found a right bound, but it's suspiciously far up the distribution. Let's
                                    # ignore this zero.
                                    pass
                                else:
                                    # We found a right bound that is in the bottom half of the distribution. Let's
                                    # use it to zero the GRF data.
                                    zero_threshold = bin_edges[right_bound]
                                    for t in range(trial_lengths[trial]):
                                        if force_norms[t] < zero_threshold:
                                            force_plate_forces[trial][i][t] = np.zeros(3)
                                            force_plate_cops[trial][i][t] = np.zeros(3)
                                            force_plate_moments[trial][i][t] = np.zeros(3)
                                            force_norms[t] = 0.0

                        trial_ground_body_cop_torque_force[trial] = np.zeros_like(trial_ground_body_cop_torque_force[trial])
                        # Next, low-pass filter the GRF data for each non-zero section
                        for i in range(len(force_plates[trial])):
                            force_matrix = np.zeros((3, trial_lengths[trial]))
                            cop_matrix = np.zeros((3, trial_lengths[trial]))
                            moment_matrix = np.zeros((3, trial_lengths[trial]))
                            force_norms = force_plate_norms[i]
                            non_zero_segments: List[Tuple[int,int]] = []
                            last_nonzero = -1
                            for t in range(trial_lengths[trial]):
                                if force_norms[t] > 0.0:
                                    if last_nonzero < 0:
                                        last_nonzero = t
                                else:
                                    if last_nonzero >= 0:
                                        non_zero_segments.append((last_nonzero, t-1))
                                        last_nonzero = -1
                                force_matrix[:, t] = force_plate_forces[trial][i][t]
                                cop_matrix[:, t] = force_plate_cops[trial][i][t]
                                moment_matrix[:, t] = force_plate_moments[trial][i][t]
                            if last_nonzero >= 0:
                                non_zero_segments.append((last_nonzero, trial_lengths[trial]-1))

                            # print start and end indices of non-zero sequences
                            for start, end in non_zero_segments:
                                # print(f"Filtering force plate {i} on non-zero range [{start}, {end}]")
                                if end - start < 10:
                                    # print(" - Skipping non-zero segment because it's too short. Zeroing instead")
                                    for t in range(start, end):
                                        force_plate_forces[trial][i][t] = np.zeros(3)
                                        force_plate_cops[trial][i][t] = np.zeros(3)
                                        force_plate_moments[trial][i][t] = np.zeros(3)
                                        force_norms[t] = 0.0
                                else:
                                    force_matrix[:, start:end] = filtfilt(b, a, force_matrix[:, start:end], padtype='constant')
                                    cop_matrix[:, start:end] = filtfilt(b, a, cop_matrix[:, start:end], padtype='constant')
                                    moment_matrix[:, start:end] = filtfilt(b, a, moment_matrix[:, start:end], padtype='constant')

                                    dist_to_contact_bodies = np.zeros(len(ground_force_bodies))

                                    for t in range(start, end):
                                        force_plate_forces[trial][i][t] = force_matrix[:, t]
                                        force_plate_cops[trial][i][t] = cop_matrix[:, t]
                                        force_plate_moments[trial][i][t] = moment_matrix[:, t]
                                        for j in range(len(ground_force_bodies)):
                                            dist_to_contact_bodies[j] += np.linalg.norm(cop_matrix[:, t] - contact_body_world_positions[j][:, t])

                                    closest_body_index = np.argmin(dist_to_contact_bodies)
                                    # print('Closest body: ', ground_force_bodies[closest_body_index])

                                    for t in range(start, end):
                                        # TODO: it's technically possible for one foot to be split over two force plates
                                        # so really, we should be summing the results from each force plate that assigns
                                        # to a given foot, but that's such a huge PITA that I'm just going to ignore it
                                        # for now
                                        trial_ground_body_cop_torque_force[trial][closest_body_index*9:closest_body_index*9+9, t] = np.hstack((cop_matrix[:, t], moment_matrix[:, t], force_matrix[:, t]))

                    # Update the force plates
                    for i in range(len(force_plates[trial])):
                        force_plates[trial][i].forces = force_plate_forces[trial][i]
                        force_plates[trial][i].centersOfPressure = force_plate_cops[trial][i]
                        force_plates[trial][i].moments = force_plate_moments[trial][i]

                    # Recompute inverse dynamics
                    for t in range(trial_lengths[trial]):
                        skel.setPositions(trial_poses[trial][:, t])
                        skel.setVelocities(trial_vels[trial][:, t])
                        skel.setAccelerations(trial_accs[trial][:, t])

                        for i in range(len(ground_force_bodies)):
                            cop = trial_ground_body_cop_torque_force[trial][i*9:i*9+3, t]
                            moment = trial_ground_body_cop_torque_force[trial][i*9+3:i*9+6, t]
                            force = trial_ground_body_cop_torque_force[trial][i*9+6:i*9+9, t]

                            body = skel.getBodyNode(ground_force_bodies[i])
                            T = body.getWorldTransform()

                            # Translation from the CoP frame to the body frame
                            p_wb = np.copy(T.translation()) - cop
                            # Rotation from the CoP frame (= world frame) to the body frame
                            R_wb = np.copy(T.rotation())
                            # Rotation from the body frame to the CoP frame
                            R_bw = R_wb.T
                            # Translation from the body frame to the CoP frame
                            p_bw = -R_bw @ p_wb

                            # Transform the wrench into the body frame
                            moment_b = R_bw @ moment - np.cross(p_bw, R_bw @ force)
                            force_b = R_bw @ force
                            wrench_b = np.hstack((moment_b, force_b))
                            body.setExtWrench(wrench_b)

                        skel.computeInverseDynamics()
                        tau = skel.getControlForces()
                        trial_taus[trial][:, t] = tau
            if sample_rate is not None:
                print('Re-sampling kinematics + kinetics data at {} Hz...'.format(sample_rate))
                print('Warning! Re-sampling input source data (markers, IMU, EMG) is not yet supported, so those will '
                      'be zeroed out')

                # Handy little utility for resampling a discrete signal
                def resample_discrete(signal, old_rate, new_rate):
                    # Compute the ratio of the old and new rates
                    ratio = old_rate / new_rate

                    # Use numpy's round and int functions to get the indices of the nearest values
                    indices = (np.round(np.arange(0, len(signal), ratio))).astype(int)

                    # Limit indices to the valid range
                    indices = np.clip(indices, 0, len(signal) - 1)

                    # Use advanced indexing to get the corresponding values
                    resampled_signal = np.array(signal)[indices]

                    return resampled_signal.tolist()


                for trial in range(len(trial_lengths)):
                    original_sample_rate = 1.0 / subject.getTrialTimestep(trial)
                    # Create an array representing the time for the original signal
                    trial_duration = trial_lengths[trial] * trial_timesteps[trial]
                    old_times = np.linspace(0, trial_duration, trial_lengths[trial])

                    # Re-sample the kinematics + kinetics data
                    trial_poses[trial] = resample_poly(trial_poses[trial],
                                                        sample_rate,
                                                        original_sample_rate,
                                                        axis=1,
                                                        padtype='line')

                    trial_lengths[trial] = trial_poses[trial].shape[1]

                    # Create an array representing the time for the resampled signal
                    new_times = np.linspace(0, trial_duration, trial_lengths[trial])

                    trial_vels[trial] = resample_poly(trial_vels[trial],
                                                      sample_rate,
                                                      original_sample_rate,
                                                       axis=1,
                                                       padtype='line')
                    trial_accs[trial] = resample_poly(trial_accs[trial],
                                                      sample_rate,
                                                      original_sample_rate,
                                                      axis=1,
                                                      padtype='line')
                    trial_taus[trial] = resample_poly(trial_taus[trial],
                                                      sample_rate,
                                                      original_sample_rate,
                                                      axis=1,
                                                      padtype='line')
                    trial_com_poses[trial] = resample_poly(trial_com_poses[trial],
                                                           sample_rate,
                                                           original_sample_rate,
                                                                              axis=1,
                                                                              padtype='line')
                    trial_com_vels[trial] = resample_poly(trial_com_vels[trial],
                                                          sample_rate,
                                                          original_sample_rate,
                                                           axis=1,
                                                           padtype='line')
                    trial_com_accs[trial] = resample_poly(trial_com_accs[trial],
                                                          sample_rate,
                                                          original_sample_rate,
                                                          axis=1,
                                                          padtype='line')
                    # Update the force plates
                    for i in range(len(force_plates[trial])):
                        force_plate_forces[trial][i] = resample_poly(force_plate_forces[trial][i],
                                                                     sample_rate,
                                                                     original_sample_rate,
                                                                     padtype='line')
                        force_plates[trial][i].forces = force_plate_forces[trial][i]
                        force_plate_cops[trial][i] = resample_poly(force_plate_cops[trial][i],
                                                                     sample_rate,
                                                                     original_sample_rate,
                                                                     padtype='line')
                        force_plates[trial][i].centersOfPressure = force_plate_cops[trial][i]
                        force_plate_moments[trial][i] = resample_poly(force_plate_moments[trial][i],
                                                                        sample_rate,
                                                                        original_sample_rate,
                                                                        padtype='line')
                        force_plates[trial][i].moments = force_plate_moments[trial][i]

                    # Re-sample the GRF data linearly
                    new_trial_ground_body_wrenches = np.zeros((trial_ground_body_wrenches[trial].shape[0], len(new_times)))
                    for row in range(trial_ground_body_wrenches[trial].shape[0]):
                        # Use scipy's interp1d function to create a function that can interpolate the signal
                        interpolator = interp1d(old_times, trial_ground_body_wrenches[trial][row, :], kind='linear')
                        new_trial_ground_body_wrenches[row, :] = interpolator(new_times)
                    trial_ground_body_wrenches[trial] = new_trial_ground_body_wrenches

                    new_trial_ground_body_cop_torque_force = np.zeros((trial_ground_body_cop_torque_force[trial].shape[0], len(new_times)))
                    for row in range(trial_ground_body_cop_torque_force[trial].shape[0]):
                        interpolator = interp1d(old_times, trial_ground_body_cop_torque_force[trial][row, :], kind='linear')
                        new_trial_ground_body_cop_torque_force[row, :] = interpolator(new_times)
                    trial_ground_body_cop_torque_force[trial] = new_trial_ground_body_cop_torque_force

                    # Re-sample the discrete values
                    probably_missing_grf[trial] = resample_discrete(probably_missing_grf[trial],
                                                                    original_sample_rate,
                                                                    sample_rate)
                    missing_grf_reason[trial] = resample_discrete(missing_grf_reason[trial],
                                                                    original_sample_rate,
                                                                    sample_rate)
                    trial_residual_norms[trial] = resample_discrete(trial_residual_norms[trial],
                                                                      original_sample_rate,
                                                                      sample_rate)

                    # Clear out unsupported values
                    custom_value_names = subject.getCustomValues()
                    custom_values[trial] = [np.zeros((0, trial_lengths[trial])) for _ in range(trial_lengths[trial])]
                    marker_observations[trial] = [{} for _ in range(trial_lengths[trial])]
                    acc_observations[trial] = [{} for _ in range(trial_lengths[trial])]
                    gyro_observations[trial] = [{} for _ in range(trial_lengths[trial])]
                    emg_observations[trial] = [{} for _ in range(trial_lengths[trial])]

                    # Set the timestep
                    trial_timesteps[trial] = 1.0 / sample_rate

            # os.path.dirname gets the directory portion from the full path
            directory = os.path.dirname(output_path)
            # Create the directory structure, if it doesn't exist already
            os.makedirs(directory, exist_ok=True)
            # Now write the output back out to the new SubjectOnDisk file
            print('Writing SubjectOnDisk to {}...'.format(output_path))
            nimble.biomechanics.SubjectOnDisk.writeSubject(output_path,
                                                           openSimFilePath=opensim_file_path,
                                                           trialTimesteps=trial_timesteps,
                                                           trialPoses=trial_poses,
                                                           trialVels=trial_vels,
                                                           trialAccs=trial_accs,
                                                           probablyMissingGRF=probably_missing_grf,
                                                           missingGRFReason=missing_grf_reason,
                                                           dofPositionsObserved=dof_positions_observed,
                                                           dofVelocitiesFiniteDifferenced=dof_velocity_finite_differenced,
                                                           dofAccelerationsFiniteDifferenced=dof_acc_finite_differenced,
                                                           trialTaus=trial_taus,
                                                           trialComPoses=trial_com_poses,
                                                           trialComVels=trial_com_vels,
                                                           trialComAccs=trial_com_accs,
                                                           trialResidualNorms=trial_residual_norms,
                                                           groundForceBodies=ground_force_bodies,
                                                           trialGroundBodyWrenches=trial_ground_body_wrenches,
                                                           trialGroundBodyCopTorqueForce=trial_ground_body_cop_torque_force,
                                                           customValueNames=custom_value_names,
                                                           customValues=custom_values,
                                                           markerObservations=marker_observations,
                                                           accObservations=acc_observations,
                                                           gyroObservations=gyro_observations,
                                                           emgObservations=emg_observations,
                                                           forcePlates=force_plates,
                                                           biologicalSex=biological_sex,
                                                           heightM=height_m,
                                                           massKg=mass_kg,
                                                           ageYears=age_years,
                                                           trialNames=trial_names,
                                                           subjectTags=subject_tags,
                                                           trialTags=trial_tags,
                                                           sourceHref=source_href,
                                                           notes=notes)
            print('Done '+str(file_index+1)+'/'+str(len(input_output_pairs)))

        print('Post-processing finished!')

        return True
