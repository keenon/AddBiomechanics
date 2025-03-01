import time

from addbiomechanics.commands.abstract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from typing import List, Dict, Tuple


class DebugCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        plot_parser = subparsers.add_parser(
            'debug', help='Print debug values from a binary *.b3d file from AddBiomechanics')

        plot_parser.add_argument(
            'file_path', help='The name of the file to view')
        plot_parser.add_argument(
            '--trial', help='The number of the trial to view (default: 0)', default=0, type=int)

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'debug':
            return False
        file_path: str = args.file_path
        trial: int = args.trial

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

        num_frames = subject.getTrialLength(trial)
        osim: nimble.biomechanics.OpenSimFile = subject.readOpenSimFile(0, ignoreGeometry=True)
        skel = osim.skeleton
        marker_map = osim.markersMap

        print('DOFs:')
        num_dofs = skel.getNumDofs()
        for i in range(num_dofs):
            print(' ['+str(i)+']: '+skel.getDofByIndex(i).getName())

        print('Missing frames:')
        for frame in range(num_frames):
            loaded: List[nimble.biomechanics.Frame] = subject.readFrames(trial, frame, 1, True, True)
            print(str(frame) + ': ' + str(loaded[0].missingGRFReason))

        return True
