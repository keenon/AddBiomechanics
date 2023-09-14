import React, { useEffect, useState } from "react";
import {
    useNavigate,
    useLocation,
    Outlet
} from "react-router-dom";
import UserHomeDirectory from "../../model/UserHomeDirectory";
import { observer } from "mobx-react-lite";

type RequiresAuthProps = {
    home: UserHomeDirectory;
}

const RequiresAuth = observer((props: RequiresAuthProps) => {
    const navigate = useNavigate();
    const location = useLocation();

    if (!props.home.loadingLoginState && !props.home.authenticated) {
        console.log("User is not logged in. Navigating to /login");
        navigate("/login", { replace: true, state: { from: location } });
    }

    return <Outlet />;
});

export default RequiresAuth;