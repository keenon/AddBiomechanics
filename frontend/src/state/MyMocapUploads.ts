import { LiveS3File, LiveS3Folder } from "./LiveS3";
import { makeAutoObservable, action } from "mobx";

const MOCAP_STATUS_FILE = "procstatus.json";

type MocapStatusJSON = {
  state:
    | "loading"
    | "ready-to-upload"
    | "waiting-for-worker"
    | "processing"
    | "done";
  progress: number;
  resultBucket: string;
};

class MocapClip {
  protectedUploadFolder: LiveS3Folder;
  status: MocapStatusJSON;
  statusFile: LiveS3File;
  markerFile: LiveS3File;

  // We only need these files if we're doing a comparison
  manualScalesFile: LiveS3File;
  manualIKFile: LiveS3File;

  constructor(protectedUploadFolder: LiveS3Folder) {
    makeAutoObservable(this);
    this.status = {
      state: "loading",
      progress: 0,
      resultBucket: "",
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

class MocapFolder {
  backingFolder: LiveS3Folder;
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
    this.backingFolder.folders.forEach((folder: LiveS3Folder) => {
      // We decide things are a MocapClip if they have a status file, otherwise it's a folder
      if (folder.files.has(MOCAP_STATUS_FILE)) {
        this.mocapClips.push(new MocapClip(folder));
      } else {
        this.folders.set(folder.bucketPath, new MocapFolder(folder, this));
      }
    });
    this.strayFiles = this.backingFolder.files;
  }

  addMocapClip = () => {
    let mocapClipName = "MocapClip" + (this.mocapClips.length + 1);
    console.log('Creating clip "' + mocapClipName + '"');
    let folder = this.backingFolder.ensureFolder(mocapClipName);
    this.mocapClips.push(new MocapClip(folder));
  };
}

class MyMocapUploads {
  loading: boolean = true;
  rootFolder: MocapFolder;
  rootBackingFolder: LiveS3Folder;

  currentFolder: MocapFolder;

  constructor(rootPrefix: string) {
    makeAutoObservable(this);
    this.rootBackingFolder = new LiveS3Folder(rootPrefix, "protected");
    this.rootFolder = new MocapFolder(this.rootBackingFolder);
    this.currentFolder = this.rootFolder;
    this.rootBackingFolder.refresh().then(
      action(() => {
        this.loading = false;
      })
    );
  }

  setFolder = (folder: MocapFolder) => {
    this.currentFolder = folder;
  };
}

export { MocapClip, MocapFolder, MyMocapUploads };
export default MyMocapUploads;
