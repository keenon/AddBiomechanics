import { ReactiveCursor, ReactiveIndex } from "./ReactiveS3";
import { makeAutoObservable } from 'mobx';

type MocapFolderEntry = {
    type: 'folder' | 'mocap';
    href: string;
    key: string;
    lastModified: Date;
    size: number;
};

type MocapTrialEntry = {
    key: string;
    lastModified: Date;
    size: number;
};

class MocapS3Cursor {
    urlPath: string;
    rawCursor: ReactiveCursor;
    publicS3Index: ReactiveIndex;
    protectedS3Index: ReactiveIndex;
    urlError: boolean;

    constructor(publicS3Index: ReactiveIndex, protectedS3Index: ReactiveIndex) {
        const parsedUrl = this.parseUrlPath(window.location.pathname);

        this.rawCursor = new ReactiveCursor(parsedUrl.isPublic ? publicS3Index : protectedS3Index, parsedUrl.path);
        this.publicS3Index = publicS3Index;
        this.protectedS3Index = protectedS3Index;
        this.urlError = parsedUrl.error;
        this.urlPath = window.location.pathname;
        makeAutoObservable(this);
    }

    /**
     * This breaks a path down into the structured data.
     * 
     * @param urlPath 
     * @returns 
     */
    parseUrlPath = (urlPath: string) => {
        let isPublic: boolean = true;
        let path: string = '';
        let error: boolean = false;

        // 1. Set an error state if the path is empty
        if (urlPath.length == 0) {
            error = true;
            return { isPublic, path, error };
        }
        let pathParts: string[] = urlPath.split("/");
        while (pathParts[0] === '') {
            pathParts.splice(0, 1);
        }

        // 2. Pick which file index to use based on the first part of the path
        if (pathParts[0] === 'public_data') {
            isPublic = true;
        }
        else if (pathParts[0] === 'my_data') {
            isPublic = false;
        }
        else {
            error = true;
        }

        // 3. Use the remainder of the path to set the S3 bucket we're viewing
        pathParts.splice(0, 1);
        path = pathParts.join("/");

        return { isPublic, path, error };
    }

    /**
     * This is a convenience method to return the current file path (not including the "my_data" / "public_data" part at the beginning)
     */
    getCurrentFilePath = () => {
        return this.parseUrlPath(this.urlPath).path;
    };

    /**
     * @returns The name of the folder we're currently in
     */
    getCurrentFileName = () => {
        const parts = this.getCurrentFilePath().split('/');
        if (parts.length === 0) return '';
        else return parts[parts.length - 1];
    };

    /**
     * This sets a path, which can update the state of the cursor
     * 
     * @param path The portion of the URL after the /, and before the ?
     */
    setUrlPath = (urlPath: string) => {
        if (urlPath === this.urlPath) return;
        this.urlPath = urlPath;

        const parsedUrl = this.parseUrlPath(this.urlPath);
        console.log("Setting url path to " + urlPath, parsedUrl);

        this.urlError = parsedUrl.error;
        this.rawCursor.setIndex(parsedUrl.isPublic ? this.publicS3Index : this.protectedS3Index);
        this.rawCursor.setPath(parsedUrl.path);
    };

    /**
     * @returns True if the cursor is pointing at readonly (i.e. public) data
     */
    dataIsReadonly = () => {
        return this.rawCursor.index === this.publicS3Index;
    };

    /**
     * @returns The opposite of dataIsReadonly()
     */
    canEdit = () => {
        return !this.dataIsReadonly();
    };

    /**
     * Deletes all the files that match a given prefix.
     * 
     * @param prefix The prefix to match to files, and if they match, delete them
     */
    deleteByPrefix = (prefix: string) => {
        return this.rawCursor.deleteByPrefix(prefix);
    };

    /**
     * This returns the type of file we're looking at, so that we can choose which viewer to display
     */
    getFileType = () => {
        const hasChildren: boolean = this.rawCursor.hasChildren();
        const exists: boolean = this.rawCursor.getExists();
        if (this.urlError || (!exists && !hasChildren)) {
            return "not-found";
        }
        else if (this.rawCursor.hasChildren(["_subject.json", "trials"])) {
            return "mocap";
        }
        else {
            return "folder";
        }
    };

    ///////////////////////////////////////////////////////////////////////////////////////////
    // Folder controls
    ///////////////////////////////////////////////////////////////////////////////////////////

    /**
     * Creates a new child folder to hold a new Mocap subject. This requires creating a folder and several nested files.
     * 
     * @param name The name of the subject to create under the current folder
     * @returns a promise for successful completion
     */
    createMocapClip = (name: string) => {
        return this.rawCursor.uploadChild(name, "").then(() => {
            this.rawCursor.uploadChild(name + "/_subject.json", "{}").then(() => {
                this.rawCursor.uploadChild(name + "/trials/", "");
            });
        });
    };

