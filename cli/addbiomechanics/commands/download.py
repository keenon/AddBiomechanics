from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from typing import List


class DownloadCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        download_parser = subparsers.add_parser(
            'download', help='Download a dataset from AddBiomechanics')
        download_parser.add_argument(
            'output_path', type=str, help='The folder to download to')
        download_parser.add_argument(
            '--path-substring', type=str, help='A substring of the path of the files you want. This could be as simple as a subject name')
        download_parser.add_argument('--grf-only', type=bool, default=False, help="Only list datasets that include GRF data")
        download_parser.add_argument('--filter-age', type=lambda d: datetime.strptime(d, '%Y-%m-%d'),
                            help='Only get data created after this date. The date in the format YYYY-MM-DD', default=None)

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'download':
            return

        output_path: str = args.output_path
        path_substring: str = args.path_substring
        grf_only: bool = args.grf_only
        filter_age: datetime = args.filter_age

        root: S3Node = retrieve_s3_structure(ctx)

        binaryFiles: List[S3Node] = root.get_download_list(path_substring, grf_only=grf_only)
        prefix = os.path.commonpath([node.get_path() for node in binaryFiles])
        if not prefix.endswith('/') and len(prefix) > 0:
            prefix += '/'
        totalSize = 0

        print('We are about to download the following files:')
        print('Prefix is '+prefix)
        for node in binaryFiles:
            path = node.get_path()
            if prefix != path:
                path = path[len(prefix):]
            print(f' > [{prefix}] {path} ({sizeof_fmt(node.size)})')
            totalSize += node.size
        print('Total size is {}'.format(sizeof_fmt(totalSize)))
        print('Is that ok?')
        confired = input('y/n: ') == 'y'
        if not confired:
            print('Aborting')
            return

        s3 = ctx.aws_session.client('s3')

        if not output_path.endswith('/'):
            output_path += '/'
        for i, node in enumerate(binaryFiles):
            full_path: str = node.get_path()
            file: str = full_path[len(prefix):]
            size: int = node.size
            dest_path = output_path+file
            print('Downloading '+str(i+1)+'/'+str(len(binaryFiles)) +
                  ' '+file+' ('+sizeof_fmt(size)+')')
            directory = os.path.dirname(dest_path)
            if not os.path.exists(directory):
                os.makedirs(directory)
            s3.download_file(ctx.deployment['BUCKET'], full_path, dest_path)
