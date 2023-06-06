from commands.abtract_command import AbstractCommand
import argparse
from auth import AuthContext


class DownloadCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        download_parser = subparsers.add_parser(
            'download', help='Download a training dataset from AddBiomechanics')
        download_parser.add_argument(
            'output_path', type=str, help='The path to the folder to put the downloaded data')

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'download':
            return

        output_path: str = args.output_path

        s3 = ctx.aws_session.client('s3')
        # Call list_objects_v2() with the continuation token
        response = s3.list_objects_v2(
            Bucket=ctx.deployment['BUCKET'], Prefix='protected/')

        binaryFiles = []
        totalSize = 0
        # Retrieve the first set of objects
        while True:
            # Process the objects in the response
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    size = obj['Size']
                    if key.endswith('.bin'):
                        binaryFiles.append((key, size))
                        totalSize += size

            # Check if there are more objects to retrieve
            if response['IsTruncated']:
                continuation_token = response['NextContinuationToken']
                response = s3.list_objects_v2(
                    Bucket=ctx.deployment['BUCKET'], Prefix='protected/', ContinuationToken=continuation_token)
            else:
                break

        print('Found '+str(len(binaryFiles))+' binary files totalling ' +
              str(round(totalSize / 1e6, 2))+' Mb:')
        if not output_path.endswith('/'):
            output_path += '/'
        for i, (file, size) in enumerate(binaryFiles):
            display_name = '/'.join(file.split('/')[-2:])
            file_name = file.replace('/', '_')
            dest_path = output_path+file_name
            print('Downloading '+str(i+1)+'/'+str(len(binaryFiles)) +
                  ' '+display_name+' ('+str(round(size / 1e6, 2))+' Mb)')
            directory = os.path.dirname(dest_path)
            if not os.path.exists(directory):
                os.makedirs(directory)
            s3.download_file(deployment['BUCKET'], file, dest_path)
