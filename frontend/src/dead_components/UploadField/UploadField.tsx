import React, { useRef, useState } from "react";
import "./UploadField.scss";
import download from "./download.svg";
import file from "./file.svg";

type UploadFieldProps = {
  name: string;
  extensions?: string[];
  multiple?: boolean;
  fileList: FileList | null;
  setFileList: (files: FileList | null) => void;
  uploading?: boolean;
  uploadProgress?: number[];
};

const UploadField = (props: React.PropsWithChildren<UploadFieldProps>) => {
  const inputRef = useRef(null);

  const acceptString = props.extensions
    ? props.extensions.join("|")
    : undefined;

  const describeExtensions = props.extensions
    ? props.extensions.map((e) => "*" + e).join(" or ")
    : "";

  let body = null;
  if (props.fileList != null && props.fileList.length > 0) {
    let fileDivs = [];
    for (let i = 0; i < props.fileList.length; i++) {
      let uploadingClass = "";
      let progressBar = null;
      if (props.uploading && props.uploadProgress) {
        if (props.uploadProgress[i] == 1.0) {
          uploadingClass = " UploadField__file-upload-done";
        } else {
          uploadingClass = " UploadField__file-uploading";
        }
        progressBar = (
          <div
            className="UploadField__file-upload-bar"
            style={{
              width: (props.uploadProgress[i] * 100).toString() + "%",
            }}
          ></div>
        );
      }

      fileDivs.push(
        <div key={i} className={"UploadField__file" + uploadingClass}>
          <img src={file} className="UploadField__file-icon" />
          <span className="UploadField__file-text">
            {props.fileList[i].name}
          </span>
          {progressBar}
        </div>
      );
    }
    body = <>{fileDivs}</>;
  } else {
    body = (
      <>
        <img src={download} className="UploadField-img" />
        <div>
          <b>
            Choose {describeExtensions} file{props.multiple ? "(s)" : ""}
          </b>{" "}
          or drag {props.multiple ? "them" : "it"} here
        </div>
      </>
    );
  }

  return (
    <div
      className={
        props.fileList != null && props.fileList.length > 0
          ? "UploadField UploadField-selected"
          : "UploadField"
      }
      onClick={() => {
        if (inputRef.current != null) {
          const uploadElem: HTMLInputElement = inputRef.current;
          uploadElem.click();
        }
      }}
    >
      <div className="UploadField-content">
        {props.children}
        {body}
        <input
          type="file"
          multiple={props.multiple}
          accept={acceptString}
          hidden={true}
          onChange={(e) => {
            if (inputRef.current != null) {
              const uploadElem: HTMLInputElement = inputRef.current;
              props.setFileList(uploadElem.files);
            }
          }}
          ref={inputRef}
        />
      </div>
      <div className="UploadField-inner-bg">
        <div className="UploadField-inner-inner-bg"></div>
      </div>
    </div>
  );
};

export default UploadField;
