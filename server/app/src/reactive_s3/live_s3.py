from __future__ import annotations
import boto3
from typing import Dict, List, Optional, Any
import tempfile
from .pubsub import PubSub
import os
import stat
import shutil
import json
from .reactive_s3_index import makeTopicPubSubSafe

BUCKET_NAME = 'biomechanics-uploads161949-dev'


class LiveS3ContextManager:
    """
    This allows us to perform a `with file.openLocally() as path:` call, handling downloading,
    re-uploading and notifying any changes
    """
    root: LiveS3
    rootFile: LiveS3File
    path: str

    def __init__(self, root: LiveS3, rootFile: LiveS3File):
        self.root = root
        self.rootFile = rootFile
        self.path = ''

    def __enter__(self):
        self.path = self.rootFile.download()
        return self.path

    def __exit__(self, exc_type, exc_value, exc_tb):
        print('cleaning up local files in '+self.path)
        if os.path.isfile(self.path):
            os.remove(self.path)
        elif os.path.isdir(self.path):
            shutil.rmtree(self.path)


class LiveS3File:
    """
    This represents a given folder of S3 data
    """
    name: str
    path: str
    parent: LiveS3File
    parentPath: str
    children: Dict[str, LiveS3File]
    root: LiveS3

    def __init__(self, root: LiveS3, name: str, path: str, parent: LiveS3File):
        self.root = root
        self.name = name
        self.path = path
        self.parent = parent
        if parent is not None:
            self.parentPath = parent.path
        else:
            self.parentPath = '/'
        # Trim any leading prefix
        self.path = self.path[1:] if len(
            self.path) > 0 and self.path[0] == '/' else self.path
        self.children = {}

    def ensureChild(self, pathParts: List[str], createIfNotExists=True) -> LiveS3File:
        """
        This returns the child file at the given path. If the file doesn't exist, it creates one.
        If the file _does_ already exist, then this call has no side effects.
        """
        if len(pathParts) == 0:
            return self
        else:
            nextPath: str = pathParts[0]
            if nextPath not in self.children:
                if createIfNotExists:
                    self.children[nextPath] = LiveS3File(
                        self.root, nextPath, self.path + '/' + nextPath, self)
                else:
                    raise Exception("path doesn't exist")
            return self.children[nextPath].ensureChild(pathParts[1:], createIfNotExists=createIfNotExists)

    def debug(self, level=0):
        """
        This prints out the S3 index in Python
        """
        print(('   ' * level) + self.path)
        for k in self.children:
            v = self.children[k]
            v.debug(level+1)

    def getNumChildren(self) -> int:
        """
        Returns the number of children this file has
        """
        return len(self.children)

    def hasChild(self, name: str) -> bool:
        """
        Returns true if there is a child by the given name
        """
        return name in self.children

    def listChildren(self) -> List[str]:
        """
        Returns the names of the children of this file
        """
        return self.children.keys()

    def getChild(self, name: str) -> LiveS3File:
        """
        Returns the child at the given name
        """
        return self.children[name]

    def download(self, prefixPath: str = None) -> str:
        """
        This downloads a folder, or a file, creating a temporary folder.
        This returns the temporary file path.
        """
        if len(self.children) == 0:
            path = ''
            if prefixPath is None:
                fd, path = tempfile.mkstemp()
            else:
                path = prefixPath + '/' + self.name
            print('downloading file '+self.path+' into '+path)
            self.root.bucket.download_file(self.path, path)
            return path
        else:
            path = ''
            if prefixPath is None:
                path = tempfile.mkdtemp()
            else:
                path = prefixPath + '/' + self.name
                os.mkdir(path)
            print('creating folder '+path)
            for k in self.children:
                self.children[k].download(path)
            return path

    def get(self) -> bytes:
        """
        This downloads the contents of the file as a byte array. If the file is a folder, returns an empty byte array
        """
        if len(self.children) > 0:
            return bytearray()
        return self.root.s3.Object(BUCKET_NAME, self.path).get()['Body'].read()

    def getJSON(self) -> Dict[str, Any]:
        return json.loads(self.get())

    def openLocally(self) -> LiveS3ContextManager:
        """
        Returns a context manager which we can use to handle
        """
        return LiveS3ContextManager(self.root, self)

    def uploadFile(self, filePath: str):
        """
        This uploads a file at a given path
        """
        print('uploading file '+filePath+' to '+self.path)
        self.root.s3.Object(BUCKET_NAME, self.path).put(
            Body=open(filePath, 'rb'))
        self.root.pubSub.publish(
            makeTopicPubSubSafe("/UPDATE/"+self.parentPath), {'path': self.path})
        self.root.rootFolder.ensureChild(filePath.split('/'))

    def uploadText(self, text: str):
        """
        This uploads text to the file at this path
        """
        self.root.s3.Object(BUCKET_NAME, self.path).put(Body=text)
        self.root.pubSub.publish(
            makeTopicPubSubSafe("/UPDATE/"+self.parentPath), {'path': self.path})

    def uploadJSON(self, contents: Dict[str, Any]):
        """
        This uploads JSON back to S3
        """
        j = json.dumps(contents)
        self.uploadText(j)

    def deleteChild(self, pathParts: List[str]):
        """
        This deletes a file from the graph. If the child isn't present in the
        graph, this is a silent no-op.
        """
        if len(pathParts) == 1:
            self.children.pop(pathParts[0])
        elif len(pathParts) > 1:
            firstPart = pathParts[0]
            if self.hasChild(firstPart):
                self.getChild(firstPart).deleteChild(pathParts[1:])


