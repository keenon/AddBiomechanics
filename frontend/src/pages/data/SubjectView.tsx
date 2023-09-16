import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Table, Button } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import UserHomeDirectory, { SubjectContents, TrialSegmentContents } from "../../model/UserHomeDirectory";
import DropFile from "../../components/DropFile";
import Session from "../../model/Session";
import { Link } from "react-router-dom";

type SubjectViewProps = {
    home: UserHomeDirectory;
    currentLocationUserId: string;
    path: string;
};


const SubjectView = observer((props: SubjectViewProps) => {
    const location = useLocation();
    const navigate = useNavigate();
    const home = props.home;
    const path = props.path;

    const subjectContents: SubjectContents = home.getSubjectContents(path);

    const subjectJson = subjectContents.subjectJson;
    const testFlag = subjectContents.testFlagFile;
    let subjectJsonContents = <div>Loading...</div>;
    if (subjectJson != null) {
        subjectJsonContents = <div>
            <ul>
                <li>
                    Sex: <input type="text"
                        value={subjectJson.getAttribute("sex", "unknown")}
                        onFocus={() => subjectJson.onFocusAttribute("sex")}
                        onBlur={() => subjectJson.onBlurAttribute("sex")}
                        onChange={(e) => {
                            subjectJson.setAttribute("sex", e.target.value);
                        }}></input>
                </li>
            </ul>
        </div>
    }
    let testFlagContents = <div>Loading...</div>;
    if (testFlag != null) {
        if (testFlag.exists) {
            testFlagContents = <div>TEST: True <button onClick={testFlag.delete}>Set False</button></div>
        }
        else {
            testFlagContents = <div>TEST: False <button onClick={testFlag.upload}>Set True</button></div>
        }
    }

    const uploadPath = path + "/test.c3d";
    const pathData = home.getPath(uploadPath, false);
    const uploadTest = (
        <div>
            <DropFile
                pathData={pathData}
                accept=".c3d"
                upload={(file: File, progressCallback: (progress: number) => void) => {
                    if (home == null) {
                        throw new Error("No directory");
                    }
                    return home.dir.uploadFile(uploadPath, file, progressCallback);
                }}
                download={() => {
                    if (home == null) {
                        throw new Error("No directory");
                    }
                    // dir.downloadFile(uploadPath);
                    console.log("Download TODO");
                }}
                required={false} />
        </div>
    );

    return <div>
        <div>
            {subjectJsonContents}
        </div>
        {testFlagContents}
        {uploadTest}
        <h2>Trials:</h2>
        <ul>
            {subjectContents.trials.map(({ name, path }) => {
                return <li key={name}>Trial: <Link to={Session.getDataURL(props.currentLocationUserId, path)}>{name}</Link></li>;
            })}
        </ul>
    </div>
});

export default SubjectView;