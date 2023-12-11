import LiveDirectory, {PathData} from "./LiveDirectory";
import { makeObservable, action, observable } from 'mobx';
import LiveJsonFile from "./LiveJsonFile";
import LiveFile from "./LiveFile";
import SubjectViewState from "./SubjectViewState";

type PathType = 'dataset' | 'subject' | 'trial' | 'trial_segment' | 'trials_folder' | '404' | 'loading';

type PathStatus = 'loading' | 'dataset' | 'needs_data' | 'ready_to_process' | 'waiting_for_server' | 'slurm' | 'processing' | 'error' | 'needs_review' | 'done';

type DatasetContents = {
    loading: boolean;
    status: PathStatus;
    contents: {name: string, path: string, type: PathType, status: PathStatus}[]
};

type SubjectContents = {
    loading: boolean;

    name: string;
    subjectJson: LiveJsonFile;

    resultsExist: boolean;
    resultsJsonPath: string;
    processingFlagFile: LiveFile; // "PROCESSING"
    readyFlagFile: LiveFile; // "READY_TO_PROCESS"
    errorFlagFile: LiveFile; // "ERROR"

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
    loading: boolean;
    path: string;
    parentSubjectPath: string;
    parentDatasetPath: string;
    name: string;
    resultsJsonPath: string;
    previewPath: string;
    dataPath: string;
    // The path to the review flag file
    reviewFlagPath: string;
    reviewFlagExists: boolean;
    // The review.json file
    reviewJson: LiveJsonFile;
};

type FolderReviewStatus = {
    loading: boolean;
    path: string;
    segmentsNeedReview: TrialSegmentContents[];
    segmentsReviewed: TrialSegmentContents[];
};

class UserHomeDirectory {
    dir: LiveDirectory;
    subjectViewStates: Map<string, SubjectViewState> = new Map();
    pathTypeCache: Map<string, PathType> = new Map();
    pathStatusCache: Map<string, PathStatus> = new Map();
    pathReviewCache: Map<string, FolderReviewStatus> = new Map();
    datasetContentsCache: Map<string, DatasetContents> = new Map();
    subjectContentsCache: Map<string, SubjectContents> = new Map();

