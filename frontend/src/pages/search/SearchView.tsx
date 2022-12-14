import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import logo from "../../assets/images/logo-alone.svg";
import MocapS3Cursor from '../../state/MocapS3Cursor';
import {
  Row,
  Col,
  Card,
  Dropdown,
  ButtonGroup,
  Spinner,
} from "react-bootstrap";
import { observer } from "mobx-react-lite";
import './SearchView.scss';

type SearchResultProps = {
  cursor: MocapS3Cursor;
  filePath: string;
};

const SearchResult = (props: SearchResultProps) => {
  const navigate = useNavigate();

  const filtered = props.filePath.replace("protected/us-west-2:", "").replace('/_SEARCH', '');
  const parts = filtered.split('/');
  if (parts.length === 2) {
    const userId = parts[0];
    return <Link to={'/data/' + userId}>{'User ' + userId}</Link>
  }
  else if (parts.length > 2) {
    const userId = parts[0];
    let link = '/data/' + userId + '/' + parts.slice(2).join('/');
    return <Link to={link}>{'User ' + userId + '/' + parts.slice(2).join('/')}</Link>
  }
  else {
    return null;
  }
};

type SearchViewProps = {
  cursor: MocapS3Cursor;
};

const SearchView = observer((props: SearchViewProps) => {
  const result = props.cursor.searchIndex.results;
  const availableOptions = [...result.keys()];

  useEffect(() => {
    props.cursor.searchIndex.startListening();

    return () => {
      props.cursor.searchIndex.stopListening();
    }
  }, []);

  let body = null;
  if (props.cursor.getIsLoading()) {
    body = <Spinner animation="border" />;
  }
  else {
    body = <>
      <ul>
        {availableOptions.map((v) => {
          return <li key={v}>
            <SearchResult cursor={props.cursor} filePath={v} />
          </li>
        })}
      </ul>
    </>
  }

  return (
    <>
      <Row className="mt-3">
        <Col md="12">
          <Card className="mt-4">
            <Card.Body>
              <h3>Published Folders:</h3>
              <p>All folders still in "draft" mode will not show up here. Authors must mark their folder as published to have it appear here.</p>
              {body}
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
});

export default SearchView;
