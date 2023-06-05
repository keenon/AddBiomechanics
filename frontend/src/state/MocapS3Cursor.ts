import { ReactiveCursor, ReactiveIndex, ReactiveJsonFile, ReactiveTextFile } from "./ReactiveS3";
import { makeObservable, observable, action } from 'mobx';
import { Auth } from "aws-amplify";
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

type ProcessingServerStatus = {
    currently_processing: string;
    job_queue: string[];
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

type Dataset = {
    key: string;
    href: string;
    userId: string;
    numSubjects: number;
    numTrials: number;
    isHomeFolder: boolean
    isPublished: boolean;
    hasDynamics: boolean;
};

class MocapDatasetIndex {
    s3Index: ReactiveIndex;
    datasets: Dataset[];

    constructor(s3Index: ReactiveIndex) {
        this.s3Index = s3Index;
        this.datasets = [];
        this.s3Index.addLoadingListener((loading: boolean) => {
            if (!loading) {
                this.reindexDatasets();
            }
        });

        this.s3Index.addChangeListener(() => {
            this.reindexDatasets();
        });

        this.reindexDatasets();

        makeObservable(this, {
            datasets: observable,
            searchDatasets: observable,
            datasetsByUserId: observable
        });
    }

    reindexDatasets = action(() => {
        if (this.s3Index.getIsLoading()) return;

        // Get a list of all the subject names, with trial counts appended, in O(n)
        const subjectTrialCount: Map<string, number> = new Map();
        this.s3Index.files.forEach((rawFile, key) => {
            if (key.startsWith("private")) {
                return;
            }
            if (key.endsWith("_subject.json")) {
                subjectTrialCount.set(key.substring(0, key.length - "/_subject.json".length) + '/trials', 0);
            }
        });
        const trialNamesTaken: Map<string, boolean> = new Map();
        this.s3Index.files.forEach((rawFile, key) => {
            if (key.startsWith("private")) {
                return;
            }
            const trialIndex = key.indexOf("/trials");
            if (trialIndex != -1) {
                const trialSubstring = key.substring(0, trialIndex + "/trials".length);
                const trialTail = key.substring(trialIndex + "/trials/".length);
                const trialName = trialSubstring + '/' + trialTail.split("/")[0]
                if (!trialNamesTaken.has(trialName)) {
                    trialNamesTaken.set(trialName, true);
                    if (subjectTrialCount.has(trialSubstring)) {
                        subjectTrialCount.set(trialSubstring, (subjectTrialCount.get(trialSubstring) ?? 0) + 1);
                    }
                }
            }
        });

        const datasetMap: Map<string, Dataset> = new Map();

        // Break down the subjects into datasets, in O(n)
        subjectTrialCount.forEach((trialCount: number, subjectTrialPath: string) => {
            const subjectPath = subjectTrialPath.substring(0, subjectTrialPath.length - "/trials".length);
            const parts = subjectPath.split("/");
            // assert(parts[0] === "protected");
            const regionAndUserId = parts[1];
            // assert(parts[2] === "data");
            const userId = regionAndUserId.split(":")[1];
            const subjectName = parts[parts.length - 1];

            const physicsBinName = subjectPath + '/' + subjectName + '.bin';
            const hasPhysics = this.s3Index.files.has(physicsBinName);

            let path = '';
            for (let i = 2; i < parts.length - 1; i++) {
                if (i == 2) {
                }
                else {
                    path += parts[i] + '/';
                }
                const key = 'protected/' + regionAndUserId + '/data/' + path;

                let dataset = datasetMap.get(key);
                if (dataset == null) {
                    dataset = {
                        key: key,
                        href: '/data/' + userId + '/' + path,
                        userId,
                        numSubjects: 0,
                        numTrials: 0,
                        isPublished: false,
                        hasDynamics: hasPhysics,
                        isHomeFolder: i == 2
                    };
                    datasetMap.set(key, dataset);
                }
                dataset.numSubjects ++;
                dataset.numTrials += trialCount;
                if (hasPhysics) {
                    dataset.hasDynamics = true;
                }
                datasetMap.set(key, dataset);
            }
        });

        // Go through and find empty datasets
        this.s3Index.files.forEach((rawFile, key) => {
            if (key.startsWith("private")) {
                return;
            }
            if (key.indexOf("_SEARCH") !== -1) {
                const filteredKey = key.replaceAll("_SEARCH", "");

                const parts = filteredKey.split("/");
                // assert(parts[0] === "protected");
                const regionAndUserId = parts[1];
                // assert(parts[2] === "data");
                const userId = regionAndUserId.split(":")[1];
                const path = parts.slice(3).join("/");
                const isHomeFolder = path === '';

                if (!datasetMap.has(filteredKey)) {
                    const dataset: Dataset = {
                        key: key,
                        href: '/data/' + userId + '/' + path + '/',
                        userId,
                        isHomeFolder,
                        numSubjects: 0,
                        numTrials: 0,
                        isPublished: true,
                        hasDynamics: false
                    };
                    datasetMap.set(filteredKey, dataset);
                }
            }
        });

        let datasets: Dataset[] = [];
        // Look for published datasets, in O(n)
        datasetMap.forEach((dataset, path) => {
            if (this.s3Index.files.has(dataset.key + '_SEARCH')) {
                dataset.isPublished = true;
            }
            datasets.push(dataset);
        });

        datasets.sort((a, b) => {
            if (b.isHomeFolder && !a.isHomeFolder) {
                return -1;
            }
            if (!b.isHomeFolder && a.isHomeFolder) {
                return 1;
            }
            return b.numTrials - a.numTrials;
        })

        this.datasets = datasets;
    });

    datasetsByUserId = (userId: string, includeUnpublished: boolean = false) => {
        return this.datasets.filter(dataset => {
            if (!dataset.isPublished && !includeUnpublished) return false;
            return dataset.userId === userId;
        });
    }

    searchDatasets = (query: string, dynamicsOnly: boolean, includeUnpublished: boolean = false) => {
        return this.datasets.filter(dataset => {
            if (!dataset.isPublished && !includeUnpublished) return false;
            if (!dataset.hasDynamics && dynamicsOnly) return false;
            if (query.length > 0) {
                if (dataset.key.toLowerCase().indexOf(query.toLowerCase()) !== -1) {
                    return true;
                }

                // TODO: we'll want to add a better variant of this for searching over home folders, 
                // once we have a more efficient way to get user's full names without downloading 
                // everyone's profile.json. Don't forget to update the text on the SearchView tooltip 
                // for title keyword search once this is supported!

                // if ("home folder".indexOf(query.toLowerCase()) !== -1 && dataset.isHomeFolder) {
                //     return true;
                // }

                return false;
            }
            return true;
        });
    };
}

class MocapS3Cursor {
    dataPrefix: string;
    rawCursor: ReactiveCursor;
    s3Index: ReactiveIndex;
    datasetIndex: MocapDatasetIndex;

    region: string;

    showValidationControls: boolean;
    cachedLogFile: Promise<string> | null;
    cachedResultsFile: Promise<string> | null;
    cachedTrialResultsFiles: Map<string, Promise<string>>;
    cachedTrialPlotCSV: Map<string, Promise<string>>;
    cachedVisulizationFiles: Map<string, LargeZipBinaryObject>;
    cachedTrialTags: Map<string, ReactiveJsonFile>;

    subjectJson: ReactiveJsonFile;
    resultsJson: ReactiveJsonFile;
    searchJson: ReactiveJsonFile;
    myProfileJson: ReactiveJsonFile;
    customModelFile: ReactiveTextFile;

    socket: RobustMqtt;

    userEmail: string | null;

    processingServers: Map<string, ProcessingServerStatus>;
    processingServersLastUpdatedTimestamp: Map<string, number>;
    lastSeenPong: Map<string, number>;

    constructor(s3Index: ReactiveIndex, socket: RobustMqtt) {
        this.dataPrefix = '';

        this.region = 'us-west-2';
        this.rawCursor = new ReactiveCursor(s3Index, 'protected/'+this.region+":"+s3Index.myIdentityId);
        this.s3Index = s3Index;
        this.datasetIndex = new MocapDatasetIndex(s3Index);

        this.cachedLogFile = null;
        this.cachedResultsFile = null;
        this.cachedTrialResultsFiles = new Map();
        this.cachedTrialPlotCSV = new Map();
        this.cachedVisulizationFiles = new Map();
        this.cachedTrialTags = new Map();
        this.showValidationControls = false;

        this.subjectJson = this.rawCursor.getJsonFile("_subject.json");
        this.resultsJson = this.rawCursor.getJsonFile("_results.json");
        this.searchJson = this.rawCursor.getJsonFile("_search.json");
        this.myProfileJson = this.rawCursor.getJsonFile('protected/'+this.region+":"+s3Index.myIdentityId+"/profile.json", true);
        this.customModelFile = this.rawCursor.getTextFile("unscaled_generic.osim");

        this.socket = socket;

        this.userEmail = null;

        this.processingServers = new Map();
        this.processingServersLastUpdatedTimestamp = new Map();
        this.lastSeenPong = new Map();

        Auth.currentCredentials().then(action((credentials) => {
            this.myProfileJson.setGlobalPath('protected/'+this.region+":"+s3Index.myIdentityId+"/profile.json");
        }))

        this.s3Index.addChildrenListener("protected/server_status/", this.updateProcessingServerFiles);
        this.updateProcessingServerFiles();

        makeObservable(this, {
            dataPrefix: observable,
            showValidationControls: observable,
            userEmail: observable,
            processingServers: observable,
            lastSeenPong: observable,
            getFullName: observable,
            getOtherProfileFullName: observable
        });
    }

    getFullName = () => {
        let name:string = this.myProfileJson.getAttribute("name", "");
        let surname:string = this.myProfileJson.getAttribute("surname", "");
        if (this.myProfileJson.loading) {
            return "(Loading...)";
        }
        else if (name !== "" && surname !== "") {
            return name + " " + surname;
        }
        else if  (name === "" && surname !== "") {
            return surname;
        }
        else if (name !== "" && surname === "") {
            return name;
        }
        else {
            return "";
        }
    }

    getOtherProfileJson = (userId: string) => {
        console.log('Get profile JSON for user '+userId);
        return this.rawCursor.getJsonFile('protected/'+this.region+":"+userId+"/profile.json", true);
    };

    getOtherProfileFullName = (userId: string) => {
        if (userId === this.s3Index.myIdentityId) {
            return this.getFullName();
        }
        console.log('Get full name for user '+userId);
        const otherProfileJson = this.getOtherProfileJson(userId);
        if (otherProfileJson.loading) {
            return "(Loading...)";
        }
        let name:string = otherProfileJson.getAttribute("name", "");
        let surname:string = otherProfileJson.getAttribute("surname", "");
        if (name !== "" && surname !== "") {
            return name + " " + surname;
        }
        else if  (name === "" && surname !== "") {
            return surname;
        }
        else if (name !== "" && surname === "") {
            return name;
        }
        else {
            console.log("Returning No Profile!");
            return "(No Profile - " + userId.substring(0, 6)+")";
        }
    }

    getDatasetSearchJson = (filteredPath: string) => {
        return this.rawCursor.getJsonFile('protected/'+this.region+":"+filteredPath+'/_search.json', true);
    };

    /**
     * This gets called after we log in, with the email of the user.
     * 
     * @param email The email of the user
     */
    userLoggedIn = (email: string) => {
        this.userEmail = email;
        this.myProfileJson.setGlobalPath('protected/'+this.region+":"+this.s3Index.myIdentityId+"/profile.json");
    }

    /**
     * Subscribe to processing details.
     */
    subscribeToCloudProcessingServerPongs = () => {
        this.socket.subscribe("/PONG/#", action((topic, msg) => {
            const serverName = topic.replace("/PONG/", "").replace("/DEV", "").replace("/PROD", "");
            console.log("Got pong from "+serverName);
            this.lastSeenPong.set(serverName, new Date().getTime());
        }));
    }

    /**
     * Send a ping to a server.
     */
    pingServer = (key: string) => {
        this.socket.publish("/PING/"+key, "{}");
    };

    /**
     * Send out pings to all servers.
     */
    pingAllServers = () => {
        this.processingServers.forEach((v,k) => {
            this.pingServer(k);
        });
    };

    updateProcessingServerFiles = action(() => {
        // Get the list of current server statuses, and pull any necessary JSON files
        const currentServerFiles = this.s3Index.getChildren("protected/server_status/");
        currentServerFiles.forEach((v,k) => {
            const timestamp = v.lastModified.getTime();
            const lastUpdatedTimestamp = this.processingServersLastUpdatedTimestamp.get(k);
            if (lastUpdatedTimestamp !== timestamp) {
                console.log("Downloading status file for: "+k);
                this.processingServersLastUpdatedTimestamp.set(k, timestamp);
                this.s3Index.downloadText(v.key).then(action((text: string) => {
                    console.log("Got status file for "+k+": "+text);
                    try {
                        const result: ProcessingServerStatus = JSON.parse(text);
                        this.processingServers.set(k, result);
                    }
                    catch (e) {
                        console.error("Failed to parse status file for processing server "+k+": "+text);
                    }
                })).catch((e) => {
                    console.warn("Failed to download status file for processing server "+k);
                });
            }
        });

        // Clean up any files that have gone away
        let toRemove: string[] = [];
        this.processingServers.forEach((v,k) => {
            console.log("Checking key: "+k);
            console.log("Comparing to dict: ", [...currentServerFiles.keys()]);

            if (!currentServerFiles.has(k)) {
                console.log("Processing server "+k+" seems to have disappeared. Removing it.");
                toRemove.push(k);
            }
        });
        toRemove.forEach((k) => {
            this.processingServers.delete(k);
        });
    });

    /**
     * Get the order of an element in the queue.
     */
    getQueueOrder = (path?: string) => {
        return 'TODO';
        /*
        let fullPath = this.s3Index.globalPrefix + this.rawCursor.path;
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
        */
    }

    /**
     * This is a convenience method to return the current file path (not including the "my_data" / "public_data" part at the beginning)
     */
    getCurrentFilePath = () => {
        return this.rawCursor.path;
    };

    /**
     * @returns The name of the folder we're currently in
     */
    getCurrentFileName = () => {
        const parts = this.getCurrentFilePath().split('/');
        if (parts.length === 0) return '';
        else return parts[parts.length - 1];
    };

    setDataPath = action((dataPath: string) => {
        if (this.rawCursor.path === dataPath) return;

        console.log("Setting data path to: "+dataPath);
        this.rawCursor.setPath(dataPath);

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
        const isReadonly = this.s3Index.myIdentityId === '' || this.rawCursor.path.indexOf(this.s3Index.myIdentityId) === -1;
        return isReadonly;
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
        const parts = this.rawCursor.path.split('/');
        while (parts.length > 0 && parts[parts.length - 1] === '') {
            parts.splice(parts.length-1, 1);
        }
        const hasChildren: boolean = this.rawCursor.hasChildren();
        const exists: boolean = this.rawCursor.getExists();
        // Special case: this happens when a user has just created an account, but hasn't uploaded anything yet.
        // If we're in the root of our private folder, even if no files uploaded yet, always treat this as a folder.
        const id = parts[1].replace(this.region+":", "");
        if (!exists && !hasChildren && parts.length === 3 && id === this.s3Index.myIdentityId && parts[2] === 'data') {
            return "folder";
        }
        // Otherwise say 404
        if (!exists && !hasChildren) {
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
        const hasSlurmFlag = this.rawCursor.getExists(path + "SLURM");
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
        else if (hasSlurmFlag) {
            return 'slurm';
        }
        else if (hasReadyToProcessFlag) {
            return 'waiting';
        }
        else {
            return 'could-process';
        }
    };

    getFolderStatus = (path: string = '') => {
        // TODO
        return 'done';

        let status: 'processing' | 'waiting' | 'could-process' | 'error' | 'done' = 'done';

        if (path !== '' && !path.endsWith('/')) path += '/';

        let contents = this.getFolderContents(path);
        for (let i = 0; i < contents.length; i++) {
            let childStatus: 'processing' | 'slurm' | 'waiting' | 'could-process' | 'error' | 'done' | 'empty' = 'done';
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

        let hrefPrefix = '';
        const pathParts = this.rawCursor.path.split('/');
        while (pathParts.length > 0 && pathParts[pathParts.length-1] === '') {
            pathParts.splice(pathParts.length-1, 1);
        }
        if (pathParts[0] === 'private') {
            hrefPrefix = '/data/private/';
        }
        else if (pathParts[0] === 'protected' && pathParts.length > 0) {
            hrefPrefix = '/data/' + encodeURIComponent(pathParts[1].replace("us-west-2:", "")) + '/';
        }
        else {
            console.error("Unsupported S3 path: "+this.rawCursor.path);
            return [];
        }
        if (pathParts.length > 3) {
            hrefPrefix += pathParts.slice(3).join('/') + '/';
        }

        for (let i = 0; i < rawFolders.length; i++) {
            if (rawFolders[i].key.indexOf("_SEARCH") !== -1 || rawFolders[i].key.indexOf("_search.json") !== -1) continue;

            let type: 'folder' | 'mocap' = 'folder';
            if (this.rawCursor.childHasChildren(rawFolders[i].key, ['trials/', '_subject.json'])) {
                type = 'mocap';
            }
            const href: string = hrefPrefix + encodeURIComponent(rawFolders[i].key);

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
        this.rawCursor.deleteChild("SLURM");
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
     * Returns true if the current folder is publicly searchable
     */
    isSearchable = () => {
        return this.rawCursor.hasChildren(["_SEARCH"]);
    }

    /**
     * Returns the path to the parent folder that is searchable, if one exists. Otherwise returns false.
     */
    isChildOfSearchable = () => {
        let path = this.rawCursor.path;
        if (path.endsWith("/")) {
            path = path.substring(0, path.length - 1);
        }
        const parts = path.split("/");
        for (let i = 0; i < parts.length; i++) {
            const subPath = parts.slice(0, i).join("/");
            console.log("Checking " + subPath + " for _SEARCH");
            if (this.rawCursor.index.getMetadata(subPath + '/_SEARCH') != null) {
                return subPath.split(":")[1];
            }
        }
        return false;
    }

    /**
     * This marks a folder as searchable
     */
    markSearchable = () => {
        return this.rawCursor.uploadChild("_SEARCH", "");
    }

    /**
     * This marks a folder as not searchable
     */
    markNotSearchable = () => {
        return this.rawCursor.deleteChild("_SEARCH");
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

        if (this.rawCursor.path.indexOf("private") !== -1) {
            if (window.confirm("Processed results will remain private, but we ask that you get approval to share your data as quickly as possible. Do you agree to make a good faith effort to share your data with the community in a timely manner?")) {
                return this.rawCursor.uploadChild("READY_TO_PROCESS", "");
            }
            else {
                // Do nothing
            }
        }
        else {
            if (window.confirm("Processed results will be shared with the community under a CC 3.0 License. Is that ok?")) {
                return this.rawCursor.uploadChild("READY_TO_PROCESS", "");
            }
            else {
                // Do nothing
            }
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
     * Returns true if there's a zip archive of the results
     * 
     * @returns 
     */
    hasSubjectOnDisk = () => {
        return this.rawCursor.hasChildren([ this.getCurrentFileName() + ".bin"]);
    };

    /**
     * Download the zip results archive
     */
    downloadSubjectOnDisk = () => {
        this.rawCursor.downloadFile(this.getCurrentFileName() + ".bin");
    };

    /**
     * Download the zip results archive
     */
    downloadTrialResultsCSV = (trialName: string) => {
        this.rawCursor.downloadFile("trials/" + trialName + "/plot.csv");
    };
}

export { LargeZipBinaryObject, MocapDatasetIndex, type Dataset };
export default MocapS3Cursor;