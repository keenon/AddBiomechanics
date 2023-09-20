import LiveDirectory from "./LiveDirectory";
import { makeObservable, observable, action } from "mobx";
import { PathData } from "./LiveDirectory";

/// This is a cacheing layer for mobx-style interaction with JSON files stored in S3. This handles doing the downloading, parsing, 
/// and re-uploading in the background.
class LiveJsonFile {
    dir: LiveDirectory;
    loading: Promise<void> | null;
    path: string;
    values: Map<string, any>;
    focused: Map<string, boolean>;
    lastUploadedValues: Map<string, any>;
    pendingTimeout: any | null;

    constructor(dir: LiveDirectory, path: string) {
        this.dir = dir;
        this.loading = null;
        this.path = path;
        this.values = new Map();
        this.focused = new Map();
        this.lastUploadedValues = new Map();
        this.pendingTimeout = null;

        this.refreshFile = this.refreshFile.bind(this);
        this.isLoadingFirstTime = this.isLoadingFirstTime.bind(this);
        this.onFocusAttribute = this.onFocusAttribute.bind(this);
        this.onBlurAttribute = this.onBlurAttribute.bind(this);
        this.getAttribute = this.getAttribute.bind(this);
        this.uploadNow = this.uploadNow.bind(this);
        this.setAttribute = this.setAttribute.bind(this);
        this.restartUploadTimer = this.restartUploadTimer.bind(this);

        makeObservable(this, {
            loading: observable,
            values: observable,
            path: observable,
            getAttribute: observable,
            refreshFile: action,
            setAttribute: action
        });

        dir.addPathChangeListener(path, action((pathData: PathData) => {
            if (pathData.files.length > 0) {
                this.refreshFile();
            }
            else {
                this.values.clear();
            }
        }));

        this.refreshFile();
    }

    /**
     * This will do a refresh of the contents of the file from S3
     */
    refreshFile() {
        this.loading = this.dir.downloadText(this.path).then(action((text: string) => {
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
        })).catch(action(() => {
            // File does not exist, so assume it's empty and hasn't yet been created
            this.values.clear();
        })).finally(action(() => {
            this.loading = null;
        }));
    }

    /**
     * @returns True if we're loading the file AND have no contents cached. False otherwise.
     */
    isLoadingFirstTime(): boolean {
        return this.loading != null && this.values.size === 0;
    }

    /**
     * When we have an input entry that we focus on, we don't want to auto-update that from the network, cause it feels like a bug.
     */
    onFocusAttribute(key: string): void {
        this.focused.set(key, true);
    }

    /**
     * When we have an input entry that we stop focusing on, we want to resume auto-updating that from the network.
     */
    onBlurAttribute(key: string): void {
        this.focused.set(key, false);
    }

    /**
     * @param key The key we want to retrieve
     * @param defaultValue A default value to return, if the value hasn't loaded yet or the file doesn't exist
     * @returns 
     */
    getAttribute(key: string, defaultValue: any): any {
        let value = this.values.get(key);
        if (value == null) return defaultValue;
        else return value;
    };

    /**
     * This uploads the contents of this file to S3
     * 
     * @returns A promise for when the upload is complete
     */
    uploadNow(): Promise<void> {
        clearTimeout(this.pendingTimeout);
        let object: any = {};
        this.values.forEach((v, k) => {
            object[k] = v;
        });
        let json = JSON.stringify(object);
        return this.dir.uploadText(this.path, json).then(action(() => {
            // Update the lastUploadedValues, which we'll reset to if we 
            this.lastUploadedValues.clear();
            this.values.forEach((v, k) => {
                this.lastUploadedValues.set(k, v);
            });
        })).catch(action((e) => {
            console.error("Caught error uploading JSON, reverting to last uploaded values", e);
            this.values.clear();
            this.lastUploadedValues.forEach((v, k) => {
                this.values.set(k, v);
            });
            throw e;
        }));
    };

    /**
     * This sets the value, overwriting the old value, and uploads the resulting JSON to S3 (after a short timeout, to avoid spamming with uploads if you're typing).
     * 
     * @param key 
     * @param value 
     */
    setAttribute(key: string, value: any, uploadImmediate?: boolean): void {
        // If this is already recorded, then nothing new here
        if (this.values.get(key) === value) {
            return;
        }
        this.values.set(key, value);
        if (uploadImmediate) {
            this.uploadNow();
        }
        else {
            this.restartUploadTimer();
        }
    }

    /**
     * When called, this starts a timer to upload in a few hundred milliseconds.
     * If it's called while another time is present, that timer is cleared before this one fires.
     */
    restartUploadTimer(): void {
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

export default LiveJsonFile;