from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext


class LsCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        ls_parser = subparsers.add_parser(
            'ls', help='List the contents of your uploads on AddBiomechanics')
        ls_parser.add_argument('path', type=str, default='')

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'ls':
            return

        path = args.path
        if len(path) > 0 and not path.startswith('/'):
            path = '/' + path
        if not path.endswith('/'):
            path += '/'
        s3_prefix = 'protected/'+ctx.user_identity_id + '/data' + path
        # print('Checking S3 Prefix ' + s3_prefix)

        s3 = ctx.aws_session.client('s3')
        # Call list_objects_v2() with the continuation token
        response = s3.list_objects_v2(
            Bucket=ctx.deployment['BUCKET'], Prefix=s3_prefix, Delimiter='/')

        # Retrieve the first set of objects
        while True:
            # Process the objects in the response
            if 'CommonPrefixes' in response:
                for common_prefix in response.get('CommonPrefixes', []):
                    print(common_prefix['Prefix'].replace(s3_prefix, ''))
            if 'Contents' in response:
                for obj in response['Contents']:
                    print(obj['Key'].replace(s3_prefix, ''))

            # Check if there are more objects to retrieve
            if response['IsTruncated']:
                continuation_token = response['NextContinuationToken']
                response = s3.list_objects_v2(
                    Bucket=ctx.deployment['BUCKET'], Prefix=s3_prefix, Delimiter='/', ContinuationToken=continuation_token)
            else:
                break
