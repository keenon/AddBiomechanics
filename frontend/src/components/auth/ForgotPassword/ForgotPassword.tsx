import React, { useState } from "react";
import "./ForgotPassword.scss";
import {
  Link,
  useNavigate,
  useLocation,
  createSearchParams,
  useSearchParams,
} from "react-router-dom";
import { Trans } from "react-i18next";
import { Auth } from "aws-amplify";

const ForgotPassword = () => {
  let navigate = useNavigate();
  let location = useLocation();
  let from = location.state?.from?.pathname || "/";
  const [errorMessage, setErrorMessage] = useState("");
  let [searchParams, setSearchParams] = useSearchParams();

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    let formData = new FormData(event.currentTarget);
    let email = formData.get("email") as string;

    // Send confirmation code to user's email
    Auth.forgotPassword(email)
      .then(() => {
        navigate(
          {
            pathname: "/enter-confirmation-code",
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
      <p>Reset your password to login and view the page from {from}</p>

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
        <button type="submit">Send Password Reset Code</button>
      </form>

      <Link
        to={{
          pathname: "/reset-password",
          search: `?${createSearchParams({
            email: searchParams.get("email") || "",
          })}`,
        }}
        state={{ from: location.state?.from }}
      >
        I already have a password reset code
      </Link>
    </div>
  );
};

export default ForgotPassword;
