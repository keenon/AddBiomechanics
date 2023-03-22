import { useState, useEffect, useReducer } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
import MocapS3Cursor from '../../state/MocapS3Cursor';
import {
  Row,
  Col,
  Card,
  OverlayTrigger,
  Tooltip
} from "react-bootstrap";
import { observer } from "mobx-react-lite";
import './ProfileView.scss';
import { Auth } from "aws-amplify";
import 'react-toastify/dist/ReactToastify.css';
import { showToast, copyProfileUrlToClipboard} from "../../utils";
import { Spinner } from "react-bootstrap";
import { parsePath } from "../files/pathHelper";
import { url } from "inspector";

type ProfileViewProps = {
  cursor: MocapS3Cursor;
};

type SearchResultProps = {
  cursor: MocapS3Cursor;
  filePath: string;
  urlId: string;
  userName: string;
};

const SearchResult = (props: SearchResultProps) => {
  const filtered = props.filePath.replace("protected/us-west-2:", "").replace('/_SEARCH', '');
  const parts = filtered.split('/');

  const [description, setDescription] = useState("")

  let link_search = ""
  if (parts.length === 2)
    link_search = "protected/" + props.cursor.s3Index.region + ":" + props.urlId + "/data/_search.json"
  else
    link_search = "protected/" + props.cursor.s3Index.region + ":" + props.urlId + "/data/" + parts.slice(2).join('/') + "/_search.json"
  props.cursor.s3Index.downloadText(link_search).then(
    function(text:string) {
      const searchObject = JSON.parse(text);
      setDescription(searchObject.notes)
    }
  );

  if (parts.length === 2) {
    const userId = parts[0];
    if(userId === props.urlId) {
      return (
        <Col md="4">
          <Card>
            <Card.Body>
              <h4><Link to={'/data/' + userId}>Main Folder</Link></h4>
              By <Link to={'/profile/' + userId}>{props.userName}</Link>
              <p></p>
              <p>{description}</p>
              <p></p>
              <span className="badge bg-success">Tag 1</span> <span className="badge bg-success">Tag 2</span> <span className="badge bg-success">Tag 3</span>
            </Card.Body>
          </Card>
        </Col>
      )
    } else {
      return null;
    }
  }
  else if (parts.length > 2) {
    const userId = parts[0];
    if(userId === props.urlId) {
      let linkDataset = '/data/' + userId + '/' + parts.slice(2).join('/');
      let linkUser = '/profile/' + userId;
      return (
        <Col md="4">
          <Card>
            <Card.Body>
              <h4><Link to={linkDataset}>{"/" + parts.slice(2).join('/')}</Link></h4>
              By <Link to={linkUser}>{props.userName}</Link>
              <p></p>
              <p>{description}</p>
              <p></p>
              <span className="badge bg-success">Tag 1</span> <span className="badge bg-success">Tag 2</span> <span className="badge bg-success">Tag 3</span>
            </Card.Body>
          </Card>
        </Col>
      )
    } else {
      return null;
    }
  }
  else {
    return null;
  }
};

