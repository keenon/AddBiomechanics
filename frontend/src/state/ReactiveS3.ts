import { makeObservable, action, observable } from 'mobx';
import { Auth, Storage } from "aws-amplify";
import {
    S3ProviderListOutput,
    S3ProviderListOutputItem,
} from "@aws-amplify/storage";
import JSZip from 'jszip';
import RobustMqtt from './RobustMqtt';
import { Credentials, getAmplifyUserAgent } from '@aws-amplify/core';
import { S3Client, ListObjectsV2Command, ListObjectsV2CommandOutput } from '@aws-sdk/client-s3';
import RobustUpload from './RobustUpload';


/**
 * This strips any illegal characters from a PubSub path (or subset of a path), and returns what's left
 * 
 * @param path The raw input path we'd like to make safe for PubSub
 * @returns a legal PubSub path (or subset of a legal path)
 */
function makeTopicPubSubSafe(path: string) {
    const MAX_TOPIC_LEN = 80;
    if (path.length > MAX_TOPIC_LEN) {
        let segments = path.split("/");
        if (segments[0].length > MAX_TOPIC_LEN) {
            return segments[0].substring(0, MAX_TOPIC_LEN);
        }
        let reconstructed = '';
        let segmentCursor = 0;
        while (segmentCursor < segments.length) {
            let proposedNext = reconstructed;
            if (segmentCursor > 0) {
                proposedNext += '/';
            }
            proposedNext += segments[segmentCursor];
            segmentCursor++;

            if (proposedNext.length < MAX_TOPIC_LEN) {
                reconstructed = proposedNext;
            }
            else {
                break;
            }
        }
        return reconstructed;
    }
    return path;
}

function ensurePathEndsWithSlash(path: string): string {
    if (path.endsWith("/") || path.length === 0) return path;
    else return path + "/";
}

/// This is a cacheing layer for mobx-style interaction with JSON files stored in S3. This handles doing the downloading, parsing, 
/// and re-uploading in the background.
class ReactiveJsonFile {
    cursor: ReactiveCursor;
    loading: boolean;
    path: string;
    values: Map<string, any>;
    focused: Map<string, boolean>;
    lastUploadedValues: Map<string, any>;
    pendingTimeout: any | null;
    changeListeners: Array<() => void>;

    constructor(cursor: ReactiveCursor, path: string) {
        this.cursor = cursor;
        this.path = path;
        this.values = new Map();
        this.focused = new Map();
        this.lastUploadedValues = new Map();
        this.pendingTimeout = null;
        this.changeListeners = [];
        this.loading = false;
        this.pathChanged();

        this.cursor.index.addLoadingListener((loading: boolean) => {
            if (!loading) {
                this.pathChanged();
            }
        });

        makeObservable(this, {
            loading: observable,
            values: observable,
            path: observable,
            getAttribute: observable
        });
    }

    /**
     * This fires when a value has changed and we've re-uploaded to S3
     */
    addChangeListener = (listener: () => {}) => {
        this.changeListeners.push(listener);
    };

    /**
     * This will do a refresh of the contents of the file from S3
     */
    refreshFile = () => {
        console.log("File exists: " + this.fileExist());
        if (this.fileExist()) {
            this.loading = true;
            this.cursor.downloadText(this.path).then(action((text: string) => {
                console.log("Downloaded text: " + text);
                try {
                    let savedValues: Map<string, any> = new Map();
                    this.focused.forEach((v, k) => {
                        if (v) {
                            savedValues.set(k, this.values.get(k));
                        }
                    });

                    this.values = savedValues;
                    this.lastUploadedValues.clear();
                    const result = JSON.parse(text);
                    for (let key in result) {
                        if (this.focused.get(key) === true) {
                            // Skip updating this entry
                        }
                        else {
                            this.values.set(key, result[key]);
                            this.lastUploadedValues.set(key, result[key]);
                        }
                    }
                }
                catch (e) {
                    console.error("Bad JSON format for file \"" + this.path + "\", got: \"" + text + "\"");
                    this.values.clear();
                }
            })).finally(action(() => {
                this.loading = false;
            }));
        }
        else {
            this.values.clear();
        }
    };

    /**
     * @returns True if we're loading the file AND have no contents cached. False otherwise.
     */
    isLoadingFirstTime = () => {
        return this.loading && this.values.size === 0;
    }

    /**
     * When the file changes on S3
     */
    onFileChanged = () => {
        console.log("Detected file change!");
        this.refreshFile();
    };

    /**
     * @returns the absolute path of the file, relative to the cursor path
     */
    getAbsolutePath = () => {
        let prefix = this.cursor.path;
        if (!prefix.endsWith('/')) prefix += '/';
        return prefix + this.path;
    };

    /**
     * This gets called right before the path changes, and leaves a chance to clean up values
     */
    pathWillChange = () => {
        this.cursor.index.removeMetadataListener(this.getAbsolutePath(), this.onFileChanged);
    };

    /**
     * This gets called when the path has changed in the supporting cursor
     */
    pathChanged = () => {
        console.log('Adding listener to: '+ this.getAbsolutePath() );
        this.cursor.index.addMetadataListener(this.getAbsolutePath(), this.onFileChanged);
        this.refreshFile();
    };

    /**
     * @returns True if the file currently exists, false otherwise
     */
    fileExist = () => {
        return this.cursor.getExists(this.path);
    };

