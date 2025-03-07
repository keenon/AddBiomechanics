import argparse
import os
from reactive_s3 import ReactiveS3Index, FileMetadata
from typing import Dict, List
import time
import nimblephysics as nimble
from nimblephysics import absPath
import json
import shutil
import hashlib
import multiprocessing
import time
import traceback

# ===================== CONSTANTS =====================
GEOMETRY_FOLDER_PATH = absPath('../../data/Geometry')
DATA_FOLDER_PATH = absPath('../../data')
MIN_TRIAL_LENGTH = 15  # trials with timesteps shorter than this will be removed
# =====================================================


class StandardizedDataset:
    """
    This class represents a dataset that has been standardized to a common skeleton, and exists on S3.

    Our goal is to keep this dataset complete and up-to-date with existing uploads.
    """
    s3_root_path: str
    osim_model_path: str

    def __init__(self, s3_root_path: str, osim_model_path: str) -> None:
        self.s3_root_path = s3_root_path
        self.osim_model_path = osim_model_path


class SubjectSnapshot:
    """
    We want to snapshot subjects, and copy every useful snapshot over to the new folder.
    """
    index: ReactiveS3Index
    path: str

    def __init__(self, index: ReactiveS3Index, path: str) -> None:
        self.index = index
        self.path = path

    def get_unique_hash(self) -> str:
        """
        This function gets the eTag value for every file in the subject folder, and then hashes them together using an
        order-independent hash.
        """
        children: Dict[str, FileMetadata] = self.index.getChildren(self.path)
        hashes = []
        for key in children:
            # We only want to hash the input files, not any of the results files
            if key.endswith(".osim") \
                    or key.endswith(".trc") \
                    or key.endswith(".mot") \
                    or key.endswith(".c3d") \
                    or key.endswith("_subject.json"):
                hashes.append(children[key].eTag)
        hashes.sort()

        # Create a hash object using SHA-256 algorithm
        hash_object = hashlib.sha256()

        # Update the hash with the encoded representation of the frozenset
        hash_object.update(str(hashes).encode())

        # Get the hexadecimal representation of the hash
        hash_hex = hash_object.hexdigest()

        return hash_hex

    def get_target_path(self, dataset: StandardizedDataset) -> str:
        """
        This returns the path on S3 where we're going to copy this subject to
        """
        return dataset.s3_root_path + '/' + self.path + self.get_unique_hash()

    def has_snapshots_to_copy(self, datasets: List[StandardizedDataset]) -> List[StandardizedDataset]:
        return [dataset for dataset in datasets if not self.dataset_up_to_date(dataset)]

    def dataset_up_to_date(self, dataset: StandardizedDataset) -> bool:
        """
        This function checks if the dataset contains the current snapshot, in full.

        This is more complex than simply checking if the folder exists, because we want to make sure that the folder
        contents are complete. Because this process can be killed at any time, there may be a partial upload that was
        cancelled when still incomplete, and if that happens we need to re-translate the data.
        """
        # If we've already tried to copy this dataset, but there's some reason we can't (like it's missing critical
        # data), then report that here as being "up to date", because it's impossible to copy over.
        if self.index.exists(self.get_target_path(dataset) + '/INCOMPATIBLE'):
            return True
        # Check if the root folder exists
        if not (self.index.exists(self.get_target_path(dataset)) or
                len(self.index.getChildren(self.get_target_path(dataset)+'/')) > 0):
            return False
        # Check if all the files exist
        for child in self.index.getChildren(self.path):
            if not self.index.exists(self.get_target_path(dataset) + '/' + child):
                if child == 'READY_TO_PROCESS' or \
                    child.endswith('.osim') or \
                        child.endswith('.mot') or \
                        child.endswith('.trc') or \
                        child.endswith('.c3d') or \
                        child.endswith('_subject.json'):
                    print('Detected that dataset '+dataset.s3_root_path+' was incompletely uploaded! Missing file ' +
                          self.get_target_path(dataset) + '/' + child)
                    return False
        # If we make it through all these checks
        return True

    def copy_snapshots(self, datasets: List[StandardizedDataset]):
        """
        This function downloads the subject data, translates it to the standard skeleton, and re-uploads it to S3
        """

        # First filter the datasets to just the ones we want to copy
        datasets = self.has_snapshots_to_copy(datasets)
        if len(datasets) == 0:
            return

        # Download the dataset locally
        tmp_folder: str = self.index.download_to_tmp(self.path)

        # Identify trials that are too short. We don't want to process these
        trial_paths_to_remove: List[str] = self.id_short_trials(tmp_folder)

        # Remove those trials from tmp folder
        for trial in trial_paths_to_remove:
            trial_folder = os.path.dirname(trial)
            try:
                shutil.rmtree(trial_folder)
            except OSError as e:
                print(f"Error: {e}")

        # Prepare the original skeleton model for translation step
        self.prep_unscaled_skeleton(tmp_folder)

        for dataset in datasets:
            print('Copying to Dataset: ' + dataset.s3_root_path)

            # 1. Translate the skeleton
            # 1.1. Download the target skeleton
            if os.path.exists(tmp_folder + 'target_skeleton.osim'):
                os.remove(tmp_folder + 'target_skeleton.osim')
            self.index.download(dataset.osim_model_path,
                                tmp_folder + 'target_skeleton.osim')

            # Check if the original model is compatible with the target model
            target_model = nimble.biomechanics.OpenSimParser.parseOsim(
                tmp_folder + 'target_skeleton.osim')
            if nimble.biomechanics.OpenSimParser.hasArms(target_model.skeleton):
                source_model = nimble.biomechanics.OpenSimParser.parseOsim(
                    tmp_folder + 'original_model.osim')
                if not nimble.biomechanics.OpenSimParser.hasArms(source_model.skeleton):
                    print('Detected that the target skeleton has arms, but the original skeleton does not. This is not'
                          ' supported, because we will not have any marker data to move the arms during simulation.')
                    self.index.uploadText(self.get_target_path(
                        dataset) + '/INCOMPATIBLE', '')
                    continue

            # 1.2. Translate the skeleton
            print('Translating markers to target skeleton at ' +
                  dataset.osim_model_path)
            try:
                markers_guessed, markers_missing = nimble.biomechanics.OpenSimParser.translateOsimMarkers(
                    tmp_folder + 'original_model.osim',
                    tmp_folder + 'target_skeleton.osim',
                    tmp_folder + 'unscaled_generic.osim',
                    verbose=True)
                print('Markers guessed: ' + str(markers_guessed))
                print('Markers missing: ' + str(markers_missing))
                target_path = self.get_target_path(dataset)
                print('Re-uploading to ' + target_path)
                # Write the data about how the translation was done to the new folder
                translation_data = {'markersGuessed': markers_guessed,
                                    'markersMissing': markers_missing,
                                    'targetSkeleton': dataset.osim_model_path,
                                    'originalFolder': self.path,
                                    'snapshotDate': time.strftime("%Y-%m-%d %H:%M:%S",
                                                                  time.gmtime())}

                # 2. UPLOADING
                # 2.1. Upload the skeleton translation output
                self.index.uploadText(
                    target_path + '/_translation.json', json.dumps(translation_data))

                # 2.2. Upload every file in the tmpFolder (excluding filtered out trials)
                for root, dirs, files in os.walk(tmp_folder):
                    for file in files:
                        if file.endswith('.osim') or file.endswith('.trc') or file.endswith('.mot') or file.endswith(
                                '.c3d') or file.endswith('_subject.json'):
                            relative_path = os.path.relpath(root, tmp_folder)
                            full_path = file if relative_path == '.' else os.path.join(
                                relative_path, file)
                            print('Uploading ' + full_path)
                            self.index.uploadFile(
                                target_path + '/'+full_path, os.path.join(root, file))

                # Mark the subject as ready to process
                self.index.uploadText(target_path + '/READY_TO_PROCESS', '')

            except Exception as e:
                print('Got an exception when trying to process dataset ' +
                      self.path+' to '+dataset.s3_root_path)
                print(e)
                self.index.uploadText(self.get_target_path(
                    dataset) + '/INCOMPATIBLE', '')

        print('Finished uploading processed datasets')
        # Delete the tmp folder
        os.system('rm -rf ' + tmp_folder)

    @staticmethod
    def id_short_trials(tmp_folder: str) -> List[str]:
        # Collect markers files corresponding to trials that are too short
        trials_folder = os.path.join(tmp_folder, 'trials/')
        trial_paths_to_remove: List[str] = []
        for root, dirs, files in os.walk(trials_folder):
            for file in files:
                local_filepath = os.path.join(root, file)
                if file.endswith('.trc'):
                    trc_file = nimble.biomechanics.OpenSimParser.loadTRC(local_filepath)
                    if len(trc_file.timestamps) < MIN_TRIAL_LENGTH:
                        trial_paths_to_remove.append(local_filepath)
                elif file.endswith('.c3d'):
                    c3d_file = nimble.biomechanics.C3DLoader.loadC3D(local_filepath)
                    if len(c3d_file.timestamps) < MIN_TRIAL_LENGTH:
                        trial_paths_to_remove.append(local_filepath)
        return trial_paths_to_remove

    @staticmethod
    def prep_unscaled_skeleton(tmp_folder: str):
        skeleton_preset = 'vicon'
        if os.path.exists(tmp_folder + '_subject.json'):
            subject_json = json.load(open(tmp_folder + '_subject.json'))
            if 'skeletonPreset' in subject_json:
                skeleton_preset = subject_json['skeletonPreset']
                # Ensure that the _subject.json file is set to custom for the upload in the standardized folder
                subject_json['skeletonPreset'] = 'custom'
                json.dump(subject_json, open(tmp_folder + '_subject.json', 'w'))
        if skeleton_preset == 'vicon':
            shutil.copy(DATA_FOLDER_PATH + '/PresetSkeletons/Rajagopal2015_ViconPlugInGait.osim',
                        tmp_folder + 'unscaled_generic.osim')
        elif skeleton_preset == 'cmu':
            shutil.copy(DATA_FOLDER_PATH + '/PresetSkeletons/Rajagopal2015_CMUMarkerSet.osim',
                        tmp_folder + 'unscaled_generic.osim')
        elif skeleton_preset == 'complete':
            shutil.copy(DATA_FOLDER_PATH + '/PresetSkeletons/CompleteHumanModel.osim',
                        tmp_folder + 'unscaled_generic.osim')
        else:
            if skeleton_preset != 'custom':
                print('Unrecognized skeleton preset "' + str(skeleton_preset) +
                      '"! Behaving as though this is "custom"')
            if not os.path.exists(tmp_folder + 'unscaled_generic.osim'):
                raise FileNotFoundError('We are using a custom OpenSim skeleton, but there is no unscaled_generic.osim '
                                        'file present.')
        # Now move the "unscaled_generic.osim" to get ready to translate its markerset to the target model
        shutil.move(tmp_folder + 'unscaled_generic.osim',
                    tmp_folder + 'original_model.osim')
        # Symlink in Geometry, if it doesn't come with the folder, so we can load meshes for the visualizer.
        if not os.path.exists(tmp_folder + 'Geometry'):
            os.symlink(GEOMETRY_FOLDER_PATH, tmp_folder + 'Geometry')
        print('Downloaded to ' + tmp_folder)

    def mark_incompatible(self, datasets: List[StandardizedDataset]):
        # First filter the datasets to just the ones we want to copy
        datasets = self.has_snapshots_to_copy(datasets)
        if len(datasets) == 0:
            return

        for dataset in datasets:
            print('Marking dataset as incompatible: ' + dataset.s3_root_path)
            self.index.uploadText(self.get_target_path(
                dataset) + '/INCOMPATIBLE', '')
        print('Finished marking datasets as incompatible')