const ProfileView = observer((props: ProfileViewProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  const s3Index = props.cursor.s3Index;

  const [editing, setEditing] = useState(false)
  const [validUser, setValidUser] = useState(false);

  let urlId = useLocation().pathname.substring(useLocation().pathname.lastIndexOf('/') + 1);

  let name = props.cursor.profileJson.getAttribute("name", "");
  let surname = props.cursor.profileJson.getAttribute("surname", "");
  let contact = props.cursor.profileJson.getAttribute("contact", "");
  let affiliation = props.cursor.profileJson.getAttribute("affiliation", "");
  let personalWebsite = props.cursor.profileJson.getAttribute("personalWebsite", "");
  let lab = props.cursor.profileJson.getAttribute("lab", "");
  let fullName = ""


  if (name !== "" && surname !== "")
    fullName = (name + " " + surname)
  else if  (name === "" && surname !== "")
    fullName = (surname)
  else if (name !== "" && surname === "")
    fullName = (name)
  else fullName = ("")

  // Search for this user's public datasets.
  const result = props.cursor.searchIndex.results;
  const availableOptions = [...result.keys()];
  let body = null;
  if(urlId != null) {
    if (props.cursor.getIsLoading()) {
      body = <Spinner animation="border" />;
    }
    else {
      body = <>
          {
          availableOptions.map((v) => {
              return <SearchResult cursor={props.cursor} filePath={v} urlId={urlId} userName={fullName}/>
          })}
      </>
    }
  }

  useEffect(() => {
    props.cursor.searchIndex.startListening();
    return () => {
      props.cursor.searchIndex.stopListening();
    }
  }, []);

  function Redirect() {
    // If the user is authenticated, but the current path is profile...
    if(props.cursor.authenticated && (location.pathname === '/profile' || location.pathname === '/profile/')) {
      // Go to user's profile.
      navigate("/profile/" + encodeURIComponent(s3Index.myIdentityId));
      urlId = s3Index.myIdentityId;
    // If the user is not authenticated...
    } else if (!props.cursor.authenticated) {
      // Go to login.
      navigate("/login/");
    }
  }

  useEffect(() => {
    Auth.currentCredentials().then((credentials) => {
      Redirect();
  
      let path = parsePath(location.pathname, urlId);
      if (!path.dataPath.includes("undefined"))
        props.cursor.setDataPath(path.dataPath);

      props.cursor.s3Index.loadFolder(path.dataPath.replace("data/", ""), true).then((results) => {
        if(results.files.length > 0 || results.folders.length > 0)
            setValidUser(true)
      });
    });

    }, [location.pathname]);
  
  function generate_input_field(valueField:any, label:string, tooltip:string, placeholder:string, attributeName:string, icon:string) {
    return (
      <form className="row g-3 mb-15">
        <div className="col-md-4">
          <label>
            <i className={"mdi me-1 vertical-middle " + icon}></i>
            {label}:
            <OverlayTrigger
              placement="right"
              delay={{ show: 50, hide: 400 }}
              overlay={(props) => (
                <Tooltip id="button-tooltip" {...props}>
                  {tooltip}
                </Tooltip>
              )}>
              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
            </OverlayTrigger></label>
          <br></br>
          <input
            type="text"
            className="form-control"
            placeholder={placeholder}
            value={valueField}
            onChange={function(e) {props.cursor.profileJson.setAttribute(attributeName, e.target.value);}}>
          </input>
        </div>
      </form>
    );
  }

  function generate_info_row(valueField:any, label:string, icon:string, show:boolean=true, link:string = "") {
    if (show)
      return (
        <div>
          <div className="row">
            <div className="col-sm-3">
              <p className="mb-0">
                <i className={"mdi me-1 vertical-middle " + icon}></i>
                {label}
              </p>
            </div>
            <div className="col-sm-9">
              {/*
                If link is not empty, insert an "<a href='...'></a> arount the paragraph."
              */}
              {link !== ""
                ?
                  <a href={link} target="_blank" rel="noreferrer">
                    <p className="mb-0">
                      {valueField}
                    </p>
                  </a>
                :
                  <p className="mb-0">
                    {valueField}
                  </p>
              }
            </div>
          </div>
          <hr></hr>
        </div>
      );
    else return ('')
  }

  return (
    <>
      <Row className="mt-3">
        <Col md="12">
          <Card className="mt-4">
            <Card.Body>
              <div>
                  {
                  /* By default show name and surname. If name is not available, show only surname.
                  If none is available, show user id. */
                  (() => {

                    if (props.cursor.getIsLoading()) {
                      return (
                        <tr key="loading">
                          <td colSpan={4}>
                            <p> Loading profile of user with ID: {urlId}</p>
                            <Spinner animation="border" />
                          </td>
                        </tr>
                      );
                    } else {
                      if(validUser) {
                        if (editing && s3Index.myIdentityId === urlId) {
                          return (
                            <div className="container">
                            <div className="justify-content-md-center">
                              {generate_input_field(name, "Name", "Insert your name.", "Your name...", "name", "mdi-account")}
                              {generate_input_field(surname, "Surname", "Insert your surname.", "Your surname...", "surname", "mdi-account-star")}
                              {generate_input_field(contact, "Contact", "Insert your contact e-mail.", "Your contact e-mail...", "contact", "mdi-email-box")}
                              {generate_input_field(personalWebsite, "Personal Website", "Insert your personal website.", "Your personal website...", "personalWebsite", "mdi-at")}
                              {generate_input_field(affiliation, "Affiliation", "Insert your affiliation.", "Your affiliation...", "affiliation", "mdi-school-outline")}
                              {generate_input_field(lab, "Lab", "Insert your lab.", "Your lab...", "lab", "mdi-test-tube")}
                              <button type="button" className="btn btn-primary" onClick={() => {setEditing(false); showToast("Profile updated.", "info");}}>Finish</button>
                            </div>
                            </div>
                          );
                        } else if (!editing){
                          return (
                            <div className="row">
                            <div className="col-lg-4">
                              <div className="card mb-4">
                                <div className="card-body text-center">
                                <img src="https://addbiomechanics.org/img/logo.svg" alt="avatar" className="rounded-circle img-fluid w-25"></img>
                                  {
                                    /* By default show name and surname. If name is not available, show only surname.
                                    If none is available, show user id. */
                                    (() => {
                                      return (
                                        <div>
                                          <button type="button" onClick={() => {copyProfileUrlToClipboard(urlId)}} className="btn btn-link m-0 p-0">
                                            <h5 className="my-3">
                                              {name !== "" ? name : ""}
                                              {name !== "" && surname !== "" ? " " : ""}
                                              {surname !== "" ? surname : ""}
                                              {name === "" && surname === "" ? "User ID: " + urlId : ""}
                                              {" "}
                                              <i className="mdi mdi-share me-1 vertical-middle"></i>
                                            </h5>
                                          </button>
                                        </div>
                                      );
                                    })()
                                  }
                                  <p className="mb-1">{affiliation}</p>
                                  <p className="mb-1">{lab}</p>
                                  {(() => {
                                    /* Show contact button only if there is an email. */
                                      if (contact !== "") {
                                        return (
                                          <a href={"mailto:" + contact} target="_blank" className="link-primary mb-1" rel="noreferrer">
                                            <p className="mb-1">
                                            <i className="mdi mdi-email-box me-1 vertical-middle"></i>
                                              Contact
                                            </p>
                                          </a>
                                        );
                                      }
                                  })()}
                                  <div className="mb-4"></div>
                                  {
                                    /* Only show edit button if this is your profile. */
                                    (() => {
                                      if(s3Index.myIdentityId === urlId) {
                                        return (
                                          <button type="button" className="btn btn-primary" onClick={() => {setEditing(true);}}>Edit Profile</button>
                                        );
                                      } 
                                    })()}
                                </div>
                              </div> 
                              
                            </div>
                            <div className="col-lg-8">
                              <div className="card mb-4">
                                <div className="card-body">
                                  {generate_info_row(fullName, "Full Name", "mdi-account", name !== "" || surname !== "")}
                                  {generate_info_row(contact, "Email", "mdi-email-box", contact !== "", "mailto:" + contact)}
                                  {generate_info_row(personalWebsite, "Personal Website", "mdi-at", personalWebsite !== "", "https://" + personalWebsite)}

                                  {/*User ID is not generated using "generate_info_row" because it has a custom onclick for the <a></a> element*/}
                                  {/*Consider creating a function for this, or modify generate_info_row, just in case it is needed in the future.*/}
                                  <div>
                                    <div className="row">
                                      <div className="col-sm-3">
                                        <p className="mb-0">
                                          <i className="mdi mdi-identifier me-1 vertical-middle"></i>
                                          User ID
                                        </p>
                                      </div>
                                      <div className="col-sm-9">
                                      <button type="button" onClick={() => {copyProfileUrlToClipboard(urlId)}} className="btn btn-link m-0 p-0">
                                        <p className="mb-0">{urlId + " "}
                                          <i className="mdi mdi-share me-1 vertical-middle"></i>
                                        </p>
                                      </button>
                                    <div>
                                      <div className="row">
                                        <div className="col-sm-3">
                                          <p className="mb-0">
                                            <i className="mdi mdi-identifier me-1 vertical-middle"></i>
                                            User ID
                                          </p>
                                        </div>
                                        <div className="col-sm-9">
                                          <a href="javascript:void(0)" role="button" onClick={() => {copyProfileUrlToClipboard(urlId)}}>
                                            <p className="mb-0">{urlId + " "}
                                              <i className="mdi mdi-share me-1 vertical-middle">
                                              </i>
                                            </p>
                                          </a>
                                        </div>

                                      </div>
                                    </div>
                                  </div>

                                </div>
                              </div>
                            </div>

                            <Row>
                              <Col md="12">
                                <Card>
                                  <Card.Body>
                                    <div className="mb-4">
                                      <h3>Public Datasets</h3>
                                    </div>
                                    <Row>
                                      {body}
                                    </Row>
                                  </Card.Body>
                                </Card>
                              </Col>
                            </Row>
                          </div>
                          );

                        }
                      } else {
                        return (
                          <p>There is no user with the following id: {urlId}</p>
                        );
                      }
                      
                    }
                  })()}
                  
              </div>

            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
});

export default ProfileView;
