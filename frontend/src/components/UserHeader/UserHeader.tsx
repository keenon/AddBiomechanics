import React, { useState } from "react";
import "./UserHeader.scss";
import { Link } from "react-router-dom";
import Amplify, { Auth } from "aws-amplify";
import { CognitoUser } from "amazon-cognito-identity-js";
import plus from "./plus.svg";

const STATE_LOADING = "loading";
const STATE_LOGGED_IN = "logged-in";
const STATE_LOGGED_OUT = "logged-out";

function UserHeader({ children }: { children: JSX.Element }) {
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

  let headerContents = null;
  let navContents = null;

  if (loggedInState == STATE_LOADING) {
    headerContents = <>Loading...</>;
  } else if (loggedInState == STATE_LOGGED_IN) {
    headerContents = (
      <>
        <div className="UserHeader__username">{email}</div>
        <div>
          <Link to="/logout">Log Out</Link>
        </div>
      </>
    );
    navContents = (
      <>
        <Link to="/my_uploads">Manage My Data</Link>
      </>
    );
  } else if (loggedInState == STATE_LOGGED_OUT) {
    headerContents = (
      <>
        <Link to="/login">Log In</Link>
      </>
    );
  }

  return (
    <div className="UserHeader">
      <div className="UserHeader__header">
        <div className="UserHeader__nav">
          <Link to="/upload" className="UserHeader__new-data-button">
            <img src={plus} className="UserHeader__new-data-button-plus" />
            Process New Data
          </Link>
          {navContents}
          <Link to="/">View Public Data</Link>
        </div>
        <div className="UserHeader__status">{headerContents}</div>
      </div>
      <div className="UserHeader__body">{children}</div>
    </div>
  );
}

export default UserHeader;
