from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os
from datetime import datetime
from addbiomechanics.s3_structure import S3Node, retrieve_s3_structure, sizeof_fmt
from botocore.exceptions import NoCredentialsError, PartialCredentialsError, ClientError
from typing import List, Dict, Tuple, Set, Optional
import json
import re


class SubjectToDownload:
    path: str
    contained_files: List[Tuple[str, int, str]]
    is_reviewed: bool
    username: str

    def __init__(self, path: str, contained_files: List[Tuple[str, int, str]]):
        self.path = path
        self.contained_files = contained_files
        contained_file_names: List[str] = [
            os.path.basename(file[0]) for file in contained_files
        ]
        self.is_reviewed = 'REVIEWED' in contained_file_names

        print('Creating SubjectToDownload for ' + path + ' with ' + str(len(contained_files)) + ' files. Is reviewed: ' + str(self.is_reviewed))
        print('Num REVIEWED flags: ' + str(len([file for file in contained_file_names if file == 'REVIEWED'])))

        # The username_pattern is: "us-west-2:" followed by any number of non-forward-slash characters,
        # ending at the first forward slash.
        username_pattern = r"us-west-2:[^/]*/"

        # Ensure we capture the username for constructing our ATTRIBUTION.txt file
        match = re.search(username_pattern, path)
        if match:
            self.username = match.group(0)
        else:
            self.username = 'Anonymous'


class DownloadCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        download_parser = subparsers.add_parser(
            'download', help='Download a dataset from AddBiomechanics')
        download_parser.add_argument('--pattern',
                                     type=str,
                                     default=None,
                                     help='The regex to match subjects to be downloaded.')
        download_parser.add_argument('--prefix',
                                     type=str,
                                     default='protected/us-west-2:e013a4d2-683d-48b9-bfe5-83a0305caf87', # 'standardized/'
                                     help='The folder prefix to match when listing potential files to download.')
        download_parser.add_argument('--marker-error-cutoff', type=float,
                                     help='The maximum marker RMSE (in meters) we will tolerate. Files that match the '
                                          'regex pattern but are from subjects that are above bbove this threshold will'
                                          ' not be downloaded.', default=None)
        download_parser.add_argument('--reviewed-only',
                                     type=bool,
                                     default=True,
                                     help='Only download files from subjects that are fully reviewed.')

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'download':
            return
        pattern: Optional[str] = args.pattern
        prefix: str = args.prefix
        marker_error_cutoff = args.marker_error_cutoff
        reviewed_only = args.reviewed_only

        # Compile the pattern as a regex
        regex = re.compile(pattern) if pattern is not None else None

        s3 = ctx.aws_session.client('s3')

        response = s3.list_objects_v2(
            Bucket=ctx.deployment['BUCKET'], Prefix=prefix)

        files: List[Tuple[str, int, str]] = []
        keys: List[str] = []

        print(f'Listing files on S3 at {prefix}...')
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
                print(f'Have {len(files)} files so far. Listing next page of files to download at {prefix}...')
                continuation_token = response['NextContinuationToken']
                response = s3.list_objects_v2(
                    Bucket=ctx.deployment['BUCKET'], Prefix=prefix, ContinuationToken=continuation_token, MaxKeys=10000)
            else:
                print(f'Finished listing files to download at {prefix}. Found {len(files)} files.')
                break

        subject_paths: List[str] = []
        for key, size, e_tag in files:
            if key.endswith("_subject.json"):
                subject_paths.append(key.replace("_subject.json", ""))

        subject_file_sets: Dict[str, List[Tuple[str, int, str]]] = {}
        for key, size, e_tag in files:
            for subject_path in subject_paths:
                if key.startswith(subject_path):
                    if subject_path not in subject_file_sets:
                        subject_file_sets[subject_path] = []
                    subject_file_sets[subject_path].append((key, size, e_tag))
                    break

        subjects: List[SubjectToDownload] = []
        for subject_path in subject_paths:
            subjects.append(SubjectToDownload(subject_path, subject_file_sets[subject_path]))

        print(f'Found {len(subjects)} subjects to download.')

        if reviewed_only:
            subjects = [subject for subject in subjects if subject.is_reviewed]
            print(f'After filtering for subjects that have been reviewed, have {len(subjects)} subjects to download.')

        if regex is not None:
            subjects = [subject for subject in subjects if regex.match(subject.path)]
            print(f'After filtering for regex "{pattern}" on subject paths, have {len(subjects)} subjects to download.')

        if marker_error_cutoff is not None:
            skip_files: List[bool] = []
            for subject in subjects:
                results_key = subject.path + "_results.json"
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
                skip_files.append(skip_file)

            subjects = [subject for i, subject in enumerate(subjects) if not skip_files[i]]
            print(f'After filtering for marker error cutoff, have {len(subjects)} subjects to download.')

        usernames: Set[str] = set([subject.username for subject in subjects])
        to_download: List[str] = []
        to_download_e_tags: List[str] = []
        to_download_sizes: List[int] = []
        to_download_size: int = 0
        already_downloaded: List[str] = []
        already_downloaded_size: int = 0

        for subject in subjects:
            for key, size, e_tag in subject.contained_files:
                if size > 0 and e_tag in to_download_e_tags:
                    continue
                if key.endswith('.b3d') or key.endswith('review.json') or key.endswith('REVIEWED'):
                    if os.path.exists(key):
                        already_downloaded.append(key)
                        already_downloaded_size += size
                    else:
                        to_download.append(key)
                        to_download_e_tags.append(e_tag)
                        to_download_sizes.append(size)
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
                to_download_e_tags = to_download_e_tags[:num]
                to_download_sizes = to_download_sizes[:num]
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

        for i, key in enumerate(to_download):
            print(f'Downloading {i+1}/{len(to_download)}: {key}')
            if os.path.exists(key):
                print('File already exists, skipping')
                continue
            # os.path.dirname gets the directory portion from the full path
            directory = os.path.dirname(key)
            # Create the directory structure, if it doesn't exist already
            os.makedirs(directory, exist_ok=True)
            # Download the file
            if to_download_sizes[i] == 0:
                # Create an empty file
                open(key, 'a').close()
            else:
                try:
                    s3.download_file(ctx.deployment['BUCKET'], key, key)
                except Exception as e:
                    print('Caught an exception trying to download. Trying refreshing AWS session and trying again.')
                    print(e)
                    ctx.refresh()
                    s3 = ctx.aws_session.client('s3')
                    # Retry the download operation
                    s3.download_file(ctx.deployment['BUCKET'], key, key)
