import React, { useState } from "react";
import { Button, Alert, Row, Col, Form } from "react-bootstrap";
import { useTranslation } from "react-i18next";
import * as yup from "yup";
import { yupResolver } from "@hookform/resolvers/yup";
import {
  Link,
  useNavigate,
  useLocation,
  createSearchParams
} from "react-router-dom";
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

  const Checkbox = (props: any) => {
    const name = props.name;
    const errors = props.errors;
    const register = props.register;
    console.log(errors);
    return (
      <div key={name} className="mb-3">
        <Form.Check>

          <Form.Check.Input type={'checkbox'} name={name} isInvalid={errors && name && errors[name] ? true : false} {...(register ? register(name) : {})} />
          <Form.Check.Label>{props.children}</Form.Check.Label>
          {errors && name && errors[name] ? (
            <Form.Control.Feedback type="invalid">
              {errors[name]["message"]}
            </Form.Control.Feedback>
          ) : null}
        </Form.Check>
      </div>
    )
  }

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
      data: yup.boolean().oneOf([true], "In order to use the freely hosted version you must agree to share data"),
      tos: yup.boolean().oneOf([true], "You must accept the terms of service")
    })
  );

  function handleSubmit(value: { [key: string]: any }) {
    let password = value["password"] as string;
    let email = value["email"] as string;
    let tos = value["tos"] as boolean;
    let data = value["data"] as boolean;
    if (!data) {
      alert("You must agree to share uploaded data in order to use the hosted version of the tool.");
      return;
    }
    if (!tos) {
      alert("You must agree to the Terms of Service in order to use the hosted version of the tool.");
      return;
    }

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
          defaultValues={{ tos: false, data: false }}
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
          <div className="text-center w-75 m-auto">
            <h4 className="text-dark-50 text-center fw-bold" style={{ marginTop: '40px' }}>
              We believe in open data
            </h4>
            <p className="text-muted mb-4">
              We provide this free service in order to encourge more public sharing of human motion data, to enable data-driven breakthroughs in human motion science. While you can choose to not share data you upload, we ask that you share as much as you can.
            </p>
          </div>
          <Checkbox name='data'>I agree to share data I upload with the community</Checkbox>
          <Checkbox name='tos'>I accept the <a href="https://addbiomechanics.org/tos.html" target="_blank">Terms of Service</a></Checkbox>

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
