import { PathData } from "./LiveDirectory";
import LiveFile from "./LiveFile";
import LiveJsonFile from "./LiveJsonFile";
import UserHomeDirectory, { TrialContents } from "./UserHomeDirectory";
import { action, autorun, makeObservable, observable } from "mobx";
import { getOpenSimBodyList } from "./OpenSimUtils";

type SegmentResultsJSON = {
    trialName: string;
    start_frame: number;
    start: number;
    end_frame: number;
    end: number;
    kinematicsStatus: "NOT_STARTED" | "FINISHED" | "ERROR";
    kinematicsAvgRMSE: number;
    kinematicsAvgMax: number;
    dynamicsStatus: "NOT_STARTED" | "FINISHED" | "ERROR";
    dynanimcsAvgRMSE: number;
    dynanimcsAvgMax: number;
    linearResiduals: number;
    angularResiduals: number;
    goldAvgRMSE: number;
    goldAvgMax: number;
    goldPerMarkerRMSE: number | null;
    hasMarkers: boolean;
    hasForces: boolean;
    hasMarkerWarnings: boolean;
};

type TrialResultsJSON = {
    segments: SegmentResultsJSON[]
};

type SubjectResultsJSON = {
    [trialName: string]: TrialResultsJSON
};

/**
 * The SubjectView grew to the point where we needed a separate class to manage its state.
 * 
 * This class currently handles several nasty pieces of stateful or complex logic necessary to 
 * render the SubjectView:
 * - The "Drop files here to upload" zone
 * - The way the subject view knows to autocomplete the available bodies in your OpenSim model
 * - The loading of the JSON results file
 */
class SubjectViewState {
    home: UserHomeDirectory;
    path: string;
    loading: boolean;

    wizardCollapsed: boolean = false;

    name: string;
    subjectJson: LiveJsonFile;

    resultsExist: boolean;
    resultsJsonPath: string;
    resultsOsimZipPath: string;
    resultsB3dPath: string;
    processingFlagFile: LiveFile; // "PROCESSING"
    readyFlagFile: LiveFile; // "READY_TO_PROCESS"
    errorFlagFile: LiveFile; // "ERROR"
    slurmFlagFile: LiveFile; // "SLURM"

    customOpensimModel: LiveFile;
    loadedOpensimModelFirstTime: boolean = false;
    loadingOpenSimModelPromise: Promise<void> | null = null;
    availableBodyNodes: string[];

    trials: TrialContents[];
    uploadedTrialPaths: Map<string, string> = new Map();

    loadedResultsJsonFirstTime: boolean = false;
    loadingResultsJsonPromise: Promise<void> | null = null;
    parsedResultsJson: SubjectResultsJSON = {};

    // This counts the number of times our autorun function has been called. This is mostly here for testing purposes.
    reloadCount: number = 0;

    constructor(home: UserHomeDirectory, path: string) {
        this.home = home;
        const dir = home.dir;

        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }
        this.path = path;

        this.name = '';
        if (path.includes('/')) {
            this.name = path.split('/').slice(-1)[0];
        }
        else {
            this.name = path;
        }

        this.subjectJson = dir.getJsonFile(path + '/_subject.json');
        this.resultsJsonPath = path + '/_results.json';
        this.resultsOsimZipPath = path + '/' + this.name + '.zip';
        this.resultsB3dPath = path + '/' + this.name + '.b3d';
        this.processingFlagFile = dir.getLiveFile(path + "/PROCESSING");
        this.readyFlagFile = dir.getLiveFile(path + "/READY_TO_PROCESS");
        this.errorFlagFile = dir.getLiveFile(path + "/ERROR");
        this.slurmFlagFile = dir.getLiveFile(path + "/SLURM");

        this.customOpensimModel = dir.getLiveFile(path + "/unscaled_generic.osim");
        this.availableBodyNodes = [];

        this.loading = true;
        this.resultsExist = false;
        this.trials = [];

