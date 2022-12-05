import { ReactiveCursor, ReactiveIndex, ReactiveJsonFile, ReactiveTextFile } from "./ReactiveS3";
import { makeObservable, observable, action } from 'mobx';
import RobustMqtt from "./RobustMqtt";

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

type MocapProcessingFlags = {
    logTopic: string;
    timestamp: number;
}

type MocapProcessingLogMsg = {
    lines: string[];
    timestamp: number;
}

class LargeZipBinaryObject {
    object: any | null;
    loading: boolean;
    loadingProgress: number;
    dispose: () => void;

    constructor(rawCursor: ReactiveCursor, path: string, dispose: () => void) {
        this.object = null;
        this.loading = true;
        this.loadingProgress = 0.0;
        this.dispose = dispose;

        makeObservable(this, {
            loading: observable,
            loadingProgress: observable
        });

        rawCursor.downloadZip(path, action((progress: number | any) => {
            if (progress.loaded != null && progress.total != null) {
                this.loadingProgress = progress.loaded / progress.total;
                if (this.loadingProgress > 1.0) {
                    this.loadingProgress = 1.0;
                }
            }
            else {
                this.loadingProgress = progress;
            }
            console.log("Loading progress: " + this.loadingProgress);
        })).then(action((result?: Uint8Array) => {
            if (result != null) {
                console.log("Downloaded large result");
                this.object = result;
            }
            this.loading = false;
        }));
    }
}

class MocapS3Cursor {
    urlPath: string;
    dataPrefix: string;
    rawCursor: ReactiveCursor;
    publicS3Index: ReactiveIndex;
    protectedS3Index: ReactiveIndex;
    urlError: boolean;

    showValidationControls: boolean;
    cachedLogFile: Promise<string> | null;
    cachedResultsFile: Promise<string> | null;
    cachedTrialResultsFiles: Map<string, Promise<string>>;
    cachedTrialPlotCSV: Map<string, Promise<string>>;
    cachedVisulizationFiles: Map<string, LargeZipBinaryObject>;
    cachedTrialTags: Map<string, ReactiveJsonFile>;

    subjectJson: ReactiveJsonFile;
    resultsJson: ReactiveJsonFile;
    customModelFile: ReactiveTextFile;

    socket: RobustMqtt;

    userEmail: string | null;

    cloudProcessingQueue: string[];

    constructor(publicS3Index: ReactiveIndex, protectedS3Index: ReactiveIndex, socket: RobustMqtt) {
        const parsedUrl = this.parseUrlPath(window.location.pathname);

        this.dataPrefix = 'data/';

        this.rawCursor = new ReactiveCursor(parsedUrl.isPublic ? publicS3Index : protectedS3Index, this.dataPrefix + parsedUrl.path);
        this.publicS3Index = publicS3Index;
        this.protectedS3Index = protectedS3Index;
        this.urlError = parsedUrl.error;
        this.urlPath = window.location.pathname;

        this.cachedLogFile = null;
        this.cachedResultsFile = null;
        this.cachedTrialResultsFiles = new Map();
        this.cachedTrialPlotCSV = new Map();
        this.cachedVisulizationFiles = new Map();
        this.cachedTrialTags = new Map();
        this.showValidationControls = false;

        this.subjectJson = this.rawCursor.getJsonFile("_subject.json");
        this.resultsJson = this.rawCursor.getJsonFile("_results.json");
        this.customModelFile = this.rawCursor.getTextFile("unscaled_generic.osim");

        this.socket = socket;

        this.userEmail = null;

        this.cloudProcessingQueue = [];

        makeObservable(this, {
            urlPath: observable,
            dataPrefix: observable,
            urlError: observable,
            showValidationControls: observable,
            userEmail: observable
        });
    }

    /**
     * This gets called after we log in, with the email of the user.
     * 
     * @param email The email of the user
     */
    setUserEmail = (email: string) => {
        this.userEmail = email;
    }

    /**
     * Subscribe to processing details.
     */
    subscribeToCloudProcessingQueueUpdates = () => {
        this.socket.subscribe("/PROC_QUEUE", action((topic, msg) => {
            const msgObj = JSON.parse(msg);
            this.cloudProcessingQueue = msgObj['queue'];
        }));
    }

