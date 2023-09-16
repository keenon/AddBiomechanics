import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import UserHomeDirectory from "../../model/UserHomeDirectory";
import { observer } from "mobx-react-lite";
import { PathData } from "../../model/LiveDirectory";
import { Link } from "react-router-dom";
import DropFile from "../../components/DropFile";
import TrialSegmentView from "./TrialSegment";
import DatasetView from "./DatasetView";
import Session from "../../model/Session";

type DataViewProps = {
  session: Session;
};

const DataView = observer((props: DataViewProps) => {
  const location = useLocation();

  console.log("Rerendering");

  const dataPath = props.session.parseDataURL(location.pathname);
  const home = dataPath.homeDirectory;
  const path = dataPath.path;
  console.log("Home S3 prefix: " + home.dir.prefix);
  console.log("Path: " + path);

  // let entries: JSX.Element[] = [];
  // const pathData: PathData = props.home.getPath(location.pathname, false);
  // if (pathData.loading) {
  //   entries = [<li key='loading'>Loading...</li>];
  // }
  // else {
  //   console.log(JSON.stringify(pathData, null, 2));
  //   entries = pathData.files.map((file) => {
  //     return <li key={"file: " + file.key}>{file.key}</li>;
  //   }).concat(pathData.folders.map((folder) => {
  //     return <li key={"folder: " + folder}><Link to={folder}>{folder}</Link></li>;
  //   }));
  // }

  // Force a load of the current location
  home.dir.faultInPath(path);

  let body = <div>Loading...</div>;

  const pathType = home.getPathType(path);
  if (pathType === 'dataset') {
    body = <DatasetView session={props.session} path={path} />
  }
  else if (pathType === 'subject') {
    const subjectContents = home.getSubjectContents(path);
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

    body = <div>
      <div>
        {subjectJsonContents}
      </div>
      {testFlagContents}
      {uploadTest}
      <h2>Trials:</h2>
      <ul>
        {subjectContents.trials.map(({ name, path }) => {
          return <li key={name}>Trial: <Link to={props.session.getDataURL(dataPath, path)}>{name}</Link></li>;
        })}
      </ul>
    </div>
  }
  else if (pathType === 'trial') {
    const trialContents = home.getTrialContents(path);
    body = <div>
      This is a trial!
      It has {trialContents.segments.length} segments.
      <ul>
        {trialContents.segments.map(({ name, path }) => {
          return <li key={name}>Trial Segment: <Link to={props.session.getDataURL(dataPath, path)}>{name}</Link></li>;
        })}
      </ul>
    </div>
  }
  else if (pathType === 'trial_segment') {
    return <TrialSegmentView session={props.session} path={path} />
  }
  else {
    body = <div>Not yet implemented type: {pathType}</div>;
  }

  return (
    <div>
      <h1>Hello World: {path} - {pathType} - {dataPath.readonly ? 'readonly' : 'readwrite'}</h1>
      {body}
    </div>
  );
});

export default DataView;
