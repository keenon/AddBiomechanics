import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import FolderView from "./FolderView";
import MocapView from "./MocapView";
import { Breadcrumb, BreadcrumbItem, Spinner } from "react-bootstrap";
import { MocapFolder } from "../state/MocapS3";
import { observer } from "mobx-react-lite";

type FileRouterProps = {
  isRootFolderPublic: boolean;
  linkPrefix: string;
  rootFolder: MocapFolder;
};

const FileRouter = observer((props: FileRouterProps) => {
  const location = useLocation();
  const navigate = useNavigate();
  const path = location.pathname.split("/");
  while (path.length > 0 && path[0].length == 0) {
    path.splice(0, 1);
  }
  while (path.length > 0 && path[path.length - 1].length == 0) {
    path.splice(path.length - 1, 1);
  }

  const LINK_PREFIX = props.linkPrefix;
  if (path.length > 0 && path[0] == LINK_PREFIX) {
    path.splice(0, 1);
  }

  //////////////////////////////////////////////////////////////
  // Set up the breadcrumbs
  //////////////////////////////////////////////////////////////

  let breadcrumbs = [];
  breadcrumbs.push(
    <BreadcrumbItem
      href={"/" + LINK_PREFIX}
      onClick={(e) => {
        e.preventDefault();
        navigate("/" + LINK_PREFIX);
      }}
      active={path.length === 0}
    >
      {props.isRootFolderPublic ? "Public" : "My Data"}
    </BreadcrumbItem>
  );
  let linkPath = "/" + LINK_PREFIX;
  for (let i = 0; i < path.length; i++) {
    linkPath += "/" + path[i];
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

  let body = null;
  if (props.rootFolder.backingFolder.loading) {
    body = <Spinner animation="border" />;
  } else {
    const dataType = props.rootFolder.getDataType(path);
    if (dataType == "folder") {
      const folder = props.rootFolder.getFolder(path);
      body = <FolderView folder={folder} linkPrefix={linkPath} />;
    } else if (dataType == "mocap") {
      const mocap = props.rootFolder.getMocapClip(path);
      body = <MocapView clip={mocap} />;
    } else {
      body = (
        <div>
          TODO: {dataType} @ {path}
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
