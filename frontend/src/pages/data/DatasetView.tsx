import React, { useState } from "react";
import { Link } from "react-router-dom";
import { observer } from "mobx-react-lite";
import UserHomeDirectory, { DatasetContents } from "../../model/UserHomeDirectory";
import Session from "../../model/Session";
import LiveJsonFile from "../../model/LiveJsonFile";
import { Spinner, OverlayTrigger, Tooltip, Row, Col} from "react-bootstrap";

type DatasetViewProps = {
    home: UserHomeDirectory;
    session: Session;
    currentLocationUserId: string;
    path: string;
    readonly: boolean;
};

const dataset_info_input = (name:string, variable:string, json_file:any, json_key:string, help_string: string, readonly:boolean) => {
  return    <div key={json_key} className="mb-3">
              <label> {name} </label>
              {readonly ? (
                  <p>
                    {variable}
                  </p>
              ) : (
                <>
                  <textarea
                    id={json_key}
                    value={variable == null ? "" : variable}
                    className={"form-control" + ((variable == null) ? " border-primary border-2" : "")}
                    onFocus={() => {
                        json_file.onFocusAttribute(json_key);
                    }}
                    onBlur={() => {
                        json_file.onBlurAttribute(json_key);
                    }}
                    onChange={(e) => {
                        json_file.setAttribute(json_key, e.target.value);
                    }}>
                  </textarea>
                  <div id={json_key + "Help"} className="form-text">{help_string}</div>
                </>
              )}
            </div>
}

const DatasetView = observer((props: DatasetViewProps) => {
    const [folderName, setFolderName] = useState("");
    const [subjectName, setSubjectName] = useState("");

    const home = props.home;
    const path = props.path;
    const dir = home.dir;
    const datasetContents: DatasetContents = home.getDatasetContents(path);

    const showCitationData = true;
    let citationDetails: React.ReactNode = null;
    if (showCitationData) {
        const searchJson: LiveJsonFile = dir.getJsonFile(path + "_search.json")

        const datasetTitle: string = searchJson.getAttribute("title", "")
        const datasetNotes: string = searchJson.getAttribute("notes", "")
        const datasetCitation: string = searchJson.getAttribute("citation", "")
        const datasetFunding: string = searchJson.getAttribute("funding", "")
        const datasetAcknowledgements: string = searchJson.getAttribute("acknowledgements", "")
        citationDetails = <>
            <div key="datasetTitle" className="mb-3">
              {props.readonly ? (
                <h4>
                  {datasetTitle}
                </h4>
                ) : (
                <>
                  <label>
                      Title:
                  </label>
                  <input
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
                  </input>
                  <div id="citeHelp" className="form-text">What title do you want for your dataset?</div>
                </>
              )}
            </div>

            {dataset_info_input("Dataset Info:", datasetNotes, searchJson, "notes", "Insert public notes about the dataset (purpose, description, number of subjects, etc.). It is your responsibility to not include any Personally Identifiable Information (PII) about your subjects!", props.readonly)}
            {dataset_info_input("Desired Citation:", datasetCitation, searchJson, "citation", "How do you want this data to be cited?", props.readonly)}
            {dataset_info_input("Funding:", datasetFunding, searchJson, "funding", "Funding supporting this project.", props.readonly)}
            {dataset_info_input("Acknowledgements:", datasetAcknowledgements, searchJson, "acknowledgements", "Acknowledgements you would like to add.", props.readonly)}
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
              <OverlayTrigger
                placement="top"
                delay={{ show: 50, hide: 400 }}
                overlay={(props) => (
                  <Tooltip id="button-tooltip" {...props}>
                    DANGER! This will reprocess all subjects in this dataset. This will delete all existing results for thees subjects. Are you sure?.
                  </Tooltip>
                )}>
                  <button className='btn btn-danger' onClick={() => {
                      if (window.confirm("DANGER! This will reprocess all subjects in this dataset. This will delete all existing results for thees subjects. Are you sure?")) {
                          home.reprocessAllSubjects(path);
                      }
                  }}>Reprocess All Subjects</button>
              </OverlayTrigger>
        );
    }

    return <div className="container">

        <Row className="mb-4 align-items-center">
            {props.readonly ? null : (
                <>
                  <Col className="align-items-center">
                    <div className="row mx-2">
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
                  </Col>
                  <Col className="align-items-center">
                    <div className="row mx-2">
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
                  </Col>
                  {props.session.userEmail.endsWith("@stanford.edu") ?
                    <Col className="align-items-center">
                      <div className="row mx-2 align-items-center">
                        {reprocessButton}
                      </div>
                    </Col>
                  : null}
                </>
              )}
        </Row>
        <Row>
          <Col xs={3}>
            <Row className="align-items-center">
                <Row className="align-items-center">
                  <div className="row mt-2">
                    {citationDetails}
                  </div>
                </Row>
            </Row>
          </Col>
          <Col>
            {dataTable}
          </Col>
        </Row>
    </div>
});

export default DatasetView;