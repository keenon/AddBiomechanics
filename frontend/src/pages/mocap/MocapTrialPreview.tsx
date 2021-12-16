import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Button, Spinner, Table } from "react-bootstrap";
import RawFileDisplay from "../../components/RawFileDisplay";
import { observer } from "mobx-react-lite";
import MocapS3Cursor from '../../state/MocapS3Cursor';

type MocapTrialPreviewProps = {
    cursor: MocapS3Cursor;
    trialName: string;
};

const MocapTrialPreview = observer((props: MocapTrialPreviewProps) => {
    const location = useLocation();
    const navigate = useNavigate();

    useEffect(() => {
        if (props.cursor.hasTrialVisualization(props.trialName)) {
            props.cursor.getTrialVisualization(props.trialName).then((text?: string) => {
                console.log(text);
            });
        }
    }, [props.trialName]);

    return <div>
        Mocap Visualization
    </div>;
});

export default MocapTrialPreview;