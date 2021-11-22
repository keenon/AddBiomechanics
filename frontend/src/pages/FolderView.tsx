import React from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Dropdown, ButtonGroup, Table, Spinner } from "react-bootstrap";
import { MocapFolder } from "../state/MocapS3";
import { observer } from "mobx-react-lite";

type FolderViewProps = {
  folder: MocapFolder;
  linkPrefix: string;
};

const FolderView = observer((props: FolderViewProps) => {
  const navigate = useNavigate();

  const folder = props.folder;
  let linkPrefix = props.linkPrefix;
  if (!linkPrefix.endsWith("/")) {
    linkPrefix = linkPrefix + "/";
  }

  const dataIsReadonly = folder.backingFolder.level === "public";

  let rows = [];
  // Render the contents of a folder
  folder.folders.forEach((folder: MocapFolder) => {
    const name = folder.name;
    rows.push(
      <tr key={name}>
        <td>
          <span className="ms-2 fw-semibold">
            <Link to={linkPrefix + name} className="text-reset">
              <i className="mdi mdi-folder-outline me-1 text-muted vertical-middle"></i>
              {name}
            </Link>
          </span>
        </td>
        <td>
          <span className="badge bg-success">Processed</span>
        </td>
        <td>
          <p className="mb-0">
            {folder.backingFolder.lastModified.toDateString()}
          </p>
        </td>
        <td>{folder.backingFolder.size}</td>
        {dataIsReadonly ? null : (
          <td>
            <ButtonGroup className="d-block mb-2">
              <Dropdown>
                {/* align="end" */}
                <Dropdown.Toggle className="table-action-btn dropdown-toggle arrow-none btn btn-light btn-xs">
                  <i className="mdi mdi-dots-horizontal"></i>
                </Dropdown.Toggle>
                <Dropdown.Menu>
                  {/*
                      <Dropdown.Item>
                        <i className="mdi mdi-share-variant me-2 text-muted vertical-middle"></i>
                        Share
                      </Dropdown.Item>
                      */}
                  <Dropdown.Item>
                    <i className="mdi mdi-link me-2 text-muted vertical-middle"></i>
                    Copy Sharable Link
                  </Dropdown.Item>
                  {/*
                      <Dropdown.Item>
                        <i className="mdi mdi-pencil me-2 text-muted vertical-middle"></i>
                        Rename
                      </Dropdown.Item>
                      <Dropdown.Item>
                        <i className="mdi mdi-download me-2 text-muted vertical-middle"></i>
                        Download
                      </Dropdown.Item>
                      */}
                  <Dropdown.Item
                    onClick={() => {
                      navigate({ search: "?delete-folder=" + folder.name });
                    }}
                  >
                    <i className="mdi mdi-delete me-2 text-muted vertical-middle"></i>
                    Delete
                  </Dropdown.Item>
                </Dropdown.Menu>
              </Dropdown>
            </ButtonGroup>
          </td>
        )}
      </tr>
    );
  });
  folder.mocapClips.forEach((clip) => {
    const name = clip.name;
    rows.push(
      <tr key={name}>
        <td>
          <span className="ms-2 fw-semibold">
            <Link to={linkPrefix + name} className="text-reset">
              <i className="mdi mdi-walk me-1 text-muted vertical-middle"></i>
              {name}
            </Link>
          </span>
        </td>
        <td>
          <span className="badge bg-success">Processed</span>
        </td>
        <td>
          <p className="mb-0">TODO</p>
        </td>
        <td>0</td>
        {dataIsReadonly ? null : (
          <td>
            <ButtonGroup className="d-block mb-2">
              <Dropdown>
                {/* align="end" */}
                <Dropdown.Toggle className="table-action-btn dropdown-toggle arrow-none btn btn-light btn-xs">
                  <i className="mdi mdi-dots-horizontal"></i>
                </Dropdown.Toggle>
                <Dropdown.Menu>
                  {/*
                      <Dropdown.Item>
                        <i className="mdi mdi-share-variant me-2 text-muted vertical-middle"></i>
                        Share
                      </Dropdown.Item>
                      */}
                  <Dropdown.Item>
                    <i className="mdi mdi-link me-2 text-muted vertical-middle"></i>
                    Copy Sharable Link
                  </Dropdown.Item>
                  {/*
                      <Dropdown.Item>
                        <i className="mdi mdi-pencil me-2 text-muted vertical-middle"></i>
                        Rename
                      </Dropdown.Item>
                      <Dropdown.Item>
                        <i className="mdi mdi-download me-2 text-muted vertical-middle"></i>
                        Download
                      </Dropdown.Item>
                      */}
                  <Dropdown.Item
                    onClick={() => {
                      navigate({ search: "?delete-folder=" + clip.name });
                    }}
                  >
                    <i className="mdi mdi-delete me-2 text-muted vertical-middle"></i>
                    Delete
                  </Dropdown.Item>
                </Dropdown.Menu>
              </Dropdown>
            </ButtonGroup>
          </td>
        )}
      </tr>
    );
  });

  if (rows.length === 0) {
    rows.push(
      <tr key="empty">
        <td colSpan={4}>This folder is empty!</td>
      </tr>
    );
  }
  return (
    <Table
      responsive={rows.length > 2}
      className="table table-centered table-nowrap mb-0"
    >
      <thead className="table-light">
        <tr>
          <th className="border-0">Name</th>
          <th className="border-0">Status</th>
          <th className="border-0">Last Modified</th>
          <th className="border-0">Size</th>
          {dataIsReadonly ? null : (
            <th className="border-0" style={{ width: "80px" }}>
              Action
            </th>
          )}
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </Table>
  );
});

export default FolderView;
