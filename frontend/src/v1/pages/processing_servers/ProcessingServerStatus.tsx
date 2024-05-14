import React, { useEffect, useState, useRef } from "react";
import { useNavigate, NavLink } from "react-router-dom";
import {
  Row,
  Col,
  Card,
  Badge,
  Table,
  OverlayTrigger, Tooltip,
  Alert, Button
} from "react-bootstrap";
import MocapS3Cursor from '../../state/MocapS3Cursor';
import './ProcessingServerStatus.scss';
import { observer } from "mobx-react-lite";

type ProcessingServerStatus = {
  currently_processing: string;
  job_queue: string[];
}

type ProcessingServerDetailsProps = {
  serverId: string;
  serverData: ProcessingServerStatus;
  cursor: MocapS3Cursor;
};

const ProcessingServerDetails = observer((props: ProcessingServerDetailsProps) => {
  const lastPingSent = useRef(new Date().getTime());
  const [secondsSinceLastPingSent, setSecondsSinceLastPingSent] = useState(0);
  const [anyPingReceived, setAnyPingReceived] = useState(false);
  const [secondsSinceLastPingReceived, setSecondsSinceLastPingReceived] = useState(0);

  // Ping the server every 5s while we're displaying this component, to check for liveness
  useEffect(() => {
    const now = new Date().getTime();
    lastPingSent.current = now;
    props.cursor.pingServer(props.serverId);

    const interval = setInterval(() => {
      const now = new Date().getTime();
      lastPingSent.current = now;
      props.cursor.pingServer(props.serverId);
    }, 5000);

    return () => {
      clearInterval(interval);
    };
  }, []);

  // Update the GUI every 1s
  useEffect(() => {
    const interval = setInterval(() => {
      const now = new Date().getTime();

      const lastPingReceived: number | undefined = props.cursor.lastSeenPong.get(props.serverId);
      if (lastPingReceived != null) {
        if (anyPingReceived != true) {
          setAnyPingReceived(true);
        }

        const msSinceLastReceived = now - lastPingReceived;
        setSecondsSinceLastPingReceived(Math.round(msSinceLastReceived / 1000));
      }

      const msSinceLastSent = now - lastPingSent.current;
      setSecondsSinceLastPingSent(Math.round(msSinceLastSent / 1000));
    }, 1000);

    return () => {
      clearInterval(interval);
    };
  }, []);

  let timeSincePingRendered = null;
  if (!anyPingReceived) {
    timeSincePingRendered = <span>Waiting to receive first proof of life from this server. Last ping sent {secondsSinceLastPingSent}s ago.</span>;
  }
  else if (secondsSinceLastPingReceived > 15) {
    timeSincePingRendered = <span style={{ color: 'red' }}>Last ping sent {secondsSinceLastPingSent}s ago. Received last pong {secondsSinceLastPingReceived}s ago.</span>;
  }

  let serverIsLive = anyPingReceived && secondsSinceLastPingReceived < 30;

  if (serverIsLive) {
    let queueRendered = null;
    let allJobs: string[] = [];
    if (props.serverData.currently_processing === '' || props.serverData.currently_processing === 'none') {
      allJobs = props.serverData.job_queue;
    }
    else {
      allJobs = [props.serverData.currently_processing].concat(props.serverData.job_queue.filter(j => j != props.serverData.currently_processing));
    }
    queueRendered = allJobs.map(rawPath => {
      const parts = rawPath.split('/');
      while (parts.length > 0 && parts[0] === '') {
        parts.splice(0, 1);
      }
      while (parts.length > 0 && parts[parts.length - 1] === '') {
        parts.splice(parts.length - 1, 1);
      }

      let privacyLevel = parts[0];
      let userId = (parts.length > 1 ? parts[1] : '').replace(props.cursor.region + ":", "");

      let username = userId === props.cursor.s3Index.myIdentityId ? 'Me' : userId;
      let isMe = userId === props.cursor.s3Index.myIdentityId;

      let inBacklog = props.serverData.currently_processing !== rawPath;
      let rowStyle: any = null;
      if (!inBacklog) {
        rowStyle = {
          backgroundColor: '#fff2cc'
          // backgroundColor: '#d5ddec'
        };
      }
      let statusRendered = inBacklog ? <Badge bg="secondary">Waiting</Badge> : <Badge bg="warning">Processing</Badge>;

      if (privacyLevel === 'protected') {
        let link = '/data/' + encodeURIComponent(userId) + '/';

        let dataName = '';
        if (parts.length > 3) {
          dataName = parts.slice(3).join('/');
          link += dataName;
        }
        return <tr key={rawPath} style={rowStyle}>
          <td>
            <span className={"badge " + (isMe ? "bg-primary" : "bg-secondary")}>{username}</span>
          </td>
          <td>
            <NavLink
              to={link}
            >
              <span>{dataName}</span>
            </NavLink>
          </td>
          <td>
            {statusRendered}
          </td>
        </tr>;
      }
      else if (privacyLevel === 'private' && isMe) {
        let link = '/data/private/';

        let dataName = '';
        if (parts.length > 3) {
          dataName = parts.slice(3).join('/');
          link += dataName;
        }
        return <tr key={rawPath} style={rowStyle}>
          <td>
            <Badge>{username}</Badge>
          </td>
          <td>
            <NavLink
              to={link}
            >
              <span>{dataName}</span>
            </NavLink>
          </td>
          <td>
            {statusRendered}
          </td>
        </tr>;
      }
      else if (privacyLevel === 'private') {
        return <tr key={rawPath} style={rowStyle}>
          <td>
            <Badge>{username}</Badge>
          </td>
          <td>
            <span>Private Data</span>
          </td>
          <td>
            {statusRendered}
          </td>
        </tr>;
      }
    });
    let queueDiv = <p>{props.serverId} - <b>Available for new jobs</b></p>;
    if (queueRendered != null && queueRendered.length > 0) {
      queueDiv =
        <p>
          {props.serverId} - <b>Work Queue:</b>
          <Table>
            <thead>
              <tr>
                <td>User</td>
                <td>Job</td>
                <td>Status</td>
              </tr>
            </thead>
            <tbody>
              {queueRendered}
            </tbody>
          </Table>
        </p>;
    }


    return <div className="alert alert-secondary">
      {queueDiv}
    </div>;
  }
  else {
    return <div className="alert alert-secondary">
      {props.serverId} - {timeSincePingRendered}
    </div>;
  }
});

