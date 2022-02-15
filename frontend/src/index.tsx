import React from "react";
import ReactDOM from "react-dom";
import "./index.scss";
import "bootstrap";
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
import ErrorDisplay from "./layouts/ErrorDisplay";

import { ReactiveIndex } from "./state/ReactiveS3";
import MocapS3Cursor from "./state/MocapS3Cursor";
import Amplify, { API, Auth } from "aws-amplify";
import awsExports from "./aws-exports";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import RequireAuth from "./pages/auth/RequireAuth";
import RobustMqtt from "./state/RobustMqtt";

// Verify TS is configured correctly
if (
  !new (class {
    x: any;
  })().hasOwnProperty("x")
)
  throw new Error("Transpiler is not configured correctly");

Amplify.configure(awsExports);

const socket: RobustMqtt = new RobustMqtt("us-west-2", "wss://adup0ijwoz88i-ats.iot.us-west-2.amazonaws.com/mqtt", {
  clean: true,
  keepalive: 10,
  reconnectPeriod: -1,
  resubscribe: false
});
const publicIndex = new ReactiveIndex(awsExports.aws_user_files_s3_bucket_region, awsExports.aws_user_files_s3_bucket, "public", false, socket);
const myData = new ReactiveIndex(awsExports.aws_user_files_s3_bucket_region, awsExports.aws_user_files_s3_bucket, "protected", false, socket);
const cursor = new MocapS3Cursor(publicIndex, myData, socket);

function afterLogin() {
  console.log("Refreshing public data...");
  publicIndex.fullRefresh().then(() => {
    console.log("Refreshing my data...");
    myData.fullRefresh().then(() => {
      console.log("Running PostAuthAPI...");
      // If we're logged in, there's extra steps we have to do to ensure that
      // our account has rights to IOT, so we have to make an extra call to
      // the backend before we set up PubSub
      API.post("PostAuthAPI", "/", {})
        .then((response) => {
          console.log("Adding PubSub plugin...");
          // Apply plugin with configuration
          socket.connect();
          publicIndex.setupPubsub();
          myData.setupPubsub();
        })
        .catch((error) => {
          console.log("Got error with PostAuthAPI!");
          console.log(error.response);
        });
    })
  })
}

Auth.currentAuthenticatedUser()
  .then(() => {
    console.log("Calling afterLogin()");
    afterLogin();
  })
  .catch(() => {
    // If we're not logged in, we can set up the PubSub provider right away
    console.log("Configuring AWSIoTProvider");
    // Apply plugin with configuration
    publicIndex.fullRefresh().then(() => {
      socket.connect();
      publicIndex.setupPubsub();
      myData.setupPubsub();
    });
  });

const PUBLIC_DATA_URL_PREFIX = "public_data";
const MY_DATA_URL_PREFIX = "my_data";

ReactDOM.render(
  <BrowserRouter>
    <Routes>
      <Route element={<ErrorDisplay cursor={cursor} />}>
        <Route index element={<Welcome />} />
        <Route element={<HorizontalLayout />}>
          <Route
            path={"/" + PUBLIC_DATA_URL_PREFIX + "/*"}
            element={
              <Row>
                <Col md="12">
                  <Card className="mt-4">
                    <Card.Body>
                      <FileRouter
                        cursor={cursor}
                        isRootFolderPublic={true}
                        linkPrefix={PUBLIC_DATA_URL_PREFIX}
                      />
                    </Card.Body>
                  </Card>
                </Col>
              </Row>
            }
          ></Route>
          <Route path={"/" + MY_DATA_URL_PREFIX + "/*"} element={<RequireAuth />}>
            <Route
              element={
                <FileControlsWrapper
                  linkPrefix={MY_DATA_URL_PREFIX}
                  cursor={cursor}
                />
              }
            >
              <Route
                path="*"
                element={
                  <FileRouter
                    cursor={cursor}
                    isRootFolderPublic={false}
                    linkPrefix={MY_DATA_URL_PREFIX}
                  />
                }
              ></Route>
            </Route>
          </Route>
        </Route>
        <Route
          path="/login"
          element={
            <Login
              onLogin={() => {
                afterLogin();
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
