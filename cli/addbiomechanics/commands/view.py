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
        view_parser.add_argument(
            '--particle-lowpass-hz',
            help='The frequency to filter the particles at',
            type=int,
            default=10)

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
        particle_lowpass_hz = args.particle_lowpass_hz

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

            #########################################################################
            # Estimate body COM minimum height (to set 0 potential energy) and treadmill speed
            #########################################################################

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

            #########################################################################
            # Compute the energy at each frame, with adjustments for potential energy and treadmill speed
            #########################################################################

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

            #########################################################################
            # Compute tendons
            #########################################################################

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

                # Find the running smallest value of stored energy over time
                smallest_seen = stored_energy[0]
                lowest_previous_stored_energy = np.zeros(num_frames)
                for frame in range(num_frames):
                    if stored_energy[frame] < smallest_seen:
                        smallest_seen = stored_energy[frame]
                    lowest_previous_stored_energy[frame] = smallest_seen

                best = 0
                for frame in range(num_frames):
                    if stored_energy[frame] - lowest_previous_stored_energy[frame] > best:
                        best = stored_energy[frame] - lowest_previous_stored_energy[frame]
                best_case_tendon_capacity[joint] = best
            energy_stored_in_tendons = np.zeros((skel.getNumJoints(), num_frames))
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
                    assert(energy_stored_in_tendons[joint, frame + 1] <= best_case_tendon_capacity[joint])
                    assert(energy_stored_in_tendons[joint, frame + 1] >= 0)
            peak_tendon_storage = np.max(energy_stored_in_tendons)
            for joint in range(skel.getNumJoints()):
                print('peak tendon energy for joint '+str(joint)+' ['+skel.getJoint(joint).getName()+']: '+str(np.max(energy_stored_in_tendons[joint, :]))+' of peak '+str(best_case_tendon_capacity[joint])+'J')
            # Don't pick a max that's too small, or the visualization will have tendons way too large
            if peak_tendon_storage < 40:
                peak_tendon_storage = 40
            print('Peak tendon storage: '+str(peak_tendon_storage)+'J')

            #########################################################################
            # Quantize the energy flows into packets
            #########################################################################

            print('Quantizing energy in '+str(num_frames)+' frames...')

            # Joints can generate energy, but bodies cannot
            node_attached_to_sink: List[bool] = []
            for _ in range(skel.getNumBodyNodes()):
                node_attached_to_sink.append(False)
            for _ in range(skel.getNumJoints()):
                node_attached_to_sink.append(True)

            # Set up the arcs connecting the graph
            arcs: List[Tuple[int, int]] = []
            joint_to_parent_arc: Dict[int, int] = {}
            joint_to_child_arc: Dict[int, int] = {}
            for j in range(skel.getNumJoints()):
                joint = skel.getJoint(j)

                # All arcs are (from, to), and because the energy frames express joints in powerToParent and
                # powerToChild, the (from) is always the joint, and (to) is always the body
                from_node = skel.getNumBodyNodes() + j

                to_child = joint.getChildBodyNode().getIndexInSkeleton()
                joint_to_child_arc[j] = len(arcs)
                arcs.append((from_node, to_child))

                if joint.getParentBodyNode() is not None:
                    to_parent = joint.getParentBodyNode().getIndexInSkeleton()
                    joint_to_parent_arc[j] = len(arcs)
                    arcs.append((from_node, to_parent))
                else:
                    joint_to_parent_arc[j] = -1

            # Create the native-code discretizer
            native_discretizer = nimble.math.GraphFlowDiscretizer(skel.getNumBodyNodes() + skel.getNumJoints(), arcs, node_attached_to_sink)

            # Create the matrices for energy levels and arc flows
            energy_levels = np.zeros((skel.getNumBodyNodes() + skel.getNumJoints(), num_frames))
            arc_rates = np.zeros((len(arcs), num_frames))

            for frame in range(num_frames):
                this_energy = energy_frames[frame]
                for i in range(skel.getNumBodyNodes()):
                    energy_levels[i, frame] = this_energy.bodyKineticEnergy[i] + this_energy.bodyPotentialEnergy[i]
                for j in range(skel.getNumJoints()):
                    energy_levels[skel.getNumBodyNodes() + j, frame] = energy_stored_in_tendons[j, frame]
                for j in range(skel.getNumJoints()):
                    if joint_to_parent_arc[j] != -1:
                        arc_rates[joint_to_parent_arc[j], frame] = this_energy.joints[j].powerToParent * subject.getTrialTimestep(trial)
                    arc_rates[joint_to_child_arc[j], frame] = this_energy.joints[j].powerToChild * subject.getTrialTimestep(trial)

            arc_rates = native_discretizer.cleanUpArcRates(energy_levels, arc_rates)

            particles: List[nimble.math.ParticlePath] = native_discretizer.discretize(num_packets, energy_levels, arc_rates)
            print('Got particles: '+str(len(particles)))

            #########################################################################
            # Render the energy flows as real particles
            #########################################################################

            # First collect all the body and joint positions
            body_com_positions = np.zeros((skel.getNumBodyNodes() * 3, num_frames))
            joint_positions = np.zeros((skel.getNumJoints() * 3, num_frames))
            for frame in range(num_frames):
                loaded = subject.readFrames(trial, frame, 1)
                skel.setPositions(loaded[0].pos)
                for b in range(skel.getNumBodyNodes()):
                    body_com_positions[b*3:b*3+3, frame] = skel.getBodyNode(b).getCOM()
                joint_positions[:, frame] = skel.getJointWorldPositions([skel.getJoint(j) for j in range(skel.getNumJoints())])

            # Animation parameters
            particle_intro_duration = 0.015
            particle_intro_frames = int(particle_intro_duration / subject.getTrialTimestep(trial))
            particle_intro_distance = 0.15
            particle_outro_duration = 0.045
            particle_outro_frames = int(particle_outro_duration / subject.getTrialTimestep(trial))
            particle_outro_distance = 0.25
            fs = 1 / subject.getTrialTimestep(trial)
            nyquist = fs / 2
            if particle_lowpass_hz < nyquist:
                b, a = butter(2, particle_lowpass_hz, 'low', fs=fs)

            # For efficiency in re-using the "delete" calls in the GUI, to keep the generated filesize down,
            # we group the particles by non-overlapping lifetimes
            particle_stacks: List[List[nimble.math.ParticlePath]] = []
            particle_stacks_start_time: List[int] = []
            particle_stacks_end_time: List[int] = []
            for p in range(len(particles)):
                particle_start_frame = max(particles[p].startTime - particle_intro_frames, 0)
                particle_death_frame = min(particles[p].startTime + len(particles[p].nodeHistory) + particle_outro_frames, num_frames)
                found_stack = False
                for s in range(len(particle_stacks)):
                    if particle_death_frame + 2 < particle_stacks_start_time[s]:
                        # This particle dies before the stack starts, so it's not overlapping, and can be added
                        particle_stacks[s].insert(0, particles[p])
                        particle_stacks_start_time[s] = particle_start_frame
                        found_stack = True
                        break
                    if particle_start_frame > particle_stacks_end_time[s] + 2:
                        # This particle starts after the stack ends, so it's not overlapping, and can be added
                        particle_stacks[s].append(particles[p])
                        particle_stacks_end_time[s] = particle_death_frame
                        found_stack = True
                        break
                if not found_stack:
                    # This particle overlaps with all existing stacks, so create a new stack
                    particle_stacks.append([particles[p]])
                    particle_stacks_start_time.append(particle_start_frame)
                    particle_stacks_end_time.append(particle_death_frame)

            print('Particles unified into non-overlapping stacks: '+str(len(particle_stacks)))

            # Now that we have the stacks, we can render them
            particle_trajectories = np.zeros((len(particle_stacks) * 3, num_frames))
            particle_live = np.zeros((len(particle_stacks), num_frames), dtype=np.int32)
            particle_nodes = np.zeros((len(particle_stacks), num_frames), dtype=np.int32)
            particle_intro_fade = np.zeros((len(particle_stacks), num_frames))
            particle_outro_fade = np.zeros((len(particle_stacks), num_frames))
            particle_age = np.zeros((len(particle_stacks), num_frames))

            for s in range(len(particle_stacks)):
                stack = particle_stacks[s]
                for p in range(len(stack)):
                    particle = stack[p]

                    # Figure out the contiguous sections of the particle's history
                    # Each section is (node, start_time, end_time)
                    sections: List[Tuple[int, int, int]] = []
                    current_node = particle.nodeHistory[0]
                    current_start = particle.startTime
                    for t in range(1, len(particle.nodeHistory)):
                        if particle.nodeHistory[t] != current_node:
                            sections.append((current_node, current_start, particle.startTime + t))
                            current_node = particle.nodeHistory[t]
                            current_start = particle.startTime + t
                    sections.append((current_node, current_start, particle.startTime + len(particle.nodeHistory)))

                    sec_offsets = []
                    for sec, (node, start_time, end_time) in enumerate(sections):
                        is_body = node < skel.getNumBodyNodes()
                        sec_offset = np.random.randn(3)
                        sec_offset /= np.linalg.norm(sec_offset)
                        sec_offset *= 0.05 if is_body else 0.03
                        sec_offsets.append(sec_offset)

                    # Sections should go (body, joint, body, joint, body, joint, ...)
                    for sec, (node, start_time, end_time) in enumerate(sections):
                        particle_nodes[s, start_time:end_time] = node
                        particle_live[s, start_time:end_time] = 1
                        # This section should never have been written to before
                        assert (particle_trajectories[s * 3:s * 3 + 3, start_time:end_time].sum() == 0)

                        is_body = node < skel.getNumBodyNodes()
                        duration = end_time - start_time
                        blend_frames = int(math.floor(duration / 2))

                        if is_body:
                            body_offset = sec_offsets[sec]

                            particle_trajectories[s*3:s*3+3, start_time:end_time] = body_com_positions[node*3:node*3+3, start_time:end_time]
                            for t in range(start_time, end_time):
                                particle_trajectories[s * 3:s * 3 + 3, t] += body_offset

                            if blend_frames > 0:
                                if sec > 0:
                                    prev_node = sections[sec-1][0]
                                    prev_node_offset = sec_offsets[sec-1]
                                    assert(prev_node >= skel.getNumBodyNodes())
                                    prev_joint = prev_node - skel.getNumBodyNodes()
                                    for i in range(blend_frames):
                                        alpha = i / blend_frames
                                        particle_trajectories[s*3:s*3+3, start_time+i] = alpha * particle_trajectories[s*3:s*3+3, start_time+i] + \
                                                                                (1-alpha) * (joint_positions[prev_joint*3:prev_joint*3+3, start_time+i] + prev_node_offset)
                                if sec < len(sections) - 1:
                                    next_node = sections[sec + 1][0]
                                    next_node_offset = sec_offsets[sec+1]
                                    if next_node < skel.getNumBodyNodes():
                                        print('WARNING: Body to body transition in particle path, this should not happen')
                                        print('  Particle: '+str(p))
                                        print('  Section: '+str(s))
                                        print('  Node: '+str(node))
                                        print('  Next node: '+str(next_node))
                                        print('  Particle: '+str(particle.nodeHistory))
                                        print('  Sections: '+str(sections))
                                        print('  Start time: '+str(start_time))
                                        print('  End time: '+str(end_time))
                                        print('  Duration: '+str(duration))
                                    assert (next_node >= skel.getNumBodyNodes())
                                    next_joint = next_node - skel.getNumBodyNodes()
                                    for i in range(blend_frames):
                                        alpha = i / blend_frames
                                        particle_trajectories[s*3:s*3+3, end_time-i-1] = alpha * particle_trajectories[s*3:s*3+3, end_time-i-1] + \
                                                                                (1-alpha) * (joint_positions[next_joint*3:next_joint*3 + 3, end_time-i-1] + next_node_offset)
                        else:
                            joint = node - skel.getNumBodyNodes()
                            particle_trajectories[s*3:s*3+3, start_time:end_time] = joint_positions[joint * 3:joint * 3 + 3, start_time:end_time]
                            node_offset = sec_offsets[sec]
                            for t in range(start_time, end_time):
                                particle_trajectories[s * 3:s * 3 + 3, t] += node_offset

                    # Compute the intro
                    if particle.startTime > 0:
                        if particle.nodeHistory[0] < skel.getNumBodyNodes():
                            start_pos = body_com_positions[particle.nodeHistory[0]*3:particle.nodeHistory[0]*3+3, particle.startTime]
                        else:
                            joint = particle.nodeHistory[0] - skel.getNumBodyNodes()
                            start_pos = joint_positions[joint*3:joint*3+3, particle.startTime]
                        random_velocity = np.random.randn(3)
                        random_velocity /= np.linalg.norm(random_velocity)
                        random_velocity *= (particle_intro_distance / particle_intro_frames) / subject.getTrialTimestep(trial)
                        for i in range(particle_intro_frames):
                            if particle.startTime - i - 1 >= 0:
                                particle_trajectories[s*3:s*3+3, particle.startTime - i - 1] = start_pos + (random_velocity * float(i) * subject.getTrialTimestep(trial))
                                particle_live[s, particle.startTime - i - 1] = 1
                                particle_intro_fade[s, particle.startTime - i - 1] = i / particle_intro_frames

                    # Compute the outro
                    if particle.startTime + len(particle.nodeHistory) < num_frames:
                        if particle.nodeHistory[-1] < skel.getNumBodyNodes():
                            end_pos = body_com_positions[particle.nodeHistory[-1]*3:particle.nodeHistory[-1]*3+3, particle.startTime + len(particle.nodeHistory)]
                        else:
                            joint = particle.nodeHistory[-1] - skel.getNumBodyNodes()
                            end_pos = joint_positions[joint*3:joint*3+3, particle.startTime + len(particle.nodeHistory)]
                        random_velocity = np.random.randn(3)
                        random_velocity /= np.linalg.norm(random_velocity)
                        random_velocity *= (particle_outro_distance / particle_outro_frames) / subject.getTrialTimestep(trial)
                        for i in range(particle_outro_frames):
                            if particle.startTime + len(particle.nodeHistory) + i + 1 < num_frames:
                                particle_trajectories[s*3:s*3+3, particle.startTime + len(particle.nodeHistory) + i + 1] = end_pos + (random_velocity * float(i) * subject.getTrialTimestep(trial))
                                particle_live[s, particle.startTime + len(particle.nodeHistory) + i + 1] = 1
                                particle_outro_fade[s, particle.startTime + len(particle.nodeHistory) + i + 1] = i / particle_outro_frames

                    start_time = max(particle.startTime - particle_intro_frames, 0)
                    end_time = min(particle.startTime + len(particle.nodeHistory) + particle_outro_frames, num_frames)

                    if particle_lowpass_hz < nyquist and end_time - start_time > 9:
                        particle_trajectories[s * 3:s * 3 + 3, start_time:end_time] = filtfilt(b, a, particle_trajectories[s * 3:s * 3 + 3, start_time:end_time])

                    for t in range(start_time, end_time):
                        particle_age[s, t] = (t - start_time) / (end_time - start_time)

                    # If we have a particle that starts on the first frame, then just assume age cannot go below 0.5
                    if start_time == 0:
                        for t in range(start_time, end_time):
                            if particle_age[s, t] < 0.5:
                                particle_age[s, t] = 0.5

                    # If we have a particle that ends on the last frame, then just assume age cannot go above 0.5
                    if end_time >= num_frames - 1:
                        for t in range(start_time, end_time):
                            if particle_age[s, t] > 0.5:
                                particle_age[s, t] = 0.5

                    # if node < skel.getNumBodyNodes():
                    #     body = skel.getBodyNode(node)
                    #     pos = body.getCOM()
                    # else:
                    #     joint = skel.getJoint(node - skel.getNumBodyNodes())
                    #     pos = joint.getTransformFromParentBodyNode().translation()
                    # color = heat_to_rgb(particle.energyHistory[frame - particle.startTime] / peak_energy_density)
                    # if particle_lowpass_hz < nyquist:
                    #     color = filtfilt(b, a, color)
                    # gui.createSphere('particle_'+str(p), [0.01, 0.01, 0.01], pos, color, layer=ENERGY_LAYER_NAME)

        if save_to_file is None:
            ticker: nimble.realtime.Ticker = nimble.realtime.Ticker(
                subject.getTrialTimestep(trial) / playback_speed)
        else:
            ticker: nimble.realtime.Ticker = None

        frame: int = 0

        running_energy_deriv: float = 0.0
        stored_energy = np.zeros(skel.getNumJoints())

        SKELETON_LAYER_NAME = 'Skeleton'
        ENERGY_LAYER_NAME = 'Energy Flow'
        TENDON_LAYER_NAME = 'Spring Energy (Idealized Tendons)'
        if show_energy:
            gui.createLayer(SKELETON_LAYER_NAME)
            gui.createLayer(ENERGY_LAYER_NAME)
            # gui.createLayer(TENDON_LAYER_NAME, defaultShow=True)

        coolwarm_cmap = plt.get_cmap('coolwarm')
        plasma_cmap = plt.get_cmap('plasma')
        # plasma_cmap = plt.get_cmap('viridis')
        # plasma_cmap = plt.get_cmap('cividis')

        if show_energy and len(particle_stacks) > 0:
            hot_rgb = coolwarm_cmap(1.0)[0:3]
            hot_color_style = 'color: rgb('+str(int(hot_rgb[0]*255))+','+str(int(hot_rgb[1]*255))+','+str(int(hot_rgb[2]*255))+')'
            cold_rgb = coolwarm_cmap(0.0)[0:3]
            cold_color_style = 'color: rgb('+str(int(cold_rgb[0]*255))+','+str(int(cold_rgb[1]*255))+','+str(int(cold_rgb[2]*255))+')'
            gui.createText('energy_plot_text', '<b>Legend:</b><br>Each particle is <b>'+str(round(particle_stacks[0][0].energyValue, 2))+'J</b><br> Particles start <b><span style="'+hot_color_style+'">red</span></b> (when created by positive mechanical work), and slowly turn <b><span style="'+cold_color_style+'">blue</span></b> until they are vented to heat (by negative work).<br/><br/> Bone colors are <b>energy density (J/kg)</b>.<br/><br/><b><span style="'+hot_color_style+'">Red spheres</span></b> at the joints show an upper-bound on how much potential energy could be stored in springs at the joint (this is probably an over-estimate of actual tendon storage).', [20, 200], [180, 30], ENERGY_LAYER_NAME)

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

                energy_sphere_scale_factor = 5e-3
                # power_sphere_scale_factor = 1e-4

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
                    name = body.getName()
                    body_energy = energy.bodyKineticEnergy[i] + energy.bodyPotentialEnergy[i]
                    body_energy_density = body_energy / skel.getBodyNode(i).getMass()
                    raw_percentage = body_energy_density / peak_energy_density
                    scaled_percentage = np.cbrt(raw_percentage)
                    rgb = heat_to_rgb(scaled_percentage)
                    color: np.ndarray = np.array([rgb[0], rgb[1], rgb[2], 1.0])
                    for k in range(body.getNumShapeNodes()):
                        key = 'world_' + skel.getName() + "_" + body.getName() + "_" + str(k)
                        gui.setObjectColor(
                            key, color)
                        gui.setObjectTooltip(key, name + " Energy: " + str(round(body_energy, 1))+'J')
                    body_plasma_colors.append(plasma_cmap(np.sqrt(scaled_percentage))[0:3])


                for i in range(len(particle_stacks)):
                    if particle_live[i, frame] == 0:
                        gui.deleteObject('particle'+str(i))
                    else:
                        points = []
                        width = []
                        hist_size = 7
                        hist_stride = max(int((0.02 / subject.getTrialTimestep(trial)) / hist_size), 1)

                        cursor = frame
                        for hist in range(hist_size * hist_stride):
                            if cursor < 0 or particle_live[i, cursor] == 0:
                                cursor += 1
                            if hist % hist_stride == 0:
                                points.append(particle_trajectories[i * 3:i * 3 + 3, cursor])
                                point_intro = particle_intro_fade[i, cursor]
                                point_outro = particle_outro_fade[i, cursor]
                                width.append(1.0 + (point_outro + point_intro) * 4.0)
                            cursor -= 1
                        transition = particle_intro_fade[i, frame] + particle_outro_fade[i, frame]

                        points.reverse()
                        width.reverse()

                        # Ensure the points and width are always a fixed length
                        while len(points) < hist_size:
                            points.append(points[-1])
                            width.append(width[-1])

                        # particle_velocity = 0.0
                        # if particle_live[i, frame-1] == 1:
                        #     particle_velocity = np.linalg.norm(particle_trajectories[i*3:i*3+3, frame] - particle_trajectories[i*3:i*3+3, frame - 1])

                        # node_index: int = particle_nodes[i][frame]
                        # if node_index < skel.getNumBodyNodes():
                        #     rgb = body_plasma_colors[node_index]
                        # else:
                        #     # joint = node_index - skel.getNumBodyNodes()
                        #     rgb = [0.5, 0.0, 0.5]
                        # # rgb = heat_to_rgb(scaled_percentage)

                        rgb = heat_to_rgb(1.0 - particle_age[i, frame])

                        color = [rgb[0], rgb[1], rgb[2], 1.0 - transition]

                        gui.createLine('particle'+str(i), points, color, layer=ENERGY_LAYER_NAME, width=width)
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
                # gui.createSphere('recycled_power', np.ones(3) * tendon_sphere_scale_factor * conserved_energy[frame], skel.getCOM() - (treadmill_offset * 2), stored_power_color, layer=CONSERVED_ENERGY_LAYER_NAME)

                for j, joint in enumerate(energy.joints):
                    # Don't store energy in "tendons" at the root joint, since the residuals aren't physical anyways
                    if j > 0:
                        tendon_percent = energy_stored_in_tendons[j, frame] / peak_tendon_storage
                        # Only show the top 50% of tendon energy in color, only the part that gets warm
                        tendon_rgb = heat_to_rgb(0.5 + 0.5 * tendon_percent)
                        tendon_color = [tendon_rgb[0], tendon_rgb[1], tendon_rgb[2], 0.5]
                        gui.createSphere('tendon_'+joint.name, np.ones(3) * tendon_percent * 0.15, joint.worldCenter, tendon_color, layer=ENERGY_LAYER_NAME)
                        gui.setObjectTooltip('tendon_'+joint.name, "Spring at " + joint.name + ": " + str(round(energy_stored_in_tendons[j, frame], 1))+'J')

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
