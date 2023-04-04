import React from "react";
import ReactDOM from "react-dom";
import "./index.scss";
import "bootstrap";
import { Link } from "react-router-dom";
import { Row, Col, Card } from "react-bootstrap";
import Login from "./pages/auth/Login";
import Logout from "./pages/auth/Logout";
import SignUp from "./pages/auth/SignUp";
import ForgotPassword from "./pages/auth/ForgotPassword";
import ResetPassword from "./pages/auth/ResetPassword";
import ConfirmUser from "./pages/auth/ConfirmUser";
import reportWebVitals from "./reportWebVitals";
import HorizontalLayout from "./layouts/Horizontal";
import FileRouter from "./pages/files/FileRouter";
import FileControlsWrapper from "./pages/files/FileControlsWrapper";
import Welcome from "./pages/Welcome";
import SearchView from "./pages/search/SearchView";
import ProfileView from "./pages/profile/ProfileView";
import ProcessingServerStatus from "./pages/processing_servers/ProcessingServerStatus";
import ErrorDisplay from "./layouts/ErrorDisplay";
import { ReactiveIndex } from "./state/ReactiveS3";
import MocapS3Cursor from "./state/MocapS3Cursor";
import Amplify, { API, Auth } from "aws-amplify";
import awsExports from "./aws-exports";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import RequireAuth from "./pages/auth/RequireAuth";
import RobustMqtt from "./state/RobustMqtt";
import {toast } from 'react-toastify';
import { showToast } from "./utils";

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

const socket: RobustMqtt = new RobustMqtt("us-west-2", "wss://adup0ijwoz88i-ats.iot.us-west-2.amazonaws.com/mqtt", isProd ? "PROD" : "DEV", {
  clean: true,
  keepalive: 10,
  reconnectPeriod: -1,
  resubscribe: false
});
const s3Index = new ReactiveIndex(awsExports.aws_user_files_s3_bucket_region, awsExports.aws_user_files_s3_bucket, false, socket);

s3Index.setIsLoading(true);

const cursor = new MocapS3Cursor(s3Index, socket);

function afterLogin(email: string) {
  console.log("Logged in as " + email);
  cursor.setUserEmail(email);
  console.log("Refreshing S3 data...");
  s3Index.fullRefresh(true).then(() => {
    console.log("Running PostAuthAPI...");
    // If we're logged in, there's extra steps we have to do to ensure that
    // our account has rights to IOT, so we have to make an extra call to
    // the backend before we set up PubSub
    API.post("PostAuthAPI", "/", {})
      .then((response) => {
        console.log("Adding PubSub plugin...");
        // Apply plugin with configuration
        socket.connect();
        s3Index.setupPubsub();

        if (s3Index.authenticated) {
          s3Index.upload("protected/" + s3Index.region + ":" + s3Index.myIdentityId + "/account.json", JSON.stringify({ email }));
          // // This is just here to be convenient for a human searching through the S3 buckets manually
          s3Index.upload("protected/" + s3Index.region + ":" + s3Index.myIdentityId + "/" + email.replace("@", ".AT."), JSON.stringify({ email }));
        }

        cursor.subscribeToCloudProcessingServerPongs();

        // Check if profile.json file is empty. This will show a toast asking users to create a profile after logging in.
        // - If the file profile.json file does not exist, the toast is not shown. This is the case of a user logging in for the first time.
        //   This way, we let users explore the tool the first time they log in, and we only ask them to create the profile the following times.
        // - If the file profile.json file exists, the toast is shown only if there are no values on the file. This is true for users that have
        //   never created a profile page, and for users that have removed their information from their profile page. 
        if(cursor.myProfileJson && cursor.myProfileJson.values && [...cursor.myProfileJson.values.values()].every(value => value === '')) {

          const CustomToastWithLink = () => (
            <div>
              We noticed you have not created a profile. Please click <Link to="/profile">here</Link> to create one!.
            </div>
          );
          showToast(CustomToastWithLink, "info", toast.POSITION.BOTTOM_CENTER, 10000);
        }
      })
      .catch((error) => {
        console.log("Got error with PostAuthAPI!");
        console.log(error.response);
      });
  })
}

Auth.currentAuthenticatedUser()
  .then((user: any) => {
    console.log("Calling afterLogin()");
    afterLogin(user.attributes.email);
  })
  .catch(() => {
    // If we're not logged in, we can set up the PubSub provider right away
    console.log("Configuring AWSIoTProvider");
    // Apply plugin with configuration
    s3Index.fullRefresh().then(() => {
      socket.connect();
      s3Index.setupPubsub();
      cursor.subscribeToCloudProcessingServerPongs();
    });
  });


ReactDOM.render(
  <BrowserRouter>
    <Routes>
      <Route element={<ErrorDisplay cursor={cursor} />}>
        <Route index element={<Welcome />} />
        <Route element={<HorizontalLayout cursor={cursor} />}>
          <Route
            path={"/search/*"}
            element={
              <SearchView cursor={cursor} />
            }
          >
          </Route>
          <Route
            path={"/profile/*"}
            element={
              <ProfileView cursor={cursor} />
            }
          >
          </Route>
          <Route
            path={"/server_status/*"}
            element={
              <ProcessingServerStatus cursor={cursor} />
            }
          ></Route>
          <Route path={"/data/*"}>
            <Route
              element={
                <FileControlsWrapper cursor={cursor} />
              }
            >
              <Route
                path="*"
                element={
                  <FileRouter cursor={cursor} />
                }
              ></Route>
            </Route>
          </Route>
        </Route>
        <Route
          path="/login"
          element={
            <Login
              onLogin={(email: string) => {
                afterLogin(email);
              }}
            />
          }
        ></Route>
        <Route path="/logout" element={<Logout />}></Route>
        <Route path="/sign-up" element={<SignUp />}></Route>
        <Route path="/forgot-password" element={<ForgotPassword />}></Route>
        <Route path="/reset-password" element={<ResetPassword />}></Route>
        <Route path="/enter-confirmation-code" element={<ConfirmUser />}></Route>
      </Route>
    </Routes>
  </BrowserRouter>,
  document.getElementById("root")
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
