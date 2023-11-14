import LiveJsonFile from "./LiveJsonFile";
import LiveDirectory, {PathData} from "./LiveDirectory";

type PathType = 'profile' | '404' | 'loading';

class UserProfile {
    dir: LiveDirectory;
    profileJson: LiveJsonFile;
    searchJson: Map<string, LiveJsonFile>;

    constructor(dir: LiveDirectory) {
        this.dir = dir;
        this.profileJson = this.dir.getJsonFile('profile.json');
        this.searchJson = new Map()
    }

    getAttribute(key: string, defaultValue: string) : string {
        return this.profileJson.getAttribute(key, defaultValue)
    }

    setAttribute(key: string, value: any) {
        this.profileJson.getAttribute(key, value)
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
        this.searchJson.set(child_folder, this.dir.getJsonFile("data/" + child_folder + "/" + "_search.json"))
      });

      return this.searchJson;
    }
};

export default UserProfile;