import React, { useRef, useState } from "react";
import "./UploadField.scss";
import download from "./download.svg";
import file from "./file.svg";

type UploadFieldProps = {
  name: string;
  extensions?: string[];
  multiple?: boolean;
};

const UploadField = (props: React.PropsWithChildren<UploadFieldProps>) => {
  const inputRef = useRef(null);
  const [fileList, setFileList] = useState(null as FileList | null);

  const acceptString = props.extensions
    ? props.extensions.join("|")
    : undefined;

  const describeExtensions = props.extensions
    ? props.extensions.map((e) => "*" + e).join(" or ")
    : "";

  let body = null;
  if (fileList != null) {
    let fileDivs = [];
    for (let i = 0; i < fileList.length; i++) {
      fileDivs.push(
        <div key={i} className="UploadField__file">
          <img src={file} className="UploadField__file-icon" />
          {fileList[i].name}
        </div>
      );
    }
    body = <div>{fileDivs}</div>;
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
        fileList != null ? "UploadField UploadField-selected" : "UploadField"
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
              setFileList(uploadElem.files);
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
