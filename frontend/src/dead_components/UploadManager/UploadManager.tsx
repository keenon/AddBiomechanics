import React, { FormEvent, useState } from "react";
import { CSSTransition } from "react-transition-group";
import UserHeader from "../../pages/UserHeader/UserHeader";
import { Link } from "react-router-dom";
import Amplify, { Storage } from "aws-amplify";
import UploadField from "../UploadField/UploadField";
import "./UploadManager.scss";

const UploadManager = () => {
  const [runComparison, setRunComparison] = useState(false);
  const [markerFileList, setMarkerFileList] = useState(null as FileList | null);
  const [handScaledFileList, setHandScaledFileList] = useState(
    null as FileList | null
  );
  const [ikFileList, setIKFileList] = useState(null as FileList | null);

  const [isUploading, setIsUploading] = useState(false);
  const [markerUploadProgress, setMarkerUploadProgress] = useState([0.5]);

  let uploadList = [];
  uploadList.push(
    <CSSTransition
      mountOnEnter
      unmountOnExit
      in={true}
      timeout={200}
      classNames="UploadManager__row-elem-transition"
    >
      <div className="UploadManager__row-elem" key="markers">
        <UploadField
          name="hand-scaled"
          extensions={[".trc"]}
          fileList={markerFileList}
          setFileList={setMarkerFileList}
          uploading={isUploading}
          uploadProgress={markerUploadProgress}
        >
          Marker data
        </UploadField>
      </div>
    </CSSTransition>
  );

  uploadList.push(
    <CSSTransition
      mountOnEnter
      unmountOnExit
      in={runComparison}
      timeout={200}
      classNames="UploadManager__row-elem-transition"
    >
      <div className="UploadManager__row-elem" key="gold-scaled">
        <UploadField
          name="hand-scaled"
          extensions={[".osim"]}
          fileList={handScaledFileList}
          setFileList={setHandScaledFileList}
          uploading={isUploading}
        >
          Hand scaled model
        </UploadField>
      </div>
    </CSSTransition>
  );
  uploadList.push(
    <CSSTransition
      mountOnEnter
      unmountOnExit
      in={runComparison}
      timeout={200}
      classNames="UploadManager__row-elem-transition"
    >
      <div className="UploadManager__row-elem" key="ik">
        <UploadField
          name="hand-scaled"
          extensions={[".mot"]}
          fileList={ikFileList}
          setFileList={setIKFileList}
          uploading={isUploading}
        >
          OpenSim IK
        </UploadField>
      </div>
    </CSSTransition>
  );

  const uploadFiles = (e: FormEvent) => {
    e.preventDefault();

    setIsUploading(true);

    if (markerFileList != null) {
      let initialUploadProgress = [];
      for (let i = 0; i < markerFileList.length; i++) {
        initialUploadProgress.push(0.0);
      }
      setMarkerUploadProgress(initialUploadProgress);

      for (let i = 0; i < markerFileList.length; i++) {
        const file: File = markerFileList[i];
        try {
          const uploadCaptureFileAndIndex = (f: File, i: number) => {
            Storage.put(f.name, f, {
              level: "protected",
              completeCallback: (event) => {
                console.log(`Successfully uploaded ${event.key}`);
              },
              progressCallback: (progress) => {
                console.log(`Uploaded: ${progress.loaded}/${progress.total}`);
                let adjustedProgress = markerUploadProgress;
                adjustedProgress[i] = progress.loaded / progress.total;
                setMarkerUploadProgress(adjustedProgress);
              },
              errorCallback: (err) => {
                console.error("Unexpected error while uploading", err);
              },
            });
          };
          uploadCaptureFileAndIndex(file, i);
        } catch (error) {
          console.log("Error uploading file: ", error);
        }
      }
    }
  };

  return (
    <UserHeader>
      <div className="UploadManager">
        <form className="UploadManager__form">
          <h3>Automatic Scaling, Marker Offsets, and IK</h3>
          <div>
            Human Model:
            <select name="cars" id="cars" className="UploadManager__dropdown">
              <option value="eval">Rajagopal 2015</option>
              <option value="scale">Lai Arnold 2017</option>
            </select>
          </div>
          <div className="UploadManager__row">{uploadList}</div>

          <button type="submit" onClick={uploadFiles}>
            Upload and Process
          </button>

          <div>
            <h3>FAQ: How can I be confident in your results?</h3>
            <label>
              <table className="UploadManager__comparison-table">
                <tbody>
                  <tr>
                    <td className="UploadManager__comparison-checkbox">
                      <input
                        type="checkbox"
                        checked={runComparison}
                        onChange={() => {
                          setRunComparison(!runComparison);
                        }}
                      ></input>
                    </td>
                    <td className="UploadManager__comparison-text">
                      Check this box to compare the output of our algorithms
                      against your own manually fit data.
                    </td>
                  </tr>
                </tbody>
              </table>
            </label>
          </div>
        </form>
      </div>
    </UserHeader>
  );
};

export default UploadManager;
