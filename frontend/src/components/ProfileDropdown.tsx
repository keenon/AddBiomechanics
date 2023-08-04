// @flow
import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Auth } from "aws-amplify";
import { CognitoUser } from "amazon-cognito-identity-js";
import Dropdown from 'react-bootstrap/Dropdown';
import './ProfileDropdown.scss';

const STATE_LOADING = "loading";
const STATE_LOGGED_IN = "logged-in";
const STATE_LOGGED_OUT = "logged-out";

const ProfileDropdown = () => {
  const [email, setEmail] = useState("");
  const [loggedInState, setLoggedInState] = useState(STATE_LOADING);

  Auth.currentAuthenticatedUser()
    .then((user: CognitoUser | any) => {
      setLoggedInState(STATE_LOGGED_IN);
      setEmail(user.attributes.email);
    })
    .catch(() => {
      setLoggedInState(STATE_LOGGED_OUT);
    });

  let contents;

  if (loggedInState === STATE_LOADING) {
    contents = <>Loading...</>;
  } else if (loggedInState === STATE_LOGGED_IN) {
    contents = (
      <>
        <Dropdown className="d-none d-lg-block">
          <Dropdown.Toggle className="btn btn-light bg-transparent border-transparent rounded-circle dropdown m-0 p-0 mt-1">
            <img src="https://upload.wikimedia.org/wikipedia/commons/2/2c/Default_pfp.svg" className="rounded-circle image-menu" height="60"></img>
          </Dropdown.Toggle>

          <Dropdown.Menu>
            <Dropdown.Item as={Link} to="/profile">
              <b>Signed in as:</b> {email}
            </Dropdown.Item>
            <hr className="mt-1 mb-1"></hr>
            <Dropdown.Item as={Link} to="/profile">
              <i className={`mdi mdi-account me-1`}></i>
              <span>Your Profile</span>
            </Dropdown.Item>
            <Dropdown.Item as={Link} to="/data">
              <i className={`mdi mdi-magnify me-1`}></i>
              <span>Your Data</span>
            </Dropdown.Item>
            <Dropdown.Item as={Link} to="/server_status">
              <i className={`mdi mdi-server me-1`}></i>
              <span>Processing Server Status</span>
            </Dropdown.Item>
            <hr className="mt-1 mb-1"></hr>
            <Dropdown.Item tag={Link} href="https://simtk.org/plugins/phpBB/indexPhpbb.php?group_id=2402" target="_blank">
              <i className={`mdi mdi-forum me-1`}></i>
              <span>Forum</span>
            </Dropdown.Item>
            <Dropdown.Item tag={Link} href="https://addbiomechanics.org/data.html" target="_blank">
              <i className={`mdi mdi-help me-1`}></i>
              <span>Help</span>
            </Dropdown.Item>
            <Dropdown.Item tag={Link} href="https://addbiomechanics.org/tos.html" target="_blank">
              <i className={`mdi mdi-file-document-edit me-1`}></i>
              <span>Terms of Service</span>
            </Dropdown.Item>
            <Dropdown.Item as={Link} to="/data_sharing_mission">
              <i className={`mdi mdi-share-all me-1`}></i>
              <span>Data Sharing Mission</span>
            </Dropdown.Item>
            <hr className="mt-1 mb-1"></hr>
            <Dropdown.Item as={Link} to="/logout">
              <i className={`mdi mdi-logout me-1`}></i>
              <span>Logout</span>
            </Dropdown.Item>
          </Dropdown.Menu>
        </Dropdown>



      </>
    );
  } else if (loggedInState === STATE_LOGGED_OUT) {
    contents = (
      <>
        Guest{"  "}
        <Link to="/login">
          <i className={`me-1`}></i>
          <span>Log In</span>
        </Link>
      </>
    );
  }

  return (
    <div className="dropdown">
      <div className="nav-link dropdown-toggle arrow-none dropdown-toggle">
        <span className="align-middle">{contents}</span>
      </div>
    </div>
  );
};

export default ProfileDropdown;
