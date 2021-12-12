import React, { useState } from "react";
import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  Row,
  Col,
  Card,
  Dropdown,
  ButtonGroup,
  Modal,
  Button,
} from "react-bootstrap";
import NewFolderModal from "./file-control-modals/NewFolderModal";
import DeleteFolderModal from "./file-control-modals/DeleteFolderModal";
import MocapS3Cursor from "../../state/MocapS3Cursor";

import { observer } from "mobx-react-lite";

type FileManagerProps = {
  cursor: MocapS3Cursor;
  linkPrefix: string;
};

// FileManager
const FileManager = observer((props: FileManagerProps) => {
  const navigate = useNavigate();
  const location = useLocation();
  const path = location.pathname.split('/');
  while (path.length > 0 && (path[0] == props.linkPrefix) || (path[0] == '')) {
    path.splice(0, 1);
  }

  const type = props.cursor.getFileType();

  let body = <Outlet />;
  if (type === "folder") {
    body = (
      <>
        <div className="page-aside-left">
          {/* "Create" dropdown */}
          <ButtonGroup className="d-block mb-2">
            <Dropdown>
              <Dropdown.Toggle className="btn btn-success dropdown-toggle w-100">
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
          {/* Left side nav links */}
          <div className="email-menu-list mt-3">
            <Link to="#">
              <i className="mdi mdi-folder-outline font-18 align-middle me-2"></i>
              My Files
            </Link>
            <Link to="#">
              <i className="mdi mdi-earth font-18 align-middle me-2"></i>
              Public Files
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
