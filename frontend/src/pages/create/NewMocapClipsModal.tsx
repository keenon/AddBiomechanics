import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Button, Form } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import { MocapFolder } from "../../state/MocapS3";

type NewMocapClipsModalProps = {
  myRootFolder: MocapFolder;
  linkPrefix: string;
};

const NewMocapClipsModal = observer((props: NewMocapClipsModalProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  let show = location.search === "?new-mocap-clips";

  let hideModal = () => {
    navigate({ search: "" });
  };

  return (
    <>
      <Modal show={show} onHide={hideModal}>
        <Modal.Header closeButton>
          <Modal.Title>
            <i className="mdi mdi-run me-1"></i> Upload Mocap Clip(s)
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>
          <p>
            Upload marker files, and we'll automatically scale and fit an
            OpenSim model to your data.
          </p>

          <Form>
            <Form.Group className="mb-3" controlId="ik">
              <Form.Label>*.trc or *.c3d file(s)</Form.Label>
              <Form.Control type="file" accept=".trc,.c3d" multiple />
              <Form.Text className="text-muted">Marker trajectories</Form.Text>
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
            Create Mocap Clip
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
});

export default NewMocapClipsModal;
