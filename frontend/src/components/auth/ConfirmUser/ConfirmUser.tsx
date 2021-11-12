import React, { useState } from "react";
import "./ConfirmUser.scss";
import {
  useNavigate,
  useLocation,
  useSearchParams,
  createSearchParams,
} from "react-router-dom";
import { Auth } from "aws-amplify";

function ConfirmUser() {
  let navigate = useNavigate();
  let location = useLocation();

  const [errorMessage, setErrorMessage] = useState("");
  let [searchParams, setSearchParams] = useSearchParams();

  let from = location.state?.from?.pathname || "/";

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    let formData = new FormData(event.currentTarget);
    let email = formData.get("email") as string;
    let code = formData.get("code") as string;

    Auth.confirmSignUp(email, code)
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
        Enter your confirmation number to activate your account (and then view
        the page at {from})
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
          Verification Code:{" "}
          <input
            name="code"
            type="text"
            defaultValue={searchParams.get("code") || ""}
          />
        </label>{" "}
        <button type="submit">Verify Account</button>
      </form>
    </div>
  );
}

export default ConfirmUser;
