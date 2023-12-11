import { PubSubSocket } from "./PubSubSocket";
import { FileMetadata, S3API } from "./S3API"; 
import { makeObservable, action, observable, ObservableMap } from 'mobx';
import LiveJsonFile from "./LiveJsonFile";
import LiveFile from "./LiveFile";

type PathData = {
    loading: boolean;
    promise: Promise<PathData> | null;
    path: string;
    folders: string[];
    files: FileMetadata[];
    children: Map<string, PathData>;
    recursive: boolean;
    readonly?: boolean;
};

type FaultIn = {
    abortController: AbortController;
    firstLoadPromise: Promise<PathData>;
    promise: Promise<void>;
    finished: boolean;
};

abstract class LiveDirectory {
    prefix: string;
    jsonFiles: Map<string, LiveJsonFile>;
    liveFiles: Map<string, LiveFile>;

    constructor(prefix: string) {
        this.prefix = prefix;
        this.jsonFiles = new Map();
        this.liveFiles = new Map();
        this.getJsonFile = this.getJsonFile.bind(this);
    }

    abstract faultInPath(path: string): FaultIn;
    abstract getPath(path: string, recursive: boolean): PathData;
    abstract getCachedPath(path: string, doNotSaveIfNotExists?: boolean): PathData | undefined;
    abstract addPathChangeListener(path: string, listener: (newData: PathData) => void): void;
    abstract addChangeListener(listener: (updatedPaths: string[]) => void): void;

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
    getLiveFile(path: string, skipImmediateRefreshOnCreate: boolean = false): LiveFile {
        let file = this.liveFiles.get(path);
        if (file == null) {
            file = new LiveFile(this, path, skipImmediateRefreshOnCreate);
            this.liveFiles.set(path, file);
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
    changeListeners: ((updatedPaths: string[]) => void)[];
    faultingIn: Map<string, FaultIn>;

    constructor(prefix: string, s3: S3API, pubsub: PubSubSocket) {
        super(prefix);
        this.s3 = s3;
        this.pubsub = pubsub;
        this.pathCache = observable.map(new Map<string, PathData>(), {
            deep: false
        });
        this.pathChangeListeners = new Map<string, ((newData: PathData) => void)[]>();
        this.changeListeners = [];
        this.faultingIn = new Map();

        this.getPath = this.getPath.bind(this);
        this.faultInPath = this.faultInPath.bind(this);
        this.getCachedPath = this.getCachedPath.bind(this);
        this._setCachedPath = this._setCachedPath.bind(this);
        this._onReceivedPubSubUpdate = this._onReceivedPubSubUpdate.bind(this);
        this._onReceivedPubSubDelete = this._onReceivedPubSubDelete.bind(this);
        this.addPathChangeListener = this.addPathChangeListener.bind(this);
        this.addChangeListener = this.addChangeListener.bind(this);

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
    faultInPath(originalPath: string, abortController?: AbortController): FaultIn {
        const faultIn: FaultIn | undefined = this.faultingIn.get(originalPath);
        if (faultIn == null) {
            let removeKeys: string[] = [];
            this.faultingIn.forEach((faultIn, path) => {
                if (!faultIn.finished && path !== originalPath) {
                    faultIn.abortController.abort();
                    removeKeys.push(path);
                }
            });
            removeKeys.forEach((key) => {
                this.faultingIn.delete(key);
            });

            if (abortController == null) {
                abortController = new AbortController();
            }
            const rootPathData: PathData = this.getPath(originalPath, false, abortController);

            let promise = new Promise<void>((resolve, reject) => {
                const loadRecursive = async (folderData: PathData) => {
                    try {
                        const folderPathDatas: PathData[] = [];
                        // Load each child recursively
                        for (let folder of folderData.folders) {
                            if (abortController?.signal.aborted) {
                                reject("Aborted");
                                return;
                            }
                            const folderPathData = this.getPath(folder, true, abortController);
                            if (folderPathData.promise != null) {
                                folderPathDatas.push(await folderPathData.promise);
                            }
                            else {
                                folderPathDatas.push(folderPathData);
                            }
                        }
                        // Finally, convert the root node to be a recursive node, and include all 
                        // the files we've loaded from the children
                        let rootPathDataOrNull: PathData | undefined = this.getCachedPath(originalPath);
                        if (rootPathDataOrNull == null) {
                            reject("Root path data was null, this should never happen.");
                            return;
                        }
                        let rootPathData: PathData = {...rootPathDataOrNull};
                        if (!rootPathData.recursive) {
                            rootPathData.recursive = true;
                            for (let folderPathData of folderPathDatas) {
                                let childName = folderPathData.path.substring(originalPath.length);
                                rootPathData.children.set(childName, folderPathData);
                            }
                            const normalizedPath = this.normalizePath(originalPath);
                            this._setCachedPath(normalizedPath, rootPathData);
                        }
                        resolve();
                    }
                    catch (e) {
                        reject(e);
                    }
                }

                // If the path is already loaded recursively, then we're done
                if (!rootPathData.loading && rootPathData.recursive) {
                    resolve();
                }
                else if (!rootPathData.loading) {
                    loadRecursive(rootPathData);
                }
                else if (rootPathData.promise != null) {
                    rootPathData.promise.then((loadedPathData) => {
                        loadRecursive(loadedPathData);
                    });
                }
                else {
                    // load recursively anyways, to attempt to recover smoothly from the error
                    loadRecursive(rootPathData);
                }
            });

            const faultIn = {
                abortController,
                firstLoadPromise: rootPathData.promise ?? Promise.resolve(rootPathData),
                promise,
                finished: false
            };
            faultIn.promise = promise.then(() => {
                faultIn.finished = true;
                this.faultingIn.set(originalPath, faultIn);
            }).catch((e) => {
                throw e;
            });
            this.faultingIn.set(originalPath, faultIn);

            return faultIn;
        }
        return faultIn;
    }

    getPath(originalPath: string, recursive: boolean = false, abortController?: AbortController): PathData {
        if (originalPath.startsWith('/')) {
            originalPath = originalPath.substring(1);
        }
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
        const onLoadedData = (folders: string[], files: FileMetadata[]) => {
            let result: PathData = {
                loading: false,
                promise: null,
                path: originalPath,
                folders: [],
                files: [],
                children: new Map(),
                recursive: recursive,
            };
            files = files.map((file) => {
                    return {
                        // Trim the prefix, and leading slashes
                        key: file.key.substring(prefix.length).replace(/^\//, ''),
                        lastModified: file.lastModified,
                        size: file.size,
                    };
                });
            if (!recursive) {
                // Remove the prefix from the folder paths
                result.files = files;
                result.folders = folders.map((folder) => {
                    return folder.substring(prefix.length).replace(/^\//, '');
                });
            }
            // else {
            //     const originalPathWithSlash = originalPath + (originalPath.endsWith('/') ? '' : '/');
            //     folders = [...new Set(files.filter((file) => {
            //         return file.key.substring(originalPathWithSlash.length).includes('/');
            //     }).map((file) => {
            //         return file.key.substring(0, file.key.indexOf('/', originalPathWithSlash.length) + 1);
            //     }))];
            // }
            // If we loaded recursively, we need to fill in the child PathData entries
            if (recursive) {
                const originalPathWithSlash = originalPath + (originalPath.endsWith('/') ? '' : '/');
                for (let i = 0; i < files.length; i++) {
                    const pathParts = files[i].key.substring(originalPath.length > 0 ? originalPathWithSlash.length : 0).split('/');

                    // Traverse the path, creating any missing PathData entries
                    let cursor: PathData = result;
                    for (let j = 0; j < pathParts.length - 1; j++) {
                        let child: PathData | undefined = cursor.children.get(pathParts[j]);
                        if (child == null) {
                            let childPath = originalPathWithSlash + pathParts.slice(0, j + 1).join('/') + '/';
                            child = {
                                loading: false,
                                promise: null,
                                path: childPath,
                                folders: [],
                                files: [],
                                children: new Map(),
                                recursive: true,
                            };
                            cursor.children.set(pathParts[j], child);
                            cursor.folders.push(childPath);
                        }
                        cursor = child;
                    }

                    // Now we have a cursor at the right place, we can add the file
                    cursor.files.push(files[i]);
                }

                // const recursivelyPrint = (pathData: PathData, indent: string) => {
                //     console.log(indent + pathData.path + " (" + pathData.files.length + " files, " + pathData.folders.length + " folders)");
                //     for (let child of pathData.children.values()) {
                //         recursivelyPrint(child, indent + "  ");
                //     }
                // };
                // recursivelyPrint(result, "");
            }

            this._setCachedPath(path, result);
            return result;
        };

        let firstLoadPath = path;
        // If we're loading recursively, and we're loading the root, then we know this is a folder and can skip the first load without the slash for efficiency
        if (originalPath == '' && !recursive) {
            firstLoadPath = path + '/';
        }
        const promise: Promise<PathData> = this.s3.loadPathData(firstLoadPath, recursive, abortController).then(action(({folders, files}) => {
            // This is a folder, we have to issue another load to get the children
            if (firstLoadPath == path && !recursive && folders.length == 1 && folders[0] == path + '/') {
                return this.s3.loadPathData(path + '/', false, abortController).then(action(({folders, files}) => {
                    return onLoadedData(folders, files);
                }));
            }
            else {
                return onLoadedData(folders, files);
            }
        })).catch(action((e) => {
            // If the load fails, we want to remove the cached path, so that we can try again later
            this.pathCache.delete(path);
            throw e;
        }));
        if (cached == null) {
            // Create a stub that is loading, and leave a non-null promise in it that will resolve when the load completes
            const stub: PathData = {
                loading: true,
                promise: promise,
                path: originalPath,
                folders: [],
                files: [],
                children: new Map(),
                recursive: recursive,
            };
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
        path = prefix + path;
        if (path.endsWith('/')) {
            path = path.substring(0, path.length - 1);
        }
        return path;
    }

    unnormalizePath(path: string): string {
        let prefix = this.prefix;
        if (!prefix.endsWith('/')) {
            prefix += '/';
        }
        if (path.startsWith(prefix)) {
            path = path.substring(prefix.length);
            return path;
        }
        else {
            return "";
        }
    }

    getCachedPath(originalPath: string, doNotSaveIfNotExists?: boolean): PathData | undefined {
        if (originalPath.startsWith('/')) {
            originalPath = originalPath.substring(1);
        }
        if (originalPath.endsWith('/')) {
            originalPath = originalPath.substring(0, originalPath.length - 1);
        }
        const normalizedPath = this.normalizePath(originalPath);

        const cached = this.pathCache.get(normalizedPath);
        if (cached != null) {
            return cached;
        }

        // Check if we've loaded any parent path recursively, in which case we can infer the contents of this path
        // without having to load it.
        const pathParts = originalPath.split('/');
        if (pathParts[-1] === '') {
            pathParts.pop();
        }
        for (let i = pathParts.length - 1; i >= 0; i--) {
            const parentPath = pathParts.slice(0, i).join('/');
            const normalizedParentPath = this.normalizePath(parentPath);
            const cachedParentPath: PathData | undefined = this.pathCache.get(normalizedParentPath);
            if (cachedParentPath != null && cachedParentPath.recursive) {
                const remainingPathParts = pathParts.slice(i);
                let cursor = cachedParentPath;
                for (let j = 0; j < remainingPathParts.length; j++) {
                    const child = cursor.children.get(remainingPathParts[j]);
                    if (child == null) {
                        if (j === remainingPathParts.length - 1) {
                            const fileMatch = cursor.files.filter((file) => {
                                return file.key.endsWith(remainingPathParts[j]);
                            });
                            if (fileMatch.length === 1) {
                                return {
                                    loading: false,
                                    promise: null,
                                    path: normalizedPath,
                                    folders: [],
                                    files: fileMatch,
                                    children: new Map(),
                                    recursive: false,
                                };
                            }
                        }
                        return undefined;
                    }
                    cursor = child;
                }
                return cursor;
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

    addChangeListener(listener: (updatedPaths: string[]) => void): void
    {
        this.changeListeners.push(listener);
    }

    _setCachedPath(normalizedPath: string, data: PathData, skipListeners?: boolean): void {
        this.pathCache.set(normalizedPath, data);
        for (let listener of this.pathChangeListeners.get(normalizedPath) ?? []) {
            listener(data);
        }

        if (!skipListeners) {
            const unnormalizePath = this.unnormalizePath(normalizedPath);
            this.changeListeners.forEach((listener) => {
                listener([unnormalizePath]);
            });
        }
    }

    _onReceivedPubSubUpdate(file: FileMetadata): Promise<void> {
        if (!file.key.startsWith(this.prefix)) {
            return Promise.resolve();
        }

        // Look for any already loaded PathData objects that contain 
        // this file, which is only the immediate parent, and itself
        const localPath = file.key.substring(this.prefix.length);
        file.key = localPath;

        const localPathParts: string[] = localPath.split('/');
        let promises: Promise<void>[] = [];
        // For every level of hierarchy depth, we want to check if that path has already been 
        // loaded (always without the trailing slash) and then send appropriate updates.
        for (let i = localPathParts.length; i >= 0; i--) {
            let localSubPath = localPathParts.slice(0, i).join('/');
            if (!this.prefix.endsWith('/') && i > 0) {
                localSubPath = '/' + localSubPath;
            }
            let pathToCheck = this.prefix + localSubPath;
            if (pathToCheck.endsWith('/')) {
                pathToCheck = pathToCheck.substring(0, pathToCheck.length - 1);
            }
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
                        const remainingPathParts = localPath.substring(updatedCacheData.path.length).split('/');
                        let cursor = updatedCacheData;
                        for (let j = 0; j < remainingPathParts.length - 1; j++) {
                            let child = cursor.children.get(remainingPathParts[j]);
                            if (child == null) {
                                let childPath = updatedCacheData.path + remainingPathParts.slice(0, j + 1).join('/') + '/';
                                child = {
                                    loading: false,
                                    promise: null,
                                    path: childPath,
                                    folders: [],
                                    files: [],
                                    children: new Map(),
                                    recursive: true,
                                };
                                cursor.children.set(remainingPathParts[j], child);
                                if (!cursor.folders.includes(childPath)) {
                                    cursor.folders.push(childPath);
                                }
                                anyChanged = true;
                            }
                            cursor = child;
                        }

                        if (!cursor.files.map(f => f.key).includes(localPath)) {
                            cursor.files.push(file);
                            anyChanged = true;
                        }
                        else {
                            // If the file is already in the list, then we need to update its lastModified and size
                            const existingFileIndex = cursor.files.map(f => f.key).indexOf(localPath);
                            if (existingFileIndex !== -1) {
                                cursor.files[existingFileIndex] = {
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

                // In the other branch, these get called as part of this._setCachedPath
                for (let listener of this.pathChangeListeners.get(pathToCheck) ?? []) {
                    listener({
                        loading: false,
                        promise: null,
                        path: file.key,
                        folders: [],
                        files: [file],
                        children: new Map(),
                        recursive: false,
                    });
                }
            }
        }
        if (promises.length > 0) {
            return Promise.all(promises).then(() => {});
        }
        return Promise.resolve();
    }

    _onReceivedPubSubDelete(path: string): Promise<void> {
        if (!path.startsWith(this.prefix)) {
            return Promise.resolve();
        }

        const localPath = path.substring(this.prefix.length);
        // Look for any already loaded PathData objects that contain 
        // this file, which is only the immediate parent, and itself

        const localPathParts: string[] = localPath.split('/');
        let promises: Promise<void>[] = [];
        // For every level of hierarchy depth, we want to check if that path has already been 
        // loaded (either with a trailing slash or without) and then send appropriate updates.
        for (let i = localPathParts.length; i >= 0; i--) {
            let localSubPath = localPathParts.slice(0, i).join('/');
            if (!this.prefix.endsWith('/')) {
                localSubPath = '/' + localSubPath;
            }
            const pathToCheck = this.normalizePath(localSubPath);

            // 1. Check if this file has already been loaded, and if so update it
            const cachedData: PathData | undefined = this.pathCache.get(pathToCheck);
            if (cachedData) {
                if (!cachedData.loading) {
                    if (cachedData.recursive) {
                        // console.log("Deleting file " + localPath + " from " + cachedData.path + " recursively");
                        // If we loaded recursively, we can regenerate the list of folders from 
                        // the files after we delete a file, to ensure that we propagate deletions 
                        // of empty folders.
                        const remainingPathParts = localPath.substring(cachedData.path.length).split('/');
                        if (remainingPathParts[0] === '') remainingPathParts.shift();
                        let cursor = cachedData;
                        let foldersToDelete: string[] = [];
                        for (let j = 0; j < remainingPathParts.length; j++) {
                            const newFiles = cursor.files.filter((file) => {
                                return file.key !== localPath;
                            });
                            if (cursor.files.length > 0 && newFiles.length === 0) {
                                foldersToDelete.push(cursor.path);
                                break;
                            }
                            else {
                                cursor.files = newFiles;
                                let child = cursor.children.get(remainingPathParts[j]);
                                if (child == null) {
                                    break;
                                }
                                cursor = child;
                            }
                        }
                        if (cursor != null) {
                            cursor.files = cursor.files.filter((file) => {
                                return file.key !== localPath;
                            });
                        }

                        // Go through and delete any empty folders
                        while (foldersToDelete.length > 0) {
                            const folderToDelete = foldersToDelete.pop();
                            if (folderToDelete != null) {
                                let folderName = folderToDelete.substring(cachedData.path.length);
                                if (folderName.endsWith('/')) folderName = folderName.substring(0, folderName.length - 1);
                                const folderPathParts = folderName.split('/');
                                if (folderPathParts[0] === '') folderPathParts.shift();

                                let cursor: PathData | undefined = cachedData;
                                // console.log(folderPathParts);
                                for (let j = 0; j < folderPathParts.length - 1; j++) {
                                    let child: PathData | undefined = cursor!.children.get(folderPathParts[j]);
                                    if (child == null) {
                                        // console.log("Couldn't find folder " + folderPathParts[j] + " in " + cursor.path);
                                        cursor = undefined;
                                        break;
                                    }
                                    cursor = child;
                                }
                                if (cursor != null) {
                                    // console.log("Deleting folder " + folderToDelete + " from " + cursor.path);
                                    cursor.children.delete(folderPathParts[folderPathParts.length - 1]);
                                    cursor.folders = cursor.folders.filter((folder) => {
                                        return folder !== folderToDelete;
                                    });
                                    if (cursor.files.length === 0 && cursor.folders.length === 0) {
                                        // console.log("Now empty, deleting folder " + cursor.path);
                                        if (cursor.path !== folderToDelete) {
                                            foldersToDelete.push(cursor.path);
                                        }
                                    }
                                    else {
                                        // console.log("Not empty, not deleting folder " + cursor.path + " (" + cursor.files.map(f => f.key) + " files, " + cursor.folders.length + " folders)");
                                    }
                                }
                            }
                        }

                        // const localPathNoLeadingSlash = localPathParts.slice(0, i).join('/');
                        // folders = [...new Set(files.filter((file) => {
                        //     return file.key.substring(localPathNoLeadingSlash.length).includes('/');
                        // }).map((file) => {
                        //     return file.key.substring(0, file.key.indexOf('/', localPathNoLeadingSlash.length + 1));
                        // }).filter((folder) => folder.length > 0 ))];
                    }
                    else {
                        cachedData.files = cachedData.files.filter((file) => {
                            return file.key !== localPath;
                        });
                    }
                    const updatedData = {
                        ...cachedData
                    };
                    this._setCachedPath(pathToCheck, updatedData);

                    // This means that a folder has been completely deleted, so we should check if its parent was _not_
                    // loaded recursively, and if so, we should delete it from the parent's list of folders.
                    if (updatedData.files.length === 0 && updatedData.folders.length === 0) {
                        let parentPath = pathToCheck;
                        if (parentPath.endsWith('/')) parentPath = parentPath.substring(0, parentPath.length - 1);
                        parentPath = parentPath.substring(0, parentPath.lastIndexOf('/') + 1);
                        if (parentPath.endsWith('/')) parentPath = parentPath.substring(0, parentPath.length - 1);
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

                // In the other branch, these get called as part of this._setCachedPath
                for (let listener of this.pathChangeListeners.get(pathToCheck) ?? []) {
                    listener({
                        loading: false,
                        promise: null,
                        path: pathToCheck,
                        folders: [],
                        files: [],
                        children: new Map(),
                        recursive: false,
                    });
                }
            }
        }
        if (promises.length > 0) {
            return Promise.all(promises).then(() => {});
        }
        return Promise.resolve();
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
            const promise = this._onReceivedPubSubUpdate({... updatedFile});
            // Also send to PubSub
            this.pubsub.publish({ topic, message: JSON.stringify(updatedFile) });
            // Allow the caller to wait for the PubSub update and all file change listeners to be notified
            return promise;
        });
    }

    uploadFile(path: string, contents: File, progressCallback: (percentage: number) => void): Promise<void>
    {
        const fullPath = this.normalizePath(path);
        return this.s3.uploadFile(fullPath, contents, progressCallback).then(() => {
            const topic = this.pubsub.makeTopicPubSubSafe("/UPDATE/" + fullPath);
            const updatedFile: FileMetadata = {
                key: fullPath,
                lastModified: new Date(),
                size: contents.size,
            };
            // Allow the caller to wait for the PubSub update and all file change listeners to be notified
            return Promise.all([
                // We're about to receive this back from PubSub, but we can synchronously update it now
                this._onReceivedPubSubUpdate({... updatedFile}),
                // Also send to PubSub
                this.pubsub.publish({ topic, message: JSON.stringify(updatedFile) })
            ]).then(() => {});
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
            // Allow the caller to wait for the PubSub update and all file change listeners to be notified
            return Promise.all([
                // We're about to receive this back from PubSub, but we can synchronously update it now
                this._onReceivedPubSubDelete(fullPath),
                // Also send to PubSub
                this.pubsub.publish({ topic, message: JSON.stringify(updatedFile) })
            ]).then(() => {});
        });
    }

    recursivelyGetAllCachedFiles(path: string): FileMetadata[] {
        if (path.endsWith('/')) {
            path = path.substring(0, path.length - 1);
        }
        if (path.startsWith('/')) {
            path = path.substring(1);
        }
        let files: FileMetadata[] = [];
        const cachedData = this.getCachedPath(path);
        if (cachedData != null) {
            files = [...cachedData.files];
            for (let child of cachedData.children.values()) {
                files = files.concat(this.recursivelyGetAllCachedFiles(child.path));
            }
        }
        return files;
    }


    async deleteByPrefix(path: string): Promise<void>
    {
        if (path.endsWith('/')) {
            path = path.substring(0, path.length - 1);
        }
        if (path.startsWith('/')) {
            path = path.substring(1);
        }
        let data = this.getPath(path, true);
        if (data.promise != null) {
            data = await data.promise;
        }
        const files = this.recursivelyGetAllCachedFiles(path);
        // console.log("Deleting " + files.length + " files: ", files);
        return Promise.all(files.map((file) => {
            return this.delete(file.key);
        })) as any as Promise<void>;
    }
};

export type { PathData, FaultIn };
export { LiveDirectoryImpl, LiveDirectory };
export default LiveDirectory;