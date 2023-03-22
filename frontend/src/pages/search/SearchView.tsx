import { ReactiveJsonFile, ReactiveCursor, ReactiveIndex } from "../../state/ReactiveS3";
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
  OverlayTrigger,
  Tooltip
} from "react-bootstrap";
import { observer } from "mobx-react-lite";
import './SearchView.scss';
import { profile } from "console";

type SearchResultProps = {
  cursor: MocapS3Cursor;
  filePath: string;
  searchText: string;
  searchUser: string;
  index: number;
};

const SearchResult = (props: SearchResultProps) => {
  const filtered = props.filePath.replace("protected/us-west-2:", "").replace('/_SEARCH', '');
  const parts = filtered.split('/');
  const userId = parts[0];

  const [name, setName] = useState("")
  const [surname, setSurname] = useState("")
  const [fullName, setFullName] = useState("")

  const [description, setDescription] = useState("")

  function highlightSearchTerm(htmlString:string, searchTerm:string) {
    // Create a regular expression to match the search term
    const regex = new RegExp(searchTerm, "gi");
  
    // Replace all occurrences of the search term with a highlighted version
    const highlightedHtmlString = htmlString.replace(regex, `<span style="background-color: #ffee5e; border-radius: 5px;">${searchTerm}</span>`);
  
    return highlightedHtmlString;
  }

  // Download profile file
  props.cursor.s3Index.downloadText("protected/" + props.cursor.s3Index.region + ":" + userId + "/profile.json").then(
    function(text:string) {
      const profileObject = JSON.parse(text);

      setName(profileObject.name)
      setSurname(profileObject.surname)
      if (name !== "" && surname !== "")
        setFullName(name + " " + surname)
      else if  (name === "" && surname !== "")
        setFullName(surname)
      else if (name !== "" && surname === "")
        setFullName(name)
      else setFullName("")

      let link_search = ""
      if (parts.length === 2)
        link_search = "protected/" + props.cursor.s3Index.region + ":" + userId + "/data/_search.json"
      else
        link_search = "protected/" + props.cursor.s3Index.region + ":" + userId + "/data/" + parts.slice(2).join('/') + "/_search.json"

      props.cursor.s3Index.downloadText(link_search).then(
        function(text:string) {
          const searchObject = JSON.parse(text);
          setDescription(searchObject.notes);
        }
      );

    }
  )
  if ( (description.toLowerCase().trim().includes(props.searchText.toLowerCase().trim()) ||
      parts.slice(2).join('/').toLowerCase().trim().includes(props.searchText.toLowerCase().trim()) ) &&
       fullName.toLowerCase().trim().includes(props.searchUser.toLowerCase().trim()) ) {
    if (parts.length === 2) {
        return (
          <Col md="12">
            <Card>
              <Card.Body>
                <h4><Link to={'/data/' + userId}>/</Link></h4>
                By <Link to={'/profile/' + userId}><span dangerouslySetInnerHTML={ {__html: highlightSearchTerm(fullName, props.searchUser) }}></span></Link>
                <p></p>
                <p dangerouslySetInnerHTML={ {__html: highlightSearchTerm(description, props.searchText) }}></p>
                <p></p>
                <span className="badge bg-success">Tag 1</span> <span className="badge bg-success">Tag 2</span> <span className="badge bg-success">Tag 3</span>
              </Card.Body>
            </Card>
          </Col>
        )
    }
    else if (parts.length > 2) {
      const userId = parts[0];
      let linkDataset = '/data/' + userId + '/' + parts.slice(2).join('/');
      let linkUser = '/profile/' + userId;
      return (
        <Col md="12">
          <Card>
            <Card.Body>
              <h4><Link to={linkDataset}><span dangerouslySetInnerHTML={ {__html: highlightSearchTerm("/" + parts.slice(2).join('/'), props.searchText) }}></span></Link></h4>
              By <Link to={linkUser}><span dangerouslySetInnerHTML={ {__html: highlightSearchTerm(fullName, props.searchUser) }}></span></Link>
              <p></p>
                <p dangerouslySetInnerHTML={ {__html: highlightSearchTerm(description, props.searchText) }}></p>
              <p></p>
              <span className="badge bg-success">Tag 1</span> <span className="badge bg-success">Tag 2</span> <span className="badge bg-success">Tag 3</span>
            </Card.Body>
          </Card>
        </Col>
      )
    }
    else {
      return null;
    }
  } else {
    return null;
  }
};

type SearchViewProps = {
  cursor: MocapS3Cursor;
};

const SearchView = observer((props: SearchViewProps) => {
  const result = props.cursor.searchIndex.results;
  const availableOptions = [...result.keys()];

  const [searchText, setSearchText] = useState("")
  const [searchUser, setSearchUser] = useState("")

  let searchResults = 0

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
        {
        availableOptions.map((v, i) => {
            // Return search result
            return (
            <>
              <SearchResult cursor={props.cursor} filePath={v} searchText={searchText} searchUser={searchUser} index={i}/>
            </>)
        })}
    </>
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
                                  Search...
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
                            onChange={function(e) {setSearchText(e.target.value)}}>
                          </input>
                        </div>
                      </form>


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
                    </Card.Body>
                  </Card>
                </Col>
                <Col md="8">
                  <Card>
                    <Card.Body>
                        <h3>Published Folders</h3>
                        <p>All folders still in "draft" mode will not show up here. Authors must mark their folder as published to have it appear here.</p>
                      <Row>

                        <Row md="12">
                        <p>{"Search results: " + searchResults}</p>
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
