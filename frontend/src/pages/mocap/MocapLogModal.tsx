import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Button, Spinner, Table } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import MocapS3Cursor, { LargeZipJsonObject } from '../../state/MocapS3Cursor';
import NimbleStandaloneReact from 'nimble-visualizer/dist/NimbleStandaloneReact';

type MocapLogModalProps = {
  cursor: MocapS3Cursor;
};

const MocapLogModal = observer((props: MocapLogModalProps) => {
  const location = useLocation();
  const navigate = useNavigate();
  const standalone = useRef(null as null | any);
  const [logText, setLogText] = useState('');
  const [logTextDownloadError, setLogTextDownloadError] = useState(false);
  const modalRef = useRef(null as any);

  let show = location.search.startsWith("?logs=");
  let subjectStatus = 'empty'
  if (show) {
    subjectStatus = props.cursor.getSubjectStatus();
  }

  const onLogLine = (logLine: string) => {
    setLogText(oldLog => oldLog + logLine);
    // Scroll to the bottom to follow the logs
    if (modalRef.current != null) {
      modalRef.current.dialog.scrollTop = modalRef.current.dialog.scrollHeight - modalRef.current.dialog.clientHeight;
    }
  };

  useEffect(() => {
    if (show && subjectStatus === 'done') {
      if (props.cursor.hasLogFile()) {
        props.cursor.getLogFileText().then((text: string) => {
          setLogText(text);

          // Scroll to the top
          if (modalRef.current != null) {
            modalRef.current.dialog.scrollTo({ top: 0, behavior: 'smooth' });
          }
        }).catch(() => {
          setLogTextDownloadError(true);
        });
      }
      else {
        setLogTextDownloadError(true);
      }
    }
    if (subjectStatus === 'processing') {
      setLogText('');
    }
    // This cleans up our log listener
    return props.cursor.subscribeToLogUpdates(onLogLine);
  }, [show, subjectStatus]);

  if (!show) {
    return <></>;
  }

  let hideModal = () => {
    if (standalone.current != null) {
      standalone.current.dispose();
      standalone.current = null;
    }
    navigate({ search: "" }, { replace: true });
  };

  const displayLogText = logTextDownloadError ? "[Error downloading logs from server]" : logText;

  let body = null;
  if (subjectStatus === 'empty') {

  }
  else if (subjectStatus === 'could-process') {
    body = (
      <div className="MocapView">
        <h2>Status: Waiting for owner to process subject</h2>
      </div>
    );
  }
  else if (subjectStatus === 'waiting') {
    body = (
      <div className="MocapView">
        <h2>Waiting to be assigned a processing server...</h2>
        <p>
          We have a number of servers that process uploaded tasks one at a
          time. It shouldn't take long to get assigned a server, but when we
          get lots of uploads at once, the servers may be busy for a while.
        </p>
      </div>
    );
  }
  else if (subjectStatus === 'processing') {
    body = (
      <div className="MocapView">
        <h2>Status: Processing</h2>
        <div>
          <pre>
            {displayLogText}
          </pre>
        </div>
        <Spinner animation='border' size="sm" /> {' '} Live Processing Logs
      </div>
    );
  }
  else if (subjectStatus === 'error') {
    body = (
      <div className="MocapView">
        <h2>Processing Server Encountered Error</h2>
        <div>
          <pre>
            {displayLogText}
          </pre>
        </div>
      </div>
    );
  }
  else if (subjectStatus === 'done') {
    body = (
      <div className="MocapView">
        <h2>
          <i className="mdi mdi-server-network me-1 text-muted vertical-middle"></i>
          Processing (Autoscale &amp; Autoregister) Log
        </h2>

        <div>
          <pre>
            {displayLogText}
          </pre>
        </div>
      </div>
    );
  }

  return (
    <Modal size="xl" show={show} onHide={hideModal} ref={modalRef}>
      <Modal.Header closeButton>
        <Modal.Title>
          <i className="mdi mdi-run me-1"></i> Logs
        </Modal.Title>
      </Modal.Header>
      <Modal.Body>{body}</Modal.Body>
    </Modal>
  );
});

export default MocapLogModal;
