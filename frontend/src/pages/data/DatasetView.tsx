import React, { useState } from "react";
import { Link } from "react-router-dom";
import { observer } from "mobx-react-lite";
import UserHomeDirectory, { DatasetContents } from "../../model/UserHomeDirectory";
import Session from "../../model/Session";
import LiveJsonFile from "../../model/LiveJsonFile";
import { Spinner } from "react-bootstrap";

type DatasetViewProps = {
    home: UserHomeDirectory;
    session: Session;
    currentLocationUserId: string;
    path: string;
    readonly: boolean;
};

const DatasetView = observer((props: DatasetViewProps) => {
    const [folderName, setFolderName] = useState("");
    const [subjectName, setSubjectName] = useState("");

    const home = props.home;
    const path = props.path;
    const dir = home.dir;
    const datasetContents: DatasetContents = home.getDatasetContents(path);

    const showCitationData = false;
    let citationDetails: React.ReactNode = null;
    if (showCitationData) {
        const searchJson: LiveJsonFile = dir.getJsonFile(path + "_search.json")

        const datasetTitle: string = searchJson.getAttribute("title", "")
        const datasetNotes: string = searchJson.getAttribute("notes", "")
        const datasetCitation: string = searchJson.getAttribute("citation", "")
        const datasetFunding: string = searchJson.getAttribute("funding", "")
        const datasetAcknowledgements: string = searchJson.getAttribute("acknowledgements", "")
        citationDetails = <>
            <h3>Dataset Citation Details:</h3>
            <div key="datasetTitle" className="mb-3">
                <label>
                    Title:
                </label>
                <textarea
                    id="title"
                    value={datasetTitle == null ? "" : datasetTitle}
                    className={"form-control" + ((datasetTitle == null) ? " border-primary border-2" : "")}
                    aria-describedby="citeHelp"
                    onFocus={() => {
                        searchJson.onFocusAttribute("title");
                    }}
                    onBlur={() => {
                        searchJson.onBlurAttribute("title");
                    }}
                    onChange={(e) => {
                        searchJson.setAttribute("title", e.target.value);
                    }}
                    readOnly={props.readonly}>
                </textarea>
                <div id="citeHelp" className="form-text">What title do you want for your dataset?</div>
            </div>

            <div key="notes" className="mb-3">
                <label>
                    Dataset Info:
                </label>
                <textarea
                    id="info"
                    value={datasetNotes == null ? "" : datasetNotes}
                    className={"form-control" + ((datasetNotes == null) ? " border-primary border-2" : "")}
                    aria-describedby="citeHelp"
                    onFocus={() => {
                        searchJson.onFocusAttribute("notes");
                    }}
                    onBlur={() => {
                        searchJson.onBlurAttribute("notes");
                    }}
                    onChange={(e) => {
                        searchJson.setAttribute("notes", e.target.value);
                    }}
                    readOnly={props.readonly}>
                </textarea>
                <div id="citeHelp" className="form-text">Insert public notes about the dataset (purpose, description, number of subjects, etc.). It is your responsibility to not include any Personally Identifiable Information (PII) about your subjects!</div>
            </div>

            <div key="citation" className="mb-3">
                <label>
                    Desired Citation:
                </label>
                <textarea
                    id="citation"
                    value={datasetCitation == null ? "" : datasetCitation}
                    className={"form-control" + ((datasetCitation == null) ? " border-primary border-2" : "")}
                    aria-describedby="citeHelp"
                    onFocus={() => {
                        searchJson.onFocusAttribute("citation");
                    }}
                    onBlur={() => {
                        searchJson.onBlurAttribute("citation");
                    }}
                    onChange={(e) => {
                        searchJson.setAttribute("citation", e.target.value);
                    }}
                    readOnly={props.readonly}>
                </textarea>
                <div id="citeHelp" className="form-text">How do you want this data to be cited?</div>
            </div>

            <div key="funding" className="mb-3">
                <label>
                    Funding:
                </label>
                <textarea
                    id="funding"
                    value={datasetFunding == null ? "" : datasetFunding}
                    className={"form-control" + ((datasetFunding == null) ? " border-primary border-2" : "")}
                    aria-describedby="citeHelp"
                    onFocus={() => {
                        searchJson.onFocusAttribute("funding");
                    }}
                    onBlur={() => {
                        searchJson.onBlurAttribute("funding");
                    }}
                    onChange={(e) => {
                        searchJson.setAttribute("funding", e.target.value);
                    }}
                    readOnly={props.readonly}>
                </textarea>
                <div id="citeHelp" className="form-text">Funding supporting this project.</div>
            </div>

            <div key="acknowledgements" className="mb-3">
                <label>
                    Acknowledgements:
                </label>
                <textarea
                    id="acknowledgements"
                    value={datasetAcknowledgements == null ? "" : datasetAcknowledgements}
                    className={"form-control" + ((datasetAcknowledgements == null) ? " border-primary border-2" : "")}
                    aria-describedby="citeHelp"
                    onFocus={() => {
                        searchJson.onFocusAttribute("acknowledgements");
                    }}
                    onBlur={() => {
                        searchJson.onBlurAttribute("acknowledgements");
                    }}
                    onChange={(e) => {
                        searchJson.setAttribute("acknowledgements", e.target.value);
                    }}
                    readOnly={props.readonly}>
                </textarea>
                <div id="citeHelp" className="form-text">Acknowledgements you would like to add.</div>
            </div>
        </>;
    }

    if (datasetContents.loading) {
        return <div>
            <Spinner animation="border" />
        </div>;
    }

    let dataTable = (
        <table className="table">
            <thead>
                <tr>
                    <th scope="col">Type</th>
                    <th scope="col">Name</th>
                    <th scope="col">Status</th>
                    <th scope="col">Delete?</th>
                </tr>
            </thead>
            <tbody>
                {datasetContents.contents.map(({ name, type, path, status }) => {
                    const typeFirstLetterCapitalized = type.charAt(0).toUpperCase() + type.slice(1);
                    let statusBadge = <span className="badge bg-secondary">Unknown</span>;
                    if (status === 'done') {
                        statusBadge = <span className="badge bg-success">Done</span>;
                    }
                    else if (status === 'error') {
                        statusBadge = <span className="badge bg-danger">Error</span>;
                    }
                    else if (status === 'processing') {
                        statusBadge = <span className="badge bg-warning">Processing</span>;
                    }
                    else if (status === 'ready_to_process') {
                        statusBadge = <span className="badge bg-info">Ready to Process</span>;
                    }
                    else if (status === 'loading') {
                        statusBadge = <span className="badge bg-secondary">Loading</span>;
                    }
                    else if (status === 'dataset') {
                        statusBadge = <span className="badge bg-info">Dataset</span>;
                    }
                    else if (status === 'needs_review') {
                        statusBadge = <span className="badge bg-warning">Needs Review</span>;
                    }
                    else if (status === 'waiting_for_server') {
                        statusBadge = <span className="badge bg-secondary">Waiting for server</span>;
                    }
                    else if (status === 'slurm') {
                        statusBadge = <span className="badge bg-warning">Queued on SLURM</span>;
                    }
                    else if (status === 'needs_data') {
                        statusBadge = <span className="badge bg-secondary">Needs Data</span>;
                    }
                    return <tr key={name}>
                        <td>
                            {typeFirstLetterCapitalized}
                        </td>
                        <td>
                            <Link to={Session.getDataURL(props.currentLocationUserId, path)}>{name}</Link>
                        </td>
                        <td>
                            {statusBadge}
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
    );
    if (datasetContents.contents.length === 0) {
        dataTable = <div style={{ textAlign: 'center' }}>
            <div style={{ paddingBottom: '50px' }}>
                No datasets or subjects yet!
            </div>
        </div>;
    }
    let reprocessButton = null;
    if (props.session.userEmail.endsWith("@stanford.edu")) {
        reprocessButton = (
            <div className="row mb-4 mt-4">
                <button className='btn btn-danger' onClick={() => {
                    if (window.confirm("DANGER! This will reprocess all subjects in this dataset. This will delete all existing results for thees subjects. Are you sure?")) {
                        home.reprocessAllSubjects(path);
                    }
                }}>Reprocess All Subjects</button>
            </div>
        );
    }

    return <div>
        {dataTable}
        <div className="row mb-4">
            <input type="text" placeholder="New Subject Name" value={subjectName} onChange={(e) => {
                setSubjectName(e.target.value);
            }}></input>
            <br />
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
            <input type="text" placeholder="New Dataset Name" value={folderName} onChange={(e) => {
                setFolderName(e.target.value);
            }}></input>
            <br />
            <button className='btn btn-dark mt-1' onClick={() => {
                if (folderName === "") {
                    alert("Dataset name cannot be empty");
                    return;
                }
                home.createDataset(path, folderName);
                setFolderName("");
            }}>Create New Dataset</button>
        </div>
        {reprocessButton}

        {citationDetails}

    </div>
});

export default DatasetView;