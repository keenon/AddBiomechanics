from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from typing import List, Dict

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

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'view':
            return False
        file_path: str = args.file_path
        trial: int = args.trial
        graph_dof: str = args.graph_dof
        graph_lowpass_hz: int = args.graph_lowpass_hz

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
        skel = subject.readSkel(geometry)

        print('DOFs:')
        for i in range(skel.getNumDofs()):
            print(' ['+str(i)+']: '+skel.getDofByIndex(i).getName())

        world = nimble.simulation.World()
        world.addSkeleton(skel)

        gui = NimbleGUI(world)
        gui.serve(8080)

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

            gui.nativeAPI().createRichPlot('dof_plot', [50, 100], [400, 200], 0, subject.getTrialLength(trial) * subject.getTrialTimestep(trial), min_over_all, max_over_all, 'DOF '+graph_dof, 'Time (s)', 'Values')

            gui.nativeAPI().setRichPlotData('dof_plot', 'Pose', 'blue', 'line', timesteps, dof_poses)
            gui.nativeAPI().setRichPlotData('dof_plot', 'Vel', 'green', 'line', timesteps, dof_vels)
            gui.nativeAPI().setRichPlotData('dof_plot', 'Tau', 'red', 'line', timesteps, dof_taus)
            # gui.nativeAPI().setRichPlotData('dof_plot', 'Power', 'purple', 'line', timesteps, dof_power)
            gui.nativeAPI().setRichPlotData('dof_plot', 'Net Work', 'purple', 'line', timesteps, dof_work)

            gui.nativeAPI().createText('dof_plot_text', 'DOF '+graph_dof+' values', [50, 350], [400, 50])
        else:
            dof = None

        # Animate the knees back and forth
        ticker: nimble.realtime.Ticker = nimble.realtime.Ticker(
            subject.getTrialTimestep(trial))

        frame: int = 0

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

            loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1)
            skel.setPositions(loaded[0].pos)
            for i in range(0, len(contact_bodies)):
                cop = loaded[0].groundContactCenterOfPressure[i*3:(i+1)*3]
                f = loaded[0].groundContactForce[i*3:(i+1)*3] * 0.001
                gui.nativeAPI().createLine('grf'+str(i), [cop, cop+f], [1, 0, 0, 1])
            gui.nativeAPI().renderSkeleton(skel)
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

            frame += 1
            if frame >= num_frames:
                frame = 0

        ticker.registerTickListener(onTick)
        ticker.start()

        # Don't immediately exit while we're serving
        gui.blockWhileServing()
        return True
