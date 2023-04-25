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


type SearchResultProps = {
    cursor: MocapS3Cursor;
    dataset: Dataset;
    searchText: string;
    index: number;
    fullWidth: boolean;
};

const SearchResult = observer((props: SearchResultProps) => {
    let filtered = props.dataset.key.replace("protected/us-west-2:", "").replace('/_SEARCH', '');
    const parts = filtered.split('/');
    const userId = parts[0];

    const fullName = props.cursor.getOtherProfileFullName(userId);
    if (filtered.endsWith('/')) {
        filtered = filtered.slice(0, -1)
    }
    const description = props.cursor.getDatasetSearchJson(filtered).getAttribute("notes", "");
    const datasetTitle = props.cursor.getDatasetSearchJson(filtered).getAttribute("title", "");

    function highlightSearchTerm(htmlString: string, searchTerm: string) {
        if (searchTerm.length == 0) return htmlString;

        // Create a regular expression to match the search term
        const regex = new RegExp('(' + searchTerm + ')', "gi");

        // Replace all occurrences of the search term with a highlighted version (use capture groups to preserve capitalization)
        const highlightedHtmlString = htmlString.replace(regex, '<span style="background-color: #ffee5e; border-radius: 5px;">$1</span>');

        return highlightedHtmlString;
    }

    let linkDataset = '/data/' + userId + '/' + parts.slice(2).join('/');
    let linkUser = '/profile/' + userId;
    let tags = [];
    if (props.dataset.hasDynamics) {
        tags.push(<><span className="badge bg-success" key="dynamics">Dynamics</span> </>);
    }
    if (props.dataset.isPublished) {
        tags.push(<><span className="badge bg-success" key="published">Published</span> </>);
    }
    else {
        tags.push(<><span className="badge bg-warning" key="unpublished">Draft</span> </>);
    }
    if (parts[parts.length - 1] === '') {
        parts.splice(parts.length - 1, 1);
    }

    // If user set a title for the dataset, show it first. If not, use only dataset folder name.
    let datasetTitleShown = "";
    if (datasetTitle !== "") {
        datasetTitleShown += datasetTitle + " - (";
    }
    // Add folder name.
    let datasetName = parts.slice(2).join('/');
    datasetTitleShown = datasetTitleShown + datasetName;
    // If dataset is home folder, add "<username>'s Home Folder" as name.
    if (datasetName === '') {
        datasetTitleShown += fullName + "'s Home Folder";
    }
    // Add ending parenthesis.
    if (datasetTitle !== "") {
        datasetTitleShown += ")";
    }

    return (
        <Col md={props.fullWidth ? "12" : "4"}>
            <Card>
                <Card.Body>
                    <h4><Link to={linkDataset}><span dangerouslySetInnerHTML={{ __html: highlightSearchTerm(datasetTitleShown, props.searchText) }}></span></Link></h4>
                    By <Link to={linkUser}><span dangerouslySetInnerHTML={{ __html: highlightSearchTerm(fullName, props.searchText) }}></span></Link>
                    <p></p>
                    <p dangerouslySetInnerHTML={{ __html: highlightSearchTerm(description, props.searchText) }}></p>
                    <p></p>
                    <p>Subjects: {props.dataset.numSubjects}, Trials: {props.dataset.numTrials}</p>
                    {tags}
                </Card.Body>
            </Card>
        </Col>
    )
});

export { type SearchResultProps };
export default SearchResult;