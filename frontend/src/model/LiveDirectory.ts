import { PubSubSocket } from "./PubSubSocket";
import { FileMetadata, S3API } from "./S3API"; 
import { makeObservable, action, observable } from 'mobx';
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

    abstract getPath(path: string, recursive: boolean): PathData;
    abstract getCachedPath(path: string): PathData | undefined;
    abstract addPathChangeListener(path: string, listener: (newData: PathData) => void): void;

    abstract getSignedURL(path: string, expiresIn: number): Promise<string>;
    abstract downloadText(path: string): Promise<string>;
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
    pathCache: Map<string, PathData>;
    pathChangeListeners: Map<string, ((newData: PathData) => void)[]>;

    constructor(prefix: string, s3: S3API, pubsub: PubSubSocket) {
        super(prefix);
        this.s3 = s3;
        this.pubsub = pubsub;
        this.pathCache = new Map<string, PathData>();
        this.pathChangeListeners = new Map<string, ((newData: PathData) => void)[]>();

        this.getPath = this.getPath.bind(this);
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

    getPath(originalPath: string, recursive: boolean = false): PathData {
        let prefix = this.prefix;
        if (!prefix.endsWith('/')) {
            prefix += '/';
        }
        const path = this.normalizePath(originalPath);

        // Now we want to check if this path is a folder or not. If it is a folder, we always want to 
        // append the "/" so that we load its children. If it's not a folder, then we never want to 
        // append a "/".

        const cached: PathData | undefined = this.pathCache.get(path);
        // Check if we've already loaded this path
        if (this.pathCache.has(path) && cached != null) {
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
                const result: PathData = {
                    loading: false,
                    promise: null,
                    path,
                    folders: folders.map((folder) => {
                        return folder.substring(prefix.length).replace(/^\//, '');
                    }),
                    files: files.map((file) => {
                        return {
                            // Trim the prefix, and leading slashes
                            key: file.key.substring(prefix.length).replace(/^\//, ''),
                            lastModified: file.lastModified,
                            size: file.size,
                        };
                    }),
                    recursive: recursive,
                };
                this._setCachedPath(path, result);
                return result;
            }
        }));
        // Create a stub that is loading, and leave a non-null promise in it that will resolve when the load completes
        const stub: PathData = {
            loading: true,
            promise: promise,
            path,
            folders: cached?.folders ?? [],
            files: cached?.files ?? [],
            recursive: recursive,
        };
        this._setCachedPath(path, stub);
        // In the mean time, return the stub saying that we're loading the data
        return stub;
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

    getCachedPath(path: string): PathData | undefined {
        return this.pathCache.get(this.normalizePath(path));
    }

    addPathChangeListener(path: string, listener: (newData: PathData) => void): void
    {
        path = this.normalizePath(path);
        this.pathChangeListeners.set(path, [...(this.pathChangeListeners.get(path) ?? []), listener]);
    }

    _setCachedPath(path: string, data: PathData) {
        this.pathCache.set(path, data);
        for (let listener of this.pathChangeListeners.get(path) ?? []) {
            listener(data);
        }
    }

    _onReceivedPubSubUpdate(file: FileMetadata) {
        // Look for any already loaded PathData objects that contain 
        // this file, which is only the immediate parent, and itself
        const localPath = file.key.substring(this.prefix.length);

        // 1. Check if this file has already been loaded, and if so update it
        const selfData: PathData | undefined = this.pathCache.get(file.key);
        if (selfData) {
            if (!selfData.loading) {
                if (!selfData.files.map(f => f.key).includes(localPath)) {
                    selfData.files.push(file);
                    this._setCachedPath(file.key, selfData);
                }
                else {
                    // If the file is already in the list, then we need to update its lastModified and size
                    const existingFile = selfData.files.find(f => f.key === localPath);
                    if (existingFile) {
                        existingFile.lastModified = file.lastModified;
                        existingFile.size = file.size;
                        this._setCachedPath(file.key, selfData);
                    }
                }
            }
        }
        else {
            // Even if this isn't loaded yet, we should notify the change listeners that something 
            // happened at this path, if anyone is listening for it.
            for (let listener of this.pathChangeListeners.get(file.key) ?? []) {
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

        // 2. Check if the parent has already been loaded
        const parentPath: string = file.key.substring(0, file.key.lastIndexOf('/')) + "/";
        const parentData: PathData | undefined = this.pathCache.get(parentPath);
        if (parentData) {
            if (!parentData.loading) {
                if (!parentData.files.map(f => f.key).includes(file.key)) {
                    parentData.files.push({
                        key: localPath,
                        lastModified: file.lastModified,
                        size: file.size,
                    });
                    this._setCachedPath(parentPath, parentData);
                }
            }
        }
    }

    _onReceivedPubSubDelete(path: string) {
        const localPath = path.substring(this.prefix.length);
        // Look for any already loaded PathData objects that contain 
        // this file, which is only the immediate parent, and itself

        // 1. Check if this file has already been loaded, and if so update it
        const selfData: PathData | undefined = this.pathCache.get(path);
        if (selfData) {
            if (!selfData.loading) {
                selfData.files = selfData.files.filter(f => f.key !== localPath);
                this._setCachedPath(path, selfData);
            }
        }
        else {
            // Even if this isn't loaded yet, we should notify the change listeners that something 
            // happened at this path, if anyone is listening for it.
            for (let listener of this.pathChangeListeners.get(path) ?? []) {
                listener({
                    loading: false,
                    promise: null,
                    path: path,
                    folders: [],
                    files: [],
                    recursive: false,
                });
            }
        }

        // 2. Check if the parent has already been loaded
        const parentPath: string = path.substring(0, path.lastIndexOf('/')) + "/";
        const parentData: PathData | undefined = this.pathCache.get(parentPath);
        if (parentData) {
            if (!parentData.loading) {
                parentData.files = parentData.files.filter(f => f.key !== localPath);
                this._setCachedPath(parentPath, parentData);
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
            this.pubsub.publish({ topic, message: JSON.stringify(updatedFile) });
        });
    }

    deleteByPrefix(path: string): Promise<void>
    {
        throw new Error("Not implemented yet.");
        
        return this.s3.deleteByPrefix(this.normalizePath(path));
    }
};

export type { PathData };
export { LiveDirectoryImpl, LiveDirectory };
export default LiveDirectory;