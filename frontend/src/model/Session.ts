import UserHomeDirectory from "./UserHomeDirectory";
import { LiveDirectoryImpl, PathData } from "./LiveDirectory";
import { S3API } from "./S3API";
import { PubSubSocket } from "./PubSubSocket";
import { makeObservable, action, observable } from 'mobx';

type DataURL = {
    homeDirectory: UserHomeDirectory;
    path: string;
    userId: string;
    readonly: boolean;
}

// This class manages the lifecycle of a user's session. It is responsible for handling login, 
// identifying the user, managing the home directory's of users who are visited, and logging out.
class Session {
    // Storage state
    s3: S3API;
    pubsub: PubSubSocket;
    region: string;
    homeDirectories: Map<string, UserHomeDirectory>;

    loadingLoginState: boolean;
    loggedIn: boolean;
    userId: string;
    userEmail: string;

    constructor(s3: S3API, pubsub: PubSubSocket, region: string) {
        this.s3 = s3;
        this.pubsub = pubsub;
        this.region = region;
        this.homeDirectories = new Map();

        // We default to loading whether or not we've loggen in
        this.loadingLoginState = true;
        this.loggedIn = false;
        this.userId = '';
        this.userEmail = '';

        this.setLoggedIn = this.setLoggedIn.bind(this);
        this.setNotLoggedIn = this.setNotLoggedIn.bind(this);
        this.parseDataURL = this.parseDataURL.bind(this);

        makeObservable(this, {
            loadingLoginState: observable,
            loggedIn: observable,
            userId: observable,
            userEmail: observable,
            setLoggedIn: action,
            setNotLoggedIn: action,
        });
    }

    /**
     * This gets called to notify the session that the user has logged in.
     * 
     * @param userId 
     * @param userEmail 
     */
    setLoggedIn(userId: string, userEmail: string): void {
        this.loadingLoginState = false;
        this.loggedIn = true;
        this.userId = userId;
        this.userEmail = userEmail;

        // s3.uploadText("protected/" + awsExports.aws_user_files_s3_bucket_region + ":" + myIdentityId + "/account.json", JSON.stringify({ email }));
        // // This is just here to be convenient for a human searching through the S3 buckets manually
        this.s3.uploadText("protected/" + this.region + ":" + userId + "/" + userEmail.replace("@", ".AT."), JSON.stringify({ email: userEmail }));
    }

    /**
     * This gets called to notify the session that either the user has logged out, or the user was never logged in 
     * and we just found out because a web request returned.
     */
    setNotLoggedIn(): void {
        this.loadingLoginState = false;
        this.loggedIn = false;
        this.userId = '';
        this.userEmail = '';
    }

    /**
     * Once the user is logged in, this returns the path to their home directory.
     * 
     * @returns The path to the user's home directory
     */
    getHomeDirectoryURL(): string
    {
        return '/data/' + this.userId + '/';
    }

    /**
     * This converts a path within the current UserHomeDirectory into a full URL suitable for a link in the browser.
     * 
     * @param currentLocation The parsed current location of the browser
     * @param pathInCurrentUserDirectory The path to the file or folder, within the same UserHomeDirectory as we're currently viewing, to get the full URL for
     */
    getDataURL(currentLocation: DataURL, pathInCurrentUserDirectory: string): string
    {
        if (pathInCurrentUserDirectory.startsWith("/")) {
            pathInCurrentUserDirectory = pathInCurrentUserDirectory.substring(1);
        }
        return '/data/' + currentLocation.userId + '/' + pathInCurrentUserDirectory;
    }

    /**
     * This interprets a URL and returns the UserHomeDirectory and path that it represents (in that directory).
     * 
     * It handles cacheing the UserHomeDirectory objects, and will create them if they don't exist.
     * 
     * @param url The URL to get the path for
     * 
     * Example URLs:
     * /data/35e1c7ca-cc58-457e-bfc5-f6161cc7278b
     * /data/35e1c7ca-cc58-457e-bfc5-f6161cc7278b/ASB2023/TestProsthetic
     * /data/35e1c7ca-cc58-457e-bfc5-f6161cc7278b/ASB2023/TestProsthetic
     */
    parseDataURL(url: string): DataURL
    {
        if (url.startsWith("/")) {
            url = url.substring(1);
        }
        if (url.startsWith("data/")) {
            url = url.substring("data/".length);
        }
        if (url.startsWith("/")) {
            url = url.substring(1);
        }
        const parts = url.split("/");
        const userId = parts[0];
        const path = parts.slice(1).join("/");
        const prefix = "protected/" + this.region + ":" + userId + "/data/";

        let homeDirectory = this.homeDirectories.get(userId);
        if (homeDirectory == null) {
            homeDirectory = new UserHomeDirectory(new LiveDirectoryImpl(prefix, this.s3, this.pubsub));
            this.homeDirectories.set(userId, homeDirectory);
        }

        const readonly = !(this.loggedIn && this.userId === userId);

        return {
            homeDirectory,
            path,
            userId,
            readonly,
        }
    }
}

export type { DataURL };
export default Session;