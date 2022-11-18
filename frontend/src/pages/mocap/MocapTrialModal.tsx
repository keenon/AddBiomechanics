import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Table } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import MocapS3Cursor, { LargeZipBinaryObject } from '../../state/MocapS3Cursor';
import NimbleStandaloneReact from 'nimble-visualizer/dist/NimbleStandaloneReact';

type MocapTrialModalProps = {
    cursor: MocapS3Cursor;
};

type ProcessingResultsJSON = {
    autoAvgMax: number;
    autoAvgRMSE: number;
    linearResidual?: number;
    angularResidual?: number;
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
    let visualization: LargeZipBinaryObject | null = null;
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
    }, [trialNumber, show, subjectStatus, trial?.key]); // note: don't depend on props.cursor, because that leads to an infinite loop in rendering

    if (!show || trial == null) {
        return <></>;
    }

    let hideModal = () => {
        if (standalone.current != null) {
            standalone.current.dispose();
            standalone.current = null;
        }
        if (visualization != null) {
            console.log("Disposing of cached visualization");
            visualization.dispose();
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
        let linearResidualText = "N/A";
        let angularResidualText = "N/A";
        if (resultsJson.linearResidual) {
            if (resultsJson.linearResidual > 10 || resultsJson.linearResidual < 1) {
                linearResidualText = (resultsJson.linearResidual).toExponential(2) + "N";
            }
            else {
                linearResidualText = (resultsJson.linearResidual).toFixed(2) + "N";
            }
        }
        if (resultsJson.angularResidual) {
            if (resultsJson.angularResidual > 10 || resultsJson.angularResidual < 1) {
                angularResidualText = (resultsJson.angularResidual).toExponential(2) + "Nm";
            }
            else {
                angularResidualText = (resultsJson.angularResidual).toFixed(2) + "Nm";
            }
        }

        body = (
            <div className="MocapView">
                <h2>Results:</h2>
                <NimbleStandaloneReact style={{ height: '400px' }} loading={visualization?.loading ?? true} loadingProgress={visualization?.loadingProgress ?? 0.0} recording={visualization?.object ?? null} />
                <div>
                    <Table>
                        <thead>
                            <tr>
                                <td></td>
                                <td>Avg. Marker-error RMSE</td>
                                <td>Avg. Marker-error Max</td>
                                <td>Avg. Linear Residual</td>
                                <td>Avg. Angular Residual</td>
                            </tr>
                        </thead>
                        <tbody>
                            {(() => {
                                if (!isNaN(resultsJson.goldAvgRMSE)) {
                                    return (
                                        <tr>
                                            <td>Hand-scaling Performance:</td>
                                            <td>{(resultsJson.goldAvgRMSE * 100 ?? 0.0).toFixed(2)} cm</td>
                                            <td>{(resultsJson.goldAvgMax * 100 ?? 0.0).toFixed(2)} cm</td>
                                        </tr>
                                    );
                                }
                            })()}
                            <tr>
                                <td>Auto-scaling Performance:</td>
                                <td>{(resultsJson.autoAvgRMSE * 100 ?? 0.0).toFixed(2)} cm {
                                    isNaN(percentImprovementRMSE) ? null : <b>({percentImprovementRMSE.toFixed(1)}% error {percentImprovementRMSE > 0 ? 'reduction' : 'increase'})</b>
                                }</td>
                                <td>{(resultsJson.autoAvgMax * 100 ?? 0.0).toFixed(2)} cm {
                                    isNaN(percentImprovementMax) ? null : <b>({percentImprovementMax.toFixed(1)}% error {percentImprovementMax > 0 ? 'reduction' : 'increase'})</b>
                                }</td>
                                <td>{linearResidualText}</td>
                                <td>{angularResidualText}</td>
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
