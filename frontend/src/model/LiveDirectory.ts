import { PubSubSocket } from "./PubSubSocket";
import { FileMetadata, S3API } from "./S3API"; 
import { makeObservable, action, observable, ObservableMap } from 'mobx';
import LiveJsonFile from "./LiveJsonFile";
import LiveFlagFile from "./LiveFlagFile";

type PathData = {
    loading: boolean;
    promise: Promise<PathData> | null;
    path: string;
    folders: string[];
    files: FileMetadata[];
    recursive: boolean;
    readonly?: boolean;
};

abstract class LiveDirectory {
    prefix: string;
    jsonFiles: Map<string, LiveJsonFile>;
    flagFiles: Map<string, LiveFlagFile>;

    constructor(prefix: string) {
        this.prefix = prefix;
        this.jsonFiles = new Map();
        this.flagFiles = new Map();
        this.getJsonFile = this.getJsonFile.bind(this);
    }

    abstract faultInPath(path: string): Promise<void>;
    abstract getPath(path: string, recursive: boolean): PathData;
    abstract getCachedPath(path: string): PathData | undefined;
    abstract addPathChangeListener(path: string, listener: (newData: PathData) => void): void;

    abstract getSignedURL(path: string, expiresIn: number): Promise<string>;
    abstract downloadText(path: string): Promise<string>;
    abstract downloadFile(path: string): void;
    abstract uploadText(path: string, text: string): Promise<void>;
    abstract uploadFile(path: string, contents: File, progressCallback: (percentage: number) => void): Promise<void>;
    getJsonFile(path: string): LiveJsonFile {
        let file = this.jsonFiles.get(path);
        if (file == null) {
            file = new LiveJsonFile(this, path);
            this.jsonFiles.set(path, file);
        }
        return file;
    }
    getFlagFile(path: string): LiveFlagFile {
        let file = this.flagFiles.get(path);
        if (file == null) {
            file = new LiveFlagFile(this, path);
            this.flagFiles.set(path, file);
        }
        return file;
    }

    abstract delete(path: string): Promise<void>;
    abstract deleteByPrefix(path: string): Promise<void>;
};

class LiveDirectoryImpl extends LiveDirectory {
    s3: S3API;
    pubsub: PubSubSocket;
    pathCache: ObservableMap<string, PathData>;
    pathChangeListeners: Map<string, ((newData: PathData) => void)[]>;
    faultingIn: Map<string, Promise<void>>;

    constructor(prefix: string, s3: S3API, pubsub: PubSubSocket) {
        super(prefix);
        this.s3 = s3;
        this.pubsub = pubsub;
        this.pathCache = observable.map(new Map<string, PathData>(), {
            deep: false
        });
        this.pathChangeListeners = new Map<string, ((newData: PathData) => void)[]>();
        this.faultingIn = new Map();

        this.getPath = this.getPath.bind(this);
        this.faultInPath = this.faultInPath.bind(this);
        this.getCachedPath = this.getCachedPath.bind(this);
        this._setCachedPath = this._setCachedPath.bind(this);
        this._onReceivedPubSubUpdate = this._onReceivedPubSubUpdate.bind(this);
        this._onReceivedPubSubDelete = this._onReceivedPubSubDelete.bind(this);
        this.addPathChangeListener = this.addPathChangeListener.bind(this);

        makeObservable(this, {
            pathCache: observable,
            _setCachedPath: action,
            _onReceivedPubSubUpdate: action,
            _onReceivedPubSubDelete: action
        });

        // Register PubSub update listener
        // const updateTopic = "/" + this.pubsub.deployment + "/UPDATE/" + prefix + "#";
        const updateTopic = "/" + this.pubsub.deployment + "/UPDATE/#";
        this.pubsub.subscribe(updateTopic, ({topic, message}) => {
            const msg: any = JSON.parse(message);
            this._onReceivedPubSubUpdate({
                key: msg.key, 
                lastModified: new Date(msg.lastModified),
                size: msg.size
            });
        });

        // Register PubSub delete listener
        // const deleteTopic = "/" + this.pubsub.deployment + "/DELETE/" + prefix + "#";
        const deleteTopic = "/" + this.pubsub.deployment + "/DELETE/#";
        this.pubsub.subscribe(deleteTopic, ({topic, message}) => {
            const msg: any = JSON.parse(message);
            this._onReceivedPubSubDelete(msg.key);
        });
    }

