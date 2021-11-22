import React from "react";
import { Button, Row, Col, Card } from "react-bootstrap";
import { useNavigate } from "react-router-dom";

const Welcome = () => {
  const navigate = useNavigate();
  return (
    <Row className="mt-3">
      <Col md="12">
        <Card>
          <Card.Body>
            <h3>Welcome to the BiomechNet community!</h3>
            <p>
              <Button
                size="lg"
                href="/public_data"
                onClick={(e) => {
                  e.preventDefault();
                  navigate("/public_data");
                }}
              >
                <i className="mdi mdi-brain me-1 vertical-middle"></i>
                Browse Public Data
              </Button>
            </p>
            <p>
              <Button
                variant="primary"
                size="lg"
                href="/my_data"
                onClick={(e) => {
                  e.preventDefault();
                  navigate("/my_data");
                }}
              >
                <i className="mdi mdi-run me-1 vertical-middle"></i>
                Process and Share Data
              </Button>
            </p>
          </Card.Body>
        </Card>
      </Col>
    </Row>
  );
};

export default Welcome;