    /**
     * When we have an input entry that we focus on, we don't want to auto-update that from the network, cause it feels like a bug.
     */
    onFocusAttribute = (key: string) => {
        this.focused.set(key, true);
    }

    /**
     * When we have an input entry that we stop focusing on, we want to resume auto-updating that from the network.
     */
    onBlurAttribute = (key: string) => {
        this.focused.set(key, false);
    }

    /**
     * @param key The key we want to retrieve
     * @param defaultValue A default value to return, if the value hasn't loaded yet or the file doesn't exist
     * @returns 
     */
    getAttribute = (key: string, defaultValue: any) => {
        let value = this.values.get(key);
        if (value == null) return defaultValue;
        else return value;
    };

    /**
     * This uploads the contents of this file to S3
     * 
     * @returns A promise for when the upload is complete
     */
    uploadNow = () => {
        clearTimeout(this.pendingTimeout);
        let object: any = {};
        this.values.forEach((v, k) => {
            object[k] = v;
        });
        let json = JSON.stringify(object);
        console.log("Uploading object");
        return this.cursor.uploadChild(this.path, json).then(action(() => {
            console.log("Uploaded successfully");
            // Update the lastUploadedValues, which we'll reset to if we 
            this.lastUploadedValues.clear();
            this.values.forEach((v, k) => {
                this.lastUploadedValues.set(k, v);
            });
            // Call all the change listeners
            this.changeListeners.forEach((listener) => listener());
        })).catch(action((e) => {
            console.error("Caught error uploading JSON, reverting to last uploaded values", e);

            this.values.clear();
            this.lastUploadedValues.forEach((v, k) => {
                this.values.set(k, v);
            });
            // Call all the change listeners
            this.changeListeners.forEach((listener) => listener());

            throw e;
        }));
    };

    /**
     * This sets the value, overwriting the old value, and uploads the resulting JSON to S3 (after a short timeout, to avoid spamming with uploads if you're typing).
     * 
     * @param key 
     * @param value 
     */
    setAttribute = (key: string, value: any, uploadImmediate?: boolean) => {
        this.values.set(key, value);
        if (uploadImmediate) {
            this.uploadNow();
        }
        else {
            this.restartUploadTimer();
        }
    };

    /**
     * When called, this starts a timer to upload in a few hundred milliseconds.
     * If it's called while another time is present, that timer is cleared before this one fires.
     */
    restartUploadTimer = () => {
        if (this.pendingTimeout != null) {
            clearTimeout(this.pendingTimeout);
            this.pendingTimeout = null;
        }
        this.pendingTimeout = setTimeout(() => {
            this.uploadNow();
            this.pendingTimeout = null;
        }, 500);
    };
}

/// This is a convenience wrapper for mobx-style interaction with ReactiveS3. It's reusable, to avoid memory leaks.
/// Ideally, users of this class create a single one, and re-use it as the GUI traverses over different paths and indexes,
/// by calling setPath() and setIndex(). This should handle cleaning up stray listeners as it traverses, which prevents leaks.
class ReactiveCursor {
    index: ReactiveIndex;
    path: string;
    metadata: ReactiveFileMetadata | null;
    children: Map<string, ReactiveFileMetadata>;
    jsonFiles: Map<string, ReactiveJsonFile>;
    loading: boolean;
    networkErrors: string[];

    constructor(index: ReactiveIndex, path: string) {
        this.index = index;
        this.path = (null as any);
        this.metadata = null;
        this.children = new Map();
        this.jsonFiles = new Map();

        this.index.addLoadingListener(action((loading: boolean) => {
            this.loading = loading;
        }));
        this.loading = this.index.loading;

        this.networkErrors = [];
        this.index.addNetworkErrorListener(action((errors: string[]) => {
            this.networkErrors = errors;
            console.log("Got network error listener called: " + JSON.stringify(errors));
        }));

        makeObservable(this, {
            path: observable,
            metadata: observable,
            loading: observable,
            children: observable,
            networkErrors: observable
        });

        this.setPath(path);
    }

    /**
     * Set the cursor to point at a new file, which will change its state to reflect the state of
     * the new file.
     * 
     * @param path the new path to use
     */
    setPath = (path: string) => {
        if (path === this.path) return;

        // Clean up the old listeners.
        // This is a no-op if the listeners aren't registered
        this.index.removeMetadataListener(this.path, this._metadataListener);
        this.index.removeChildrenListener(this.path, this._onChildrenListener);

        this.jsonFiles.forEach((file: ReactiveJsonFile) => file.pathWillChange());
        this.path = path;
        this.metadata = this.index.getMetadata(this.path);
        this.children = this.index.getChildren(this.path);
        this.jsonFiles.forEach((file: ReactiveJsonFile) => file.pathChanged());

        // Add new listeners for changes at the current path
        this.index.addMetadataListener(this.path, this._metadataListener);
        this.index.addChildrenListener(this.path, this._onChildrenListener);
    };

    /**
     * @returns True if the S3 index is refreshing
     */
    getIsLoading = () => {
        return this.loading;
    };

    /**
     * This returns true if there are any active network errors
     */
    hasNetworkErrors = () => {
        return this.networkErrors.length > 0;
    };

    /**
     * @returns A list of human-readable strings describing the currently active errors.
     */
    getNetworkErrors = () => {
        return this.networkErrors;
    };

