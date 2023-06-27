from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure


class LsCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        ls_parser = subparsers.add_parser(
            'ls', help='List the datasets uploaded to AddBiomechanics')
        ls_parser.add_argument('--grf-only', type=bool, default=False, help="Only list datasets that include GRF data")
        ls_parser.add_argument('--filter-age', type=lambda d: datetime.strptime(d, '%Y-%m-%d'),
                                     help='Only get data created after this date. The date in the format YYYY-MM-DD', default=None)

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'ls':
            return

        grf_only: bool = args.grf_only
        filter_age: datetime = args.filter_age

        root: S3Node = retrieve_s3_structure(ctx)
        root.debug(grf_only=grf_only)
