import argparse
import os
import boto3
import requests
from typing import Dict, List, Tuple
import json
import time
from auth import ensure_login, get_id_token, get_user_identity_id, get_temp_aws_access_keys, get_temp_aws_session


PROD_DEPLOYMENT = {
    'POOL_NAME': "biomechanicsfrontendf7e99b66_userpool_f7e99b66-prod",
    'POOL_ID': "us-west-2_vRDVX9u35",
    'POOL_ARN': "arn:aws:cognito-idp:us-west-2:756193201945:userpool/us-west-2_vRDVX9u35",
    'POOL_CLIENT_ID': '2sf0gfv660a0q6abr8d3hi99ck',
    'ID_POOL': 'us-west-2:8817f48e-9e7b-46a4-91ea-42f4b35a55b3',
    'BUCKET': "biomechanics-uploads83039-prod",
    'REGION': "us-west-2",
    'ROLE_ARN': "arn:aws:iam::756193201945:role/amplify-biomechanicsfrontend-prod-83039-authRole",
    'MQTT_PREFIX': "PROD"
}

DEV_DEPLOYMENT = {
    'POOL_NAME': "biomechanicsfrontendf7e99b66_userpool_f7e99b66-dev",
    'POOL_ID': "us-west-2_2axuLRtXr",
    'POOL_ARN': "arn:aws:cognito-idp:us-west-2:756193201945:userpool/us-west-2_2axuLRtXr",
    'POOL_CLIENT_ID': '9edncgra4lj0dlt245sio7qpn',
    'ID_POOL': 'us-west-2:3c433c8f-9b94-44b5-83c0-bae84529e0f7',
    'BUCKET': "biomechanics-uploads161949-dev",
    'REGION': "us-west-2",
    'ROLE_ARN': "arn:aws:iam::756193201945:role/amplify-biomechanicsfrontend-dev-161949-authRole",
    'MQTT_PREFIX': "DEV"
}


def ls(session: boto3.Session, deployment: Dict[str, str], user_identity_id: str) -> None:
    s3 = session.client('s3')
    # Call list_objects_v2() with the continuation token
    response = s3.list_objects_v2(
        Bucket=deployment['BUCKET'], Prefix='protected/'+user_identity_id)
    # Retrieve the first set of objects
    while True:
        # Process the objects in the response
        if 'Contents' in response:
            for obj in response['Contents']:
                print(obj['Key'])

        # Check if there are more objects to retrieve
        if response['IsTruncated']:
            continuation_token = response['NextContinuationToken']
            response = s3.list_objects_v2(
                Bucket=deployment['BUCKET'], Prefix='protected/'+user_identity_id, ContinuationToken=continuation_token)
        else:
            break


def download_dataset(session: boto3.Session, deployment: Dict[str, str], output_path: str):
    s3 = session.client('s3')
    # Call list_objects_v2() with the continuation token
    response = s3.list_objects_v2(
        Bucket=deployment['BUCKET'], Prefix='protected/')
    
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
                Bucket=deployment['BUCKET'], Prefix='protected/'+user_identity_id, ContinuationToken=continuation_token)
        else:
            break
    
    print('Found '+str(len(binaryFiles))+' binary files totalling '+str(round(totalSize / 1e6, 2))+' Mb:')
    if not output_path.endswith('/'):
        output_path += '/'
    for i, (file, size) in enumerate(binaryFiles):
        display_name = '/'.join(file.split('/')[-2:])
        file_name = file.replace('/', '_')
        dest_path = output_path+file_name
        print('Downloading '+str(i+1)+'/'+str(len(binaryFiles))+' '+display_name+' ('+str(round(size / 1e6, 2))+' Mb)')
        directory = os.path.dirname(dest_path)
        if not os.path.exists(directory):
            os.makedirs(directory)
        s3.download_file(deployment['BUCKET'], file, dest_path)


