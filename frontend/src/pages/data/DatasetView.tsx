import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Table, Button } from "react-bootstrap";
import { Link } from "react-router-dom";
import { observer } from "mobx-react-lite";
import UserHomeDirectory, { DatasetContents } from "../../model/UserHomeDirectory";
import Session from "../../model/Session";

type DatasetViewProps = {
    session: Session;
    path: string;
};

const DatasetView = observer((props: DatasetViewProps) => {
    const location = useLocation();
    const navigate = useNavigate();
    const [folderName, setFolderName] = useState("");

    const dataPath = props.session.parseDataURL(location.pathname);
    const home = dataPath.homeDirectory;
    const path = dataPath.path;
    const dir = home.dir;
    const datasetContents: DatasetContents = home.getDatasetContents(path);

    if (datasetContents.loading) {
        return <div>Loading...</div>;
    }
    return <div>
        <ul>
            {datasetContents.contents.map(({ name, type, path }) => {
                return <li key={name}>{type}: <Link to={props.session.getDataURL(dataPath, path)}>{name}</Link> <button onClick={() => {
                    if (window.confirm("Are you sure you want to delete " + name + "?")) {
                        console.log("Deleting " + name + " from " + dataPath.path);
                        home.deleteFolder(dataPath.path, name);
                    }
                }}>Delete</button></li>;
            })}
        </ul>
        <div>
            Create new folder:
            <input type="text" placeholder="Name" value={folderName} onChange={(e) => {
                setFolderName(e.target.value);
            }}></input>
            <button onClick={() => {
                home.createFolder(path, folderName);
                setFolderName("");
            }}>Create</button>
        </div>
    </div>
});

export default DatasetView;