import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Table } from "react-bootstrap";
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
    const [resultsJson, setResultsJson] = useState({} as ProcessingResultsJSON);
    const modalRef = useRef(null as any);

    let show = location.search.startsWith("?show-trial=");
    let trialNumber: number = 0;
    let subjectStatus = 'empty'
    let trial: MocapTrialEntry | null = null;
    let visualization: LargeZipJsonObject | null = null;
    if (show) {
        trialNumber = parseInt(decodeURIComponent(location.search.substring("?show-trial=".length)));
        trial = props.cursor.getTrials()[trialNumber];
        if (trial != null) {
            subjectStatus = props.cursor.getSubjectStatus();
        }
        if (subjectStatus === 'done' && props.cursor.hasTrialVisualization(trial.key)) {
            visualization = props.cursor.getTrialVisualization(trial.key);
        }
    }

    useEffect(() => {
        if (show && trial != null && subjectStatus === 'done') {
            props.cursor.getTrialResultsFileText(trial.key).then((text: string) => {
                setResultsJson(JSON.parse(text));

                // Scroll to the top
                if (modalRef.current != null) {
                    modalRef.current.dialog.scrollTo({ top: 0, behavior: 'smooth' });
                }
            }).catch(() => { });
        }
    }, [trialNumber, show, subjectStatus, trial?.key]);

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
    if (subjectStatus === 'empty') {

    }
    else if (subjectStatus === 'could-process') {
        if (props.cursor.canEdit()) {
            body = (
                <div className="MocapView">
                    <h2>Status: Ready to process</h2>
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
            </div>
        );
    }
    else if (subjectStatus === 'error') {
        body = (
            <div className="MocapView">
                <h2>Processing Server Encountered Error</h2>
            </div>
        );
    }
    else if (subjectStatus === 'done') {
        let percentImprovementRMSE = ((resultsJson.goldAvgRMSE - resultsJson.autoAvgRMSE) / resultsJson.goldAvgRMSE) * 100;
        let percentImprovementMax = ((resultsJson.goldAvgMax - resultsJson.autoAvgMax) / resultsJson.goldAvgMax) * 100;

        body = (
            <div className="MocapView">
                <h2>Results:</h2>
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
