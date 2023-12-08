import { S3Client, ListObjectsV2Command, ListObjectsV2CommandOutput, GetObjectCommand, DeleteObjectCommand, DeleteObjectCommandOutput } from '@aws-sdk/client-s3';
import { Auth } from "aws-amplify";
import { Credentials, getAmplifyUserAgent } from '@aws-amplify/core';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';
import RobustUpload from './infra/RobustUpload';
import { AxiosHttpHandler, SEND_UPLOAD_PROGRESS_EVENT, AxiosHttpHandlerOptions } from './infra/RobustHandler';

/// This holds the low-level copy of the S3 output, without nulls
type FileMetadata = {
    key: string;
    lastModified: Date;
    size: number;
}

abstract class S3API {
    region: string = 'us-west-2';

    abstract loadPathData(path: string, recursive: boolean, abortController?: AbortController): Promise<{files: FileMetadata[], folders: string[]}>;

    abstract getSignedURL(path: string, expiresIn: number): Promise<string>;
    abstract downloadText(path: string): Promise<string>;
    abstract uploadText(path: string, text: string): Promise<void>;
    abstract uploadFile(path: string, contents: File, progressCallback: (percentage: number) => void): Promise<void>;

    abstract delete(path: string): Promise<void>;
    abstract deleteByPrefix(path: string): Promise<void>;

    abstract getNetworkErrorMessage(): string | null;
    abstract addNetworkErrorListener(listener: (message: string | null) => void): void;
};

class S3APIMock extends S3API {
    files: FileMetadata[];
    filesChangeListeners: Map<string, ((loading: boolean, files: FileMetadata[]) => void)[]>;
    fileContents: Map<string, string>;
    networkOutage: boolean = false;
    networkErrorMessage: string | null = null;
    networkErrorMessageListeners: ((message: string | null) => void)[] = [];
    networkCallCount: number = 0;
    mockFileUploadPartialProgress: boolean = false;
    mockFileUploadResolves: (() => void)[] = [];

    // This allows us to set the mock to have the first N loads succeed, then hang the next one
    mockLoadBeforeHalt: number = -1;
    // If `mockLoadBeforeHalt` hits zero during a load, that load will stall, and a callback will be appended to this list to allow you to continue it
    mockLoadContinues: (() => void)[] = []

    constructor() {
        super();
        this.files = [];
        this.filesChangeListeners = new Map();
        this.fileContents = new Map();

        this.setFiles = this.setFiles.bind(this);
        this.setFileContents = this.setFileContents.bind(this);
        this.getFileContents = this.getFileContents.bind(this);
        this.setNetworkOutage = this.setNetworkOutage.bind(this);
        this.loadPathData = this.loadPathData.bind(this);
        this.downloadText = this.downloadText.bind(this);
        this.uploadText = this.uploadText.bind(this);
        this.uploadFile = this.uploadFile.bind(this);
        this.setNetworkErrorMessage = this.setNetworkErrorMessage.bind(this);
        this.getNetworkErrorMessage = this.getNetworkErrorMessage.bind(this);
        this.addNetworkErrorListener = this.addNetworkErrorListener.bind(this);
    }

    setFiles(files: FileMetadata[]) {
        this.files = files;
    }

    setFilePathsExist(files: string[]) {
        this.files = files.map((f) => {
            return {
                key: f,
                lastModified: new Date(),
                size: 0,
            }
        });
    }

    setFileContents(path: string, contents: string) {
        this.fileContents.set(path, contents);
    }

    getFileContents(path: string): string {
        return this.fileContents.get(path) || "";
    }

    setNetworkOutage(outage: boolean) {
        this.networkOutage = outage;
    }

    loadPathData(path: string, recursive: boolean, abortController?: AbortController): Promise<{files: FileMetadata[], folders: string[]}> {
        this.networkCallCount ++;
        return new Promise((resolve, reject) => {
            if (this.networkOutage) {
                reject("Network outage");
                return;
            }

            let removeCancelListeners: (() => void)[] = [];
            const cancelListener = () => {
                removeCancelListeners.forEach(l => l());
                console.log("Mocking a cancelled load");
                reject("Cancelled");
            };
            if (abortController) {
                abortController.signal.addEventListener("abort", cancelListener);
                removeCancelListeners.push(() => {
                    abortController.signal.removeEventListener("abort", cancelListener);
                });
            }

            const finishLoad = () => {
                if (!recursive) {
                    const allFiles = this.files.filter(f => f.key.startsWith(path));
                    // These will be returned as folder names
                    const filesWithSlashAfterPath = allFiles.filter(f => f.key.substring(path.length).indexOf("/") !== -1);
                    const folderNames = [...new Set(filesWithSlashAfterPath.map(f => path + f.key.substring(path.length).split("/")[0]))].map(f => f+"/");
                    // These will be returned directly
                    const filesWithoutSlashAfterPath = allFiles.filter(f => f.key.substring(path.length).indexOf("/") === -1);
                    // Return the resolution
                    removeCancelListeners.forEach(l => l());
                    resolve({
                        files: filesWithoutSlashAfterPath,
                        folders: folderNames
                    });
                }
                else {
                    removeCancelListeners.forEach(l => l());
                    resolve({
                        files: this.files.filter(f => f.key.startsWith(path)),
                        folders: []
                    });
                }
            };

            if (this.mockLoadBeforeHalt >= 0) {
                if (this.mockLoadBeforeHalt === 0) {
                    this.mockLoadContinues.push(finishLoad);
                }
                else {
                    this.mockLoadBeforeHalt --;
                    finishLoad();
                }
            }
            else {
                finishLoad();
            }
        });
    }

