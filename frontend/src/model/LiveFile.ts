import LiveDirectory, { PathData } from "./LiveDirectory";
import { makeObservable, observable, action } from "mobx";
import { FileMetadata } from "./S3API";

/// This is a simple object for mobx-style interaction with flag files stored in S3.
/// Flag files transmit information by either existing or not existing.
class LiveFile {
    dir: LiveDirectory;
    loading: Promise<void> | null;
    metadata: FileMetadata | null;
    name: string;
    path: string;
    parentPath: string;
    exists: boolean;
    uploading: Promise<void> | null;
    uploadProgress: number;

    constructor(dir: LiveDirectory, path: string, skipImmediateRefresh: boolean = false) {
        this.dir = dir;
        if (path.startsWith('/')) {
            path = path.substring(1);
        }
        this.path = path;
        this.name = path.split('/')[-1];
        this.parentPath = this.path.split('/').slice(0, -1).join('/') + '/';
        this.loading = null;
        this.metadata = null;
        this.exists = false;
        this.uploading = null;
        this.uploadProgress = 0;

        this.refreshFile = this.refreshFile.bind(this);
        this.uploadFlag = this.uploadFlag.bind(this);
        this.uploadFile = this.uploadFile.bind(this);
        this.delete = this.delete.bind(this);

        makeObservable(this, {
            loading: observable,
            exists: observable,
            refreshFile: action,
            uploadFile: action,
            uploadFlag: action,
        });

        dir.addPathChangeListener(this.parentPath, () => {
            this.refreshFile();
        });

        if (!skipImmediateRefresh) {
            this.refreshFile();
        }
    }

    /**
     * Uploads a simple flag file, just containing the date, if one did not already exist here.
     */
    uploadFlag(): Promise<void> {
        return this.dir.uploadText(this.path, (new Date()).getTime().toString()).then(action(() => {
            this.exists = true;
        }));
    }

    /**
     * Uploads a file from disk, probably from a drag and drop interface.
     */
    uploadFile(file: File): Promise<void> {
        this.uploading = this.dir.uploadFile(this.path, file, action((percentage: number) => {
            this.uploadProgress = percentage;
        })).then(action(() => {
            this.uploading = null;
            this.exists = true;
            this.metadata = {
                key: this.path,
                lastModified: new Date(),
                size: file.size
            };
        }));
        return this.uploading;
    }

    /**
     * This downloads a file
     */
    download(): void {
        return this.dir.downloadFile(this.path);
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
        const pathData = this.dir.getCachedPath(this.path, false);
        const loading = pathData?.loading ?? true;
        if (loading && pathData?.promise != null) {
            this.loading = pathData.promise.then(action((resultData: PathData) => {
                this.exists = resultData.files.map((file) => file.key).includes(this.path);
                if (this.exists) {
                    this.metadata = resultData.files.filter((file) => file.key === this.path)[0];
                }
            })).finally(action(() => {
                this.loading = null;
            }));
            return this.loading;
        }
        else {
            const files = pathData?.files ?? [];
            this.exists = files.map((file) => file.key).includes(this.path);
            if (this.exists) {
                this.metadata = files.filter((file) => file.key === this.path)[0];
            }
            this.loading = null;
            return Promise.resolve();
        }
    }
}

export default LiveFile;