def upload_subject(session: boto3.Session,
                   deployment: Dict[str, str],
                   user_email: str,
                   dataset_path: str,
                   opensim_unscaled: str = 'vicon',
                   filter_markers: str = '',
                   subject_name: str = '',
                   dataset_name: str = '',
                   subject_height_m: float = 1.68,
                   subject_weight_kg: float = 68.8,
                   subject_sex: str = 'unknown',
                   foot_body_names: List[str] = ['calcn_l', 'calcn_r'],
                   skip_confirm: bool = False) -> None:
    trc_files: List[str] = []
    c3d_files: List[str] = []
    grf_files: List[str] = []

    # Get the list of files in the dataset
    for root, dirs, files in os.walk(dataset_path):
        for file in files:
            if file.endswith(".trc"):
                trc_files.append(os.path.join(root, file))
            elif file.endswith(".c3d"):
                c3d_files.append(os.path.join(root, file))
            elif file.endswith(".mot"):
                grf_files.append(os.path.join(root, file))

    class Trial:
        def __init__(self, trial_name: str, marker_file: str, grf_file: str):
            self.trial_name = trial_name
            self.marker_file = marker_file
            self.grf_file = grf_file
    trials: List[Trial] = []

    marker_files = trc_files + c3d_files
    for marker_file in marker_files:
        if filter_markers not in marker_file:
            continue

        trial_name = marker_file.split('/')[-1].split('.')[0]
        trial_path = marker_file.split(trial_name)[0]

        grf_name_matches: List[str] = []
        grf_path_matches: List[str] = []
        for grf_file in grf_files:
            grf_name = grf_file.split('/')[-1].split('.')[0]
            grf_path = grf_file.split(grf_name)[0]

            if trial_name in grf_name:
                grf_name_matches.append(grf_file)
            if trial_path == grf_path:
                grf_path_matches.append(grf_file)

        if len(grf_name_matches) == 1:
            trials.append(Trial(trial_name, marker_file, grf_name_matches[0]))
        elif len(grf_path_matches) == 1:
            trials.append(Trial(trial_name, marker_file, grf_path_matches[0]))
        elif len(grf_name_matches) == 0 and len(grf_path_matches) == 0:
            trials.append(Trial(trial_name, marker_file, None))
        else:
            # Use some simple heuristics to check first
            grf_names_with_forces = [
                name for name in grf_name_matches if 'force' in name.lower()]
            if len(grf_names_with_forces) == 1:
                trials.append(Trial(trial_name, marker_file,
                              grf_names_with_forces[0]))
                continue

            print(
                f"Multiple possible matches for {marker_file}:")
            possible_grf_matches = grf_name_matches + grf_path_matches
            for i in range(len(possible_grf_matches)):
                print(f"{i}: {possible_grf_matches[i]}")
            choice = int(input("Which one should be used? "))
            trials.append(Trial(trial_name, marker_file,
                          possible_grf_matches[choice]))

    print('Found the following trials:')
    prefix = os.path.abspath(dataset_path)
    for trial in trials:
        trial_name = trial.trial_name
        marker_file = trial.marker_file
        grf_file = trial.grf_file
        marker_relative_path = marker_file.replace(prefix, '')
        if grf_file is not None:
            grf_relative_path = grf_file.replace(prefix, '')
            print(
                f' > Markers: {marker_relative_path}, GRF: {grf_relative_path}')
        else:
            print(f' > Markers: {marker_relative_path}, no GRF file found')

    parts = dataset_path.split('/')
    subject_name = parts[-1] if subject_name == '' else subject_name
    dataset_name = (parts[-2] if len(parts) >
                    1 else 'Misc') if dataset_name == '' else dataset_name

    skeleton_preset = 'custom'
    model_display_name = opensim_unscaled
    if opensim_unscaled == 'vicon' or opensim_unscaled == 'cmu':
        skeleton_preset = opensim_unscaled
        if opensim_unscaled == 'vicon':
            model_display_name = 'Rajagopal with Vicon Markers'
        elif opensim_unscaled == 'cmu':
            model_display_name = 'Rajagopal with CMU Markers'

    print('Dataset Name: '+dataset_name)
    print('Subject Name: '+subject_name)
    print(' > Height: '+str(subject_height_m)+'m')
    print(' > Mass: '+str(subject_weight_kg)+'kg')
    print(' > Biological Sex: '+str(subject_sex))
    print(' > Unscaled Model: '+str(model_display_name))

    if not skip_confirm:
        confirm = input('Is this correct? [y/n] ')
        if confirm != 'y':
            print('Aborting upload. You can use the --help flag to see the available options to customize the above.')
            return

    print('Uploading...')

    # Upload the files
    s3 = session.client('s3')
    pubsub = session.client('iot-data')

    # Send real-time updates to PubSub saying that this file was uploaded
    def notifyFileChanged(key: str, size_bytes: int = 0):
        parts = key.split('/')
        topic = '/' + deployment['MQTT_PREFIX'] + '/UPDATE/'
        if len(parts) > 0:
            topic += parts[0]
        if len(parts) > 1:
            topic += '/' + parts[1]
        print('publishing to '+topic)
        pubsub.publish(
            topic=topic,
            qos=1,
            payload=json.dumps({'key': key, 'topic': topic, 'size': size_bytes, 'lastModified': int(time.time()*1000)}))

    s3_prefix = 'protected/'+user_identity_id + \
        '/data/' + dataset_name + '/' + subject_name + '/'

    # Generate the config file
    subject_json: Dict[str, str] = {
        'name': subject_name,
        'massKg': str(subject_weight_kg),
        'heightM': str(subject_height_m),
        "email": user_email,
        "footBodyNames": foot_body_names,
        "skeletonPreset": skeleton_preset
    }
    s3.put_object(Body=json.dumps(subject_json),
                  Bucket=deployment['BUCKET'], Key=s3_prefix+'_subject.json')
    notifyFileChanged(s3_prefix+'_subject.json')
    s3.put_object(Body='',
                  Bucket=deployment['BUCKET'], Key=s3_prefix+'trials/')
    notifyFileChanged(s3_prefix+'trials/')

    # Upload the opensim unscaled model
    if skeleton_preset == 'custom':
        osim_file_key = s3_prefix + 'unscaled_generic.osim'
        s3.upload_file(opensim_unscaled,
                       deployment['BUCKET'], osim_file_key)
        print(f'Uploading {opensim_unscaled} to {osim_file_key}')
        notifyFileChanged(osim_file_key,
                          size_bytes=os.path.getsize(opensim_unscaled))

    for trial in trials:
        trial_name = trial.trial_name
        marker_file = trial.marker_file
        marker_data_type = marker_file.split('.')[-1].lower()
        grf_file = trial.grf_file

        # Upload the marker file
        marker_file_key = s3_prefix+'trials/'+trial_name+'/markers.'+marker_data_type
        print(f'Uploading {marker_file} to {marker_file_key}')
        s3.upload_file(marker_file, deployment['BUCKET'], marker_file_key)
        notifyFileChanged(
            marker_file_key, size_bytes=os.path.getsize(marker_file))

        # Upload the grf file
        if grf_file is not None:
            grf_file_key = s3_prefix+'trials/'+trial_name+'/grf.mot'
            print(f'Uploading {grf_file} to {grf_file_key}')
            s3.upload_file(grf_file, deployment['BUCKET'], grf_file_key)
            notifyFileChanged(
                grf_file_key, size_bytes=os.path.getsize(grf_file))
    # Mark to begin processing immediately
    s3.put_object(Body='',
                  Bucket=deployment['BUCKET'], Key=s3_prefix+'READY_TO_PROCESS')
    notifyFileChanged(s3_prefix+'READY_TO_PROCESS')


