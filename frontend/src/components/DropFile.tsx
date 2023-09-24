import React, { useEffect, useState } from "react";
import { PathData } from "../model/LiveDirectory";
import { ProgressBar, Button } from "react-bootstrap";
import { humanFileSize } from '../utils';
import { action } from "mobx";
import { FileMetadata } from "../model/S3API";
import LiveFile from "../model/LiveFile";
import { observer } from "mobx-react-lite";

type DropFileProps = {
  file: LiveFile;
  readonly: boolean;
  accept: string;
  onDrop: (f: File[]) => Promise<void>;
  text?: string;
  hideDate?: boolean;
  required?: boolean;
};

const DropFile = observer((props: DropFileProps) => {
  let [isDragActive, setIsDragActive] = useState(false);

  let body = <></>;

  const loading: Promise<void> | null = props.file.loading;
  const exists = props.file.exists;
  const uploading = props.file.uploading;
  const metadata = props.file.metadata;

  if (props.readonly) {
    if (exists) {
      return (<Button className="btn-light" onClick={() => props.file.download()}>
        <i className="mdi mdi-download me-2 vertical-middle"></i>
        Download
      </Button>);
    }
    else {
      return <></>;
    }
  }
  else if (uploading) {
    body = <ProgressBar
      style={{ width: "100%" }}
      min={0}
      max={1}
      now={props.file.uploadProgress}
      striped={true}
      animated={true}
    />;
  }
  else {
    if (loading != null) {
      body = <><i className="mdi mdi-loading mdi-spin me-2"></i> Loading...</>
    }
    else if (exists && metadata != null) {
      const file: FileMetadata = metadata;
      if (props.hideDate) {
        body = <>{humanFileSize(file.size)}</>
      }
      else {
        body = <>{humanFileSize(file.size)} on {file.lastModified.toDateString()}</>
      }
    }
    else {
      body = <><i className={(props.required ? "" : "text-muted ") + "dripicons-cloud-upload"} style={{ marginRight: '5px' }}></i> {(props.required ? <b>Required: </b> : null)} {props.text ? props.text : "Drop files here or click to upload"}</>
    }
  }

    const onDrop = action((e: DragEvent) => {
        setIsDragActive(false);
        e.preventDefault();

        let acceptedFiles: File[] = [];
        if (e.dataTransfer && e.dataTransfer.items) {
            for (let i = 0; i < e.dataTransfer.items.length; i++) {
                if (e.dataTransfer.items[i].kind === 'file') {
                    const file = e.dataTransfer.items[i].getAsFile();
                    if (file) {
                        acceptedFiles.push(file);
                    }
                }
            }
        }

        props.onDrop(acceptedFiles).catch((e) => {
          console.error(e);
          alert(e);
        });
      });

  return (
    <div className={"dropzone dropzone-sm" + (exists ? " dropzone-replace" : "") + (isDragActive ? ' dropzone-hover' : ((props.required && !exists && !uploading) ? ' dropzone-error' : ''))}
        onDrop={onDrop as any}
        onDragOver={(e) => {
          e.preventDefault();
        }}
        onDragEnter={() => {
          setIsDragActive(true);
        }}
        onDragLeave={() => {
          setIsDragActive(false);
        }}>
      <div className="dz-message needsclick">
        {body}
      </div>
    </div>
  );
});

export default DropFile;
