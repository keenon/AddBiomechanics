import React from "react";
import { Link, Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  Row,
  Col,
  Card,
  Dropdown,
  OverlayTrigger,
  Tooltip,
  ButtonGroup,
} from "react-bootstrap";
import NewFolderModal from "./file-control-modals/NewFolderModal";
import DeleteFolderModal from "./file-control-modals/DeleteFolderModal";
import MocapS3Cursor from "../../state/MocapS3Cursor";
import { ReactiveJsonFile } from '../../state/ReactiveS3';
import './FileControlsWrapper.scss';
import { useState, useEffect } from "react";
import { observer } from "mobx-react-lite";
import { parsePath } from './pathHelper';
import { showToast, copyProfileUrlToClipboard, getIdFromURL } from "../../utils";

type FileManagerProps = {
  cursor: MocapS3Cursor;
};

type ProfileJSON = {
  name: string;
  surname: string;
  contact: string;
  affiliation: string;
  personalWebsite: string;
  lab: string;
}

// FileManager
const FileManager = observer((props: FileManagerProps) => {
  const navigate = useNavigate();
  const location = useLocation();

  const path = parsePath(location.pathname, props.cursor.s3Index.myIdentityId);

  const urlId = getIdFromURL(location.pathname);

  const fullName = props.cursor.getOtherProfileFullName(urlId);

  const type = props.cursor.getFileType();

  let body = <Outlet />;
  if (type === "folder" && props.cursor.s3Index.authenticated) {
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

    let securityNotice = <></>;

    if (path.type === 'mine') {
      // This is the section of the left bar where the user can edit the properties of the dataset
      const getEditableDescriptionSection = (searchJson: ReactiveJsonFile) => {
        return <>
          <div>
            <label className="mb-1">
              Dataset Title:
              <OverlayTrigger
                placement="right"
                delay={{ show: 50, hide: 400 }}
                overlay={(props) => (
                  <Tooltip id="button-tooltip" {...props}>
                    This is the name of the dataset, currently not editable
                  </Tooltip>
                )}>
                <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
              </OverlayTrigger>
            </label>
            <textarea className="mb-2" style={{ width: '100%' }} placeholder="Full title of dataset" value={searchJson.getAttribute("title", "")} onChange={(e) => {
              searchJson.setAttribute("title", e.target.value);
            }} onFocus={() => searchJson.onFocusAttribute("title")} onBlur={() => searchJson.onBlurAttribute("title")} />
          </div>
          <div>
            <fieldset>
              <label className="mb-1">
                Dataset Information:
                <OverlayTrigger
                  placement="right"
                  delay={{ show: 50, hide: 400 }}
                  overlay={(props) => (
                    <Tooltip id="button-tooltip" {...props}>
                      Insert public notes about the dataset (purpose, description, number of subjects, etc.). It is your responsibility to not include any Personally Identifiable Information (PII) about your subjects!
                    </Tooltip>
                  )}>
                  <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                </OverlayTrigger>
              </label>
              <textarea className="mb-2" style={{ width: '100%' }} placeholder="Public notes (how to cite, etc). It is your responsibility to not include any Personally Identifiable Information (PII) about your subjects!" value={searchJson.getAttribute("notes", "")} onChange={(e) => {
                searchJson.setAttribute("notes", e.target.value);
              }} onFocus={() => searchJson.onFocusAttribute("notes")} onBlur={() => searchJson.onBlurAttribute("notes")} />
              <label className="mb-1">
                Citation:
                <OverlayTrigger
                  placement="right"
                  delay={{ show: 50, hide: 400 }}
                  overlay={(props) => (
                    <Tooltip id="button-tooltip" {...props}>
                      Insert how do you prefer to be cited.
                    </Tooltip>
                  )}>
                  <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                </OverlayTrigger>
              </label>
              <textarea className="mb-2" style={{ width: '100%' }} placeholder="Insert how do you want to be cited. (e.g., you can insert a citation in any style, like APA or IEEE." value={searchJson.getAttribute("citation", "")} onChange={(e) => {
                searchJson.setAttribute("citation", e.target.value);
              }} onFocus={() => searchJson.onFocusAttribute("citation")} onBlur={() => searchJson.onBlurAttribute("citation")} />
              <label className="mb-1">
                Funding:
                <OverlayTrigger
                  placement="right"
                  delay={{ show: 50, hide: 400 }}
                  overlay={(props) => (
                    <Tooltip id="button-tooltip" {...props}>
                      Insert information about funding supporting this project.
                    </Tooltip>
                  )}>
                  <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                </OverlayTrigger>
              </label>
              <textarea className="mb-2" style={{ width: '100%' }} placeholder="Insert information about funding supporting this project." value={searchJson.getAttribute("funding", "")} onChange={(e) => {
                searchJson.setAttribute("funding", e.target.value);
              }} onFocus={() => searchJson.onFocusAttribute("funding")} onBlur={() => searchJson.onBlurAttribute("funding")} />
            </fieldset>
          </div>
        </>;
      };

      const childOfSearchable = props.cursor.isChildOfSearchable();
      if (childOfSearchable) {
        const parentPathParts = childOfSearchable.split("/");
        const userId = parentPathParts[0];
        const data = parentPathParts[1];
        let path = '/data/' + userId + '/' + parentPathParts.slice(2).join('/');
        let parentName = parentPathParts[parentPathParts.length - 1];
        if (parentName === 'data') {
          parentName = 'My Data';
        }
        const otherDatasetJson = props.cursor.getDatasetSearchJson(childOfSearchable);
        securityNotice = (
          <>
            <h4>
              <span className="badge rounded-pill p-1 px-2 bg-success mb-2">FINALIZED SUBFOLDER</span>
              <OverlayTrigger
                placement="right"
                delay={{ show: 50, hide: 800 }}
                overlay={(props) => (
                  <Tooltip id="button-tooltip" {...props}>
                    <p>This is a sub-folder in a <b>finalized dataset</b>, and can be found on the AddBiomechanics <Link to="/search">search page</Link>.</p>
                    <p>You can leave public notes to help others using the data (how to cite the data, etc). It is <b>your responsibility</b> to not include any Personally Identifiable Information (PII) about your subjects!</p>
                  </Tooltip>
                )}>
                <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
              </OverlayTrigger>
            </h4>
            <h5>
              Part of Dataset: <Link to={path} className="mb-5">{parentName}</Link>
            </h5>
            <div className="FileControlsWrapper-folder-description">
              {getEditableDescriptionSection(otherDatasetJson)}
            </div>
          </>
        );
      }
      else if (props.cursor.isSearchable()) {
        securityNotice = (
          <>
            <h4>
              <span className="badge rounded-pill p-1 px-2 bg-success mb-2">FINALIZED DATA</span>
              <OverlayTrigger
                placement="right"
                delay={{ show: 50, hide: 800 }}
                overlay={(props) => (
                  <Tooltip id="button-tooltip" {...props}>
                    <p>This folder is <b>finalized data</b>, and can be found on the AddBiomechanics <Link to="/search">search page</Link>.</p>
                    <p>You can leave public notes to help others using the data (how to cite the data, etc). It is <b>your responsibility</b> to not include any Personally Identifiable Information (PII) about your subjects!</p>
                  </Tooltip>
                )}>
                <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
              </OverlayTrigger>
            </h4>
            <div className="FileControlsWrapper-folder-description">
              {getEditableDescriptionSection(props.cursor.searchJson)}
              <button type="submit" className="btn btn-light mt-2" onClick={() => props.cursor.markNotSearchable()}>
                <i className="mdi mdi-earth-minus"></i> Mark as a Draft
              </button>
            </div>
          </>
        );
      }
      else {
        securityNotice = (
          <>
            <h4>
              <span className="badge rounded-pill p-1 px-2 bg-warning">UNFINALIZED DRAFT</span>
              <OverlayTrigger
                placement="right"
                delay={{ show: 50, hide: 800 }}
                overlay={(props) => (
                  <Tooltip id="button-tooltip" {...props}>
                    <p>This folder is a <b>draft</b>. It is accessible to anyone who has the link, and will show up on the AddBiomechanics <Link to="/search">search page</Link> marked as a draft.</p>
                    <p>You can leave public notes to help others using the data (how to cite the data, etc). It is <b>your responsibility</b> to not include any Personally Identifiable Information (PII) about your subjects!</p>
                  </Tooltip>
                )}>
                <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
              </OverlayTrigger>
            </h4>
            <div className="FileControlsWrapper-folder-description">
              {getEditableDescriptionSection(props.cursor.searchJson)}
              <button type="submit" className="btn btn-primary mt-2" onClick={() => props.cursor.markSearchable()}>
                <i className="mdi mdi-earth-plus"></i> Mark Dataset as Finalized
              </button>
              <p className="mt-2"><small>(You can always mark it as a draft again later if you change your mind)</small></p>
            </div>
          </>
        );
      }
    }
    else if (path.type === 'private') {
      securityNotice = (
        <>
          <h4>
            <span className="badge rounded-pill p-1 px-2 bg-secondary">PRIVATE </span>
            <i className="mdi mdi-lock-outline font-18 align-middle me-2"></i>
            <OverlayTrigger
              placement="right"
              delay={{ show: 50, hide: 3000 }}
              overlay={(props) => (
                <Tooltip id="button-tooltip" {...props}>
                  <p>This folder is <b>private</b> and password protected (link sharing won't work here).{' '}</p>
                  <p><b>Honor system:</b> AddBiomechanics is a community effort to create a huge shared dataset that everyone can benefit from! When you upload here, you're not sharing your data with the community. We understand that getting IRB approvals to share de-identified data publicly takes time, so you can use this area in the meantime. We don't limit your use of this area, but we ask that you make a good faith effort to share your data as soon as you can.</p>
                  If we see you using this area a lot, we'll reach out by email to see if we can help with your data-sharing approval process.
                </Tooltip>
              )}>
              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
            </OverlayTrigger>
          </h4>

        </>
      );
    }
    let navLinks = null;
    if (path.type === 'mine' || path.type === 'private') {
      navLinks = (
        <div className="email-menu-list mt-3">
          <Link to={"/data/" + encodeURIComponent(props.cursor.s3Index.myIdentityId)} className={path.type === 'mine' ? "fw-bold" : ""}>
            <i className="mdi mdi-folder-outline font-18 align-middle me-2"></i>
            My Data
          </Link>
          <Link to="/data/private" className={path.type === 'private' ? "fw-bold" : ""}>
            <i className="mdi mdi-lock-outline font-18 align-middle me-2"></i>
            Private Workspace
          </Link>
        </div>
      );
    }
    // Get user id from url.
    let url_id = location.pathname.split('/')[2];
    body = (
      <>
        <div className="page-aside-left">
          <Link to={"/profile/" + url_id}>
            <h3 className="my-3">
              {fullName != "" ? fullName : "User ID: " + url_id}
              <i className="mdi mdi-share me-1 vertical-middle"></i>
            </h3>
          </Link>

          {dropdown}
          {/* Left side nav links */}
          {navLinks}
          <div className="mt-3">
            {securityNotice}
          </div>
          {
            (() => {
              if (path.type !== 'mine' && path.type != 'private') {
                return (
                  <>
                    {(() => {
                      let sidebarContent = []

                      if (props.cursor.searchJson.getAttribute("title", "") !== "") {
                        sidebarContent.push(
                          <li key="title">
                            <br></br>
                            <h2 style={{ width: '100%' }}>{props.cursor.searchJson.getAttribute("title", "")}</h2>
                          </li>
                        )
                      }

                      if (props.cursor.searchJson.getAttribute("notes", "") !== "") {
                        sidebarContent.push(
                          <li key="notes">
                            <br></br>
                            <label>
                              <i className="mdi mdi-account me-1 vertical-middle"></i>
                              Dataset Information:
                              <OverlayTrigger
                                placement="right"
                                delay={{ show: 50, hide: 400 }}
                                overlay={(props) => (
                                  <Tooltip id="button-tooltip" {...props}>
                                    Public notes about the dataset (purpose, description, number of subjects, etc.) inserted by the authors.
                                  </Tooltip>
                                )}>
                                <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                              </OverlayTrigger>
                            </label>
                            <br></br>
                            <div style={{ width: '100%' }}>{props.cursor.searchJson.getAttribute("notes", "")}</div>
                          </li>
                        )
                      }

                      if (props.cursor.searchJson.getAttribute("citation", "") !== "") {
                        sidebarContent.push(
                          <li key="citation">
                            <br></br>
                            <label>
                              <i className="mdi mdi-account me-1 vertical-middle"></i>
                              Citation:
                              <OverlayTrigger
                                placement="right"
                                delay={{ show: 50, hide: 400 }}
                                overlay={(props) => (
                                  <Tooltip id="button-tooltip" {...props}>
                                    This is how the authors of this dataset prefer to be cited.
                                  </Tooltip>
                                )}>
                                <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                              </OverlayTrigger>
                            </label>
                            <br></br>
                            <div style={{ width: '100%' }}>{props.cursor.searchJson.getAttribute("citation", "")}</div>
                          </li>
                        )
                      }
                      if (props.cursor.searchJson.getAttribute("funding", "") !== "") {
                        sidebarContent.push(
                          <li key="funding">
                            <br></br>
                            <label>
                              <i className="mdi mdi-account me-1 vertical-middle"></i>
                              Funding:
                              <OverlayTrigger
                                placement="right"
                                delay={{ show: 50, hide: 400 }}
                                overlay={(props) => (
                                  <Tooltip id="button-tooltip" {...props}>
                                    This is the funding the authors have received to create this dataset.
                                  </Tooltip>
                                )}>
                                <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                              </OverlayTrigger>
                            </label>
                            <br></br>
                            <div style={{ width: '100%' }}>{props.cursor.searchJson.getAttribute("funding", "")}</div>
                          </li>
                        )
                      }
                      return (
                        <fieldset>
                          <ul className="no-bullets">{sidebarContent}</ul>
                        </fieldset>
                      )

                    })()}

                  </>
                )
              }
            })()}



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