    getSignedURL(path: string, expiresIn: number): Promise<string> {
        this.networkCallCount ++;

        return new Promise((resolve, reject) => {
            if (this.networkOutage) {
                reject("Network outage");
                return;
            }
            resolve("https://example.com");
        });
    }

    downloadText(path: string): Promise<string> {
        this.networkCallCount ++;

        return new Promise((resolve, reject) => {
            if (this.networkOutage) {
                reject("Network outage");
                return;
            }
            let contents = this.fileContents.get(path);
            if (contents != null) {
                resolve(contents);
            } else {
                reject("File not found");
            }
        });
    }

    uploadText(path: string, text: string): Promise<void> {
        this.networkCallCount ++;

        return new Promise((resolve, reject) => {
            if (this.networkOutage) {
                reject("Network outage");
                return;
            }
            else if (this.mockFileUploadPartialProgress) {
                // Return a promise that never resolevs
                this.mockFileUploadResolves.push(() => {
                    this.files = this.files.filter(f => f.key !== path);
                    this.files.push({
                        key: path,
                        lastModified: new Date(),
                        size: text.length
                    });
                    this.fileContents.set(path, text);
                    resolve();
                });
            }
            else {
                this.files = this.files.filter(f => f.key !== path);
                this.files.push({
                    key: path,
                    lastModified: new Date(),
                    size: text.length
                });
                this.fileContents.set(path, text);
                resolve();
            }
        });
    }

    setMockFileUploadPartialProgress(partialProgress: boolean) {
        this.mockFileUploadPartialProgress = partialProgress;
    }

    resolveMockFileUploads() {
        this.mockFileUploadResolves.forEach(r => r());
        this.mockFileUploadResolves = [];
    }

    uploadFile(path: string, contents: File, progressCallback: (percentage: number) => void): Promise<void>
    {
        this.networkCallCount++;
        if (this.networkOutage) {
            return Promise.reject("network outage");
        }
        else if (this.mockFileUploadPartialProgress) {
            progressCallback(0.5);
            // Return a promise that never resolevs
            return new Promise((resolve, reject) => {
                this.mockFileUploadResolves.push(() => {
                    this.files = this.files.filter(f => f.key !== path);
                    this.files.push({
                        key: path,
                        lastModified: new Date(),
                        size: contents.size
                    });
                    this.fileContents.set(path, "[File]");
                    resolve();
                });
            });
        }
        else {
            this.files = this.files.filter(f => f.key !== path);
            this.files.push({
                key: path,
                lastModified: new Date(),
                size: contents.size
            });
            this.fileContents.set(path, "[File]");
            return Promise.resolve();
        }
    }

    delete(path: string): Promise<void>
    {
        this.networkCallCount++;
        return new Promise((resolve, reject) => {
            if (this.networkOutage) {
                reject("Network outage");
                return;
            }
            this.fileContents.delete(path);
            this.files = this.files.filter(f => f.key !== path);
            resolve();
        });
    }

    deleteByPrefix(path: string): Promise<void>
    {
        return new Promise((resolve, reject) => {
            if (this.networkOutage) {
                reject("Network outage");
                return;
            }
            this.fileContents.forEach((v, k) => {
                if (k.startsWith(path)) {
                    this.fileContents.delete(k);
                }
            });
            resolve();
        });
    }

    setNetworkErrorMessage(message: string | null) {
        this.networkErrorMessage = message;
        this.networkErrorMessageListeners.forEach(l => l(message));
    }

    getNetworkErrorMessage(): string | null {
        return this.networkErrorMessage;
    }

    addNetworkErrorListener(listener: (message: string | null) => void): void {
        this.networkErrorMessageListeners.push(listener);
    }
}

