import React, { useEffect, useRef } from "react";
import { MocapClip } from "../state/MocapS3";
import { observer } from "mobx-react-lite";
import "./MocapView.scss";
import { Button } from "react-bootstrap";
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

  return (
    <div className="MocapView">
      <h2>
        <i className="mdi mdi-walk me-1 text-muted vertical-middle"></i>
        Motion Data
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
                  const newStandalone = new (document as any).NimbleStandalone(
                    r
                  );
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
});

export default MocapView;
