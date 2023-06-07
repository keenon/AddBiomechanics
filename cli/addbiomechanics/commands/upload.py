from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
from typing import Dict, List, Tuple
import os
import json
import time


def upload_files(ctx: AuthContext, s3_to_local_file: Dict[str, str], s3_to_contents: Dict[str, str], s3_ready_flags: List[str], s3_prefix: str):
    """
    This method will upload a dictionary of files to S3 as a bulk operation, and send the 
    appropriate notifications to PubSub to notify other listeners that the files have changed.
    """
    session: boto3.Session = ctx.aws_session
    deployment: Dict[str, str] = ctx.deployment

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

    # Upload the files
    for s3_key, local_path in s3_to_local_file.items():
        s3_key = s3_prefix + s3_key
        print(f'Uploading {local_path} to {s3_key}')
        s3.upload_file(local_path, deployment['BUCKET'], s3_key)
        # Notify PubSub that this file changed
        notifyFileChanged(s3_key, size_bytes=os.path.getsize(local_path))

    # Upload the raw contents
    for s3_key, contents in s3_to_contents.items():
        s3_key = s3_prefix + s3_key
        print(
            f'Uploading raw string of length {str(len(contents))} to {s3_key}')
        s3.put_object(Body=contents,
                      Bucket=deployment['BUCKET'], Key=s3_key)
        # Notify PubSub that this file changed
        notifyFileChanged(s3_key, size_bytes=len(contents))

    # Upload the ready flags last, once everything else is already uploaded
    for s3_key in s3_ready_flags:
        s3_key = s3_prefix + s3_key
        s3.put_object(Body="",
                      Bucket=deployment['BUCKET'], Key=s3_key)
        # Notify PubSub that this file changed
        notifyFileChanged(s3_key, size_bytes=0)


