import { makeAutoObservable, action } from "mobx";
import { Storage } from "aws-amplify";
import {
  S3ProviderListOutput,
  S3ProviderListOutputItem,
} from "@aws-amplify/storage";

class LiveS3File {
  folder: LiveS3Folder;
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

  constructor(
    folder: LiveS3Folder,
    fullPath: string,
    level: "protected" | "public"
  ) {
    makeAutoObservable(this);
    this.folder = folder;
    this.fullPath = fullPath;
    this.level = level;
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
            completeCallback: action((event) => {
              console.log(`Successfully uploaded ${event.key}`);
              this.state = "s3";
              resolve();
            }),
            progressCallback: action((progress) => {
              console.log(`Uploaded: ${progress.loaded}/${progress.total}`);
              this.uploadProgress = progress.loaded / progress.total;
            }),
            errorCallback: action((err) => {
              console.error("Unexpected error while uploading", err);
              this.state = "error";
              reject(err);
            }),
          });
        }
      )
    );
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
        (result.Body as Blob).text().then((text: string) => {
          console.log(text);
          return text;
        });
      }
      throw new Error("Result didn't have a Body");
    });
  };

  deleteFile = () => {
    Storage.remove(this.fullPath, { level: this.level })
      .then((result) => {
        console.log(result);
      })
      .catch((e: Error) => {
        console.log(e);
      });
  };
}

/**
 * This class abstracts the annoyances in creating, uploading, and downloading data from S3.
 * It also allows you to track live updates about files, coming in as notifications over PubSub.
 */
class LiveS3Folder {
  // This is the S3 prefix for the data
  bucketPath: string;

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

  constructor(
    bucketPath: string,
    level: "public" | "protected",
    parent: LiveS3Folder | null = null
  ) {
    makeAutoObservable(this);
    this.level = level;
    this.bucketPath = bucketPath;
    this.lastModified = new Date();
    this.parent = parent;
  }

  /**
   * This either gets or (if it doesn't exist yet) creates a folder at this name
   *
   * @param folderName
   * @returns
   */
  ensureFolder = (folderName: string) => {
    let folder: LiveS3Folder | undefined = this.folders.get(folderName);
    if (folder == null) {
      folder = new LiveS3Folder(
        this.bucketPath + "/" + folderName,
        this.level,
        this
      );
      this.folders.set(folderName, folder);
    }
    return folder;
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
   * This ensures that there's a file that records the existence of a file in S3.
   *
   * @param fileName
   */
  ensureFileInS3 = (fileName: string, lastModified: Date, size: number) => {
    let file: LiveS3File | undefined = this.files.get(fileName);
    if (file == null) {
      file = new LiveS3File(this, this.bucketPath + fileName, this.level);
      this.files.set(fileName, file);
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
  };

  /**
   * This lists all the files in the protected space (after the prefix, if one is provided), and creates/updates folders for them.
   */
  refresh = () => {
    this.loading = true;
    return Storage.list(this.bucketPath, { level: this.level })
      .then((result: S3ProviderListOutput) => {
        console.log(
          'Successfully refreshed folder "' +
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
      .catch((err: Error) => {
        console.error('Unable to refresh folder "' + this.bucketPath + '"');
        console.log(err);
        this.loading = false;
      });
  };
}

export { LiveS3Folder, LiveS3File };
