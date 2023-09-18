import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import UserHomeDirectory from "../../model/UserHomeDirectory";
import { observer } from "mobx-react-lite";
import { PathData } from "../../model/LiveDirectory";
import { Link } from "react-router-dom";
import TrialSegmentView from "./TrialSegment";
import DatasetView from "./DatasetView";
import SubjectView from "./SubjectView";
import Session from "../../model/Session";

type DataViewProps = {
  session: Session;
};

const DataTypeRouter = observer((props: DataViewProps) => {
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
    body = <DatasetView home={home} path={path} currentLocationUserId={dataPath.userId} />
  }
  else if (pathType === 'subject') {
    return <SubjectView home={home} path={path} currentLocationUserId={dataPath.userId} />
  }
  else if (pathType === 'trial') {
    const trialContents = home.getTrialContents(path);
    body = <div>
      This is a trial!
      It has {trialContents.segments.length} segments.
      <ul>
        {trialContents.segments.map((segment) => {
          return <li key={segment.name}>Trial Segment: <Link to={Session.getDataURL(dataPath.userId, segment.path)}>{segment.name}</Link></li>;
        })}
      </ul>
    </div>
  }
  else if (pathType === 'trial_segment') {
    return <TrialSegmentView home={home} path={path} />
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

export default DataTypeRouter;
