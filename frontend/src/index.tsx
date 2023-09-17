import React from "react";
import ReactDOM from "react-dom";
import "./index.scss";
import "bootstrap";
import Login from "./pages/auth/Login";
import Logout from "./pages/auth/Logout";
import SignUp from "./pages/auth/SignUp";
import ForgotPassword from "./pages/auth/ForgotPassword";
import ResetPassword from "./pages/auth/ResetPassword";
import ConfirmUser from "./pages/auth/ConfirmUser";
import DataTypeRouter from "./pages/data/DataTypeRouter";
import RequiresAuth from "./pages/auth/RequiresAuth";
import Amplify, { API, Auth } from "aws-amplify";
import awsExports from "./aws-exports";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { PubSubSocketImpl, PubSubSocket } from "./model/PubSubSocket";
import { S3APIImpl, S3API } from "./model/S3API";
import LiveDirectory, { LiveDirectoryImpl } from "./model/LiveDirectory";
import UserHomeDirectory from "./model/UserHomeDirectory";
import Session from "./model/Session";
import { configure } from "mobx"
import RedirectHome from "./pages/auth/RedirectHome";

configure({
  enforceActions: 'always'
});

// Verify TS is configured correctly
if (
  !new (class {
    x: any;
  })().hasOwnProperty("x")
)
  throw new Error("Transpiler is not configured correctly");

Amplify.configure(awsExports);

const isProd = awsExports.aws_user_files_s3_bucket.indexOf("prod") !== -1;
console.log("Is prod: " + isProd);

// Construct the state objects that will manage our interaction with AWS
const socket: PubSubSocket = new PubSubSocketImpl("us-west-2", "wss://adup0ijwoz88i-ats.iot.us-west-2.amazonaws.com/mqtt", isProd ? "PROD" : "DEV", {
  clean: true,
  keepalive: 10,
  reconnectPeriod: -1,
  resubscribe: false
});
socket.connect();
const s3: S3API = new S3APIImpl(awsExports.aws_user_files_s3_bucket_region, awsExports.aws_user_files_s3_bucket);
const session: Session = new Session(s3, socket, awsExports.aws_user_files_s3_bucket_region);

Auth.currentAuthenticatedUser()
  .then((user: any) => {
    Auth.currentCredentials().then((credentials) => {
      const authenticated = credentials.authenticated;
      const myIdentityId = credentials.identityId.replace("us-west-2:", "");

      if (authenticated) {
        session.setLoggedIn(myIdentityId, user.attributes.email);
      }
      else {
        session.setNotLoggedIn();
      }
    });
  })
  .catch(() => {
    session.setNotLoggedIn();
  });

// On home, we should require authentication. Once authenticated, we should redirect to the data view for the user.
// In the data view, we should not require authentication.

ReactDOM.render(
  <BrowserRouter>
    <Routes>
      <Route index element={<RedirectHome session={session} />}></Route>
      <Route path="/data/*" element={<DataTypeRouter session={session} />} />
      <Route
        path="/login"
        element={
          <Login
            session={session}
            onLogin={(myIdentityId: string, email: string) => {
              session.setLoggedIn(myIdentityId, email);
            }}
          />
        }
      ></Route>
      <Route path="/logout" element={<Logout />}></Route>
      <Route path="/sign-up" element={<SignUp />}></Route>
      <Route path="/forgot-password" element={<ForgotPassword />}></Route>
      <Route path="/reset-password" element={<ResetPassword />}></Route>
      <Route path="/enter-confirmation-code" element={<ConfirmUser />}></Route>
    </Routes>
  </BrowserRouter>,
  document.getElementById("root")
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
// reportWebVitals();