    /**
     * This will fault in the given path, and all of its children recursively. This will attempt 
     * to do the loading in a way that delivers rapid visual responsiveness to the user.
     * 
     * @param originalPath the path on this directory to load in recursively
     * @returns 
     */
    faultInPath(originalPath: string): Promise<void> {
        let promise = this.faultingIn.get(originalPath);
        if (promise == null) {
            promise = new Promise<void>((resolve, reject) => {
                const pathData: PathData = this.getPath(originalPath, false);

                const loadRecursive = (folderData: PathData) => {
                    // Load each child recursively
                    Promise.all(folderData.folders.map((folder) => {
                        return this.getPath(folder, true).promise ?? Promise.resolve();
                    })).then(() => {
                        resolve();
                    }).catch((e) => {
                        reject(e);
                    });
                }

                // If the path is already loaded recursively, then we're done
                if (!pathData.loading && pathData.recursive) {
                    resolve();
                }
                else if (!pathData.loading) {
                    loadRecursive(pathData);
                }
                else if (pathData.promise != null) {
                    pathData.promise.then(loadRecursive);
                }
                else {
                    console.error("PathData was loading, but promise was null. This should never happen.");
                    // load recursively anyways, to attempt to recover smoothly from the error
                    loadRecursive(pathData);
                }
            });
        }
        this.faultingIn.set(originalPath, promise);
        return promise;
    }

