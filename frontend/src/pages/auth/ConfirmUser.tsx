// @flow
import React, { useRef, useState } from "react";
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

const ConfirmUser = () => {
  const { t } = useTranslation();
  let location = useLocation();
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(null as null | string);
  let searchParams = useSearchParams()[0];
  const emailRef = useRef(null as HTMLInputElement | null);

  function handleSubmit(value: { [key: string]: any }) {
    let email = value["email"] as string;
    let code = value["code"] as string;

    // Send confirmation code to user's email
    setLoading(true);
    setError(null);

    Auth.confirmSignUp(email, code)
      .then(() => {
        setLoading(false);
        setSuccess(true);
        /*
        navigate(
          {
            pathname: "/login",
            search: `?${createSearchParams({ email })}`,
          },
          {
            state: { from: location.state?.from },
          }
        );
        */
      })
      .catch((e: Error) => {
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
            {t("Activate Account")}
          </h4>
          <p className="text-muted mb-4">
            {t("Enter your confirmation number to activate your account")}
          </p>
        </div>

        {success && (
          <Alert variant="success">
            <p>{t("Your account is activated!")}</p>
            <Link
              to={{
                pathname: "/login",
                search: `?${createSearchParams({ email: (emailRef.current != null ? emailRef.current.value : "") })}`,
              }}
              state={{ from: location.state?.from }}
            >
              {t("Click here to login")}
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
            placeholder={t("Enter your email")}
            refCallback={emailRef}
            containerClass={"mb-3"}
          />
          <FormInput
            label={t("Activation Code")}
            type="text"
            name="code"
            placeholder={t("Enter the code we emailed you")}
            containerClass={"mb-3"}
          />

          <div className="mb-3 mb-0 text-center">
            {success ? null : (
              <Button variant="primary" type="submit" disabled={loading}>
                {t("Submit")}
              </Button>
            )}
          </div>
        </VerticalForm>
      </AccountLayout>
    </>
  );
};

export default ConfirmUser;