    /**
     * This clears the errors displayed for the network. This could be a temporary action, if the network calls are retried and re-establish errors.
     */
    clearNetworkErrors = () => {
        this.index.clearAllNetworkErrors();
    }

    /**
     * This retrieves or creates an object whose job is to retrieve and store changes to a JSON file in S3.
     * 
     * @param path The path of the JSON file object to retrieve or create
     */
    getJsonFile = (path: string) => {
        let file = this.jsonFiles.get(path);
        if (file == null) {
            file = new ReactiveJsonFile(this, path);
            this.jsonFiles.set(path, file);
        }
        return file;
    };

    /**
     * This cleans up the resources currently claimed by a JSON file.
     * 
     * @param path 
     */
    deleteJsonFile = (path: string) => {
        this.jsonFiles.delete(path);
    };

    /**
     * Set a ReactiveIndex to back this cursor. This handles cleaning up any old listeners we 
     * had pointed at an old index, and creating new ones on the new index.
     * 
     * @param index the new ReactiveIndex to use
     */
    setIndex = (index: ReactiveIndex) => {
        if (index === this.index) return;

        // Clean up the old listeners.
        // This is a no-op if the listeners aren't registered
        this.index.removeMetadataListener(this.path, this._metadataListener);
        this.index.removeChildrenListener(this.path, this._onChildrenListener);

        this.jsonFiles.forEach((file: ReactiveJsonFile) => file.pathWillChange());
        this.index = index;
        this.metadata = this.index.getMetadata(this.path);
        this.children = this.index.getChildren(this.path);
        this.jsonFiles.forEach((file: ReactiveJsonFile) => file.pathChanged());

        // Add new listeners for changes at the current path
        this.index.addMetadataListener(this.path, this._metadataListener);
        this.index.addChildrenListener(this.path, this._onChildrenListener);
    };

    /**
     * @returns True if the file pointed to at "path" exists in S3
     */
    getExists = (path?: string) => {
        if (path == null) {
            return this.metadata != null;
        }
        else {
            return this.getChildMetadata(path) != null;
        }
    };

    /**
     * @param child The child file name to look for
     * @returns the child metadata if the child exists, null otherwise
     */
    getChildMetadata = (child: string) => {
        return this.children.get(child) ?? null;
    };

    /**
     * This computes and returns the children of a given "child" path. If the 
     * child doesn't exist, this will return an empty set of children.
     * 
     * @param childPath the child folder to return the children of
     */
    getChildrenOf = (childPath: string) => {
        if (!childPath.startsWith("/")) childPath = childPath + "/";

        let subChildren: Map<string, ReactiveFileMetadata> = new Map();
        this.children.forEach((file, path) => {
            if (path.startsWith(childPath)) {
                let subPath = path.substring(childPath.length);
                subChildren.set(subPath, file);
            }
        });

        return subChildren;
    };

    /**
     * This computes synthetic ReactiveFileMetadata objects for each folder, 
     * by summing the sizes of the child files that lie within that folder, and 
     * taking the most recent modification time.
     * 
     * @argument of the child path to get the child folders for
     */
    getImmediateChildFolders = (of: string = '') => {
        let folders: Map<string, ReactiveFileMetadata> = new Map();
        this.children.forEach((file: ReactiveFileMetadata, relativePath: string) => {
            if (!relativePath.startsWith(of) || relativePath === of) {
                return;
            }
            relativePath = relativePath.substring(of.length);
            let parts = relativePath.split('/');
            let existingFolder: ReactiveFileMetadata | undefined = folders.get(parts[0]);
            if (existingFolder == null) {
                // Create a folder to contain just this object
                folders.set(parts[0], {
                    key: parts[0],
                    lastModified: file.lastModified,
                    size: file.size
                });
            }
            else {
                // Add our size to the folder, and update the lastModified
                folders.set(parts[0], {
                    key: parts[0],
                    lastModified: file.lastModified > existingFolder.lastModified ? file.lastModified : existingFolder.lastModified,
                    size: file.size + existingFolder.size
                });
            }
        });
        return [...folders.values()].sort();
    };

    /**
     * Returns true if all the childNames exist as files (or are implied by path names as virtual folders)
     * 
     * @param childNames A list of child paths to check for existence. If not provided, this method just checks if we have _any_ children at all.
     */
    hasChildren = (childNames?: string[]) => {
        if (childNames == null) {
            return this.children.size > 0;
        }
        else {
            let existingChildNames: string[] = [...this.children.keys()];

            for (let i = 0; i < childNames.length; i++) {
                let foundMatch = false;
                for (let j = 0; j < existingChildNames.length; j++) {
                    if (existingChildNames[j].startsWith(childNames[i])) {
                        let remainingPath = existingChildNames[j].substring(childNames[i].length);
                        if (remainingPath.length === 0 || remainingPath.charAt(0) === '/' || childNames[i].endsWith('/')) {
                            foundMatch = true;
                            break;
                        }
                    }
                }
                if (!foundMatch) {
                    return false;
                }
            }

            return true;
        }
    };

    /**
     * Returns true if the folder at `childPath` has the children `grandchildNames`
     * 
     * This is a convenience method to concatente the childPath with each grandchildName, and pass that to this.hasChildren()
     * 
     * @param childPath 
     * @param grandchildNames 
     */
    childHasChildren = (childPath: string, grandchildNames: string[]) => {
        if (!childPath.endsWith("/")) childPath += "/";
        let concatenated: string[] = [];
        for (let i = 0; i < grandchildNames.length; i++) {
            concatenated.push(childPath + grandchildNames[i]);
        }
        return this.hasChildren(concatenated);
    };

