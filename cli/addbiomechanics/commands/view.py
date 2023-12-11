import time

from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from typing import List, Dict, Tuple

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
            '--show-root-frame',
            help='Show all the motion and features in the root frame, rather than world frame. This means locking the '
                 'root frame to the origin.',
            type=bool,
            default=False)
        view_parser.add_argument(
            '--playback-speed',
            help='A number representing the fraction of realtime to play back the data at. Default is 1.0, for '
                 'realtime playback.',
            type=float,
            default=1.0)
        view_parser.add_argument('--loop-frames', type=int, nargs='+', default=[],
                               help='Specific frames to loop over.')

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'view':
            return False
        file_path: str = args.file_path
        trial: int = args.trial
        graph_dof: str = args.graph_dof
        graph_lowpass_hz: int = args.graph_lowpass_hz
        playback_speed: float = args.playback_speed
        show_energy: bool = args.show_energy
        show_root_frame: bool = args.show_root_frame
        loop_frames: List[int] = args.loop_frames

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

        geometry: str = args.geometry

        if geometry is None:
            # Check if the "./Geometry" folder exists, and if not, download it
            if not os.path.exists('./Geometry'):
                print('Downloading the Geometry folder from https://addbiomechanics.org/resources/Geometry.zip')
                exit_code = os.system('wget https://addbiomechanics.org/resources/Geometry.zip')
                if exit_code != 0:
                    print('ERROR: Failed to download Geometry.zip. You may need to install wget. If you are on a Mac, '
                          'try running "brew install wget"')
                    return False
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
        contact_bodies = subject.getGroundForceBodies()
        print('Contact bodies: '+str(contact_bodies))

        num_frames = subject.getTrialLength(trial)
        skel = subject.readSkel(0, geometry)

        print('DOFs:')
        for i in range(skel.getNumDofs()):
            print(' ['+str(i)+']: '+skel.getDofByIndex(i).getName())

        world = nimble.simulation.World()
        world.addSkeleton(skel)
        world.setGravity([0, -9.81, 0])
        skel.setGravity([0, -9.81, 0])

        gui = NimbleGUI(world)
        gui.serve(8080)

        gui.nativeAPI().createText('missing_reason', '', [100, 50], [200, 50])

        if graph_dof is not None:
            dof = skel.getDof(graph_dof)
            if dof is None:
                print('ERROR: DOF to graph "'+graph_dof+'" not found')
                return False
            graph_joint = skel.getJoint(dof.getJointName())
            joint_pos = skel.getJointWorldPositions([graph_joint])
            gui.nativeAPI().createSphere('active_joint', [0.05, 0.05, 0.05], joint_pos, [1,0,0,1])
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
                loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1, True, True)
                processing_pass = loaded[0].processingPasses[0]
                p = processing_pass.pos[dof_index]
                v = processing_pass.vel[dof_index]
                a = processing_pass.acc[dof_index]
                t = processing_pass.tau[dof_index]
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

            gui.nativeAPI().createRichPlot('dof_plot', [50, 100], [400, 200], 0, subject.getTrialLength(trial) * subject.getTrialTimestep(trial), min_over_all, max_over_all, 'DOF '+graph_dof, 'Time (s)', 'Values')

            gui.nativeAPI().setRichPlotData('dof_plot', 'Pose', 'blue', 'line', timesteps, dof_poses)
            gui.nativeAPI().setRichPlotData('dof_plot', 'Vel', 'green', 'line', timesteps, dof_vels)
            gui.nativeAPI().setRichPlotData('dof_plot', 'Tau', 'red', 'line', timesteps, dof_taus)
            # gui.nativeAPI().setRichPlotData('dof_plot', 'Power', 'purple', 'line', timesteps, dof_power)
            gui.nativeAPI().setRichPlotData('dof_plot', 'Net Work', 'purple', 'line', timesteps, dof_work)

            gui.nativeAPI().createText('dof_plot_text', 'DOF '+graph_dof+' values', [50, 350], [400, 50])
        else:
            dof = None

        if show_energy:
            body_min_height = np.ones(skel.getNumBodyNodes()) * 1000

            for frame in range(num_frames):
                loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1)
                skel.setPositions(loaded[0].pos)

                for i in range(skel.getNumBodyNodes()):
                    body_min_height[i] = min(body_min_height[i], skel.getBodyNode(i).getCOM()[1])

            body_last_energy = np.zeros(skel.getNumBodyNodes())

        # Animate the knees back and forth
        ticker: nimble.realtime.Ticker = nimble.realtime.Ticker(
            subject.getTrialTimestep(trial) / playback_speed)

        loop_counter: int = 0

        running_energy_deriv: float = 0.0

        def onTick(now):
            nonlocal loop_counter
            nonlocal loop_frames
            nonlocal skel
            nonlocal subject
            nonlocal dof
            nonlocal dof_poses
            nonlocal dof_vels
            nonlocal dof_accs
            nonlocal dof_taus
            nonlocal timesteps
            nonlocal running_energy_deriv

            if len(loop_frames) == 0:
                frame = loop_counter
            else:
                frame = loop_frames[loop_counter]

            loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1, contactThreshold=20)

            if show_root_frame:
                pos_in_root_frame = np.copy(loaded[0].processingPasses[-1].pos)
                pos_in_root_frame[0:6] = 0
                skel.setPositions(pos_in_root_frame)

                missing_grf = loaded[0].missingGRFReason != nimble.biomechanics.MissingGRFReason.notMissingGRF

                gui.nativeAPI().renderSkeleton(skel, overrideColor=[1,0,0,1] if missing_grf else [0.7,0.7,0.7,1])
                gui.nativeAPI().setTextContents('missing_reason', str(loaded[0].missingGRFReason))

                joint_centers = loaded[0].processingPasses[-1].jointCentersInRootFrame
                num_joints = int(len(joint_centers) / 3)
                for j in range(num_joints):
                    gui.nativeAPI().createSphere('joint_'+str(j), [0.05, 0.05, 0.05], joint_centers[j*3:(j+1)*3], [1,0,0,1])

                root_lin_vel = loaded[0].processingPasses[-1].rootLinearAccInRootFrame
                gui.nativeAPI().createLine('root_lin_vel', [[0,0,0], root_lin_vel], [1,0,0,1])

                root_pos_history = loaded[0].processingPasses[-1].rootPosHistoryInRootFrame
                num_history = int(len(root_pos_history) / 3)
                for h in range(num_history):
                    gui.nativeAPI().createSphere('root_pos_history_'+str(h), [0.05, 0.05, 0.05], root_pos_history[h*3:(h+1)*3], [0,1,0,1])

                force_cops = loaded[0].processingPasses[-1].groundContactCenterOfPressureInRootFrame
                force_fs = loaded[0].processingPasses[-1].groundContactForceInRootFrame
                num_forces = int(len(force_cops) / 3)
                for f in range(num_forces):
                    cop = force_cops[f*3:(f+1)*3]
                    force = force_fs[f*3:(f+1)*3] * 0.001
                    gui.nativeAPI().createLine('force_'+str(f),
                                               [cop,
                                                cop + force],
                                               [1,0,1,1])
            else:
                skel.setPositions(loaded[0].processingPasses[0].pos)
                gui.nativeAPI().renderSkeleton(skel)
                # Render assigned force plates
                for i in range(0, subject.getNumForcePlates(trial)):
                    cop = loaded[0].rawForcePlateCenterOfPressures[i]
                    f = loaded[0].rawForcePlateForces[i] * 0.001
                    color: np.ndarray = np.array([1, 1, 0, 1])
                    gui.nativeAPI().createLine('raw_grf'+str(i), [cop, cop+f], color)

                for i in range(0, len(contact_bodies)):
                    cop = loaded[0].processingPasses[-1].groundContactCenterOfPressure[i*3:(i+1)*3]
                    f = loaded[0].processingPasses[-1].groundContactForce[i*3:(i+1)*3] * 0.001
                    if np.linalg.norm(f) > 0:
                        body_pos = skel.getBodyNode(contact_bodies[i]).getWorldTransform().translation()
                        color: np.ndarray = np.array([0, 0, 0, 1])
                        color[i] = 1.0
                        gui.nativeAPI().createLine('grf'+str(i), [body_pos, cop, cop+f], color)
                    else:
                        gui.nativeAPI().deleteObject('grf'+str(i))
                    # if loaded[0].processingPasses[0].contact[i]:
                    #     for k in range(skel.getBodyNode(contact_bodies[i]).getNumShapeNodes()):
                    #         gui.nativeAPI().setObjectColor('world_'+skel.getName()+"_"+contact_bodies[i]+"_"+str(k), color)
                    # else:
                    #     for k in range(skel.getBodyNode(contact_bodies[i]).getNumShapeNodes()):
                    #         gui.nativeAPI().setObjectColor('world_' + skel.getName() + "_" + contact_bodies[i] + "_" + str(k),
                    #                                        [0.5, 0.5, 0.5, 1])

                if loaded[0].missingGRFReason != nimble.biomechanics.MissingGRFReason.notMissingGRF:
                    for b in range(skel.getNumBodyNodes()):
                        for k in range(skel.getBodyNode(b).getNumShapeNodes()):
                            gui.nativeAPI().setObjectColor('world_' + skel.getName() + "_" + skel.getBodyNode(b).getName() + "_" + str(k),
                                                           [1, 0, 0, 1])
                else:
                    for b in range(skel.getNumBodyNodes()):
                        for k in range(skel.getBodyNode(b).getNumShapeNodes()):
                            gui.nativeAPI().setObjectColor('world_' + skel.getName() + "_" + skel.getBodyNode(b).getName() + "_" + str(k),
                                                           [0.7, 0.7, 0.7, 1])

                gui.nativeAPI().setTextContents('missing_reason', str(loaded[0].missingGRFReason))

                if dof is not None:
                    joint_pos = skel.getJointWorldPositions([graph_joint])
                    gui.nativeAPI().setObjectPosition('active_joint', joint_pos)
                    p = dof_poses[frame]
                    v = dof_vels[frame]
                    a = dof_accs[frame]
                    t = dof_taus[frame]

                    # dof_poses_with_zeros = np.zeros(num_frames)
                    # dof_poses_with_zeros[0:frame] = dof_poses[0:frame]
                    # gui.nativeAPI().setRichPlotData('dof_plot', 'Pose', 'blue', 'line', timesteps, dof_poses_with_zeros)
                    # dof_vels_with_zeros = np.zeros(num_frames)
                    # dof_vels_with_zeros[0:frame] = dof_vels[0:frame]
                    # gui.nativeAPI().setRichPlotData('dof_plot', 'Vel', 'green', 'line', timesteps, dof_vels_with_zeros)
                    # dof_taus_with_zeros = np.zeros(num_frames)
                    # dof_taus_with_zeros[0:frame] = dof_taus[0:frame]
                    # gui.nativeAPI().setRichPlotData('dof_plot', 'Tau', 'red', 'line', timesteps, dof_taus_with_zeros)
                    # # dof_power_with_zeros = np.zeros(num_frames)
                    # # dof_power_with_zeros[0:frame] = dof_power[0:frame]
                    # # gui.nativeAPI().setRichPlotData('dof_plot', 'Power', 'purple', 'line', timesteps, dof_power_with_zeros)
                    # dof_work_with_zeros = np.zeros(num_frames)
                    # dof_work_with_zeros[0:frame] = dof_work[0:frame]
                    # gui.nativeAPI().setRichPlotData('dof_plot', 'Net Work', 'purple', 'line', timesteps, dof_work_with_zeros)

                    gui.nativeAPI().setTextContents('dof_plot_text', 'DOF '+graph_dof+' values<br>Pos: '+str(p)+'<br>Vel: '+str(v)+'<br>Acc: '+str(a)+'<br>Tau: '+str(t)+'<br>Power:'+str(dof_power[frame])+'<br>Work: '+str(dof_work[frame]))

                if show_energy:
                    # Compute and render energy
                    skel.setPositions(loaded[0].pos)
                    skel.setVelocities(loaded[0].vel)
                    skel.setAccelerations(loaded[0].acc)

                    contact_body_pointers = []
                    cops = []
                    forces = []
                    moments = []

                    skel.clearExternalForces()
                    for i in range(0, len(contact_bodies)):
                        cop = loaded[0].groundContactCenterOfPressure[i*3:(i+1)*3]
                        f = loaded[0].groundContactForce[i*3:(i+1)*3]
                        tau = loaded[0].groundContactTorque[i*3:(i+1)*3]

                        local_wrench = np.zeros(6)
                        local_wrench[0:3] = tau
                        local_wrench[3:6] = f
                        global_wrench = nimble.math.dAdInvT(np.eye(3), cop, local_wrench)
                        body = skel.getBodyNode(contact_bodies[i])
                        wrench_local = nimble.math.dAdT(body.getWorldTransform().rotation(), body.getWorldTransform().translation(), global_wrench)
                        body.setExtWrench(wrench_local)

                        contact_body_pointers.append(body)
                        cops.append(cop)
                        forces.append(f)
                        moments.append(tau)
                    skel.computeInverseDynamics(withExternalForces=True)

                    energy = skel.getEnergyAccounting(0.0, contact_body_pointers, cops, forces, moments)

                    power_arrow_scale_factor = 2e-4
                    energy_sphere_scale_factor = 5e-3
                    # power_sphere_scale_factor = 1e-4
                    power_sphere_scale_factor = 3e-4

                    overall_scale = 1.5
                    power_arrow_scale_factor *= overall_scale
                    energy_sphere_scale_factor *= overall_scale
                    power_sphere_scale_factor *= overall_scale

                    body_energy_grad = np.zeros(skel.getNumBodyNodes())
                    body_joint_power_sum = np.zeros(skel.getNumBodyNodes())
                    body_radii = np.zeros(skel.getNumBodyNodes())
                    body_power_sources: List[List[Tuple[str, float]]] = [[] for _ in range(skel.getNumBodyNodes())]
                    for i in range(0, skel.getNumBodyNodes()):
                        body = skel.getBodyNode(i)
                        total_energy = energy.bodyKineticEnergy[i] + body.getMass() * 9.81 * (body.getCOM()[1] - body_min_height[i])
                        radius = energy_sphere_scale_factor * total_energy
                        gui.nativeAPI().createSphere(body.getName()+"_energy", radius * np.ones(3), energy.bodyCenters[i], [0, 0, 1, 0.5])
                        body_radii[i] = radius

                        # Verify energy gradients
                        body_energy_grad[i] = (total_energy - body_last_energy[i]) / subject.getTrialTimestep(trial)
                        body_last_energy[i] = total_energy

                        # body_power_sources[i].append(("Gravity", energy.bodyGravityPower[i]))
                        if energy.bodyExternalForcePower[i] != 0:
                            body_power_sources[i].append(("External", energy.bodyExternalForcePower[i]))
                        body_power_sources[i].append(("Parent Joint", energy.bodyParentJointPower[i]))
                        body_power_sources[i].append(("Child Joint", energy.bodyChildJointPowerSum[i]))
                    for j in range(0, len(energy.joints)):
                        body_joint_power_sum[skel.getBodyNode(energy.joints[j].childBody).getIndexInSkeleton()] += energy.joints[j].powerToChild
                        body_power_sources[skel.getBodyNode(energy.joints[j].childBody).getIndexInSkeleton()].append((energy.joints[j].name, energy.joints[j].powerToChild))
                        if skel.getBodyNode(energy.joints[j].parentBody) is not None:
                            body_joint_power_sum[skel.getBodyNode(energy.joints[j].parentBody).getIndexInSkeleton()] += energy.joints[j].powerToParent
                            body_power_sources[skel.getBodyNode(energy.joints[j].parentBody).getIndexInSkeleton()].append((energy.joints[j].name, energy.joints[j].powerToParent))

                    # body_energy_analytical_grad = energy.bodyKineticEnergyDeriv + energy.bodyPotentialEnergyDeriv
                    # compare = np.zeros((skel.getNumBodyNodes(), 3))
                    # compare[:, 0] = body_energy_grad
                    # compare[:, 1] = body_energy_analytical_grad
                    # compare[:, 2] = body_joint_power_sum
                    # print('FD energy gradient - Joint energy gradient - Joint power sum: ')
                    # for i in range(skel.getNumBodyNodes()):
                    #     if energy.bodyExternalForcePower[i] != 0:
                    #         print(skel.getBodyNode(i).getName()+': '+str(compare[i, :])+', '+str(body_power_sources[i]))
                    running_energy_deriv += np.sum(energy.bodyKineticEnergyDeriv + energy.bodyPotentialEnergyDeriv) * subject.getTrialTimestep(trial)

                    for joint in energy.joints:
                        net_power = joint.powerToChild + joint.powerToParent
                        joint_radius = abs(net_power) * power_sphere_scale_factor

                        child_to_joint_dir = (joint.worldCenter - joint.childCenter) / max(np.linalg.norm(joint.worldCenter - joint.childCenter), 1.0e-7)
                        adjusted_child_center = joint.childCenter + child_to_joint_dir * body_radii[skel.getBodyNode(joint.childBody).getIndexInSkeleton()]
                        adjusted_child_joint_center = joint.worldCenter - child_to_joint_dir * joint_radius

                        parent_to_joint_dir = (joint.worldCenter - joint.parentCenter) / max(np.linalg.norm(joint.worldCenter - joint.parentCenter), 1.0e-7)
                        adjusted_parent_center = np.copy(joint.parentCenter)
                        if skel.getBodyNode(joint.parentBody) is not None:
                             adjusted_parent_center += parent_to_joint_dir * body_radii[skel.getBodyNode(joint.parentBody).getIndexInSkeleton()]
                        adjusted_parent_joint_center = joint.worldCenter - parent_to_joint_dir * joint_radius

                        if joint.powerToChild > 0:
                            gui.nativeAPI().renderArrow(adjusted_child_joint_center, adjusted_child_center, joint.powerToChild * power_arrow_scale_factor * 0.5, joint.powerToChild * power_arrow_scale_factor, color=[0,0,1,0.5], prefix=joint.name+'_child')
                        else:
                            gui.nativeAPI().renderArrow(adjusted_child_center, adjusted_child_joint_center, -joint.powerToChild * power_arrow_scale_factor * 0.5, -joint.powerToChild * power_arrow_scale_factor, color=[0,0,1,0.5], prefix=joint.name+'_child')
                        if joint.powerToParent > 0:
                            gui.nativeAPI().renderArrow(adjusted_parent_joint_center, adjusted_parent_center, joint.powerToParent * power_arrow_scale_factor * 0.5, joint.powerToParent * power_arrow_scale_factor, color=[0,0,1,0.5], prefix=joint.name+'_parent')
                        else:
                            gui.nativeAPI().renderArrow(adjusted_parent_center, adjusted_parent_joint_center, -joint.powerToParent * power_arrow_scale_factor * 0.5, -joint.powerToParent * power_arrow_scale_factor, color=[0,0,1,0.5], prefix=joint.name+'_parent')

                        if net_power < 0:
                            gui.nativeAPI().createSphere('energy_'+joint.name, np.ones(3) * -net_power * power_sphere_scale_factor, joint.worldCenter, [1, 0, 0, 1])
                        else:
                            gui.nativeAPI().createSphere('energy_'+joint.name, np.ones(3) * net_power * power_sphere_scale_factor, joint.worldCenter, [0, 1, 0, 1])

                    for contact in energy.contacts:
                        if contact.powerToBody > 0:
                            gui.nativeAPI().renderArrow(contact.worldCenter - np.array([0, 0.2, 0]), contact.worldCenter, contact.powerToBody * power_arrow_scale_factor * 0.5, contact.powerToBody * power_arrow_scale_factor, color=[0,0,1,0.5], prefix=contact.contactBody+'_contact')
                        else:
                            gui.nativeAPI().renderArrow(contact.worldCenter, contact.worldCenter - np.array([0, 0.2, 0]), -contact.powerToBody * power_arrow_scale_factor * 0.5, -contact.powerToBody * power_arrow_scale_factor, color=[0,0,1,0.5], prefix=contact.contactBody+'_contact')
                        if contact.powerToBody < 0:
                            gui.nativeAPI().createSphere('energy_'+contact.contactBody, np.ones(3) * -contact.powerToBody * power_sphere_scale_factor, contact.worldCenter, [1, 0, 0, 1])
                        else:
                            gui.nativeAPI().createSphere('energy_'+contact.contactBody, np.ones(3) * contact.powerToBody * power_sphere_scale_factor, contact.worldCenter, [0, 1, 0, 1])

                    # for i in range(len(skel.getNumBodyNodes())):
                    #     body = skel.getBodyNode(i)
                    #     body_force = body.getBodyForce()
                    #     tau = body.getParentJoint().getRelativeJacobianStatic().transpose() @ body_force
                    #     reprojected_force = body.getParentJoint().getRelativeJacobianStatic() @ tau
                    #     joint_force =  body_force - reprojected_force
                    #     V = body.getSpatialVelocity(offset, relativeTo=Frame::World(), inCoordinatesOf)

            loop_counter += 1
            loop_number = num_frames
            if len(loop_frames) > 0:
                loop_number = len(loop_frames)
            if loop_counter >= loop_number:
                loop_counter = 0

        # ticker.registerTickListener(onTick)
        # ticker.start()
        while True:
            onTick(time.time())
            time.sleep(0.01)

        print(subject.getHref())
        print(subject.getTrialName(trial))

        # Don't immediately exit while we're serving
        gui.blockWhileServing()
        return True
