import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Button, Spinner, Table } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import MocapS3Cursor, { LargeZipJsonObject } from '../../state/MocapS3Cursor';
import NimbleStandaloneReact from 'nimble-visualizer/dist/NimbleStandaloneReact';

type MocapTrialModalProps = {
    cursor: MocapS3Cursor;
};

type ProcessingResultsJSON = {
    autoAvgMax: number;
    autoAvgRMSE: number;
    goldAvgMax: number;
    goldAvgRMSE: number;
};

type MocapTrialEntry = {
    key: string;
    lastModified: Date;
    size: number;
};

const MocapTrialModal = observer((props: MocapTrialModalProps) => {
    const location = useLocation();
    const navigate = useNavigate();
    const standalone = useRef(null as null | any);
    const [logText, setLogText] = useState('');
    const [resultsJson, setResultsJson] = useState({} as ProcessingResultsJSON);
    const modalRef = useRef(null as any);

    let show = location.search.startsWith("?show-trial=");
    let trialNumber: number = 0;
    let trialStatus = 'empty'
    let trial: MocapTrialEntry | null = null;
    let visualization: LargeZipJsonObject | null = null;
    if (show) {
        trialNumber = parseInt(decodeURIComponent(location.search.substring("?show-trial=".length)));
        trial = props.cursor.getTrials()[trialNumber];
        if (trial != null) {
            trialStatus = props.cursor.getTrialStatus(trial.key);
        }
        if (trialStatus === 'done') {
            visualization = props.cursor.getTrialVisualization(trial.key);
        }
    }

    const onLogLine = (logLine: string) => {
        setLogText(oldLog => oldLog + logLine);
        // Scroll to the bottom to follow the logs
        if (modalRef.current != null) {
            modalRef.current.dialog.scrollTop = modalRef.current.dialog.scrollHeight - modalRef.current.dialog.clientHeight;
        }
    };

    useEffect(() => {
        if (show && trial != null && trialStatus === 'done') {
            props.cursor.getLogFileText(trial.key).then((text: string) => {
                setLogText(text);

                // Scroll to the top
                if (modalRef.current != null) {
                    modalRef.current.dialog.scrollTo({ top: 0, behavior: 'smooth' });
                }
            }).catch(() => {

            });
            props.cursor.getResultsFileText(trial.key).then((text: string) => {
                setResultsJson(JSON.parse(text));

                // Scroll to the top
                if (modalRef.current != null) {
                    modalRef.current.dialog.scrollTo({ top: 0, behavior: 'smooth' });
                }
            }).catch(() => { });
        }
        if (trialStatus === 'processing') {
            setLogText('');
        }
        // This cleans up our log listener
        return props.cursor.subscribeToLogUpdates(trial?.key, onLogLine);
    }, [trialNumber, show, trialStatus, trial?.key]);

    if (!show || trial == null) {
        return <></>;
    }

    let hideModal = () => {
        if (standalone.current != null) {
            standalone.current.dispose();
            standalone.current = null;
        }
        navigate({ search: "" }, { replace: true });
    };


    let body = null;
    if (trialStatus === 'empty') {

    }
    else if (trialStatus === 'could-process') {
        if (props.cursor.canEdit()) {
            body = (
                <div className="MocapView">
                    <h2>Status: Ready to process</h2>
                    <Button size="lg" onClick={() => props.cursor.markTrialReadyForProcessing(trial?.key ?? '')}>Process</Button>
                </div>
            );
        }
        else {
            body = (
                <div className="MocapView">
                    <h2>Status: Waiting for owner to process</h2>
                </div>
            );
        }
    }
    else if (trialStatus === 'waiting') {
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
    else if (trialStatus === 'processing') {
        body = (
            <div className="MocapView">
                <h2>Status: Processing</h2>
                <div>
                    <pre>
                        {logText}
                    </pre>
                </div>
                <Spinner animation='border' size="sm" /> {' '} Live Processing Logs
            </div>
        );
    }
    else if (trialStatus === 'error') {
        body = (
            <div className="MocapView">
                <h2>Processing Server Encountered Error</h2>
                <div>
                    <pre>
                        {logText}
                    </pre>
                </div>
            </div>
        );
    }
    else if (trialStatus === 'done') {
        let percentImprovementRMSE = ((resultsJson.goldAvgRMSE - resultsJson.autoAvgRMSE) / resultsJson.goldAvgRMSE) * 100;
        let percentImprovementMax = ((resultsJson.goldAvgMax - resultsJson.autoAvgMax) / resultsJson.goldAvgMax) * 100;

        let download = null;
        if (props.cursor.hasResultsArchive(trial?.key ?? '')) {
            download = (
                <div style={{ 'marginBottom': '5px' }}>
                    <Button onClick={() => props.cursor.downloadResultsArchive(trial?.key ?? '')}>
                        <i className="mdi mdi-download me-2 vertical-middle"></i>
                        Download OpenSim Results
                    </Button>
                </div>
            );
        }

        body = (
            <div className="MocapView">
                <h2>Results:</h2>
                {download}
                <NimbleStandaloneReact style={{ height: '400px' }} loading={visualization?.loading ?? true} loadingProgress={visualization?.loadingProgress ?? 0.0} recording={visualization?.object ?? null} />
                <div>
                    <Table>
                        <thead>
                            <tr>
                                <td></td>
                                <td>Avg. RMSE</td>
                                <td>Avg. Max</td>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td>Manual:</td>
                                <td>{(resultsJson.goldAvgRMSE * 100 ?? 0.0).toFixed(2)} cm</td>
                                <td>{(resultsJson.goldAvgMax * 100 ?? 0.0).toFixed(2)} cm</td>
                            </tr>
                            <tr>
                                <td>Automatic:</td>
                                <td>{(resultsJson.autoAvgRMSE * 100 ?? 0.0).toFixed(2)} cm <b>({percentImprovementRMSE.toFixed(1)}% error {percentImprovementRMSE > 0 ? 'reduction' : 'increase'})</b></td>
                                <td>{(resultsJson.autoAvgMax * 100 ?? 0.0).toFixed(2)} cm <b>({percentImprovementMax.toFixed(1)}% error {percentImprovementMax > 0 ? 'reduction' : 'increase'})</b></td>
                            </tr>
                        </tbody>
                    </Table>
                </div>

                <h2>
                    <i className="mdi mdi-server-network me-1 text-muted vertical-middle"></i>
                    Processing (Autoscale &amp; Autoregister) Log
                </h2>

                <div>
                    <pre>
                        {logText}
                    </pre>
                </div>
            </div>
        );
    }

    return (
        <Modal size="xl" show={show} onHide={hideModal} ref={modalRef}>
            <Modal.Header closeButton>
                <Modal.Title>
                    <i className="mdi mdi-run me-1"></i> Trial: {trial.key}
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>{body}</Modal.Body>
        </Modal>
    );
});

export default MocapTrialModal;
