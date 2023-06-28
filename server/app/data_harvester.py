import argparse
import os
from reactive_s3 import ReactiveS3Index, FileMetadata
from typing import Dict, List
import time
import threading
import nimblephysics as nimble
from nimblephysics import absPath
import json
import shutil

GEOMETRY_FOLDER_PATH = absPath('../engine/Geometry')
DATA_FOLDER_PATH = absPath('../data')

class SubjectSnapshot:
    """
    We want to snapshot subjects, and copy every useful snapshot over to the new folder.
    """
    index: ReactiveS3Index
    path: str
    target_folder: str
    target_skeleton: str

    def __init__(self, index: ReactiveS3Index, path: str, target_folder: str, target_skeleton: str) -> None:
        self.index = index
        self.path = path
        self.target_folder = target_folder
        self.target_skeleton = target_skeleton

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
        return str(hash(tuple(hashes)))

    def get_target_path(self) -> str:
        """
        This returns the path on S3 where we're going to copy this subject to
        """
        return self.target_folder + '/' + self.path + '/' + self.get_unique_hash()

    def ready_to_snapshot(self):
        return not self.index.exists(self.get_target_path())

    def copy_snapshot(self):
        """
        This function downloads the subject data, translates it to the standard skeleton, and re-uploads it to S3
        """
        tmpFolder: str = self.index.downloadToTmp(self.path)
        print('Downloaded to ' + tmpFolder)
        print('Translating markers to ' + self.target_skeleton)
        shutil.copyfile(self.target_skeleton, tmpFolder + 'target_skeleton.osim')
        shutil.move(tmpFolder + 'unscaled_generic.osim', tmpFolder + 'original_model.osim')
        # 1.2. Symlink in Geometry, if it doesn't come with the folder, so we can load meshes for the visualizer.
        if not os.path.exists(tmpFolder + 'Geometry'):
            os.symlink(GEOMETRY_FOLDER_PATH, tmpFolder + 'Geometry')
        markersGuessed, markersMissing = nimble.biomechanics.OpenSimParser.translateOsimMarkers(
            tmpFolder + 'original_model.osim',
            tmpFolder + 'target_skeleton.osim',
            tmpFolder + 'unscaled_generic.osim',
            verbose=True)
        print('Markers guessed: ' + str(markersGuessed))
        print('Markers missing: ' + str(markersMissing))
        target_path = self.get_target_path()
        print('Re-uploading to ' + target_path)

        # Write the data about how the translation was done to the new folder
        translationData = {'markersGuessed': markersGuessed,
                           'markersMissing': markersMissing,
                           'targetSkeleton': self.target_skeleton,
                           'originalFolder': self.path,
                           'snapshotDate': time.strftime("%Y-%m-%d %H:%M:%S",
                                                         time.gmtime())}
        self.index.uploadText(target_path + '/_translation.json', json.dumps(translationData))

        # Upload every file in the tmpFolder
        for root, dirs, files in os.walk(tmpFolder):
            for file in files:
                if file.endswith('.osim') or file.endswith('.trc') or file.endswith('.mot') or file.endswith(
                        '.c3d') or file.endswith('_subject.json'):
                    print('Uploading ' + file)
                    self.index.uploadFile(target_path + '/' + file, os.path.join(root, file))

        # Delete the tmp folder
        os.system('rm -rf ' + tmpFolder)

        # Mark the subject as ready to process
        self.index.uploadText(target_path + '/READY_TO_PROCESS', '')


class DataHarvester:
    """
    Raw data uploaded to AddBiomechanics has several problems:
    (1) It is uses whatever skeleton the user has uploaded, which means it is largely not comparable across subjects
    (2) When users delete the data, it is really gone forever, and we don't keep a backup

    To resolve these issues, this class will:
    (1) Scan for new data uploaded to S3
    (2) Download the data, translate the skeleton to the standard skeleton, and re-upload it to S3 under a protected partition
    """
    bucket: str
    deployment: str
    target_folder: str
    target_skeleton: str
    index: ReactiveS3Index
    queue: List[SubjectSnapshot]

    def __init__(self, bucket: str, deployment: str, target_folder: str, target_skeleton: str, disable_pubsub: bool) -> None:
        self.bucket = bucket
        self.deployment = deployment
        self.target_folder = target_folder
        self.target_skeleton = target_skeleton
        self.queue = []
        self.index = ReactiveS3Index(bucket, deployment, disable_pubsub)
        self.index.addChangeListener(self.onChange)
        self.index.refreshIndex()
        if not disable_pubsub:
            self.index.registerPubSub()

    def onChange(self):
        print('S3 CHANGED!')

        # 1. Collect all Trials
        new_queue: List[SubjectSnapshot] = []
        for folder in self.index.listAllFolders():
            if self.index.hasChildren(folder, ['trials/', '_subject.json']):
                if not folder.endswith('/'):
                    folder += '/'
                subject = SubjectSnapshot(self.index, folder, self.target_folder, self.target_skeleton)
                if subject.ready_to_snapshot():
                    print('Ready to snapshot: ' + str(subject.path))
                    new_queue.append(subject)

        print('Updating queue to have ' + str(len(new_queue)) + ' items')
        self.queue = new_queue

    def processQueueForever(self):
        """
        This busy-waits on the queue updating, and will process the head of the queue one at a time when it becomes available.

        While processing, this blocks, so even though the queue is updating in the background, that shouldn't change the outcome of this process.
        """
        while True:
            try:
                if len(self.queue) > 0:
                    print('Processing queue: ' + str(len(self.queue)) + ' items remaining')
                    self.queue[0].copy_snapshot()
                    self.queue.pop(0)
            except Exception as e:
                print(e)
            time.sleep(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Run a data harvesting daemon.')
    parser.add_argument('target_folder', type=str, default='rajagopal_with_arms',
                        help='The folder where the converted data will be stored')
    parser.add_argument('target_skeleton', type=str, default='data/PresetSkeletons/Rajagopal2015_CMUMarkerSet.osim',
                        help='The OSIM skeleton to convert all the data to')
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
    server = DataHarvester(args.bucket, args.deployment, args.target_folder, args.target_skeleton, args.disable_pubsub)

    # 2. Run forever
    server.processQueueForever()
