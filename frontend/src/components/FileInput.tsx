import React, { useState } from "react";
import { LiveS3File } from "../state/LiveS3";
import { Form, ProgressBar, InputGroup, Button } from "react-bootstrap";
import { observer } from "mobx-react-lite";

type FileInputType = {
  file: LiveS3File;
  name?: string;
  description?: string;
  accept?: string;
  canEdit?: boolean;
};

const FileInput = observer((props: FileInputType) => {
  let [replaceFile, setReplaceFile] = useState(false);

  let body = <></>;
  if (
    props.file.state === "empty" ||
    props.file.state === "staged-for-upload" ||
    props.file.state === "staged-for-overwrite" ||
    (props.file.state === "s3" && replaceFile)
  ) {
    body = (
      <>
        <InputGroup className="mt-1">
          <Form.Control
            type="file"
            accept={props.accept}
            onChange={(e) => {
              props.file.stageFileForUpload(e.target.value);
            }}
          />
          {props.file.state === "staged-for-upload" ||
          props.file.state === "staged-for-overwrite" ? (
            <Button
              variant="outline-success"
              onClick={() => {
                setReplaceFile(false);
                props.file.upload();
              }}
            >
              <i className="mdi mdi-upload-outline me-1"></i>
              Upload
            </Button>
          ) : null}
          {replaceFile ? (
            <Button
              variant="outline-secondary"
              onClick={() => setReplaceFile(false)}
            >
              <i className="mdi mdi-cancel me-1"></i>
              Cancel
            </Button>
          ) : null}
        </InputGroup>
      </>
    );
  } else if (props.file.state === "uploading") {
    body = (
      <>
        <div className="input-group">
          <ProgressBar
            style={{ width: "100%" }}
            min={0}
            max={1}
            now={props.file.uploadProgress}
            striped={true}
            animated={true}
          />
        </div>
      </>
    );
  } else if (props.file.state === "s3") {
    body = (
      <div>
        <div className="input-group">
          <Button
            variant="outline-primary"
            onClick={(e) => {
              props.file.downloadFile();
            }}
          >
            <i className="mdi mdi-download-outline me-1"></i>
            Download
          </Button>
          {props.canEdit ? (
            <Button
              variant="outline-secondary"
              onClick={(e) => {
                setReplaceFile(true);
              }}
            >
              <i className="mdi mdi-upload-outline me-1"></i>
              Replace
            </Button>
          ) : null}
        </div>
      </div>
    );
  }

  if (props.name || props.description) {
    return (
      <>
        <Form.Group className="mb-3">
          <Form.Label>{props.name}</Form.Label>
          {body}
          <Form.Text className="text-muted">{props.description}</Form.Text>
        </Form.Group>
      </>
    );
  } else {
    return body;
  }
});

export default FileInput;
