import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Button, FormGroup, FormLabel, Form } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import { MocapFolder } from "../../state/MocapS3";

type NewAutoscaleTestProps = {
  myRootFolder: MocapFolder;
  linkPrefix: string;
};

const NewAutoscaleTest = observer((props: NewAutoscaleTestProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  let show = location.search === "?new-autoscale-test";

  let hideModal = () => {
    navigate({ search: "" });
  };

  return (
    <>
      <Modal show={show} onHide={hideModal}>
        <Modal.Header closeButton>
          <Modal.Title>
            <i className="mdi mdi-flask-plus-outline me-1"></i> Help Test
            BiomechNet!
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>
            The automatic processing we do for uploaded motion data is still in
            beta. <b>We'd love your help testing it!</b>
          </p>
          <p>
            When you upload a manually scaled and fit motion capture clip, along
            with the raw marker files, we can run a comparison of the automated
            processing versus the manual fit.
          </p>
          <Form>
            <Form.Group className="mb-3" controlId="ik">
              <Form.Label>Markers *.trc</Form.Label>
              <Form.Control type="file" accept=".trc" />
              <Form.Text className="text-muted">
                The marker trajectories for this motion trial
              </Form.Text>
            </Form.Group>
            <Form.Group className="mb-3" controlId="scaledOsim">
              <Form.Label>Generic Base *.osim</Form.Label>
              <Form.Control type="file" accept=".osim" />
              <Form.Text className="text-muted">
                The generic OpenSim model (including your marker set!),
                unscaled, to use for this experiment.
              </Form.Text>
            </Form.Group>
            <Form.Group className="mb-3" controlId="scaledOsim">
              <Form.Label>Manually scaled *.osim</Form.Label>
              <Form.Control type="file" accept=".osim" />
              <Form.Text className="text-muted">
                The hand-scaled OpenSim model corresponding to the subject of
                this motion trial
              </Form.Text>
            </Form.Group>
            <Form.Group className="mb-3" controlId="ik">
              <Form.Label>IK *.mot</Form.Label>
              <Form.Control type="file" accept=".mot" />
              <Form.Text className="text-muted">
                The OpenSim IK output, corresponding to the subject of this
                motion trial
              </Form.Text>
            </Form.Group>
          </Form>
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={hideModal}>
            Close
          </Button>
          <Button
            variant="primary"
            onClick={() => {
              // props.myRootFolder.ensureFolder(folderName);
              alert("Not implemented yet");
              hideModal();
            }}
          >
            Run Autoscaling Test!
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
});

export default NewAutoscaleTest;
