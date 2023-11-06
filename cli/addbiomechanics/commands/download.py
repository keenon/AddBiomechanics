from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from typing import List, Dict, Tuple, Set
import json
import re


class DownloadCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        download_parser = subparsers.add_parser(
            'download', help='Download a dataset from AddBiomechanics')
        download_parser.add_argument('pattern', type=str,
                                     help='The regex to match files to be downloaded.')
        download_parser.add_argument('--prefix', type=str, default='standardized/',
                                     help='The folder prefix to match when listing potential files to download.')
        download_parser.add_argument('--marker-error-cutoff', type=float,
                                     help='The maximum marker RMSE (in meters) we will tolerate. Files that match the regex '
                                          'pattern but are from subjects that are above bbove this threshold will not '
                                          'be downloaded.', default=None)

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'download':
            return
        pattern: str = args.pattern
        prefix: str = args.prefix
        marker_error_cutoff = args.marker_error_cutoff

        # Compile the pattern as a regex
        regex = re.compile(pattern)

        s3 = ctx.aws_session.client('s3')

        response = s3.list_objects_v2(
            Bucket=ctx.deployment['BUCKET'], Prefix=prefix)

        to_download: List[str] = []
        to_download_e_tags: List[str] = []
        to_download_size: int = 0
        already_downloaded: List[str] = []
        already_downloaded_size: int = 0

        files: List[Tuple[str, int, str]] = []
        keys: List[str] = []

        while True:
            if 'Contents' in response:
                for obj in response['Contents']:
                    key: str = obj['Key']
                    size: int = obj['Size']
                    e_tag: str = obj['ETag']
                    files.append((key, size, e_tag))
                    keys.append(key)

            # Check if there are more objects to retrieve
            if response['IsTruncated']:
                continuation_token = response['NextContinuationToken']
                response = s3.list_objects_v2(
                    Bucket=ctx.deployment['BUCKET'], Prefix=prefix, ContinuationToken=continuation_token)
            else:
                break

        subjects: Set[str] = set()
        for key, size, e_tag in files:
            if key.endswith("_subject.json"):
                subject = key.replace("_subject.json", "")
                subjects.add(subject)

        # The username_pattern is: "us-west-2:" followed by any number of non-forward-slash characters,
        # ending at the first forward slash.
        username_pattern = r"us-west-2:[^/]*/"

        usernames: Set[str] = set()

        for key, size, e_tag in files:
            if regex.match(key):
                if e_tag in to_download_e_tags:
                    continue
                if os.path.exists(key):
                    already_downloaded.append(key)
                    already_downloaded_size += size

                    # Ensure we capture the username for constructing our ATTRIBUTION.txt file
                    match = re.search(username_pattern, key)
                    if match:
                        username = match.group(0)
                        if username not in usernames:
                            usernames.add(username)
                else:
                    skip_file = False
                    if marker_error_cutoff is not None:
                        for subject in subjects:
                            if key.startswith(subject):
                                results_key = subject + "_results.json"
                                print(results_key)
                                if results_key in keys:
                                    try:
                                        response = s3.get_object(Bucket=ctx.deployment['BUCKET'], Key=results_key)
                                        file_content = response['Body'].read().decode('utf-8')
                                        results_json = json.loads(file_content)
                                        if 'autoAvgRMSE' in results_json:
                                            error_meters = results_json['autoAvgRMSE']
                                            if error_meters > marker_error_cutoff:
                                                print('!! Skipping ' + key + ' because the marker error is ' +
                                                      str(results_json['autoAvgRMSE']) + ' m')
                                                skip_file = True
                                                break
                                            else:
                                                print('Including ' + key + ' because the marker error is ' +
                                                      str(results_json['autoAvgRMSE']) + ' m')
                                    except Exception as e:
                                        print('!! Skipping ' + key + ' because we could not read the results file.')
                                        skip_file = True
                                break
                    if skip_file:
                        continue

                    # Ensure we capture the username for constructing our ATTRIBUTION.txt file
                    match = re.search(username_pattern, key)
                    if match:
                        username = match.group(0)
                        if username not in usernames:
                            usernames.add(username)

                    to_download.append(key)
                    to_download_e_tags.append(e_tag)
                    to_download_size += size

        print('A total of '+str(len(usernames))+' AddBiomechanics users will be credited in the ATTRIBUTION.txt file.')
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

        credit_list: List[str] = []
        for username in usernames:
            credit = username
            profile_link = 'https://' + ('dev' if ctx.deployment['NAME'] == 'DEV' else 'app') + '.addbiomechanics.org/profile/' + username.replace('us-west-2:', '')

            # Try to get the profile.json file, if it exists
            profile_key: str = "protected/" + str(username) + "profile.json"
            try:
                response = s3.get_object(Bucket=ctx.deployment['BUCKET'], Key=profile_key)
                file_content = response['Body'].read().decode('utf-8')
                profile_json = json.loads(file_content)
                name = ''
                surname = ''
                if 'name' in profile_json:
                    name = profile_json['name']
                if 'surname' in profile_json:
                    surname = profile_json['surname']
                if name != '' or surname != '':
                    credit = name + ' ' + surname + ' (' + profile_link + ')'
            except Exception as e:
                credit = 'Anonymous (' + profile_link + ')'
                pass

            credit_list.append(credit)

        data_credits = 'Data Licensed as Creative Commons BY 4.0 (See https://creativecommons.org/licenses/by/4.0/ for details)\nCredits:\n'
        for credit in credit_list:
            data_credits += '  - ' + credit + '\n'
        print(data_credits)
        with open('DATA_LICENSE.txt' if ctx.deployment['NAME'] == 'PROD' else 'DATA_LICENSE_DEV_SERVER.txt', 'w') as f:
            f.write(data_credits)

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
            try:
                s3.download_file(ctx.deployment['BUCKET'], key, key)
            except (NoCredentialsError, PartialCredentialsError, ClientError) as e:
                if 'ExpiredToken' in str(e):
                    print('Session expired. Refreshing AWS session.')
                    ctx.refresh()
                    s3 = ctx.aws_session.client('s3')
                    # Retry the download operation
                    s3.download_file(ctx.deployment['BUCKET'], key, key)
                else:
                    raise
