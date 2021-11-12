import React, { useState } from "react";
import UserHeader from "../UserHeader/UserHeader";
import LeftTabs from "../LeftTabs/LeftTabs";
import { Link } from "react-router-dom";
import UploadField from "../UploadField/UploadField";
import "./UploadManager.scss";

const UploadManager = () => {
  const [runComparison, setRunComparison] = useState(false);

  let uploadList = [];
  uploadList.push(
    <div className="UploadManager__row-elem" key="markers">
      <UploadField name="hand-scaled" extensions={[".trc"]}>
        Marker data
      </UploadField>
    </div>
  );

  if (runComparison) {
    uploadList.push(
      <div className="UploadManager__row-elem" key="gold-scaled">
        <UploadField name="hand-scaled" extensions={[".osim"]}>
          Hand scaled model
        </UploadField>
      </div>
    );
    uploadList.push(
      <div className="UploadManager__row-elem" key="ik">
        <UploadField name="hand-scaled" extensions={[".mot"]}>
          OpenSim IK
        </UploadField>
      </div>
    );
  }

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

          <button type="submit">Upload and Process</button>

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
                        onClickCapture={() => {
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
