import React, { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Button, Spinner, Form } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import { MocapFolder, parsePathParts } from "../../state/MocapS3";

type DeleteFolderModalProps = {
  myRootFolder: MocapFolder;
  linkPrefix: string;
};

const DeleteFolderModal = observer((props: DeleteFolderModalProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  const [folderName, setFolderName] = useState("");
  const [valid, setValid] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  let show = location.search.startsWith("?delete-folder=");
  let folderToDelete = "";
  if (show) {
    folderToDelete = decodeURIComponent(
      location.search.substr("?delete-folder=".length)
    );
  }

  let hideModal = () => {
    navigate({ search: "" });
  };

  const path = parsePathParts(location.pathname, props.linkPrefix);

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
            <Form.Label>
              This cannot be undone! Confirm to make sure.
            </Form.Label>
            <Form.Control
              type="text"
              value={folderName}
              onChange={(e) => {
                setFolderName(e.target.value);
                let isValid = e.target.value === folderToDelete;
                console.log(isValid);
                if (!isValid) {
                  e.target.setCustomValidity("Must match folder name");
                  setValid(false);
                } else {
                  e.target.setCustomValidity("");
                  setValid(true);
                }
              }}
              isInvalid={!valid}
            />
            <Form.Text className="text-muted">
              Please re-type "{folderToDelete}" to confirm that you really want
              to delete.
            </Form.Text>
            <Form.Control.Feedback type="invalid">
              You must re-type "{folderToDelete}" exactly
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
          <Modal.Title>Delete Folder "{folderToDelete}"</Modal.Title>
        </Modal.Header>
        <Modal.Body>{body}</Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={hideModal}>
            Close
          </Button>
          <Button
            variant="danger"
            disabled={!valid}
            onClick={() => {
              if (folderName.length === 0) {
                setValid(false);
              } else if (valid) {
                setLoading(true);
                props.myRootFolder
                  .deleteByPrefix(path, folderName)
                  .then(() => {
                    setLoading(false);
                    hideModal();
                  })
                  .catch((e) => {
                    setLoading(false);
                    setError(e);
                  });
              }
            }}
          >
            Delete Folder
          </Button>
        </Modal.Footer>
      </Modal>
    </>
  );
});

export default DeleteFolderModal;
