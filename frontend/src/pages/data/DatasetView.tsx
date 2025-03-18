import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { observer } from "mobx-react-lite";
import UserHomeDirectory, { DatasetContents, AttributionContents } from "../../model/UserHomeDirectory";
import Session from "../../model/Session";
import LiveJsonFile from "../../model/LiveJsonFile";
import { Spinner, OverlayTrigger, Tooltip, Row, Col} from "react-bootstrap";
import { toast } from 'react-toastify';
import { parseLinks, showToast } from "../../utils"
import { useLocation } from 'react-router-dom';

type DatasetViewProps = {
    home: UserHomeDirectory;
    session: Session;
    currentLocationUserId: string;
    path: string;
    readonly: boolean;
};

const dataset_info_input = (name:string, variable:string, searchJson:any, json_key:string, help_string: string, inherit:boolean, readonly:boolean) => {
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
                        searchJson.onFocusAttribute(json_key);
                    }}
                    onBlur={() => {
                        searchJson.onBlurAttribute(json_key);
                    }}
                    onChange={(e) => {
                        searchJson.setAttribute(json_key, e.target.value)
                    }}>
                  </textarea>
                  <div id={json_key + "Help"} className="form-text">{help_string}</div>
                </>
              )}
            </div>
}

const get_parent_path_absolute = (path:string|undefined) => {
  var parent = "undefined";
  if (path !== undefined) {
    const path_parts = path.split("/");
    parent = "";
    if (path.trim() === "")
      parent = "undefined";
    else if (!path.includes("/") || (path.includes("/") && path_parts.length === 2 && path_parts[path_parts.length-1] === ""))
      parent = "";
    else if (path.endsWith("/")) {
      for(var i = 0; i < path_parts.length-2; i++)
        parent += path_parts[i] + "/";
    } else {
      for(var i = 0; i < path_parts.length-1; i++)
        parent += path_parts[i] + "/";
    }
  }
  return parent
}