    /**
     * Tries to upload to the file we're currently pointing at
     * @returns a promise for successful upload
     */
    upload = (contents: File | string, progressCallback: (percentage: number) => void = () => { }) => {
        return this.index.upload(this.path, contents, progressCallback);
    };

    /**
     * Tries to upload to the file we're currently pointing at
     * @returns a promise for successful upload
     */
    uploadChild = (childPath: string, contents: File | string, progressCallback: (percentage: number) => void = () => { }) => {
        let myPath = ensurePathEndsWithSlash(this.path);

        return this.index.upload(myPath + childPath, contents, progressCallback);
    };

    /**
     * This actually downloads a file from S3, if the browser allows it
     */
    downloadFile = (childPath?: string) => {
        let myPath = this.path;
        if (childPath != null) {
            myPath = ensurePathEndsWithSlash(myPath);
            myPath += childPath;
        }

        return this.index.downloadFile(myPath);
    };

    /**
     * This downloads and parses a file into a string, and returns it
     * 
     * @returns A promise for the text of the file being downloaded
     */
    downloadText = (childPath?: string) => {
        let myPath = this.path;
        if (childPath != null) {
            myPath = ensurePathEndsWithSlash(myPath);
            myPath += childPath;
        }

        return this.index.downloadText(myPath);
    };

    /**
     * This downloads and parses a file into a string, and returns it
     * 
     * @returns A promise for the text of the file being downloaded
     */
    downloadZip = (childPath?: string, progressCallback?: (progress: number) => void) => {
        let myPath = this.path;
        if (childPath != null) {
            myPath = ensurePathEndsWithSlash(myPath);
            myPath += childPath;
        }

        return this.index.downloadZip(myPath, progressCallback);
    };

    /**
     * Tries to delete the file we're currently pointing at, which fails if it doesn't exist.
     * @returns a promise for successful deletion
     */
    delete = () => {
        return this.index.delete(this.path);
    };

    /**
     * Tries to delete the file we're currently pointing at, which fails if it doesn't exist.
     * @returns a promise for successful deletion
     */
    deleteChild = (childPath: string) => {
        let myPath = this.path;
        myPath = ensurePathEndsWithSlash(myPath);

        return this.index.delete(myPath + childPath);
    };

    /**
     * Deletes all the files that match a given prefix.
     * 
     * @param prefix The prefix to match to files, and if they match, delete them
     */
    deleteByPrefix = (prefix: string) => {
        let totalPrefix = this.path;
        if (this.path.length > 0 && prefix.length > 0) {
            totalPrefix = ensurePathEndsWithSlash(totalPrefix);
            totalPrefix += prefix;
        }
        else {
            totalPrefix += prefix;
        }
        totalPrefix = ensurePathEndsWithSlash(totalPrefix);

        return this.index.deleteByPrefix(totalPrefix);
    };

    _metadataListener = (file: ReactiveFileMetadata | null) => {
        this.metadata = file;
    };

    _onChildrenListener = (children: Map<string, ReactiveFileMetadata>) => {
        this.children = children;
    };
}

/// This holds the low-level copy of the S3 output, without nulls
type ReactiveFileMetadata = {
    key: string;
    lastModified: Date;
    size: number;
}

/// This is the low-level API that interacts directly with S3 and PubSub to keep up to date.
class ReactiveIndex {
    files: Map<string, ReactiveFileMetadata> = new Map();

    region: string;
    bucketName: string;
    // This is the level, in the Amplify API's, of storage this index is reflecting
    level: 'protected' | 'public';
    // This is the prefix that's getting attached (invisibly) to the paths we send to Amplify
    // before they get forwarded to S3
    globalPrefix: string = '';

    metadataListeners: Map<string, Array<(metadata: ReactiveFileMetadata | null) => void>> = new Map();

    childrenListenersEnabled: boolean = true;
    childrenListeners: Map<string, Array<(children: Map<string, ReactiveFileMetadata>) => void>> = new Map();
    childrenLastNotified: Map<string, Map<string, ReactiveFileMetadata>> = new Map();

    // We initialize as "loading", because we haven't loaded the relevant file index yet
    loading: boolean = true;
    loadingListeners: Array<(loading: boolean) => void> = [];

    // This holds network error messages, one per key. Individual keys identify different errors that may have independent lifetimes.
    // For example, an upload request may fail, and then retry and eventually resolve, with the key "UPLOAD", while a websocket glitch
    // with key "SOCKET" could happen and then resolve at any time during that process.
    networkErrors: Map<string, string> = new Map();
    networkErrorListeners: Array<(errors: string[]) => void> = [];

    // This is a handle on the PubSub socket object we'll use
    socket: RobustMqtt;

    constructor(region: string, bucketName: string, level: 'protected' | 'public', runNetworkSetup: boolean = true, socket: RobustMqtt) {
        this.region = region;
        this.bucketName = bucketName;
        this.level = level;
        this.socket = socket;

        // We don't want to run network setup in our unit tests
        if (runNetworkSetup) {
            this.fullRefresh();
            this.setupPubsub();
        }
    }

