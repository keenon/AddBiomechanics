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
import reportWebVitals from "./reportWebVitals";
import HorizontalLayout from "./layouts/Horizontal";
import FileManager from "./pages/FileManager";

import MyMocapUploads from "./state/MyMocapUploads";
import MyUploads from "./pages/MyUploads/MyUploads";
import Amplify, { API } from "aws-amplify";
import { AWSIoTProvider } from "@aws-amplify/pubsub";
import awsExports from "./aws-exports";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import RequireAuth from "./pages/auth/RequireAuth";
import UserData from "./pages/UserData/UserData";
import Home from "./pages/Home/Home";
import UploadManager from "./dead_components/UploadManager/UploadManager";

// Verify TS is configured correctly
if (
  !new (class {
    x: any;
  })().hasOwnProperty("x")
)
  throw new Error("Transpiler is not configured correctly");

Amplify.configure(awsExports);

API.post("PostAuthAPI", "/", {})
  .then((response) => {
    console.log("Got response!");
    console.log(response);

    console.log("Configuring AWSIoTProvider");
    // Apply plugin with configuration
    Amplify.addPluggable(
      new AWSIoTProvider({
        aws_pubsub_region: "us-west-2",
        aws_pubsub_endpoint:
          "wss://adup0ijwoz88i-ats.iot.us-west-2.amazonaws.com/mqtt",
      })
    );
  })
  .catch((error) => {
    console.log(error.response);
  });

const myUploads = new MyMocapUploads("/my_mocap");

ReactDOM.render(
  <BrowserRouter>
    <Routes>
      <Route
        index
        element={
          <HorizontalLayout>
            <FileManager />
          </HorizontalLayout>
        }
      ></Route>
      <Route
        path="/my_uploads"
        element={
          <RequireAuth>
            <MyUploads state={myUploads} />
          </RequireAuth>
        }
      ></Route>
      <Route
        path="/upload"
        element={
          <RequireAuth>
            <UploadManager />
          </RequireAuth>
        }
      ></Route>
      <Route path="/login" element={<Login />}></Route>
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
reportWebVitals();
