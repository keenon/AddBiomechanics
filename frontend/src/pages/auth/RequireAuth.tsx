import React, { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Trans } from "react-i18next";
import Amplify, { Auth } from "aws-amplify";

function RequireAuth({ children }: { children: JSX.Element }) {
  let location = useLocation();
  const [authState, setAuthState] = useState("loading");
  Auth.currentAuthenticatedUser()
    .then(() => {
      setAuthState("authenticated");
    })
    .catch(() => {
      // Redirect them to the /login page, but save the current location they were
      // trying to go to when they were redirected. This allows us to send them
      // along to that page after they login, which is a nicer user experience
      // than dropping them off on the home page.
      setAuthState("unauthenticated");
    });

  if (authState == "authenticated") {
    return children;
  } else if (authState == "unauthenticated") {
    return <Navigate to="/login" replace={true} state={{ from: location }} />;
  } else if (authState == "loading" || true) {
    return <div>Loading...</div>;
  }
}

export default RequireAuth;
