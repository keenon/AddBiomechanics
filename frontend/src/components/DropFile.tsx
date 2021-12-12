import React, { useEffect, useState } from "react";
import { Form, ProgressBar, InputGroup, Button } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import MocapS3Cursor from '../state/MocapS3Cursor';
import { humanFileSize } from '../utils';
import Dropzone from "react-dropzone";
import { action } from "mobx";

type DropFileProps = {
    cursor: MocapS3Cursor;
    path: string;
    accept: string;
    uploadOnMount?: File;
};

const DropFile = observer((props: DropFileProps) => {
    let [isUploading, setIsUploading] = useState(false);
    let [uploadProgress, setUploadProgress] = useState(0.0);
    let metadata = props.cursor.rawCursor.getChildMetadata(props.path);

    useEffect(() => {
        if (props.uploadOnMount) {
            setUploadProgress(0.0);
            setIsUploading(true);
            props.cursor.rawCursor.uploadChild(props.path, props.uploadOnMount, setUploadProgress).then(action(() => {
                setIsUploading(false);
            }));
        }
    }, []);

    let body = <></>;

    if (isUploading) {
        body = <ProgressBar
            style={{ width: "100%" }}
            min={0}
            max={1}
            now={uploadProgress}
            striped={true}
            animated={true}
        />;
    }
    else {
        if (metadata != null) {
            body = <>{humanFileSize(metadata.size)} on {metadata.lastModified.toDateString()}</>
        }
        else {
            body = <><i className="text-muted dripicons-cloud-upload" style={{ marginRight: '5px' }}></i> Drop files here or click to upload</>
        }
    }

    return (
        <Dropzone
            {...props}
            onDrop={action((acceptedFiles) => {
                if (acceptedFiles.length > 0) {
                    setUploadProgress(0.0);
                    setIsUploading(true);
                    props.cursor.rawCursor.uploadChild(props.path, acceptedFiles[0], setUploadProgress).then(action(() => {
                        setIsUploading(false);
                    }));
                }
            })}
        >
            {({ getRootProps, getInputProps }) => (
                <div className={"dropzone dropzone-sm" + (metadata != null ? " dropzone-replace" : "")}>
                    <div className="dz-message needsclick" {...getRootProps()}>
                        <input {...getInputProps()} />
                        {body}
                    </div>
                </div>
            )}
        </Dropzone>
    );
});

export default DropFile;
