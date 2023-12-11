import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Row, Col } from "react-bootstrap";
import { Auth } from "aws-amplify";

// components
import AccountLayout from "./AccountLayout";
import { Spinner } from "react-bootstrap";

import logoutIcon from "./logout-icon.svg";

import Session from "../../model/Session";

/* bottom link */
const BottomLink = () => {
  const { t } = useTranslation();

  return (
    <Row className="mt-3">
      <Col className="text-center">
        <p className="text-muted">
          {t("Back to ")}{" "}
          <Link to={"/login"} className="text-muted ms-1">
            <b>{t("Log In")}</b>
          </Link>
        </p>
      </Col>
    </Row>
  );
};

type LogoutProps = {
  session: Session;
};

const Logout = (props: LogoutProps) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Auth.signOut().then(() => {
      setLoading(false);
    });
  }, []);

  let body;
  if (loading) {
    body = <Spinner animation="border" />;
  } else {
    body = <img src={logoutIcon} alt="" />;
  }

  return (
    <>
      <AccountLayout bottomLinks={<BottomLink />}>
        <div className="text-center w-75 m-auto">
          <h4 className="text-dark-50 text-center mt-0 fw-bold">
            {t("See You Again!")}
          </h4>
          <p className="text-muted mb-4">
            {t("You are now successfully signed out.")}
          </p>

          <div className="logout-icon m-auto">{body}</div>
        </div>
      </AccountLayout>
    </>
  );
};

export default Logout;
