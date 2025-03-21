import LiveJsonFile from "./LiveJsonFile";
import LiveFile from "./LiveFile";
import LiveDirectory, {PathData} from "./LiveDirectory";
import Session from "./Session";
import { action, makeObservable, observable } from "mobx";

type PathType = 'profile' | '404' | 'loading';

class UserProfile {
    dir: LiveDirectory;
    profilePicture: LiveFile;
    profileJson: LiveJsonFile;
    searchJson: Map<string, LiveJsonFile>;
    session: Session;

    constructor(dir: LiveDirectory, path: string, session: Session) {
        this.dir = dir;
        this.session = session;
        console.log(this.dir)

        this.profileJson = this.dir.getJsonFile('profile.json');
        this.searchJson = new Map()
        this.profilePicture = dir.getLiveFile("/profile_picture.png");

        this.dropProfilePicture = this.dropProfilePicture.bind(this);

        makeObservable(this, {
            dir: observable,
            profilePicture: observable,
            profileJson: observable,
            searchJson: observable,
            getAttribute: action,
            setAttribute: action,
            getProfileFullName: action,
            getUserDatasetMetadata: action,
            dropProfilePicture: action
        });

    }

    getAttribute(key: string, defaultValue: string) : string {
        return this.profileJson.getAttribute(key, defaultValue)
    }

    setAttribute(key: string, value: any) {
        this.profileJson.setAttribute(key, value)
    }

    getProfileFullName() : string {
        let name:string = this.profileJson.getAttribute("name", "");
        let surname:string = this.profileJson.getAttribute("surname", "");
        if (this.profileJson.loading) {
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

    getPathType(path: string): PathType {
        if (path.startsWith('/')) {
            path = path.substring(1);
        }

        const pathData: PathData | undefined = this.dir.getPath(path, false)
        if (pathData == null || pathData.loading) {
            return 'loading';
        }

        const child_files = pathData.files.map((file) => {
            return file.key.substring(path.length).replace(/\/$/, '').replace(/^\//, '');
        });

        if (child_files.length === 0) {
            return '404';
        } else {
            return 'profile';
        }
    };

    getUserDatasetMetadata() : Map<string, LiveJsonFile> {
      const child_folders = this.dir.getPath("data/", false).folders.map((folder) => {
          return folder.substring("data/".length).replace(/\/$/, '').replace(/^\//, '');
      });

      child_folders.forEach((child_folder) => {
        // Save the live json file.
        this.searchJson.set(child_folder, this.dir.getJsonFile("data/" + child_folder + "/_search.json"))
      });

      return this.searchJson;
    }

    deleteProfilePicture(): void {
      this.session.profilePictureURL = 'https://upload.wikimedia.org/wikipedia/commons/2/2c/Default_pfp.svg';
    }

    /**
     * This file uploads a png file to the server.
     */
    dropProfilePicture(files: File[]): Promise<void> {
        if (files.length !== 1) {
            return Promise.reject("Don't support multiple files for a drop");
        }

        const file = files[0];

        if (!file.type.startsWith('image/')) {
            return Promise.reject("Unsupported file type. Please drop an image.");
        }

        const image = new Image();
        const reader = new FileReader();

        return new Promise<void>((resolve, reject) => {
            reader.onload = (e) => {
                image.src = e.target?.result as string;
            };

            image.onload = () => {
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');

                canvas.width = image.width;
                canvas.height = image.height;
                ctx?.drawImage(image, 0, 0);

                // Convert canvas to PNG
                canvas.toBlob((blob) => {
                    if (!blob) {
                        reject("Failed to convert image to PNG");
                        return;
                    }

                    const pngFile = new File([blob], 'profile_picture.png', { type: 'image/png' });

                    // Proceed with the upload logic
                    if (this.profilePicture === undefined) {
                        console.log(this.dir);
                        this.profilePicture = this.dir.getLiveFile("/profile_picture.png");
                    }

                    console.log(this.profilePicture);
                    const uploadPromise = this.profilePicture.uploadFile(pngFile);

                    this.session.profilePictureURL = this.profilePicture.path;

                    Promise.all([uploadPromise])
                        .then(() => resolve())
                        .catch((error) => reject(error));
                }, 'image/png');
            };

            reader.onerror = () => {
                reject("Error reading the file");
            };

            reader.readAsDataURL(file);
        });
    }
};

export default UserProfile;