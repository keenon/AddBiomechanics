import React, { useEffect, useState } from "react";
import {
    useNavigate,
    useLocation,
    Outlet
} from "react-router-dom";
import Session from "../../model/Session";
import { observer } from "mobx-react-lite";

type RequiresAuthProps = {
    session: Session;
}

const RedirectHome = observer((props: RequiresAuthProps) => {
    const navigate = useNavigate();
    const location = useLocation();

    if (!props.session.loadingLoginState) {
        if (!props.session.loggedIn) {
            console.log("User is not logged in. Navigating to /login");
            navigate("/login", { replace: true, state: { from: location } });
        }
        else {
            navigate(props.session.getHomeDirectoryURL(), { replace: true, state: { from: location } });
        }
    }

    return <div>Loading...</div>;
});

export default RedirectHome;