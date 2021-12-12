import React, { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { observer } from "mobx-react-lite";
import "./MocapView.scss";
import {
  Button,
  ButtonGroup,
  Dropdown,
  Form,
  Table,
  Accordion,
  Spinner,
  ProgressBar,
} from "react-bootstrap";
import DropFile from "../../components/DropFile";
import Dropzone from "react-dropzone";
import { useTranslation } from "react-i18next";
import MocapTrialModal from "./MocapTrialModal";
import { action } from "mobx";
import MocapS3Cursor from '../../state/MocapS3Cursor';

type MocapTrialRowViewProps = {
  index: number;
  name: string;
  canEdit: boolean;
  cursor: MocapS3Cursor;
  uploadFiles: { [key: string]: File; };
};

const MocapTrialRowView = observer((props: MocapTrialRowViewProps) => {
  let status = props.cursor.getTrialStatus(props.name);
  console.log(status);
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
    statusBadge = <Button onClick={() => props.cursor.markTrialReadyForProcessing(props.name)}>Process</Button>;
  }
  else if (status === "waiting") {
    statusBadge = <span className="badge bg-secondary">Waiting for server</span>;
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
      <td>
        <DropFile cursor={props.cursor} path={"trials/" + props.name + "/gold_ik.mot"} uploadOnMount={props.uploadFiles[props.name + "_ik.mot"]} accept=".mot" />
      </td>
      <td>
        <DropFile cursor={props.cursor} path={"trials/" + props.name + "/grf.mot"} uploadOnMount={props.uploadFiles[props.name + "_grf.mot"]} accept=".mot" />
      </td>
      <td>{statusBadge}</td>
      {!props.canEdit ? null : (
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
  const { t } = useTranslation();
  const [uploadFiles, setUploadFiles] = useState({} as { [key: string]: File; });

  let trialViews: any[] = [];

  let trials = props.cursor.getTrials();
  for (let i = 0; i < trials.length; i++) {
    trialViews.push(
      <MocapTrialRowView
        cursor={props.cursor}
        index={i}
        key={trials[i].key}
        name={trials[i].key}
        canEdit={true}
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
            {({ getRootProps, getInputProps }) => (
              <div className="dropzone">
                <div className="dz-message needsclick" {...getRootProps()}>
                  <input {...getInputProps()} />
                  <i className="h3 text-muted dripicons-cloud-upload"></i>
                  <h5>
                    Drop files here or click to upload trials.
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

  return (
    <div className="MocapView">
      {/* <MocapTrialModal cursor={props.cursor} /> */}
      <h3>
        <i className="mdi mdi-walk me-1 text-muted vertical-middle"></i>
        Subject: {props.cursor.getCurrentFileName()}{" "}
        <span className="badge bg-secondary">{"TODO"}</span>
      </h3>
      <div>
        <h5>Unscaled OpenSim</h5>
        <DropFile cursor={props.cursor} path={"unscaled_generic.osim"} accept=".osim" />
      </div>
      <div>
        <h5>(Optional) Manually Scaled OpenSim</h5>
        <DropFile cursor={props.cursor} path={"manually_scaled.osim"} accept=".osim" />
      </div>
      <div>
        <h5>Trials</h5>
        <Table
          responsive={trials.length > 2}
          className="table table-centered table-nowrap mb-0"
        >
          <thead className="table-light">
            <tr>
              <th className="border-0">Trial Name</th>
              <th className="border-0">Markers</th>
              <th className="border-0">Gold IK</th>
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
      </div>
    </div>
  );
});

export default MocapSubjectView;