    // 'protected/' + s3.region + ':' + userId + '/data/'
    constructor(dir: LiveDirectory) {
        this.dir = dir;

        this.getPathType = this.getPathType.bind(this);
        this.getSubjectContents = this.getSubjectContents.bind(this);
        this.getTrialContents = this.getTrialContents.bind(this);
        this.getTrialSegmentContents = this.getTrialSegmentContents.bind(this);
        this.getReviewStatus = this.getReviewStatus.bind(this);
        this.getFolderReviewStatus = this.getFolderReviewStatus.bind(this);

        this.dir.addChangeListener(action((paths) => {
            paths.forEach((path) => {
                let pathParts = path.split('/');
                for (let i = pathParts.length - 1; i >= 0; i--) {
                    const subPath = pathParts.slice(0, i+1).join('/');
                    this.pathTypeCache.delete(subPath);
                    this.pathStatusCache.delete(subPath);
                    this.pathReviewCache.delete(subPath);
                    this.datasetContentsCache.delete(subPath);
                    this.subjectContentsCache.delete(subPath);
                }
            });
        }));

        makeObservable(this, {
            pathTypeCache: observable,
            pathStatusCache: observable,
            pathReviewCache: observable,
            datasetContentsCache: observable,
            subjectContentsCache: observable,
        });
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
                children: new Map(),
                recursive,
            };
        }
        return dir.getPath(path, recursive);
    }

    getPathType(path: string): PathType {
        if (path.startsWith('/')) {
            path = path.substring(1);
        }
        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }

        let type = this.pathTypeCache.get(path);
        if (type == null) {
            type = this.computePathType(path);
            action(() => {
                this.pathTypeCache.set(path, type!);
            });
        }
        return type;
    }

    computePathType(path: string): PathType {
        if (path.startsWith('/')) {
            path = path.substring(1);
        }
        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }

        const pathData: PathData | undefined = this.dir.getCachedPath(path, true);
        // console.log("Computing path type for " + path, pathData);
        if (pathData == null || pathData.loading) {
            return 'loading';
        }

        const child_files = pathData.files.map((file) => {
            return file.key.substring(path.length).replace(/\/$/, '').replace(/^\//, '');
        });
        const child_folders = pathData.folders.map((folder) => {
            return folder.substring(path.length).replace(/\/$/, '').replace(/^\//, '');
        });

        if (child_files.length === 0 && child_folders.length === 0) {
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
     * Gets the status of a given path, whether it's a subject or folder.
     * 
     * @param path The path to the folder to check
     */
    getPathStatus(path: string): PathStatus {
        if (path.startsWith('/')) {
            path = path.substring(1);
        }
        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }

        let status = this.pathStatusCache.get(path);
        if (status == null) {
            status = this.computePathStatus(path);
            action(() => {
                this.pathStatusCache.set(path, status!);
            });
        }
        return status;
    }

    /**
     * Gets the status of a given path, whether it's a subject or folder.
     * 
     * @param path The path to the folder to check
     */
    computePathStatus(path: string): PathStatus {
        if (path.startsWith('/')) {
            path = path.substring(1);
        }

        const pathData: PathData | undefined = this.dir.getCachedPath(path, true);
        if (pathData == null || pathData.loading) {
            return 'loading';
        }

        const pathType: PathType = this.getPathType(path);

        if (pathType === 'dataset') {
            return 'dataset';
            /*
            const folderStatus: PathStatus[] = pathData.folders.map((folder) => {
                // If the folder is the same as the path, or just the path + '/'
                if (folder.length <= path.length + 1) {
                    return 'done';
                }
                return this.getPathStatus(folder);
            });
            if (folderStatus.includes('loading')) {
                return 'loading';
            }
            else if (folderStatus.length === 0) {
                return 'needs_data';
            }
            else if (folderStatus.includes('processing')) {
                return 'processing';
            }
            else if (folderStatus.includes('waiting_for_server')) {
                return 'waiting_for_server';
            }
            else if (folderStatus.includes('slurm')) {
                return 'slurm';
            }
            else if (folderStatus.includes('error')) {
                return 'error';
            }
            else if (folderStatus.includes('ready_to_process')) {
                return 'ready_to_process';
            }
            else if (folderStatus.includes('needs_review')) {
                return 'needs_review';
            }
            else {
                return 'done';
            }
            */
        }

        if (pathType === 'subject') {
            const child_files = pathData.files.map((file) => {
                return file.key.substring(path.length).replace(/\/$/, '').replace(/^\//, '');
            });
            if (child_files.includes('_results.json')) {
                const subjectContents = this.getSubjectContents(path);
                if (subjectContents.loading) {
                    return 'loading';
                }
                for (let trial of subjectContents.trials) {
                    for (let segment of trial.segments) {
                        if (!segment.reviewFlagExists) {
                            return 'needs_review';
                        }
                    }
                }
                return 'done';
            }
            else if (child_files.includes('ERROR')) {
                return 'error';
            }
            else if (child_files.includes('PROCESSING')) {
                return 'processing';
            }
            else if (child_files.includes('SLURM')) {
                return 'slurm';
            }
            else if (child_files.includes('READY_TO_PROCESS')) {
                return 'waiting_for_server';
            }
            else if (child_files.filter((file) => {
                return file.indexOf('trials/') > 0;
            }).length > 0) {
                return 'needs_data';
            }
            else {
                return 'ready_to_process';
            }
        }

        return 'done';
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

        let dataset = this.datasetContentsCache.get(path);
        if (dataset == null) {
            dataset = {
                loading: pathData.loading,
                status: this.getPathStatus(path),
                contents: pathData.folders.filter(folder => folder !== path).map((folder) => {
                    return {
                        name: folder.substring(path.length).replace(/\/$/, '').replace(/^\//, ''),
                        path: folder,
                        status: this.getPathStatus(folder),
                        type: this.getPathType(folder),
                    };
                })
            }
            action(() => {
                this.datasetContentsCache.set(path, dataset!);
            });
        }
        return dataset;
    }

    /**
     * This will reprocess all the subjects within a directory
     * 
     * @param path 
     * @returns 
     */
    async reprocessAllSubjects(path: string): Promise<void> {
        const dir = this.dir;
        let pathData: PathData = dir.getPath(path, false);
        if (pathData.promise) {
            pathData = await pathData.promise;
        }
        for (let folder of pathData.folders) {
            if (this.getPathType(folder) === 'subject') {
                const status = this.getPathStatus(folder);
                if (status !== 'waiting_for_server' && status !== 'slurm' && status !== 'processing') {
                    await this.getSubjectViewState(folder).reprocess();
                }
                else {
                    console.log("Not reprocessing " + folder + " because it is " + status);
                }
            }
        }
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
     * This call will create an empty trial object, and optionally begin uploading files to it.
     */
    createTrial(subjectPath: string, trialName: string, markerFile?: File, grfFile?: File): Promise<void> {
        const dir = this.dir;

        let promises: Promise<void>[] = [];
        // Create the trial object as a JSON file, which will upload quickly and cause the UI to update.
        promises.push(dir.uploadText(subjectPath + (subjectPath.length > 0 ? '/' : '') + 'trials/' + trialName + '/_trial.json', '{}'));

        // Upload files. These uploads will proceed asynchronously, but we don't need to wait for them.
        const prefixPath = subjectPath + (subjectPath.length > 0 ? '/' : '') + 'trials/' + trialName;
        if (markerFile != null) {
            if (markerFile.name.endsWith('.c3d')) {
                promises.push(dir.getLiveFile(prefixPath + '/markers.c3d').uploadFile(markerFile));
            }
            else if (markerFile.name.endsWith('.trc')) {
                promises.push(dir.getLiveFile(prefixPath + '/markers.trc').uploadFile(markerFile));
            }
        }
        if (grfFile != null) {
            if (grfFile.name.endsWith('.mot')) {
                promises.push(dir.getLiveFile(prefixPath + '/grf.mot').uploadFile(grfFile));
            }
        }

        // Return the promise for the _trial.json file, which will resolve when its upload is complete.
        return Promise.all(promises).then(() => {});
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
     * This gets (and then caches) a SubjectViewState object for a given subject. This object
     * is always the same for a given subject, and is used to track the state of the subject.
     * 
     * @param path The path to the subject
     * @returns a SubjectViewState object
     */
    getSubjectViewState(path: string): SubjectViewState {
        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }
        let state = this.subjectViewStates.get(path);
        if (state == null) {
            state = new SubjectViewState(this, path);
            this.subjectViewStates.set(path, state);
        }
        return state;
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

        let subject = this.subjectContentsCache.get(path);
        if (subject == null) {
            let name = '';
            if (path.includes('/')) {
                name = path.split('/').slice(-1)[0];
            }
            const subjectJson = dir.getJsonFile(path + '/_subject.json');
            const resultsJsonPath: string = path + '/_results.json';
            const processingFlagFile: LiveFile = dir.getLiveFile(path + "/PROCESSING");
            const readyFlagFile: LiveFile = dir.getLiveFile(path + "/READY_TO_PROCESS");
            const errorFlagFile: LiveFile = dir.getLiveFile(path + "/ERROR");

            const subjectPathData: PathData = dir.getPath(path, false);
            const trialsPathData: PathData = dir.getPath(path+'/trials/', false);

            subject = {
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
            action(() => {
                this.subjectContentsCache.set(path, subject!);
            });
        }
        return subject;
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
        const dir = this.dir;

        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }
        if (path.startsWith('/')) {
            path = path.substring(1);
        }

        const segment: PathData = dir.getPath(path + '/', false);

        const name = path.split('/').slice(-1)[0];
        const resultsJsonPath = path + '/_results.json';
        const previewPath = path + '/preview.bin';
        const dataPath = path + '/data.csv';

        const reviewFlagPath = path + '/REVIEWED';
        const reviewJsonPath = path + '/review.json';

        const prefix = path.substring(0, path.lastIndexOf('/trials/'));
        const parentSubjectPath: string = prefix;
        const parentDatasetPath: string = prefix.substring(0, prefix.lastIndexOf('/'));

        return {
            loading: segment.loading,
            path: path + '/',
            name,
            parentSubjectPath,
            parentDatasetPath,
            resultsJsonPath,
            previewPath,
            dataPath,
            reviewFlagPath,
            reviewFlagExists: segment.files.map((file) => {
                return file.key;
            }).includes(reviewFlagPath),
            reviewJson: dir.getJsonFile(reviewJsonPath)
        };
    }

    /**
     * This finds the highest loaded folder that is a parent of the current path, and returns the review status for that.
     */
    getReviewStatus(path: string): FolderReviewStatus {
        const pathParts = path.split('/');
        for (let i = 0; i < pathParts.length; i++) {
            const subPath = pathParts.slice(0, i+1).join('/');
            if (this.dir.getCachedPath(subPath, true) != null) {
                return this.getFolderReviewStatus(subPath, this.getPathType(subPath));
            }
        }
        return this.getFolderReviewStatus(path, this.getPathType(path));
    }

    getFolderReviewStatus(path: string, type: PathType): FolderReviewStatus {
        if (type === 'dataset') {
            const dataset = this.getDatasetContents(path);
            let loading = false;
            let segmentsNeedReview: TrialSegmentContents[] = [];
            let segmentsReviewed: TrialSegmentContents[] = [];
            dataset.contents.forEach((content) => {
                const review = this.getFolderReviewStatus(content.path, this.getPathType(content.path));
                if (review.loading) {
                    loading = true;
                }
                segmentsNeedReview = segmentsNeedReview.concat(review.segmentsNeedReview);
                segmentsReviewed = segmentsReviewed.concat(review.segmentsReviewed);
            });
            return {
                loading,
                path,
                segmentsNeedReview,
                segmentsReviewed
            };
        }
        else if (type === 'subject') {
            const subject = this.getSubjectContents(path);
            let loading = false;
            let segmentsNeedReview: TrialSegmentContents[] = [];
            let segmentsReviewed: TrialSegmentContents[] = [];

            subject.trials.forEach((trial) => {
                trial.segments.forEach((segment) => {
                    if (segment.loading) {
                        loading = true;
                    }
                    if (segment.reviewFlagExists) {
                        segmentsReviewed.push(segment);
                    }
                    else {
                        segmentsNeedReview.push(segment);
                    }
                });
            });

            return {
                loading,
                path,
                segmentsNeedReview,
                segmentsReviewed
            };
        }
        else {
            return {
                loading: false,
                path,
                segmentsNeedReview: [],
                segmentsReviewed: []
            };
        }
    }
};

export type { PathType, DatasetContents, SubjectContents, TrialContents, TrialSegmentContents, FolderReviewStatus };
export default UserHomeDirectory;