    getPath(originalPath: string, recursive: boolean = false): PathData {
        let prefix = this.prefix;
        if (!prefix.endsWith('/')) {
            prefix += '/';
        }
        const path = this.normalizePath(originalPath);

        const cached: PathData | undefined = this.getCachedPath(originalPath);
        // Check if we've already loaded this path
        if (cached != null) {
            if (recursive && !cached.recursive) {
                // Then we still want to load this path, but recursively now
            }
            else {
                // This is a redundant call, we don't need to load this one
                return cached;
            }
        }

        // If we reach this point, the path has not yet been loaded
        // Kick off a load for the PathData, and keep around a promise for that load completing
        const promise: Promise<PathData> = this.s3.loadPathData(path, recursive).then(action(({folders, files}) => {
            // This is a folder, we have to issue another load to get the children
            if (!recursive && !path.endsWith('/') && folders.length == 1 && folders[0] == path + '/') {
                const withSlash: PathData = this.getPath(originalPath + '/', recursive);
                this._setCachedPath(path, withSlash);
                const promise = withSlash.promise;
                if (promise != null) {
                    promise.then((result) => {
                        this._setCachedPath(path, result);
                    });
                    return promise;
                }
                else {
                    return Promise.reject("Promise on recursive withSlash call was null. This should never happen.");
                }
            }
            else {
                files = files.map((file) => {
                        return {
                            // Trim the prefix, and leading slashes
                            key: file.key.substring(prefix.length).replace(/^\//, ''),
                            lastModified: file.lastModified,
                            size: file.size,
                        };
                    });
                if (recursive) {
                    // If we loaded this recursively, then we need to infer the folder paths from the file paths
                    const originalPathWithSlash = originalPath + (originalPath.endsWith('/') ? '' : '/');
                    folders = [...new Set(files.filter((file) => {
                        return file.key.substring(originalPathWithSlash.length).includes('/');
                    }).map((file) => {
                        return file.key.substring(0, file.key.indexOf('/', originalPathWithSlash.length) + 1);
                    }))];
                }
                else {
                    // Remove the prefix from the folder paths
                    folders = folders.map((folder) => {
                        return folder.substring(prefix.length).replace(/^\//, '');
                    });
                }
                const result: PathData = {
                    loading: false,
                    promise: null,
                    path,
                    folders,
                    files,
                    recursive: recursive,
                };
                this._setCachedPath(path, result);
                return result;
            }
        }));
        if (cached == null) {
            // Create a stub that is loading, and leave a non-null promise in it that will resolve when the load completes
            const stub: PathData = {
                loading: true,
                promise: promise,
                path,
                folders: [],
                files: [],
                recursive: recursive,
            };
            this._setCachedPath(path, stub);
            // In the mean time, return the stub saying that we're loading the data
            return stub;
        }
        else {
            // Update the promise, but otherwise just return the cached path
            cached.promise = promise;
            return cached;
        }
    }

    normalizePath(path: string): string {
        if (path.startsWith('/')) {
            path = path.substring(1);
        }
        let prefix = this.prefix;
        if (!prefix.endsWith('/')) {
            prefix += '/';
        }
        // Replace any accidental // with /
        path = path.replace(/\/\//g, '/');
        return prefix + path;
    }

    getCachedPath(originalPath: string): PathData | undefined {
        if (originalPath.startsWith('/')) {
            originalPath = originalPath.substring(1);
        }
        const normalizedPath = this.normalizePath(originalPath);
        const cached = this.pathCache.get(normalizedPath);
        if (cached != null) return cached;

        // Check if we've loaded any parent path recursively, in which case we can infer the contents of this path
        // without having to load it.
        const pathParts = originalPath.split('/');
        if (pathParts[-1] === '') {
            pathParts.pop();
        }
        for (let i = pathParts.length; i >= 0; i--) {
            for (let slash = 0; slash <= 1; slash++) {
                const parentPath = pathParts.slice(0, i).join('/') + (slash == 0 ? '' : '/');
                const normalizedParentPath = this.normalizePath(parentPath);
                const cachedParentPath: PathData | undefined = this.pathCache.get(normalizedParentPath);
                if (cachedParentPath != null && cachedParentPath.recursive) {
                    // We've already loaded the parent path recursively, so we can infer the contents of this path
                    // without having to load it.
                    let allFiles = cachedParentPath.files.filter((file) => {
                        return file.key.startsWith(originalPath);
                    });
                    const originalPathWithSlash = originalPath + (originalPath.endsWith('/') ? '' : '/');
                    let folders: string[] = [...new Set(allFiles.filter((file) => {
                        return file.key.substring(originalPathWithSlash.length).includes('/');
                    }).map((file) => {
                        return file.key.substring(0, file.key.indexOf('/', originalPathWithSlash.length + 1) + 1);
                    }))];
                    const result: PathData = {
                        loading: false,
                        promise: null,
                        path: originalPath,
                        folders: folders,
                        files: allFiles,
                        recursive: true,
                    };
                    this._setCachedPath(originalPath, result);
                    return result;
                }
            }
        }

        // If we reach here, there's no parent to be found
        return undefined;
    }

    addPathChangeListener(path: string, listener: (newData: PathData) => void): void
    {
        path = this.normalizePath(path);
        this.pathChangeListeners.set(path, [...(this.pathChangeListeners.get(path) ?? []), listener]);
    }

    _setCachedPath(normalizedPath: string, data: PathData) {
        this.pathCache.set(normalizedPath, data);
        for (let listener of this.pathChangeListeners.get(normalizedPath) ?? []) {
            listener(data);
        }
    }

    _onReceivedPubSubUpdate(file: FileMetadata) {
        // Look for any already loaded PathData objects that contain 
        // this file, which is only the immediate parent, and itself
        const localPath = file.key.substring(this.prefix.length);
        file.key = localPath;

        const localPathParts: string[] = localPath.split('/');
        // For every level of hierarchy depth, we want to check if that path has already been 
        // loaded (either with a trailing slash or without) and then send appropriate updates.
        for (let i = localPathParts.length; i >= 0; i--) {
            let localSubPath = localPathParts.slice(0, i).join('/');
            if (!this.prefix.endsWith('/') && i > 0) {
                localSubPath = '/' + localSubPath;
            }
            const fullPath = this.prefix + localSubPath;
            for (let slash = 0; slash <= 1; slash++) {
                const pathToCheck = fullPath + (slash == 0 ? '' : '/');

                // 1. Check if this file has already been loaded, and if so update it
                const cachedData: PathData | undefined = this.pathCache.get(pathToCheck);
                if (cachedData) {
                    // Check if we're missing the folder for this new path, and if so create it
                    let folders: string[] = cachedData.folders;
                    let anyChanged: boolean = false;
                    if (i < localPathParts.length - 1) {
                        const folderName = localSubPath + (localSubPath.length > 0 ? '/' : '') + localPathParts[i] + '/';
                        if (!folders.includes(folderName)) {
                            folders.push(folderName);
                            anyChanged = true;
                        }
                    }
                    let updatedCacheData: PathData = {...cachedData, folders};

                    if (!updatedCacheData.loading) {
                        if (updatedCacheData.recursive || i >= localPathParts.length - 1) {
                            if (!updatedCacheData.files.map(f => f.key).includes(localPath)) {
                                updatedCacheData.files.push(file);
                                anyChanged = true;
                            }
                            else {
                                // If the file is already in the list, then we need to update its lastModified and size
                                const existingFileIndex = updatedCacheData.files.map(f => f.key).indexOf(localPath);
                                if (existingFileIndex !== -1) {
                                    updatedCacheData.files[existingFileIndex] = {
                                        ...updatedCacheData.files[existingFileIndex],
                                        lastModified: file.lastModified,
                                        size: file.size
                                    };
                                    anyChanged = true;
                                }
                            }
                        }
                    }

                    if (anyChanged) {
                        this._setCachedPath(pathToCheck, updatedCacheData);
                    }
                }
                else {
                    // Even if this isn't loaded yet, we should notify the change listeners that something 
                    // happened at this path, if anyone is listening for it.
                    for (let listener of this.pathChangeListeners.get(pathToCheck) ?? []) {
                        listener({
                            loading: false,
                            promise: null,
                            path: file.key,
                            folders: [],
                            files: [file],
                            recursive: false,
                        });
                    }
                }
            }
        }
    }

    _onReceivedPubSubDelete(path: string) {
        const localPath = path.substring(this.prefix.length);
        // Look for any already loaded PathData objects that contain 
        // this file, which is only the immediate parent, and itself

        const localPathParts: string[] = localPath.split('/');
        // For every level of hierarchy depth, we want to check if that path has already been 
        // loaded (either with a trailing slash or without) and then send appropriate updates.
        for (let i = localPathParts.length; i >= 0; i--) {
            let localSubPath = localPathParts.slice(0, i).join('/');
            if (!this.prefix.endsWith('/')) {
                localSubPath = '/' + localSubPath;
            }
            const fullPath = this.normalizePath(localSubPath);
            for (let slash = 0; slash <= 1; slash++) {
                const pathToCheck = fullPath + (slash == 0 ? '' : '/');

                // 1. Check if this file has already been loaded, and if so update it
                const cachedData: PathData | undefined = this.pathCache.get(pathToCheck);
                if (cachedData) {
                    if (!cachedData.loading) {
                        const files = cachedData.files.filter(f => f.key !== localPath);
                        let folders = cachedData.folders;
                        if (cachedData.recursive) {
                            // If we loaded recursively, we can regenerate the list of folders from 
                            // the files after we delete a file, to ensure that we propagate deletions 
                            // of empty folders.
                            const localPathNoLeadingSlash = localPathParts.slice(0, i).join('/');
                            folders = [...new Set(files.filter((file) => {
                                return file.key.substring(localPathNoLeadingSlash.length).includes('/');
                            }).map((file) => {
                                return file.key.substring(0, file.key.indexOf('/', localPathNoLeadingSlash.length) + 1);
                            }))];
                        }
                        this._setCachedPath(pathToCheck, {
                            ...cachedData,
                            files,
                            folders
                        });

                        // This means that a folder has been completely deleted, so we should check if its parent was _not_
                        // loaded recursively, and if so, we should delete it from the parent's list of folders.
                        if (files.length === 0 && folders.length === 0) {
                            let parentPath = pathToCheck;
                            if (parentPath.endsWith('/')) parentPath = parentPath.substring(0, parentPath.length - 1);
                            parentPath = parentPath.substring(0, parentPath.lastIndexOf('/') + 1);
                            const parentData = this.pathCache.get(parentPath);
                            let folderNameToDelete = pathToCheck.substring(this.prefix.length);
                            if (!folderNameToDelete.endsWith('/')) folderNameToDelete += '/';
                            if (parentData != null && !parentData.recursive) {
                                this._setCachedPath(parentPath, {
                                    ...parentData,
                                    folders: parentData.folders.filter((folder) => {
                                        return folder !== folderNameToDelete;
                                    })
                                });
                            }
                        }
                    }
                }
                else {
                    // Even if this isn't loaded yet, we should notify the change listeners that something 
                    // happened at this path, if anyone is listening for it.
                    for (let listener of this.pathChangeListeners.get(pathToCheck) ?? []) {
                        listener({
                            loading: false,
                            promise: null,
                            path: pathToCheck,
                            folders: [],
                            files: [],
                            recursive: false,
                        });
                    }
                }
            }
        }
    }
    
    getSignedURL(path: string, expiresIn: number): Promise<string>
    {
        return this.s3.getSignedURL(this.normalizePath(path), expiresIn);
    }

    downloadText(path: string): Promise<string>
    {
        return this.s3.downloadText(this.normalizePath(path));
    }

    downloadFile(path: string): void
    {
        this.getSignedURL(path, 3600).then((url) => {
            // Download the file in the browser
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', '');
            document.body.appendChild(link);
            link.click();
            link.remove();
        });
    }

    uploadText(path: string, text: string): Promise<void>
    {
        const fullPath = this.normalizePath(path);
        return this.s3.uploadText(fullPath, text).then(() => {
            const topic = this.pubsub.makeTopicPubSubSafe("/UPDATE/" + fullPath);
            const updatedFile: FileMetadata = {
                key: fullPath,
                lastModified: new Date(),
                size: text.length,
            };
            // We're about to receive this back from PubSub, but we can synchronously update it now
            this._onReceivedPubSubUpdate({... updatedFile});
            // Also send to PubSub
            this.pubsub.publish({ topic, message: JSON.stringify(updatedFile) });
        });
    }

    uploadFile(path: string, contents: File, progressCallback: (percentage: number) => void): Promise<void>
    {
        const fullPath = this.normalizePath(path);
        return this.s3.uploadFile(fullPath, contents, progressCallback).then(() => {
            console.log("Finished uploading file!");
            const topic = this.pubsub.makeTopicPubSubSafe("/UPDATE/" + fullPath);
            const updatedFile: FileMetadata = {
                key: fullPath,
                lastModified: new Date(),
                size: contents.size,
            };
            // We're about to receive this back from PubSub, but we can synchronously update it now
            this._onReceivedPubSubUpdate(updatedFile);
            // Also send to PubSub
            this.pubsub.publish({ topic, message: JSON.stringify(updatedFile) });
        });
    }

    delete(path: string): Promise<void>
    {
        const fullPath = this.normalizePath(path);
        return this.s3.delete(fullPath).then(() => {
            const topic = this.pubsub.makeTopicPubSubSafe("/DELETE/" + fullPath);
            const updatedFile: FileMetadata = {
                key: fullPath,
                lastModified: new Date(),
                size: 0
            };
            // We're about to receive this back from PubSub, but we can synchronously update it now
            this._onReceivedPubSubDelete(fullPath);
            // Also send to PubSub
            this.pubsub.publish({ topic, message: JSON.stringify(updatedFile) });
        });
    }

    async deleteByPrefix(path: string): Promise<void>
    {
        let data = this.getPath(path, true);
        if (data.promise != null) {
            data = await data.promise;
        }
        const files = data.files;
        return Promise.all(files.map((file) => {
            return this.delete(file.key);
        })) as any as Promise<void>;
    }
};

export type { PathData };
export { LiveDirectoryImpl, LiveDirectory };
export default LiveDirectory;