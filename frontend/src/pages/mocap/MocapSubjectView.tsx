import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { observer } from "mobx-react-lite";
import "./MocapView.scss";
import {
  Button,
  ButtonGroup,
  Dropdown,
  Table,
} from "react-bootstrap";
import DropFile from "../../components/DropFile";
import Dropzone from "react-dropzone";
import MocapTrialModal from "./MocapTrialModal";
import MocapS3Cursor from '../../state/MocapS3Cursor';

type MocapTrialRowViewProps = {
  index: number;
  name: string;
  cursor: MocapS3Cursor;
  uploadFiles: { [key: string]: File; };
};

const MocapTrialRowView = observer((props: MocapTrialRowViewProps) => {
  let status = props.cursor.getTrialStatus(props.name);
  let statusBadge = null;
  if (status === "empty") {
  }
  else if (status === "done") {
    statusBadge = <span className="badge bg-success">Processed</span>;
  }
  else if (status === "processing") {
    statusBadge = <span className="badge bg-warning">Processing</span>;
  }
  else if (status === "could-process") {
    if (props.cursor.canEdit()) {
      statusBadge = <Button onClick={() => props.cursor.markTrialReadyForProcessing(props.name)}>Process</Button>;
    }
    else {
      statusBadge = <span className="badge bg-secondary">Waiting for owner to process</span>;
    }
  }
  else if (status === "waiting") {
    statusBadge = <span className="badge bg-secondary">Waiting for server</span>;
  }

  let manualIKRow = null;
  if (props.cursor.getShowValidationControls()) {
    manualIKRow = (
      <td>
        <DropFile cursor={props.cursor} path={"trials/" + props.name + "/manual_ik.mot"} uploadOnMount={props.uploadFiles[props.name + "_ik.mot"]} accept=".mot" />
      </td>
    );
  }

  return (
    <tr>
      <td>
        <Link
          to={{
            search: "?show-trial=" + props.index,
          }}
        >
          {props.name}
        </Link>
      </td>
      <td>
        <DropFile cursor={props.cursor} path={"trials/" + props.name + "/markers.trc"} uploadOnMount={props.uploadFiles[props.name + ".trc"]} accept=".trc" />
      </td>
      {manualIKRow}
      <td>
        <DropFile cursor={props.cursor} path={"trials/" + props.name + "/grf.mot"} uploadOnMount={props.uploadFiles[props.name + "_grf.mot"]} accept=".mot" />
      </td>
      <td>{statusBadge}</td>
      {!props.cursor.canEdit() ? null : (
        <td>
          <ButtonGroup className="d-block mb-2">
            <Dropdown>
              <Dropdown.Toggle className="table-action-btn dropdown-toggle arrow-none btn btn-light btn-xs">
                <i className="mdi mdi-dots-horizontal"></i>
              </Dropdown.Toggle>
              <Dropdown.Menu>
                <Dropdown.Item
                  onClick={() => {
                    props.cursor.rawCursor.deleteByPrefix("trials/" + props.name);
                  }}
                >
                  <i className="mdi mdi-delete me-2 text-muted vertical-middle"></i>
                  Delete
                </Dropdown.Item>
              </Dropdown.Menu>
            </Dropdown>
          </ButtonGroup>
        </td>
      )}
    </tr>
  );
});

type MocapSubjectViewProps = {
  cursor: MocapS3Cursor;
};

