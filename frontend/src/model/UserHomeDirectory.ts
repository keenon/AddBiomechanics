import LiveDirectory, {PathData} from "./LiveDirectory";
import { makeObservable, action, observable } from 'mobx';
import LiveJsonFile from "./LiveJsonFile";
import LiveFlagFile from "./LiveFlagFile";

type PathType = 'dataset' | 'subject' | 'trial' | 'trial_segment' | 'trials_folder' | '404' | 'loading';

type DatasetContents = {
    loading: boolean;
    contents: {name: string, path: string, type: PathType}[]
};

type SubjectContents = {
    loading: boolean;

    name: string;
    subjectJson: LiveJsonFile;

    resultsExist: boolean;
    resultsJsonPath: string;
    processingFlagFile: LiveFlagFile; // "PROCESSING"
    readyFlagFile: LiveFlagFile; // "READY_TO_PROCESS"
    errorFlagFile: LiveFlagFile; // "ERROR"

    trials: TrialContents[]
};

type TrialContents = {
    loading: boolean;
    path: string;
    name: string;
    trialJson: LiveJsonFile;
    // C3D marker + GRF data
    c3dFilePath: string;
    c3dFileExists: boolean;
    // TRC marker data
    trcFilePath: string;
    trcFileExists: boolean;
    // MOT force plate data
    grfMotFilePath: string;
    grfMotFileExists: boolean;
    // Segment data, if we've processed it
    segments: TrialSegmentContents[];
};

type TrialSegmentContents = {
    path: string;
    name: string;
    resultsJsonPath: string;
    previewPath: string;
    dataPath: string;
};

class UserHomeDirectory {
    dir: LiveDirectory;

    // 'protected/' + s3.region + ':' + userId + '/data/'
    constructor(dir: LiveDirectory) {
        this.dir = dir;

        this.getPathType = this.getPathType.bind(this);
        this.getSubjectContents = this.getSubjectContents.bind(this);
        this.getTrialContents = this.getTrialContents.bind(this);
        this.getTrialSegmentContents = this.getTrialSegmentContents.bind(this);
    }

    getPath(path: string, recursive: boolean = false): PathData {
        const dir = this.dir;
        if (dir == null) {
            return {
                loading: true,
                promise: null,
                path,
                folders: [],
                files: [],
                recursive,
            };
        }
        return dir.getPath(path, recursive);
    }