type ProcessingServerStatusProps = {
  cursor: MocapS3Cursor;
};

const ProcessingServerStatus = observer((props: ProcessingServerStatusProps) => {

  let servers = props.cursor.processingServers;
  let loading = props.cursor.s3Index.loading;

  let faqs = (
    <div className="alert alert-light">
      <p>
        FAQ: <b>How long does a typical processing job take?</b>
      </p>
      <p>
        For "normal" jobs with at most a dozen motion capture clips per subject and not attempting to minimize residuals, it shouldn't take longer than 15 minutes per job. If you also want to minimize residuals, that should take about 30 minutes. If your job is very large, and you have more than a hundred motion capture clips for a single subject, it can take several hours to process fully.
      </p>
      <p>
        FAQ: <b>Help! My job is stuck in "Waiting for server", but it's not showing up in the work queue.</b>
      </p>
      <p>
        Unfortunately, this is a known issue. We're working to resolve it more robustly, but for now there are three possible solutions.
        <ol>
          <li>Wait 30 minutes.
            <OverlayTrigger
              placement="right"
              delay={{ show: 50, hide: 400 }}
              overlay={(props) => (
                <Tooltip id="button-tooltip" {...props}>
                  <b>Why might this help?</b> We send shortcut messages to the processing servers right when you hit "Process" to tell them to start your job, but sometimes those messages get dropped. The processing server does a full refresh of the index every 30 minutes, at which point it should pick up your job.
                </Tooltip>
              )}
            >
              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
            </OverlayTrigger>
          </li>
          <li>Create a new subject (with a new name), upload the data to that subject, and try processing it instead.</li>
          <li>If all else fails, email keenon@cs.stanford.edu (or reach him on Slack, if you're a Stanford student) and ask him to restart the processing servers.</li>
        </ol>
      </p>
    </div>
  );

  let body = null;

  if (servers.size === 0) {
    if (loading) {
      body = <div>
        <p>
          Loading...
        </p>
      </div>;
    }
    else {
      body = <div>
        <p>
          It appears no servers are online.
        </p>
      </div>;
    }
  }
  else {
    const serverNames: string[] = [...servers.keys()];
    serverNames.sort();

    let serverBlocks = serverNames.map(server => {
      const serverData = servers.get(server);
      if (serverData != null) {
        return <ProcessingServerDetails key={server} cursor={props.cursor} serverId={server} serverData={serverData} />
      }
    });

    body = (
      <div>
        {serverBlocks}
      </div>
    );
  }

  return (
    <>
      <Row className="mt-3">
        <Col md="12">
          <Card className="mt-4">
            <Card.Body>
              {body}
              {faqs}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
});

export default ProcessingServerStatus;