import React, { useEffect } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import FolderView from "./FolderView";
import MocapSubjectView from "../mocap/MocapSubjectView";
import { Breadcrumb, BreadcrumbItem, Spinner } from "react-bootstrap";
import MocapS3Cursor from "../../state/MocapS3Cursor";
import { observer } from "mobx-react-lite";
import { parsePath } from './pathHelper';

type FileRouterProps = {
  cursor: MocapS3Cursor;
};

const FileRouter = observer((props: FileRouterProps) => {
  const location = useLocation();
  const navigate = useNavigate();

  useEffect(() => {
    if ((location.pathname === '/data' || location.pathname === '/data/') && props.cursor.myIdentityId !== '') {
      if (props.cursor.authenticated) {
        navigate("/data/" + encodeURIComponent(props.cursor.myIdentityId));
      }
      else {
        navigate("/login", { replace: true, state: { from: location } });
      }
    }
  }, [location.pathname, props.cursor.myIdentityId]);

  const path = parsePath(location.pathname, props.cursor.myIdentityId);

  useEffect(() => {
    props.cursor.setDataPath(path.dataPath);
  }, [props.cursor, path.dataPath]);

  //////////////////////////////////////////////////////////////
  // Set up the breadcrumbs
  //////////////////////////////////////////////////////////////

  let breadcrumbs = [];
  let linkPath = "/data";
  if (path.type === 'mine') {
    linkPath += encodeURIComponent(props.cursor.myIdentityId);
    breadcrumbs.push(
      <BreadcrumbItem
        href={"/data/" + encodeURIComponent(props.cursor.myIdentityId)}
        onClick={(e) => {
          e.preventDefault();
          navigate("/data/" + encodeURIComponent(props.cursor.myIdentityId));
        }}
        active={path.parts.length === 1}
        key="header"
      >
        My Data
      </BreadcrumbItem>
    );
  }
  else if (path.type === 'readonly') {
    breadcrumbs.push(
      <BreadcrumbItem
        href={"/search"}
        onClick={(e) => {
          e.preventDefault();
          navigate("/search");
        }}
        active={path.parts.length === 0}
        key="header"
      >
        Search Public Data
      </BreadcrumbItem>
    );
    if (path.parts.length > 0) {
      linkPath += encodeURIComponent(path.parts[0]);
      breadcrumbs.push(
        <BreadcrumbItem
          href={"/data/" + encodeURIComponent(path.parts[0])}
          onClick={(e) => {
            e.preventDefault();
            navigate("/data/" + encodeURIComponent(path.parts[0]));
          }}
          active={path.parts.length === 1}
          key="user"
        >
          User {path.parts[0]}
        </BreadcrumbItem>
      );
    }
  }
  else if (path.type === 'private') {
    linkPath += "private/";
    breadcrumbs.push(
      <BreadcrumbItem
        href={"/data/private"}
        onClick={(e) => {
          e.preventDefault();
          navigate("/data/private");
        }}
        active={path.parts.length === 1}
        key="header"
      >
        Private Workspace
      </BreadcrumbItem>
    );
  }
  for (let i = 1; i < path.parts.length; i++) {
    linkPath += "/" + encodeURIComponent(path.parts[i]);
    breadcrumbs.push(
      <BreadcrumbItem
        href={linkPath}
        onClick={((savePath) => {
          return (e: React.MouseEvent) => {
            e.preventDefault();
            navigate(savePath);
          };
        })(linkPath)}
        active={i === path.parts.length - 1}
        key={"path" + i}
      >
        {path.parts[i]}
      </BreadcrumbItem>
    );
  }

  //////////////////////////////////////////////////////////////
  // Render the body
  //////////////////////////////////////////////////////////////

  const type = props.cursor.getFileType();
  let body = null;
  if (type === 'folder') {
    body = <FolderView cursor={props.cursor} />;
  }
  else if (type === 'mocap') {
    body = (
      <MocapSubjectView cursor={props.cursor} />
    );
  }
  else if (type === 'not-found') {
    if (props.cursor.getIsLoading()) {
      body = (
        <Spinner animation="border" />
      );
    }
    else {
      body = (
        <div>
          404 Not Found!
        </div>
      );
    }
  }

  return (
    <>
      <div className="mt-0">
        <Breadcrumb className="m-0">{breadcrumbs}</Breadcrumb>
        {body}
      </div>
    </>
  );
});

export default FileRouter;