    /**
     * If you call the constructor with `runNetworkSetup = false`, then you can use this method later to set up the network for this index.
     */
    setupPubsub = () => {
        if (this.level === 'public') {
            this.globalPrefix = 'public/';
            return this.registerPubSubListeners();
        }
        else if (this.level === 'protected') {
            return Auth.currentCredentials().then((credentials) => {
                this.globalPrefix = "protected/" + credentials.identityId + "/";
                return this.registerPubSubListeners();
            });
        }
        return Promise.resolve();
    };

    /**
     * This uploads a file to the server, and notifies PubSub of having done so.
     * 
     * @param path the path to upload to
     * @param contents the contents to upload
     * @param progressCallback OPTIONAL: a callback to receive with updates on upload progress
     * @returns a promise that resolves when the full operation is complete
     */
    upload = (path: string, contents: File | string, progressCallback: (percentage: number) => void = () => { }) => {
        const fullPath = this.globalPrefix + path;
        const updatedFile = {
            key: fullPath,
            lastModified: (new Date()).getTime(), // = now
            size: new Blob([contents]).size
        };
        const topic = makeTopicPubSubSafe("/UPDATE/" + fullPath);
        console.log("Updating '" + topic + "' with " + JSON.stringify(updatedFile));
        const uploadObject = new RobustUpload(this.region, this.bucketName, fullPath, contents, '');
        return uploadObject.upload((progress) => {
            progressCallback(progress.loaded / progress.total);
        }).then((response: any) => {
            console.log("S3.put() Completed callback", response);
            progressCallback(1.0);
            this.clearNetworkError("Upload");
            return this.socket.publish(topic, JSON.stringify(updatedFile));
        }).catch((e: any) => {
            this.setNetworkError("Upload", "We got an error trying to upload data!");
            console.error("Error on Storage.put(), caught in .errorCallback() handler", e);
            throw e;
        });

        /*
        return new Promise(
            (resolve: (value: void) => void, reject: (reason?: any) => void) => {
                try {
                    Storage.put(path, contents, {
                        level: this.level,
                        progressCallback: (progress) => {
                            console.log("S3.put() Progress callback");
                            progressCallback(progress.loaded / progress.total);
                        },
                        completeCallback: action((event) => {
                            console.log("S3.put() Completed callback", event);
                            progressCallback(1.0);
                            this.clearNetworkError("Upload");
                            this.socket.publish(topic, JSON.stringify(updatedFile)).then(() => resolve());
                        }),
                        errorCallback: (e: any) => {
                            this.setNetworkError("Upload", "We got an error trying to upload a file!");
                            console.error("Error on Storage.put(), caught in .errorCallback() handler", e);
                            reject(e);
                        }
                    })
                        .then((result) => {
                            console.log("S3.put() Promise resolved", result);
                            progressCallback(1.0);
                            this.clearNetworkError("Upload");
                            this.socket.publish(topic, JSON.stringify(updatedFile)).then(() => resolve());
                        })
                        .catch((e) => {
                            console.log("S3.put() Promise error");
                            this.setNetworkError("Upload", "We got an error trying to upload a file!");
                            console.error("Error on Storage.put(), caught in .catch() handler", e);
                            reject(e);
                        });
                }
                catch (e) {
                    this.setNetworkError("Upload", "We got an error trying to upload a file!");
                    console.error("Error on Storage.put(), caught in catch block", e);
                    reject(e);
                }
            }
        );
        */
    }

    /**
     * This attempts to delete a file in S3, and notify PubSub of having done so.
     * 
     * @param path The file to delete
     * @returns a promise that resolves when the full operation is complete
     */
    delete = (path: string) => {
        const fullPath = this.globalPrefix + path;
        const topic = makeTopicPubSubSafe("/DELETE/" + fullPath);
        return Storage.remove(path, { level: this.level })
            .then((result) => {
                console.log("Delete", result);
                if (result != null && result.$metadata != null && result.$metadata.httpStatusCode != null) {
                    this.clearNetworkError("Delete");
                    return this.socket.publish(topic, JSON.stringify({ key: fullPath }));
                }
                else {
                    this.setNetworkError("Delete", "We got an error trying to delete a file!");
                    console.log("delete() error: " + path);
                    throw new Error("Got an error trying to delete a file");
                }
            }).catch(e => {
                this.setNetworkError("Delete", "We got an error trying to delete a file!");
                console.log("delete() error: " + path);
                console.log(e);
                throw e;
            });
    }

    /**
     * Deletes all the files that match a given prefix.
     * 
     * @param prefix The prefix to match to files, and if they match, delete them
     * @returns a promise that resolves when the full operation is complete
     */
    deleteByPrefix = (prefix: string) => {
        let allPromises: Promise<void>[] = [];
        this.files.forEach((v, path: string) => {
            if (path.startsWith(prefix)) {
                allPromises.push(this.delete(path));
            }
        });
        return Promise.all(allPromises);
    }

    /**
     * @returns A signed URL that someone could use to download a file
     */
    getSignedURL = (path: string) => {
        return Storage.get(path, {
            level: this.level,
        });
    };

    /**
     * This actually downloads a file from S3, if the browser allows it
     */
    downloadFile = (path: string) => {
        return Storage.get(path, {
            level: this.level,
        }).then((signedURL) => {
            this.clearNetworkError("Get");
            const link = document.createElement("a");
            link.href = signedURL;
            link.target = "#";
            link.click();
        }).catch(e => {
            this.setNetworkError("Get", "We got an error trying to download a file!");
            console.log("DownloadFile() error: " + path);
            console.log(e);
            return '';
        });
    };