class DataHarvester:
    """
    Raw data uploaded to AddBiomechanics has several problems:
    (1) It is uses whatever skeleton the user has uploaded, which means it is largely not comparable across subjects
    (2) When users delete the data, it is really gone forever, and we don't keep a backup

    To resolve these issues, this class will:
    (1) Scan for new data uploaded to S3
    (2) Download the data, translate the skeleton to the standard skeleton, and re-upload it to S3 under a protected
    partition
    """
    bucket: str
    deployment: str
    index: ReactiveS3Index
    queue: List[SubjectSnapshot]
    datasets: List[StandardizedDataset]

    def __init__(self, bucket: str, deployment: str, disable_pubsub: bool) -> None:
        self.bucket = bucket
        self.deployment = deployment
        self.queue = []
        self.datasets = []
        self.index = ReactiveS3Index(bucket, deployment, disable_pubsub)
        self.index.refreshIndex()
        if not disable_pubsub:
            self.index.register_pub_sub()

    def recompute_queue(self):
        start_time = time.time()
        # 1. Collect all Trials
        new_queue: List[SubjectSnapshot] = []
        new_datasets: List[StandardizedDataset] = []
        for folder in self.index.listAllFolders():
            # We want to collect all the dataset targets that we're supposed to be copying data to, in case
            # those have been updated
            if folder.startswith('standardized'):
                if folder.endswith('/'):
                    folder = folder[:-1]
                parts = folder.split('/')
                if len(parts) == 2:
                    children = self.index.getImmediateChildren(folder+'/')
                    osim_files = [x for x in children if x.endswith('.osim')]
                    if len(osim_files) == 1:
                        new_datasets.append(StandardizedDataset(
                            folder+'/data', folder + '/' + osim_files[0]))
                    else:
                        print('Found a dataset target with ' + str(len(osim_files)) +
                              ' osim files, expected 1. Ignoring it as a target for copying data.')
            # We want to collect all the subjects with data people have uploaded, except for data
            # in people's private folders.
            elif not folder.startswith('private'):
                if self.index.hasChildren(folder, ['trials/', '_subject.json']):
                    if not folder.endswith('/'):
                        folder += '/'
                    subject = SubjectSnapshot(self.index, folder)
                    new_queue.append(subject)

        print('Updating datasets to have ' + str(len(new_datasets)) + ' items')
        self.datasets = new_datasets
        new_queue = [entry for entry in new_queue if len(
            entry.has_snapshots_to_copy(self.datasets)) > 0]
        print('Updating queue to have ' + str(len(new_queue)) + ' items')
        self.queue = new_queue

        print('Queue updated in ' + str(time.time() - start_time) + ' seconds')
        print('Queue length: '+str(len(self.queue)))

    def process_queue_forever(self):
        """
        This busy-waits on the queue updating, and will process the head of the queue one at a time when it
        becomes available.

        While processing, this blocks, so even though the queue is updating in the background, that shouldn't change
        the outcome of this process.
        """
        print('Starting processing queue.')
        print('Computing inital queue...')
        start_time = time.time()
        self.recompute_queue()
        print('[PERFORMANCE] Initial queue computed in ' + str(time.time() - start_time) + ' seconds')
        print('Queue length: '+str(len(self.queue)))
        while True:
            try:
                # First, we process the queue of PubSub messages that the index has received since the last time we
                # checked.
                print('Processing incoming messages...')
                start_time = time.time()
                any_changed = self.index.process_incoming_messages()
                print('[PERFORMANCE] Processed incoming messages in ' + str(time.time() - start_time) + ' seconds')
                if any_changed:
                    print('Incoming messages changed the state of the index, recomputing queue')
                    start_time = time.time()
                    self.recompute_queue()
                    print('[PERFORMANCE] Recomputed queue in ' + str(time.time() - start_time) + ' seconds')

                if len(self.queue) > 0:
                    print('Processing queue: ' +
                          str(len(self.queue)) + ' items remaining')
                    # Create a new process to handle the copy_snapshots call, to shield the server from segfaults in
                    # Nimble as it is attempting to convert whatever crazy raw OpenSim file the user has uploaded into
                    # our standard skeletons.
                    p = multiprocessing.Process(target=self.copy_snashots_other_process_entry_point, args=(self.queue[0],))
                    p.start()  # Start the process
                    p.join()  # Wait for the process to complete
                    # Check the process exit code (0 means success)
                    if p.exitcode == 0:
                        print('Snapshot copied successfully.')
                    else:
                        print('Error in copying snapshots. Exit code:', p.exitcode)
                        # We will mark this dataset as incompatible, because we can't process it. This will prevent
                        # us from trying to process it again in the future.
                        try:
                            self.queue[0].mark_incompatible(self.datasets)
                        except Exception as e2:
                            print('Got an exception when trying to mark dataset as incompatible ' +
                                  self.queue[0].path)
                            print('Caught exception in mark_incompatible(): '+str(e2))
                            traceback.print_exc()  # Print the traceback
                            print('We will now quit, because it is pointless to keep looping on this dataset')
                            break

                    self.queue.pop(0)  # Remove the processed item from the queue

            except Exception as e:
                print('Caught overall processing loop exception: '+str(e))
                traceback.print_exc()  # Print the traceback
            time.sleep(1)

    def copy_snashots_other_process_entry_point(self, dataset):
        """
        Method to call copy_snapshots in a separate process, so that if it segfaults, it doesn't take down the whole
        server. The server can then mark the dataset as incompatible, and move on.
        """
        try:
            dataset.copy_snapshots(self.datasets)
        except Exception as e:
            print(f'Got an exception when trying to process dataset {dataset.path}')
            print(e)
            try:
                dataset.mark_incompatible(self.datasets)
            except Exception as e2:
                print(f'Got an exception when trying to mark dataset as incompatible {dataset.path}')
                print(e2)
                raise Exception('Critical error, terminating process')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run a data harvesting daemon.')
    parser.add_argument('--bucket', type=str, default="biomechanics-uploads161949-dev",
                        help='The S3 bucket to access user data in')
    parser.add_argument('--deployment', type=str,
                        default='DEV',
                        help='The deployment to target (must be DEV or PROD)')
    parser.add_argument('--disable-pubsub', type=bool,
                        default=False,
                        help='Set this to true to disable the pubsub S3 change listener')
    args = parser.parse_args()

    # 1. Launch a harvesting server
    server = DataHarvester(args.bucket, args.deployment, args.disable_pubsub)

    # 2. Run forever
    server.process_queue_forever()