        this.reloadState = this.reloadState.bind(this);
        this.dropOpensimFile = this.dropOpensimFile.bind(this);
        this.dropMarkerFiles = this.dropMarkerFiles.bind(this);
        this.dropGRFFiles = this.dropGRFFiles.bind(this);
        this.dropFilesToUpload = this.dropFilesToUpload.bind(this);
        this.submitForProcessing = this.submitForProcessing.bind(this);

        makeObservable(this, {
            name: observable,
            path: observable,
            loading: observable,
            wizardCollapsed: observable,
            resultsExist: observable,
            availableBodyNodes: observable,
            trials: observable,
            parsedResultsJson: observable,
            reloadCount: observable,
            uploadedTrialPaths: observable,
            dropOpensimFile: action,
            dropFilesToUpload: action,
            dropMarkerFiles: action,
            dropGRFFiles: action,
            deleteTrial: action,
            submitForProcessing: action,
        });

        // Automatically reload the state whenever the underlying directories change
        autorun(() => {
            this.reloadState();
        });

        // TODO: Load the OpenSim file someplace
        /*
        if (!customOpensimModelLiveFile.loading && customOpensimModelLiveFile.exists) {
            home.dir.downloadText(customOpensimModelLiveFile.path).then((openSimText) => {
                setAvailableBodyList(getOpenSimBodyList(openSimText));
            }).catch((e) => {
                console.error("Error downloading OpenSim model text from " + customOpensimModelLiveFile.path + ": ", e);
            });
        }
        */

