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

const RequiresAuth = observer((props: RequiresAuthProps) => {
    const navigate = useNavigate();
    const location = useLocation();

    if (!props.session.loadingLoginState && !props.session.loggedIn) {
        console.log("User is not logged in. Navigating to /login");
        navigate("/login", { replace: true, state: { from: location } });
    }

    return <Outlet />;
});

export default RequiresAuth;