    /**
     * Get the order of an element in the queue.
     */
    getQueueOrder = (path?: string) => {
        let fullPath = this.protectedS3Index.globalPrefix + this.rawCursor.path;
        if (path != null) {
            fullPath += path;
        }
        if (!fullPath.endsWith('/')) fullPath += '/';
        console.log("Getting queue order for "+fullPath);
        let index = this.cloudProcessingQueue.indexOf(fullPath);
        if (index === -1) {
            return '';
        }
        else {
            return ': '+(index+1)+' ahead';
        }
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

        urlPath = decodeURI(urlPath);

        // 1. Set an error state if the path is empty
        if (urlPath.length === 0) {
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
    setUrlPath = action((urlPath: string) => {
        if (urlPath === this.urlPath) return;
        this.urlPath = urlPath;

        const parsedUrl = this.parseUrlPath(this.urlPath);

        this.urlError = parsedUrl.error;
        this.rawCursor.setIndex(parsedUrl.isPublic ? this.publicS3Index : this.protectedS3Index);
        this.rawCursor.setPath(this.dataPrefix + parsedUrl.path);

        // Subject state
        this.showValidationControls = this.rawCursor.getExists("manually_scaled.osim");

        // Clear the cache when we move to a new url
        this.cachedLogFile = null;
        this.cachedResultsFile = null;
        this.cachedTrialResultsFiles.clear();
        this.cachedTrialPlotCSV.clear();
        this.cachedVisulizationFiles.clear();
        this.cachedTrialTags.forEach((v,k) => {
            this.rawCursor.deleteJsonFile("trials/"+k+"/tags.json");
        });
        this.cachedTrialTags.clear();
    });

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
    deleteFolder = (prefix: string) => {
        return this.rawCursor.deleteByPrefix(prefix).then(() => {
            return this.rawCursor.deleteChild(prefix);
        });
    };

    /**
     * This returns the type of file we're looking at, so that we can choose which viewer to display
     */
    getFileType = () => {
        const hasChildren: boolean = this.rawCursor.hasChildren();
        const exists: boolean = this.rawCursor.getExists();
        const parsedPath = this.parseUrlPath(this.urlPath);
        // Special case: this happens when a user has just created an account, but hasn't uploaded anything yet.
        // If we're in the root of our private folder, even if no files uploaded yet, always treat this as a folder.
        if (!exists && !hasChildren && !parsedPath.isPublic && parsedPath.path === '') {
            return "folder";
        }
        // Otherwise say 404
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

    /**
     * @returns True if the S3 index is currently refreshing
     */
    getIsLoading = () => {
        return this.rawCursor.getIsLoading();
    }

    /**
     * This returns true if there are any active network errors
     */
    hasNetworkErrors = () => {
        return this.rawCursor.hasNetworkErrors();
    };

    /**
     * @returns A list of human-readable strings describing the currently active errors.
     */
    getNetworkErrors = () => {
        return this.rawCursor.getNetworkErrors();
    };

    clearNetworkErrors = () => {
        this.rawCursor.clearNetworkErrors();
    }

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
            this.rawCursor.uploadChild(name + "/_subject.json", JSON.stringify({ email: this.userEmail })).then(() => {
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

    getSubjectStatus = (path: string = '') => {
        if (path !== '' && !path.endsWith('/')) path = path + '/';

        let trials = this.getTrials(path);

        let anyTrialsMissingMarkers = false;
        const hasAnyTrials = trials.length > 0;

        for (let i = 0; i < trials.length; i++) {
            const c3dMetadata = this.rawCursor.getChildMetadata(path + "trials/" + trials[i].key + "/markers.c3d");
            const trcMetadata = this.rawCursor.getChildMetadata(path + "trials/" + trials[i].key + "/markers.trc");
            if (c3dMetadata == null && trcMetadata == null) {
                anyTrialsMissingMarkers = true;
            }
        }

        const hasCustomFlag = this.rawCursor.getExists(path + "CUSTOM_OSIM");
        const hasOsimFile = this.rawCursor.getExists(path + "unscaled_generic.osim");

        const hasReadyToProcessFlag = this.rawCursor.getExists(path + "READY_TO_PROCESS");
        const hasProcessingFlag = this.rawCursor.getExists(path + "PROCESSING");
        const hasErrorFlag = this.rawCursor.getExists(path + "ERROR");

        const logMetadata = this.rawCursor.getChildMetadata(path + "log.txt");
        const resultsMetadata = this.rawCursor.getChildMetadata(path + "_results.json");

        let anyConfigInvalid = false;
        if (path === '') {
            let weightValue = this.subjectJson.getAttribute("massKg", 0.0);
            let heightValue = this.subjectJson.getAttribute("heightM", 0.0);
            let fitDynamics = this.subjectJson.getAttribute("fitDynamics", false);
            let skeletonPreset = this.subjectJson.getAttribute("skeletonPreset", this.hasModelFile() ? "custom" : "vicon");
            let footBodyNames = this.subjectJson.getAttribute("footBodyNames", []);

            if (weightValue < 5 || weightValue > 700) {
                anyConfigInvalid = true;
            }
            if (heightValue < 0.1 || heightValue > 3) {
                anyConfigInvalid = true;
            }
            if (fitDynamics && skeletonPreset === "custom" && footBodyNames.length != 2) {
                anyConfigInvalid = true;
            }
        }

        if (anyTrialsMissingMarkers || anyConfigInvalid || (hasCustomFlag && !hasOsimFile) || !hasAnyTrials) {
            return 'empty';
        }
        else if (logMetadata != null && resultsMetadata != null) {
            return 'done';
        }
        else if (hasErrorFlag) {
            return 'error';
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

    getFolderStatus = (path: string = '') => {
        let status: 'processing' | 'waiting' | 'could-process' | 'error' | 'done' = 'done';

        if (path !== '' && !path.endsWith('/')) path += '/';

        let contents = this.getFolderContents(path);
        for (let i = 0; i < contents.length; i++) {
            let childStatus: 'processing' | 'waiting' | 'could-process' | 'error' | 'done' | 'empty' = 'done';
            if (contents[i].type === 'folder') {
                childStatus = this.getFolderStatus(path + contents[i].key);
            }
            else if (contents[i].type === 'mocap') {
                childStatus = this.getSubjectStatus(path + contents[i].key);
            }

            if (childStatus === 'processing') {
                status = 'processing';
            }
            if (childStatus === 'error' && status !== 'processing') {
                status = 'error';
            }
        }

        return status;
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
     * If this returns true, we should show the validation controls for this subject. The validation
     * controls include the scaled *.osim model, and the *.mot Gold IK files.
     */
    getShowValidationControls = () => {
        // Store "override" to ensure we access both variables before returning
        let override = this.showValidationControls;
        return this.rawCursor.getExists("manually_scaled.osim") || override;
    };

    /**
     * This shows/hides the validation controls. This only has an effect if there aren't already validation 
     * files that have been uploaded.
     * 
     * @param show 
     */
    setShowValidationControls = (show: boolean) => {
        if (this.rawCursor.getExists("manually_scaled.osim")) {
            if (window.confirm("Disabling comparisons will delete the manually scaled OpenSim file. Are you sure you want to do this?")) {
                this.rawCursor.deleteChild("manually_scaled.osim");
            }
            else {
                return;
            }
        }
        this.showValidationControls = show;
    };

    /**
     * This gets the list of the trials under this folder. If we're not pointing to a mocap subject, 
     * then this returns nothing.
     * 
     * @returns A list of all the trials that have been uploaded
     */
    getTrials = (prefix: string = '') => {
        let trials: MocapTrialEntry[] = [];
        let rawFolders = this.rawCursor.getImmediateChildFolders(prefix + "trials/");
        rawFolders.sort((a, b) => {
            return a.key.localeCompare(b.key);
        });
        for (let i = 0; i < rawFolders.length; i++) {
            trials.push({
                ...rawFolders[i]
            });
        }
        return trials;
    };

    /**
     * Creates a new trial folder on the mocap subject.
     */
    createTrial = (name: string) => {
        return this.rawCursor.uploadChild("trials/" + name, "");
    }

    /**
     * This attempts to guess from file names how to group bulk uploaded files into trials,
     * then goes ahead and creates those trials.
     * 
     * @param fileNames The list of file names that have been dragged onto the bulk uploader
     */
    bulkCreateTrials = (fileNames: string[]) => {
        const progress: Promise<void>[] = [];
        for (let i = 0; i < fileNames.length; i++) {
            if (fileNames[i].endsWith(".c3d") || fileNames[i].endsWith(".trc") || fileNames[i].endsWith(".sto")) {
                const file = fileNames[i].substring(0, fileNames[i].length - ".c3d".length);
                progress.push(this.rawCursor.uploadChild("trials/" + file, ""));
            }
        }
        return Promise.all(progress);
    };

    /**
     * This requests that a subject be reprocessed, by deleting the results of previous processing.
     */
    requestReprocessSubject = () => {
        this.rawCursor.deleteChild("log.txt");
        this.rawCursor.deleteChild("_results.json");
        this.rawCursor.deleteChild("PROCESSING");
        this.rawCursor.deleteChild("ERROR");
    };

    /**
     * @param trialName The name of the trial to check
     * @returns true if there's a visualization file for this trial
     */
    hasTrialVisualization = (trialName: string) => {
        return this.rawCursor.getExists('trials/' + trialName + '/preview.bin.zip');
    };

    /**
     * This downloads and unzips the recorded JSON for the preview of the recorded motion
     * 
     * @param trialName The trial name to retrieve
     * @returns a promise for the downloaded and unzipped trial preview
     */
    getTrialVisualization = (trialName: string) => {
        let visualization = this.cachedVisulizationFiles.get(trialName);
        if (visualization == null) {
            visualization = new LargeZipBinaryObject(this.rawCursor, 'trials/' + trialName + '/preview.bin.zip', () => {
                this.cachedVisulizationFiles.delete(trialName);
            });
            this.cachedVisulizationFiles.set(trialName, visualization);
        }
        return visualization;
    };

    /**
     * This either creates or retrieves a JSON file for this trial
     * 
     * @param trialName The trial name to retrieve
     * @returns a promise for the downloaded and unzipped trial preview
     */
    getTrialTagFile = (trialName: string) => {
        let file = this.cachedTrialTags.get(trialName);
        if (file == null) {
            file = this.rawCursor.getJsonFile("trials/" + trialName+ "/tags.json");
            this.cachedTrialTags.set(trialName, file);
        }
        return file;
    };

    /**
     * This downloads and parses the contents of the PROCESSING flag
     */
    getProcessingInfo = () => {
        return this.rawCursor.downloadText("PROCESSING").then((text: string) => {
            let val: MocapProcessingFlags = JSON.parse(text);
            return val;
        })
    };

    /**
     * This gets the PROCESSING info, attaches a PubSub listener, and returns a handle to remove it when we're done.
     * 
     * @param onLogLine the callback when a new line of the log is received
     * @returns an unsubscribe method
     */
    subscribeToLogUpdates = (onLogLine: (line: string) => void) => {
        // Do nothing if we're not PROCESSING
        if (this.getSubjectStatus() !== 'processing') return () => { };
        // Otherwise, attach a log
        console.log("Subscribing to log updates for current subject");
        let logListener: any[] = [() => { }];
        let unsubscribed: boolean[] = [false];
        this.getProcessingInfo().then((procFlagContents) => {
            // Try to avoid race conditions if we already cleaned up
            if (unsubscribed[0]) return;

            logListener[0] = this.socket.subscribe("/LOG/" + procFlagContents.logTopic, (topic, msg) => {
                console.log(msg);
                const logMsg: MocapProcessingLogMsg = JSON.parse(msg);
                if (logMsg.lines) {
                    for (let i = 0; i < logMsg.lines.length; i++) {
                        onLogLine(logMsg.lines[i]);
                    }
                }
            });
        });

        return () => {
            console.log("Cleaning up /LOG/# PubSub for current subject");
            unsubscribed[0] = true;
            logListener[0]();
        }
    };

    /**
     * @returns True if we've got a custom model file, false otherwise
     */
    hasModelFile = () => {
        return this.rawCursor.hasChildren(["unscaled_generic.osim"]);
    }

    /**
     * @returns True if we've got a log file, false otherwise
     */
    hasLogFile = () => {
        return this.rawCursor.hasChildren(["log.txt"]);
    }

    /**
     * Gets the contents of the log.txt for this subject, as a promise
     */
    getLogFileText = () => {
        if (this.cachedLogFile == null) {
            this.cachedLogFile = this.rawCursor.downloadText("log.txt");
        }
        return this.cachedLogFile;
    };

    /**
     * @returns True if we've got a results file, false otherwise
     */
    hasResultsFile = () => {
        return this.rawCursor.hasChildren(["_results.json"]);
    }

    /**
     * Gets the contents of the _results.json for this subject, as a promise
     */
    getResultsFileText = () => {
        if (this.cachedResultsFile == null) {
            console.log("Getting results file");
            this.cachedResultsFile = this.rawCursor.downloadText("_results.json");
        }
        return this.cachedResultsFile;
    };

    /**
     * Gets the contents of the _results.json for this trial, as a promise
     */
    getTrialResultsFileText = (trialName: string) => {
        let promise: Promise<string> | undefined = this.cachedTrialResultsFiles.get(trialName);
        if (promise == null) {
            promise = this.rawCursor.downloadText("trials/" + trialName + "/_results.json");
            this.cachedTrialResultsFiles.set(trialName, promise);
        }
        return promise;
    };

    /**
     * Gets the contents of the _results.json for this trial, as a promise
     */
    getTrialPlotDataCSV = (trialName: string) => {
        let promise: Promise<string> | undefined = this.cachedTrialPlotCSV.get(trialName);
        if (promise == null) {
            promise = this.rawCursor.downloadText("trials/" + trialName + "/plot.csv");
            this.cachedTrialPlotCSV.set(trialName, promise);
        }
        return promise;
    };

    /**
     * This adds the "CUSTOM_OSIM" file on the backend, which marks the trial as using a custom OpenSim model, so that the validation checker can see if you're missing uploaded files.
     */
    markCustomOsim = () => {
        console.log("Marking as a custom osim file");
        return this.rawCursor.uploadChild("CUSTOM_OSIM", "");
    }
    
    /**
     * This removes the "CUSTOM_OSIM" file on the backend, which marks the trial as using a custom OpenSim model, so that the validation checker can see if you're missing uploaded files.
     */
    clearCustomOsim = () => {
        return this.rawCursor.deleteChild("CUSTOM_OSIM");
    }

    /**
     * This adds the "READY_TO_PROCESS" file on the backend, which marks the trial as being fully uploaded, and
     * ready for the backend to pick up and work on.
     */
    markReadyForProcessing = () => {
        let weightValue = this.subjectJson.getAttribute("massKg", 0.0);
        if (weightValue === 0) {
            alert("Cannot process a trial with a subject weight of 0kg");
            return;
        }
        let heightValue = this.subjectJson.getAttribute("heightM", 0.0);
        if (heightValue === 0) {
            alert("Cannot process a trial with a subject height of 0m");
            return;
        }
        this.subjectJson.setAttribute("email", this.userEmail, true);

        if (window.confirm("Processed results will be shared with the community under a CC 3.0 License. Is that ok?")) {
            return this.rawCursor.uploadChild("READY_TO_PROCESS", "");
        }
        else {
            // Do nothing
        }
    };

    /**
     * Returns true if there's a zip archive of the results
     * 
     * @returns 
     */
    hasResultsArchive = () => {
        return this.rawCursor.hasChildren([ this.getCurrentFileName() + ".zip"]);
    };

    /**
     * Download the zip results archive
     */
    downloadResultsArchive = () => {
        this.rawCursor.downloadFile(this.getCurrentFileName() + ".zip");
    };

    /**
     * Download the zip results archive
     */
    downloadTrialResultsCSV = (trialName: string) => {
        this.rawCursor.downloadFile("trials/" + trialName + "/plot.csv");
    };
}

export { LargeZipBinaryObject };
export default MocapS3Cursor;