// @flow
import React, { useState } from "react";
import { Button, Alert, Row, Col } from "react-bootstrap";
import * as yup from "yup";
import { yupResolver } from "@hookform/resolvers/yup";
import { useTranslation } from "react-i18next";
import {
  Link,
  useLocation,
  createSearchParams,
  useSearchParams,
} from "react-router-dom";
import { Auth } from "aws-amplify";

// components
import VerticalForm from "../../components/VerticalForm";
import FormInput from "../../components/FormInput";

import AccountLayout from "./AccountLayout";

/* bottom link */
const BottomLink = () => {
  let location = useLocation();
  const { t } = useTranslation();

  return (
    <Row className="mt-3">
      <Col className="text-center">
        <p className="text-muted">
          {t("Back to")}{" "}
          <Link
            to={"/login"}
            className="text-muted ms-1"
            state={{ from: location.state?.from }}
          >
            <b>{t("Log In")}</b>
          </Link>
        </p>
      </Col>
    </Row>
  );
};

const ForgetPassword = () => {
  const { t } = useTranslation();
  let location = useLocation();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [email, setEmail] = useState("");
  const [error, setError] = useState(null as null | string);
  let searchParams = useSearchParams()[0];

  function handleSubmit(value: { [key: string]: any }) {
    let email = value["email"] as string;

    // Send confirmation code to user's email
    setLoading(true);
    setError(null);
    Auth.forgotPassword(email)
      .then(() => {
        setLoading(false);
        setSuccess(true);
        setEmail(email);
      })
      .catch((e: Error) => {
        setLoading(false);
        setError(e.message);
      });
  }

  /*
   * form validation schema
   */
  const schemaResolver = yupResolver(
    yup.object().shape({
      email: yup
        .string()
        .required(t("Please enter Email"))
        .email(t("Please enter valid Email")),
    })
  );

  return (
    <>
      <AccountLayout bottomLinks={<BottomLink />}>
        <div className="text-center m-auto">
          <h4 className="text-dark-50 text-center mt-0 font-weight-bold">
            {t("Reset Password")}
          </h4>
          <p className="text-muted mb-4">
            {t(
              "Enter your email address and we'll send you an email with instructions to reset your password"
            )}
          </p>
        </div>

        {success && (
          <Alert variant="success">
            <p>{t("We've sent a code to your email!")}</p>
            <Link
              to={{
                pathname: "/enter-confirmation-code",
                search: `?${createSearchParams({ email })}`,
              }}
              state={{ from: location.state?.from }}
            >
              {t("Click here to enter your code")}
            </Link>
          </Alert>
        )}

        {error && (
          <Alert variant="danger" className="my-2">
            {error}
          </Alert>
        )}

        <VerticalForm
          onSubmit={handleSubmit}
          resolver={schemaResolver}
          defaultValues={{ email: searchParams.get("email") || "" }}
        >
          <FormInput
            label={t("Email")}
            type="text"
            name="email"
            placeholder={t("Enter your Email")}
            containerClass={"mb-3"}
          />

          <div className="mb-3 mb-0 text-center">
            <Button variant="primary" type="submit" disabled={loading}>
              {t("Submit")}
            </Button>
          </div>
        </VerticalForm>

        <div className="text-center m-auto">
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
      </AccountLayout>
    </>
  );
};

export default ForgetPassword;
