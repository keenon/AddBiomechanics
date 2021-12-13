import os
from .pubsub import PubSub
import boto3
import json
import time
import tempfile
from typing import Dict, List, Set, Callable, Any

BUCKET_NAME = 'biomechanics-uploads161949-dev'


class FileMetadata:
    key: str
    lastModified: int
    size: int

    def __init__(self, key: str, lastModified: int, size: int) -> None:
        self.key = key
        self.lastModified = lastModified
        self.size = size

    def __str__(self) -> str:
        return "<"+self.key+", "+str(self.size)+">"

    def __repr__(self) -> str:
        return "<"+self.key+", "+str(self.size)+"b, "+str(self.lastModified)+"ms>"


class ReactiveS3Index:
    pubSub: PubSub
    files: Dict[str, FileMetadata]
    changeListeners: List[Callable]

    def __init__(self) -> None:
        self.s3_low_level = boto3.client('s3', region_name='us-west-2')
        self.s3 = boto3.resource('s3', region_name='us-west-2')
        self.bucket = self.s3.Bucket(BUCKET_NAME)
        self.pubSub = PubSub()
        self.files = {}
        self.changeListeners = []

    def registerPubSub(self) -> None:
        """
        This registers a PubSub listener
        """
        self.pubSub.subscribe("/UPDATE/#", self._onUpdate)
        self.pubSub.subscribe("/DELETE/#", self._onDelete)

    def refreshIndex(self) -> None:
        """
        This updates the index
        """
        for object in self.bucket.objects.all():
            key: str = object.key
            lastModified: int = object.last_modified.timestamp() * 1000
            size: int = object.size
            file = FileMetadata(key, lastModified, size)
            self.files[key] = file
        self._onRefresh()

    def listAllFolders(self) -> Set[str]:
        """
        This parses the different file names, and lists all virtual folders implied by the paths, along with all real folders
        """
        folders: Set[str] = set()
        for path in self.files:
            cursor = -1
            while True:
                try:
                    cursor = path.index('/', cursor+1)
                    subPath = path[:cursor]
                    # End all files/folders with a slash
                    if len(subPath) > 0 and subPath[-1] != '/':
                        subPath += '/'
                    folders.add(subPath)
                except ValueError:
                    # the slash was not found
                    folders.add(path)
                    break
        return folders

    def exists(self, path: str) -> bool:
        return path in self.files

    def getMetadata(self, path: str) -> FileMetadata:
        return self.files[path]

    def getChildren(self, folder: str) -> Dict[str, FileMetadata]:
        """
        This returns a list of all the children of a given folder
        """
        children: Dict[str, FileMetadata] = {}
        for path in self.files:
            if path.startswith(folder) and path != folder:
                subPath = path[len(folder):]
                children[subPath] = self.files[path]
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
                        key=folderName, lastModified=allChildren[key].lastModified, size=allChildren[key].size)
        return immediateChildren

    def hasChildren(self, folder: str, subPaths: List[str]) -> bool:
        """
        This returns True if a given folder has the listed children, and False otherwise
        """
        children: Dict[str, FileMetadata] = self.getChildren(folder)
        for path in subPaths:
            foundChild = False
            for key in children:
                if key.startswith(path):
                    foundChild = True
                    break
            if not foundChild:
                return False
        return True

    def addChangeListener(self, listener: Callable) -> None:
        self.changeListeners.append(listener)

    def makeTopicPubSubSafe(self, path: str) -> str:
        MAX_TOPIC_LEN = 80
        if (len(path) > MAX_TOPIC_LEN):
            segments = path.split("/")
            if (len(segments[0]) > MAX_TOPIC_LEN):
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

    def uploadFile(self, bucketPath: str, localPath: str):
        """
        This uploads a local file to a given spot in the bucket
        """
        print('uploading file '+localPath+' to '+bucketPath)
        self.s3.Object(BUCKET_NAME, bucketPath).put(
            Body=open(localPath, 'rb'))
        self.pubSub.sendMessage(
            self.makeTopicPubSubSafe("/UPDATE/"+bucketPath), {'key': bucketPath, 'lastModified': time.time() * 1000, 'size': os.path.getsize(localPath)})

    def uploadText(self, bucketPath: str, text: str):
        """
        This uploads text to the file at this path
        """
        self.s3.Object(BUCKET_NAME, bucketPath).put(Body=text)
        self.pubSub.sendMessage(
            self.makeTopicPubSubSafe("/UPDATE/"+bucketPath), {'key': bucketPath, 'lastModified': time.time() * 1000, 'size': len(text.encode('utf-8'))})

    def uploadJSON(self, contents: Dict[str, Any]):
        """
        This uploads JSON back to S3
        """
        j = json.dumps(contents)
        self.uploadText(j)

    def delete(self, bucketPath: str):
        """
        This deletes a file from S3
        """
        if not self.exists(bucketPath):
            return bytearray()
        self.root.s3.Object(BUCKET_NAME, bucketPath).delete()
        self.pubSub.sendMessage(
            self.makeTopicPubSubSafe("/DELETE/"+bucketPath), {'key': bucketPath})

    def download(self, bucketPath: str, localPath: str) -> None:
        print('downloading file '+bucketPath+' into '+localPath)
        self.bucket.download_file(bucketPath, localPath)

    def downloadToTmp(self, bucketPath: str) -> str:
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
                self.bucket.download_file(bucketPath + k, path + k)
            return path

    def getText(self, bucketPath: str) -> bytes:
        """
        This downloads the contents of the file as a byte array. If the file is a folder, returns an empty byte array
        """
        if not self.exists(bucketPath):
            return bytearray()
        return self.root.s3.Object(BUCKET_NAME, bucketPath).get()['Body'].read()

    def getJSON(self, bucketPath: str) -> Dict[str, Any]:
        return json.loads(self.getText(bucketPath))

    def _onUpdate(self, topic: str, payload: bytes) -> None:
        """
        We received a PubSub message telling us a file was created
        """
        body = json.loads(payload)
        key: str = body['key']
        lastModified: int = body['lastModified']
        size: int = body['size']
        file = FileMetadata(key, lastModified, size)
        print("onUpdate() file: "+str(file))
        self.files[key] = file
        self._onRefresh()

    def _onDelete(self, topic: str, payload: bytes) -> None:
        """
        We received a PubSub message telling us a file was deleted
        """
        body = json.loads(payload)
        key: str = body['key']
        print("onDelete() key: "+str(key))
        if key in self.files:
            del self.files[key]
            self._onRefresh()

    def _onRefresh(self) -> None:
        """
        Iterate through all the files in the bucket, looking for updates
        """
        for listener in self.changeListeners:
            listener()
