import React, { useState } from "react";
import "./Logout.scss";
import { Link } from "react-router-dom";
import { Trans } from "react-i18next";
import { Auth } from "aws-amplify";

const STATE_LOADING = "loading";
const STATE_SUCCESS = "success";
const STATE_ERROR = "error";

const Logout = () => {
  const [logoutState, setLogoutState] = useState(STATE_LOADING);
  const [errorMessage, setErrorMessage] = useState("");

  Auth.signOut()
    .then(() => {
      setLogoutState(STATE_SUCCESS);
    })
    .catch((e: Error) => {
      setLogoutState(STATE_ERROR);
      setErrorMessage(e.message);
    });

  if (logoutState == STATE_LOADING) {
    return <div className="Logout">Logging out...</div>;
  } else if (logoutState == STATE_SUCCESS) {
    return (
      <div className="Logout">
        <div className="Logout__message">We've logged you out!</div>
        <Link to="/">Back Home</Link>
      </div>
    );
  } else if (logoutState == STATE_ERROR) {
    return (
      <div className="Logout">
        Error: {errorMessage}
        <Link to="/">Back Home</Link>
      </div>
    );
  }
  return <div></div>;
};

export default Logout;
