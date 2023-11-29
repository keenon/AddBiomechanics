import { useState, useEffect, useReducer } from "react";
import { useLocation, useNavigate, Link } from "react-router-dom";
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
import { showToast, copyProfileUrlToClipboard, getIdFromURL } from "../../utils";
import { Spinner } from "react-bootstrap";
import { parsePath } from "../files/pathHelper";
import { url } from "inspector";
import UserProfile from "../../model/UserProfile"
import Session from "../../model/Session"
import SearchResult from "../search/SearchResult";

type InputFieldProps = {
  userProfile: UserProfile;
  label: string;
  tooltip: string;
  placeholder: string;
  attributeName: string;
  icon: string;
}

const InputField = observer((props: InputFieldProps) => {
  let valueField: string = props.userProfile.getAttribute(props.attributeName, "");
  return (
    <form className="row g-3 mb-15">
      <div className="col-md-12">
        <label>
          <i className={"mdi me-1 vertical-middle " + props.icon}></i>
          {props.label}:
{/*           <OverlayTrigger */}
{/*             placement="right" */}
{/*             delay={{ show: 50, hide: 400 }} */}
{/*             overlay={(props) => ( */}
{/*               <Tooltip id="button-tooltip" {...props}> */}
{/*                 {props.tooltip} */}
{/*               </Tooltip> */}
{/*             )}> */}
{/*             <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i> */}
{/*           </OverlayTrigger> */}
          </label>
        <br></br>
        <input
          type="text"
          className="form-control"
          placeholder={props.placeholder}
          value={valueField}
          onFocus={(e) => props.userProfile.profileJson.onFocusAttribute(props.attributeName)}
          onBlur={(e) => props.userProfile.profileJson.onBlurAttribute(props.attributeName)}
          onChange={(e) => props.userProfile.profileJson.setAttribute(props.attributeName, e.target.value)}>
        </input>
        <div id="citeHelp" className="form-text">{props.tooltip}</div>

      </div>
    </form>
  );
});

type ProfileViewProps = {
  userProfile: UserProfile;
  session: Session;
  userId: string;
};

const ProfileView = observer((props: ProfileViewProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  //const validUser = props.cursor.s3Index.isUserValid(urlId);

  const [editing, setEditing] = useState(false)

  let name: string = props.userProfile.getAttribute("name", "");
  let surname: string = props.userProfile.getAttribute("surname", "");
  let contact: string = props.userProfile.getAttribute("contact", "");
  let affiliation: string = props.userProfile.getAttribute("affiliation", "");
  let personalWebsite: string = props.userProfile.getAttribute("personalWebsite", "");
  let lab: string = props.userProfile.getAttribute("lab", "");
  let fullName: string = props.userProfile.getProfileFullName();

  // Get user's datasets and add to profile.
  const datasetsInfo = props.userProfile.getUserDatasetMetadata();
  let body = null;
  body = <>
    {Array.from(datasetsInfo.entries()).map(([key, dataset], index) => (
      <SearchResult
        key={key}
        folderName={key}
        datasetInfo={dataset}
        numSubjects={0}
        numTrials={0}
        userName={fullName}
        userId={props.userId}
        searchText=''
        index={index}
        fullWidth={false}
      />
    ))}
  </>;


  function generate_info_row(valueField: any, label: string, icon: string, show: boolean = true, link: string = "") {
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

                      if (editing && props.session.userId === props.userId) {
                        return (
                          <div className="container">
                            <div className="justify-content-md-center">
                              <InputField userProfile={props.userProfile} label="First Name" tooltip="Insert your first name." placeholder="Your first name..." attributeName="name" icon="mdi-account" />
                              {/* {generate_input_field(name, "First Name", "Insert your first name.", "Your first name...", "name", "mdi-account")} */}
                              <InputField userProfile={props.userProfile} label="Last Name" tooltip="Insert your last name (surname)." placeholder="Your last name (surname)..." attributeName="surname" icon="mdi-account-star" />
                              {/* {generate_input_field(surname, "Last Name (Surname)", "Insert your last name (surname).", "Your last name (surname)...", "surname", "mdi-account-star")} */}
                              <InputField userProfile={props.userProfile} label="Contact" tooltip="Insert your contact e-mail." placeholder="Your contact e-mail..." attributeName="contact" icon="mdi-email-box" />
                              {/* {generate_input_field(contact, "Contact", "Insert your contact e-mail.", "Your contact e-mail...", "contact", "mdi-email-box")} */}
                              <InputField userProfile={props.userProfile} label="Personal Website" tooltip="Insert your personal website." placeholder="Your personal website..." attributeName="personalWebsite" icon="mdi-at" />
                              {/* {generate_input_field(personalWebsite, "Personal Website", "Insert your personal website.", "Your personal website...", "personalWebsite", "mdi-at")} */}
                              <InputField userProfile={props.userProfile} label="Affiliation" tooltip="Insert your affiliation (university, company...)." placeholder="Your affiliation..." attributeName="affiliation" icon="mdi-school-outline" />
                              {/* {generate_input_field(affiliation, "Affiliation", "Insert your affiliation.", "Your affiliation...", "affiliation", "mdi-school-outline")} */}
                              <InputField userProfile={props.userProfile} label="Lab" tooltip="Insert your lab." placeholder="Your lab..." attributeName="lab" icon="mdi-test-tube" />
                              {/* {generate_input_field(lab, "Lab", "Insert your lab.", "Your lab...", "lab", "mdi-test-tube")} */}

                              <div className="col-md-12">
                                <button type="button" className="btn btn-primary w-100" onClick={() => { navigate("/forgot-password") }}>Change Password</button>
                              </div>
                              <div className="col-md-12">
                                <button type="button" className="btn btn-primary mt-2 w-100" onClick={() => { setEditing(false); showToast("Profile updated.", "info"); }}>Finish</button>
                              </div>
                            </div>
                          </div>
                        );
                      } else if (!editing) {
                        return (
                          <div className="row">
                            <div className="col-lg-4">
                              <div className="card mb-4">
                                <div className="card-body text-center">
                                  <img src="https://upload.wikimedia.org/wikipedia/commons/2/2c/Default_pfp.svg" alt="avatar" className="rounded-circle img-fluid w-25"></img>
                                  {
                                    /* By default show name and surname. If name is not available, show only surname.
                                    If none is available, show user id. */
                                    (() => {
                                      return (
                                        <div>
                                          <button type="button" onClick={() => { copyProfileUrlToClipboard(props.userId) }} className="btn btn-link m-0 p-0">
                                            <h5 className="my-3">
                                              {name !== "" ? name : ""}
                                              {name !== "" && surname !== "" ? " " : ""}
                                              {surname !== "" ? surname : ""}
                                              {name === "" && surname === "" ? "User ID: " + props.userId : ""}
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
                                      if (props.session.userId === props.userId) {
                                        return (
                                          <button type="button" className="btn btn-primary" onClick={() => { setEditing(true); }}>Edit Profile</button>
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
                                  {generate_info_row(personalWebsite, "Personal Website", "mdi-at", personalWebsite !== "", (personalWebsite.startsWith("https://") || personalWebsite.startsWith("http://")) ? personalWebsite : "https://" + personalWebsite)}

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
                                        <button type="button" onClick={() => { copyProfileUrlToClipboard(props.userId) }} className="btn btn-link m-0 p-0">
                                          <p className="mb-0">{props.userId + " "}
                                            <i className="mdi mdi-share me-1 vertical-middle"></i>
                                          </p>
                                        </button>

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
