import { makeAutoObservable, action } from "mobx";
import { Storage, PubSub, Auth } from "aws-amplify";
import {
  S3ProviderListOutput,
  S3ProviderListOutputItem,
} from "@aws-amplify/storage";
import { ZenObservable } from 'zen-observable-ts';

class LiveS3File {
  folder: LiveS3Folder;
  name: string;
  fullPath: string;
  level: "protected" | "public";
  lastModified: Date = new Date();
  size: number = 0.0;
  state:
    | "empty"
    | "staged-for-upload"
    | "staged-for-overwrite"
    | "uploading"
    | "s3"
    | "error" = "empty";
  stagedForUpload?: File | string;
  uploadProgress: number = 0.0;
  updateListeners: Array<() => void> = [];

  constructor(
    folder: LiveS3Folder,
    fullPath: string,
    level: "protected" | "public"
  ) {
    makeAutoObservable(this);
    this.folder = folder;
    this.fullPath = fullPath;
    this.level = level;
    const parts = fullPath.split("/");
    this.name = parts.length == 0 ? fullPath : parts[parts.length - 1];
    console.log("Creating new file at "+this.fullPath+" inside folder "+this.folder.bucketPath);
  }

  setLastModified = (date: Date) => {
    this.lastModified = date;
    this.folder.updateLastModified();
  };

  stageFileForUpload = (
    contents?: File | string,
    allowOverwrite: boolean = true
  ) => {
    if (contents != null) {
      if (this.state === "s3") {
        if (!allowOverwrite) {
          console.error(
            'Attempting to overwrite file "' +
              this.fullPath +
              '" but allowOverwrite=false.'
          );
          return false;
        }
        this.state = "staged-for-overwrite";
      } else {
        this.state = "staged-for-upload";
      }
    }
    this.stagedForUpload = contents;
    this.setLastModified(new Date());
  };

  registerUpdateListener = (listener: () => void) => {
    this.updateListeners.push(listener);
  }

  notifyUpdateListeners = () => {
    console.log("Attempting to notify "+this.updateListeners.length+" listeners for "+this.fullPath);
    this.updateListeners.forEach(l => l());
  }

  upload = () => {
    if (this.stagedForUpload == null) {
      return Promise.reject(
        "No raw file ready to upload, so call to upload() fails."
      );
    }
    return new Promise(
      action(
        (resolve: (value: void) => void, reject: (reason?: any) => void) => {
          this.state = "uploading";
          Storage.put(this.fullPath, this.stagedForUpload, {
            level: this.level,
            progressCallback: action((progress) => {
              console.log(`Uploaded: ${progress.loaded}/${progress.total}`);
              this.uploadProgress = progress.loaded / progress.total;
            }),
            completeCallback: action(() => {
              console.log("Finished uploading");
              this.uploadProgress = 1.0;
              // Ensure we flash the full progress bar for at least 500ms
              setTimeout(
                action(() => {
                  this.state = "s3";
                  this.folder.reportChangeToPubSub(this.fullPath, 'uploaded');
                  resolve();
                }),
                500
              );
            }),
          })
            .then(
              action(() => {
                console.log("Finished uploading");
                // Ensure we flash the full progress bar for at least 500ms
                this.uploadProgress = 1.0;
                setTimeout(
                  action(() => {
                    this.state = "s3";
                    this.folder.reportChangeToPubSub(this.fullPath, 'uploaded');
                    resolve();
                  }),
                  500
                );
              })
            )
            .catch(
              action((e) => {
                this.state = "error";
                reject(e);
              })
            );
        }
      )
    );
  };

  getSignedURL = () => {
    return Storage.get(this.fullPath, {
      level: this.level,
    });
  };

  downloadFile = () => {
    Storage.get(this.fullPath, {
      level: this.level,
    }).then((signedURL) => {
      const link = document.createElement("a");
      link.href = signedURL;
      link.target = "#";
      link.click();
    });
  };

  downloadText = () => {
    return Storage.get(this.fullPath, {
      level: this.level,
      download: true,
      cacheControl: "no-cache",
    }).then((result) => {
      if (result != null && result.Body != null) {
        // data.Body is a Blob
        return (result.Body as Blob).text().then((text: string) => {
          return text;
        });
      }
      throw new Error(
        'Result of downloading "' + this.fullPath + "\" didn't have a Body"
      );
    });
  };

  deleteFile = () => {
    return Storage.remove(this.fullPath, { level: this.level })
      .then((result) => {
        console.log(result);
      })
      .catch((e: Error) => {
        console.log(e);
      });
  };
}

