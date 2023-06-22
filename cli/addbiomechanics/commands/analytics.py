from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext


class AnalyticsCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        analytics_parser = subparsers.add_parser(
            'analytics', help='Parse the state of the AddBiomechanics database, and show the number of users, subjects uploaded, and trials')

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'analytics':
            return

        s3_prefix = 'protected/'
        s3 = ctx.aws_session.client('s3')
        # Call list_objects_v2() with the continuation token
        response = s3.list_objects_v2(
            Bucket=ctx.deployment['BUCKET'], Prefix=s3_prefix)

        subjects = set()
        trials = set()
        binaryFiles = []
        totalSize = 0
        # Retrieve the first set of objects
        while True:
            # Process the objects in the response
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    size = obj['Size']
                    if 'trials/' in key:
                        subjectName = key.split('trials/')[0]
                        if subjectName not in subjects:
                            subjects.add(subjectName)
                        trialName = key.split('trials/')[1].split('/')[0]
                        trialPath = subjectName + 'trials/' + trialName
                        if trialPath not in trials:
                            trials.add(trialPath)

            # Check if there are more objects to retrieve
            if response['IsTruncated']:
                continuation_token = response['NextContinuationToken']
                response = s3.list_objects_v2(
                    Bucket=ctx.deployment['BUCKET'], Prefix='protected/', ContinuationToken=continuation_token)
            else:
                break

        print('Found '+str(len(subjects))+' subjects and ' +
              str(len(trials))+' trials')
