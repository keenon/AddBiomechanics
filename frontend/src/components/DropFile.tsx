import React, { useState } from "react";
import { ProgressBar, Button } from "react-bootstrap";
import { humanFileSize } from '../utils';
import { action } from "mobx";
import { FileMetadata } from "../model/S3API";
import LiveFile from "../model/LiveFile";
import { observer } from "mobx-react-lite";
import * as path from 'path';
import { format } from 'date-fns';
import './DropFile.scss'

type DropFileProps = {
  file: LiveFile;
  readonly: boolean;
  accept: string;
  onDrop: (f: File[]) => Promise<void>;
  onDeleteFile?: () => void;
  text?: string;
  hideDate?: boolean;
  required?: boolean;
  original_name?: string;
};

const DropFile = observer((props: DropFileProps) => {
  let [isDragActive, setIsDragActive] = useState(false);

  let body = <></>;
  let body_download = <></>;
  let body_remove = <></>

  const loading: Promise<void> | null = props.file.loading;
  const exists = props.file.exists;
  const uploading = props.file.uploading;
  const metadata = props.file.metadata;

  if (props.readonly) {
    if (exists) {
      if (metadata != null) {
        const file: FileMetadata = metadata;
        const file_path:string = metadata.key;
        let fileName: string = "";

        if (path.basename(file_path).split('.').pop() === "trc" || path.basename(file_path).split('.').pop() === "mot")
          fileName = path.basename(path.dirname(file_path)) + "." + path.basename(file_path).split('.').pop();
        else
          fileName = path.basename(file_path)
        console.log(fileName)
        return (<Button className="btn-light ml-2" onClick={() => props.file.download(fileName)}>
          <i className="mdi mdi-download me-2 vertical-middle middle"></i>
          Download <b>{fileName} - {humanFileSize(file.size)}</b>
        </Button>);
      }
      else {
        return (<Button className="btn-light ml-2" onClick={() => props.file.download()}>
          <i className="mdi mdi-download me-2 vertical-middle middle"></i>
          Download
        </Button>);
      }
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
    else if (exists) {
      if (metadata != null) {
        const file: FileMetadata = metadata;
        let fileName: string = "";
        if (path.basename(file.key).split('.').pop() === "trc" || path.basename(file.key).split('.').pop() === "mot")
          fileName = path.basename(path.dirname(file.key)) + "." + path.basename(file.key).split('.').pop();
        else
          fileName = path.basename(file.key)
        if (props.hideDate) {
          body = <>Uploaded <b>{fileName} - {humanFileSize(file.size)}</b></>
          body_download = <Button className="btn-light DropFile__light_button form-text" onClick={() => props.file.download(fileName)}>
            <i className="mdi mdi-download me-2 vertical-middle"></i>
            Download {/*<b>{path.basename(file.key)}</b> - */} <b>{humanFileSize(file.size)}</b>
          </Button>
        }
        else {
          body = <>Uploaded <b>{fileName}</b> on {format(file.lastModified.toString(), 'yyyy/MM/dd kk:mm:ss')} - {humanFileSize(file.size)}</>
          body_download = <Button className="btn-light DropFile__light_button form-text" onClick={() => props.file.download(fileName)}>
            <i className="mdi mdi-download me-2 vertical-middle"></i>
            Download {/*<b>{path.basename(file.key)}</b> - */} <b>{humanFileSize(file.size)}</b>
          </Button>
        }
        body_remove = <Button className="btn-light DropFile__delete_button form-text" onClick={() => {
          if (window.confirm(`Are you sure you want to delete ${path.basename(file.key)}?`)) {
            props.file.delete(); if (props.onDeleteFile !== undefined) props.onDeleteFile();
          }
        }}>
          <i className="mdi mdi-delete me-2 vertical-middle"></i>
          Delete {/*<b>{path.basename(file.key)}</b>*/}
        </Button>
      }
      else {
        body = <>Loading size...</>
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

  const handleFileSelect = () => {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.multiple = true; // Allow multiple file selection
    fileInput.addEventListener('change', (event) => {
      const inputElement = event.target as HTMLInputElement;

      let acceptedFiles: File[] = [];
      if (inputElement.files) {
        const files = Array.from(inputElement.files);
        files.forEach((file) => {
          acceptedFiles.push(file);
        });


        props.onDrop(acceptedFiles).catch((e) => {
          console.error(e);
          alert(e);
        });
      }
    });
    fileInput.click();
  };

  return (
    <>
      <div className={"DropFile dropzone dropzone-sm" + (exists ? " dropzone-replace" : "") + (isDragActive ? ' dropzone-hover' : ((props.required && !exists && !uploading) ? ' dropzone-error' : ''))}
        onDrop={onDrop as any}
        onDragOver={(e) => {
          e.preventDefault();
        }}
        onDragEnter={() => {
          setIsDragActive(true);
        }}
        onDragLeave={() => {
          setIsDragActive(false);
        }}
        onClick={(e) => {
          //e.preventDefault();
          handleFileSelect();
        }}>
        <div className="dz-message needsclick" style={{
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
        }}>
          {body}
        </div>
      </div>
      <div className="flex-container">
        {body_download}
        {body_remove}
      </div>
    </>
  );
});

export default DropFile;
