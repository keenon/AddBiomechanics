from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from typing import List, Dict, Tuple
import math

class ViewCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        view_parser = subparsers.add_parser(
            'view', help='View a binary *.bin file from AddBiomechanics')

        view_parser.add_argument(
            'file_path', help='The name of the file to view')
        view_parser.add_argument(
            '--trial', help='The number of the trial to view (default: 0)', default=0, type=int)
        view_parser.add_argument(
            '--geometry',
            help='The path to the Geometry folder to use when loading OpenSim skeletons',
            type=str,
            default=None)
        view_parser.add_argument(
            '--graph-dof',
            help='The name of a DOF to highlight and to graph',
            type=str,
            default=None)
        view_parser.add_argument(
            '--graph-lowpass-hz',
            help='The frequency to lowpass filter the DOF values being plotted',
            type=int,
            default=None)
        view_parser.add_argument(
            '--show-energy',
            help='Add visualizations to show the energy flowing through the body',
            type=bool,
            default=False)
        view_parser.add_argument(
            '--playback-speed',
            help='A number representing the fraction of realtime to play back the data at. Default is 1.0, for '
                 'realtime playback.',
            type=float,
            default=1.0)
        view_parser.add_argument(
            '--save-to-file',
            help='Save the visualization to a file, which can be embedded in a website for use with the Nimble Physics Viewer',
            type=str,
            default=None)
        view_parser.add_argument(
            '--limit-frames',
            help='Only visualize the first N frames of the data, useful for very long trials',
            type=int,
            default=-1)
        view_parser.add_argument(
            '--num-energy-packets',
            help='The number of packets to use when computing energy. Default is 250, which is a good balance between performance and resolution when walking',
            type=int,
            default=250)

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'view':
            return False
        file_path: str = args.file_path
        trial: int = args.trial
        graph_dof: str = args.graph_dof
        graph_lowpass_hz: int = args.graph_lowpass_hz
        playback_speed: float = args.playback_speed
        show_energy: bool = args.show_energy
        save_to_file: str = args.save_to_file
        limit_frames: int = args.limit_frames
        num_packets: int = args.num_energy_packets

        try:
            import nimblephysics as nimble
            from nimblephysics import NimbleGUI
        except ImportError:
            print("The required library 'nimblephysics' is not installed. Please install it and try this command again.")
            return True
        try:
            import numpy as np
        except ImportError:
            print("The required library 'numpy' is not installed. Please install it and try this command again.")
            return True
        try:
            from scipy.signal import butter, filtfilt
        except ImportError:
            print("The required library 'scipy' is not installed. Please install it and try this command again.")
            return True
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("The required library 'matplotlib' is not installed. Please install it and try this command again.")
            return True

        def quantize_vector_fixed_sum(x: np.ndarray, sum: int):
            rounded = np.round(x)
            rounded_sum = np.sum(rounded)
            while rounded_sum != sum:
                if rounded_sum < sum:
                    rounded[np.argmax(x - rounded)] += 1
                else:
                    rounded[np.argmin(x - rounded)] -= 1
                rounded_sum = np.sum(rounded)
            return rounded.astype(dtype=np.int64)

        geometry: str = args.geometry

        if geometry is None:
            # Check if the "./Geometry" folder exists, and if not, download it
            if not os.path.exists('./Geometry'):
                print('Downloading the Geometry folder from https://addbiomechanics.org/resources/Geometry.zip')
                os.system('wget https://addbiomechanics.org/resources/Geometry.zip')
                os.system('unzip ./Geometry.zip')
                os.system('rm ./Geometry.zip')
            geometry = './Geometry'
        print('Using Geometry folder: '+geometry)
        geometry = os.path.abspath(geometry)
        if not geometry.endswith('/'):
            geometry += '/'
        print(' > Converted to absolute path: '+geometry)

        print('Reading SubjectOnDisk at '+file_path+'...')
        subject: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(file_path)
        print('Subject height: '+str(subject.getHeightM())+"m")
        print('Subject mass: '+str(subject.getMassKg())+"kg")
        print('Subject biological sex: '+subject.getBiologicalSex())
        contact_bodies = subject.getContactBodies()
        print('Contact bodies: '+str(contact_bodies))

        num_frames = subject.getTrialLength(trial)
        if limit_frames > -1 and limit_frames < num_frames:
            num_frames = limit_frames
        skel = subject.readSkel(geometry)

        print('DOFs:')
        for i in range(skel.getNumDofs()):
            print(' ['+str(i)+']: '+skel.getDofByIndex(i).getName())

        world = nimble.simulation.World()
        world.addSkeleton(skel)
        world.setGravity([0, -9.81, 0])
        skel.setGravity([0, -9.81, 0])

        if save_to_file is not None:
            gui = nimble.server.GUIRecording()
        else:
            nimble_gui = NimbleGUI(world)
            nimble_gui.serve(8080)
            gui = nimble_gui.nativeAPI()

        if graph_dof is not None:
            dof = skel.getDof(graph_dof)
            if dof is None:
                print('ERROR: DOF to graph "'+graph_dof+'" not found')
                return False
            graph_joint = skel.getJoint(dof.getJointName())
            joint_pos = skel.getJointWorldPositions([graph_joint])
            gui.createSphere('active_joint', [0.05, 0.05, 0.05], joint_pos, [1,0,0,1])
            dof_index = dof.getIndexInSkeleton()

            timesteps = np.zeros(num_frames)
            dof_poses = np.zeros(num_frames)
            dof_vels = np.zeros(num_frames)
            dof_accs = np.zeros(num_frames)
            dof_taus = np.zeros(num_frames)
            dof_power = np.zeros(num_frames)
            dof_work = np.zeros(num_frames)
            for frame in range(num_frames):
                timesteps[frame] = frame * subject.getTrialTimestep(trial)
                loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1)
                p = loaded[0].pos[dof_index]
                v = loaded[0].vel[dof_index]
                a = loaded[0].acc[dof_index]
                t = loaded[0].tau[dof_index]
                dof_poses[frame] = p
                dof_vels[frame] = v
                dof_accs[frame] = a
                dof_taus[frame] = t

            # Filter down to "--graph-lowpass-hz" Hz
            if graph_lowpass_hz is not None:
                fs = 1/subject.getTrialTimestep(trial)
                nyquist = fs / 2
                if graph_lowpass_hz < nyquist:
                    print('Filtering to '+str(graph_lowpass_hz)+' Hz...')
                    b, a = butter(2, graph_lowpass_hz, 'low', fs=fs)
                    dof_poses = filtfilt(b, a, dof_poses)
                    dof_vels = filtfilt(b, a, dof_vels)
                    dof_accs = filtfilt(b, a, dof_accs)
                    dof_taus = filtfilt(b, a, dof_taus)
                else:
                    print('WARNING: Cannot filter to '+str(graph_lowpass_hz)+' Hz because it is greater than the '+
                          'Nyquist frequency of '+str(nyquist)+' Hz. Not filtering.')
            dof_power = dof_vels * dof_taus
            dof_work = np.cumsum(dof_power) * subject.getTrialTimestep(trial)

            max_over_all = np.percentile(np.concatenate((dof_poses, dof_vels, dof_accs, dof_taus, dof_power)), 95)
            min_over_all = np.percentile(np.concatenate((dof_poses, dof_vels, dof_accs, dof_taus, dof_power)), 5)

            gui.createRichPlot('dof_plot', [50, 100], [400, 200], 0, subject.getTrialLength(trial) * subject.getTrialTimestep(trial), min_over_all, max_over_all, 'DOF '+graph_dof, 'Time (s)', 'Values')

            gui.setRichPlotData('dof_plot', 'Pose', 'blue', 'line', timesteps, dof_poses)
            gui.setRichPlotData('dof_plot', 'Vel', 'green', 'line', timesteps, dof_vels)
            gui.setRichPlotData('dof_plot', 'Tau', 'red', 'line', timesteps, dof_taus)
            # gui.setRichPlotData('dof_plot', 'Power', 'purple', 'line', timesteps, dof_power)
            gui.setRichPlotData('dof_plot', 'Net Work', 'purple', 'line', timesteps, dof_work)

            gui.createText('dof_plot_text', 'DOF '+graph_dof+' values', [50, 350], [400, 50])
        else:
            dof = None

        if show_energy:
            body_min_height = np.ones(skel.getNumBodyNodes()) * 1000
            for frame in range(num_frames):
                loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1)
                skel.setPositions(loaded[0].pos)
                for i in range(skel.getNumBodyNodes()):
                    body_min_height[i] = min(body_min_height[i], skel.getBodyNode(i).getCOM()[1])

            print('Estimating treadmill speed...')
            avg_vel = np.zeros(3)
            vel_obs_count = 0
            for frame in range(num_frames):
                loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1)
                skel.setPositions(loaded[0].pos)
                skel.setVelocities(loaded[0].vel)
                skel.setAccelerations(loaded[0].acc)
                for i in range(0, len(contact_bodies)):
                    f = loaded[0].groundContactForce[i*3:(i+1)*3]

                    if np.linalg.norm(f) > 5:
                        body = skel.getBodyNode(contact_bodies[i])
                        avg_vel += body.getLinearVelocity()
                        vel_obs_count += 1
            if vel_obs_count > 0:
                avg_vel /= vel_obs_count
                avg_vel[1] = 0.0
                avg_vel *= -1
            print('  Average velocity: '+str(avg_vel))

            energy_frames: List[nimble.dynamics.EnergyAccountingFrame] = []
            body_total_energy = np.zeros(num_frames)
            conserved_energy = np.zeros(num_frames)
            print('Precomputing energy in '+str(num_frames)+' frames...')
            for frame in range(num_frames):
                if frame % 100 == 0:
                    print('  '+str(frame)+'/'+str(num_frames))
                loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1)
                skel.setPositions(loaded[0].pos)
                skel.setVelocities(loaded[0].vel)
                skel.setAccelerations(loaded[0].acc)
                contact_body_pointers = []
                cops = []
                forces = []
                moments = []
                skel.clearExternalForces()
                for i in range(0, len(contact_bodies)):
                    start_cop = loaded[0].groundContactCenterOfPressure[i*3:(i+1)*3]
                    f = loaded[0].groundContactForce[i*3:(i+1)*3]
                    tau = loaded[0].groundContactTorque[i*3:(i+1)*3]

                    local_wrench = np.zeros(6)
                    local_wrench[0:3] = tau
                    local_wrench[3:6] = f
                    global_wrench = nimble.math.dAdInvT(np.eye(3), start_cop, local_wrench)
                    body = skel.getBodyNode(contact_bodies[i])
                    wrench_local = nimble.math.dAdT(body.getWorldTransform().rotation(), body.getWorldTransform().translation(), global_wrench)
                    body.setExtWrench(wrench_local)

                    contact_body_pointers.append(body)
                    cops.append(start_cop)
                    forces.append(f)
                    moments.append(tau)
                energy = skel.getEnergyAccounting(0.0, avg_vel, contact_body_pointers, cops, forces, moments)
                # Reset potential energies to be relative to the lowest point these bodies reach over the trial
                potential_energy = np.copy(energy.bodyPotentialEnergy)
                for i in range(0, skel.getNumBodyNodes()):
                    body = skel.getBodyNode(i)
                    potential_energy[i] = body.getMass() * 9.81 * (body.getCOM()[1] - body_min_height[i])
                energy.bodyPotentialEnergy = potential_energy
                energy_frames.append(energy)
                body_total_energy[frame] = np.sum(energy.bodyKineticEnergy) + np.sum(energy.bodyPotentialEnergy)
            # Compute the conserved energy reserve, so total energy every frame is constant
            peak_body_energy = np.max(body_total_energy)
            for frame in range(num_frames):
                conserved_energy[frame] = peak_body_energy - body_total_energy[frame]

            peak_energy_density = 0.0
            for frame in range(num_frames):
                for i in range(skel.getNumBodyNodes()):
                    body_energy_density = (energy_frames[frame].bodyKineticEnergy[i] + energy_frames[frame].bodyPotentialEnergy[i]) / skel.getBodyNode(i).getMass()
                    peak_energy_density = max(peak_energy_density, body_energy_density)

            if num_packets > 0:
                print('Correcting discrete-time numerical issues in energy in '+str(num_frames)+' frames...')
                # Now we need to go through and project the rates of power on each frame to perfectly reflect changes in
                # energy on the subsequent frame. This is necessary, because our time integration is _highly_ imperfect
                # here, especially because we may be low-pass filtering the acc / vels separately from positions.
                for frame in range(num_frames - 1):
                    if frame % 100 == 0:
                        print('  '+str(frame)+'/'+str(num_frames))

                    this_energy = energy_frames[frame]
                    next_energy = energy_frames[frame + 1]

                    # Compute the power rate from gravity
                    body_potential_energy_change: np.ndarray = next_energy.bodyPotentialEnergy - this_energy.bodyPotentialEnergy
                    body_gravity_power_rate: np.ndarray = -body_potential_energy_change / subject.getTrialTimestep(trial)
                    this_energy.bodyGravityPower = body_gravity_power_rate

                    # Compute the power rate from kinetic energy change
                    body_kinetic_energy_change = next_energy.bodyKineticEnergy - this_energy.bodyKineticEnergy
                    body_kinetic_power_rate: np.ndarray = body_kinetic_energy_change / subject.getTrialTimestep(trial)

                    # this_energy.bodyKineticEnergyDeriv == this_energy.bodyExternalForcePower + this_energy.bodyChildJointPowerSum + this_energy.bodyParentJointPower + this_energy.bodyGravityPower
                    body_kinetic_power_without_gravity: np.ndarray = body_kinetic_power_rate - body_gravity_power_rate
                    # body_kinetic_power_without_gravity == this_energy.bodyExternalForcePower + this_energy.bodyChildJointPowerSum + this_energy.bodyParentJointPower

                    # Now we want to find the least-squares closest set of bodyExternalForcePower and each joint power such
                    # that the sums add up to body_kinetic_power_without_gravity
                    new_body_external_force_power = np.copy(this_energy.bodyExternalForcePower)
                    new_body_child_joint_power_sum = np.copy(this_energy.bodyChildJointPowerSum)
                    new_body_parent_joint_power = np.copy(this_energy.bodyParentJointPower)
                    for i in range(skel.getNumBodyNodes()):
                        correction = body_kinetic_power_without_gravity[i] - (this_energy.bodyExternalForcePower[i] + this_energy.bodyChildJointPowerSum[i] + this_energy.bodyParentJointPower[i])
                        num_non_zero_power_sources = 0
                        num_child_power_sources = 0
                        if this_energy.bodyExternalForcePower[i] != 0:
                            num_non_zero_power_sources += 1
                        if this_energy.bodyChildJointPowerSum[i] != 0:
                            # Find all the child joints
                            for joint in this_energy.joints:
                                if joint.parentBody == skel.getBodyNode(i).getName():
                                    num_non_zero_power_sources += 1
                                    num_child_power_sources += 1
                        if this_energy.bodyParentJointPower[i] != 0:
                            num_non_zero_power_sources += 1

                        per_source_correction = correction / num_non_zero_power_sources
                        if this_energy.bodyExternalForcePower[i] != 0:
                            new_body_external_force_power[i] += per_source_correction
                        for joint in this_energy.joints:
                            if joint.parentBody == skel.getBodyNode(i).getName():
                                joint.powerToParent += per_source_correction
                                new_body_child_joint_power_sum[i] += per_source_correction
                            if joint.childBody == skel.getBodyNode(i).getName():
                                joint.powerToChild += per_source_correction
                                new_body_parent_joint_power[i] += per_source_correction

                        # Just to double-check things are being updated
                        recovered_parent_power = 0.0
                        recovered_child_power = 0.0
                        for joint in this_energy.joints:
                            if joint.parentBody == skel.getBodyNode(i).getName():
                                recovered_child_power += joint.powerToParent
                            if joint.childBody == skel.getBodyNode(i).getName():
                                recovered_parent_power += joint.powerToChild
                        assert(abs(recovered_parent_power - new_body_parent_joint_power[i]) < 1.0e-6)
                        assert(abs(recovered_child_power - new_body_child_joint_power_sum[i]) < 1.0e-6)

                    remaining_error = body_kinetic_power_without_gravity - (new_body_external_force_power + new_body_child_joint_power_sum + new_body_parent_joint_power)
                    assert(np.linalg.norm(remaining_error) < 1.0e-6)

                    this_energy.bodyExternalForcePower = new_body_external_force_power
                    this_energy.bodyParentJointPower = new_body_parent_joint_power
                    this_energy.bodyChildJointPowerSum = new_body_child_joint_power_sum

                    # Double check that the kinetic power adds up
                    body_power_total = this_energy.bodyParentJointPower + this_energy.bodyChildJointPowerSum + this_energy.bodyGravityPower + this_energy.bodyExternalForcePower
                    expected_kinetic_energy_change = body_power_total * subject.getTrialTimestep(trial)
                    actual_kinetic_energy_change = next_energy.bodyKineticEnergy - this_energy.bodyKineticEnergy
                    assert(np.linalg.norm(expected_kinetic_energy_change - actual_kinetic_energy_change) < 1.0e-6)

            # Now we want to work out the energy storage in tendons at each joint
            best_case_tendon_capacity = np.zeros(skel.getNumJoints())
            for joint in range(skel.getNumJoints()):
                stored_energy = np.zeros(num_frames)
                for frame in range(num_frames - 1):
                    this_energy = energy_frames[frame]
                    stored_energy[frame + 1] = stored_energy[frame] + (this_energy.joints[joint].powerToParent + this_energy.joints[joint].powerToChild) * subject.getTrialTimestep(trial)

                # Now we look for the largest amount of positive work done by the joint over any time period, and cap
                # the tendons at that amount of storage. For joints that do positive work, it'll mean the tendons are
                # effectively uncapped, and for joints that do negative work it'll be a cap to ensure some energy is
                # still vented.

                # To limit compute time, only scan the first 1000 frames
                scan_frames = min(1000, num_frames)

                best = 0
                for start_frame in range(scan_frames - 1):
                    for end_frame in range(start_frame + 1, scan_frames):
                        if stored_energy[end_frame] - stored_energy[start_frame] > best:
                            best = stored_energy[end_frame] - stored_energy[start_frame]
                best_case_tendon_capacity[joint] = best

            energy_stored_in_tendons = np.zeros((skel.getNumJoints(), num_frames))
            power_not_retrieved_from_tendons = np.zeros((skel.getNumJoints(), num_frames))
            for frame in range(num_frames - 1):
                this_energy = energy_frames[frame]
                for joint in range(skel.getNumJoints()):
                    power = this_energy.joints[joint].powerToParent + this_energy.joints[joint].powerToChild
                    delta_energy = power * subject.getTrialTimestep(trial)

                    if delta_energy < 0:
                        energy_to_tendon = -delta_energy
                        if energy_to_tendon > best_case_tendon_capacity[joint] - energy_stored_in_tendons[joint, frame]:
                            energy_to_tendon = best_case_tendon_capacity[joint] - energy_stored_in_tendons[joint, frame]
                        energy_stored_in_tendons[joint, frame + 1] = energy_stored_in_tendons[joint, frame] + energy_to_tendon
                    if delta_energy > 0:
                        energy_from_tendon = delta_energy
                        if energy_from_tendon > energy_stored_in_tendons[joint, frame]:
                            energy_from_tendon = energy_stored_in_tendons[joint, frame]
                        energy_stored_in_tendons[joint, frame + 1] = energy_stored_in_tendons[joint, frame] - energy_from_tendon
                        if energy_from_tendon == 0:
                            power_not_retrieved_from_tendons[joint, frame] = power
                        else:
                            power_from_tendon = energy_from_tendon / subject.getTrialTimestep(trial)
                            power_not_retrieved_from_tendons[joint, frame] = power - power_from_tendon
                    assert(energy_stored_in_tendons[joint, frame + 1] <= best_case_tendon_capacity[joint])
                    assert(energy_stored_in_tendons[joint, frame + 1] >= 0)

            peak_joint_net_power = 0.0
            joint_net_powers = []
            peak_tendon_storage = np.max(energy_stored_in_tendons)
            for frame in range(num_frames):
                for joint in energy_frames[frame].joints:
                    joint_net_powers.append(abs(joint.powerToParent - joint.powerToChild))
            joint_net_powers.sort()
            # Get the 90th percentile of the joint net powers
            peak_joint_net_power = joint_net_powers[int(len(joint_net_powers) * 0.9)]

            if num_packets > 0:
                print('Quantizing energy in '+str(num_frames)+' frames...')

                particle_ramp_duration = 1000 # Effectively, just don't wait in the bodies ever, just go slowly from body to body
                negative_work_particle_lifetime = int(0.1 / subject.getTrialTimestep(trial))
                negative_work_particle_dist_traveled = (0.1 / negative_work_particle_lifetime)

                # We want to scale the energy so that the total sum is always equal to num_packets
                energy_scale = num_packets / peak_body_energy
                quantized_body_energies: List[np.ndarray] = []
                for frame in range(num_frames):
                    this_energy = energy_frames[frame]

                    continuous_body_energy = np.zeros(skel.getNumBodyNodes() + 1)
                    continuous_body_energy[0] = conserved_energy[frame]
                    continuous_body_energy[1:] += this_energy.bodyKineticEnergy + this_energy.bodyPotentialEnergy

                    quantized_body_energy = quantize_vector_fixed_sum(continuous_body_energy * energy_scale, num_packets)
                    quantized_body_energies.append(quantized_body_energy)

                # Store the quantized power flows
                quantized_external_power = np.zeros((skel.getNumBodyNodes(), num_frames), dtype=np.int64)
                quantized_joint_parent_power = np.zeros((skel.getNumJoints(), num_frames), dtype=np.int64)
                quantized_joint_child_power = np.zeros((skel.getNumJoints(), num_frames), dtype=np.int64)

                # Now we need to map this to a discrete set of energy flows
                for i in range(skel.getNumBodyNodes()):
                    body = skel.getBodyNode(i)
                    num_child_power_sources = body.getNumChildJoints()

                    # parent, external, and children
                    continuous_power_integrals = np.zeros(2 + num_child_power_sources)
                    quantized_power_integrals = np.zeros(2 + num_child_power_sources)

                    for frame in range(num_frames - 1):
                        this_energy = energy_frames[frame]
                        next_energy = energy_frames[frame + 1]

                        # Double check that the kinetic power adds up
                        body_power_total = this_energy.bodyParentJointPower + this_energy.bodyChildJointPowerSum + this_energy.bodyGravityPower + this_energy.bodyExternalForcePower
                        expected_kinetic_energy_change = body_power_total * subject.getTrialTimestep(trial)
                        actual_kinetic_energy_change = next_energy.bodyKineticEnergy - this_energy.bodyKineticEnergy
                        assert (np.linalg.norm(expected_kinetic_energy_change - actual_kinetic_energy_change) < 1.0e-6)
                        # </test>

                        this_body_energy = quantized_body_energies[frame][i+1]
                        next_body_energy = quantized_body_energies[frame + 1][i+1]
                        quantized_energy_diff = next_body_energy - this_body_energy

                        body_power = np.zeros(3 + num_child_power_sources)
                        # Power from gravity
                        body_power[0] = this_energy.bodyGravityPower[i]
                        # Power from the parent joint
                        body_power[1] = this_energy.bodyParentJointPower[i]
                        # Power from external
                        body_power[2] = this_energy.bodyExternalForcePower[i]
                        # Power from children
                        child_cursor = 3
                        child_power_sum = 0.0
                        for joint in this_energy.joints:
                            if joint.parentBody == body.getName():
                                body_power[child_cursor] = joint.powerToParent
                                child_power_sum += joint.powerToParent
                                child_cursor += 1
                        assert(child_cursor - 3 == num_child_power_sources)
                        assert(abs(child_power_sum - this_energy.bodyChildJointPowerSum[i]) < 1e-6)

                        # Idiot check that the powers add up
                        expected_potential_delta = -body_power[0] * subject.getTrialTimestep(trial)
                        actual_potential_delta = next_energy.bodyPotentialEnergy[i] - this_energy.bodyPotentialEnergy[i]
                        assert(abs(expected_potential_delta - actual_potential_delta) < 1e-8)

                        expected_kinetic_delta = np.sum(body_power) * subject.getTrialTimestep(trial)
                        actual_kinetic_delta = next_energy.bodyKineticEnergy[i] - this_energy.bodyKineticEnergy[i]
                        assert(abs(expected_kinetic_delta - actual_kinetic_delta) < 1e-8)

                        expected_energy_delta = np.sum(body_power[1:]) * subject.getTrialTimestep(trial)
                        actual_energy_delta = (next_energy.bodyKineticEnergy[i] + next_energy.bodyPotentialEnergy[i]) - (this_energy.bodyKineticEnergy[i] + this_energy.bodyPotentialEnergy[i])
                        assert(abs(expected_energy_delta - actual_energy_delta) < 1e-8)

                        continuous_power_integrals += body_power[1:] * subject.getTrialTimestep(trial) * energy_scale

                        delta_power = continuous_power_integrals - quantized_power_integrals
                        quantized_power = quantize_vector_fixed_sum(delta_power, quantized_energy_diff)
                        quantized_power_integrals += quantized_power
                        # Reminder, order is: gravity, parent joint, external, children
                        quantized_joint_child_power[body.getParentJoint().getJointIndexInSkeleton(), frame] = quantized_power[0]
                        quantized_external_power[i, frame] = quantized_power[1]
                        for j in range(body.getNumChildJoints()):
                            quantized_joint_parent_power[body.getChildJoint(j).getJointIndexInSkeleton(), frame] = quantized_power[2 + j]

                # Now we just want to double check that all the sums still work out
                for frame in range(num_frames - 1):
                    this_energy = quantized_body_energies[frame]
                    next_energy = quantized_body_energies[frame + 1]
                    energy_diff = next_energy - this_energy
                    assert(np.sum(energy_diff) == 0)
                    expected_energy_diff = np.zeros(skel.getNumBodyNodes() + 1)
                    for i in range(skel.getNumBodyNodes()):
                        expected_energy_diff[i + 1] += quantized_external_power[i, frame]
                        expected_energy_diff[i + 1] += quantized_joint_child_power[skel.getBodyNode(i).getParentJoint().getJointIndexInSkeleton(), frame]
                        for c in range(skel.getBodyNode(i).getNumChildJoints()):
                            expected_energy_diff[i + 1] += quantized_joint_parent_power[skel.getBodyNode(i).getChildJoint(c).getJointIndexInSkeleton(), frame]
                        # Always equal and opposite
                        expected_energy_diff[0] -= expected_energy_diff[i + 1]
                    assert(np.all(expected_energy_diff == energy_diff))

            num_negative_work_particles = 0
            fs = 1 / subject.getTrialTimestep(trial)
            nyquist = fs / 2
            particle_lowpass_hz = 50
            if particle_lowpass_hz < nyquist:
                b, a = butter(2, particle_lowpass_hz, 'low', fs=fs)

            if num_packets > 0:
                # Now we want to map to particle motions in a (from, to, through_joint) format
                joint_quantized_stored_energy = np.zeros((num_frames, skel.getNumJoints()), dtype=np.int64)
                particle_transfers: List[List[Tuple[int, int, int, bool]]] = []
                for frame in range(num_frames - 1):
                    frame_transfers: List[Tuple[int, int, int, bool]] = []
                    this_energy = quantized_body_energies[frame]
                    next_energy = quantized_body_energies[frame + 1]
                    energy_diff = next_energy - this_energy
                    assert(np.sum(energy_diff) == 0)

                    for i in range(skel.getNumBodyNodes()):
                        if quantized_external_power[i, frame] < 0:
                            # External power always transfers to the reserve, and not through a joint
                            for _ in range(abs(quantized_external_power[i, frame])):
                                frame_transfers.append((i + 1, 0, -1, False))
                        elif quantized_external_power[i, frame] > 0:
                            # External power always transfers from the reserve, and not through a joint
                            for _ in range(abs(quantized_external_power[i, frame])):
                                frame_transfers.append((0, i + 1, -1, False))
                    for j in range(skel.getNumJoints()):
                        from_reserve_to_parent = quantized_joint_parent_power[j, frame]
                        from_reserve_to_child = quantized_joint_child_power[j, frame]
                        parent = 0 if skel.getJoint(j).getParentBodyNode() is None else skel.getJoint(j).getParentBodyNode().getIndexInSkeleton()
                        child = skel.getJoint(j).getChildBodyNode().getIndexInSkeleton()

                        # We want to transfer power from the parent to the child, if possible, and avoid the reserve
                        if from_reserve_to_parent < 0 and from_reserve_to_child > 0:
                            from_parent_to_child = min(abs(from_reserve_to_parent), from_reserve_to_child)
                            from_reserve_to_parent += from_parent_to_child
                            from_reserve_to_child -= from_parent_to_child
                            for _ in range(from_parent_to_child):
                                frame_transfers.append((parent + 1, child + 1, j, False))
                        elif from_reserve_to_parent > 0 and from_reserve_to_child < 0:
                            from_child_to_parent = min(abs(from_reserve_to_child), from_reserve_to_parent)
                            from_reserve_to_parent -= from_child_to_parent
                            from_reserve_to_child += from_child_to_parent
                            for _ in range(from_child_to_parent):
                                frame_transfers.append((child + 1, parent + 1, j, False))

                        # All remaining transfers are from the power reserve
                        if from_reserve_to_parent < 0:
                            for _ in range(abs(from_reserve_to_parent)):
                                through_tendon = False
                                if joint_quantized_stored_energy[frame, j] > 0:
                                    joint_quantized_stored_energy[frame, j] -= 1
                                    through_tendon = True
                                frame_transfers.append((parent + 1, 0, j, through_tendon))
                        elif from_reserve_to_parent > 0:
                            for _ in range(abs(from_reserve_to_parent)):
                                through_tendon = False
                                if joint_quantized_stored_energy[frame, j] < best_case_tendon_capacity[j] * energy_scale:
                                    joint_quantized_stored_energy[frame, j] += 1
                                    through_tendon = True
                                frame_transfers.append((0, parent + 1, j, through_tendon))
                        if from_reserve_to_child < 0:
                            for _ in range(abs(from_reserve_to_child)):
                                through_tendon = False
                                if joint_quantized_stored_energy[frame, j] > 0:
                                    joint_quantized_stored_energy[frame, j] -= 1
                                    through_tendon = True
                                frame_transfers.append((child + 1, 0, j, through_tendon))
                        elif from_reserve_to_child > 0:
                            for _ in range(abs(from_reserve_to_child)):
                                through_tendon = False
                                if joint_quantized_stored_energy[frame, j] < best_case_tendon_capacity[j] * energy_scale:
                                    joint_quantized_stored_energy[frame, j] += 1
                                    through_tendon = True
                                frame_transfers.append((0, child + 1, j, through_tendon))
                    joint_quantized_stored_energy[frame + 1, :] = joint_quantized_stored_energy[frame, :]

                    particle_transfers.append(frame_transfers)

                    # Sanity check the particle transfers
                    energy = np.copy(this_energy)
                    for source, dest, joint, through_tendon in frame_transfers:
                        energy[source] -= 1
                        energy[dest] += 1
                    if not np.all(energy == next_energy):
                        print('ERROR: Energy transfer quantization failed on frame '+str(frame))
                        print('  '+str(frame_transfers))
                        print('  Start ' +str(this_energy))
                        print('  Got ' +str(energy))
                        print('  Expected ' + str(next_energy))
                    assert(np.all(energy == next_energy))

                # Map particles to flows through the graph

                particle_bodies = []
                particle_source_joints = []
                particle_transfer_time = []
                particle_through_tendon = []
                body_particle_stacks = [[] for _ in range(skel.getNumBodyNodes() + 1)]
                # Initialize the traces by setting up particles on the first frame of the motion
                # These are the particles in the "conservation sink"
                for _ in range(quantized_body_energies[0][0]):
                    body_particle_stacks[0].append(len(particle_bodies))
                    particle_bodies.append([0])
                    particle_source_joints.append([-1])
                    particle_transfer_time.append([0])
                    particle_through_tendon.append([False])
                # These are the particles in the bodies
                for i in range(skel.getNumBodyNodes()):
                    for _ in range(quantized_body_energies[0][i+1]):
                        body_particle_stacks[i+1].append(len(particle_bodies))
                        particle_bodies.append([i+1])
                        particle_source_joints.append([-1])
                        particle_transfer_time.append([0])
                        particle_through_tendon.append([False])

                def graph_search_joint(j: int, already_visited_bodies: List[int]) -> List[int]:
                    joints: List[int] = [j]
                    joint = skel.getJoint(j)

                    visit_bodies: List[int] = []
                    if joint.getParentBodyNode() is not None and joint.getParentBodyNode().getIndexInSkeleton() not in already_visited_bodies:
                        visit_bodies.append(joint.getParentBodyNode().getIndexInSkeleton())
                    if joint.getChildBodyNode().getIndexInSkeleton() not in already_visited_bodies:
                        visit_bodies.append(joint.getChildBodyNode().getIndexInSkeleton())

                    for body_index in visit_bodies:
                        body = skel.getBodyNode(body_index)
                        if body.getParentJoint() is not None:
                            joints += graph_search_joint(body.getParentJoint().getJointIndexInSkeleton(), already_visited_bodies + [body_index])
                        for c in range(body.getNumChildJoints()):
                            child_joint = body.getChildJoint(c)
                            if child_joint != joint:
                                joints += graph_search_joint(child_joint.getJointIndexInSkeleton(), already_visited_bodies + [body_index])

                    return joints

                body_joint_families = [[0 for j in range(skel.getNumJoints() + 1)] for i in range(skel.getNumBodyNodes()+1)]
                for i in range(skel.getNumBodyNodes()):
                    body: nimble.dynamics.BodyNode = skel.getBodyNode(i)
                    parent_joint = body.getParentJoint()

                    body_joint_families[i+1][0] = 0

                    parent_joint_group = graph_search_joint(parent_joint.getJointIndexInSkeleton(), [i])
                    for j in parent_joint_group:
                        body_joint_families[i+1][j+1] = 1

                    for c in range(body.getNumChildJoints()):
                        child_joint = body.getChildJoint(c)
                        joints = graph_search_joint(child_joint.getJointIndexInSkeleton(), [i])
                        for j in joints:
                            body_joint_families[i+1][j+1] = c + 2

                # Now we want to go through and assign particles to the flows
                for frame in range(num_frames - 1):
                    # Verify that the stack sizes reflect the energy we expect
                    for i in range(len(quantized_body_energies[frame])):
                        assert (len(body_particle_stacks[i]) == quantized_body_energies[frame][i])
                        # On frame 0, we expect to be initialized with our starting configuration
                        assert (len(particle_bodies[i]) == frame + 1)

                    remaining_transfers = particle_transfers[frame]

                    next_frame_body_particle_stacks = [[] for _ in range(skel.getNumBodyNodes() + 1)]

                    while len(remaining_transfers) > 0:
                        transfer_options = []
                        for i, (source, dest, joint, through_tendon) in enumerate(remaining_transfers):
                            for j in range(len(body_particle_stacks[source])):
                                transfer_options.append({
                                    'source': source,
                                    'dest': dest,
                                    'joint': joint,
                                    'transfer_index': i,
                                    'stack_index': j,
                                    'through_tendon': through_tendon,
                                    'particle_index': body_particle_stacks[source][j],
                                    'particle_age': frame - particle_transfer_time[body_particle_stacks[source][j]][-1],
                                    'particle_source_joint': particle_source_joints[body_particle_stacks[source][j]][-1]
                                })

                        if len(transfer_options) > 0:
                            # We'd like to send the spatially closest particle to the new body. That means, if you came in
                            # through this joint recently, we'd like to transfer you out through this joint
                            same_joint_transfer_options = [x for x in transfer_options if body_joint_families[x['source']][x['particle_source_joint']+1] == body_joint_families[x['source']][x['joint']+1]]
                            if len(same_joint_transfer_options) > 0:
                                same_joint_transfer_options.sort(key=lambda x: x['particle_age'])
                                transfer = same_joint_transfer_options[0]
                            else:
                                # Otherwise, we'd like to take the oldest particle on this body from another joint
                                transfer_options.sort(key=lambda x: x['particle_age'], reverse=True)
                                transfer = transfer_options[0]

                            particle_index = body_particle_stacks[transfer['source']].pop(transfer['stack_index'])
                            assert(particle_index == transfer['particle_index'])
                            next_frame_body_particle_stacks[transfer['dest']].append(particle_index)
                            particle_bodies[particle_index].append(transfer['dest'])
                            particle_source_joints[particle_index].append(transfer['joint'])
                            particle_transfer_time[particle_index].append(frame)
                            particle_through_tendon[particle_index].append(transfer['through_tendon'])
                            del remaining_transfers[transfer['transfer_index']]
                        else:
                            # If we make it here, it's because we had no good transfer options based on the previous frame,
                            # so we need to transfer particles that we already transferred on this frame (a "double hop")
                            assert(len(transfer_options) == 0)
                            found_transfer = False
                            for i, (source, dest, joint, through_tendon) in enumerate(remaining_transfers):
                                if len(next_frame_body_particle_stacks[source]) > 0:
                                    particle_index = next_frame_body_particle_stacks[source].pop(0)
                                    next_frame_body_particle_stacks[dest].append(particle_index)
                                    particle_bodies[particle_index][-1] = dest
                                    # We don't actually want to overwrite the joint, since this energy is coming from the
                                    # first joint, and has jumped multiple locked joints in a single timestep
                                    # particle_source_joints[particle_index][-1] = joint
                                    del remaining_transfers[i]
                                    found_transfer = True
                                    break

                            if not found_transfer:
                                print('We failed to find a valid transfer on frame '+str(frame)+'!')
                                print(remaining_transfers)
                                print(quantized_body_energies[frame])
                                print([len(x) for x in body_particle_stacks])
                                print([len(x) for x in next_frame_body_particle_stacks])
                                print(quantized_body_energies[frame+1])
                                assert(False)

                    # Fill in any particle traces that didn't move
                    for i in range(len(particle_bodies)):
                        if len(particle_bodies[i]) < frame + 2:
                            next_frame_body_particle_stacks[particle_bodies[i][-1]].append(i)
                            particle_bodies[i].append(particle_bodies[i][-1])
                            particle_transfer_time[i].append(particle_transfer_time[i][-1])
                            particle_source_joints[i].append(particle_source_joints[i][-1])
                            particle_through_tendon[i].append(particle_through_tendon[i][-1])

                    body_particle_stacks = next_frame_body_particle_stacks

                # Now that particles are assigned to bodies and joints over time, it's time to render that as a trajectory
                # First collect all the body and joint positions
                body_com_positions = np.zeros((skel.getNumBodyNodes() * 3, num_frames))
                joint_positions = np.zeros((skel.getNumJoints() * 3, num_frames))
                for frame in range(num_frames):
                    loaded = subject.readFrames(trial, frame, 1)
                    skel.setPositions(loaded[0].pos)
                    for b in range(skel.getNumBodyNodes()):
                        body_com_positions[b*3:b*3+3, frame] = skel.getBodyNode(b).getCOM()
                    joint_positions[:, frame] = skel.getJointWorldPositions([skel.getJoint(j) for j in range(skel.getNumJoints())])

                particle_trajectories = np.zeros((len(particle_bodies) * 3, num_frames))
                particle_age = np.zeros((len(particle_bodies), num_frames))
                particle_importance = np.zeros((len(particle_bodies), num_frames))
                particle_live = np.zeros((len(particle_bodies), num_frames), dtype=np.int64)

                negative_work_particle_emissions: List[Tuple[int, np.ndarray]] = []

                for p in range(len(particle_bodies)):
                    start_joint = -1
                    start_time = 0
                    current_body: int = particle_bodies[p][0]
                    # List of (start_joint, start_time, body, end_joint, end_time)
                    sections: List[Tuple[int, int, int, int, int]] = []

                    for frame in range(1, num_frames):
                        body: int = particle_bodies[p][frame]
                        # This is the end/beginning of a section
                        if body != current_body:
                            duration = frame - start_time
                            if current_body != 0 and body != 0 and duration < 5:
                                # If it's a short hop, then we want to actually merge with the previous section, keeping
                                # the same source joint and start time, and jumping directly to this body
                                current_body = body
                            else:
                                current_joint = particle_source_joints[p][frame]
                                sections.append((start_joint, start_time, current_body, current_joint, frame))
                                start_joint = current_joint
                                current_body = body
                                start_time = frame
                    # Add the last section
                    sections.append((start_joint, start_time, current_body, -1, num_frames))

                    # List of (start_time, end_time) for liveness
                    live_ranges: List[Tuple[int, int]] = []
                    from_tendons: List[bool] = []
                    to_tendons: List[bool] = []
                    start_live = -1
                    end_live = -1
                    last_live = False

                    # Now run through the sections and compute the trajectory
                    for start_joint, start_time, body_index, end_joint, end_time in sections:
                        duration = end_time - start_time
                        live = duration > 3 and body_index != 0
                        if live != last_live:
                            if live:
                                start_live = start_time
                                end_live = end_time
                            else:
                                live_ranges.append((start_live, end_live))
                                from_tendons.append(particle_through_tendon[p][start_time])
                                to_tendons.append(particle_through_tendon[p][end_time - 1])
                        last_live = live

                        if not live:
                            continue
                        if live:
                            end_live = end_time

                        ramp_duration = int(math.floor(duration * 0.5))
                        if ramp_duration > particle_ramp_duration:
                            ramp_duration = particle_ramp_duration
                        weights = np.zeros((3, duration))
                        for i in range(duration):
                            if i < ramp_duration and start_joint != -1:
                                weights[0, i] = (ramp_duration - i) / ramp_duration
                            if i >= duration - ramp_duration and end_joint != -1:
                                weights[2, i] = (i - (duration - ramp_duration)) / ramp_duration
                            weights[1, i] = 1.0 - weights[0, i] - weights[2, i]

                        start_cop = np.zeros(3)
                        if start_joint == -1 and start_time > 0:
                            loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, start_time, 1)
                            best_force_mag = 0.0
                            for i in range(0, len(contact_bodies)):
                                force_mag = np.linalg.norm(loaded[0].groundContactForce[i*3:(i+1)*3])
                                if force_mag > best_force_mag:
                                    start_cop = loaded[0].groundContactCenterOfPressure[i * 3:(i + 1) * 3]
                                    best_force_mag = force_mag

                        end_cop = np.zeros(3)
                        if end_joint == -1 and end_time < num_frames:
                            loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, end_time, 1)
                            best_force_mag = 0.0
                            for i in range(0, len(contact_bodies)):
                                force_mag = np.linalg.norm(loaded[0].groundContactForce[i*3:(i+1)*3])
                                if force_mag > best_force_mag:
                                    end_cop = loaded[0].groundContactCenterOfPressure[i * 3:(i + 1) * 3]
                                    best_force_mag = force_mag

                        # Now we want to compute the trajectory of the particle
                        random_body_offset = np.random.randn(3) * 0.015

                        for i in range(duration):
                            if start_joint != -1:
                                particle_trajectories[p*3:p*3+3, start_time + i] += weights[0, i] * joint_positions[start_joint*3:start_joint*3+3, start_time + i]
                            elif start_time > 0:
                                particle_trajectories[p * 3:p * 3 + 3, start_time + i] += weights[0, i] * start_cop

                            if body_index != 0:
                                particle_trajectories[p * 3:p * 3 + 3, start_time + i] += weights[1, i] * body_com_positions[
                                    ((body_index - 1) * 3):(body_index * 3), start_time + i] + random_body_offset

                            if end_joint != -1:
                                particle_trajectories[p * 3:p * 3 + 3, start_time + i] += weights[2, i] * joint_positions[
                                                                                                          end_joint * 3:end_joint * 3 + 3,
                                                                                                          start_time + i]
                            elif end_time < num_frames:
                                particle_trajectories[p * 3:p * 3 + 3, start_time + i] += weights[2, i] * end_cop

                    # Add the last section
                    if last_live:
                        live_ranges.append((start_live, num_frames))
                        from_tendons.append(particle_through_tendon[p][start_time])
                        to_tendons.append(particle_through_tendon[p][num_frames-1])

                    # Now we want to filter the live sections
                    for i, (start_time, end_time) in enumerate(live_ranges):
                        duration = end_time - start_time
                        if duration == 1:
                            particle_age[p, start_time] = 0.5
                        elif duration > 1:
                            ramp_duration = int(math.floor(duration * 0.5))
                            if ramp_duration > particle_ramp_duration:
                                ramp_duration = particle_ramp_duration

                            for t in range(duration):
                                particle_age[p, start_time + t] = float(t) / float(duration-1)
                                if t < ramp_duration:
                                    particle_importance[p, start_time + t] = 1.0 - (float(t) / float(ramp_duration))
                                if duration - t < ramp_duration:
                                    particle_importance[p, start_time + t] = 1.0 - (float(duration - t) / float(ramp_duration))
                        # Now we want to low-pass filter the active section of the trajectory
                        if duration > 9:
                            # if particle_lowpass_hz < nyquist:
                            #     print('pre filtered: ')
                            #     print(particle_trajectories[p*3:p*3+3, start_time:end_time])
                            #     particle_trajectories[p*3:p*3+3, start_time:end_time] = filtfilt(b, a, particle_trajectories[p*3:p*3+3, start_time:end_time], method='gust') # padlen=200, padtype='constant')
                            #     print('filtered: ')
                            #     print(particle_trajectories[p*3:p*3+3, start_time:end_time])
                            particle_live[p, start_time:end_time] = 1

                            # for t in range(start_time, end_time):
                            #     if t > 0:
                            #         particle_velocity = np.linalg.norm(particle_trajectories[p*3:p*3+3, t] - particle_trajectories[p*3:p*3+3, t-1])
                            #         particle_velocities.append(particle_velocity)
                        if to_tendons[i]:
                            continue
                        negative_work_particle_emissions.append((end_time - 1, particle_trajectories[p*3:p*3+3, end_time - 1]))

                num_negative_work_particles_alive = [len([start_time for start_time, _ in negative_work_particle_emissions if (start_time <= t and start_time + negative_work_particle_lifetime > t)]) for t in range(num_frames)]
                num_negative_work_particles = max(num_negative_work_particles_alive)

                negative_work_particle_trajectories = np.zeros((num_negative_work_particles * 3, num_frames))
                negative_work_particle_age = np.zeros((num_negative_work_particles, num_frames))
                negative_work_particle_live = np.zeros((num_negative_work_particles, num_frames), dtype=np.int64)

                for start_time, start_pos in negative_work_particle_emissions:
                    avg_com_pos = np.zeros(3)
                    for b in range(skel.getNumBodyNodes()):
                        avg_com_pos += body_com_positions[b*3:b*3+3, start_time] * skel.getBodyNode(b).getMass()
                    avg_com_pos /= skel.getMass()

                    drift_dir = start_pos - avg_com_pos
                    drift_dir[1] = 0
                    # drift_dir = np.random.randn(3)
                    drift_dir /= np.linalg.norm(drift_dir)

                    for p in range(num_negative_work_particles):
                        if negative_work_particle_live[p, start_time:start_time+negative_work_particle_lifetime].sum() == 0:
                            break

                    for t in range(negative_work_particle_lifetime):
                        if start_time + t >= num_frames:
                            break
                        negative_work_particle_trajectories[p*3:p*3+3, start_time + t] = start_pos + drift_dir * negative_work_particle_dist_traveled * t
                        negative_work_particle_age[p, start_time + t] = float(t) / float(negative_work_particle_lifetime-1)
                        negative_work_particle_live[p, start_time + t] = 1

        if save_to_file is None:
            ticker: nimble.realtime.Ticker = nimble.realtime.Ticker(
                subject.getTrialTimestep(trial) / playback_speed)
        else:
            ticker: nimble.realtime.Ticker = None

        frame: int = 0

        running_energy_deriv: float = 0.0
        stored_energy = np.zeros(skel.getNumJoints())

        SKELETON_LAYER_NAME = 'Skeleton'
        ENERGY_ARROWS_LAYER_NAME = 'Energy Creation / Destruction'
        ENERGY_LAYER_NAME = 'Energy Flow'
        TENDON_LAYER_NAME = 'Best-Case Tendons'
        CONSERVED_ENERGY_LAYER_NAME = 'Conserved Energy'
        if show_energy:
            gui.createLayer(SKELETON_LAYER_NAME)
            gui.createLayer(ENERGY_LAYER_NAME)
            gui.createLayer(ENERGY_ARROWS_LAYER_NAME, defaultShow=False)
            gui.createLayer(TENDON_LAYER_NAME, defaultShow=False)
            gui.createLayer(CONSERVED_ENERGY_LAYER_NAME, defaultShow=False)

        coolwarm_cmap = plt.get_cmap('coolwarm')
        plasma_cmap = plt.get_cmap('plasma')
        # plasma_cmap = plt.get_cmap('viridis')
        # plasma_cmap = plt.get_cmap('cividis')

        def onTick(now):
            nonlocal frame
            nonlocal skel
            nonlocal subject
            nonlocal dof
            nonlocal dof_poses
            nonlocal dof_vels
            nonlocal dof_accs
            nonlocal dof_taus
            nonlocal timesteps
            nonlocal running_energy_deriv

            loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1, contactThreshold=20)
            skel.setPositions(loaded[0].pos)
            color = [-1, -1, -1, -1]
            # if show_energy:
            #     color = [0.5, 0.5, 0.5, 0.25]
            layer = ''
            if show_energy:
                layer = SKELETON_LAYER_NAME
            gui.renderSkeleton(skel, overrideColor=color, layer=layer)

            if dof is not None:
                joint_pos = skel.getJointWorldPositions([graph_joint])
                gui.setObjectPosition('active_joint', joint_pos)
                p = dof_poses[frame]
                v = dof_vels[frame]
                a = dof_accs[frame]
                t = dof_taus[frame]

                # dof_poses_with_zeros = np.zeros(num_frames)
                # dof_poses_with_zeros[0:frame] = dof_poses[0:frame]
                # gui.setRichPlotData('dof_plot', 'Pose', 'blue', 'line', timesteps, dof_poses_with_zeros)
                # dof_vels_with_zeros = np.zeros(num_frames)
                # dof_vels_with_zeros[0:frame] = dof_vels[0:frame]
                # gui.setRichPlotData('dof_plot', 'Vel', 'green', 'line', timesteps, dof_vels_with_zeros)
                # dof_taus_with_zeros = np.zeros(num_frames)
                # dof_taus_with_zeros[0:frame] = dof_taus[0:frame]
                # gui.setRichPlotData('dof_plot', 'Tau', 'red', 'line', timesteps, dof_taus_with_zeros)
                # # dof_power_with_zeros = np.zeros(num_frames)
                # # dof_power_with_zeros[0:frame] = dof_power[0:frame]
                # # gui.setRichPlotData('dof_plot', 'Power', 'purple', 'line', timesteps, dof_power_with_zeros)
                # dof_work_with_zeros = np.zeros(num_frames)
                # dof_work_with_zeros[0:frame] = dof_work[0:frame]
                # gui.setRichPlotData('dof_plot', 'Net Work', 'purple', 'line', timesteps, dof_work_with_zeros)

                gui.setTextContents('dof_plot_text', 'DOF '+graph_dof+' values<br>Pos: '+str(p)+'<br>Vel: '+str(v)+'<br>Acc: '+str(a)+'<br>Tau: '+str(t)+'<br>Power:'+str(dof_power[frame])+'<br>Work: '+str(dof_work[frame]))

            if show_energy:
                energy = energy_frames[frame]

                def heat_to_rgb(heat):
                    # ensure the heat value is between 0 and 1
                    heat = max(0, min(heat, 1))

                    # get the RGB value from the 'magma' colormap
                    rgb = coolwarm_cmap(heat)[0:3]
                    # rgb = plt.get_cmap('plasma')(1.0 - heat)[0:3]

                    # scale the RGB value to between 0 and 255
                    return rgb

                power_arrow_scale_factor = 0.25 / peak_joint_net_power
                energy_sphere_scale_factor = 5e-3
                # power_sphere_scale_factor = 1e-4
                tendon_sphere_scale_factor = 0.25 / peak_tendon_storage

                # gui.createSphere('recycled_power', np.ones(3) * energy_sphere_scale_factor * conserved_energy[frame], [1, 0, 0], [0, 0, 1, 1])

                body_radii = np.zeros(skel.getNumBodyNodes())
                # for i in range(0, skel.getNumBodyNodes()):
                #     body = skel.getBodyNode(i)
                #     total_energy = energy.bodyKineticEnergy[i] + energy.bodyPotentialEnergy[i]
                #     radius = energy_sphere_scale_factor * total_energy
                #     gui.createSphere(body.getName()+"_energy", radius * np.ones(3), energy.bodyCenters[i], [0, 0, 1, 0.5])
                #     body_radii[i] = radius

                # for i in range(0, skel.getNumBodyNodes()):
                #     body = skel.getBodyNode(i)
                #     radius = (float(quantized_body_energies[frame][i+1]) * 0.3 / num_packets)
                #     gui.createSphere(body.getName()+"_energy_discrete", radius * np.ones(3), energy.bodyCenters[i], [0, 0, 1, 0.5])
                #     body_radii[i] = radius

                body_plasma_colors = []

                for i in range(0, skel.getNumBodyNodes()):
                    body = skel.getBodyNode(i)
                    energy_density = (energy.bodyKineticEnergy[i] + energy.bodyPotentialEnergy[i]) / skel.getBodyNode(i).getMass()
                    raw_percentage = energy_density / peak_energy_density
                    scaled_percentage = np.cbrt(raw_percentage)
                    rgb = heat_to_rgb(scaled_percentage)
                    color: np.ndarray = np.array([rgb[0], rgb[1], rgb[2], 1.0])
                    for k in range(body.getNumShapeNodes()):
                        gui.setObjectColor(
                            'world_' + skel.getName() + "_" + body.getName() + "_" + str(k), color)
                    body_plasma_colors.append(plasma_cmap(np.sqrt(scaled_percentage))[0:3])


                for i in range(num_packets):
                    if particle_live[i, frame] == 0:
                        gui.deleteObject('particle'+str(i))
                    else:
                        points = []
                        hist_size = 7
                        hist_stride = 3
                        last_live_point = particle_trajectories[i*3:i*3+3, frame]
                        hist_live_continuous = True
                        for hist in range(hist_size):
                            hist_frame = max(frame - (hist * hist_stride), 0)
                            if hist > 0:
                                for s in range(hist_stride + 1):
                                    test_frame = max(frame - (((hist - 1) * hist_stride) + s), 0)
                                    if particle_live[i, test_frame] == 0:
                                        hist_live_continuous = False
                            if hist_live_continuous:
                                last_live_point = particle_trajectories[i*3:i*3+3, hist_frame]
                            points.append(last_live_point)

                        points.reverse()
                        # particle_velocity = 0.0
                        # if particle_live[i, frame-1] == 1:
                        #     particle_velocity = np.linalg.norm(particle_trajectories[i*3:i*3+3, frame] - particle_trajectories[i*3:i*3+3, frame - 1])

                        age: float = particle_age[i, frame]

                        body_index: int = particle_bodies[i][frame] - 1
                        rgb = body_plasma_colors[body_index]
                        # rgb = heat_to_rgb(scaled_percentage)

                        # age_fraction = particle_ramp_duration
                        importance = (max(age, 1.0 - age))
                        # importance = particle_importance[i, frame]
                        color = [rgb[0], rgb[1], rgb[2], importance * 0.75]

                        gui.createLine('particle'+str(i), points, color, layer=ENERGY_LAYER_NAME)
                        # gui.createBox('particle' + str(i), np.ones(3) * 0.02, particle_trajectories[i*3:i*3+3, frame],
                        #                           np.zeros(3), color, layer=ENERGY_LAYER_NAME)

                # negative_work_rgb = heat_to_rgb(1.0)
                # for i in range(num_negative_work_particles):
                #     if negative_work_particle_live[i, frame] == 0:
                #         gui.deleteObject('negative_work_particle'+str(i))
                #     else:
                #         age: float = negative_work_particle_age[i, frame]
                #         size: float = age * age * age
                #         color = [negative_work_rgb[0], negative_work_rgb[1], negative_work_rgb[2], 0.2 * (1.0 - age) + 0.025]
                #         gui.createBox('negative_work_particle' + str(i), np.ones(3) * 0.02 * (1.0 + 4.0 * size), negative_work_particle_trajectories[i*3:i*3+3, frame],
                #                                   np.zeros(3), color, layer=ENERGY_LAYER_NAME)

                running_energy_deriv += np.sum(energy.bodyKineticEnergyDeriv + energy.bodyPotentialEnergyDeriv) * subject.getTrialTimestep(trial)

                positive_power_rgb = heat_to_rgb(1.0)
                positive_power_color = [positive_power_rgb[0], positive_power_rgb[1], positive_power_rgb[2], 1.0]
                stored_power_rgb = heat_to_rgb(0.5)
                stored_power_color = [179.0 / 255, 123.0 / 255, 201.0 / 255, 0.8]
                negative_power_rgb = heat_to_rgb(0.0)
                negative_power_color = [negative_power_rgb[0], negative_power_rgb[1], negative_power_rgb[2], 1.0]

                treadmill_offset = avg_vel / np.linalg.norm(avg_vel)
                gui.createSphere('recycled_power', np.ones(3) * tendon_sphere_scale_factor * conserved_energy[frame], skel.getCOM() - (treadmill_offset * 2), stored_power_color, layer=CONSERVED_ENERGY_LAYER_NAME)

                for j, joint in enumerate(energy.joints):
                    net_power = power_not_retrieved_from_tendons[j, frame] # joint.powerToChild + joint.powerToParent
                    # net_power = joint.powerToChild + joint.powerToParent

                    net_joint_power = joint.powerToParent + joint.powerToChild
                    if abs(joint.powerToParent) > abs(joint.powerToChild):
                        # Point to parent
                        if net_joint_power > 0:
                            gui.renderArrow(joint.worldCenter, joint.parentCenter,
                                            net_joint_power * power_arrow_scale_factor * 0.5,
                                            net_joint_power * power_arrow_scale_factor, color=positive_power_color,
                                            prefix=joint.name+'_arrow', layer=ENERGY_ARROWS_LAYER_NAME)
                        else:
                            gui.renderArrow(joint.worldCenter, joint.parentCenter,
                                            -net_joint_power * power_arrow_scale_factor * 0.5,
                                            -net_joint_power * power_arrow_scale_factor * 0.5, color=negative_power_color,
                                            prefix=joint.name + '_arrow', layer=ENERGY_ARROWS_LAYER_NAME)
                    else:
                        # Point to child
                        if net_joint_power > 0:
                            gui.renderArrow(joint.worldCenter, joint.childCenter,
                                            net_joint_power * power_arrow_scale_factor * 0.5,
                                            net_joint_power * power_arrow_scale_factor, color=positive_power_color,
                                            prefix=joint.name+'_arrow', layer=ENERGY_ARROWS_LAYER_NAME)
                        else:
                            gui.renderArrow(joint.worldCenter, joint.childCenter,
                                            -net_joint_power * power_arrow_scale_factor * 0.5,
                                            -net_joint_power * power_arrow_scale_factor * 0.5, color=negative_power_color,
                                            prefix=joint.name + '_arrow', layer=ENERGY_ARROWS_LAYER_NAME)

                    # if joint.powerToChild > 0:
                    #     gui.renderArrow(adjusted_child_joint_center, adjusted_child_center, joint.powerToChild * power_arrow_scale_factor * 0.5, joint.powerToChild * power_arrow_scale_factor, color=[0,0,1,0.5], prefix=joint.name+'_child', layer=ENERGY_ARROWS_LAYER_NAME)
                    # else:
                    #     gui.renderArrow(adjusted_child_center, adjusted_child_joint_center, -joint.powerToChild * power_arrow_scale_factor * 0.5, -joint.powerToChild * power_arrow_scale_factor, color=[0,0,1,0.5], prefix=joint.name+'_child', layer=ENERGY_ARROWS_LAYER_NAME)
                    # if joint.powerToParent > 0:
                    #     gui.renderArrow(adjusted_parent_joint_center, adjusted_parent_center, joint.powerToParent * power_arrow_scale_factor * 0.5, joint.powerToParent * power_arrow_scale_factor, color=[0,0,1,0.5], prefix=joint.name+'_parent', layer=ENERGY_ARROWS_LAYER_NAME)
                    # else:
                    #     gui.renderArrow(adjusted_parent_center, adjusted_parent_joint_center, -joint.powerToParent * power_arrow_scale_factor * 0.5, -joint.powerToParent * power_arrow_scale_factor, color=[0,0,1,0.5], prefix=joint.name+'_parent', layer=ENERGY_ARROWS_LAYER_NAME)

                    # if net_power < 0:
                    #     gui.createSphere('energy_'+joint.name, np.ones(3) * net_power * power_sphere_scale_factor, joint.worldCenter, negative_power_color)
                    #     # gui.deleteObject('energy_' + joint.name)
                    # else:
                    #     gui.createSphere('energy_'+joint.name, np.ones(3) * net_power * power_sphere_scale_factor, joint.worldCenter, positive_power_color, layer=ENERGY_LAYER_NAME)

                    # Don't store energy in "tendons" at the root joint, since the residuals aren't physical anyways
                    if j > 0:
                        gui.createSphere('tendon_'+joint.name, np.ones(3) * energy_stored_in_tendons[j, frame] * tendon_sphere_scale_factor, joint.worldCenter, stored_power_color, layer=TENDON_LAYER_NAME)

                # for contact in energy.contacts:
                #     if contact.powerToBody < 0:
                #         gui.deleteObject('energy_' + contact.contactBody)
                #     else:
                #         gui.createSphere('energy_'+contact.contactBody, np.ones(3) * np.cbrt(contact.powerToBody) * power_sphere_scale_factor, contact.worldCenter, positive_power_color, layer=ENERGY_LAYER_NAME)

            frame += 1
            # Loop before the last frame, if we're showing energy
            if show_energy:
                if frame >= num_frames - 1:
                    frame = 0
            else:
                if frame >= num_frames:
                    frame = 0

        if save_to_file is None:
            ticker.registerTickListener(onTick)
            ticker.start()

            print(subject.getHref())
            print(subject.getTrialName(trial))

            # Don't immediately exit while we're serving
            nimble_gui.blockWhileServing()
        else:
            gui.setFramesPerSecond(int(1.0/ subject.getTrialTimestep(trial)))
            print('Constructing frames:')
            for t in range(num_frames):
                if t % 25 == 0:
                    print(str(t)+'/'+str(num_frames))
                onTick(t)
                gui.saveFrame()
            gui.writeFramesJson(save_to_file)

        return True
