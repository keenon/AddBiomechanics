import React from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { Dropdown, ButtonGroup, Table, Spinner } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import MocapS3Cursor from '../../state/MocapS3Cursor';
import { humanFileSize } from '../../utils';

type FolderViewProps = {
  cursor: MocapS3Cursor;
};

const FolderView = observer((props: FolderViewProps) => {
  const navigate = useNavigate();

  const dataIsReadonly = props.cursor.dataIsReadonly();
  let contents = props.cursor.getFolderContents();

  let rows = [];
  contents.forEach((entry) => {
    const name = entry.key;

    let status: 'processing' | 'waiting' | 'could-process' | 'error' | 'done' | 'empty' | 'slurm' = 'done';
    if (entry.type === 'folder') {
      status = props.cursor.getFolderStatus(entry.key);
    }
    else if (entry.type === 'mocap') {
      status = props.cursor.getSubjectStatus(entry.key);
    }

    let statusBadge = null;
    if (status === "done") {
      statusBadge = <span className="badge bg-primary">Processed</span>;
    }
    else if (status === "error") {
      statusBadge = <span className="badge bg-danger">Error</span>;
    }
    else if (status === "processing") {
      statusBadge = <span className="badge bg-warning">Processing</span>;
    }
    else if (status === "could-process") {
      if (props.cursor.canEdit()) {
        statusBadge = <span className="badge bg-secondary">Waiting for you to process</span>;
      }
      else {
        statusBadge = <span className="badge bg-secondary">Waiting for owner to process</span>;
      }
    }
    else if (status === "waiting") {
      statusBadge = <span className="badge bg-secondary">Waiting for server</span>;
    }
    else if (status === "slurm") {
      statusBadge = <span className="badge bg-secondary">Queued on SLURM cluster</span>;
    }
    else if (status === "empty") {
      statusBadge = <span className="badge bg-secondary">Waiting for you to upload data</span>;
    }


    rows.push(
      <tr key={name}>
        <td>
          <span className="ms-2 fw-semibold">
            <Link to={entry.href} className="text-reset">
              <i className={"mdi me-1 text-muted vertical-middle " + (entry.type === 'folder' ? 'mdi-folder-outline' : 'mdi-walk')}></i>
              {name}
            </Link>
          </span>
        </td>
        <td>
          {statusBadge}
        </td>
        <td>
          <p className="mb-0">
            {entry.lastModified.toDateString()}
          </p>
        </td>
        <td>{humanFileSize(entry.size)}</td>
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
                  <Dropdown.Item>
                    <i className="mdi mdi-link me-2 text-muted vertical-middle"></i>
                    Copy Sharable Link
                  </Dropdown.Item>
                      <Dropdown.Item>
                        <i className="mdi mdi-pencil me-2 text-muted vertical-middle"></i>
                        Rename
                      </Dropdown.Item>
                      */}
                  <Dropdown.Item
                    onClick={() => {
                      navigate(entry.href);
                    }}
                  >
                    <i className="mdi mdi-eye me-2 text-muted vertical-middle"></i>
                    View
                  </Dropdown.Item>
                  <Dropdown.Item
                    onClick={() => {
                      navigate({ search: "?delete-folder=" + entry.key });
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
    if (props.cursor.getIsLoading()) {
      rows.push(
        <tr key="loading">
          <td colSpan={4}>
            <Spinner animation="border" />
          </td>
        </tr>
      );
    }
    else {
      rows.push(
        <tr key="empty">
          <td colSpan={4}>This folder is empty!</td>
        </tr>
      );
    }
  }

  return (
    <>
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
    </>
  );
});

export default FolderView;