    /**
     * This downloads and parses a file into a string, and returns it
     * 
     * @returns A promise for the text of the file being downloaded
     */
    downloadText = (path: string) => {
        return Storage.get(path, {
            level: this.level,
            download: true,
            cacheControl: "no-cache",
        }).then((result) => {
            this.clearNetworkError("Get");
            if (result != null && result.Body != null) {
                // data.Body is a Blob
                return (result.Body as Blob).text().then((text: string) => {
                    return text;
                });
            }
            throw new Error(
                'Result of downloading "' + path + "\" didn't have a Body"
            );
        }).catch(e => {
            this.setNetworkError("Get", "We got an error trying to download a file!");
            console.log("DownloadText() error: " + path);
            console.log(e);
            return '';
        });
    };

    /**
     * This downloads and unzips a file into a string, and returns it
     * 
     * @param path the path of the file to download
     * @returns a promise for the unzipped text of the file being downloaded
     */
    downloadZip = (path: string, progressCallback?: (progress: number) => void) => {
        if (progressCallback) progressCallback(0.0);
        return Storage.get(path, {
            level: this.level,
            download: true,
            cacheControl: "no-cache",
            progressCallback
        }).then((result) => {
            this.clearNetworkError("Get");
            const zip = new JSZip();
            if (progressCallback) progressCallback(1.0);
            console.log("Unzipping large file");
            if (result != null && result.Body != null) {
                // data.Body is a Blob
                return zip.loadAsync(result.Body as Blob, ((metadata: any) => {
                    console.log(metadata);
                }) as any).then((unzipped: JSZip) => {
                    console.log("Unzipped!");
                    return unzipped.file(Object.keys(unzipped.files)[0])?.async("uint8array");
                });
            }
            throw new Error(
                'Result of downloading "' + path + "\" didn't have a Body"
            );
        }).catch(e => {
            this.setNetworkError("Get", "We got an error trying to download a file!");
            console.log("DownloadZip() error: " + path);
            console.log(e);
            return new Uint8Array();
        });;
    };

    /**
     * This gets called when we detect a file at a given path is deleted. It removes the file from the 
     * index, and calls any waiting listeners.
     * 
     * @private
     * @param path 
     */
    _deleteFileInIndex = (path: string) => {
        this.files.delete(path);
        // call child listeners
        this._updateChildListeners();
        // call metadata listeners to alert them the file doesn't exist anymore
        const existListeners = this.metadataListeners.get(path) ?? [];
        for (let listener of existListeners) {
            listener(null);
        }
    };

    /**
     * This gets called when a file was created or updated. Because S3 is only eventually consistent and 
     * PubSub is slow, this may get called with an older copy of the file, so we have to ignore updates 
     * that are older than the current files.
     * 
     * @private
     * @param file 
     */
    _updateFileInIndex = (file: ReactiveFileMetadata) => {
        const existingFile: ReactiveFileMetadata | undefined = this.files.get(file.key);
        // If the file doesn't exist, or this update has a later timestamp, update and replace
        if (existingFile == null || existingFile.lastModified < file.lastModified) {
            this.files.set(file.key, file);
            // call child listeners
            this._updateChildListeners();
            // call creation/update listeners
            const updateListeners = this.metadataListeners.get(file.key) ?? [];
            for (let listener of updateListeners) {
                listener(file);
            }
        }
    };

    /**
     * This can temporarily disable the child listeners, while we do a large number of updates to the page structure.
     */
    _setChildListenerUpdatesEnabled = (enabled: boolean) => {
        this.childrenListenersEnabled = enabled;
        if (this.childrenListenersEnabled) {
            this._updateChildListeners();
        }
    }

    /**
     * This goes through and computes whether we need to notify any should child listeners of changes.
     */
    _updateChildListeners = () => {
        if (!this.childrenListenersEnabled) return;
        this.childrenListeners.forEach((listeners, key: string) => {
            let children = this.getChildren(key);

            if (JSON.stringify([...(this.childrenLastNotified.get(key) ?? new Map())].sort()) !== JSON.stringify([...children].sort())) {
                for (let listener of listeners) {
                    listener(children);
                }
            }

            this.childrenLastNotified.set(key, children);
        });
    };

    /**
     * Gets called when PubSub receives an "/UPDATE/#" message. This is broken out as a separate function to make testing easier.
     * 
     * @param file 
     */
    _onReceivedPubSubUpdate = (file: ReactiveFileMetadata) => {
        console.log("Got PubSub update!", file);
        this._updateFileInIndex(file);
    };

    /**
     * Gets called when PubSub receives an "/DELETE/#" message. This is broken out as a separate function to make testing easier.
     * 
     * @param file 
     */
    _onReceivedPubSubDelete = (file: { key: string }) => {
        console.log("Got PubSub delete!", file);
        this._deleteFileInIndex(file.key);
    };

