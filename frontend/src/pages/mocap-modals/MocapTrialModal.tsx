import React, { useEffect, useRef } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { MocapSubject, MocapTrial } from "../../state/MocapS3";
import { Modal, Button, Spinner } from "react-bootstrap";
import RawFileDisplay from "../../components/RawFileDisplay";
import { observer } from "mobx-react-lite";

type MocapTrialModalProps = {
  subject: MocapSubject;
};

const MocapTrialModal = observer((props: MocapTrialModalProps) => {
  const location = useLocation();
  const navigate = useNavigate();
  const standalone = useRef(null as null | any);

  let show = location.search.startsWith("?show-trial=");
  let trialNumber: number = 0;
  if (show) {
    trialNumber = parseInt(
      decodeURIComponent(location.search.substr("?show-trial=".length))
    );
  } else {
    if (standalone.current != null) {
      standalone.current.dispose();
      standalone.current = null;
    }
  }

  let hideModal = () => {
    if (standalone.current != null) {
      standalone.current.dispose();
      standalone.current = null;
    }
    navigate({ search: "" });
  };

  useEffect(() => {
    return () => {
      console.log("Cleaning up");
      if (standalone.current != null) {
        standalone.current.dispose();
        standalone.current = null;
      }
    };
  }, []);

  let body = null;
  let name = null;
  if (props.subject.trials.length > trialNumber && trialNumber >= 0) {
    const trial = props.subject.trials[trialNumber];
    name = trial.name;
    if (trial.status.state === "loading") {
      body = <Spinner animation="border" />;
    } else if (trial.status.state === "waiting-for-worker") {
      body = (
        <div className="MocapView">
          <h2>Waiting to be assigned a processing server...</h2>
          <p>
            We have a number of servers that process uploaded tasks one at a
            time. It shouldn't take long to get assigned a server, but when we
            get lots of uploads at once, the servers may be busy for a while.
          </p>
          <Button onClick={trial.refreshStatus}>Refresh</Button>
        </div>
      );
    } else if (trial.status.state === "processing") {
      body = (
        <div className="MocapView">
          <h2>Status: Processing</h2>
          <h2>
            <i className="mdi mdi-server-network me-1 text-muted vertical-middle"></i>
            Processing (Autoscale &amp; Autofit) Log
          </h2>

          <div>
            <RawFileDisplay file={trial.logFile} />
          </div>
        </div>
      );
    } else if (trial.status.state === "done") {
      body = (
        <div className="MocapView">
          <div
            className="MocapView__viewer"
            ref={(r: HTMLDivElement | null) => {
              if (r != null) {
                setTimeout(() => {
                  if (trial.resultsPreviewFile) {
                    trial.resultsPreviewFile.getSignedURL().then((url) => {
                      if (standalone.current != null) {
                        standalone.current.dispose();
                      }
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
            <RawFileDisplay file={trial.logFile} />
          </div>
          {/*
            <FileInput
              file={props.clip.markerFile}
              name="Marker *.trc"
              accept=".trc"
              description="The marker trajectories for this motion trial"
            />
            <FileInput
              file={props.clip.manualIKFile}
              name="IK *.mot"
              accept=".mot"
              description="The OpenSim IK output, corresponding to the subject of this motion trial"
            />
            */}
        </div>
      );
    }
  }

  return (
    <Modal size="xl" show={show} onHide={hideModal}>
      <Modal.Header closeButton>
        <Modal.Title>
          <i className="mdi mdi-run me-1"></i> Trial: {name}
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>{body}</Modal.Body>
    </Modal>
  );
});

export default MocapTrialModal;
