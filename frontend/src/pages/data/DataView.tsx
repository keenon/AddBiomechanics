import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import UserHomeDirectory from "../../model/UserHomeDirectory";
import { observer } from "mobx-react-lite";
import { PathData } from "../../model/LiveDirectory";
import { Link } from "react-router-dom";

type DataViewProps = {
  home: UserHomeDirectory
};

const DataView = observer((props: DataViewProps) => {
  const location = useLocation();

  console.log("Rerendering");

  const dir = props.home.dir;
  let homeDir = <div>Loading home dir...</div>;
  if (dir != null) {
    homeDir = <div>Home dir loaded</div>;
  }

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
  const pathData: PathData = props.home.getPath(location.pathname, false);
  let body = <div>Loading...</div>;

  const pathType = props.home.getPathType(location.pathname);
  if (pathType === 'dataset') {
    const datasetContents = props.home.getDatasetContents(location.pathname);
    if (datasetContents.loading) {
      body = <div>Loading...</div>;
    }
    else {
      body = <div>
        <ul>
          {datasetContents.contents.map(({ name, type, path }) => {
            return <li key={name}>{type}: <Link to={path}>{name}</Link></li>;
          })}
        </ul>
      </div>
    }
  }
  else if (pathType === 'subject') {
    const subjectContents = props.home.getSubjectContents(location.pathname);
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
    body = <div>
      <div>
        {subjectJsonContents}
      </div>
      {testFlagContents}
      <h2>Trials:</h2>
      <ul>
        {subjectContents.trials.map(({ name, path }) => {
          return <li key={name}>Trial: <Link to={path}>{name}</Link></li>;
        })}
      </ul>
    </div>
  }
  else {
    body = <div>Not yet implemented type: {pathType}</div>;
  }

  return (
    <div>
      <h1>Hello World: {location.pathname} - {pathType}</h1>
      {homeDir}
      {body}
    </div>
  );
});

export default DataView;
