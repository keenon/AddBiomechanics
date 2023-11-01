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
import { Breadcrumb, BreadcrumbItem } from "react-bootstrap";

type DataViewProps = {
  session: Session;
};

const DataTypeRouter = observer((props: DataViewProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  const dataPath = props.session.parseDataURL(location.pathname);
  const home = dataPath.homeDirectory;
  const path = dataPath.path;
  const readonly = dataPath.userId !== props.session.userId;

  //////////////////////////////////////////////////////////////
  // Set up the breadcrumbs
  //////////////////////////////////////////////////////////////

  let breadcrumbs = [];
  let homeName = '';
  if (dataPath.userId === props.session.userId) {
    homeName = "My Shared Data";
  }
  else if (dataPath.userId === 'private') {
    homeName = "My Private Data";
  }
  else {
    homeName = "User " + dataPath.userId + "";
  }
  breadcrumbs.push(
    <BreadcrumbItem
      href={"/data/" + encodeURIComponent(dataPath.userId) + "/"}
      onClick={(e) => {
        e.preventDefault();
        navigate("/data/" + encodeURIComponent(dataPath.userId) + "/");
      }}
      active={path === '' || path === '/'}
      key={'home'}
    >
      {homeName}
    </BreadcrumbItem>
  );

  const pathParts = path.split('/');
  if (pathParts.length > 0 && pathParts[pathParts.length - 1] === '') {
    pathParts.pop();
  }
  let cumulativePath = '';
  for (let i = 0; i < pathParts.length; i++) {
    let name = pathParts[i];
    if (i > 0) {
      cumulativePath += '/';
    }
    cumulativePath += name;
    const thisBreadcrumbPath = cumulativePath;
    breadcrumbs.push(
      <BreadcrumbItem
        href={"/data/" + encodeURIComponent(dataPath.userId) + "/" + thisBreadcrumbPath}
        onClick={(e) => {
          e.preventDefault();
          navigate("/data/" + encodeURIComponent(dataPath.userId) + "/" + thisBreadcrumbPath);
        }}
        active={i === pathParts.length - 1}
        key={i}
      >
        {name}
      </BreadcrumbItem>
    );
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
  home.dir.faultInPath(path);

  let body = <div>Loading...</div>;

  const pathType = home.getPathType(path);
  if (pathType === 'dataset') {
    body = <DatasetView home={home} path={path} currentLocationUserId={dataPath.userId} readonly={readonly} />
  }
  else if (pathType === 'subject') {
    body = <SubjectView home={home} path={path} currentLocationUserId={dataPath.userId} readonly={readonly} />
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
    return <TrialSegmentView home={home} path={path} currentLocationUserId={dataPath.userId} readonly={readonly} />
  }
  else {
    body = <div>Not yet implemented type: {pathType}</div>;
  }

  let loginStatus = <></>;
  if (props.session.loggedIn) {
    loginStatus = (
      <div className="row mt-2">
        <div className="col">
          Logged in as {props.session.userEmail}. <Link to="/logout">Logout</Link>
        </div>
      </div>
    );
  }
  else if (props.session.loadingLoginState) {
    loginStatus = (
      <div className="row mt-2">
        <div className="col">
          Loading login status...
        </div>
      </div>
    );
  }
  else {
    loginStatus = (
      <div className="row mt-2">
        <div className="col">
          Not logged in. <Link to="/login">Login</Link>
        </div>
      </div>
    );
  }

  return (
    <div className='container'>
      {loginStatus}
      <Breadcrumb className="m-0 mb-0">{breadcrumbs}</Breadcrumb>
      {body}
    </div>
  );
});

export default DataTypeRouter;
