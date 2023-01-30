import { useState, useEffect } from "react";
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



type ProfileViewProps = {
  cursor: MocapS3Cursor;
};

type ProfileJSON = {
  name:string;
  surname:string;
  contact:string;
  affiliation:string;
  personalWebsite:string;
  lab:string;
}

const ProfileView = observer((props: ProfileViewProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  const [editing, setEditing] = useState(false)

  const s3Index = props.cursor.s3Index;
  const [name, setName] = useState("");
  const [surname, setSurname] = useState("");
  const [contact, setContact] = useState("");
  const [affiliation, setAffiliation] = useState("");
  const [personalWebsite, setPersonalWebsite] = useState("");
  const [lab, setLab] = useState("");
  const [urlId, setUrlId] = useState(useLocation().pathname.substring(useLocation().pathname.lastIndexOf('/') + 1));

  const [validUser, setValidUser] = useState(false);

  let typingTimeout: null | ReturnType<typeof setTimeout> = null

  function generateProfileJson(name:string, surname:string, contact:string, affiliation:string, personalWebsite:string, lab:string) {
    let profile:ProfileJSON = {"name": name, "surname":surname, "contact":contact, "affiliation":affiliation, "personalWebsite":personalWebsite, "lab":lab};
    return profile;
  }

  function uploadProfileName(name:string) {
    if (typingTimeout !== null) {
      clearTimeout(typingTimeout);
    }
    
    typingTimeout = setTimeout(function () {
      const profile:ProfileJSON = generateProfileJson(name, surname, contact, affiliation, personalWebsite, lab)
      s3Index.upload("protected/" + s3Index.region + ":" + s3Index.myIdentityId + "/profile.json", JSON.stringify(profile));
    }, 500)
  }

  function uploadProfileSurname(surname:string) {
    if (typingTimeout !== null) {
      clearTimeout(typingTimeout);
    }
    
    typingTimeout = setTimeout(function () {
      const profile:ProfileJSON = generateProfileJson(name, surname, contact, affiliation, personalWebsite, lab)
      s3Index.upload("protected/" + s3Index.region + ":" + s3Index.myIdentityId + "/profile.json", JSON.stringify(profile));
    }, 500)
  }

  function uploadProfileContact(contact:string) {
    if (typingTimeout !== null) {
      clearTimeout(typingTimeout);
    }
    
    typingTimeout = setTimeout(function () {
      const profile:ProfileJSON = generateProfileJson(name, surname, contact, affiliation, personalWebsite, lab)
      s3Index.upload("protected/" + s3Index.region + ":" + s3Index.myIdentityId + "/profile.json", JSON.stringify(profile));
    }, 500)
  }

  function uploadProfileAffiliation(affiliation:string) {
    if (typingTimeout !== null) {
      clearTimeout(typingTimeout);
    }
    
    typingTimeout = setTimeout(function () {
      const profile:ProfileJSON = generateProfileJson(name, surname, contact, affiliation, personalWebsite, lab)
      s3Index.upload("protected/" + s3Index.region + ":" + s3Index.myIdentityId + "/profile.json", JSON.stringify(profile));
    }, 500)
  }

  function uploadProfilePersonalWebsite(personalWebsite:string) {
    if (typingTimeout !== null) {
      clearTimeout(typingTimeout);
    }
    
    typingTimeout = setTimeout(function () {
      const profile:ProfileJSON = generateProfileJson(name, surname, contact, affiliation, personalWebsite, lab)
      s3Index.upload("protected/" + s3Index.region + ":" + s3Index.myIdentityId + "/profile.json", JSON.stringify(profile));
    }, 500)
  }

  function uploadProfileLab(lab:string) {
    if (typingTimeout !== null) {
      clearTimeout(typingTimeout);
    }
    
    typingTimeout = setTimeout(function () {
      const profile:ProfileJSON = generateProfileJson(name, surname, contact, affiliation, personalWebsite, lab)
      s3Index.upload("protected/" + s3Index.region + ":" + s3Index.myIdentityId + "/profile.json", JSON.stringify(profile));
    }, 500)
  }

  function setProfileName(name:string) {
    uploadProfileName(name);
    setName(name);
  }

  function setProfileSurname(surname:string) {
    uploadProfileSurname(surname);
    setSurname(surname);
  }

  function setProfileContact(contact:string) {
    uploadProfileContact(contact);
    setContact(contact);
  }

  function setProfileAffiliation(affiliation:string) {
    uploadProfileAffiliation(affiliation);
    setAffiliation(affiliation);
  }

  function setProfilePersonalWebsite(personalWebsite:string) {
    uploadProfilePersonalWebsite(personalWebsite);
    setPersonalWebsite(personalWebsite);
  }

  function setProfileLab(lab:string) {
    uploadProfileLab(lab);
    setLab(lab);
  }

  function Redirect() {
    if(urlId == "" || urlId == "profile") {
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

  function DownloadProfile() {
      s3Index.downloadText("protected/" + s3Index.region + ":" + urlId + "/profile.json").then(function(text: string) {
        const profileObject:ProfileJSON = JSON.parse(text);
        if(text == "" && text.includes("The specified key does not exist.")) {
          setValidUser(false)
        } else {
          setName(profileObject.name);
          setSurname(profileObject.surname);
          setContact(profileObject.contact);
          setAffiliation(profileObject.affiliation);
          setPersonalWebsite(profileObject.personalWebsite);
          setLab(profileObject.lab);
          setValidUser(true)
        }
      });
  }

  useEffect(() => {
    Auth.currentCredentials().then((credentials) => {
      Redirect();
      DownloadProfile();
    })
  }, [location.pathname, s3Index.myIdentityId, urlId]);


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
                    if(validUser) {
                      if (editing && s3Index.myIdentityId === urlId) {
                        return (
                          <div className="container">
                          <div className="justify-content-md-center">
                            <form className="row g-3 mb-15">
                              <div className="col-md-4">
                                <label>Name:
                                  <OverlayTrigger
                                    placement="right"
                                    delay={{ show: 50, hide: 400 }}
                                    overlay={(props) => (
                                      <Tooltip id="button-tooltip" {...props}>
                                        Insert your name.
                                      </Tooltip>
                                    )}>
                                    <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                                  </OverlayTrigger></label>
                                <br></br>
                                <input
                                  type="text"
                                  className="form-control"
                                  placeholder="Your name..."
                                  value={name}
                                  onChange={function(e) {setProfileName(e.target.value)}}>
                                </input>
                              </div>
                            </form>

                            <form className="row g-3 mb-15">
                              <div className="col-md-4">
                                <label>Surname:
                                  <OverlayTrigger
                                    placement="right"
                                    delay={{ show: 50, hide: 400 }}
                                    overlay={(props) => (
                                      <Tooltip id="button-tooltip" {...props}>
                                        Insert your surname.
                                      </Tooltip>
                                    )}>
                                    <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                                  </OverlayTrigger></label>
                                <br></br>
                                <input
                                  type="text"
                                  className="form-control"
                                  placeholder="Your surname..."
                                  value={surname}
                                  onChange={function(e) {setProfileSurname(e.target.value)}}>
                                </input>
                              </div>
                            </form>


                            <form className="row g-3 mb-15">
                              <div className="col-md-4">
                                <label>contact:
                                  <OverlayTrigger
                                    placement="right"
                                    delay={{ show: 50, hide: 400 }}
                                    overlay={(props) => (
                                      <Tooltip id="button-tooltip" {...props}>
                                        Insert your contact e-mail.
                                      </Tooltip>
                                    )}>
                                    <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                                  </OverlayTrigger></label>
                                <br></br>
                                <input
                                  type="text"
                                  className="form-control"
                                  placeholder="Your contact e-mail..."
                                  value={contact}
                                  onChange={function(e) {setProfileContact(e.target.value)}}>
                                </input>
                              </div>
                            </form>

                            <form className="row g-3 mb-15">
                              <div className="col-md-4">
                                <label>Personal Website:
                                  <OverlayTrigger
                                    placement="right"
                                    delay={{ show: 50, hide: 400 }}
                                    overlay={(props) => (
                                      <Tooltip id="button-tooltip" {...props}>
                                        Insert your personal website.
                                      </Tooltip>
                                    )}>
                                    <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                                  </OverlayTrigger></label>
                                <br></br>
                                <input
                                  type="text"
                                  className="form-control"
                                  placeholder="Your personal website..."
                                  value={personalWebsite}
                                  onChange={function(e) {setProfilePersonalWebsite(e.target.value)}}>
                                </input>
                              </div>
                            </form>


                            <form className="row g-3 mb-15">
                              <div className="col-md-4">
                                <label>Affiliation:
                                  <OverlayTrigger
                                    placement="right"
                                    delay={{ show: 50, hide: 400 }}
                                    overlay={(props) => (
                                      <Tooltip id="button-tooltip" {...props}>
                                        Insert your affiliation.
                                      </Tooltip>
                                    )}>
                                    <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                                  </OverlayTrigger></label>
                                <br></br>
                                <input
                                  type="text"
                                  className="form-control"
                                  placeholder="Your affiliation..."
                                  value={affiliation}
                                  onChange={function(e) {setProfileAffiliation(e.target.value)}}>
                                </input>
                              </div>

                            </form>
                            <form className="row g-3 mb-15">
                              <div className="col-md-4">
                                <label>Lab:
                                  <OverlayTrigger
                                    placement="right"
                                    delay={{ show: 50, hide: 400 }}
                                    overlay={(props) => (
                                      <Tooltip id="button-tooltip" {...props}>
                                        Insert your lab.
                                      </Tooltip>
                                    )}>
                                    <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                                  </OverlayTrigger></label>
                                <br></br>
                                <input
                                  type="text"
                                  className="form-control"
                                  placeholder="Your lab..."
                                  value={lab}
                                  onChange={function(e) {setProfileLab(e.target.value)}}>
                                </input>
                              </div>
                            </form>
                            
                            <button type="button" className="btn btn-primary" onClick={() => {setEditing(false); console.log("EDITING: " + editing);}}>Finish</button>
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
                                <h5 className="my-3">
                                  {
                                  /* By default show name and surname. If name is not available, show only surname.
                                  If none is available, show user id. */
                                  (() => {
                                    if (name != "") {
                                      return (
                                        <h5 className="my-3">
                                          {name + " " + surname}
                                        </h5>
                                      );
                                    } else if (surname != "") {
                                      return (
                                        <h5 className="my-3">
                                          {surname}
                                        </h5>
                                      );
                                    } else {
                                      return (
                                        <h5 className="my-3">
                                          {"User " + s3Index.myIdentityId}
                                        </h5>
                                      );

                                    }
                                  })()}
                                </h5>
                                <p className="mb-1">{affiliation}</p>
                                <p className="mb-1">{lab}</p>
                                <a href={"mail-to:" + contact} className="link-primary mb-4"><p className="mb-4">Contact</p></a>
                                {
                                  /* Only show edit button if this is your profile. */
                                  (() => {
                                    if(s3Index.myIdentityId === urlId) {
                                      return (
                                        <button type="button" className="btn btn-primary" onClick={() => {setEditing(true); console.log("EDITING: " + editing);}}>Edit Profile</button>
                                      );
                                    } 
                                  })()}
                              </div>
                            </div> 
                            
                          </div>
                          <div className="col-lg-8">
                            <div className="card mb-4">
                              <div className="card-body">
                                <div className="row">
                                  <div className="col-sm-3">
                                    <p className="mb-0">Full Name</p>
                                  </div>
                                  <div className="col-sm-9">
                                    <p className="mb-0">{name + " " + surname}</p>
                                  </div>
                                </div>
                                <hr></hr>
                                <div className="row">
                                  <div className="col-sm-3">
                                  <p className="mb-0">Email</p>
                                  </div>
                                  <div className="col-sm-9">
                                  <a href={"mail-to:" + contact}><p className="mb-0">{contact}</p></a>
                                  </div>
                                </div>
                                <hr></hr>
                                
                                {
                                  /* Show website only if there is a website. */
                                  (() => {
                                    if (personalWebsite != "") {
                                      return (
                                        <div>
                                          <div className="row">
                                            <div className="col-sm-3">
                                              <p className="mb-0">Personal Website</p>
                                            </div>
                                            <div className="col-sm-9">
                                              <a href={"https://" + personalWebsite}><p className="mb-0">{personalWebsite}</p></a>
                                            </div>
                                          </div>
                                        <hr></hr>
                                        </div>
                                      );
                                    }
                                  })()}





                                </div>
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