    /**
     * This does a complete refresh, overwriting the paths
     */
    fullRefresh = () => {
        this.setIsLoading(true);
        return this.loadFolder("", false).then((result) => {
            this.clearNetworkError("FullRefresh");

            // 2. Update the set of files

            // 2.1. Build a map of the updated set of objects
            const newFiles: Map<string, ReactiveFileMetadata> = new Map();
            for (let i = 0; i < result.files.length; i++) {
                const key = result.files[i].key;
                if (key != null) {
                    newFiles.set(key, result.files[i]);
                }
            }

            //////////////////////////////////////////////
            // Begin a bulk change to the index
            this._setChildListenerUpdatesEnabled(false);
            //////////////////////////////////////////////

            // 2.2. For each existing key in our current files, check if it doesn't
            // exist in the updated set. If it doesn't, then it's been deleted.
            this.files.forEach((file: ReactiveFileMetadata, path: string) => {
                if (!newFiles.has(path)) {
                    // This means that "path" was deleted!
                    this._deleteFileInIndex(path);
                }
            });

            newFiles.forEach((file: ReactiveFileMetadata, path: string) => {
                this._updateFileInIndex(file);
            });

            //////////////////////////////////////////////
            // Register the bulk change to the index
            this._setChildListenerUpdatesEnabled(true);
            //////////////////////////////////////////////

            this.setIsLoading(false);
        })
            .catch((err: Error) => {
                this.setIsLoading(false);
                console.error('Unable to refresh index type "' + this.level + '"');
                console.log(err);
                this.setNetworkError("FullRefresh", "We got an error trying to load the files! Attempting to reconnect...");
            });
    };


    /**
     * This is a replacement for Storage.load(), but with support for limiting the results to one folder level, and to doing multiple pages of calls.
     */
    loadFolder = async (folder: string, limitToOneFolderLevel: boolean) => {

        if (this.level === 'public') {
            this.globalPrefix = 'public/';
        }
        else if (this.level === 'protected') {
            let credentials = await Auth.currentCredentials();
            this.globalPrefix = "protected/" + credentials.identityId + "/";
        }

        if (folder !== '' && !folder.endsWith('/')) {
            folder += '/';
        }
        let path = this.globalPrefix + folder;

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
        }

        const s3client = new S3Client({
            region: this.region,
            // Using provider instead of a static credentials, so that if an upload task was in progress, but credentials gets
            // changed or invalidated (e.g user signed out), the subsequent requests will fail.
            credentials: credentialsProvider,
            customUserAgent: getAmplifyUserAgent()
        });