class S3APIImpl extends S3API {
    s3client: Promise<S3Client>;
    bucketName: string = "";
    myIdentityId: string = "";

    networkErrorMessage: string | null = null;
    networkErrorMessageListeners: ((message: string | null) => void)[] = [];

    constructor(region: string, bucketName: string) {
        super();
        this.region = region;
        this.bucketName = bucketName;
        this.s3client = new Promise<S3Client>((resolve, reject) => {
            Auth.currentCredentials().then((credentials) => {
                this.myIdentityId = credentials.identityId.replace("us-west-2:", "");

                const INVALID_CRED = { accessKeyId: '', secretAccessKey: '' };
                const credentialsProvider = async () => {
                    try {
                        const credentials = await Credentials.get();
                        if (!credentials) return INVALID_CRED;
                        const cred = Credentials.shear(credentials);
                        return cred;
                    } catch (error) {
                        console.warn('credentials provider error', error);
                        return INVALID_CRED;
                    }
                };

                // Authenticated S3 client
                resolve(new S3Client({
                    region: this.region,
                    requestHandler: new AxiosHttpHandler(),
                    // Using provider instead of a static credentials, so that if an upload task was in progress, but credentials gets
                    // changed or invalidated (e.g user signed out), the subsequent requests will fail.
                    credentials: credentialsProvider,
                    customUserAgent: getAmplifyUserAgent()
                }));
            }).catch((err) => {
                console.log(err);
                reject(err);
            });
        });

        this.loadPathData = this.loadPathData.bind(this);
        this.downloadText = this.downloadText.bind(this);
        this.uploadText = this.uploadText.bind(this);
    }

    async listAsync(path: string, recursive: boolean, continuationToken?: string, filesSoFar?: FileMetadata[], foldersSoFar?: string[], abortController?: AbortController): Promise<{ files: FileMetadata[], folders: string[] }> {
        const listObjectsCommand = new ListObjectsV2Command({
            Bucket: this.bucketName,
            Prefix: path,
            Delimiter: recursive ? undefined : '/',
            MaxKeys: 1000,
            ContinuationToken: continuationToken
        });

        const client = await this.s3client;
        const output: ListObjectsV2CommandOutput = await client.send(listObjectsCommand, { abortController: abortController } as any);

        let files: FileMetadata[] = filesSoFar ? [...filesSoFar] : [];
        if (output.CommonPrefixes == null && output.Contents == null && output.IsTruncated == null && output.KeyCount == null) {
            // Something bad happened to our request, so just try again
            return this.listAsync(path, recursive, output.NextContinuationToken);
        }
        else {
            if (output.Contents != null && output.Contents.length > 0) {
                for (let i = 0; i < output.Contents.length; i++) {
                    let file = output.Contents[i];
                    if (file.Key != null && file.LastModified != null && file.Size != null) {
                        files.push({
                            key: file.Key,
                            lastModified: file.LastModified,
                            size: file.Size
                        });
                    }
                }
            }

            let folders: string[] = foldersSoFar ? [...foldersSoFar] : [];
            if (output.CommonPrefixes != null && output.CommonPrefixes.length > 0) {
                for (let i = 0; i < output.CommonPrefixes.length; i++) {
                    let folder = output.CommonPrefixes[i];
                    if (folder.Prefix != null) {
                        let folderFullPath = folder.Prefix;
                        folders.push(folderFullPath);
                    }
                }
            }

            if (output.NextContinuationToken != null) {
                return this.listAsync(path, recursive, output.NextContinuationToken, files, folders);
            }

            return {
                files,
                folders
            }
        }
    };

    loadPathData(path: string, recursive: boolean, abortController?: AbortController): Promise<{files: FileMetadata[], folders: string[]}> {
        return this.listAsync(path, recursive, undefined, undefined, undefined, abortController).then((results) => {
            return results;
        });
    };

    /**
     * This gets a signed URL, then fetches it.
     */
    fetchFile = (path: string, bodyType: 'blob' | 'text', progressCallback?: (progress: number) => void) => {
        return this.getSignedURL(path, 3600).then((signedURL) => {
            return new Promise<any>((resolve, reject) => {
                const xhr = new XMLHttpRequest();
                xhr.onload = () => {
                    if (xhr.status === 200) {
                        resolve(xhr.response);
                    }
                    else {
                        reject("Got status "+xhr.status);
                    }
                };
                xhr.onerror = () => {
                    reject();
                }
                xhr.onabort = () => {
                    reject();
                }
                if (progressCallback) {
                    xhr.onprogress = (event: any) => {
                        progressCallback(event.loaded / event.total);
                    }
                }
                xhr.responseType = bodyType;
                xhr.open('GET', signedURL);
                try {
                    xhr.send();
                }
                catch (e) {
                    reject();
                }
            });
            // return fetch(signedURL, {
            //     cache: 'no-cache'
            // });
        });
    };

