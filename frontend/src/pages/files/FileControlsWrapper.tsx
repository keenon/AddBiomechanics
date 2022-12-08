import React from "react";
import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  Row,
  Col,
  Card,
  Dropdown,
  ButtonGroup,
} from "react-bootstrap";
import NewFolderModal from "./file-control-modals/NewFolderModal";
import DeleteFolderModal from "./file-control-modals/DeleteFolderModal";
import MocapS3Cursor from "../../state/MocapS3Cursor";
import './FileControlsWrapper.scss';

import { observer } from "mobx-react-lite";
import { parsePath } from './pathHelper';

type FileManagerProps = {
  cursor: MocapS3Cursor;
};

// FileManager
const FileManager = observer((props: FileManagerProps) => {
  const navigate = useNavigate();
  const location = useLocation();

  const path = parsePath(location.pathname, props.cursor.myIdentityId);

  const type = props.cursor.getFileType();

  let body = <Outlet />;
  if (type === "folder" && props.cursor.authenticated) {
    let dropdown = null;
    if (path.type === 'mine' || path.type === 'private') {
      dropdown = (
        <ButtonGroup className="d-block mb-2">
          <Dropdown>
            <Dropdown.Toggle className="btn btn-primary dropdown-toggle w-100">
              <i className="mdi mdi-plus"></i> Create New{" "}
            </Dropdown.Toggle>
            <Dropdown.Menu>
              <Dropdown.Item
                onClick={() => navigate({ search: "?new-folder" })}
              >
                <i className="mdi mdi-folder-plus-outline me-1"></i> Folder
              </Dropdown.Item>
              <Dropdown.Item
                onClick={() => navigate({ search: "?new-subject" })}
              >
                <i className="mdi mdi-run me-1"></i> Subject
              </Dropdown.Item>
            </Dropdown.Menu>
          </Dropdown>
        </ButtonGroup>
      );
    }

    let securityNotice = <div>{path.type}</div>;
    if (path.type === 'mine') {
      securityNotice = (
        <div className="d-flex justify-content-between align-items-center">
          <div className="FileControlsWrapper-folder-description">
            This folder is accessible to anyone who has the link (<a href={window.location.href}>{window.location.href}</a>), but is not searchable.
          </div>
          {/*
          <div>
            <button type="submit" className="btn btn-primary">
              <i className="mdi mdi-earth-plus"></i> Make Searchable
            </button>
          </div>
          */}
        </div>
      );
    }
    else if (path.type === 'private') {
      securityNotice = (
        <div className="d-flex justify-content-between align-items-center">
          <div className="FileControlsWrapper-folder-description">
            <p>
              This folder is password protected and only accessible from your account.{' '} <i className="mdi mdi-lock-outline font-18 align-middle me-2"></i>
            </p>
            <p>
              <b>Please try not to use this area:</b> AddBiomechanics is a community effort to create a big public dataset that everyone can benefit from! When you upload here, you're not sharing your data with the community. We understand that getting IRB approvals to share de-identified data publicly takes time, so you can use this area in the meantime. We don't limit your use of this area, but we ask that you make a good faith effort to share your data as soon as you can.
            </p>
            <p>
              If we see you using this area a lot, we'll reach out by email to see if we can help with your data-sharing approval process.
            </p>
          </div>
        </div>
      );
    }

    body = (
      <>
        <div className="page-aside-left">
          {dropdown}
          {/* Left side nav links */}
          <div className="email-menu-list mt-3">
            <Link to={"/data/" + encodeURIComponent(props.cursor.myIdentityId)}>
              <i className="mdi mdi-folder-outline font-18 align-middle me-2"></i>
              My Data
            </Link>
            <Link to="/data/private">
              <i className="mdi mdi-lock-outline font-18 align-middle me-2"></i>
              Private Workspace
            </Link>
          </div>
          {/*
                  <div className="mt-5">
                    <h4>
                      <span className="badge rounded-pill p-1 px-2 bg-secondary">FREE</span>
                    </h4>
                    <h6 className="text-uppercase mt-3">Storage</h6>
                    <ProgressBar variant="success" now={46} className="my-2 progress-sm" />
                    <p className="text-muted font-13 mb-0">7.02 GB (46%) of 15 GB used</p>
                  </div>
                  */}
        </div>
        <div className="page-aside-right">
          {/*
          <div className="d-flex justify-content-between align-items-center">
            <div className="app-search">
              <form>
                <div className="mb-2 position-relative">
                  <input
                    type="text"
                    className="form-control"
                    placeholder="Search files..."
                  />
                  <span className="mdi mdi-magnify search-icon"></span>
                </div>
              </form>
            </div>
            <div>
              <button type="submit" className="btn btn-sm btn-light">
                <i className="mdi mdi-format-list-bulleted"></i>
              </button>
              <button type="submit" className="btn btn-sm">
                <i className="mdi mdi-view-grid"></i>
              </button>
              <button type="submit" className="btn btn-sm">
                <i className="mdi mdi-information-outline"></i>
              </button>
            </div>
          </div>
          */}


          {/*
                <QuickAccess quickAccessFiles={quickAccessFiles} />
                */}
          {securityNotice}
          {/*
          <div className="d-flex justify-content-between align-items-center">
            <div className="FileControlsWrapper-folder-description">
              Public link: <a href="https://addbiomechanics.org/atnthoeunth/OpenCapDataset">https://addbiomechanics.org/atnthoeunth/OpenCapDataset</a>
            </div>
            <div>
              <button type="submit" className="btn btn-primary">
                <i className="mdi mdi-earth-plus"></i> Publish Folder
              </button>
            </div>
          </div>
          */}

          <Outlet />
        </div>
      </>
    );
  }

  return (
    <>
      <Row className="mt-3">
        <Col md="12">
          <Card className="mt-4">
            <Card.Body>
              <NewFolderModal {...props} />
              <DeleteFolderModal {...props} />
              {body}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
});

export default FileManager;
