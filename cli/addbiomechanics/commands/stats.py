import time

from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from typing import List, Dict, Tuple

class StatsCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        view_parser = subparsers.add_parser(
            'stats', help='Prints the statistics for a *.b3d file (or set of *.b3d files) from AddBiomechanics')

        view_parser.add_argument(
            'file_path', help='The name of the file to view')

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'stats':
            return False
        file_path: str = args.file_path

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

        # 5. Read the file back in, and print out some summary stats
        print('B3D Summary Statistics:', flush=True)
        read_back: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(file_path)
        print('  Num Trials: ' + str(read_back.getNumTrials()), flush=True)
        print('  Num Processing Passes: ' + str(read_back.getNumProcessingPasses()), flush=True)
        print('  Num Dofs: ' + str(read_back.getNumDofs()), flush=True)
        for t in range(read_back.getNumTrials()):
            print('  Trial '+str(t)+':', flush=True)
            print('    Name: ' + read_back.getTrialName(t), flush=True)
            missing_grf_reason = read_back.getMissingGRF(t)
            num_have_grf = len([r for r in missing_grf_reason if r == nimble.biomechanics.MissingGRFReason.notMissingGRF])
            print('    Num have GRF frames: ' + str(num_have_grf), flush=True)
            print('    Num missing GRF frames: ' + str(len([r for r in missing_grf_reason if r != nimble.biomechanics.MissingGRFReason.notMissingGRF])), flush=True)
            for p in range(read_back.getTrialNumProcessingPasses(t)):
                print('    Processing pass '+str(p)+':', flush=True)
                print('      Marker RMS: ' + str(np.mean(read_back.getTrialMarkerRMSs(t, p))), flush=True)
                print('      Marker Max: ' + str(np.mean(read_back.getTrialMarkerMaxs(t, p))), flush=True)
                if num_have_grf > 0:
                    linear_residuals = read_back.getTrialLinearResidualNorms(t, p)
                    angular_residuals = read_back.getTrialAngularResidualNorms(t, p)
                    for j in range(len(linear_residuals)):
                        if missing_grf_reason[j] != nimble.biomechanics.MissingGRFReason.notMissingGRF:
                            linear_residuals[j] = 0.0
                            angular_residuals[j] = 0.0

                    non_zero_linear_residuals = [r for r in linear_residuals if r > 0.0]
                    if len(non_zero_linear_residuals) > 0:
                        print('      Linear Residual (on frames with GRF): ' + str(np.mean(non_zero_linear_residuals)), flush=True)
                    else:
                        print('      Linear Residual (on frames with GRF): 0.0', flush=True)

                    non_zero_angular_residuals = [r for r in angular_residuals if r > 0.0]
                    if len(non_zero_angular_residuals) > 0:
                        print('      Angular Residual (on frames with GRF): ' + str(np.mean(non_zero_angular_residuals)), flush=True)
                    else:
                        print('      Angular Residual (on frames with GRF): 0.0', flush=True)
