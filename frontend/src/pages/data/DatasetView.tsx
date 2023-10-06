import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Table, Button } from "react-bootstrap";
import { Link } from "react-router-dom";
import { observer } from "mobx-react-lite";
import UserHomeDirectory, { DatasetContents } from "../../model/UserHomeDirectory";
import Session from "../../model/Session";

type DatasetViewProps = {
    home: UserHomeDirectory;
    currentLocationUserId: string;
    path: string;
};

const DatasetView = observer((props: DatasetViewProps) => {
    const location = useLocation();
    const navigate = useNavigate();
    const [folderName, setFolderName] = useState("");
    const [subjectName, setSubjectName] = useState("");

    const home = props.home;
    const path = props.path;
    const dir = home.dir;
    const datasetContents: DatasetContents = home.getDatasetContents(path);

    if (datasetContents.loading) {
        return <div>Loading...</div>;
    }
    return <div>
        <h3>Dataset Contents:</h3>
        <table className="table">
            <thead>
                <tr>
                    <th scope="col">Type</th>
                    <th scope="col">Name</th>
                    <th scope="col">Delete?</th>
                </tr>
            </thead>
            <tbody>
                {datasetContents.contents.map(({ name, type, path }) => {
                    const typeFirstLetterCapitalized = type.charAt(0).toUpperCase() + type.slice(1);
                    return <tr key={name}>
                        <td>
                            {typeFirstLetterCapitalized}
                        </td>
                        <td>
                            <Link to={Session.getDataURL(props.currentLocationUserId, path)}>{name}</Link>
                        </td>
                        <td>
                            <button className='btn btn-dark' onClick={() => {
                                if (window.confirm("Are you sure you want to delete " + name + "?")) {
                                    console.log("Deleting " + name + " from " + path);
                                    home.deleteFolder(path);
                                }
                            }}>Delete</button>
                        </td>
                    </tr>;
                })}
            </tbody>
        </table>
        <div className="row mb-4">
            <input type="text" placeholder="New Subject Name" value={subjectName} onChange={(e) => {
                setSubjectName(e.target.value);
            }}></input>
            <br/>
            <button className='btn btn-primary mt-1' onClick={() => {
                if (subjectName === "") {
                    alert("Subject name cannot be empty");
                    return;
                }
                home.createSubject(path, subjectName);
                setSubjectName("");
            }}>Create New Subject</button>
        </div>
        <div className="row mb-4 mt-4">
            <input type="text" placeholder="New Folder Name" value={folderName} onChange={(e) => {
                setFolderName(e.target.value);
            }}></input>
            <br/>
            <button className='btn btn-dark mt-1' onClick={() => {
                if (folderName === "") {
                    alert("Folder name cannot be empty");
                    return;
                }
                home.createDataset(path, folderName);
                setFolderName("");
            }}>Create New Folder</button>
        </div>
    </div>
});

export default DatasetView;