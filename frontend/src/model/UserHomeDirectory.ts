import LiveDirectory, {PathData} from "./LiveDirectory";
import { makeObservable, action, observable } from 'mobx';
import LiveJsonFile from "./LiveJsonFile";
import LiveFlagFile from "./LiveFlagFile";

type PathType = 'dataset' | 'subject' | 'trial' | 'segment' | 'trials_folder' | '404' | 'loading';

type DatasetContents = {
    loading: boolean;
    contents: {name: string, path: string, type: PathType}[]
};

type SubjectContents = {
    loading: boolean;
    subjectJson: LiveJsonFile | null;
    testFlagFile: LiveFlagFile | null;
    trials: {name: string, path: string}[]
};

class UserHomeDirectory {
    dir: LiveDirectory | null;

    // Login relate data
    loadingLoginState: boolean = true;
    authenticated: boolean = false;
    email: string = '';

    // 'protected/' + s3.region + ':' + userId + '/data/'
    constructor(dir?: LiveDirectory) {
        this.dir = dir ?? null;

        this.setDirectory = this.setDirectory.bind(this);
        this.setEmail = this.setEmail.bind(this);
        this.setAuthFailed = this.setAuthFailed.bind(this);
        this.getPathType = this.getPathType.bind(this);

        makeObservable(this, {
            dir: observable,
            loadingLoginState: observable,
            authenticated: observable,
            email: observable,
            setDirectory: action,
            setEmail: action,
            setAuthFailed: action,
        });
    }

    setDirectory(dir: LiveDirectory): void {
        console.log("Setting home directory");
        this.dir = dir;
    }

    setEmail(email: string): void {
        this.authenticated = true;
        this.loadingLoginState = false;
        this.email = email;
    }

    setAuthFailed(): void {
        this.authenticated = false;
        this.loadingLoginState = false;
        this.email = '';
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
        const dir = this.dir;
        if (dir == null) {
            return 'loading';
        }
        if (path.startsWith('/')) {
            path = path.substring(1);
        }

        const pathData: PathData | undefined = dir.getCachedPath(path);
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

        // The presence of marker files indicate that this is a segment
        if (child_files.includes('markers.c3d') || 
            child_files.includes('markers.trc') || 
            child_files.includes('grf.mot')) {
            return 'segment';
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
        const dir = this.dir;
        if (dir == null) {
            return {
                loading: true,
                contents: [],
            };
        }

        const pathData: PathData = dir.getPath(path, false);
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
     * If this is a subject, we will return the contents.
     * 
     * @param path The path to the subject
     */
    getSubjectContents(path: string): SubjectContents {
        const dir = this.dir;
        if (dir == null) {
            return {
                loading: true,
                subjectJson: null,
                testFlagFile: null,
                trials: [],
            };
        }

        /*
        const thisPathData = dir.getPath(path, false);
        if (thisPathData.promise) {
            thisPathData.promise.then((result) => {
                console.log(result);
            });
        }
        else {
            console.log(thisPathData);
        }
        */

        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }
        const subjectJson = dir.getJsonFile(path + '/_subject.json');
        const testFlagFile = dir.getFlagFile(path + '/TEST');

        const trialsPathData: PathData = dir.getPath(path+'/trials/', false);
        return {
            loading: trialsPathData.loading,
            subjectJson,
            testFlagFile,
            trials: trialsPathData.folders.map((folder) => {
                return {
                    name: folder.substring(path.length).replace(/\/$/, '').replace(/^\//, ''),
                    path: folder,
                };
            })
        };
    }
};

export type { PathType, DatasetContents };
export default UserHomeDirectory;