type LiveS3UpdateMessage = {
  path: string;
};

type LiveS3DeleteMessage = {
  path: string;
};

/**
 * This class abstracts the annoyances in creating, uploading, and downloading data from S3.
 * It also allows you to track live updates about files, coming in as notifications over PubSub.
 */
class LiveS3Folder {
  // This is the S3 prefix for the data
  bucketPath: string;

  // The human-readable name of S3 folder
  name: string;

  // This is the level for this data
  level: "public" | "protected";

  // True if this is actively refreshing
  loading: boolean = false;

  // These are files, which can be uploaded, downloaded, and displayed depending on their status.
  files: Map<string, LiveS3File> = new Map();

  // These are the child folders
  folders: Map<string, LiveS3Folder> = new Map();

  // This points to the parent folder. If this is null, this is a root folder.
  parent: LiveS3Folder | null = null;

  // This is the most recently modified file in this hierarchy
  lastModified: Date;

  // This is the total size of the folder's contents
  size: number = 0;

  // This listens for updates to the files in this folder, and then re-fetches files as we're notified of changes to them.
  updateListener: ZenObservable.Subscription | null = null;
  deleteListener: ZenObservable.Subscription | null = null;

  constructor(
    bucketPath: string,
    level: "public" | "protected",
    parent: LiveS3Folder | null = null
  ) {
    makeAutoObservable(this);
    this.level = level;
    this.bucketPath = bucketPath;
    // Ensure we always end bucket paths with a "/"
    if (!this.bucketPath.endsWith("/")) {
      this.bucketPath = this.bucketPath + "/";
    }
    this.lastModified = new Date();
    this.parent = parent;

    const parts = bucketPath.split("/");
    this.name = parts.length == 0 ? bucketPath : parts[parts.length - 1];
  }

  /**
   * This returns true if there's a child (either folder or file) at the given name. False otherwise.
   *
   * @param name The name of the child to check for
   */
  hasChild = (name: string) => {
    return this.files.has(name) || this.folders.has(name);
  };

  /**
   * This transforms a raw, "global", bucket path into a path within our little folder.
   * 
   * @param globalPath This is the S3 path in raw bucket space
   */
  rawBucketPathToLocalPath = (globalPath: string) => {
    if (this.level === 'public') {
      if (globalPath.startsWith('public/'+this.bucketPath)) {
        return globalPath.substring('public/'.length + this.bucketPath.length);
      }
      console.warn("rawBucketPathToLocalPath() handed a path that doesn't look like a global path for this (public) folder: "+globalPath);
      return globalPath;
    }
    else if (this.level === 'protected') {
      const parts: string[] = globalPath.split('/');
      const bucketPathParts: string[] = this.bucketPath.split('/');
      if (parts.length >= (2 + bucketPathParts.length) && parts[0] === 'protected') {
        for (let i = 0; i < bucketPathParts.length; i++) {
          if (parts[i+2] != bucketPathParts[i]) {
            console.warn("rawBucketPathToLocalPath() handed a path that doesn't look like a global path for this (protected) folder: "+globalPath);
            return globalPath;
          }
        }
        return parts.slice(2 + bucketPathParts.length).join('/');
      }
      console.warn("rawBucketPathToLocalPath() handed a path that doesn't look like a global path for this (protected) folder: "+globalPath);
      return globalPath;
    }
    return globalPath;
  };

  /**
   * This transforms a local path within our folder to a raw, "global" bucket path in S3
   * 
   * @param localPath This is the local path within our little folder
   */
  localPathToRawBucketPath = (localPath: string) => {

  };

