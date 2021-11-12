import React, { useState, useEffect } from "react";
import "./Login.scss";
import {
  Link,
  useNavigate,
  useLocation,
  createSearchParams,
  useSearchParams,
} from "react-router-dom";
import { Trans } from "react-i18next";
import { Auth } from "aws-amplify";

const Login = () => {
  let navigate = useNavigate();
  let location = useLocation();
  let [searchParams, setSearchParams] = useSearchParams();

  const [errorMessage, setErrorMessage] = useState("");
  const [pending, setPending] = useState(false);

  let from = location.state?.from?.pathname || "/";

  function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    let formData = new FormData(event.currentTarget);
    let email = formData.get("email") as string;
    let password = formData.get("password") as string;

    setPending(true);
    Auth.signIn(email, password)
      .then(() => {
        // Send them back to the page they tried to visit when they were
        // redirected to the login page. Use { replace: true } so we don't create
        // another entry in the history stack for the login page.  This means that
        // when they get to the protected page and click the back button, they
        // won't end up back on the login page, which is also really nice for the
        // user experience.
        navigate(from, { replace: true });
      })
      .catch((reason: Error) => {
        setPending(false);
        if (reason.name == "UserNotConfirmedException") {
          navigate(
            {
              pathname: "/enter-confirmation-code",
              search: `?${createSearchParams({ email })}`,
            },
            {
              state: { from: location.state?.from },
            }
          );
        } else {
          setErrorMessage(reason.message);
        }
      });
  }

  let errorBanner = null;
  if (errorMessage != "") {
    errorBanner = <div>{errorMessage}</div>;
  }

  let loginBanner = null;
  if (from != "/") {
    loginBanner = <p>You must log in to view the page at {from}</p>;
  }

  if (pending) {
    return <div className="Login">Logging you in...</div>;
  }

  return (
    <div className="Login">
      {loginBanner}
      {errorBanner}

      <form onSubmit={handleSubmit} className="Login__form">
        <table>
          <tbody>
            <tr>
              <td>Email</td>
              <td>
                <input
                  name="email"
                  type="text"
                  value={searchParams.get("email") || ""}
                  onChange={(e) => {
                    setSearchParams({ email: e.target.value });
                  }}
                />
              </td>
            </tr>
            <tr>
              <td>Password</td>
              <td>
                <input name="password" type="password" />
              </td>
            </tr>
          </tbody>
        </table>

        <button type="submit">Login</button>
      </form>

      <Link
        to={{
          pathname: "/sign-up",
          search: `?${createSearchParams({
            email: searchParams.get("email") || "",
          })}`,
        }}
        state={{ from: location.state?.from }}
      >
        Create Account
      </Link>
      <Link
        to={{
          pathname: "/forgot-password",
          search: `?${createSearchParams({
            email: searchParams.get("email") || "",
          })}`,
        }}
        state={{ from: location.state?.from }}
      >
        Forgot Password
      </Link>
    </div>
  );
};

export default Login;
