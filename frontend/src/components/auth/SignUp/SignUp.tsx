import React, { useState } from "react";
import "./SignUp.scss";
import {
  Link,
  useNavigate,
  useLocation,
  createSearchParams,
  useSearchParams,
} from "react-router-dom";
import { Trans } from "react-i18next";
import { Auth } from "aws-amplify";

const SignUp = () => {
  let navigate = useNavigate();
  let location = useLocation();
  let from = location.state?.from?.pathname || "/";
  const [errorMessage, setErrorMessage] = useState("");
  let [searchParams, setSearchParams] = useSearchParams();

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    let formData = new FormData(event.currentTarget);
    let password = formData.get("password") as string;
    let email = formData.get("email") as string;

    Auth.signUp({ username: email, password })
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
      <p>Create an account to view the page at {from}</p>

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
          Password: <input name="password" type="password" />
        </label>{" "}
        <button type="submit">Create Account</button>
      </form>
    </div>
  );
};

export default SignUp;
