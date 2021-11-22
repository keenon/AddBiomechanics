import React, { useState } from "react";
import { Button, Alert, Row, Col } from "react-bootstrap";
import { useTranslation } from "react-i18next";
import * as yup from "yup";
import { yupResolver } from "@hookform/resolvers/yup";
import {
  Link,
  useNavigate,
  useLocation,
  createSearchParams,
  useSearchParams,
} from "react-router-dom";
import { Trans } from "react-i18next";
import { Auth } from "aws-amplify";

import VerticalForm from "../../components/VerticalForm";
import FormInput from "../../components/FormInput";

import AccountLayout from "./AccountLayout";

/* bottom link */
const BottomLink = () => {
  const { t } = useTranslation();

  return (
    <Row className="mt-3">
      <Col className="text-center">
        <p className="text-muted">
          {t("Already have account?")}{" "}
          <Link to={"/login"} className="text-muted ms-1">
            <b>{t("Log In")}</b>
          </Link>
        </p>
      </Col>
    </Row>
  );
};

const SignUp = () => {
  const { t } = useTranslation();
  let navigate = useNavigate();
  let location = useLocation();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null as null | string);

  /*
   * form validation schema
   */
  const schemaResolver = yupResolver(
    yup.object().shape({
      // fullname: yup.string().required(t("Please enter Fullname")),
      email: yup
        .string()
        .required("Please enter Email")
        .email("Please enter valid Email"),
      password: yup.string().required(t("Please enter Password")),
    })
  );

  function handleSubmit(value: { [key: string]: any }) {
    let password = value["password"] as string;
    let email = value["email"] as string;

    console.log("Signing up!");
    setLoading(true);
    Auth.signUp({ username: email, password })
      .then(() => {
        setLoading(false);
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
        setLoading(false);
        setError(e.message);
      });
  }

  return (
    <>
      <AccountLayout bottomLinks={<BottomLink />}>
        <div className="text-center w-75 m-auto">
          <h4 className="text-dark-50 text-center mt-0 fw-bold">
            {t("Join the Community!")}
          </h4>
          <p className="text-muted mb-4">
            {t(
              "Create your account to start processing and sharing data with the community."
            )}
          </p>
        </div>

        {error && (
          <Alert variant="danger" className="my-2">
            {error}
          </Alert>
        )}

        <VerticalForm
          onSubmit={handleSubmit}
          resolver={schemaResolver}
          defaultValues={{}}
        >
          <FormInput
            label={t("Email address")}
            type="email"
            name="email"
            placeholder={t("Enter your email")}
            containerClass={"mb-3"}
          />
          <FormInput
            label={t("Password")}
            type="password"
            name="password"
            placeholder={t("Enter your password")}
            containerClass={"mb-3"}
          />
          <FormInput
            label={t("I accept Terms and Conditions")}
            type="checkbox"
            name="checkboxsignup"
            containerClass={"mb-3 text-muted"}
          />

          <div className="mb-3 mb-0 text-center">
            <Button variant="primary" type="submit" disabled={loading}>
              {t("Sign Up")}
            </Button>
          </div>
        </VerticalForm>
      </AccountLayout>
    </>
  );
};

export default SignUp;
