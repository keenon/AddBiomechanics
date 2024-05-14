import React from "react";
import { Row, Col } from "react-bootstrap";

const Footer = () => {
  const currentYear = new Date().getFullYear();
  return (
    <React.Fragment>
      <footer className="footer bg-white">
        <div className="container-fluid">
          <Row>
            <Col md={12}>{currentYear} © Stanford University</Col>
          </Row>
        </div>
      </footer>
    </React.Fragment>
  );
};

export default Footer;
