import UserHomeDirectory from "./UserHomeDirectory";
import UserProfile from "./UserProfile";
import { LiveDirectoryImpl } from "./LiveDirectory";
import { S3API } from "./S3API";
import { PubSubSocket } from "./PubSubSocket";
import { makeObservable, action, observable } from 'mobx';

type DataURL = {
    homeDirectory: UserHomeDirectory;
    path: string;
    userProfile: UserProfile;
    userId: string;
    readonly: boolean;
}

type ProfileURL = {
    homeDirectory: UserHomeDirectory;
    path: string;
    userProfile: UserProfile;
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
    userProfiles: Map<string, UserProfile>;

    loadingLoginState: boolean;
    loggedIn: boolean;
    userId: string;
    userEmail: string;
    profilePictureURL: string;

    constructor(s3: S3API, pubsub: PubSubSocket, region: string) {
        this.s3 = s3;
        this.pubsub = pubsub;
        this.region = region;
        this.homeDirectories = new Map();
        this.userProfiles = new Map();

        // We default to loading whether or not we've loggen in
        this.loadingLoginState = true;
        this.loggedIn = false;
        this.userId = '';
        this.userEmail = '';
        this.profilePictureURL = 'https://upload.wikimedia.org/wikipedia/commons/2/2c/Default_pfp.svg';

        this.setLoggedIn = this.setLoggedIn.bind(this);
        this.setNotLoggedIn = this.setNotLoggedIn.bind(this);
        this.parseDataURL = this.parseDataURL.bind(this);
        this.parseProfileURL = this.parseProfileURL.bind(this);

        makeObservable(this, {
            loadingLoginState: observable,
            loggedIn: observable,
            userId: observable,
            userEmail: observable,
            profilePictureURL: observable,
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
    static getDataURL(currentLocationUserId: string, pathInCurrentUserDirectory: string): string
    {
        if (pathInCurrentUserDirectory.startsWith("/")) {
            pathInCurrentUserDirectory = pathInCurrentUserDirectory.substring(1);
        }
        return '/data/' + currentLocationUserId + '/' + pathInCurrentUserDirectory;
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
        let userId = ""
        let prefix = ""
        let path = ""

        if (url.startsWith("/")) {
            url = url.substring(1);
        }
        if (url.startsWith("data/")) {
            url = url.substring("data/".length);
        }

        if (url.startsWith("/")) {
            url = url.substring(1);
        }
        const parts = decodeURI(url).split("/");
        userId = parts[0];
        path = parts.slice(1).join("/");
        prefix = (userId === 'private' ? 'private/' : 'protected/') + this.region + ":" + (userId === 'private' ? this.userId : userId) + "/data/";

        let homeDirectory = this.homeDirectories.get(userId);
        if (homeDirectory == null) {
            homeDirectory = new UserHomeDirectory(new LiveDirectoryImpl(prefix, this.s3, this.pubsub));
            this.homeDirectories.set(userId, homeDirectory);
        }

        prefix = (userId === 'private' ? 'private/' : 'protected/') + this.region + ":" + (userId === 'private' ? this.userId : userId) + "/";
        const liveDirectoryImplProfile = new LiveDirectoryImpl(prefix, this.s3, this.pubsub)
        let userProfile = this.userProfiles.get(userId);
        if (userProfile == null) {
            userProfile = new UserProfile(liveDirectoryImplProfile, path, this);
            this.userProfiles.set(userId, userProfile);

            if (userId === this.userId || this.userId === "") {
              userProfile.dir.getSignedURL(userProfile.profilePicture.path, 1000).then((url) => {
                fetch(url).then((response) => {
                  if (response.ok) {
                      this.profilePictureURL = url;
                  }
                });
              })
            }
        }

        const readonly = !(this.loggedIn && (this.userId === userId || userId === 'private'));

        return {
            homeDirectory,
            path,
            userProfile,
            userId,
            readonly,
        }
    }
    /**
     * This interprets a URL and returns the Profile data.
     *
     * It handles cacheing the profile objects, and will create them if they don't exist.
     *
     * @param url The URL to get the path for
     *
     * Example URLs:
     * /profile/35e1c7ca-cc58-457e-bfc5-f6161cc7278b
     */
    parseProfileURL(url: string): ProfileURL
    {
        let userId = ""
        let prefix = ""
        let path = ""

        if (url.startsWith("/")) {
            url = url.substring(1);
        }
        if (url.startsWith("profile/")) {
            url = url.substring("profile/".length);
        }

        if (url.startsWith("/")) {
            url = url.substring(1);
        }
        const parts = decodeURI(url).split("/");
        userId = parts[0];
        path = parts.slice(1).join("/");

        prefix = (userId === 'private' ? 'private/' : 'protected/') + this.region + ":" + (userId === 'private' ? this.userId : userId) + "/data/";
        const liveDirectoryImpl = new LiveDirectoryImpl(prefix, this.s3, this.pubsub)
        let homeDirectory = this.homeDirectories.get(userId);
        if (homeDirectory == null) {
            homeDirectory = new UserHomeDirectory(liveDirectoryImpl);
            this.homeDirectories.set(userId, homeDirectory);
        }

        prefix = (userId === 'private' ? 'private/' : 'protected/') + this.region + ":" + (userId === 'private' ? this.userId : userId) + "/";
        const liveDirectoryImplProfile = new LiveDirectoryImpl(prefix, this.s3, this.pubsub)
        let userProfile = this.userProfiles.get(userId);
        if (userProfile == null) {
            userProfile = new UserProfile(liveDirectoryImplProfile, path, this);
            this.userProfiles.set(userId, userProfile);

            if (userId === this.userId || this.userId === "") {
              userProfile.dir.getSignedURL(userProfile.profilePicture.path, 1000).then((url) => {
                fetch(url).then((response) => {
                  if (response.ok) {
                    this.profilePictureURL = url;
                  }
                });
              })
            }
        }

        const readonly = !(this.loggedIn && (this.userId === userId || userId === 'private'));

        return {
            homeDirectory,
            path,
            userProfile,
            userId,
            readonly,
        }
    }
}

export type { DataURL };
export default Session;