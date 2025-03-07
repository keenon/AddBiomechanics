import os
from .pubsub import PubSub
import boto3
import json
import time
import tempfile
from typing import Dict, List, Set, Callable, Any
import threading
from datetime import datetime


class FileMetadata:
    key: str
    lastModified: int
    size: int
    eTag: str

    def __init__(self, key: str, lastModified: int, size: int, eTag: str) -> None:
        self.key = key
        self.lastModified = lastModified
        self.size = size
        self.eTag = eTag

    def __str__(self) -> str:
        return "<"+self.key+", "+str(self.size)+">"

    def __repr__(self) -> str:
        return "<"+self.key+", "+str(self.size)+"b, "+str(self.lastModified)+"ms>"


def makeTopicPubSubSafe(path: str) -> str:

    # Check if the path contains a user ID by searching for the ":" character.
    # If it does, then keep the topic up to the user ID and discard the rest.
    if path.find(":") != -1:
        segments = path.split(":")
        path = segments[0] + ":" + segments[1].split("/")[0]

    MAX_TOPIC_LEN = 80
    if len(path) > MAX_TOPIC_LEN:
        segments = path.split("/")

        if len(segments[0]) > MAX_TOPIC_LEN:
            return segments[0][0:MAX_TOPIC_LEN]

        reconstructed = ''
        segmentCursor = 0
        while segmentCursor < len(segments):
            proposedNext = reconstructed
            if segmentCursor > 0:
                proposedNext += '/'
            proposedNext += segments[segmentCursor]
            segmentCursor += 1

            if len(proposedNext) < MAX_TOPIC_LEN:
                reconstructed = proposedNext
            else:
                break
        return reconstructed
    return path


