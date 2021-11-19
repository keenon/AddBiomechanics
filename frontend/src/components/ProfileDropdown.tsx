// @flow
import React, { useState } from "react";
import { Link } from "react-router-dom";
import { Dropdown } from "react-bootstrap";
import { Auth } from "aws-amplify";
import { CognitoUser } from "amazon-cognito-identity-js";

const STATE_LOADING = "loading";
const STATE_LOGGED_IN = "logged-in";
const STATE_LOGGED_OUT = "logged-out";

const ProfileDropdown = () => {
  const [dropdownOpen, setDropdownOpen] = useState(false);
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

  /*
   * toggle profile-dropdown
   */
  const toggleDropdown = () => {
    setDropdownOpen(!dropdownOpen);
  };

  let contents;

  if (loggedInState == STATE_LOADING) {
    contents = <>Loading...</>;
  } else if (loggedInState == STATE_LOGGED_IN) {
    contents = (
      <>
        {email}
        {"  "}

        <Link to="/logout">
          <i className={`mdi mdi-logout me-1`}></i>
          <span>Logout</span>
        </Link>
      </>
    );
  } else if (loggedInState == STATE_LOGGED_OUT) {
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
