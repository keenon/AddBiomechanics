import LiveDirectory, { PathData } from "./LiveDirectory";
import { makeObservable, observable, action } from "mobx";

/// This is a simple object for mobx-style interaction with flag files stored in S3.
/// Flag files transmit information by either existing or not existing.
class LiveFlagFile {
    dir: LiveDirectory;
    loading: Promise<void> | null;
    path: string;
    parentPath: string;
    exists: boolean;

    constructor(dir: LiveDirectory, path: string) {
        this.dir = dir;
        if (path.startsWith('/')) {
            path = path.substring(1);
        }
        this.path = path;
        this.parentPath = this.path.split('/').slice(0, -1).join('/') + '/';
        this.loading = null;
        this.exists = false;

        this.refreshFile = this.refreshFile.bind(this);
        this.upload = this.upload.bind(this);
        this.delete = this.delete.bind(this);

        makeObservable(this, {
            loading: observable,
            exists: observable,
            refreshFile: action,
        });

        dir.addPathChangeListener(this.parentPath, () => {
            this.refreshFile();
        });

        this.refreshFile();
    }

    /**
     * Creates a flag file, if one did not already exist here.
     */
    upload(): Promise<void> {
        return this.dir.uploadText(this.path, (new Date()).getTime().toString()).then(action(() => {
            this.exists = true;
        }));
    }

    /**
     * Deletes a flag file.
     */
    delete(): Promise<void> {
        return this.dir.delete(this.path).then(action(() => {
            this.exists = false;
        }));
    }

    /**
     * This will do a refresh of the contents of the file from S3
     */
    refreshFile(): Promise<void> {
        const pathData = this.dir.getPath(this.parentPath, false);
        if (pathData.loading && pathData.promise != null) {
            this.loading = pathData.promise.then(action((resultDate: PathData) => {
                this.exists = resultDate.files.map((file) => file.key).includes(this.path);
            })).finally(action(() => {
                this.loading = null;
            }));
            return this.loading;
        }
        else {
            this.exists = pathData.files.map((file) => file.key).includes(this.path);
            this.loading = null;
            return Promise.resolve();
        }
    }
}

export default LiveFlagFile;