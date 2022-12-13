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
} from "react-bootstrap";
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
    return <Link to={link}>{userId + '/' + parts.slice(2).join('/')}</Link>
  }
  else {
    return null;
  }
}

type SearchViewProps = {
  cursor: MocapS3Cursor;
};

const SearchView = (props: SearchViewProps) => {
  const [availableOptions, setAvailableOptions] = useState([] as string[]);

  useEffect(() => {
    setAvailableOptions([...props.cursor.s3Index.getAllPathsContaining("SEARCH").keys()]);
  }, []);

  console.log(availableOptions);

  return (
    <>
      <Row className="mt-3">
        <Col md="12">
          <Card className="mt-4">
            <Card.Body>
              <h3>All Public Files:</h3>
              <ul>
                {availableOptions.map((v) => {
                  return <li key={v}>
                    <SearchResult cursor={props.cursor} filePath={v} />
                  </li>
                })}
              </ul>
            </Card.Body>
          </Card>
        </Col>
      </Row>
    </>
  );
};

export default SearchView;
