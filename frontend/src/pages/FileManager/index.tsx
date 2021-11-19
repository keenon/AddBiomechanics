// @flow
import React from "react";
import { Link } from "react-router-dom";
import {
  Row,
  Col,
  Card,
  Dropdown,
  ButtonGroup,
  ProgressBar,
} from "react-bootstrap";

// components
import PageTitle from "../../components/PageTitle";

import QuickAccess from "./QuickAccess";
import Recent from "./Recent";

// dummy data
import { quickAccessFiles, recentFiles } from "./data";

// left side panel
const LeftSide = () => {
  return (
    <>
      <ButtonGroup className="d-block mb-2">
        <Dropdown>
          <Dropdown.Toggle className="btn btn-success dropdown-toggle w-100">
            <i className="mdi mdi-plus"></i> Create New{" "}
          </Dropdown.Toggle>
          <Dropdown.Menu>
            <Dropdown.Item>
              <i className="mdi mdi-folder-plus-outline me-1"></i> Folder
            </Dropdown.Item>
            <Dropdown.Item>
              <i className="mdi mdi-file-plus-outline me-1"></i> File
            </Dropdown.Item>
            <Dropdown.Item>
              <i className="mdi mdi-file-document me-1"></i> Document
            </Dropdown.Item>
            <Dropdown.Item>
              <i className="mdi mdi-upload me-1"></i> Choose File
            </Dropdown.Item>
          </Dropdown.Menu>
        </Dropdown>
      </ButtonGroup>

      <div className="email-menu-list mt-3">
        <Link to="/apps/file">
          <i className="mdi mdi-folder-outline font-18 align-middle me-2"></i>
          My Files
        </Link>
        <Link to="/apps/file">
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
    </>
  );
};

// FileManager
const FileManager = () => {
  return (
    <>
      {/*
      <PageTitle
        breadCrumbItems={[
          { label: "Apps", path: "/apps/file" },
          { label: "File Manager", path: "/apps/file", active: true },
        ]}
        title={"File Manager"}
      />
      */}
      <Row className="mt-3">
        <Col md="12">
          <Card>
            <Card.Body>
              <div className="page-aside-left">
                <LeftSide />
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

                <Recent
                  title="My Files"
                  breadCrumbItems={[
                    { label: "Apps", path: "/apps/file" },
                    { label: "File Manager", path: "/apps/file", active: true },
                  ]}
                  recentFiles={recentFiles}
                />
              </div>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
};

export default FileManager;
