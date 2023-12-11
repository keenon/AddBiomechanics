import React, { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import logo from "../../assets/images/logo-alone.svg";
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
import { profile } from "console";
import LiveJsonFile from "../../model/LiveJsonFile";

type SearchResultProps = {
  datasetInfo: LiveJsonFile
  folderName: string
  numSubjects: number
  numTrials: number
  userName: string
  userId: string
  searchText: string;
  index: number;
  fullWidth: boolean;
};

const SearchResult = observer((props: SearchResultProps) => {
    const fullName = props.userName
    const titleToShow = props.datasetInfo.getAttribute("title", "") === "" ? props.folderName : props.datasetInfo.getAttribute("title", "")
    const description = props.datasetInfo.getAttribute("notes", "");

    function highlightSearchTerm(htmlString: string, searchTerm: string) {
        if (searchTerm.length == 0) return htmlString;

        // Create a regular expression to match the search term
        const regex = new RegExp('(' + searchTerm + ')', "gi");

        // Replace all occurrences of the search term with a highlighted version (use capture groups to preserve capitalization)
        const highlightedHtmlString = htmlString.replace(regex, '<span style="background-color: #ffee5e; border-radius: 5px;">$1</span>');

        return highlightedHtmlString;
    }

    let linkDataset = '/data/' + props.userId + '/' + props.folderName;
    let linkUser = '/profile/' + props.userId;
//     let tags = [];
//     if (props.dataset.hasDynamics) {
//         tags.push(<><span className="badge bg-success" key="dynamics">Dynamics</span> </>);
//     }
//     if (props.dataset.isPublished) {
//         tags.push(<><span className="badge bg-success" key="published">Published</span> </>);
//     }
//     else {
//         tags.push(<><span className="badge bg-warning" key="unpublished">Draft</span> </>);
//     }

    return (
        <Col md={props.fullWidth ? "12" : "4"}>
            <Card>
                <Card.Body>
                    <h4><Link to={linkDataset}><span dangerouslySetInnerHTML={{ __html: highlightSearchTerm(titleToShow, props.searchText) }}></span></Link></h4>
                    By <Link to={linkUser}><span dangerouslySetInnerHTML={{ __html: highlightSearchTerm(fullName, props.searchText) }}></span></Link>
                    <p></p>
                    <p dangerouslySetInnerHTML={{ __html: highlightSearchTerm(description, props.searchText) }}></p>
                    <p></p>
                    {/*<p>Subjects: {props.numSubjects}, Trials: {props.numTrials}</p>*/}
                    {/*{tags}*/}
                </Card.Body>
            </Card>
        </Col>
    )
});

export { type SearchResultProps };
export default SearchResult;