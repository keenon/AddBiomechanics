from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
import tempfile
from typing import List, Dict, Tuple
import itertools


class TransferReviewsCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        parser = subparsers.add_parser(
            'transfer-reviews', help='This command will read a SubjectOnDisk binary file, or a folder full of them, '
                                     'do some processing (e.g. lowpass filter the values and/or standardize the sample '
                                     'rates), and then write out the result to a new binary file or folder with the '
                                     'same relative paths.')
        parser.add_argument('review_folder', type=str)

    def run_local(self, args: argparse.Namespace) -> bool:
        if args.command != 'transfer-reviews':
            return False

        review_folder: str = args.review_folder

        import numpy as np

        npy_dict: Dict[str, np.ndarray] = {}
        for dirpath, dirnames, filenames in os.walk(review_folder):
            for file in filenames:
                if file.endswith('.npy'):
                    relative_path = os.path.relpath(os.path.join(dirpath, file), review_folder)
                    npy_dict[relative_path] = np.load(os.path.join(dirpath, file))

        print(npy_dict)

        return True
