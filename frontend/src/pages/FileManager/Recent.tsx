import React from "react";
import { Link } from "react-router-dom";
import {
  Dropdown,
  ButtonGroup,
  Table,
  Breadcrumb,
  BreadcrumbItem,
  OverlayTrigger,
  Tooltip,
} from "react-bootstrap";

type MemberItems = {
  image: string;
  name: string;
};

type RecentFilesItems = {
  name: string;
  modifiedDate: string;
  modifiedBy: string;
  size: string;
  owner: string;
};

type BreadcrumbItems = {
  label: string;
  path: string;
  active?: boolean;
};

type RecentProps = {
  recentFiles: Array<RecentFilesItems>;
  breadCrumbItems: Array<BreadcrumbItems>;
  title: string;
};

const Recent = (props: RecentProps) => {
  return (
    <>
      <div className="mt-0">
        <Breadcrumb className="m-0">
          <BreadcrumbItem href="/">Hyper</BreadcrumbItem>

          {props.breadCrumbItems.map((item, index) => {
            return item.active ? (
              <BreadcrumbItem active key={index}>
                {item.label}
              </BreadcrumbItem>
            ) : (
              <BreadcrumbItem key={index} href={item.path}>
                {item.label}
              </BreadcrumbItem>
            );
          })}
        </Breadcrumb>

        <Table responsive className="table table-centered table-nowrap mb-0">
          <thead className="table-light">
            <tr>
              <th className="border-0">Name</th>
              <th className="border-0">Last Modified</th>
              <th className="border-0">Size</th>
              <th className="border-0">Owner</th>
              <th className="border-0" style={{ width: "80px" }}>
                Action
              </th>
            </tr>
          </thead>
          <tbody>
            {props.recentFiles.map((file, index) => {
              return (
                <tr key={index}>
                  <td>
                    <span className="ms-2 fw-semibold">
                      <Link to="#" className="text-reset">
                        {file.name}
                      </Link>
                    </span>
                  </td>
                  <td>
                    <p className="mb-0">{file.modifiedDate}</p>
                    <span className="font-12">by {file.modifiedBy}</span>
                  </td>
                  <td>{file.size}</td>
                  <td>{file.owner}</td>
                  <td>
                    <ButtonGroup className="d-block mb-2">
                      <Dropdown>
                        {/* align="end" */}
                        <Dropdown.Toggle className="table-action-btn dropdown-toggle arrow-none btn btn-light btn-xs">
                          <i className="mdi mdi-dots-horizontal"></i>
                        </Dropdown.Toggle>
                        <Dropdown.Menu>
                          <Dropdown.Item>
                            <i className="mdi mdi-share-variant me-2 text-muted vertical-middle"></i>
                            Share
                          </Dropdown.Item>
                          <Dropdown.Item>
                            <i className="mdi mdi-link me-2 text-muted vertical-middle"></i>
                            Get Sharable Link
                          </Dropdown.Item>
                          <Dropdown.Item>
                            <i className="mdi mdi-pencil me-2 text-muted vertical-middle"></i>
                            Rename
                          </Dropdown.Item>
                          <Dropdown.Item>
                            <i className="mdi mdi-download me-2 text-muted vertical-middle"></i>
                            Download
                          </Dropdown.Item>
                          <Dropdown.Item>
                            <i className="mdi mdi-delete me-2 text-muted vertical-middle"></i>
                            Remove
                          </Dropdown.Item>
                        </Dropdown.Menu>
                      </Dropdown>
                    </ButtonGroup>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </Table>
      </div>
    </>
  );
};

export default Recent;
