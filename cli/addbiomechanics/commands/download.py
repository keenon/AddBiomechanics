from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from typing import List, Dict
import re


class DownloadCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        download_parser = subparsers.add_parser(
            'download', help='Download a dataset from AddBiomechanics')
        download_parser.add_argument('pattern', type=str,
                                     help='The regex to match files to be downloaded.')

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'download':
            return
        pattern: str = args.pattern
        # Compile the pattern as a regex
        regex = re.compile(pattern)

        s3 = ctx.aws_session.client('s3')

        response = s3.list_objects_v2(
            Bucket=ctx.deployment['BUCKET'], Prefix='standardized/')

        to_download: List[str] = []
        to_download_e_tags: List[str] = []
        to_download_size: int = 0
        already_downloaded: List[str] = []
        already_downloaded_size: int = 0

        while True:
            if 'Contents' in response:
                for obj in response['Contents']:
                    key: str = obj['Key']
                    size: int = obj['Size']
                    e_tag: str = obj['ETag']
                    if regex.match(key):
                        if e_tag in to_download_e_tags:
                            continue
                        if os.path.exists(key):
                            already_downloaded.append(key)
                            already_downloaded_size += size
                        else:
                            to_download.append(key)
                            to_download_e_tags.append(e_tag)
                            to_download_size += size

            # Check if there are more objects to retrieve
            if response['IsTruncated']:
                continuation_token = response['NextContinuationToken']
                response = s3.list_objects_v2(
                    Bucket=ctx.deployment['BUCKET'], Prefix='standardized/', ContinuationToken=continuation_token)
            else:
                break

        if len(already_downloaded) > 0:
            print('Found '+str(len(already_downloaded))+' files already downloaded.')
            print('Total size already downloaded is '+sizeof_fmt(already_downloaded_size))
        print('Found '+str(len(to_download))+' new files to download.')
        print('Total size to download is '+sizeof_fmt(to_download_size))
        if len(to_download) > 5:
            print('Here are the first 5:')
            for i in range(5):
                print("  - "+to_download[i])
        else:
            for td in to_download:
                print("  - " + td)
        print('Is that ok?')
        resp: str = input('y/n or an integer number to download: ')
        confired: bool = False
        if resp == 'y':
            confired = True
        elif resp == 'n':
            confired = False
        else:
            # Check if the user entered an integer
            try:
                confired = True
                num: int = int(resp)
                if num > len(to_download):
                    print('Invalid number')
                    return
                else:
                    print('Downloading only the first '+str(num)+' results')
                to_download = to_download[:num]
            except ValueError:
                pass

        if not confired:
            print('Aborting')
            return

        for key in to_download:
            print('Downloading '+key)
            if os.path.exists(key):
                print('File already exists, skipping')
                continue
            # os.path.dirname gets the directory portion from the full path
            directory = os.path.dirname(key)
            # Create the directory structure, if it doesn't exist already
            os.makedirs(directory, exist_ok=True)
            # Download the file
            s3.download_file(ctx.deployment['BUCKET'], key, key)