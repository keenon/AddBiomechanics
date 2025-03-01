from addbiomechanics.commands.abstract_command import AbstractCommand
import argparse
import os
from typing import List, Dict, Optional


class CreateB3DCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        parser = subparsers.add_parser(
            'create-b3d', help='This command will read an OpenSim file and a motion, and create a simple B3D file.')
        parser.add_argument('output_path', type=str)
        parser.add_argument('--opensim-path', type=str, default=None)
        parser.add_argument(
            '--poses-mot-path',
            help='This is the path to a MOT file containing the skeleton poses over time.',
            type=str,
            default=None)
        parser.add_argument(
            '--joint-poses-csv-path',
            help='This is the path to a CSV file containing the skeleton joint poses over time, which can be used to '
                 'override the MOT file.',
            type=str,
            default=None)

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'create-b3d':
            return False
        
        output_path: str = args.output_path
        output_path = os.path.abspath(output_path)
        opensim_path: str = args.opensim_path
        opensim_path = os.path.abspath(opensim_path)
        poses_mot_path: Optional[str] = args.poses_mot_path
        if poses_mot_path is not None:
            poses_mot_path = os.path.abspath(poses_mot_path)
        joint_poses_csv_path: Optional[str] = args.joint_poses_csv_path
        if joint_poses_csv_path is not None:
            joint_poses_csv_path = os.path.abspath(joint_poses_csv_path)

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
        try:
            import pandas as pd
        except ImportError:
            print("The required library 'pandas' is not installed. Please install it and try this command again.")
            return True

        # Create an empty subject, which we will fill in with data
        subject: nimble.biomechanics.SubjectOnDiskHeader = nimble.biomechanics.SubjectOnDiskHeader()
        subject_pass: nimble.biomechanics.SubjectOnDiskPassHeader = subject.addProcessingPass()
        subject_pass.setProcessingPassType(nimble.biomechanics.ProcessingPassType.KINEMATICS)

        if not os.path.exists(opensim_path):
            print('The provided OpenSim file does not exist.')
            return True
        with open(opensim_path, 'r') as f:
            file_contents: str = f.read()
            subject_pass.setOpenSimFileText(file_contents)

        trial: nimble.biomechanics.SubjectOnDiskTrial = subject.addTrial()
        trial_pass: nimble.biomechanics.SubjectOnDiskTrialPass = trial.addPass()
        trial_pass.setType(nimble.biomechanics.ProcessingPassType.KINEMATICS)

        parsed_opensim: nimble.biomechanics.OpenSimFile = nimble.biomechanics.OpenSimParser.parseOsim(opensim_path)
        skeleton: nimble.dynamics.Skeleton = parsed_opensim.skeleton
        subject.setNumDofs(skeleton.getNumDofs())
        subject.setNumJoints(skeleton.getNumJoints())

        if not os.path.exists(poses_mot_path):
            print('The provided poses MOT file does not exist.')
            return True
        with open(poses_mot_path, 'r') as f:
            mot: nimble.biomechanics.OpenSimMot = nimble.biomechanics.OpenSimParser.loadMot(skeleton, poses_mot_path)
            poses: np.ndarray = np.copy(mot.poses)

        if not os.path.exists(joint_poses_csv_path):
            print('The provided joint poses CSV file does not exist. Skipping.')
        else:
            with open(joint_poses_csv_path, 'r') as f:
                # Parse with pandas
                df: pd.DataFrame = pd.read_csv(f)
                # Convert to numpy array
                joint_poses: np.ndarray = df.to_numpy()
                # Get column names
                column_names: List[str] = list(df.columns)
                dof_indices: List[int] = []
                for name in column_names:
                    parts = name.split('_')
                    index = int(parts[-1])
                    joint_name = '_'.join(parts[:-2])
                    dof_index: int = skeleton.getJoint(joint_name).getIndexInSkeleton(index)
                    dof_indices.append(dof_index)
                print(dof_indices)
                print(poses.shape)
                # Overwrite the MOT poses with the joint poses
                poses[dof_indices, :] = joint_poses.transpose()

        poses = poses[:, :5000]
        for t in range(1, poses.shape[1]):
            poses[:, t] = skeleton.unwrapPositionToNearest(poses[:, t], poses[:, t - 1])

        fs = int(1.0 / (mot.timestamps[1] - mot.timestamps[0]))
        nyq = 0.5 * fs
        normal_cutoff = 5.0 / nyq
        b, a = butter(3, normal_cutoff, btype='low', analog=False)
        poses = filtfilt(b, a, poses, axis=1, padtype='constant')

        timesteps: int = poses.shape[1]
        markers: List[Dict[str, np.ndarray]] = [{} for _ in range(timesteps)]
        trial.setMarkerObservations(markers)
        trial.setTimestep(mot.timestamps[1] - mot.timestamps[0])
        print('Timestep: ' + str(mot.timestamps[1] - mot.timestamps[0]))
        trial_pass.setPoses(poses)
        trial_pass.computeValues(
            skeleton,
            mot.timestamps[1] - mot.timestamps[0],
            poses,
            [],
            np.zeros((0, timesteps)),
            np.zeros((0, timesteps)),
            np.zeros((0, timesteps)),
            rootHistoryLen=10,
            rootHistoryStride=3)

        # os.path.dirname gets the directory portion from the full path
        directory = os.path.dirname(output_path)
        # Create the directory structure, if it doesn't exist already
        os.makedirs(directory, exist_ok=True)
        # Now write the output back out to the new SubjectOnDisk file
        print('Writing SubjectOnDisk to {}...'.format(output_path))
        nimble.biomechanics.SubjectOnDisk.writeB3D(output_path, subject)

        return True
