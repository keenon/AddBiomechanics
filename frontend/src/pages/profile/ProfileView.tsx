import { useState, useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
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

type ProfileViewProps = {
  cursor: MocapS3Cursor;
};

const ProfileView = observer((props: ProfileViewProps) => {
  console.log("LOG: " + Array.from(props.cursor.s3Index.files.keys()))
  console.log("LOG: " + props.cursor.profileJson.getAbsolutePath())
  console.log("LOG: " + props.cursor.s3Index.myIdentityId)

  const location = useLocation();
  const navigate = useNavigate();

  const [editing, setEditing] = useState(false)

  const s3Index = props.cursor.s3Index;
  let name = props.cursor.profileJson.getAttribute("name", "");
  let surname = props.cursor.profileJson.getAttribute("surname", "");
  let contact = props.cursor.profileJson.getAttribute("contact", "");
  let affiliation = props.cursor.profileJson.getAttribute("affiliation", "");
  let personalWebsite = props.cursor.profileJson.getAttribute("personalWebsite", "");
  let lab = props.cursor.profileJson.getAttribute("lab", "");

  let fullName = "";

  if (name !== "" && surname !== "")
    fullName = name + " " + surname
  else if  (name === "" && surname !== "")
    fullName = surname
  else if (name !== "" && surname === "")
    fullName = name
  else fullName = ""

  const [urlId, setUrlId] = useState(useLocation().pathname.substring(useLocation().pathname.lastIndexOf('/') + 1));

  const [validUser, setValidUser] = useState(false);

  function Redirect() {
    if(urlId === "" || urlId === "profile") {
      if ((location.pathname === '/profile' || location.pathname === '/profile/') && s3Index.myIdentityId !== '') {
        if (props.cursor.authenticated) {
          navigate("/profile/" + encodeURIComponent(s3Index.myIdentityId));
        }
        else {
          navigate("/login", { replace: true, state: { from: location } });
        }
      }
      setUrlId(location.pathname.substring(location.pathname.lastIndexOf('/') + 1));
    }
  }

  useEffect(() => {
    Redirect();
  })

  useEffect(() => {
    Auth.currentCredentials().then((credentials) => {
      setValidUser(false)
      // Iterate all files.
      s3Index.files.forEach((v,k) => {
        // Count all files containing the urlId in its path.
        if (k.includes(urlId)) {
          setValidUser(true)
        }
      });
    })
  }, [urlId, s3Index.files]);

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
                                          <button type="button" onClick={() => {copyProfileUrlToClipboard(urlId)}} className="btn btn-link  m-0 p-0">
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

                                      </div>
                                    </div>
                                  </div>

                                </div>
                              </div>
                            </div>

                            <div className="col-lg-12">
                              <div className="card mb-4">
                                <div className="card-body"></div>
                                  <h1>Public Datasets</h1>

                                      {/*TODO: Insert list of public datasets for this user here.*/}

                                </div>
                              </div>
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
