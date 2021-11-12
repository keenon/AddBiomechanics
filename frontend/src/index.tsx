import React from "react";
import ReactDOM from "react-dom";
import "./index.css";
import Login from "./components/auth/Login/Login";
import Logout from "./components/auth/Logout/Logout";
import SignUp from "./components/auth/SignUp/SignUp";
import reportWebVitals from "./reportWebVitals";

import Amplify from "aws-amplify";
import awsExports from "./aws-exports";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import RequireAuth from "./components/auth/RequireAuth/RequireAuth";
import UserData from "./components/UserData/UserData";
import ConfirmUser from "./components/auth/ConfirmUser/ConfirmUser";
import Home from "./components/Home/Home";
import ForgotPassword from "./components/auth/ForgotPassword/ForgotPassword";
import ResetPassword from "./components/auth/ResetPassword/ResetPassword";
import UploadManager from "./components/UploadManager/UploadManager";

Amplify.configure(awsExports);

ReactDOM.render(
  <BrowserRouter>
    <Routes>
      <Route index element={<Home />}></Route>
      <Route
        path="/my_uploads"
        element={
          <RequireAuth>
            <UserData />
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
