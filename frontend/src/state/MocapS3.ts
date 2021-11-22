import { LiveS3File, LiveS3Folder } from "./LiveS3";
import { makeAutoObservable, action } from "mobx";
import { parsePath } from "history";

const MOCAP_STATUS_FILE = "_status.json";

type MocapStatusJSON = {
  state:
    | "loading"
    | "ready-to-upload"
    | "waiting-for-worker"
    | "processing"
    | "done";
  progress: number;
  markersFile?: string;
  heightMeters?: number;
  weightKg?: number;
  logFile?: string;
  grfFile?: string;
  resultsPreviewFile?: string;
  unscaledOsimFile?: string;
  manuallyScaledOsimFile?: string;
  manuallyScaledIKFile?: string;
};

function parsePathParts(pathname: string, linkPrefix?: string): string[] {
  const path = decodeURI(pathname).split("/");
  while (path.length > 0 && path[0].length == 0) {
    path.splice(0, 1);
  }
  while (path.length > 0 && path[path.length - 1].length == 0) {
    path.splice(path.length - 1, 1);
  }
  if (path.length > 0 && path[0] == linkPrefix) {
    path.splice(0, 1);
  }
  console.log(path);
  return path;
}

class MocapClip {
  name: string;
  parent: MocapFolder | null;
  backingFolder: LiveS3Folder;
  status: MocapStatusJSON;
  statusFile: LiveS3File;
  markerFile: LiveS3File;

  // We only need these files if we're doing a comparison
  manualScalesFile: LiveS3File;
  manualIKFile: LiveS3File;

  // These are the files that are created by processing
  resultsPreviewFile: LiveS3File | null = null;
  logFile: LiveS3File | null = null;

  constructor(backingFolder: LiveS3Folder, parent: MocapFolder | null = null) {
    makeAutoObservable(this);
    this.name = backingFolder.name;
    this.parent = parent;
    this.status = {
      state: "loading",
      progress: 0,
    };
    let statusFileOrNull = backingFolder.files.get(MOCAP_STATUS_FILE);
    if (statusFileOrNull == null) {
      this.status.state = "ready-to-upload";
      this.statusFile = backingFolder.ensureFileToUpload(
        MOCAP_STATUS_FILE,
        JSON.stringify(this.status, null, 2)
      );
    } else {
      this.statusFile = statusFileOrNull;
      this.statusFile.downloadText().then(
        action((value: string) => {
          this.status = JSON.parse(value);

          if (this.status.resultsPreviewFile) {
            this.resultsPreviewFile = this.backingFolder.getFile(
              this.status.resultsPreviewFile
            );
          }
          if (this.status.logFile) {
            this.logFile = this.backingFolder.getFile(this.status.logFile);
          }
        })
      );
    }
    this.backingFolder = backingFolder;

    this.markerFile = backingFolder.getOrCreateEmptyFileToUpload("markers.trc");
    this.manualScalesFile =
      backingFolder.getOrCreateEmptyFileToUpload("gold_ik.osim");
    this.manualIKFile =
      backingFolder.getOrCreateEmptyFileToUpload("hand_ik.mot");
  }

  uploadEmptyPlaceholders = () => {
    return this.backingFolder.uploadEmptyFileForFolder().then(() => {
      return this.statusFile.upload();
    });
  };

  upload = () => {
    let promises: Promise<void>[] = [];
    if (this.markerFile != null) promises.push(this.markerFile.upload());
    if (this.manualIKFile != null) promises.push(this.manualIKFile.upload());
    if (this.manualScalesFile != null)
      promises.push(this.manualScalesFile.upload());
    return Promise.all(promises).then(
      action(() => {
        this.status.state = "waiting-for-worker";
        this.statusFile.stageFileForUpload(
          JSON.stringify(this.status, null, 2)
        );
        return this.statusFile.upload();
      })
    );
  };
}

type MocapDataType = "none" | "folder" | "mocap" | "file";

class MocapFolder {
  backingFolder: LiveS3Folder;
  name: string;
  parent: MocapFolder | null;
  // These are the mocap clips to display
  mocapClips: Map<string, MocapClip> = new Map();
  // These are the child folders and files
  folders: Map<string, MocapFolder> = new Map();
  strayFiles: Map<string, LiveS3File> = new Map();

  constructor(backingFolder: LiveS3Folder, parent: MocapFolder | null = null) {
    makeAutoObservable(this);
    this.parent = parent;
    this.backingFolder = backingFolder;
    this.name = this.backingFolder.name;
    this.updateFromBackingFolder();
  }

  getDataType: (path: string[]) => MocapDataType = (path: string[]) => {
    if (path.length == 0) return "folder";
    if (path.length == 1) {
      const fileName = path[0];
      if (this.mocapClips.has(fileName)) return "mocap";
      if (this.folders.has(fileName)) return "folder";
      if (this.strayFiles.has(fileName)) return "file";
      return "none";
    } else {
      const folderName = path[0];
      const folder: MocapFolder | undefined = this.folders.get(folderName);
      if (folder == null) return "none";
      const subPath: string[] = [];
      for (let i = 1; i < path.length; i++) {
        subPath.push(path[i]);
      }
      return folder.getDataType(subPath);
    }
    return "none";
  };

