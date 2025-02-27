from addbiomechanics.commands.abstract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from typing import List, Dict, Tuple, Set, Optional
import json
import re


class DownloadFilesCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        download_parser = subparsers.add_parser(
            'download-files', help='Download raw files from AddBiomechanics')
        download_parser.add_argument('--pattern',
                                     type=str,
                                     default='.*_dynamics_trials_only\.b3d',
                                     help='The regex to match files to be downloaded.')
        download_parser.add_argument('--prefix',
                                     type=str,
                                     default='standardized/rajagopal_no_arms',
                                     help='The folder prefix to match when listing potential files to download.')

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'download-files':
            return
        pattern: Optional[str] = args.pattern
        prefix: str = args.prefix

        # Compile the pattern as a regex
        regex = re.compile(pattern) if pattern is not None else None

        s3 = ctx.aws_session.client('s3')

        response = s3.list_objects_v2(
            Bucket=ctx.deployment['BUCKET'], Prefix=prefix)

        files: List[Tuple[str, int, str]] = []
        keys: List[str] = []
        total_unfiltered_files: int = 0

        print(f'Listing files on S3 at {prefix}...')
        while True:
            if 'Contents' in response:
                for obj in response['Contents']:
                    key: str = obj['Key']
                    if regex.match(key):
                        size: int = obj['Size']
                        e_tag: str = obj['ETag']
                        files.append((key, size, e_tag))
                        keys.append(key)

                        print(f'Downloading {key}')
                        if os.path.exists(key):
                            print('File already exists, skipping')
                            continue
                        # os.path.dirname gets the directory portion from the full path
                        directory = os.path.dirname(key)
                        # Create the directory structure, if it doesn't exist already
                        os.makedirs(directory, exist_ok=True)
                        # Check the size of the file, and if it's 0, create an empty file
                        if size == 0:
                            # Create an empty file
                            open(key, 'a').close()
                        else:
                            try:
                                s3.download_file(ctx.deployment['BUCKET'], key, key)
                            except Exception as e:
                                print(
                                    'Caught an exception trying to download. Trying refreshing AWS session and trying again.')
                                print(e)
                                ctx.refresh()
                                s3 = ctx.aws_session.client('s3')
                                # Retry the download operation
                                s3.download_file(ctx.deployment['BUCKET'], key, key)
                    total_unfiltered_files += 1

            # Check if there are more objects to retrieve
            if response['IsTruncated']:
                print(f'Have {len(files)}/{total_unfiltered_files} matches so far. Listing next page of files to download at {prefix}...')
                continuation_token = response['NextContinuationToken']
                response = s3.list_objects_v2(
                    Bucket=ctx.deployment['BUCKET'], Prefix=prefix, ContinuationToken=continuation_token, MaxKeys=10000)
            else:
                print(f'Finished listing files to download at {prefix}. Found {len(files)} files.')
                break

        print(f'Found {len(files)} files to download.')

        # for i, key in enumerate(keys):
        #     print(f'Downloading {i+1}/{len(keys)}: {key}')
        #     if os.path.exists(key):
        #         print('File already exists, skipping')
        #         continue
        #     # os.path.dirname gets the directory portion from the full path
        #     directory = os.path.dirname(key)
        #     # Create the directory structure, if it doesn't exist already
        #     os.makedirs(directory, exist_ok=True)
        #     # Check the size of the file, and if it's 0, create an empty file
        #     if files[i][1] == 0:
        #         # Create an empty file
        #         open(key, 'a').close()
        #     else:
        #         try:
        #             s3.download_file(ctx.deployment['BUCKET'], key, key)
        #         except Exception as e:
        #             print('Caught an exception trying to download. Trying refreshing AWS session and trying again.')
        #             print(e)
        #             ctx.refresh()
        #             s3 = ctx.aws_session.client('s3')
        #             # Retry the download operation
        #             s3.download_file(ctx.deployment['BUCKET'], key, key)
