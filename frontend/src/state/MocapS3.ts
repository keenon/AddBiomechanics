import { LiveS3File, LiveS3Folder } from "./LiveS3";
import { makeAutoObservable, action } from "mobx";

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

class MocapClip {
  name: string;
  protectedUploadFolder: LiveS3Folder;
  status: MocapStatusJSON;
  statusFile: LiveS3File;
  markerFile: LiveS3File;

  // We only need these files if we're doing a comparison
  manualScalesFile: LiveS3File;
  manualIKFile: LiveS3File;

  // These are the files that are created by processing
  resultsPreviewFile: LiveS3File | null = null;
  logFile: LiveS3File | null = null;

  constructor(protectedUploadFolder: LiveS3Folder) {
    makeAutoObservable(this);
    this.name = protectedUploadFolder.name;
    this.status = {
      state: "loading",
      progress: 0,
    };
    let statusFileOrNull = protectedUploadFolder.files.get(MOCAP_STATUS_FILE);
    if (statusFileOrNull == null) {
      this.status.state = "ready-to-upload";
      this.statusFile = protectedUploadFolder.ensureFileToUpload(
        MOCAP_STATUS_FILE,
        JSON.stringify(this.status, null, 2)
      );
    } else {
      this.statusFile = statusFileOrNull;
      this.statusFile.downloadText().then(
        action((value: string) => {
          this.status = JSON.parse(value);

          if (this.status.resultsPreviewFile) {
            this.resultsPreviewFile = this.protectedUploadFolder.getFile(
              this.status.resultsPreviewFile
            );
          }
          if (this.status.logFile) {
            this.logFile = this.protectedUploadFolder.getFile(
              this.status.logFile
            );
          }
        })
      );
    }
    this.protectedUploadFolder = protectedUploadFolder;

    this.markerFile =
      protectedUploadFolder.getOrCreateEmptyFileToUpload("markers.trc");
    this.manualScalesFile =
      protectedUploadFolder.getOrCreateEmptyFileToUpload("gold_ik.osim");
    this.manualIKFile =
      protectedUploadFolder.getOrCreateEmptyFileToUpload("hand_ik.mot");
  }

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
  mocapClips: MocapClip[] = [];
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
      for (let i = 0; i < this.mocapClips.length; i++) {
        if (this.mocapClips[i].name == fileName) return "mocap";
      }
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
        for (let i = 0; i < this.mocapClips.length; i++) {
          if (this.mocapClips[i].name == path[0]) return this.mocapClips[i];
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

  addMocapClip = () => {
    let mocapClipName = "MocapClip" + (this.mocapClips.length + 1);
    console.log('Creating clip "' + mocapClipName + '"');
    let folder = this.backingFolder.ensureFolder(mocapClipName);
    this.mocapClips.push(new MocapClip(folder));
  };

  ensureFolder = (name: string) => {
    console.log("Ensuring folder: " + name);
    if (!this.folders.has(name)) {
      const newFolder: LiveS3Folder = this.backingFolder.ensureFolder(name);
      this.folders.set(name, new MocapFolder(newFolder, this));
    }
  };

  updateFromBackingFolder = () => {
    this.backingFolder.folders.forEach((folder: LiveS3Folder) => {
      // We decide things are a MocapClip if they have a status file, otherwise it's a folder
      if (folder.files.has(MOCAP_STATUS_FILE)) {
        this.mocapClips.push(new MocapClip(folder));
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

export { MocapClip, MocapFolder };