if __name__ == '__main__':
    # Create an ArgumentParser object
    parser = argparse.ArgumentParser(
        description='AddBiomechanics Command Line Interface')
    parser.add_argument('-u', '--username', type=str, default=None,
                        help='The username to use to log in to AddBiomechanics (if not provided, will attempt to load from ~/.addb_login.json, and then fallback to prompting for username and password)')
    parser.add_argument('-p', '--password', type=str, default=None,
                        help='The password to use to log in to AddBiomechanics (if not provided, will attempt to load from ~/.addb_login.json, and then fallback to prompting for username and password)')
    parser.add_argument('-d', '--deployment', type=str, default='dev', choices=['dev', 'prod'],
                        help='The deployment to interact with (default: dev)')

    # Split up by command
    subparsers = parser.add_subparsers(dest="command")

    # Add a parser for the ls command
    ls_parser = subparsers.add_parser(
        'ls', help='List the contents of your uploads on AddBiomechanics')

    # Add a parser for the download command
    download_parser = subparsers.add_parser(
        'download', help='Download a training dataset from AddBiomechanics')
    download_parser.add_argument(
        'output_path', type=str, help='The path to the folder to put the downloaded data')

    # Add a parser for the process command
    process_parser = subparsers.add_parser(
        'upload', help='Upload a subject-worth of data to AddBiomechanics to process')
    process_parser.add_argument(
        'dataset_path', type=str, help='The path to the folder containing the data you wish to process')
    process_parser.add_argument('-o', '--opensim_unscaled', type=str, default='vicon',
                                help='Either "vicon" or "cmu" (to use a preset Rajagopal model with markerset), or a path to the unscaled *.OSIM file you would like to use to fit the data')
    process_parser.add_argument('-m', '--height_m', type=float, default=1.68,
                                help='The height of the subject, in meters')
    process_parser.add_argument('-k', '--mass_kg', type=float, default=68.0,
                                help='The mass of the subject, in kilograms')
    process_parser.add_argument('-s', '--sex', type=str, choices=[
                                'male', 'female', 'unknown'], default='unknown', help='The biological sex of the subject')
    process_parser.add_argument('-b', '--foot_body_names', type=List[str], default=['calcn_r', 'calcn_l'],
                                help='The names of the bodies in the model that will be used to fit the GRF data. See the AddBiomechanics paper for more details about how these bodies are used.')
    process_parser.add_argument('-f', '--filter_markers', type=str, default='',
                                help='Marker data will only be included if it contains this string in the path')
    process_parser.add_argument('-n', '--subject_name', type=str, default='',
                                help='The name of the subject. If not specified, we will guess based on the dataset path')
    process_parser.add_argument('-d', '--dataset_name', type=str, default='',
                                help='The name of the dataset to include the subject in on AddBiomechanics. If not specified, we will guess based on the dataset path')
    process_parser.add_argument('-y', '--yes', type=bool, default=False,
                                help='This skips the manual confirmation step')

    # Parse the arguments
    args = parser.parse_args()

    # Get deployment info
    deployment = DEV_DEPLOYMENT if args.deployment == 'dev' else PROD_DEPLOYMENT

    # Authenticate the user
    username, password = ensure_login(args.username, args.password)
    id_token = get_id_token(
        deployment['POOL_CLIENT_ID'], username, password)
    user_identity_id = get_user_identity_id(
        id_token, deployment['REGION'], deployment['POOL_ID'], deployment['ID_POOL'])
    print('Got user identity: '+user_identity_id)
    aws_keys = get_temp_aws_access_keys(
        id_token, user_identity_id, deployment['REGION'], deployment['POOL_ID'])
    aws_session = get_temp_aws_session(
        aws_keys, deployment['REGION'])

    # Call the main function with the parsed arguments
    if args.command == 'ls':
        ls(aws_session, deployment, user_identity_id)
    if args.command == 'download':
        download_dataset(aws_session, deployment, args.output_path)
    elif args.command == 'upload':
        upload_subject(aws_session,
                       deployment,
                       username,
                       args.dataset_path,
                       opensim_unscaled=args.opensim_unscaled,
                       filter_markers=args.filter_markers,
                       subject_name=args.subject_name,
                       dataset_name=args.dataset_name,
                       subject_height_m=args.height_m,
                       subject_weight_kg=args.mass_kg,
                       subject_sex=args.sex,
                       foot_body_names=args.foot_body_names,
                       skip_confirm=args.yes)