class LiveS3:
    """
    This creates a local index of an S3 bucket, and parses the document structure into useful form.

    It also handles receiving live updates from users, and pushing updates back to other clients.
    """
    rootFolder: LiveS3File
    pubSub: PubSub

    def __init__(self):
        self.s3_low_level = boto3.client('s3', region_name='us-west-2')
        self.s3 = boto3.resource('s3', region_name='us-west-2')
        self.bucket = self.s3.Bucket(BUCKET_NAME)
        self.rootFolder = LiveS3File(self, '', '', None)
        self.pubSub = PubSub()

    def registerListeners(self):
        """
        This registers a PubSub listener
        """
        self.pubSub.subscribe("/UPDATE/#", self.onUpdate)
        self.pubSub.subscribe("/DELETE/#", self.onDelete)

    def onUpdate(self, topic: str, payload: bytes):
        """
        We received a PubSub message telling us a file was created
        """
        body = json.loads(payload)
        path = body['path']
        print('notified of create/update '+path)
        # This is idempotent if the file already exists
        self.rootFolder.ensureChild(path.split('/'))

    def onDelete(self, topic: str, payload: bytes):
        """
        We received a PubSub message telling us a file was deleted
        """
        body = json.loads(payload)
        path = body['path']
        print('notified of delete '+path)
        # This is idempotent if the file doesn't exist
        self.rootFolder.deleteChild(path.split('/'))

    def refreshIndex(self):
        """
        This updates the index
        """
        for object_name in self.bucket.objects.all():
            key: str = object_name.key.strip()
            if key.endswith('/'):
                key = key[:-1]
            parts: List[str] = key.split('/')
            self.rootFolder.ensureChild(parts)

    def allFiles(self, parent: LiveS3File = None) -> List[LiveS3File]:
        """
        This retrieves all files that are the child of a given parent (including that parent itself), as a list
        """
        if parent is None:
            parent = self.rootFolder

        results: List[LiveS3File] = []
        results.append(parent)
        for child in parent.children.values():
            results.extend(self.allFiles(child))
        return results

    def debug(self):
        """
        Debug the contents of the S3 index
        """
        print('LiveS3 index:')
        self.rootFolder.debug()
