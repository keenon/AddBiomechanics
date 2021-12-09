import React, { useEffect, useRef } from "react";
import { MocapSubject, MocapTrial } from "../state/MocapS3";
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
import FileInput from "../components/FileInput";
import Dropzone from "react-dropzone";
import { useTranslation } from "react-i18next";
import MocapTrialModal from "./mocap-modals/MocapTrialModal";
import { action } from "mobx";
// import NimbleStandaloneReact from "nimble-visualizer/src/NimbleStandaloneReact";

type MocapTrialRowViewProps = {
  index: number;
  trial: MocapTrial;
  canEdit: boolean;
};

const MocapTrialRowView = observer((props: MocapTrialRowViewProps) => {
  let statusBadge = null;
  if (props.trial.status.state === "loading") {
    statusBadge = <Spinner animation="border" />;
  } else if (props.trial.status.state === "uploading") {
    statusBadge = (
      <ProgressBar
        style={{ width: "100%" }}
        min={0}
        max={1}
        now={props.trial.markerFile.uploadProgress}
        striped={true}
        animated={true}
      />
    );
  } else if (props.trial.status.state === "waiting-for-worker") {
    statusBadge = (
      <span className="badge bg-secondary">Waiting for server</span>
    );
  } else if (props.trial.status.state === "processing") {
    statusBadge = <span className="badge bg-warning">Processing...</span>;
  } else if (props.trial.status.state === "done") {
    statusBadge = <span className="badge bg-success">Processed</span>;
  } else {
    statusBadge = (
      <span className="badge bg-success">{props.trial.status.state}</span>
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
          {props.trial.name}
        </Link>
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
                <Dropdown.Item>
                  <i className="mdi mdi-link me-2 text-muted vertical-middle"></i>
                  Copy Sharable Link
                </Dropdown.Item>
                <Dropdown.Item
                  onClick={() => {
                    props.trial.delete();
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
  subject: MocapSubject;
  canEdit: boolean;
};

const MocapSubjectView = observer((props: MocapSubjectViewProps) => {
  const { t } = useTranslation();
  const genericBaseModelSelector = useRef<HTMLSelectElement>();
  const genericBaseModelInput = useRef();

  let trials: any[] = [];
  for (let i = 0; i < props.subject.trials.length; i++) {
    trials.push(
      <MocapTrialRowView
        index={i}
        key={props.subject.trials[i].name}
        trial={props.subject.trials[i]}
        canEdit={props.canEdit}
      />
    );
  }
  if (props.canEdit) {
    trials.push(
      <tr key="upload">
        <td colSpan={4}>
          <Dropzone
            {...props}
            accept=".trc,.c3d"
            onDrop={(acceptedFiles) => {
              props.subject.createTrials(acceptedFiles);
              console.log(acceptedFiles);
            }}
          >
            {({ getRootProps, getInputProps }) => (
              <div className="dropzone">
                <div className="dz-message needsclick" {...getRootProps()}>
                  <input {...getInputProps()} />
                  <i className="h3 text-muted dripicons-cloud-upload"></i>
                  <h5>
                    Drop files here or click to upload trials. Extensions: *.trc
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

  let subjectControlsAccordion = <Spinner animation="border" />;
  if (!props.subject.loading) {
    subjectControlsAccordion = (
      <Accordion
        defaultActiveKey={
          props.canEdit && !props.subject.isGenericOsimFileValid()
            ? "0"
            : undefined
        }
      >
        <Accordion.Item eventKey="0">
          <Accordion.Header>
            <i className="mdi mdi-walk me-1"></i> Customize OpenSim Base Model
          </Accordion.Header>
          <Accordion.Body>
            <p>
              This is the standard OpenSim model (<i>with markers!</i>) that
              we'll automatically scale and fit to your trial data.
            </p>
            <Form noValidate validated={true}>
              <Form.Group className="mb-3">
                {/*
                  <div className="input-group">
                  </div>
                  */}
                <Form.Label>Generic Base OpenSim Model</Form.Label>
                <Form.Select
                  id="inlineFormCustomSelect"
                  value={props.subject.status.genericOsimFile}
                  ref={(r: any) => {
                    genericBaseModelSelector.current = r;
                    if (genericBaseModelSelector.current != null) {
                      if (props.subject.isGenericOsimFileValid()) {
                        genericBaseModelSelector.current.setCustomValidity("");
                      } else {
                        genericBaseModelSelector.current.setCustomValidity(
                          "Invalid"
                        );
                      }
                    }
                  }}
                  onChange={action((e) => {
                    const value = e.target.value as any;
                    props.subject.setStatusValues({
                      genericOsimFile: value,
                    });
                    if (props.subject.isGenericOsimFileValid()) {
                      e.target.setCustomValidity("");
                    } else {
                      e.target.setCustomValidity(
                        "Must select a generic base OpenSim Model"
                      );
                    }
                  })}
                  disabled={!props.canEdit}
                  isValid={false}
                >
                  <option value="" selected>
                    Choose...
                  </option>
                  <option value="rajagopal">Rajagopal 2015</option>
                  <option value="lai_arnold">Lai Arnold 2017</option>
                  <option value="custom">Custom</option>
                </Form.Select>
                {props.subject.status.genericOsimFile === "custom" ? (
                  <FileInput
                    file={props.subject.customGenericOsimFile}
                    accept=".osim"
                    canEdit={props.canEdit}
                  />
                ) : null}
                <Form.Text className="text-muted">
                  The generic OpenSim model (including your marker set!),
                  unscaled, that will be automatically scaled to represent this
                  subject.
                </Form.Text>
                <Form.Control.Feedback type="invalid">
                  Must select a generic OpenSim Model
                </Form.Control.Feedback>
              </Form.Group>
            </Form>
          </Accordion.Body>
        </Accordion.Item>
        {props.canEdit || props.subject.manualScalesFile.state === "s3" ? (
          <Accordion.Item eventKey="1">
            <Accordion.Header>
              <i className="mdi mdi-flask-plus-outline me-1"></i>
              {props.canEdit
                ? t("Help Test the Auto-fitter Accuracy!")
                : t("Evaluating Auto-fitter Accuracy")}
            </Accordion.Header>
            <Accordion.Body>
              <p>
                {props.canEdit
                  ? t(`When you upload a manually scaled version, we can run a comparison
              of the automated processing versus the manual fit.`)
                  : t(
                      `This is a manually scaled version of the skeleton, which we use as a reference to compare our automated processing to.`
                    )}
              </p>
              <FileInput
                file={props.subject.manualScalesFile}
                name="Manually scaled *.osim"
                accept=".osim"
                description="The hand-scaled OpenSim model corresponding to the subject of this motion trial"
                canEdit={props.canEdit}
              />
            </Accordion.Body>
          </Accordion.Item>
        ) : null}
        <Accordion.Item eventKey="2">
          <Accordion.Header>
            <i className="mdi mdi-desktop-classic me-1"></i>
            {t("Autoscaling Logs")}
          </Accordion.Header>
          <Accordion.Body>
            <p>TODO: Autoscaling Logs</p>
          </Accordion.Body>
        </Accordion.Item>
      </Accordion>
    );
  }

  return (
    <div className="MocapView">
      <MocapTrialModal subject={props.subject} />
      <h3>
        <i className="mdi mdi-walk me-1 text-muted vertical-middle"></i>
        Subject: {props.subject.name}{" "}
        <span className="badge bg-secondary">{props.subject.status.state}</span>
      </h3>
      <div>
        {subjectControlsAccordion}
        <Table
          responsive={trials.length > 2}
          className="table table-centered table-nowrap mb-0"
        >
          <thead className="table-light">
            <tr>
              <th className="border-0">Trial Name</th>
              <th className="border-0" style={{ width: "100px" }}>
                Status
              </th>
              {props.canEdit ? (
                <th className="border-0" style={{ width: "50px" }}>
                  Action
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>{trials}</tbody>
        </Table>
      </div>
    </div>
  );
});

export default MocapSubjectView;