        const bucketName = this.bucketName;
        const globalPrefix = this.globalPrefix;
        async function listAsync(continuationToken?: string, filesSoFar?: ReactiveFileMetadata[], foldersSoFar?: string[]): Promise<{ files: ReactiveFileMetadata[], folders: string[] }> {
            const listObjectsCommand = new ListObjectsV2Command({
                Bucket: bucketName,
                Prefix: path,
                Delimiter: limitToOneFolderLevel ? '/' : undefined,
                MaxKeys: 1000,
                ContinuationToken: continuationToken
            });

            const output: ListObjectsV2CommandOutput = await s3client.send(listObjectsCommand);

            let files: ReactiveFileMetadata[] = filesSoFar ? [...filesSoFar] : [];
            if (output.Contents != null && output.Contents.length > 0) {
                for (let i = 0; i < output.Contents.length; i++) {
                    let file = output.Contents[i];
                    if (file.Key != null && file.LastModified != null && file.Size != null && file.Key.startsWith(globalPrefix)) {
                        files.push({
                            key: file.Key.substring(globalPrefix.length),
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
                    if (folder.Prefix != null && folder.Prefix.startsWith(globalPrefix)) {
                        let folderFullPath = folder.Prefix.substring(globalPrefix.length);
                        folders.push(folderFullPath);
                    }
                }
            }

            if (output.NextContinuationToken != null) {
                return listAsync(output.NextContinuationToken, files, folders);
            }

            return {
                files,
                folders
            }
        };

        return listAsync().then((results) => {
            return results;
        });
    };

    /**
     * This registers a PubSub listener for live change-updates on our S3 index
     */
    registerPubSubListeners = () => {
        this.socket.subscribe("/UPDATE/" + this.globalPrefix + "#", (topic: string, message: string) => {
            const msg: any = JSON.parse(message);
            const globalKey: string = msg.key;
            const key: string = globalKey.substring(this.globalPrefix.length);
            const lastModified: Date = new Date(msg.lastModified);
            const size: number = msg.size;
            this._onReceivedPubSubUpdate({
                key, lastModified, size
            });
        });

        this.socket.subscribe("/DELETE/" + this.globalPrefix + "#", (topic: string, message: string) => {
            const msg: any = JSON.parse(message);
            const globalKey: string = msg.key;
            const key: string = globalKey.substring(this.globalPrefix.length);
            this._onReceivedPubSubDelete({ key });
        });

        this.socket.addConnectionListener((connected) => {
            if (!connected) {
                console.log("PubSub disconnected");
                this.setNetworkError("PubSub", "We got an error in PubSub! Attempting to reconnect...");
            }
            else {
                this.clearNetworkError("PubSub");
            }
        });
    };

    /**
     * @returns a list of errors currently active
     */
    getNetworkErrorMessages = () => {
        let errorsList: { key: string, value: string }[] = [];

        this.networkErrors.forEach((value: string, key: string) => {
            errorsList.push({ key, value });
        });

        errorsList.sort((a, b) => a.key.localeCompare(b.key));
        return errorsList.map((a) => a.value);
    };

    /**
     * This adds a network error listener
     * 
     * @param listener the listener to add
     */
    addNetworkErrorListener = (listener: (errors: string[]) => void) => {
        this.networkErrorListeners.push(listener);
    }

    /**
     * Thes raises a network error (or overwrites the message displayed to the user).
     * 
     * @param key The key of the error, to allow us to clear this error later
     * @param value The user-friendly text to (optionally) display to the user
     */
    setNetworkError = (key: string, value: string) => {
        console.log("Setting network error " + key + "=" + value);
        let oldErrors = this.getNetworkErrorMessages();
        this.networkErrors.set(key, value);
        let newErrors = this.getNetworkErrorMessages();
        if (JSON.stringify(newErrors) !== JSON.stringify(oldErrors)) {
            this.networkErrorListeners.forEach(listener => listener(newErrors));
        }
    };

    /**
     * This resolves all current network errors
     */
    clearAllNetworkErrors = () => {
        let oldErrors = this.getNetworkErrorMessages();
        this.networkErrors.clear();
        let newErrors = this.getNetworkErrorMessages();
        if (JSON.stringify(newErrors) !== JSON.stringify(oldErrors)) {
            this.networkErrorListeners.forEach(listener => listener(newErrors));
        }
    };

    /**
     * This resolves a network error
     * 
     * @param key The key of the error, must match the key in setNetworkError()
     */
    clearNetworkError = (key: string) => {
        console.log("Clearing network error " + key);
        let oldErrors = this.getNetworkErrorMessages();
        this.networkErrors.delete(key);
        let newErrors = this.getNetworkErrorMessages();
        if (JSON.stringify(newErrors) !== JSON.stringify(oldErrors)) {
            this.networkErrorListeners.forEach(listener => listener(newErrors));
        }
    };

    /**
     * @returns True if the index is currently loading
     */
    getIsLoading = () => {
        return this.loading;
    };

    /**
     * Sets the loading flag, and calls any listeners.
     */
    setIsLoading = (loading: boolean) => {
        console.log("Setting isLoading to " + loading);
        if (loading !== this.loading) {
            this.loading = loading;
            this.loadingListeners.forEach((listener) => {
                listener(loading);
            });
        }
    };

    /**
     * This adds a listener that gets called when the loading state of the index changes.
     */
    addLoadingListener = (onLoading: (loading: boolean) => void) => {
        this.loadingListeners.push(onLoading);
    };

    /**
     * This returns true if a file exists, and false if it doesn't.
     * 
     * @param path The exact path to check
     * @returns the FileMetadata for this file, or null if it doesn't exist
     */
    getMetadata = (path: string) => {
        return this.files.get(path) ?? null;
    };

    /**
     * Fires whenever the file is created, deleted, or updated
     * 
     * @param path The path to listen to
     * @param onUpdate Fires whenever a path is created, or deleted
     */
    addMetadataListener = (path: string, onUpdate: (exists: ReactiveFileMetadata | null) => void) => {
        if (!this.metadataListeners.has(path)) {
            this.metadataListeners.set(path, []);
        }
        this.metadataListeners.get(path)?.push(onUpdate);
    };

    /**
     * This cleans up a listener. This is good to call to avoid memory leaks, since listeners can 
     * hold references to other objects.
     * 
     * @param path 
     * @param onUpdate 
     */
    removeMetadataListener = (path: string, onUpdate: (exists: ReactiveFileMetadata | null) => void) => {
        const index: number = this.metadataListeners.get(path)?.indexOf(onUpdate) ?? -1;
        if (index !== -1) {
            this.metadataListeners.get(path)?.splice(index, 1);
        }
    };

    /**
     * This computes the set of all child files.
     * 
     * @param path The folder path
     * @returns A map where keys are sub-paths, and values are file information
     */
    getChildren = (path: string) => {
        if (path !== '' && !path.endsWith('/')) path = path + '/';

        let children: Map<string, ReactiveFileMetadata> = new Map();

        this.files.forEach((file: ReactiveFileMetadata, key: string) => {
            if (key.startsWith(path) && key !== path) {
                let suffix = key.substring(path.length);
                children.set(suffix, file);
            }
        });

        return children;
    };

    /**
     * Fires whenever the set of children of a given path changes (either added or deleted)
     * 
     * @param path The folder path to listen for
     */
    addChildrenListener = (path: string, onChange: (children: Map<string, ReactiveFileMetadata>) => void) => {
        if (!this.childrenListeners.has(path)) {
            this.childrenListeners.set(path, []);
        }
        this.childrenListeners.get(path)?.push(onChange);
    };

    /**
     * This cleans up a listener. This is good to call to avoid memory leaks, since listeners can 
     * hold references to other objects.
     * 
     * @param path 
     * @param onChange
     */
    removeChildrenListener = (path: string, onChange: (children: Map<string, ReactiveFileMetadata>) => void) => {
        const index: number = this.childrenListeners.get(path)?.indexOf(onChange) ?? -1;
        if (index !== -1) {
            this.childrenListeners.get(path)?.splice(index, 1);
        }
    };

    /**
     * This is useful for detecting memory leaks.
     * 
     * @returns The total number of registered existence listeners
     */
    getNumMetadataListeners = () => {
        let count = [0];
        this.metadataListeners.forEach(l => {
            count[0] += l.length;
        });
        return count[0];
    }

    /**
     * This is useful for detecting memory leaks.
     * 
     * @returns The total number of registered children listeners
     */
    getNumChildrenListeners = () => {
        let count = [0];
        this.childrenListeners.forEach(l => {
            count[0] += l.length;
        });
        return count[0];
    }
}

export { ReactiveIndex, ReactiveCursor, ReactiveJsonFile };