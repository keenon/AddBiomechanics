import React from "react";
import { useLocation, useNavigate } from "react-router-dom";
import FolderView from "./FolderView";
import MocapView from "./MocapView";
import { Breadcrumb, BreadcrumbItem, Spinner } from "react-bootstrap";
import { MocapFolder, parsePathParts } from "../state/MocapS3";
import { observer } from "mobx-react-lite";

type FileRouterProps = {
  isRootFolderPublic: boolean;
  linkPrefix: string;
  rootFolder: MocapFolder;
};

const FileRouter = observer((props: FileRouterProps) => {
  const location = useLocation();
  const navigate = useNavigate();
  const path = parsePathParts(location.pathname, props.linkPrefix);

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