  /**
   * This registers a PubSub listener for live change-updates on this S3 bucket.
   */
  registerPubSubListener = () => {
    console.log("Registering PubSub listeners");

    if (this.updateListener != null && !this.updateListener.closed) {
      this.updateListener.unsubscribe();
    }
    if (this.deleteListener != null && !this.deleteListener.closed) {
      this.deleteListener.unsubscribe();
    }

    const onUpdate = (data: LiveS3UpdateMessage) => {
      const localPath: string = this.rawBucketPathToLocalPath(data.path);
      console.log("Update received for "+localPath);
      this.ensureFileInS3(localPath, new Date(), 0).notifyUpdateListeners();
    };

    const onDelete = (data: LiveS3DeleteMessage) => {
      const localPath: string = this.rawBucketPathToLocalPath(data.path);
      console.log("Delete received for "+localPath);
      this.deleteByPrefix(localPath);
    };

    if (this.level === 'protected') {
      Auth.currentCredentials().then((credentials) => {
        // If we're logged in, then we want to establish a listener for our own data
        this.updateListener = PubSub.subscribe("/UPDATE/protected/"+credentials.identityId+"/#").subscribe({
          next: (msg) => {
            onUpdate(msg.value);
          },
          error: (error) => {
            console.error("Error on PubSub.subscribe()");
            console.error(error);
          },
          complete: () => console.log("Done"),
        });
        this.deleteListener = PubSub.subscribe("/DELETE/protected/"+credentials.identityId+"/#").subscribe({
          next: (msg) => {
            onDelete(msg.value);
          },
          error: (error) => {
            console.error("Error on PubSub.subscribe()");
            console.error(error);
          },
          complete: () => console.log("Done"),
        });
      });
    }
    else if (this.level === 'public') {
      // If we're logged in, then we want to establish listeners for both public and private data updates
      this.updateListener = PubSub.subscribe("/UPDATE/public/#").subscribe({
        next: (msg) => {
          onUpdate(msg.value);
        },
        error: (error) => {
          console.error("Error on PubSub.subscribe()");
          console.error(error);
        },
        complete: () => console.log("Done"),
      });
      this.deleteListener = PubSub.subscribe("/DELETE/public/#").subscribe({
        next: (msg) => {
          onDelete(msg.value);
        },
        error: (error) => {
          console.error("Error on PubSub.subscribe()");
          console.error(error);
        },
        complete: () => console.log("Done"),
      });
    }
  };

  /**
   * This notifies any listening servers/clients that this S3 bucket has changed
   */
  reportChangeToPubSub = (path: string, reason: string) => {
    const message = {
      path,
      reason
    };
    if (this.level === 'protected') {
      Auth.currentCredentials().then((credentials) => {
        PubSub.publish("/UPDATE/protected/"+credentials.identityId+"/", message);
      });
    }
    else if (this.level === 'public') {
      PubSub.publish("/UPDATE/public/", message);
    }
  };

  /**
   * This either gets or (if it doesn't exist yet) creates a folder at this name
   *
   * @param folderName
   * @returns
   */
  ensureFolder = action((folderName: string) => {
    let folder: LiveS3Folder | undefined = this.folders.get(folderName);
    if (folder == null) {
      folder = new LiveS3Folder(this.bucketPath + folderName, this.level, this);
      this.folders.set(folderName, folder);
    }
    return folder;
  });

  /**
   * This uploads an empty file to S3 at this folder's path, which records the existence of the folder.
   */
  uploadEmptyFileForFolder = () => {
    return Storage.put(this.bucketPath, "", {
      level: this.level,
    });
  };

  /**
   * This deletes everything inside a folder
   */
  clearFolder = () => {
    let deletePromises: Promise<any>[] = [];
    this.folders.forEach((folder) => {
      deletePromises.push(folder.deleteFolder());
    });
    this.folders.clear();
    this.files.forEach((file) => {
      deletePromises.push(file.deleteFile());
    });
    this.files.clear();
    return Promise.all(deletePromises);
  };

  /**
   * This recursively deletes this folder and all its contents
   */
  deleteFolder = () => {
    return this.clearFolder().then(() => {
      return Storage.remove(this.bucketPath, {
        level: this.level,
      });
    });
  };

  /**
   * This deletes all the files that match a given prefix
   *
   * @param prefix
   */
  deleteByPrefix = (prefix: string) => {
    let deleteFiles: string[] = [];
    this.files.forEach((v: LiveS3File, key: string) => {
      if (key.startsWith(prefix)) {
        deleteFiles.push(key);
      }
    });
    let deletePromises: Promise<any>[] = [];

    for (let key of deleteFiles) {
      let file = this.files.get(key);
      if (file != null) {
        deletePromises.push(file.deleteFile());
      }
      this.files.delete(key);
    }

    let deleteFolders: string[] = [];
    this.folders.forEach((v: LiveS3Folder, key: string) => {
      if (key.startsWith(prefix)) {
        deleteFolders.push(key);
      }
    });
    for (let key of deleteFolders) {
      let folder = this.folders.get(key);
      if (folder != null) {
        deletePromises.push(folder.deleteFolder());
      }
      this.folders.delete(key);
    }

    return Promise.all(deletePromises);
  };

  /**
   * This either grabs the file that already exists, or creates an empty slot to upload
   *
   * @param fileName The name of the file to retrieve, or create an empty upload placeholder for
   * @returns a file with the specified name
   */
  getOrCreateEmptyFileToUpload = (fileName: string) => {
    let file: LiveS3File | undefined = this.files.get(fileName);
    if (file == null) {
      file = new LiveS3File(this, this.bucketPath + fileName, this.level);
      this.files.set(fileName, file);
    }
    return file;
  };

