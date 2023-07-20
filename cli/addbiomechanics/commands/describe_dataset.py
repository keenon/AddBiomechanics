import scipy.signal
from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
import tempfile
from typing import List, Dict, Tuple
from datetime import timedelta
import re

class DescribeDatasetCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        parser = subparsers.add_parser(
            'describe-dataset', help='This command will read a folder full of SubjectOnDisk binary files, '
                                     'and compute a bunch of aggregrate statistics and summary data so you know what '
                                     'you are looking at, without having to look at each trial individually.')
        parser.add_argument('data_dir', type=str)

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'describe-dataset':
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


        data_dir: str = os.path.abspath(args.data_dir)

        subject_paths: List[str] = []
        for dirpath, dirnames, filenames in os.walk(data_dir):
            for filename in filenames:
                if filename.endswith('.bin'):
                    input_path = os.path.join(dirpath, filename)
                    subject_paths.append(input_path)

        print('Found '+str(len(subject_paths))+' file' + ("s" if len(subject_paths) > 1 else ""))
        all_trial_durations: List[float] = []
        subject_durations: List[float] = []

        contact_phase_total_duration: Dict[str, float] = {
            'F': 0.0, # flight phase
            'L': 0.0, # left leg
            'R': 0.0, # right leg
            'D': 0.0, # double support
        }

        phase_regexes: Dict[str, str] = {
            'walking_left_stance': r'(D|^)(LD)(R|$)',
            'walking_right_stance': r'(D|^)(RD)(L|$)',
            'isolated_left_stance': r'(^)(L)($)',
            'isolated_right_stance': r'(^)(R)($)',
            'isolated_double_support': r'(^)(D)($)',
            'isolated_flight': r'(^)(F)($)',
            'running_left_stance': r'(F|^)(LF)(R|$)',
            'running_right_stance': r'(F|^)(RF)(L|$)'
        }
        phase_durations: Dict[str, List[float]] = { key: [] for key in phase_regexes.keys() }

        for file_index, input_path in enumerate(subject_paths):
            print('Reading SubjectOnDisk '+str(file_index+1)+'/'+str(len(subject_paths))+' at ' + input_path + '...')

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
            force_plates: List[List[nimble.biomechanics.ForcePlate]] = [[nimble.biomechanics.ForcePlate() for i in range(subject.getNumForcePlates(trial))] for trial in range(subject.getNumTrials())]
            biological_sex: str = subject.getBiologicalSex()
            height_m: float = subject.getHeightM()
            mass_kg: float = subject.getMassKg()
            age_years: int = subject.getAgeYears()
            trial_names: List[str] = [subject.getTrialName(trial) for trial in range(subject.getNumTrials())]
            subject_tags: List[str] = subject.getSubjectTags()
            trial_tags: List[List[str]] = [subject.getTrialTags(trial) for trial in range(subject.getNumTrials())]
            source_href: str = subject.getHref()
            notes: str = subject.getNotes()

            for trial in range(len(trial_lengths)):
                contact_phases: List[str] = []
                contact_durations: List[float] = []

                for t in range(trial_lengths[trial]):
                    frame: nimble.biomechanics.Frame = subject.readFrames(trial, t, 1, contactThreshold=20.0)[0]
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

                    marker_observations[trial][t] = dict(frame.markerObservations)
                    acc_observations[trial][t] = dict(frame.accObservations)
                    gyro_observations[trial][t] = dict(frame.gyroObservations)
                    emg_observations[trial][t] = dict(frame.emgSignals)

                    contact_phase = ""
                    if not frame.contact[0] and not frame.contact[1]:
                        # Flight phase
                        contact_phase = "F"
                    elif frame.contact[0] and not frame.contact[1]:
                        # Left leg
                        contact_phase = "L"
                    elif not frame.contact[0] and frame.contact[1]:
                        # Right leg
                        contact_phase = "R"
                    elif frame.contact[0] and frame.contact[1]:
                        # Double support
                        contact_phase = "D"
                    assert(contact_phase != "")
                    if len(contact_phases) == 0 or contact_phases[-1] != contact_phase:
                        contact_phases.append(contact_phase)
                        contact_durations.append(0)
                    contact_durations[-1] += trial_timesteps[trial]

                # Want to pre-filter out any super short phases
                for t in range(len(contact_phases)):
                    if contact_durations[t] < 0.02:
                        contact_phases[t] = None

                cursor = 0
                while cursor < len(contact_phases):
                    if contact_phases[cursor] is None or (cursor > 0 and contact_phases[cursor] == contact_phases[cursor - 1]):
                        if cursor > 0:
                            contact_durations[cursor - 1] += contact_durations[cursor]
                        elif cursor < len(contact_phases) - 1:
                            contact_durations[cursor + 1] += contact_durations[cursor]

                        del contact_phases[cursor]
                        del contact_durations[cursor]
                    else:
                        cursor += 1

                for t in range(len(contact_phases)):
                    contact_phase_total_duration[contact_phases[t]] += contact_durations[t]

                # Complete gait cycle: L to something else and back to L
                    # Running if middle is FRF
                    # Walking if middle is DRD
                # Half gait cycle: L to something else and to R
                    # Running if middle is F
                    # Walking if middle is D

                phase_instances: Dict[str, List[Tuple[int, int]]] = {key: [] for key in phase_regexes.keys()}

                phase_string = ''.join(contact_phases)
                segment_match_counts = [0 for _ in range(len(phase_string))]
                for phase_name in phase_regexes.keys():
                    matches = re.finditer(phase_regexes[phase_name], phase_string)
                    match_count = 0
                    for match in matches:
                        match_count += 1
                        phase_instances[phase_name].append((match.start(2), match.end(2)))
                        for i in range(match.start(2), match.end(2)):
                            segment_match_counts[i] += 1

                for phase_name in phase_instances.keys():
                    for instance in phase_instances[phase_name]:
                        phase_start = instance[0]
                        phase_end = instance[1]
                        phase_duration = 0
                        for t in range(phase_start, phase_end):
                            phase_duration += contact_durations[t]
                        phase_durations[phase_name].append(phase_duration)

                no_match_string = ''.join([str(n) for n in segment_match_counts])
                no_match_matches = re.finditer(r'0+', no_match_string)
                num_no_matches = 0
                for no_match in no_match_matches:
                    print('Trial '+str(trial)+' no match: ('+str(no_match.start())+'-'+str(no_match.end())+')/'+str(len(phase_string))+' = ')
                    print(phase_string[:no_match.start()]+' [[[ '+phase_string[no_match.start():no_match.end()]+' ]]] '+phase_string[no_match.end():])
                    num_no_matches += 1

                if re.match(r'(^)(D)($)', phase_string):
                    print('Input path '+input_path+' '+str(trial)+' ALL DOUBLE SUPPORT')

            trial_durations = [trial_lengths[trial] * trial_timesteps[trial] for trial in range(subject.getNumTrials())]
            all_trial_durations.extend(trial_durations)
            subject_durations.append(sum(trial_durations))

            print('Done '+str(file_index+1)+'/'+str(len(subject_paths)))

        print('Done reading data!')

        print('Total subjects: '+str(len(subject_paths)))
        print('Total trials: '+str(len(all_trial_durations)))
        print('Total dataset duration (HH:MM:SS): '+str(timedelta(seconds=int(sum(all_trial_durations)))))
        print('Contact phases:')
        for key in contact_phase_total_duration.keys():
            print('  '+key+': '+str(timedelta(seconds=int(contact_phase_total_duration[key])))+' ('+str(round(contact_phase_total_duration[key]/sum(all_trial_durations)*100, 1))+'%)')
        print('Phase durations:')
        for key in phase_durations.keys():
            print('  '+key+': '+str(len(phase_durations[key]))+' instances, avg '+ str(timedelta(seconds=sum(phase_durations[key])/max(len(phase_durations[key]), 1)))+', total '+str(timedelta(seconds=int(sum(phase_durations[key]))))+' ('+str(round(sum(phase_durations[key])/sum(all_trial_durations)*100, 1))+'%)')

        return True
