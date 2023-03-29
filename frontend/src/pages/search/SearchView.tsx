import { ReactiveJsonFile, ReactiveCursor, ReactiveIndex } from "../../state/ReactiveS3";
import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import logo from "../../assets/images/logo-alone.svg";
import MocapS3Cursor, { Dataset } from '../../state/MocapS3Cursor';
import {
  Row,
  Col,
  Card,
  Dropdown,
  ButtonGroup,
  Spinner,
  OverlayTrigger,
  Tooltip
} from "react-bootstrap";
import { observer } from "mobx-react-lite";
import './SearchView.scss';
import { profile } from "console";
import SearchResult from './SearchResult';

type SearchViewProps = {
  cursor: MocapS3Cursor;
};

const SearchView = observer((props: SearchViewProps) => {
  const [searchText, setSearchText] = useState("")
  const [includeUnpublished, setIncludeUnpublished] = useState(false)
  const [dynamicsOnly, setDynamicsOnly] = useState(false)

  const datasets = props.cursor.datasetIndex.searchDatasets(searchText, dynamicsOnly, includeUnpublished);
  // Collect the list of "root" datasets (that are not contained as part of any other dataset results) in order to avoid double counting.
  const datasetsNoSubsidiaries: Dataset[] = [];
  for (let i = 0; i < datasets.length; i++) {
    let foundParent = false;
    for (let j = 0; j < datasets.length; j++) {
      if (datasets[i].key != datasets[j].key && datasets[j].key.indexOf(datasets[i].key) !== -1) {
        foundParent = true;
        break;
      }
    }
    if (!foundParent) {
      datasetsNoSubsidiaries.push(datasets[i]);
    }
  }
  const totalSubjects = datasetsNoSubsidiaries.map(d => d.numSubjects).reduce((sum, n) => sum + n, 0);
  const totalTrials = datasetsNoSubsidiaries.map(d => d.numTrials).reduce((sum, n) => sum + n, 0);

  let body = null;
  if (props.cursor.getIsLoading()) {
    body = <Spinner animation="border" />;
  }
  else {
    body = <>
      {
        datasets.map((dataset, i) => {
          // Return search result
          return (
            <>
              <SearchResult cursor={props.cursor} dataset={dataset} searchText={searchText} index={i} />
            </>)
        })}
    </>
  }

  let header = null;
  if (includeUnpublished) {
    header = <>
      <h3>All Folders</h3>
      <p>All folders, including those still in "draft" mode, will not show up here. WARNING: Use this data at your own risk, it has not been certified by its authors.</p>
    </>;
  }
  else {
    header = <>
      <h3>Published Folders</h3>
      <p>All folders still in "draft" mode will not show up here. Authors must mark their folder as published to have it appear here.</p>
    </>;
  }

  const isAdmin = true;

  let adminOptions = null;
  if (isAdmin) {
    adminOptions = (
      <form className="row g-3 mb-15">
        <div className="col-md-12">
          <label>
            <i className={"mdi me-1 vertical-middle mdi-account"}></i>
            Include Unpublished
            <OverlayTrigger
              placement="right"
              delay={{ show: 50, hide: 400 }}
              overlay={(props) => (
                <Tooltip id="button-tooltip" {...props}>
                  Checking this box will include datasets that the author has not marked as "published" in your results. This data should not be trusted!
                </Tooltip>
              )}>
              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
            </OverlayTrigger></label>
          <br></br>
          <input
            type="checkbox"
            checked={includeUnpublished}
            onChange={function (e) { setIncludeUnpublished(e.target.checked) }}>
          </input>
        </div>
      </form>
    );
  }

  return (
    <>
      <Row className="mt-3">
        <Col md="12">
          <Card className="mt-4">
            <Card.Body>
              <Row className="mt-3">
                <Col md="3">
                  <Card>
                    <Card.Body>
                      <h3>Search</h3>

                      <form className="row g-3 mb-15">
                        <div className="col-md-12">
                          <label>
                            <i className={"mdi me-1 vertical-middle mdi-account"}></i>
                            Search
                            <OverlayTrigger
                              placement="right"
                              delay={{ show: 50, hide: 400 }}
                              overlay={(props) => (
                                <Tooltip id="button-tooltip" {...props}>
                                  Type keywords here to match dataset titles
                                </Tooltip>
                              )}>
                              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                            </OverlayTrigger></label>
                          <br></br>
                          <input
                            type="text"
                            className="form-control"
                            placeholder="Placeholder"
                            value={searchText}
                            onChange={function (e) { setSearchText(e.target.value) }}>
                          </input>
                        </div>
                      </form>
                      <form className="row g-3 mb-15">
                        <div className="col-md-12">
                          <label>
                            <i className={"mdi me-1 vertical-middle mdi-account"}></i>
                            Dynamics Required
                            <OverlayTrigger
                              placement="right"
                              delay={{ show: 50, hide: 400 }}
                              overlay={(props) => (
                                <Tooltip id="button-tooltip" {...props}>
                                  Checking this box will only show datasets that have ground-reaction-force (GRF) data, and have been processed for dynamic consistency with AddBiomechanics.
                                </Tooltip>
                              )}>
                              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                            </OverlayTrigger></label>
                          <br></br>
                          <input
                            type="checkbox"
                            checked={dynamicsOnly}
                            onChange={function (e) { setDynamicsOnly(e.target.checked) }}>
                          </input>
                        </div>
                      </form>
                      {adminOptions}


                      {/*
                      <form className="row g-3 mb-15">
                        <div className="col-md-12">
                          <label>
                            <i className={"mdi me-1 vertical-middle mdi-account"}></i>
                            User
                            <OverlayTrigger
                              placement="right"
                              delay={{ show: 50, hide: 400 }}
                              overlay={(props) => (
                                <Tooltip id="button-tooltip" {...props}>
                                  User...
                                </Tooltip>
                              )}>
                              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                            </OverlayTrigger></label>
                          <br></br>
                          <input
                            type="text"
                            className="form-control"
                            placeholder="Placeholder"
                            value={searchUser}
                            onChange={function(e) {setSearchUser(e.target.value)}}>
                          </input>
                        </div>
                      </form>
                      */}
                    </Card.Body>
                  </Card>
                </Col>
                <Col md="8">
                  <Card>
                    <Card.Body>
                      {header}
                      <Row>
                        <Row md="12">
                          <p>Search results: {datasets.length} datasets, {totalSubjects} subjects, {totalTrials} trials</p>
                        </Row>
                        {body}
                      </Row>
                    </Card.Body>
                  </Card>
                </Col>
              </Row>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
});

export default SearchView;
