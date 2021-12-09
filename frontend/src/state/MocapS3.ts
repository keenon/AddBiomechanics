import { LiveS3File, LiveS3Folder } from "./LiveS3";
import { makeAutoObservable, action } from "mobx";
import { parsePath } from "history";

/////////////////////////////////////////////////////////////////////////////////////////////////////////
// This folder handles the Mocap file system.
/////////////////////////////////////////////////////////////////////////////////////////////////////////

const MOCAP_TRIAL_FILE = "_trial.json";

type MocapTrialStatusJSON = {
  state:
    | "loading"
    | "ready-to-upload"
    | "uploading"
    | "waiting-for-worker"
    | "processing"
    | "done";
  progress: number;
  markersFile?: string;
  logFile?: string;
  grfFile?: string;
  manualIKFile?: string;
  resultsPreviewFile?: string;
};

type GenericOsimFile = "rajagopal" | "lai_arnold" | "custom";

const MOCAP_SUBJECT_FILE = "_subject.json";

type MocapStatusJSON = {
  heightMeters?: number;
  weightKg?: number;
  genericOsimFile?: GenericOsimFile;
  customGenericOsimFile?: string;
  manuallyScaledOsimFile?: string;
  logFile?: string;
  state?: "loading" | "waiting-for-worker" | "processing" | "done";
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
  return path;
}

class MocapTrial {
  name: string;
  status: MocapTrialStatusJSON;
  statusFile: LiveS3File;
  markerFile: LiveS3File;
  manualIKFile: LiveS3File;
  grfFile: LiveS3File;
  backingFolder: LiveS3Folder;
  parent: MocapSubject;

  // These are the files that are created by processing
  resultsPreviewFile: LiveS3File | null = null;
  logFile: LiveS3File | null = null;

  constructor(backingFolder: LiveS3Folder, parent: MocapSubject) {
    makeAutoObservable(this);
    this.name = backingFolder.name;
    this.backingFolder = backingFolder;
    this.parent = parent;

    this.markerFile = backingFolder.getOrCreateEmptyFileToUpload("markers.trc");
    this.manualIKFile =
      backingFolder.getOrCreateEmptyFileToUpload("hand_ik.mot");
    this.grfFile = backingFolder.getOrCreateEmptyFileToUpload("grf.mot");

    this.status = {
      state: "loading",
      progress: 0,
    };
    let statusFileOrNull = backingFolder.files.get(MOCAP_TRIAL_FILE);
    if (statusFileOrNull == null) {
      this.status.state = "ready-to-upload";
      this.statusFile = backingFolder.ensureFileToUpload(
        MOCAP_TRIAL_FILE,
        JSON.stringify(this.status, null, 2)
      );
    } else {
      this.statusFile = statusFileOrNull;
      this.statusFile.downloadText().then(
        action((value: string) => {
          this.status = JSON.parse(value);
          this.refreshStatus();
        })
      );
    }
    // On updates to the trial status file, we pull the latest from S3, and parse it
    this.statusFile.registerUpdateListener(() => {
      this.refreshStatus();
    });
  }

  /**
   * Re-download the status JSON from the backend
   */
  refreshStatus = () => {
    this.status.state = "loading";
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
  };

  upload = () => {
    let promises: Promise<void>[] = [];
    this.status.state = "uploading";
    this.statusFile.stageFileForUpload(JSON.stringify(this.status));
    promises.push(this.statusFile.upload());
    if (this.markerFile != null && this.markerFile.stagedForUpload != null)
      promises.push(this.markerFile.upload());
    if (this.manualIKFile != null && this.manualIKFile.stagedForUpload != null)
      promises.push(this.manualIKFile.upload());
    if (this.grfFile != null && this.grfFile.stagedForUpload != null)
      promises.push(this.grfFile.upload());

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

  delete = () => {
    this.parent.deleteTrial(this.name);
  };
}

class MocapSubject {
  name: string;
  parent: MocapFolder | null;
  backingFolder: LiveS3Folder;
  trialFolder: LiveS3Folder;

  status: MocapStatusJSON;
  loading: boolean;
  statusFile: LiveS3File;

  customGenericOsimFile: LiveS3File;
  manualScalesFile: LiveS3File;

  trials: MocapTrial[] = [];

