from addbiomechanics.commands.abstract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import collections
import re


class AnalyticsCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        analytics_parser = subparsers.add_parser(
            'analytics', help='Parse the state of the AddBiomechanics database, and show the number of users, subjects uploaded, and trials')

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'analytics':
            return

        s3 = ctx.aws_session.client('s3')

        user_stats = collections.defaultdict(lambda: {"subjects": set(
        ), "trials": set(), "trial_etags": set(), "total_size": 0})
        dataset_stats = collections.defaultdict(
            lambda: {"subjects": set(), "trials": set(), "trial_etags": set(), "total_size": 0})

        prefixes = ['protected/', 'standardized/']

        for prefix in prefixes:
            response = s3.list_objects_v2(
                Bucket=ctx.deployment['BUCKET'], Prefix=prefix)

            # Compile the regular expression
            subject_name_pattern = re.compile(r"([^/]*)/trials/")
            trial_name_pattern = re.compile(r"/trials/([^/]*)")

            # Retrieve the first set of objects
            while True:
                # Process the objects in the response
                if 'Contents' in response:
                    for obj in response['Contents']:
                        key: str = obj['Key']
                        size: int = obj['Size']
                        e_tag: str = obj['ETag']
                        if key.endswith('.c3d') or key.endswith('.trc') or key.endswith('grf.mot'):
                            trial_name_matches = trial_name_pattern.findall(key)
                            if len(trial_name_matches) == 0:
                                continue

                            trial_name = trial_name_matches[0]
                            subject_name_matches = subject_name_pattern.findall(key)
                            subject_name = subject_name_matches[0]
                            trial_path = key.split(trial_name)[0] + trial_name

                            if key.startswith('protected/') and 'trials/' in key and len(key.split('trials/')) == 2:
                                user_id = key.split(
                                    'protected/')[1].split('/')[0]
                                if subject_name not in user_stats[user_id]["subjects"]:
                                    user_stats[user_id]["subjects"].add(
                                        subject_name)
                                if e_tag not in user_stats[user_id]["trial_etags"]:
                                    user_stats[user_id]["trial_etags"].add(e_tag)
                                    user_stats[user_id]["total_size"] += size
                                if trial_path not in user_stats[user_id]["trials"]:
                                    user_stats[user_id]["trials"].add(trial_path)

                            elif key.startswith('standardized/') and 'trials/' in key and len(key.split('trials/')) == 2:
                                dataset_name = key.split(
                                    'standardized/')[1].split('/')[0]
                                if subject_name not in dataset_stats[dataset_name]["subjects"]:
                                    dataset_stats[dataset_name]["subjects"].add(
                                        subject_name)
                                if e_tag not in dataset_stats[dataset_name]["trial_etags"]:
                                    dataset_stats[dataset_name]["trial_etags"].add(
                                        e_tag)
                                    dataset_stats[dataset_name]["total_size"] += size
                                if trial_path not in dataset_stats[dataset_name]["trials"]:
                                    dataset_stats[dataset_name]["trials"].add(
                                        trial_path)

                # Check if there are more objects to retrieve
                if response['IsTruncated']:
                    continuation_token = response['NextContinuationToken']
                    response = s3.list_objects_v2(
                        Bucket=ctx.deployment['BUCKET'], Prefix=prefix, ContinuationToken=continuation_token)
                else:
                    break

        # Sort and print user stats
        for user_id, stats in sorted(user_stats.items(), key=lambda item: item[1]["total_size"], reverse=True):
            print(
                f'User {user_id} has {len(stats["subjects"])} subjects, {len(stats["trials"])} trials, {len(stats["trial_etags"])} unique TRC/C3D/GRF files, total size of unique trial TRC/C3D/GRF files: {stats["total_size"]/1024/1024} MB')

        # Sort and print dataset stats
        for dataset_name, stats in sorted(dataset_stats.items(), key=lambda item: item[1]["total_size"], reverse=True):
            print(
                f'Dataset {dataset_name} has {len(stats["subjects"])} subjects, has {len(stats["trials"])} trials, {len(stats["trial_etags"])} unique TRC/C3D/GRF files, total size of unique trial TRC/C3D/GRF files: {stats["total_size"]/1024/1024} MB')
