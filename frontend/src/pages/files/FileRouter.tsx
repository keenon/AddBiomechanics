import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import FolderView from "./FolderView";
import MocapSubjectView from "../mocap/MocapSubjectView";
import { Breadcrumb, BreadcrumbItem, Spinner } from "react-bootstrap";
import MocapS3Cursor from "../../state/MocapS3Cursor";
import { observer } from "mobx-react-lite";
import { autorun } from "mobx";

type FileRouterProps = {
  isRootFolderPublic: boolean;
  linkPrefix: string;
  cursor: MocapS3Cursor;
};

const FileRouter = observer((props: FileRouterProps) => {
  const location = useLocation();
  const navigate = useNavigate();
  props.cursor.setUrlPath(location.pathname);

  const path = location.pathname.split('/');
  while (path.length > 0 && (path[0] == props.linkPrefix) || (path[0] == '')) {
    path.splice(0, 1);
  }


  //////////////////////////////////////////////////////////////
  // Set up the breadcrumbs
  //////////////////////////////////////////////////////////////

  let breadcrumbs = [];
  breadcrumbs.push(
    <BreadcrumbItem
      href={"/" + props.linkPrefix}
      onClick={(e) => {
        e.preventDefault();
        navigate("/" + props.linkPrefix);
      }}
      active={path.length === 0}
    >
      {props.isRootFolderPublic ? "Public" : "My Data"}
    </BreadcrumbItem>
  );
  let linkPath = "/" + props.linkPrefix;
  for (let i = 0; i < path.length; i++) {
    linkPath += "/" + encodeURIComponent(path[i]);
    breadcrumbs.push(
      <BreadcrumbItem
        href={linkPath}
        onClick={((savePath) => {
          return (e: React.MouseEvent) => {
            e.preventDefault();
            navigate(savePath);
          };
        })(linkPath)}
        active={i === path.length - 1}
      >
        {path[i]}
      </BreadcrumbItem>
    );
  }

  //////////////////////////////////////////////////////////////
  // Render the body
  //////////////////////////////////////////////////////////////

  const type = props.cursor.getFileType();
  console.log("Re-rendering FileRouter");
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
    body = (
      <div>
        404 Not Found!
      </div>
    );
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