class ReactiveS3Index:
    disable_pubsub: bool
    pubSub: PubSub
    files: Dict[str, FileMetadata]
    children: Dict[str, List[str]]
    bucketName: str
    deployment: str
    lock: threading.Lock

    def __init__(self, bucket: str, deployment: str, disable_pubsub = False) -> None:
        self.s3_low_level = boto3.client('s3', region_name='us-west-2')
        self.s3 = boto3.resource('s3', region_name='us-west-2')
        self.lock = threading.Lock()
        self.bucketName = bucket
        self.deployment = deployment
        self.bucket = self.s3.Bucket(self.bucketName)
        self.disable_pubsub = disable_pubsub
        if not disable_pubsub:
            try:
                self.pubSub = PubSub(deployment)
            except Exception as e:
                print(e)
                print('PubSub disabled')
                self.disable_pubsub = True
        self.files = {}
        self.children = {}
        self.incomingMessages = []

    # Add pickling support
    def __getstate__(self):
        state = self.__dict__.copy()
        del state['s3_low_level']
        del state['s3']
        del state['lock']
        if 'pubSub' in state:
            del state['pubSub']
        del state['bucket']
        return state

    # Add unpickling support - always unpickle with PubSub disabled, since we don't want multiple instances of the
    # PubSub connection from separate processing threads.
    def __setstate__(self, state):
        self.__dict__.update(state)
        self.s3_low_level = boto3.client('s3', region_name='us-west-2')
        self.s3 = boto3.resource('s3', region_name='us-west-2')
        self.bucket = self.s3.Bucket(self.bucketName)
        self.lock = threading.Lock()
        self.disable_pubsub = True
        self.incomingMessages = []

    def queue_pub_sub_update_message(self, topic: str, payload: bytes) -> None:
        self.incomingMessages.append(('UPDATE', topic, payload))

    def queue_pub_sub_delete_message(self, topic: str, payload: bytes) -> None:
        self.incomingMessages.append(('DELETE', topic, payload))

    def register_pub_sub(self) -> None:
        """
        This registers a PubSub listener
        """
        if self.disable_pubsub:
            return
        self.pubSub.subscribe("/UPDATE/#", self.queue_pub_sub_update_message)
        self.pubSub.subscribe("/DELETE/#", self.queue_pub_sub_delete_message)

        # Make sure we refresh our index when our connection resumes, if our connection was interrupted
        #
        # I think this is actually getting really expensive, because the connection gets interrupted A LOT and the full refresh requires a lot of downloading.
        #
        # self.pubSub.addResumeListener(self.refreshIndex)

    def process_incoming_messages(self) -> bool:
        """
        This processes incoming PubSub messages
        """
        any_changes = False
        while len(self.incomingMessages) > 0:
            message = self.incomingMessages.pop(0)
            if message[0] == 'UPDATE':
                any_changes |= self._onUpdate(message[1], message[2])
            elif message[0] == 'DELETE':
                any_changes |= self._onDelete(message[1], message[2])
        return any_changes

    def load_only_folder(self, folder: str) -> None:
        """
        This updates the index
        """
        print('Loading folder '+folder)
        self.files.clear()
        self.children.clear()
        for object in self.bucket.objects.filter(Prefix=folder):
            key: str = object.key
            lastModified: int = int(object.last_modified.timestamp() * 1000)
            eTag = object.e_tag[1:-1]  # Remove the double quotes around the ETag value
            size: int = object.size
            file = FileMetadata(key, lastModified, size, eTag)
            self.updateChildrenOnAddFile(key)
            self.files[key] = file
        print('Folder load finished!')

    def refreshIndex(self) -> None:
        """
        This updates the index
        """
        print('Doing full index refresh...')
        self.files.clear()
        self.children.clear()
        for object in self.bucket.objects.all():
            key: str = object.key
            lastModified: int = int(object.last_modified.timestamp() * 1000)
            eTag = object.e_tag[1:-1]  # Remove the double quotes around the ETag value
            size: int = object.size
            file = FileMetadata(key, lastModified, size, eTag)
            self.updateChildrenOnAddFile(key)
            self.files[key] = file
        print('Full index refresh finished!')

    def updateChildrenOnAddFile(self, path: str):
        cursor = -1
        subPath = ''
        while True:
            try:
                cursor = path.index('/', cursor+1)
                subPath = path[:cursor]
                # End all files/folders with a slash
                if len(subPath) > 0 and subPath[-1] != '/':
                    subPath += '/'
                if subPath not in self.children:
                    self.children[subPath] = []
                self.children[subPath].append(path)
            except ValueError:
                # the slash was not found
                break

    def updateChildrenOnRemoveFile(self, path: str):
        cursor = -1
        subPath = ''
        while True:
            try:
                cursor = path.index('/', cursor+1)
                subPath = path[:cursor]
                # End all files/folders with a slash
                if len(subPath) > 0 and subPath[-1] != '/':
                    subPath += '/'
                if subPath in self.children and path in self.children[subPath]:
                    self.children[subPath].remove(path)
                    if len(self.children[subPath]) == 0:
                        del self.children[subPath]
            except ValueError:
                # the slash was not found
                break

    def listAllFolders(self) -> Set[str]:
        """
        This parses the different file names, and lists all virtual folders implied by the paths, along with all real folders
        """
        return set(self.children.keys())
        # folders: Set[str] = set()
        # for path in self.files:
        #     cursor = -1
        #     while True:
        #         try:
        #             cursor = path.index('/', cursor+1)
        #             subPath = path[:cursor]
        #             # End all files/folders with a slash
        #             if len(subPath) > 0 and subPath[-1] != '/':
        #                 subPath += '/'
        #             folders.add(subPath)
        #         except ValueError:
        #             # the slash was not found
        #             folders.add(path)
        #             break
        # return folders

    def exists(self, path: str) -> bool:
        return path in self.files

    def getMetadata(self, path: str) -> FileMetadata:
        return self.files[path]

    def getChildren(self, folder: str) -> Dict[str, FileMetadata]:
        """
        This returns a list of all the children of a given folder
        """
        children: Dict[str, FileMetadata] = {}
        if folder in self.children:
            toRemove = []
            for path in self.children[folder]:
                if path != folder:
                    if path in self.files:
                        children[path[len(folder):]] = self.files[path]
                    else:
                        print('DATA SYNCHRONIZATION ISSUE: '+path +
                              ' in children['+folder+'], but not in files. Removing from children['+folder+']', flush=True)
                        toRemove.append(path)
            for path in toRemove:
                self.children[folder].remove(path)
        # for path in self.files:
        #     if path.startswith(folder) and path != folder:
        #         subPath = path[len(folder):]
        #         children[subPath] = self.files[path]
        return children

    def getImmediateChildren(self, folder: str) -> Dict[str, FileMetadata]:
        """
        This returns a list of folders that are children of 'folder'
        """
        allChildren: Dict[str, FileMetadata] = self.getChildren(folder)
        immediateChildren: Dict[str, FileMetadata] = {}
        for key in allChildren:
            pathParts: List[str] = key.split('/')
            if len(pathParts) > 0:
                folderName = pathParts[0]
                if folderName in immediateChildren:
                    immediateChildren[folderName].size += allChildren[key].size
                    immediateChildren[folderName].lastModified = max(
                        allChildren[key].lastModified, immediateChildren[folderName].lastModified)
                else:
                    immediateChildren[folderName] = FileMetadata(
                        key=folderName, lastModified=allChildren[key].lastModified, size=allChildren[key].size, eTag=allChildren[key].eTag)
        return immediateChildren

    def hasChildren(self, folder: str, subPaths: List[str]) -> bool:
        """
        This returns True if a given folder has the listed children, and False otherwise
        """
        children: Dict[str, FileMetadata] = self.getChildren(folder)
        for path in subPaths:
            foundChild = False
            if len(subPaths) == 1 and subPaths[0] == 'INCOMPATIBLE':
                print('Checking for '+path+' in '+str(children.keys()))
            for key in children:
                if key.startswith(path) or key.startswith('/'+path):
                    foundChild = True
                    break
            if not foundChild:
                return False
        return True

    def uploadFile(self, bucketPath: str, localPath: str):
        """
        This uploads a local file to a given spot in the bucket
        """
        print('uploading file '+localPath+' to '+bucketPath)
        self.s3.Object(self.bucketName, bucketPath).put(
            Body=open(localPath, 'rb'))
        if 'pubSub' in self.__dict__ and self.pubSub is not None:
            topic = makeTopicPubSubSafe("/UPDATE/"+bucketPath)
            body = {'key': bucketPath, 'lastModified': time.time() * 1000, 'size': os.path.getsize(localPath)}
            self.queue_pub_sub_update_message(topic, json.dumps(body).encode('utf-8'))
            self.pubSub.publish(topic, body)

    def uploadText(self, bucketPath: str, text: str):
        """
        This uploads text to the file at this path
        """
        self.s3.Object(self.bucketName, bucketPath).put(Body=text)
        if 'pubSub' in self.__dict__ and self.pubSub is not None:
            topic = makeTopicPubSubSafe("/UPDATE/"+bucketPath)
            body = {'key': bucketPath, 'lastModified': time.time() * 1000, 'size': len(text.encode('utf-8'))}
            self.queue_pub_sub_update_message(topic, json.dumps(body).encode('utf-8'))
            self.pubSub.publish(topic, body)

    def uploadJSON(self, bucketPath: str, contents: Dict[str, Any]):
        """
        This uploads JSON back to S3
        """
        j = json.dumps(contents)
        self.uploadText(bucketPath, j)

    def delete(self, bucketPath: str):
        """
        This deletes a file from S3
        """
        if not self.exists(bucketPath):
            return bytearray()
        self.s3.Object(self.bucketName, bucketPath).delete()
        if 'pubSub' in self.__dict__ and self.pubSub is not None:
            topic = makeTopicPubSubSafe("/DELETE/"+bucketPath)
            body = {'key': bucketPath}
            self.queue_pub_sub_delete_message(topic, json.dumps(body).encode('utf-8'))
            self.pubSub.publish(topic, body)

    def download(self, bucketPath: str, localPath: str) -> None:
        print('downloading file '+bucketPath+' into '+localPath)
        self.bucket.download_file(bucketPath, localPath)

    def download_to_tmp(self, bucketPath: str) -> str:
        """
        This downloads a folder, or a file, creating a temporary folder.
        This returns the temporary file path.
        """
        children = self.getChildren(bucketPath)
        if len(children) == 0:
            # This is a file
            fd, path = tempfile.mkstemp()
            print('downloading file '+bucketPath+' into '+path)
            self.bucket.download_file(bucketPath, path)
            return path
        else:
            path = ''
            # This is a folder
            path = tempfile.mkdtemp()
            print('creating temp folder '+path)
            if len(path) > 0 and path[-1] != '/':
                path += '/'
            if len(bucketPath) > 0 and bucketPath[-1] != '/':
                bucketPath += '/'
            # Actually download the files
            for k in children:
                if k.endswith('.osim') or k.endswith('.mot') or k.endswith('.trc') or k.endswith('.c3d') or k.endswith('_subject.json'):
                    print('Downloading '+bucketPath+k+' to '+path+k)
                    try:
                        folder_path = os.path.dirname(path + k)
                        os.makedirs(folder_path, exist_ok=True)
                        self.bucket.download_file(bucketPath + k, path + k)
                    except Exception as e:
                        print(e)
            return path

    def getText(self, bucketPath: str) -> bytes:
        """
        This downloads the contents of the file as a byte array. If the file is a folder, returns an empty byte array
        """
        if not self.exists(bucketPath):
            return bytearray()
        return self.root.s3.Object(self.bucketName, bucketPath).get()['Body'].read()

    def getJSON(self, bucketPath: str) -> Dict[str, Any]:
        return json.loads(self.getText(bucketPath))

    def _onUpdate(self, topic: str, payload: bytes) -> bool:
        """
        We received a PubSub message telling us a file was created
        """
        body = json.loads(payload)
        key: str = body['key']
        last_modified_str: str = body['lastModified']
        last_modified: int
        try:
            last_modified = int(last_modified_str)
        except ValueError:
            try:
                # Removing 'Z' and manually handling it as UTC
                last_modified_str_utc = last_modified_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(last_modified_str_utc)
                last_modified = int(dt.timestamp() * 1000)
            except ValueError as e:
                print("Error parsing lastModified: "+last_modified_str)
                print(e)
                print('Defaulting to current time')
                last_modified = int(time.time() * 1000)
        size: int = body['size']
        e_tag: str = body['eTag'] if 'eTag' in body else ''
        file = FileMetadata(key, last_modified, size, e_tag)
        print("onUpdate() file: "+str(file))
        self.files[key] = file
        self.updateChildrenOnAddFile(key)
        return True

    def _onDelete(self, topic: str, payload: bytes) -> bool:
        """
        We received a PubSub message telling us a file was deleted
        """
        body = json.loads(payload)
        key: str = body['key']
        print("onDelete() key: "+str(key))
        anyDeleted = False
        if key in self.files:
            self.updateChildrenOnRemoveFile(key)
            del self.files[key]
            anyDeleted = True
        return anyDeleted