import time

from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from typing import List, Dict, Tuple

class CompareCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        view_parser = subparsers.add_parser(
            'compare', help='Compare two *.b3d files from AddBiomechanics')

        view_parser.add_argument(
            'file_path_one', help='The name of the first file to view')
        view_parser.add_argument(
            'file_path_two', help='The name of the first file to view')
        view_parser.add_argument(
            '--trial', help='The number of the trial to view (default: 0)', default=0, type=int)
        view_parser.add_argument(
            '--geometry',
            help='The path to the Geometry folder to use when loading OpenSim skeletons',
            type=str,
            default=None)
        view_parser.add_argument('--show-markers',
                                 help='Show the markers',
                                 action='store_true')
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
            '--playback-speed',
            help='A number representing the fraction of realtime to play back the data at. Default is 1.0, for '
                 'realtime playback.',
            type=float,
            default=1.0)
        view_parser.add_argument('--loop-frames', type=int, nargs='+', default=[],
                               help='Specific frames to loop over.')

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'compare':
            return False
        file_path_one: str = args.file_path_one
        file_path_two: str = args.file_path_two
        trial: int = args.trial
        graph_dof: str = args.graph_dof
        graph_lowpass_hz: int = args.graph_lowpass_hz
        playback_speed: float = args.playback_speed

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

        print('Reading first SubjectOnDisk at '+file_path_one+'...')
        subject_one: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(file_path_one)
        print('Subject 1 height: '+str(subject_one.getHeightM())+"m")
        print('Subject 1 mass: '+str(subject_one.getMassKg())+"kg")
        print('Subject 1 biological sex: '+subject_one.getBiologicalSex())

        subject_two: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(file_path_two)
        print('Subject 1 height: '+str(subject_two.getHeightM())+"m")
        print('Subject 1 mass: '+str(subject_two.getMassKg())+"kg")
        print('Subject 1 biological sex: '+subject_two.getBiologicalSex())

        num_frames = subject_one.getTrialLength(trial)

        osim_one: nimble.biomechanics.OpenSimFile = subject_one.readOpenSimFile(0, geometry)
        skel_one = osim_one.skeleton
        osim_two: nimble.biomechanics.OpenSimFile = subject_two.readOpenSimFile(0, geometry)
        skel_two = osim_two.skeleton

        print('DOFs:')
        for i in range(skel_one.getNumDofs()):
            print(' ['+str(i)+']: '+skel_one.getDofByIndex(i).getName())

        gui = NimbleGUI()
        gui.serve(8080)

        gui.nativeAPI().createText('missing_reason', '', [100, 50], [200, 50])

        if graph_dof is not None:
            dof = skel_one.getDof(graph_dof)
            if dof is None:
                print('ERROR: DOF to graph "'+graph_dof+'" not found')
                return False
            graph_joint_one = skel_one.getJoint(dof.getJointName())
            joint_one_pos = skel_one.getJointWorldPositions([graph_joint_one])
            gui.nativeAPI().createSphere('active_joint_one', [0.05, 0.05, 0.05], joint_one_pos, [1,0,0,1])

            graph_joint_two = skel_one.getJoint(dof.getJointName())
            joint_two_pos = skel_one.getJointWorldPositions([graph_joint_two])
            gui.nativeAPI().createSphere('active_joint_one', [0.05, 0.05, 0.05], joint_two_pos, [0,0,1,1])

            dof_index = dof.getIndexInSkeleton()

            timesteps = np.zeros(num_frames)
            dof_poses_one = np.zeros(num_frames)
            dof_poses_two = np.zeros(num_frames)

            for frame in range(num_frames):
                timesteps[frame] = frame * subject_one.getTrialTimestep(trial)

                loaded_one: List[nimble.biomechanics.Frame] = subject_one.readFrames(trial, frame, 1, False, True)
                dof_poses_one[frame] = loaded_one[0].processingPasses[-1].pos[dof_index]

                loaded_two: List[nimble.biomechanics.Frame] = subject_two.readFrames(trial, frame, 1, False, True)
                dof_poses_one[frame] = loaded_two[0].processingPasses[-1].pos[dof_index]

            # Filter down to "--graph-lowpass-hz" Hz
            if graph_lowpass_hz is not None:
                fs = 1/subject_one.getTrialTimestep(trial)
                nyquist = fs / 2
                if graph_lowpass_hz < nyquist:
                    print('Filtering to '+str(graph_lowpass_hz)+' Hz...')
                    b, a = butter(2, graph_lowpass_hz, 'low', fs=fs)
                    dof_poses_one = filtfilt(b, a, dof_poses_one)
                    dof_poses_two = filtfilt(b, a, dof_poses_two)
                else:
                    print('WARNING: Cannot filter to '+str(graph_lowpass_hz)+' Hz because it is greater than the '+
                          'Nyquist frequency of '+str(nyquist)+' Hz. Not filtering.')

            max_over_all = np.max(np.concatenate((dof_poses_one, dof_poses_two)))
            min_over_all = np.min(np.concatenate((dof_poses_one, dof_poses_two)))

            gui.nativeAPI().createRichPlot('dof_plot', [50, 100], [400, 200], 0, subject_one.getTrialLength(trial) * subject_one.getTrialTimestep(trial), min_over_all, max_over_all, 'DOF '+graph_dof, 'Time (s)', 'Values')

            gui.nativeAPI().setRichPlotData('dof_plot', 'Pose 1', 'blue', 'line', timesteps, dof_poses_one)
            gui.nativeAPI().setRichPlotData('dof_plot', 'Pose 2', 'red', 'line', timesteps, dof_poses_two)
            gui.nativeAPI().createText('dof_plot_text', 'DOF '+graph_dof+' values', [50, 350], [400, 50])
        else:
            dof = None

        # Animate the knees back and forth
        ticker: nimble.realtime.Ticker = nimble.realtime.Ticker(
            subject_one.getTrialTimestep(trial) / playback_speed)

        loop_counter: int = 0

        def onTick(now):
            nonlocal loop_counter
            nonlocal skel_one
            nonlocal subject_one
            nonlocal skel_two
            nonlocal subject_two
            nonlocal dof
            nonlocal dof_poses_one
            nonlocal dof_poses_two
            nonlocal timesteps
            # nonlocal marker_map
            # nonlocal show_markers

            frame = loop_counter

            loaded_one: List[nimble.biomechanics.Frame] = subject_one.readFrames(trial, frame, 1, contactThreshold=20)
            skel_one.setPositions(loaded_one[0].processingPasses[-1].pos)
            gui.nativeAPI().renderSkeleton(skel_one, prefix='one_')

            loaded_two: List[nimble.biomechanics.Frame] = subject_two.readFrames(trial, frame, 1, contactThreshold=20)
            skel_two.setPositions(loaded_two[0].processingPasses[-1].pos)
            gui.nativeAPI().renderSkeleton(skel_two, prefix='two_', overrideColor=[1, 0, 0, 1])

            loop_counter += 1
            loop_number = num_frames
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