    getPathType(path: string): PathType {
        if (path.startsWith('/')) {
            path = path.substring(1);
        }

        const pathData: PathData | undefined = this.dir.getCachedPath(path);
        if (pathData == null || pathData.loading) {
            return 'loading';
        }

        const child_files = pathData.files.map((file) => {
            return file.key.substring(path.length).replace(/\/$/, '').replace(/^\//, '');
        });
        const child_folders = pathData.folders.map((folder) => {
            return folder.substring(path.length).replace(/\/$/, '').replace(/^\//, '');
        });

        if (child_files.length === 0) {
            return '404';
        }

        // The shape of the path gives away that this is a trial segment
        if (path.match(/trials\/[^\/]+\/segment_\d+(\/)?$/)) {
            return 'trial_segment';
        }
        // The presence of marker files indicate that this is a trial
        if (child_files.includes('markers.c3d') || 
            child_files.includes('markers.trc') || 
            child_files.includes('grf.mot') ||
            child_files.includes('_trial.json')) {
            return 'trial';
        }
        // The presence of a _subject.json file indicates that this is a subject
        if (child_files.includes('_subject.json')) {
            return 'subject';
        }
        // The 'trials_folder' class is a special case. It is a folder that is an immediate 
        // child of a subject, which is named 'trials'.
        if (path.endsWith('/trials') || path.endsWith('/trials/')) {
            const parent = path.replace(/\/$/, '').split('/').slice(0, -1).join('/');
            if (this.getPathType(parent) === 'subject' || this.getPathType(parent) === 'loading') {
                return 'trials_folder';
            }
        }
        // Checking for trials is a bit more complicated. We need to check if the immediate
        // parent is a 'trials/' folder

        return 'dataset';
    };

    /**
     * If this is a dataset, we will return the contents.
     * 
     * @param path The path to the dataset
     */
    getDatasetContents(path: string): DatasetContents {
        const pathData: PathData = this.dir.getPath(path, false);
        if (path.startsWith('/')) {
            path = path.substring(1);
        }

        return {
            loading: pathData.loading,
            contents: pathData.folders.map((folder) => {
                return {
                    name: folder.substring(path.length).replace(/\/$/, '').replace(/^\//, ''),
                    path: folder,
                    type: this.getPathType(folder),
                };
            })
        };
    }

    /**
     * This call will create a stub file to hold a new dataset folder.
     * 
     * @param path The path to the folder to create the new folder in
     * @param folderName The name of the new folder
     */
    createDataset(path: string, folderName: string): Promise<void> {
        const dir = this.dir;
        return dir.uploadText(path + (path.length > 0 ? '/' : '') + folderName + '/_dataset.json', '{}');
    }

    /**
     * This call will create a stub file to hold a new subject
     * 
     * @param path The path to the folder to create the new folder in
     * @param folderName The name of the new folder
     */
    createSubject(path: string, folderName: string): Promise<void> {
        const dir = this.dir;
        return dir.uploadText(path + (path.length > 0 ? '/' : '') + folderName + '/_subject.json', '{}');
    }

    /**
     * This call will create an empty trial object
     */
    createTrial(subjectPath: string, trialName: string): Promise<void> {
        const dir = this.dir;
        return dir.uploadText(subjectPath + (subjectPath.length > 0 ? '/' : '') + 'trials/' + trialName + '/_trial.json', '{}');
    }

    /**
     * This call will delete a folder.
     * 
     * @param path The path to the folder to delete
     * @returns A promise for when the folder is deleted
     */
    deleteFolder(path: string): Promise<void> {
        const dir = this.dir;
        return dir.deleteByPrefix(path + (path.length > 0 ? '/' : ''));
    }

    /**
     * If this is a subject, we will return the contents.
     * 
     * @param path The path to the subject
     */
    getSubjectContents(path: string): SubjectContents {
        const dir = this.dir;

        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }
        let name = '';
        if (path.includes('/')) {
            name = path.split('/').slice(-1)[0];
        }
        const subjectJson = dir.getJsonFile(path + '/_subject.json');
        const resultsJsonPath: string = path + '/_results.json';
        const processingFlagFile: LiveFlagFile = dir.getFlagFile(path + "/PROCESSING");
        const readyFlagFile: LiveFlagFile = dir.getFlagFile(path + "/READY_TO_PROCESS");
        const errorFlagFile: LiveFlagFile = dir.getFlagFile(path + "/ERROR");

        const subjectPathData: PathData = dir.getPath(path, false);
        const trialsPathData: PathData = dir.getPath(path+'/trials/', false);

        return {
            name,
            loading: trialsPathData.loading || subjectPathData.loading,
            subjectJson,
            resultsJsonPath,
            resultsExist: subjectPathData.files.map((file) => {
                return file.key;
            }).includes(resultsJsonPath),
            processingFlagFile,
            readyFlagFile,
            errorFlagFile,
            trials: trialsPathData.folders.map((folder) => this.getTrialContents(folder))
        };
    }

    getTrialContents(path: string): TrialContents {
        const dir = this.dir;
        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }
        if (path.startsWith('/')) {
            path = path.substring(1);
        }

        const name = path.split('/').slice(-1)[0];
        const trial: PathData = dir.getPath(path + '/', false);
        const trialJson = dir.getJsonFile(path + '/_trial.json');

        const c3dFilePath = path + '/markers.c3d';
        const trcFilePath = path + '/markers.trc';
        const grfMotFilePath = path + '/grf.mot';

        return {
            loading: trial.loading,
            path: path + '/',
            name,
            c3dFilePath,
            c3dFileExists: trial.files.map((file) => {
                return file.key;
            }).includes(c3dFilePath),
            trcFilePath,
            trcFileExists: trial.files.map((file) => {
                return file.key;
            }).includes(trcFilePath),
            grfMotFilePath,
            grfMotFileExists: trial.files.map((file) => {
                return file.key;
            }).includes(grfMotFilePath),
            trialJson,
            segments: trial.folders.map((folder) => this.getTrialSegmentContents(folder))
        };
    }

    getTrialSegmentContents(path: string): TrialSegmentContents {
        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }
        if (path.startsWith('/')) {
            path = path.substring(1);
        }

        const name = path.split('/').slice(-1)[0];
        const resultsJsonPath = path + '/_results.json';
        const previewPath = path + '/preview.bin';
        const dataPath = path + '/data.csv';

        return {
            path: path + '/',
            name,
            resultsJsonPath,
            previewPath,
            dataPath,
        };
    }
};

export type { PathType, DatasetContents, SubjectContents, TrialContents, TrialSegmentContents };
export default UserHomeDirectory;