        // TODO: Load the results JSON someplace
        /*
        home.dir.downloadText(path + "/_results.json").then((resultsText) => {
            setParsedResultsJSON(JSON.parse(resultsText));
        }).catch((e) => {
            console.error("Error downloading _results.json from " + path + ": ", e);
        });
        */
    }

    /**
     * This function recomputes the state from the current state of the UserHomeDirectory.
     */
    reloadState() {
        const subjectPathData: PathData = this.home.dir.getPath(this.path, false);
        const trialsPathData: PathData = this.home.dir.getPath(this.path+'/trials/', true);
        // Do nothing, just touch all the entries outside the action() call to get MobX to re-render when this changes
        this.uploadedTrialPaths.forEach((name, path) => {});

        // If the OpenSim model exists on the server, and we haven't loaded it yet, then load it
        if (!this.loadedOpensimModelFirstTime) {
            if (!this.customOpensimModel.loading && this.customOpensimModel.exists) {
                this.loadedOpensimModelFirstTime = true;

                this.loadingOpenSimModelPromise = this.home.dir.downloadText(this.customOpensimModel.path).then(action((openSimText) => {
                    this.availableBodyNodes = getOpenSimBodyList(openSimText);
                    this.loadingOpenSimModelPromise = null;
                })).catch((e) => {
                    console.error("Error downloading OpenSim model text from " + this.customOpensimModel.path + ": ", e);
                });
            }
        }

        // If the results file exists on the server, and we haven't loaded it yet, then load it
        const resultsExist = subjectPathData.files.map((file) => {
            return file.key;
        }).includes(this.resultsJsonPath);
        if (!this.loadedResultsJsonFirstTime) {
            if (resultsExist) {
                this.loadedResultsJsonFirstTime = true;
                this.loadingResultsJsonPromise = this.home.dir.downloadText(this.path + "/_results.json").then(action((resultsText) => {
                    try {
                        const reviver = (key: string, value: any) => {
                            if (typeof value === 'string') {
                                switch (value) {
                                    case 'NaN':
                                        return NaN;
                                    case 'Infinity':
                                        return Infinity;
                                    case '-Infinity':
                                        return -Infinity;
                                    default:
                                        return value;
                                }
                            }
                            return value;
                        };
                        const preprocessJson = (jsonString: string): string => {
                            return jsonString
                                .replace(/(:\s*)NaN(\s*[,}])/g, '$1"NaN"$2')
                                .replace(/(:\s*)Infinity(\s*[,}])/g, '$1"Infinity"$2')
                                .replace(/(:\s*)-Infinity(\s*[,}])/g, '$1"-Infinity"$2');
                        };
                        const resultsTextProcessed = preprocessJson(resultsText);
                        const results: SubjectResultsJSON = JSON.parse(resultsTextProcessed, reviver);
                        this.parsedResultsJson = results;
                    }
                    catch (e) {
                        console.error("Bad JSON format for file \"" + this.path + "/_results.json\", got: \"" + resultsText + "\"");
                    }
                })).catch((e) => {
                    console.error("Error downloading _results.json from " + this.path + '/_results.json' + ": ", e);
                });
            }
        }

        // Edit the observable state in a single transaction, so that we only trigger a single re-render
        action(() => {
            this.reloadCount++;
            this.loading = trialsPathData.loading || subjectPathData.loading;
            this.resultsExist = resultsExist;

            const trialPaths = trialsPathData.folders.map((folder) => {
                if (folder.endsWith('/')) {
                    return folder.substring(0, folder.length-1);
                }
                return folder;
            });
            const overrideFileType = trialPaths.map((path) => '');
            this.uploadedTrialPaths.forEach((name, path) => {
                if (!trialPaths.includes(path)) {
                    trialPaths.push(path);
                    overrideFileType.push(name.split('.').slice(-1)[0]);
                }
            });

            this.trials = trialPaths.map((folder) => this.home.getTrialContents(folder));
            for (let i = 0; i < this.trials.length; i++) {
                if (overrideFileType[i].toLocaleLowerCase() === 'c3d') {
                    this.trials[i].c3dFileExists = true;
                }
                if (overrideFileType[i].toLocaleLowerCase() === 'trc') {
                    this.trials[i].trcFileExists = true;
                }
            }
        })();
    }

    /**
     * This file uploads a grf file to the server, if you drop a single one. If you drop in bulk, it attempts to match by name with the other trials.
     */
    dropOpensimFile(files: File[]): Promise<void> {
        if (files.length === 1) {
            const file = files[0];
            if (file.name.endsWith('.osim')) {
                this.loadedOpensimModelFirstTime = true;

                const uploadPromise = this.customOpensimModel.uploadFile(file);

                // Read the text of `file` locally
                const localPromise = new Promise<void>((resolve, reject) => {
                    const reader = new FileReader();
                    reader.onload = (event) => {
                        const text = (event.target?.result as string);
                        const availableBodyNodes = getOpenSimBodyList(text);
                        action(() => {
                            this.availableBodyNodes = availableBodyNodes;
                            resolve();
                        })();
                    };

                    reader.onerror = action((event) => {
                        console.log("Local OpenSim model file could not be read:", event.target?.error?.message);
                        reject(event);
                    });

                    reader.readAsText(file);
                });

                return Promise.all([uploadPromise, localPromise]).then(() => {});
            }
            else {
                return Promise.reject("Unsupported OpenSim file type");
            }
        }
        else {
            return Promise.reject("Don't support multiple files for a drop");
        }
    };

    /**
     * This function is called when the user drops files onto the "Drop files here to upload" zone.
     * 
     * @param files A list of files that just landed on the "Drop files here to upload" zone
     */
    dropFilesToUpload(files: File[]): Promise<void> {
        let markerFiles: Map<string, File> = new Map();
        let grfFiles: Map<string, File> = new Map();
        for (let i = 0; i < files.length; i++) {
            const name = files[i].name.split('.')[0];
            if (files[i].name.endsWith('.mot')) {
                grfFiles.set(name, files[i]);
            }
            else if (files[i].name.endsWith('.trc') || files[i].name.endsWith('.c3d')) {
                markerFiles.set(name, files[i]);
            }
        }

        // De-duplicate trialNames
        const trialNames: string[] = [...new Set([...markerFiles.keys(), ...grfFiles.keys()])];

        // Ensure all the trialPaths are in this.uploadedTrialPaths
        for (let name of trialNames) {
            this.uploadedTrialPaths.set(this.path + '/trials/' + name, markerFiles.get(name)?.name ?? '');
        }

        return Promise.all(trialNames.map((name) => {
            return this.home.createTrial(this.path, name, markerFiles.get(name), grfFiles.get(name));
        })).then(() => {});
    }

    /**
     * This gets the appropriate LiveFile to show for a given trial's marker file.
     */
    getLiveFileForTrialMarkers(trial: TrialContents): LiveFile {
        if (trial.c3dFileExists) {
            return this.home.dir.getLiveFile(trial.c3dFilePath);
        }
        else if (trial.trcFileExists) {
            return this.home.dir.getLiveFile(trial.trcFilePath);
        }
        // By default, return the C3D, though it doesn't matter because neither one exists
        return this.home.dir.getLiveFile(trial.c3dFilePath);
    }

    /**
     * @param trial The trial to delete
     */
    deleteTrial(trial: TrialContents): Promise<void> {
        let path = trial.path;
        if (path.endsWith('/')) {
            path = path.substring(0, path.length-1);
        }
        this.uploadedTrialPaths.delete(path);
        return this.home.dir.deleteByPrefix(path);
    }

    /**
     * This file uploads a marker file to the server, and potentially deletes the old marker file, if the type has changed.
     */
    dropMarkerFiles(trial: TrialContents, files: File[]): Promise<void> {
        if (files.length === 1) {
            const file = files[0];
            if (file.name.endsWith('.c3d')) {
                return this.home.dir.getLiveFile(trial.c3dFilePath, true).uploadFile(file).then(() => {
                    // Delete the old TRC file, if there is one
                    if (trial.trcFileExists) {
                        return this.home.dir.delete(trial.trcFilePath);
                    }
                    else {
                        return Promise.resolve();
                    }
                });
            }
            else if (file.name.endsWith('.trc')) {
                return this.home.dir.getLiveFile(trial.trcFilePath, true).uploadFile(file).then(() => {
                    // Delete the old C3D file, if there is one
                    if (trial.c3dFileExists) {
                        return this.home.dir.delete(trial.c3dFilePath);
                    }
                    else {
                        return Promise.resolve();
                    }
                });
            }
            else {
                return Promise.reject("Unsupported marker file type");
            }
        }
        else {
            return Promise.reject("Don't support multiple files for a drop");
        }
    };

    /**
     * This file uploads a grf file to the server, if you drop a single one. If you drop in bulk, it attempts to match by name with the other trials.
     */
    dropGRFFiles(trial: TrialContents, files: File[]): Promise<void> {
        if (files.length === 1) {
            const file = files[0];
            if (file.name.endsWith('.mot')) {
                return this.home.dir.getLiveFile(trial.grfMotFilePath).uploadFile(file);
            }
            else {
                return Promise.reject("Unsupported GRF file type");
            }
        }
        else {
            return Promise.reject("Don't support multiple files for a drop");
        }
    };

    submitForProcessing(): Promise<void> {
        return this.readyFlagFile.uploadFlag().then(() => {
            this.wizardCollapsed = true;
        });
    }

    reprocess(): Promise<void> {
        return this.errorFlagFile.delete().then(() => {
            return this.slurmFlagFile.delete().then(() => {
                return this.processingFlagFile.delete().then(() => {
                    return this.home.dir.delete(this.resultsJsonPath).then(action(() => {
                        this.parsedResultsJson = {};
                        this.loadingResultsJsonPromise = null;
                        this.loadedResultsJsonFirstTime = false;
                    }));
                });
            });
        });
    }
};

export type { SubjectResultsJSON, TrialResultsJSON, SegmentResultsJSON };
export default SubjectViewState;