const DatasetView = observer((props: DatasetViewProps) => {
    const location = useLocation();

    const [folderName, setFolderName] = useState("");
    const [subjectName, setSubjectName] = useState("");

    const home = props.home;
    const path = props.path;
    const dir = home.dir;

    // Informative toast
    // showToast(
    //   "Scheduled Maintenance: AddBiomechanics will be unavailable on Tuesday, February 4, 2025, from 8:00 AM to 6:00 PM due to maintenance of the Stanford Computing Cluster. Tasks queued during this time will be paused and resume automatically afterward. Thank you for your understanding.",
    //   "warning",
    //   "processing",
    //   toast.POSITION.BOTTOM_CENTER,
    //   false
    // );

    const datasetContents: DatasetContents = home.getDatasetContents(path);

    const attributionContents: AttributionContents | undefined = home.getAttributionContents(path);
    const searchJson:LiveJsonFile | undefined = attributionContents?.searchJson;
    const searchJsonParent:LiveJsonFile | undefined = searchJson

    let datasetTitle = searchJson?.getAttribute("title", "")
    let datasetNotes = searchJson?.getAttribute("notes", "")
    let datasetCitation = searchJson?.getAttribute("citation", "")
    let datasetFunding = searchJson?.getAttribute("funding", "")
    let datasetAcknowledgements = searchJson?.getAttribute("acknowledgements", "")
    let inheritFromParent = searchJson?.getAttribute("inherit", "true") === "true"

    // If inherit from parent, get parent path recursively until a parent without inherit is found, and load it.
//    if (inheritFromParent) {
//      let parent_path = get_parent_path_absolute(path)
//      let attributionContentsParent: AttributionContents | undefined = home.getAttributionContents(parent_path);
//      let searchJsonParent = attributionContentsParent?.searchJson;
//      while (searchJsonParent?.getAttribute("inherit", "false") === "true" && parent_path !== "undefined") {
//        attributionContentsParent = home.getAttributionContents(parent_path)
//        searchJsonParent = attributionContentsParent?.searchJson;
//        parent_path = get_parent_path_absolute(parent_path)
//      }
//      datasetTitle = searchJsonParent?.getAttribute("title", "")
//      datasetNotes = searchJsonParent?.getAttribute("notes", "")
//      datasetCitation = searchJsonParent?.getAttribute("citation", "")
//      datasetFunding = searchJsonParent?.getAttribute("funding", "")
//      datasetAcknowledgements = searchJsonParent?.getAttribute("acknowledgements", "")
//    }

    useEffect(() => {
      setInheritButton(inheritFromParent);
    }, [inheritFromParent]);

    const [inheritButton, setInheritButton] = useState(inheritFromParent)

    let parent_path = get_parent_path_absolute(path)
    const showCitationData = parent_path == "";
    console.log("PATH: " + path)
    console.log("PARENT PATH: " + parent_path)
    let citationDetails: React.ReactNode = null;
    if (showCitationData) {

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
                        if (inheritFromParent) {
                            searchJsonParent?.onFocusAttribute("title");
                        } else {
                            searchJson?.onFocusAttribute("title");
                        }
                    }}
                    onBlur={() => {
                        if (inheritFromParent) {
                            searchJsonParent?.onBlurAttribute("title");
                        } else {
                            searchJson?.onBlurAttribute("title");
                        }
                    }}
                    onChange={(e) => {
                        if (inheritFromParent) {
                            searchJsonParent?.setAttribute("title", e.target.value)
                        } else {
                            searchJson?.setAttribute("title", e.target.value)
                        }
                    }}
                    readOnly={props.readonly}>
                </input>
                <div id="citeHelp" className="form-text">What title do you want for your dataset?</div>
              </>
            )}
          </div>

          {dataset_info_input("Dataset Info:", datasetNotes, inheritFromParent ? searchJsonParent : searchJson, "notes", "Insert public notes about the dataset (purpose, description, number of subjects, etc.). It is your responsibility to not include any Personally Identifiable Information (PII) about your subjects!", inheritFromParent, props.readonly)}
          {dataset_info_input("Desired Citation:", datasetCitation, inheritFromParent ? searchJsonParent : searchJson, "citation", "How do you want this data to be cited?", inheritFromParent, props.readonly)}
          {dataset_info_input("Funding:", datasetFunding, inheritFromParent ? searchJsonParent : searchJson, "funding", "Funding supporting this project.", inheritFromParent, props.readonly)}
          {dataset_info_input("Acknowledgements:", datasetAcknowledgements, inheritFromParent ? searchJsonParent : searchJson, "acknowledgements", "Acknowledgements you would like to add.", inheritFromParent, props.readonly)}

      </>;
    }
//          {path !== "" ? (
//            <Row>
//              <Col>
//                <input
//                  type="checkbox"
//                  id="checkboxInheritFromParent"
//                  checked={inheritButton}
//                  onFocus={() => {
//                      searchJson?.onFocusAttribute("inherit");
//                  }}
//                  onBlur={() => {
//                      searchJson?.onBlurAttribute("inherit");
//                  }}
//                  onChange={(e) => {
//                    searchJson?.setAttribute("inherit", e.target.checked ? "true" : "false")
//                    setInheritButton(e.target.checked)
//                  }}
//                  disabled={props.readonly}
//                />
//                <label htmlFor="checkboxInheritFromParent">Inherit from parent</label>
//              </Col>
//            </Row>
//          ) : null }

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
                    else if (status === 'incomplete') {
                        statusBadge = <span className="badge bg-warning">Incomplete</span>;
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
                  {/* If no parent, we are in home. Only allow to create folders (datasets) here. */}
                  {parent_path === "undefined" ?
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
                    :
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
                    </Col>}
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

        {/* This folder is not a dataset.*/}
        {showCitationData ?
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
        :
        <Row>
          <Col>
            {dataTable}
          </Col>
        </Row>}

    </div>
});

export default DatasetView;