    /**
     * Creates an empty folder within the current folder. This creates an empty placeholder file in S3.
     * 
     * @param name The name of the folder to create
     * @returns a promise for successful completion
     */
    createFolder = (name: string) => {
        return this.rawCursor.uploadChild(name, "");
    };

    /**
     * @returns The contents of the current folder, with useful annotations on the data
     */
    getFolderContents = (of: string = '') => {
        let contents: MocapFolderEntry[] = [];
        let rawFolders = this.rawCursor.getImmediateChildFolders(of);
        let hrefPrefix = this.urlPath;
        if (!hrefPrefix.endsWith('/')) hrefPrefix += '/';

        for (let i = 0; i < rawFolders.length; i++) {
            let type: 'folder' | 'mocap' = 'folder';
            if (this.rawCursor.childHasChildren(rawFolders[i].key, ['trials/', '_subject.json'])) {
                type = 'mocap';
            }
            const href: string = hrefPrefix + rawFolders[i].key;

            contents.push({
                type,
                href,
                ...rawFolders[i]
            });
        }
        return contents;
    }

    ///////////////////////////////////////////////////////////////////////////////////////////
    // Mocap controls
    ///////////////////////////////////////////////////////////////////////////////////////////

    /**
     * This gets the list of the trials under this folder. If we're not pointing to a mocap subject, 
     * then this returns nothing.
     * 
     * @returns A list of all the trials that have been uploaded
     */
    getTrials = () => {
        let trials: MocapTrialEntry[] = [];
        let rawFolders = this.rawCursor.getImmediateChildFolders("trials/");
        for (let i = 0; i < rawFolders.length; i++) {
            if (this.rawCursor.childHasChildren(rawFolders[i].key, ['trials/', '_subject.json'])) {
            }

            trials.push({
                ...rawFolders[i]
            });
        }
        return trials;
    };

    /**
     * This attempts to guess from file names how to group bulk uploaded files into trials,
     * then goes ahead and creates those trials.
     * 
     * @param fileNames The list of file names that have been dragged onto the bulk uploader
     */
    bulkCreateTrials = (fileNames: string[]) => {
        const progress: Promise<void>[] = [];
        for (let i = 0; i < fileNames.length; i++) {
            if (fileNames[i].endsWith(".trc")) {
                const file = fileNames[i].substring(0, fileNames[i].length - ".trc".length);
                progress.push(this.rawCursor.uploadChild("trials/" + file, ""));
            }
        }
        return Promise.all(progress);
    };

    /**
     * This figures out the status of a given trial, based on which child files exist and don't exist.
     * 
     * @param trialName the name of the trial to check
     */
    getTrialStatus = (trialName: string) => {
        const markersMetadata = this.rawCursor.getChildMetadata("trials/" + trialName + "/markers.trc");

        const hasIK = this.rawCursor.getExists("trials/" + trialName + "/gold_ik.mot");
        const hasGRF = this.rawCursor.getExists("trials/" + trialName + "/grf.mot");
        const hasReadyToProcessFlag = this.rawCursor.getExists("trials/" + trialName + "/READY_TO_PROCESS");
        const hasProcessingFlag = this.rawCursor.getExists("trials/" + trialName + "/PROCESSING");

        const logMetadata = this.rawCursor.getChildMetadata("trials/" + trialName + "/log.txt");
        const previewMetadata = this.rawCursor.getChildMetadata("trials/" + trialName + "/preview.json");

        if (markersMetadata == null) {
            return 'empty';
        }
        else if (logMetadata != null && previewMetadata != null) {
            if (logMetadata.lastModified > markersMetadata.lastModified) {
                return 'done';
            }
            else {
                if (hasProcessingFlag) {
                    return 'processing';
                }
                else if (hasReadyToProcessFlag) {
                    return 'waiting';
                }
                else {
                    return 'could-process';
                }
            }
        }
        else if (hasProcessingFlag) {
            return 'processing';
        }
        else if (hasReadyToProcessFlag) {
            return 'waiting';
        }
        else {
            return 'could-process';
        }
    };

    /**
     * This adds the "READY_TO_PROCESS" file on the backend, which marks the trial as being fully uploaded, and
     * ready for the backend to pick up and work on.
     * 
     * @param trialName The name of the trial to mark
     */
    markTrialReadyForProcessing = (trialName: string) => {
        return this.rawCursor.uploadChild("trials/" + trialName + "/READY_TO_PROCESS", "");
    };
}

export default MocapS3Cursor;