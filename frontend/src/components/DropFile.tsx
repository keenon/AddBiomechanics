import React, { useEffect, useState } from "react";
import { PathData } from "../model/LiveDirectory";
import { ProgressBar, Button } from "react-bootstrap";
import { humanFileSize } from '../utils';
import Dropzone from "react-dropzone";
import { action } from "mobx";
import { FileMetadata } from "../model/S3API";

type DropFileProps = {
  pathData: PathData;
  upload: (file: File, progressCallback: (progress: number) => void) => Promise<void>;
  download: () => void;
  accept: string;
  uploadOnMount?: File;
  validateFile?: (f: File) => Promise<string | null>;
  onMultipleFiles?: (files: File[]) => void;
  text?: string;
  hideDate?: boolean;
  required?: boolean;
};

const DropFile = (props: DropFileProps) => {
  let [isUploading, setIsUploading] = useState(false);
  let [uploadProgress, setUploadProgress] = useState(0.0);

  useEffect(() => {
    if (props.uploadOnMount) {
      setUploadProgress(0.0);
      setIsUploading(true);
      props.upload(props.uploadOnMount, (progress) => {
        setUploadProgress(progress);
      }).then(action(() => {
        console.log("Finished upload");
        setIsUploading(false);
      }));
    }
  }, [props.uploadOnMount]);

  let body = <></>;

  if (props.pathData.readonly) {
    if (props.pathData.files.length === 1) {
      return (<Button className="btn-light" onClick={() => props.download()}>
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
    if (props.pathData.files.length === 1) {
      const file: FileMetadata = props.pathData.files[0];
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
              props.upload(acceptedFiles[0], (progress) => {
                setUploadProgress(progress);
              }).then(action(() => {
                console.log("Finished upload");
                setIsUploading(false);
              })).catch(action(() => {
                console.log("Caught error during upload");
                setIsUploading(false);
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
        return <div className={"dropzone dropzone-sm" + (props.pathData.files.length === 1 ? " dropzone-replace" : "") + (isDragActive ? ' dropzone-hover' : ((props.required && props.pathData.files.length !== 1 && !isUploading) ? ' dropzone-error' : ''))} {...rootProps}>
          <div className="dz-message needsclick">
            <input {...inputProps} />
            {body}
          </div>
        </div>
      }}
    </Dropzone >
  );
};

export default DropFile;
