import argparse
import os
from reactive_s3 import ReactiveS3Index, FileMetadata
import boto3


def upload_data(standard_model: str, target_gdrive_folder: str):
    # Load the 'rclone' module
    os.system(f'ml system rclone')

    prod_bucket = 'biomechanics-uploads83039-prod'
    dev_bucket = 'biomechanics-uploads161949-dev'
    buckets = [prod_bucket, dev_bucket]
    s3 = boto3.resource('s3', region_name='us-west-2')
    for bucket_name in buckets:
        bucket = s3.Bucket(bucket_name)
        for object in bucket.objects.all():
            key: str = object.key
            if key.startswith('standardized/'+standard_model):
                if key.endswith('.osim') or key.endswith('.b3d'):
                    last_modified: int = int(object.last_modified.timestamp() * 1000)
                    e_tag = object.e_tag[1:-1]  # Remove the double quotes around the ETag value
                    size: int = object.size
                    local_file_path = f'/tmp/{key}'
                    bucket.download_file(key, local_file_path)
                    google_file_path = f'{target_gdrive_folder}/{key}'
                    os.system(f'rclone copy {local_file_path} gdrive:{google_file_path}')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run a data harvesting daemon.')
    parser.add_argument('--standard-model', type=str,
                        default='rajagopal_with_arms',
                        help='The standardized model to upload. Either rajagopal_with_arms or rajagopal_no_arms')
    parser.add_argument('--target-gdrive-folder', type=str, required=True,
                        help='The target Google Drive folder to upload the data to.')
    args = parser.parse_args()
    upload_data(args.standard_model, args.target_gdrive_folder)