const MocapSubjectView = observer((props: MocapSubjectViewProps) => {
  const [uploadFiles, setUploadFiles] = useState({} as { [key: string]: File; });
  const navigate = useNavigate();

  let trialViews: any[] = [];

  let trials = props.cursor.getTrials();
  for (let i = 0; i < trials.length; i++) {
    trialViews.push(
      <MocapTrialRowView
        cursor={props.cursor}
        index={i}
        key={trials[i].key}
        name={trials[i].key}
        uploadFiles={uploadFiles}
      />
    );
  }
  if (props.cursor.canEdit()) {
    trialViews.push(
      <tr key="upload">
        <td colSpan={6}>
          <Dropzone
            {...props}
            accept=".trc,.mot"
            onDrop={(acceptedFiles) => {
              // This allows us to store that we'd like to auto-upload these files once the trials with matching names are created
              let updatedUploadFiles = uploadFiles;
              let fileNames: string[] = [];
              for (let i = 0; i < acceptedFiles.length; i++) {
                fileNames.push(acceptedFiles[i].name);
                updatedUploadFiles[acceptedFiles[i].name] = acceptedFiles[i];
              }
              setUploadFiles(updatedUploadFiles);
              props.cursor.bulkCreateTrials(fileNames);
            }}
          >
            {({ getRootProps, getInputProps, isDragActive }) => (
              <div className={"dropzone" + (isDragActive ? ' dropzone-hover' : '')} {...getRootProps()}>
                <div className="dz-message needsclick">
                  <input {...getInputProps()} />
                  <i className="h3 text-muted dripicons-cloud-upload"></i>
                  <h5>
                    Drop files here or click to bulk upload trials.
                  </h5>
                  <span className="text-muted font-13">
                    (You can drop multiple files at once to create multiple
                    trials simultaneously)
                  </span>
                </div>
              </div>
            )}
          </Dropzone>
        </td>
      </tr>
    );
  }

  let showValidationControls = props.cursor.getShowValidationControls();
  let validationControlsEnabled = props.cursor.getValidationControlsEnabled();

  let manuallyScaledOpensimUpload = null;
  let manualIkRowHeader = null;
  if (showValidationControls) {
    manuallyScaledOpensimUpload = (
      <div>
        <h5>Manually Scaled OpenSim</h5>
        <DropFile cursor={props.cursor} path={"manually_scaled.osim"} accept=".osim" />
      </div>
    );
    manualIkRowHeader = (
      <th className="border-0">Gold IK</th>
    );
  }

  return (
    <div className="MocapView">
      <MocapTrialModal cursor={props.cursor} />
      <h3>
        <i className="mdi mdi-walk me-1 text-muted vertical-middle"></i>
        Subject: {props.cursor.getCurrentFileName()}{" "}
        {/*<span className="badge bg-secondary">{"TODO"}</span>*/}
      </h3>
      <div>Run Comparison with Hand-Scaled Version: <input type="checkbox" checked={showValidationControls} onChange={(e) => {
        props.cursor.setShowValidationControls(e.target.checked);
      }} disabled={!validationControlsEnabled} /></div>
      <div>
        <h5>Unscaled OpenSim</h5>
        <DropFile cursor={props.cursor} path={"unscaled_generic.osim"} accept=".osim" />
      </div>
      {manuallyScaledOpensimUpload}
      <h5>Anthropometrics</h5>
      <p>
        Weight: <input type="number" value={props.cursor.subjectJson.getAttribute("massKg", 0.0)} onChange={(e) => {
          props.cursor.subjectJson.setAttribute("massKg", e.target.value);
        }}></input> kg
      </p>
      <p>
        Height: <input type="number" value={props.cursor.subjectJson.getAttribute("heightM", 0.0)} onChange={(e) => {
          props.cursor.subjectJson.setAttribute("heightM", e.target.value);
        }}></input> m
      </p>
      <div>
        <h5>Trials</h5>
        <Table
          responsive={trials.length > 2}
          className="table table-centered table-nowrap mb-0 mt-2"
        >
          <thead className="table-light">
            <tr>
              <th className="border-0">Trial Name</th>
              <th className="border-0">Markers</th>
              {manualIkRowHeader}
              <th className="border-0">GRF</th>
              <th className="border-0" style={{ width: "100px" }}>
                Status
              </th>
              {props.cursor.canEdit() ? (
                <th className="border-0" style={{ width: "50px" }}>
                  Action
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>{trialViews}</tbody>
        </Table>
        <Button onClick={() => navigate({ search: "?new-trial" })}>Create new trial</Button>
      </div>
    </div>
  );
});

export default MocapSubjectView;