  getFolder: (path: string[]) => MocapFolder = (path: string[]) => {
    if (path.length == 0) return this;
    else {
      const folderName = path[0];
      const folder: MocapFolder | undefined = this.folders.get(folderName);
      if (folder == null)
        throw new Error(
          'Folder "' +
            this.backingFolder.bucketPath +
            '" unable to find child folder to recurse on ' +
            path
        );
      if (path.length == 1) return folder;
      else {
        const subPath: string[] = [];
        for (let i = 1; i < path.length; i++) {
          subPath.push(path[i]);
        }
        return folder.getFolder(subPath);
      }
    }
  };

  getMocapClip: (path: string[]) => MocapClip = (path: string[]) => {
    if (path.length == 0)
      throw new Error(
        'Folder "' +
          this.backingFolder.bucketPath +
          '" unable to find mocap clip at ' +
          path
      );
    else {
      if (path.length == 1) {
        const clip: MocapClip | undefined = this.mocapClips.get(path[0]);
        if (clip) {
          return clip;
        }
        throw new Error(
          'Folder "' +
            this.backingFolder.bucketPath +
            '" unable to find mocap clip at ' +
            path
        );
      } else {
        const folder: MocapFolder | undefined = this.folders.get(path[0]);
        if (folder == null)
          throw new Error(
            'Folder "' +
              this.backingFolder.bucketPath +
              '" unable to find child folder to recurse on ' +
              path
          );
        const subPath: string[] = [];
        for (let i = 1; i < path.length; i++) {
          subPath.push(path[i]);
        }
        return folder.getMocapClip(subPath);
      }
    }
  };

  getRawFile: (path: string[]) => LiveS3File = (path: string[]) => {
    if (path.length == 0)
      throw new Error(
        'Folder "' +
          this.backingFolder.bucketPath +
          '" unable to find raw file at ' +
          path
      );
    else {
      if (path.length == 1) {
        const file: LiveS3File | undefined = this.strayFiles.get(path[0]);
        if (file == null) {
          throw new Error(
            'Folder "' +
              this.backingFolder.bucketPath +
              '" unable to find raw file at ' +
              path
          );
        }
        return file;
      } else {
        const folder: MocapFolder | undefined = this.folders.get(path[0]);
        if (folder == null)
          throw new Error(
            'Folder "' +
              this.backingFolder.bucketPath +
              '" unable to find child folder to recurse on ' +
              path
          );
        const subPath: string[] = [];
        for (let i = 1; i < path.length; i++) {
          subPath.push(path[i]);
        }
        return folder.getRawFile(subPath);
      }
    }
  };

  createMocapClip = (path: string[], name: string) => {
    if (this.getDataType(path) !== "folder") {
      return Promise.reject(
        "Trying to create a folder within a path that doesn't exist."
      );
    }
    const targetFolder: MocapFolder = this.getFolder(path);
    if (!targetFolder.backingFolder.hasChild(name)) {
      const newFolder: LiveS3Folder =
        targetFolder.backingFolder.ensureFolder(name);
      const newClip: MocapClip = new MocapClip(newFolder, targetFolder);
      targetFolder.mocapClips.set(name, newClip);

      return newClip.uploadEmptyPlaceholders();
    } else {
      return Promise.reject('Folder "' + name + '" already exists');
    }
  };

  createFolder = (path: string[], name: string) => {
    console.log("Ensuring folder: " + name);
    if (this.getDataType(path) !== "folder") {
      return Promise.reject(
        "Trying to create a folder within a path that doesn't exist."
      );
    }
    const targetFolder: MocapFolder = this.getFolder(path);
    if (!targetFolder.backingFolder.hasChild(name)) {
      const newFolder: LiveS3Folder =
        targetFolder.backingFolder.ensureFolder(name);
      targetFolder.folders.set(name, new MocapFolder(newFolder, targetFolder));
      return newFolder.uploadEmptyFileForFolder();
    } else {
      return Promise.reject('Folder "' + name + '" already exists');
    }
  };

  deleteByPrefix = (path: string[], prefix: string) => {
    if (this.getDataType(path) !== "folder") {
      return Promise.reject(
        "Trying to delete within a folder within a path that doesn't exist."
      );
    }
    const targetFolder: MocapFolder = this.getFolder(path);
    return targetFolder.backingFolder.deleteByPrefix(prefix).then(() => {
      targetFolder.updateFromBackingFolder();
    });
  };

  updateFromBackingFolder = () => {
    this.mocapClips.clear();
    this.folders.clear();
    this.strayFiles.clear();

    this.backingFolder.folders.forEach((folder: LiveS3Folder) => {
      // We decide things are a MocapClip if they have a status file, otherwise it's a folder
      if (folder.files.has(MOCAP_STATUS_FILE)) {
        this.mocapClips.set(folder.name, new MocapClip(folder));
      } else {
        this.folders.set(folder.name, new MocapFolder(folder, this));
      }
    });
    this.strayFiles = this.backingFolder.files;
  };

  refresh = () => {
    return this.backingFolder.refresh().then(() => {
      this.updateFromBackingFolder();
    });
  };
}

export { MocapClip, MocapFolder, parsePathParts };