    getSignedURL(path: string, expiresIn: number): Promise<string>
    {
        const objectCommand = new GetObjectCommand({
            Bucket: this.bucketName,
            Key: path,
        });
        return this.s3client.then(client => getSignedUrl(client, objectCommand, { expiresIn }));
    };

    downloadText(path: string): Promise<string>
    {
        return this.fetchFile(path, 'text').then((result) => {
            this.setNetworkErrorMessage(null);
            return result;
        }).catch(e => {
            if (e === "Got status 404") {
                // 404s should be treated as a file not found, and do not indicate that the network is down
                throw e;
            }
            else {
                // Other network errors should be treated as a network error
                this.setNetworkErrorMessage("We got an error trying to download a file!");
                console.log("DownloadText() error: " + path);
                console.log(e);
                throw e;
            }
        });
    }

    uploadText(path: string, text: string): Promise<void>
    {
        return this.upload(path, text);
    }

    uploadFile(path: string, contents: File, progressCallback: (percentage: number) => void): Promise<void>
    {
        return this.upload(path, contents, progressCallback);
    }

    /**
     * This attempts to delete a file in S3
     * 
     * @param path The file to delete
     * @returns a promise that resolves when the full operation is complete
     */
    delete = (path: string) => {
        const deleteCommand = new DeleteObjectCommand({
            Bucket: this.bucketName,
            Key: path,
        });
        return this.s3client.then(client => client.send(deleteCommand).then((result: DeleteObjectCommandOutput) => {
            console.log("Delete", result);
            if (result != null && result.$metadata != null && result.$metadata.httpStatusCode != null) {
                this.setNetworkErrorMessage(null);
                return;
            }
            else {
                this.setNetworkErrorMessage("We got an error trying to delete a file!");
                console.log("delete() error: " + path);
                throw new Error("Got an error trying to delete a file");
            }
        }).catch(e => {
            this.setNetworkErrorMessage("We got an error trying to delete a file!");
            console.log("delete() error: " + path);
            console.log(e);
            throw e;
        }));
    }

    /**
     * Deletes all the files that match a given prefix.
     * 
     * @param prefix The prefix to match to files, and if they match, delete them
     * @returns a promise that resolves when the full operation is complete
     */
    deleteByPrefix(prefix: string): Promise<void> {
        return this.loadPathData(prefix, true).then(({folders, files}) => {
            let allPromises: Promise<void>[] = [];
            files.forEach((v) => {
                if (v.key.startsWith(prefix)) {
                    allPromises.push(this.delete(v.key));
                }
            });
            return (Promise.all(allPromises) as unknown) as Promise<void>;
        });
    }

    setNetworkErrorMessage(message: string | null) {
        this.networkErrorMessage = message;
        this.networkErrorMessageListeners.forEach(l => l(message));
    }

    getNetworkErrorMessage(): string | null
    {
        return this.networkErrorMessage;
    }

    addNetworkErrorListener(listener: (message: string | null) => void): void
    {
        this.networkErrorMessageListeners.push(listener);
    }

    ////////////////////////////////////////////////////////////////////////////////////////////////
    // Internal utils methods
    ////////////////////////////////////////////////////////////////////////////////////////////////

    /**
     * This uploads a file to the server, and notifies PubSub of having done so.
     * 
     * @param path the path to upload to
     * @param contents the contents to upload
     * @param progressCallback OPTIONAL: a callback to receive with updates on upload progress
     * @returns a promise that resolves when the full operation is complete
     */
    upload(path: string, contents: File | string, progressCallback: (percentage: number) => void = () => { }): Promise<void> {
        const fullPath = path;
        const updatedFile = {
            key: fullPath,
            lastModified: (new Date()).getTime(), // = now
            size: new Blob([contents]).size
        };
        return this.s3client.then((client) => {
            const uploadObject = new RobustUpload(client, this.region, this.bucketName, fullPath, contents, '');
            return uploadObject.upload((progress) => {
                progressCallback(progress.loaded / progress.total);
            }).then((response: any) => {
                progressCallback(1.0);
                this.setNetworkErrorMessage(null);
                console.log("Finished upload for "+path+" contents: \""+contents+"\"");
                return;
            }).catch((e: any) => {
                this.setNetworkErrorMessage("We got an error trying to upload data!");
                console.error("Error on RobustUpload.upload(), caught in .errorCallback() handler", e);
                throw e;
            });
        });
    }
}

export type { FileMetadata };
export { S3API, S3APIMock, S3APIImpl };
export default S3API;