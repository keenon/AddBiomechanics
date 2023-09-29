import argparse
from reactive_s3 import ReactiveS3Index, FileMetadata
import json

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='This is a skeleton of a script to patch the standardized data in various ways.')
    parser.add_argument('--bucket', type=str, default="biomechanics-uploads161949-dev",
                        help='The S3 bucket to access user data in')
    parser.add_argument('--deployment', type=str,
                        default='DEV',
                        help='The deployment to target (must be DEV or PROD)')
    args = parser.parse_args()

    print('Connecting to S3...')
    index = ReactiveS3Index(args.bucket, args.deployment, disable_pubsub=True)
    index.refreshIndex()

    for folder in index.listAllFolders():
        # We want to collect all the dataset targets that we're supposed to be copying data to, in case
        # those have been updated
        if folder.startswith('standardized'):
            if folder.endswith('/'):
                folder = folder[:-1]
            children = index.getImmediateChildren(folder + '/')
            subject_files = [x for x in children if x.endswith('_subject.json')]
            if len(subject_files) == 1:
                print('Checking subject file: '+subject_files[0])
                tmp_file: str = index.downloadToTmp(folder + '/_subject.json')
                with open(tmp_file, 'r') as f:
                    subject = json.load(f)
                    if 'skeletonPreset' in subject:
                        skeleton_preset = subject['skeletonPreset']
                        if skeleton_preset != 'custom':
                            print('Found a non-custom skeleton preset: '+skeleton_preset)
                            print('Patching to custom skeleton preset')
                            subject['skeletonPreset'] = 'custom'
                            index.uploadJSON(folder + '/_subject.json', subject)
                            index.delete(folder + '/SLURM')
                            index.delete(folder + '/PROCESSING')
                            index.delete(folder + '/_results.json')
                            bin_files = [x for x in children if x.endswith('.bin')]
                            for bin_file in bin_files:
                                index.delete(folder + '/' + bin_file)
