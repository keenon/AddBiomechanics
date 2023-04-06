import React, { useEffect, useState } from "react";
import { ProgressBar, Button } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import MocapS3Cursor from '../state/MocapS3Cursor';
import { humanFileSize } from '../utils';
import Dropzone from "react-dropzone";
import { action } from "mobx";

type DropFileProps = {
  cursor: MocapS3Cursor;
  path: string;
  accept: string;
  keepFileExtension?: boolean;
  uploadOnMount?: File;
  validateFile?: (f: File) => Promise<string | null>;
  onMultipleFiles?: (files: File[]) => void;
  text?: string;
  hideDate?: boolean;
  required?: boolean;
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
  }, [props.cursor.rawCursor, props.path, props.uploadOnMount]);

  let body = <></>;

  if (props.cursor.dataIsReadonly()) {
    if (metadata != null) {
      return (<Button className="btn-light" onClick={() => props.cursor.rawCursor.downloadFile(props.path)}>
        <i className="mdi mdi-download me-2 vertical-middle"></i>
        Download
      </Button>);
    }
    else {
      return <></>;
    }
  }
  else if (isUploading) {
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
      if (props.hideDate) {
        body = <>{humanFileSize(metadata.size)}</>
      }
      else {
        body = <>{humanFileSize(metadata.size)} on {metadata.lastModified.toDateString()}</>
      }
    }
    else {
      body = <><i className={(props.required ? "" : "text-muted ") + "dripicons-cloud-upload"} style={{ marginRight: '5px' }}></i> {(props.required ? <b>Required: </b> : null)} {props.text ? props.text : "Drop files here or click to upload"}</>
    }
  }

  return (
    <Dropzone
      {...props}
      onDrop={action((acceptedFiles) => {
        if (acceptedFiles.length === 1) {
          let errorPromise: Promise<string | null>;
          if (props.validateFile) {
            errorPromise = props.validateFile(acceptedFiles[0]);
          }
          else {
            errorPromise = Promise.resolve(null);
          }
          errorPromise.then((error: string | null) => {
            if (error != null) {
              alert(error);
            }
            else {
              setUploadProgress(0.0);
              setIsUploading(true);
              let pathToUpload = props.path;
              if (props.keepFileExtension) {
                console.log(acceptedFiles[0].name);
                // Default to the first accepted type
                let extension = props.accept.split(",")[0];
                const fileNameParts = acceptedFiles[0].name.split(".");
                if (fileNameParts.length > 1) {
                  extension = "." + fileNameParts[1];
                }
                pathToUpload = pathToUpload.split(".")[0] + extension;
              }
              props.cursor.rawCursor.uploadChild(pathToUpload, acceptedFiles[0], setUploadProgress).then(action(() => {
                
              })).catch(action(() => {
                
              }));
            }
          });

          /*
          */
        }
        else if (acceptedFiles.length > 1 && props.onMultipleFiles != null) {
          let errorPromise: Promise<string | null>;
          if (props.validateFile) {
            let errorPromises: Promise<string | null>[] = [];
            for (let i = 0; i < acceptedFiles.length; i++) {
              errorPromises.push(props.validateFile(acceptedFiles[i]));
            }
            errorPromise = Promise.all(errorPromises).then((errors: (string | null)[]) => {
              for (let j = 0; j < errors.length; j++) {
                if (errors[j] != null) {
                  return acceptedFiles[j].name + ": " + errors[j];
                }
              }
              return null;
            });
          }
          else {
            errorPromise = Promise.resolve(null);
          }

          errorPromise.then((error: string | null) => {
            if (error != null) {
              alert(error);
            }
            else if (props.onMultipleFiles != null) {
              props.onMultipleFiles(acceptedFiles);
            }
          });
        }
        else if (acceptedFiles.length > 1) {
          alert("This input doesn't accept multiple files at once!");
        }
      })}
    >
      {({ getRootProps, getInputProps, isDragActive }) => {
        const rootProps = getRootProps();
        const inputProps = getInputProps();
        return <div className={"dropzone dropzone-sm" + (metadata != null ? " dropzone-replace" : "") + (isDragActive ? ' dropzone-hover' : ((props.required && metadata == null && !isUploading) ? ' dropzone-error' : ''))} {...rootProps}>
          <div className="dz-message needsclick">
            <input {...inputProps} />
            {body}
          </div>
        </div>
      }}
    </Dropzone >
  );
});

export default DropFile;
