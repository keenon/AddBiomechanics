import time

from addbiomechanics.commands.abstract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from typing import List, Dict, Tuple


class PlotCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        plot_parser = subparsers.add_parser(
            'plot', help='Plot values from a binary *.bin file from AddBiomechanics')

        plot_parser.add_argument(
            'file_path', help='The name of the file to view')
        plot_parser.add_argument(
            '--trial', help='The number of the trial to view (default: 0)', default=0, type=int)
        plot_parser.add_argument(
            '--trial-pass', help='The number of the processing pass to view (default: -1)', default=-1, type=int)
        plot_parser.add_argument(
            '--graph-dof',
            help='The name of a DOF to highlight and to graph',
            type=str,
            default=None)

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'plot':
            return False
        file_path: str = args.file_path
        trial: int = args.trial
        trial_pass: int = args.trial_pass
        graph_dof: str = args.graph_dof

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

        print('Reading SubjectOnDisk at '+file_path+'...')
        subject: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(file_path)
        print('Subject height: '+str(subject.getHeightM())+"m")
        print('Subject mass: '+str(subject.getMassKg())+"kg")
        print('Subject biological sex: '+subject.getBiologicalSex())
        contact_bodies = subject.getGroundForceBodies()
        print('Contact bodies: '+str(contact_bodies))

        print('Marker RMS: '+str(np.mean(subject.getTrialMarkerRMSs(trial, trial_pass))))
        print('Marker Max: '+str(np.mean(subject.getTrialMarkerMaxs(trial, trial_pass))))
        print('Linear residuals: '+str(np.mean(subject.getTrialLinearResidualNorms(trial, trial_pass))))
        print('Angular residuals: '+str(np.mean(subject.getTrialAngularResidualNorms(trial, trial_pass))))

        num_frames = subject.getTrialLength(trial)
        osim: nimble.biomechanics.OpenSimFile = subject.readOpenSimFile(0, ignoreGeometry=True)
        skel = osim.skeleton
        marker_map = osim.markersMap

        print('DOFs:')
        num_dofs = skel.getNumDofs()
        for i in range(num_dofs):
            print(' ['+str(i)+']: '+skel.getDofByIndex(i).getName())

        dof = skel.getDof(graph_dof)
        if dof is None:
            print('ERROR: DOF to graph "'+graph_dof+'" not found')
            return False

        dof_index = dof.getIndexInSkeleton()
        timesteps = np.zeros(num_frames)
        dof_poses = np.zeros(num_frames)
        dof_vels = np.zeros(num_frames)
        dof_accs = np.zeros(num_frames)
        dof_taus = np.zeros(num_frames)
        dof_power = np.zeros(num_frames)
        grfs = [np.zeros(num_frames) for _ in range(subject.getNumForcePlates(trial))]
        grms = [np.zeros(num_frames) for _ in range(subject.getNumForcePlates(trial))]
        grcops = [np.zeros(num_frames) for _ in range(subject.getNumForcePlates(trial))]
        all_accs = np.zeros((num_dofs, num_frames))
        for frame in range(num_frames):
            timesteps[frame] = frame * subject.getTrialTimestep(trial)
            loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1, True, True)
            processing_pass = loaded[0].processingPasses[trial_pass]
            p = processing_pass.pos[dof_index]
            v = processing_pass.vel[dof_index]
            a = processing_pass.acc[dof_index]
            t = processing_pass.tau[dof_index]
            dof_poses[frame] = p
            dof_vels[frame] = v
            dof_accs[frame] = a
            all_accs[:, frame] = processing_pass.acc
            dof_taus[frame] = t
            dof_power[frame] = v*t
            forces = loaded[0].rawForcePlateForces
            moments = loaded[0].rawForcePlateTorques
            cops = loaded[0].rawForcePlateCenterOfPressures
            for i in range(len(grfs)):
                grfs[i][frame] = np.linalg.norm(forces[i])
                grms[i][frame] = np.linalg.norm(moments[i])
                grcops[i][frame] = np.linalg.norm(cops[i])

        import matplotlib.pyplot as plt
        fig, axs = plt.subplots(3, 2)
        fig.suptitle('DOF: '+graph_dof)
        axs[0, 0].plot(timesteps, dof_poses)
        axs[0, 0].set_title('Position')
        axs[0, 0].set(xlabel='Time (s)', ylabel='Position (rad)')
        axs[0, 1].plot(timesteps, dof_vels)
        axs[0, 1].set_title('Velocity')
        axs[0, 1].set(xlabel='Time (s)', ylabel='Velocity (rad/s)')
        axs[1, 0].plot(timesteps, dof_accs)
        axs[1, 0].set_title('Acceleration')
        axs[1, 0].set(xlabel='Time (s)', ylabel='Acceleration (rad/s^2)')
        axs[1, 1].plot(timesteps, dof_taus)
        # for i in range(len(grfs)):
        #     axs[1, 1].plot(timesteps, grfs[i], label='Force Plate '+str(i))
        #     axs[1, 1].plot(timesteps, grms[i], label='Moment Plate '+str(i))
        #     axs[1, 1].plot(timesteps, grcops[i], label='COP Plate '+str(i))
        axs[1, 1].set_title('Torque')
        axs[1, 1].set(xlabel='Time (s)', ylabel='Torque (Nm)')
        axs[1, 1].legend()
        axs[2, 0].plot(timesteps, dof_power)
        axs[2, 0].set_title('Power')
        axs[2, 0].set(xlabel='Time (s)', ylabel='Power (W)')
        for i in range(num_dofs):
            axs[2, 1].plot(timesteps, all_accs[i, :], label=skel.getDofByIndex(i).getName())
        axs[2, 1].set_title('All Accelerations')
        axs[2, 1].set(xlabel='Time (s)', ylabel='Acceleration (rad/s^2)')
        axs[2, 1].legend()
        plt.show()

        return True