class ParserFolderStructure:
    """
    This class is used to parse a folder structure on disk and upload it to S3 in a way that
    AddBiomechanics can understand. It is designed to be used in conjunction with the UploadCommand
    to automatically upload a dataset to AddBiomechanics.

    This uses heuristics to detect common folder structures automatically, so that the user does not
    need to specify the exact structure of the dataset.
    """
    # These are the inputs to the parsing
    common_prefix: str
    input_file_list: List[str]

    # These are the outputs of the parsing
    inferred_as_single_subject: bool
    inferred_dataset_name: str
    inferred_subject_name: str
    s3_to_local_file: Dict[str, str]
    s3_to_contents: Dict[str, str]
    s3_ready_flags: List[str]

    def __init__(self, input_file_list: List[str]):
        self.common_prefix = os.path.commonprefix(input_file_list)
        self.input_file_list = [
            f.replace(self.common_prefix, "") for f in input_file_list]
        self.s3_to_local_file = {}
        self.s3_to_contents = {}
        self.s3_ready_flags = []
        self.inferred_as_single_subject = False
        self.inferred_dataset_name = ''
        self.inferred_subject_name = ''

    def attempt_parse_as_preformatted_dataset(self, verbose=False, dont_read_files=False, override_osim_file: str = '', filter_out_trials: str = '') -> bool:
        """
        This method attempts to parse the input file list as a pre-formatted dataset, where the 
        _subject.json files already exist, and everything is in the AddBiomechanics S3 disk format 
        already. This method returns True if the data passes a validation check, and False otherwise.
        """
        if verbose:
            print('Attempting to parse as pre-formatted dataset...')

        subjectFiles = [
            f for f in self.input_file_list if f.endswith('_subject.json')]
        subjectRootFolders = [f.replace('_subject.json', '')
                              for f in subjectFiles]
        subjectNames = [f.split('/')[0] for f in subjectRootFolders]

        num_subjects = 0
        num_trials = 0
        for subjectFolder in subjectRootFolders:
            trialPath = subjectFolder+'trials/'
            trialFiles = [
                f for f in self.input_file_list if f.startswith(trialPath)]
            if len(trialFiles) == 0:
                if verbose:
                    print(
                        f' > {subjectFolder} does not have any trials, failing as invalid')
                return False
            trialNames = list(set([f.replace(trialPath, '').split('/')[0]
                                   for f in trialFiles if f.endswith('.mot') or f.endswith('.trc') or f.endswith('.c3d')]))
            for trialName in trialNames:
                trialFolder = trialPath+trialName+'/'
                trialFiles = [
                    f.replace(trialFolder, "") for f in self.input_file_list if f.startswith(trialFolder)]
                if len(trialFiles) == 0:
                    if verbose:
                        print(
                            f' > {trialFolder} does not have any files, failing as invalid')
                    return False
                # We don't actually fail on missing GRF during upload
                # if 'grf.mot' not in trialFiles:
                #     if verbose:
                #         print(
                #             f' > {trialFolder} does not have a grf.mot file, failing as invalid')
                #     return False
                if 'markers.trc' not in trialFiles and 'markers.c3d' not in trialFiles:
                    if verbose:
                        print(
                            f' > {trialFolder} does not have a markers.trc or markers.c3d file, failing as invalid')
                    return False

            # Check for the _subject.json file
            subjectJsonFile = subjectFolder+'_subject.json'
            if subjectJsonFile not in self.input_file_list:
                if verbose:
                    print(
                        f' > {subjectFolder} does not have a _subject.json file, failing as invalid')
                return False

            # Load and parse the _subject.json file
            if dont_read_files:
                if override_osim_file is '' and subjectFolder+'unscaled_generic.osim' not in self.input_file_list:
                    if verbose:
                        print(
                            f' > we have dont_read_files=True and {subjectJsonFile} could therefore have skeletonPreset=custom but we do not have a "unscaled_generic.osim" file, failing as invalid')
                    return False
            else:
                with open(self.common_prefix + subjectJsonFile, 'r') as f:
                    subjectJson = json.load(f)
                    if 'massKg' not in subjectJson:
                        if verbose:
                            print(
                                f' > {subjectJsonFile} does not have a "massKg" field, failing as invalid')
                        return False
                    if 'heightM' not in subjectJson:
                        if verbose:
                            print(
                                f' > {subjectJsonFile} does not have a "heightM" field, failing as invalid')
                        return False
                    # if 'email' not in subjectJson:
                    #     if verbose:
                    #         print(
                    #             f' > {subjectJsonFile} does not have a "email" field, failing as invalid')
                    #     return False
                    if 'footBodyNames' not in subjectJson:
                        if verbose:
                            print(
                                f' > {subjectJsonFile} does not have a "footBodyNames" field, failing as invalid')
                        return False
                    if ('skeletonPreset' not in subjectJson or subjectJson['skeletonPreset'] == 'custom') and override_osim_file is '' and subjectFolder+'unscaled_generic.osim' not in self.input_file_list:
                        if verbose:
                            print(
                                f' > {subjectJsonFile} has skeletonPreset=custom but does not have a "unscaled_generic.osim" file, failing as invalid')
                        return False

            filesInSubjectFolder = [
                f for f in self.input_file_list if f.startswith(subjectFolder)]
            if verbose:
                print(
                    f' > Subject "{subjectFolder}" is valid, with {len(trialNames)} trials')
            for file in filesInSubjectFolder:
                if filter_out_trials is not '' and filter_out_trials in file:
                    if verbose:
                        print(
                            ' > Skipping '+file+' because it matches filter "' + filter_out_trials + '"')
                    continue
                if file.endswith(".json") or file.endswith(".mot") or file.endswith(".trc") or file.endswith(".c3d") or file.endswith(".osim"):
                    self.s3_to_local_file[
                        file] = self.common_prefix+file
                if override_osim_file is not '':
                    self.s3_to_local_file[
                        subjectFolder+'unscaled_generic.osim'] = override_osim_file
            self.s3_ready_flags.append(subjectFolder+'READY_TO_PROCESS')

            num_subjects += 1
            num_trials += len(trialNames)

        if num_subjects == 0:
            if verbose:
                print(f'Failed to find any subjects, returning failure')
            return False

        common_prefix_parts = self.common_prefix.split('/')
        if len(common_prefix_parts) > 0 and common_prefix_parts[-1] == '':
            common_prefix_parts = common_prefix_parts[:-1]

        if num_subjects == 1 and subjectNames[0] == '':
            self.inferred_as_single_subject = True
            self.inferred_dataset_name = common_prefix_parts[-2] if len(
                common_prefix_parts) > 1 else ''
            self.inferred_subject_name = common_prefix_parts[-1] if len(
                common_prefix_parts) > 0 else ''
        else:
            self.inferred_as_single_subject = False
            self.inferred_subject_name = ''
            self.inferred_dataset_name = common_prefix_parts[-1] if len(
                common_prefix_parts) > 0 else ''

        if verbose:
            print(f'Parsed {num_subjects} subjects with {num_trials} trials')

        return True

    def attempt_parse_subject_as_osim_standard_folder(self) -> bool:
        # TODO: implement this
        return False

    def confirm_with_user(self, s3_prefix: str) -> bool:
        print('We are about to upload the following files:')
        for s3_key, local_path in self.s3_to_local_file.items():
            s3_key = s3_prefix + s3_key
            print(f' > {local_path} to {s3_key}')
        for s3_key in self.s3_ready_flags:
            s3_key = s3_prefix + s3_key
            print(f' > {s3_key}')
        print('Is that ok?')
        return input('y/n: ') == 'y'


class UploadCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        process_parser = subparsers.add_parser(
            'upload', help='Upload data to AddBiomechanics to process. This command attempts to be smart about auto-detecting the common structures of datasets on disk.')
        process_parser.add_argument(
            'dataset_path', type=str, help='The path to the folder containing the data you wish to process')
        process_parser.add_argument('-t', '--target_path', type=str, default='',
                                    help='This is the path on AddBiomechanics where the data will be uploaded. If not specified, we will guess based on the dataset path')
        process_parser.add_argument('-o', '--opensim_unscaled', type=str, default='vicon',
                                    help='Either "vicon" or "cmu" (to use a preset Rajagopal model with markerset), or a path to the unscaled *.OSIM file you would like to use to fit the data')
        process_parser.add_argument('-u', '--unscaled_model', type=str, default=None,
                                    help='This is the path to the unscaled model you would like to use to fit all the data. If specified, this will override any other unscaled models found with the data.')
        process_parser.add_argument('-m', '--height_m', type=float, default=1.68,
                                    help='The height of the subject, in meters')
        process_parser.add_argument('-k', '--mass_kg', type=float, default=68.0,
                                    help='The mass of the subject, in kilograms')
        process_parser.add_argument('-s', '--sex', type=str, choices=[
                                    'male', 'female', 'unknown'], default='unknown', help='The biological sex of the subject')
        process_parser.add_argument('-b', '--foot_body_names', type=List[str], default=['calcn_r', 'calcn_l'],
                                    help='The names of the bodies in the model that will be used to fit the GRF data. See the AddBiomechanics paper for more details about how these bodies are used.')
        process_parser.add_argument('-f', '--filter_out_trials', type=str, default='',
                                    help='Trials will be excluded from the upload if they contain this string in their name')
        process_parser.add_argument('-n', '--subject_name', type=str, default='',
                                    help='The name of the subject. If not specified, we will guess based on the dataset path')
        process_parser.add_argument('-d', '--dataset_name', type=str, default='',
                                    help='The name of the dataset to include the subject in on AddBiomechanics. If not specified, we will guess based on the dataset path')
        process_parser.add_argument('-y', '--yes', type=bool, default=False,
                                    help='This skips the manual confirmation step')
        pass

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'upload':
            return

        session: boto3.Session = ctx.aws_session
        deployment: Dict[str, str] = ctx.deployment
        user_email: str = ctx.user_email
        dataset_path: str = args.dataset_path
        target_path: str = args.target_path
        opensim_unscaled: str = args.opensim_unscaled
        filter_out_trials: str = args.filter_out_trials
        subject_name: str = args.subject_name
        dataset_name: str = args.dataset_name
        subject_height_m: float = args.height_m
        subject_weight_kg: float = args.mass_kg
        subject_sex: str = args.sex
        foot_body_names: List[str] = args.foot_body_names
        skip_confirm: bool = args.yes

        dir_files: List[str] = []

        # Get the list of files in the dataset
        for root, dirs, files in os.walk(dataset_path):
            for file in files:
                dir_files.append(os.path.join(root, file))

        structure = ParserFolderStructure(dir_files)
        if structure.attempt_parse_as_preformatted_dataset(verbose=True, override_osim_file=opensim_unscaled, filter_out_trials=filter_out_trials):
            print('Detected pre-formatted dataset')
        else:
            print('Failed to parse folder as pre-formatted dataset')

        # Compute the prefix for S3
        prefix = 'protected/'+ctx.user_identity_id + '/data/'
        if target_path != '':
            prefix += target_path
            if not target_path.endswith('/'):
                prefix += '/'
        dataset_name = dataset_name if dataset_name != '' else structure.inferred_dataset_name
        if structure.inferred_as_single_subject:
            subject_name = subject_name if subject_name != '' else structure.inferred_subject_name
            prefix += dataset_name + \
                '/' + subject_name + '/'
        else:
            prefix += dataset_name + '/'

        if structure.confirm_with_user(prefix):
            print('Uploading...')
            upload_files(ctx, structure.s3_to_local_file,
                         structure.s3_to_contents, structure.s3_ready_flags, prefix)