  /**
   * Stage a file to upload. If this filename already exists, by default this will try to overwrite the existing file.
   *
   * @param fileName The name of the file (not the full path, just the name within this folder)
   * @param contents The contents to be uploaded, when we ask it to.
   */
  ensureFileToUpload = (
    fileName: string,
    contents: string | File,
    allowOverwrite: boolean = true
  ) => {
    let file: LiveS3File | undefined = this.files.get(fileName);
    if (file == null) {
      file = new LiveS3File(this, this.bucketPath + fileName, this.level);
      this.files.set(fileName, file);
    }
    file.stageFileForUpload(contents, allowOverwrite);
    return file;
  };

  /**
   * This either returns the desired file, or null if it doesn't exist
   *
   * @param fileName The file to retrieve
   */
  getFile = (fileName: string) => {
    let file: LiveS3File | undefined = this.files.get(fileName);
    if (file == null) {
      return null;
    }
    return file;
  };

  /**
   * This ensures that there's a file that records the existence of a file in S3.
   *
   * @param fileName
   */
  ensureFileInS3 = (filePath: string, lastModified: Date, size: number) => {
    let pathParts = filePath.split('/');

    let folder: LiveS3Folder = this;
    for (let i = 0; i < pathParts.length - 1; i++) {
      folder = folder.ensureFolder(pathParts[i]);
    }

    let fileName = pathParts[pathParts.length - 1];
    let file: LiveS3File | undefined = folder.files.get(fileName);
    if (file == null) {
      file = new LiveS3File(folder, folder.bucketPath + fileName, folder.level);
      folder.files.set(fileName, file);
    }
    if (file.stagedForUpload != null) {
      console.error(
        "Calling ensureFileInS3(" +
          fileName +
          "), but that file was staged for upload. This will clear the pending upload, and probably represents a weird race condition with other users using the same account elsewhere."
      );
    }
    file.state = "s3";
    file.setLastModified(lastModified);
    file.size = size;
    file.stagedForUpload = undefined;
    return file;
  };

  updateLastModified = () => {
    this.lastModified = new Date();
    this.lastModified.setDate(this.lastModified.getDate() - 1000);
    this.files.forEach((file: LiveS3File) => {
      if (file.lastModified.getTime() > this.lastModified.getTime()) {
        this.lastModified = file.lastModified;
      }
    });
  };

  /**
   * This processes raw S3 output, which is just a long list of file keys, and updates the appropriate folders
   *
   * @param rawS3 The raw output from AWS S3
   * @param folders The folder map we'll be updating
   */
  __ensureRawS3Item = (rawFileS3: S3ProviderListOutputItem) => {
    if (rawFileS3.key != null) {
      const key: string = rawFileS3.key;
      if (!key.startsWith(this.bucketPath)) {
        console.error(
          'Folder "' +
            this.bucketPath +
            '" being asked to process Raw S3 Item "' +
            key +
            "\", but the Raw S3 Item doesn't live inside the folder. This indicates a bug."
        );
        return;
      }

      const suffix = key.substr(this.bucketPath.length);
      // We get empty files indicating each folder in S3, but ignore those
      if (suffix.length > 0) {
        let pathIndex = suffix.indexOf("/");
        if (pathIndex != -1) {
          const folderName = suffix.substr(0, pathIndex);
          this.ensureFolder(folderName).__ensureRawS3Item(rawFileS3);
        } else {
          this.ensureFileInS3(
            suffix,
            rawFileS3.lastModified ?? new Date(),
            rawFileS3.size ?? 0
          );
        }
      }
    }
  };

  /**
   * This lists all the files in the protected space (after the prefix, if one is provided), and creates/updates folders for them.
   */
  refresh = () => {
    this.loading = true;
    return Storage.list(this.bucketPath, { level: this.level })
      .then(
        action((result: S3ProviderListOutput) => {
          console.log(
            "Successfully refreshed " +
              this.level +
              ' folder "' +
              this.bucketPath +
              '", got ' +
              result.length +
              " items"
          );
          for (let i = 0; i < result.length; i++) {
            this.__ensureRawS3Item(result[i]);
          }
          this.loading = false;
        })
      )
      .catch((err: Error) => {
        console.error('Unable to refresh folder "' + this.bucketPath + '"');
        console.log(err);
        this.loading = false;
      });
  };
}

export { LiveS3Folder, LiveS3File };
