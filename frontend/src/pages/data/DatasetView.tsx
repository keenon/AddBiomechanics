import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { observer } from "mobx-react-lite";
import UserHomeDirectory, { DatasetContents } from "../../model/UserHomeDirectory";
import Session from "../../model/Session";
import LiveJsonFile from "../../model/LiveJsonFile";
import { Spinner, OverlayTrigger, Tooltip, Row, Col} from "react-bootstrap";
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
                        getSearchJsonObject(searchJson, inherit).onFocusAttribute(json_key);
                    }}
                    onBlur={() => {
                        getSearchJsonObject(searchJson, inherit).onBlurAttribute(json_key);
                    }}
                    onChange={(e) => {
                        setJsonValue(json_key, e.target.value, searchJson)
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

function normalizePath(path: string): string {
    if (path.startsWith('/')) {
        path = path.substring(1);
    }
    // Replace any accidental // with /
    path = path.replace(/\/\//g, '/');

    if (path !== "")
      if (!path.endsWith("/"))
        path = path + "/"
    return path;
}

const loadSearchJson = async (path:string, dir:any, session:Session) => {
    // Get current search json and information associated.
    var searchJsonParent: LiveJsonFile | null = null
    path = normalizePath(path)
    var searchJson: LiveJsonFile = await dir.getJsonFile(path + "_search.json")
    var inheritFromParent: boolean = searchJson.getAttribute("inherit", "false") === "true" ? true : false

    // If path is home, it cannot inherit from parent, so it will always be set to false.
    if (path === ""){
      inheritFromParent = false
      searchJson.setAttribute("inherit", "false");
    }

    // If the attribution info is inherited from parent, let's search for the parent.
    if (inheritFromParent && path !== "") {
      // Recursively retrieve parents until one of them is not marked as inheriting, or home is reached.
      var path_parent_absolute:string = get_parent_path_absolute(path)
      var dir_parent = session.parseDataURL('/data/' + session.userId + "/" + path_parent_absolute).homeDirectory.dir;
      searchJsonParent = dir_parent.getJsonFile("_search.json")
      var inheritFromParentOfParent = searchJsonParent.getAttribute("inherit", "true") === "true" ? true : false
      while (inheritFromParentOfParent && path_parent_absolute !== "undefined") {
        path_parent_absolute = get_parent_path_absolute(path_parent_absolute)
        dir_parent = session.parseDataURL(path_parent_absolute).homeDirectory.dir;
        searchJsonParent = dir_parent.getJsonFile("_search.json")
        inheritFromParentOfParent = searchJsonParent.getAttribute("inherit", "true") === "true" ? true : false
      }
    }

    return {
      "current": searchJson,
      "parent": searchJsonParent,
    }
}

const getSearchJsonObject = (searchJson:any, inherit:boolean) => {
  return inherit ? searchJson["parent"] : searchJson["current"]
}

const getJsonValue = (key:string, searchJson:any) => {
  var inherit = searchJson["current"].getAttribute("inherit", false) === "true" ? true : false
  if (key === "title") {
    return inherit ? searchJson["parent"].getAttribute("title", "") : searchJson["current"].getAttribute("title", "")
  } else if (key === "notes") {
    return inherit ? searchJson["parent"].getAttribute("notes", "") : searchJson["current"].getAttribute("notes", "")
  } else if (key === "citation") {
    return inherit ? searchJson["parent"].getAttribute("citation", "") : searchJson["current"].getAttribute("citation", "")
  } else if (key === "funding") {
    return inherit ? searchJson["parent"].getAttribute("funding", "") : searchJson["current"].getAttribute("funding", "")
  } else if (key === "acknowledgements") {
    return inherit ? searchJson["parent"].getAttribute("acknowledgements", "") : searchJson["current"].getAttribute("acknowledgements", "")
  } else if (key === "inherit") {
    return inherit ? (searchJson["parent"].getAttribute("inherit", "") === "true" ? true : false) : inherit
  }
}

const setJsonValue = (key:string, value:string, searchJson:any) => {
  var inherit = searchJson["current"].getAttribute("inherit", true) === "true" ? true : false
  if (key === "title") {
    inherit ? searchJson["parent"].setAttribute("title", value) : searchJson["current"].setAttribute("title", value)
  } else if (key === "notes") {
    inherit ? searchJson["parent"].setAttribute("notes", value) : searchJson["current"].setAttribute("notes", value)
  } else if (key === "citation") {
    inherit ? searchJson["parent"].setAttribute("citation", value) : searchJson["current"].setAttribute("citation", value)
  } else if (key === "funding") {
    inherit ? searchJson["parent"].setAttribute("funding", value) : searchJson["current"].setAttribute("funding", value)
  } else if (key === "acknowledgements") {
    inherit ? searchJson["parent"].setAttribute("acknowledgements", value) : searchJson["current"].setAttribute("acknowledgements", value)
  } else if (key === "inherit") {
    searchJson["current"].setAttribute("inherit", value) // Only current because we do not want to change inherit in parent.
  }
}

const DatasetView = observer((props: DatasetViewProps) => {
    const location = useLocation();

    const [folderName, setFolderName] = useState("");
    const [subjectName, setSubjectName] = useState("");

    const home = props.home;
    const path = props.path;
    const dir = home.dir;

    const datasetContents: DatasetContents = home.getDatasetContents(path);

    const [searchJson, setSearchJson] = useState(loadSearchJson(path, dir, props.session))

    const [datasetTitle, setDatasetTitle] = useState("")
    const [datasetNotes, setDatasetNotes] = useState("")
    const [datasetCitation, setDatasetCitation] = useState("")
    const [datasetFunding, setDatasetFunding] = useState("")
    const [datasetAcknowledgements, setDatasetAcknowledgements] = useState("")
    const [inheritFromParent, setInheritFromParent] = useState(false)


    useEffect(() => {
      searchJson.then((jsonFile) => {
        setDatasetTitle(getJsonValue("title", jsonFile))
        setDatasetNotes(getJsonValue("notes", jsonFile))
        setDatasetCitation(getJsonValue("citation", jsonFile))
        setDatasetFunding(getJsonValue("funding", jsonFile))
        setDatasetAcknowledgements(getJsonValue("acknowledgements", jsonFile))
      })
    }, [location.pathname, inheritFromParent, searchJson]);

    const showCitationData = true;
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
                        getSearchJsonObject(searchJson, inheritFromParent).onFocusAttribute("title");
                    }}
                    onBlur={() => {
                        getSearchJsonObject(searchJson, inheritFromParent).onBlurAttribute("title");
                    }}
                    onChange={(e) => {
                        setJsonValue("title", e.target.value, searchJson)
                        setDatasetTitle(e.target.value)
                    }}
                    readOnly={props.readonly}>
                </input>
                <div id="citeHelp" className="form-text">What title do you want for your dataset?</div>
              </>
            )}
          </div>

          {dataset_info_input("Dataset Info:", datasetNotes, searchJson, "notes", "Insert public notes about the dataset (purpose, description, number of subjects, etc.). It is your responsibility to not include any Personally Identifiable Information (PII) about your subjects!", inheritFromParent, props.readonly)}
          {dataset_info_input("Desired Citation:", datasetCitation, searchJson, "citation", "How do you want this data to be cited?", inheritFromParent, props.readonly)}
          {dataset_info_input("Funding:", datasetFunding, searchJson, "funding", "Funding supporting this project.", inheritFromParent, props.readonly)}
          {dataset_info_input("Acknowledgements:", datasetAcknowledgements, searchJson, "acknowledgements", "Acknowledgements you would like to add.", inheritFromParent, props.readonly)}

          {path !== "" ? (
            <Row>
              <Col>
                <input
                  type="checkbox"
                  id="checkboxInheritFromParent"
                  checked={inheritFromParent}
                  onFocus={() => {
                      getSearchJsonObject(searchJson, false).onFocusAttribute("inherit"); // False because we only modify the inherit variable in the current file.
                  }}
                  onBlur={() => {
                      getSearchJsonObject(searchJson, false).onBlurAttribute("inherit"); // False because we only modify the inherit variable in the current file.
                  }}
                  onChange={(e) => {
                    setJsonValue("inherit", e.target.checked ? "true" : "false", searchJson)
                    setInheritFromParent(e.target.checked)
                  }}
                  disabled={props.readonly}
                />
                <label htmlFor="checkboxInheritFromParent">Inherit from parent</label>
              </Col>
            </Row>
          ) : null }
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