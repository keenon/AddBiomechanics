import React, { useState } from "react";
import "./ResetPassword.scss";
import {
  Link,
  useNavigate,
  useLocation,
  createSearchParams,
  useSearchParams,
} from "react-router-dom";
import { Trans } from "react-i18next";
import { Auth } from "aws-amplify";

const ResetPassword = () => {
  let navigate = useNavigate();
  let location = useLocation();
  let from = location.state?.from?.pathname || "/";
  const [errorMessage, setErrorMessage] = useState("");
  let [searchParams, setSearchParams] = useSearchParams();

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    let formData = new FormData(event.currentTarget);
    let email = formData.get("email") as string;
    let code = formData.get("code") as string;
    let password = formData.get("password") as string;

    // Send confirmation code to user's email
    Auth.forgotPasswordSubmit(email, code, password)
      .then(() => {
        navigate(
          {
            pathname: "/login",
            search: `?${createSearchParams({ email })}`,
          },
          {
            state: { from: location.state?.from },
          }
        );
      })
      .catch((e: Error) => {
        setErrorMessage(e.message);
      });
  }

  return (
    <div>
      <p>
        Enter the code from your email to login and view the page from {from}
      </p>

      <div>{errorMessage}</div>

      <form onSubmit={handleSubmit}>
        <label>
          Email:{" "}
          <input
            name="email"
            type="text"
            defaultValue={searchParams.get("email") || ""}
          />
        </label>{" "}
        <label>
          Code:{" "}
          <input
            name="code"
            type="text"
            defaultValue={searchParams.get("code") || ""}
          />
        </label>{" "}
        <label>
          New Password: <input name="password" type="password" />
        </label>{" "}
        <button type="submit">Reset Password</button>
      </form>

      <Link to="/forgot-password">Get another code</Link>
    </div>
  );
};

export default ResetPassword;
