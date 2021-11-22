import React, { useEffect, useRef } from "react";
import { MocapClip } from "../state/MocapS3";
import { observer } from "mobx-react-lite";
import "./MocapView.scss";
import { Button, Form } from "react-bootstrap";
import RawFileDisplay from "../components/RawFileDisplay";
// import NimbleStandaloneReact from "nimble-visualizer/src/NimbleStandaloneReact";

type MocapViewProps = {
  clip: MocapClip;
};

const MocapView = observer((props: MocapViewProps) => {
  const standalone = useRef(null as null | any);

  useEffect(() => {
    return () => {
      console.log("Cleaning up");
      if (standalone.current != null) {
        standalone.current.dispose();
      }
    };
  }, []);

  if (props.clip.status.state === "done") {
    return (
      <div className="MocapView">
        <h2>
          <i className="mdi mdi-walk me-1 text-muted vertical-middle"></i>
          Subject: {props.clip.name}
        </h2>

        <Button
          size="lg"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            alert("Downloading results files not implemented yet");
          }}
        >
          <i className="mdi mdi-download me-1 vertical-middle"></i>
          Download Files
        </Button>

        <h3>Preview:</h3>

        <div
          className="MocapView__viewer"
          ref={(r: HTMLDivElement | null) => {
            if (r != null) {
              setTimeout(() => {
                if (props.clip.resultsPreviewFile) {
                  props.clip.resultsPreviewFile.getSignedURL().then((url) => {
                    const newStandalone = new (
                      document as any
                    ).NimbleStandalone(r);
                    newStandalone.loadRecording(url);
                    standalone.current = newStandalone;
                  });
                }
              }, 1000);
            }
          }}
        ></div>

        <h2>
          <i className="mdi mdi-server-network me-1 text-muted vertical-middle"></i>
          Processing (Autoscale &amp; Autofit) Log
        </h2>

        <div>
          <RawFileDisplay file={props.clip.logFile} />
        </div>
      </div>
    );
  } else {
    return (
      <div className="MocapView">
        <h2>
          <i className="mdi mdi-walk me-1 text-muted vertical-middle"></i>
          Subject: {props.clip.name}
        </h2>
        <div>
          {/*
          <h3>
            <i className="mdi mdi-flask-plus-outline me-1"></i> Help Test
            BiomechNet!
          </h3>
          */}
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
        </div>
      </div>
    );
  }
});

export default MocapView;
