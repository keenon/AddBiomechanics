import React, { useEffect, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Button, Spinner, Form, InputGroup } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import MocapS3Cursor from '../../../state/MocapS3Cursor';

type NewFolderModalProps = {
  cursor: MocapS3Cursor;
  linkPrefix: string;
};

let validation = /^[a-zA-Z0-9-_ ]+$/;

const NewFolderModal = observer((props: NewFolderModalProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  const [folderName, setFolderName] = useState("");
  const [valid, setValid] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  let show =
    location.search === "?new-folder" || location.search === "?new-subject" || location.search === '?new-trial';

  useEffect(() => {
    setFolderName("");
  }, [show]);

  let typeToCreate: "Folder" | "Subject" | "Trial" = "Folder";
  let icon = "";
  if (location.search === "?new-folder") {
    typeToCreate = "Folder";
    icon = "mdi-folder-plus-outline";
  } else if (location.search === "?new-subject") {
    typeToCreate = "Subject";
    icon = "mdi-run";
  } else if (location.search === "?new-trial") {
    typeToCreate = "Trial";
    icon = "mdi-run";
  }


  let hideModal = () => {
    navigate({ search: "" });
  };

  const filePath: string = props.cursor.getCurrentFilePath();

  let body = [];
  if (loading) {
    body.push(<Spinner animation="grow" />);
  } else {
    if (error) {
      body.push(<div key="error">{error}</div>);
    }
    body.push(
      <div key="body">
        <Form noValidate validated={false}>
          <Form.Group className="mb-3" controlId="folderName">
            <Form.Label>{typeToCreate} name</Form.Label>
            <Form.Control
              type="text"
              value={folderName}
              onChange={(e) => {
                setFolderName(e.target.value);
                let isValid = validation.test(e.target.value);
                console.log(isValid);
                if (!isValid) {
                  e.target.setCustomValidity(
                    "Must be non-empty string of letters, numbers, hyphens, underscores and spaces"
                  );
                  setValid(false);
                } else {
                  e.target.setCustomValidity("");
                  setValid(true);
                }
              }}
              isInvalid={!valid}
            />
            <Form.Text className="text-muted">
              The {typeToCreate.toLocaleLowerCase()} to create inside of "{filePath}" in your protected space.
            </Form.Text>
            <Form.Control.Feedback type="invalid">
              Must be non-empty string of letters, numbers, hyphens, underscores
              and spaces.
            </Form.Control.Feedback>
          </Form.Group>
        </Form>
      </div>
    );
  }

  return (
    <>
      <Modal show={show} onHide={hideModal}>
        <Modal.Header closeButton>
          <Modal.Title>
            <i className={"mdi me-1 " + icon}></i> Create {typeToCreate}
          </Modal.Title>
        </Modal.Header>
        <Modal.Body>{body}</Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={hideModal}>
            Close
          </Button>
          <Button
            variant="primary"
            disabled={!valid}
            onClick={() => {
              if (folderName.length === 0) {
                setValid(false);
              } else if (valid) {
                setLoading(true);
                if (typeToCreate == "Trial") {
                  props.cursor
                    .createTrial(folderName)
                    .then(() => {
                      setLoading(false);
                      hideModal();
                    })
                    .catch((e) => {
                      setLoading(false);
                      setError(e);
                    });
                }
                else if (typeToCreate == "Subject") {
                  props.cursor
                    .createMocapClip(folderName)
                    .then(() => {
                      setLoading(false);
                      hideModal();
                    })
                    .catch((e) => {
                      setLoading(false);
                      setError(e);
                    });
                } else {
                  props.cursor
                    .createFolder(folderName)
                    .then(() => {
                      setLoading(false);
                      hideModal();
                    })
                    .catch((e) => {
                      setLoading(false);
                      setError(e);
                    });
                }
              }
            }}
          >
            Create {typeToCreate}
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
});

export default NewFolderModal;
