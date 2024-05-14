from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure
from typing import List, Dict


class LsCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        ls_parser = subparsers.add_parser(
            'ls', help='List the datasets uploaded to AddBiomechanics')
        ls_parser.add_argument(
            '--grf-only', action='store_true', help='Only show datasets that contain GRF data')

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'ls':
            return

        grf_only: bool = args.grf_only

        root: S3Node = retrieve_s3_structure(ctx, s3_prefix='standardized/')
        root.debug(grf_only=grf_only)