  constructor(backingFolder: LiveS3Folder, parent: MocapFolder | null = null) {
    makeAutoObservable(this);
    this.name = backingFolder.name;
    this.parent = parent;
    this.status = {};
    let statusFileOrNull = backingFolder.files.get(MOCAP_SUBJECT_FILE);
    this.loading = false;
    if (statusFileOrNull == null) {
      // Default to Rajagopal for new subjects
      this.status.genericOsimFile = "rajagopal";
      this.statusFile = backingFolder.ensureFileToUpload(
        MOCAP_SUBJECT_FILE,
        JSON.stringify(this.status, null, 2)
      );
    } else {
      this.statusFile = statusFileOrNull;
      this.refreshStatus();
    }
    // On updates to the trial status file, we pull the latest from S3, and parse it
    this.statusFile.registerUpdateListener(() => {
      this.refreshStatus();
    });
    this.backingFolder = backingFolder;

    this.customGenericOsimFile =
      backingFolder.getOrCreateEmptyFileToUpload("generic.osim");
    this.manualScalesFile = backingFolder.getOrCreateEmptyFileToUpload(
      "manually_scaled.osim"
    );

    this.trialFolder = this.backingFolder.ensureFolder("trials");
    this.trialFolder.folders.forEach((trialFolder: LiveS3Folder) => {
      this.trials.push(new MocapTrial(trialFolder, this));
    });
  }

  refreshStatus = () => {
    this.loading = true;
    this.statusFile.downloadText().then(
      action((value: string) => {
        this.status = JSON.parse(value);
        this.loading = false;
      })
    );
  };

  setStatusValues = (values: MocapStatusJSON) => {
    for (let key in values) {
      (this.status as any)[key] = (values as any)[key];
    }
    this.statusFile.stageFileForUpload(JSON.stringify(this.status));
    this.statusFile.upload();
  };

  isGenericOsimFileValid(): boolean {
    return (
      this.status.genericOsimFile === "rajagopal" ||
      this.status.genericOsimFile === "lai_arnold" ||
      (this.status.genericOsimFile === "custom" &&
        this.customGenericOsimFile.state !== "empty")
    );
  }

  uploadEmptyPlaceholders = () => {
    return this.backingFolder.uploadEmptyFileForFolder().then(() => {
      return this.statusFile.upload();
    });
  };

  upload = () => {
    let promises: Promise<void>[] = [];
    if (this.customGenericOsimFile != null)
      promises.push(this.customGenericOsimFile.upload());
    if (this.manualScalesFile != null)
      promises.push(this.manualScalesFile.upload());
    return Promise.all(promises).then(
      action(() => {
        this.statusFile.stageFileForUpload(
          JSON.stringify(this.status, null, 2)
        );
        return this.statusFile.upload();
      })
    );
  };

  createTrials = (files: File[]) => {
    for (let i = 0; i < files.length; i++) {
      let suffix = "";
      let suffixIndex = 0;
      while (this.trialFolder.hasChild(files[i].name + suffix)) {
        suffixIndex++;
        suffix = " Copy " + suffixIndex;
      }
      const trialFolder = this.trialFolder.ensureFolder(files[i].name + suffix);
      const newTrial = new MocapTrial(trialFolder, this);
      newTrial.markerFile.stageFileForUpload(files[i]);
      newTrial.upload();
      this.trials.push(newTrial);
    }
  };

  deleteTrial = (name: string) => {
    this.trials = this.trials.filter((t) => t.name !== name);
    return this.trialFolder.deleteByPrefix(name);
  };
}

type MocapDataType = "none" | "folder" | "mocap" | "file";

class MocapFolder {
  backingFolder: LiveS3Folder;
  name: string;
  parent: MocapFolder | null;
  // These are the mocap clips to display
  mocapSubjects: Map<string, MocapSubject> = new Map();
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
      if (this.mocapSubjects.has(fileName)) return "mocap";
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

  getMocapClip: (path: string[]) => MocapSubject = (path: string[]) => {
    if (path.length == 0)
      throw new Error(
        'Folder "' +
          this.backingFolder.bucketPath +
          '" unable to find mocap clip at ' +
          path
      );
    else {
      if (path.length == 1) {
        const clip: MocapSubject | undefined = this.mocapSubjects.get(path[0]);
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
      const newClip: MocapSubject = new MocapSubject(newFolder, targetFolder);
      targetFolder.mocapSubjects.set(name, newClip);

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
    this.mocapSubjects.clear();
    this.folders.clear();
    this.strayFiles.clear();

    this.backingFolder.folders.forEach((folder: LiveS3Folder) => {
      // We decide things are a MocapClip if they have a status file, otherwise it's a folder
      if (folder.files.has(MOCAP_SUBJECT_FILE)) {
        this.mocapSubjects.set(folder.name, new MocapSubject(folder));
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

export { MocapSubject, MocapFolder, parsePathParts, MocapTrial };
