import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Modal, Button, Spinner } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import MocapS3Cursor from '../../state/MocapS3Cursor';
import TagEditor from '../../components/TagEditor';

type MocapTagModalProps = {
    cursor: MocapS3Cursor;
};

const MocapTagModal = observer((props: MocapTagModalProps) => {
    const location = useLocation();
    const navigate = useNavigate();
    const [tagList, setTagList] = useState([] as string[]);
    const [tagValues, setTagValues] = useState({} as { [key: string]: number });
    const [working, setWorking] = useState(false);
    const [finishedTrials, setFinishedTrials] = useState(0);

    let show = location.search.startsWith("?bulk-tags");
    const actionType = decodeURIComponent(location.search.substring("?bulk-tags=".length));
    let addTags = actionType === 'add';

    if (!show) {
        return <></>;
    }

    let hideModal = () => {
        setTagList([]);
        navigate({ search: "" }, { replace: true });
    };

    const commitEdit = async () => {
        setWorking(true);
        let trials = props.cursor.getTrials();
        for (let i = 0; i < trials.length; i++) {
            setFinishedTrials(i);
            const name = trials[i].key;
            const tagsFile = props.cursor.getTrialTagFile(name);
            let existingTagList = tagsFile.getAttribute("tags", [] as string[]);
            let existingTagValues = Object.assign({}, tagsFile.getAttribute("tagValues", {} as { [key: string]: number }));
            if (addTags) {
                for (let tag of tagList) {
                    if (existingTagList.indexOf(tag) === -1) {
                        existingTagList.push(tag);
                    }
                    if (tag in tagValues) {
                        existingTagValues[tag] = tagValues[tag];
                    }
                }
            }
            else {
                for (let tag of tagList) {
                    if (existingTagList.indexOf(tag) !== -1) {
                        existingTagList.splice(existingTagList.indexOf(tag), 1, []);
                    }
                }
            }
            tagsFile.setAttribute("tags", existingTagList);
            tagsFile.setAttribute("tagValues", existingTagValues);
            await tagsFile.uploadNow();
        }
        setWorking(false);
        setTagList([]);
        hideModal();
    }

    let body;
    if (working) {
        let numTrials = props.cursor.getTrials().length;
        body = <>
            <div className="mb-15">
                Saving... Updated {finishedTrials} / {numTrials}
            </div>
            <Spinner animation="border" />
        </>
    }
    else {
        body = <>
            <div className="mb-15">
                <TagEditor
                    tagSet='trial'
                    tags={tagList}
                    onTagsChanged={(newTags) => {
                        setTagList(newTags);
                    }}
                    tagValues={tagValues}
                    onTagValuesChanged={(newTagValues) => {
                        setTagValues(newTagValues);
                    }}
                    hideNumbers={!addTags}
                />
            </div>
            <Button onClick={commitEdit} disabled={tagList.length === 0}>{addTags ? "Add tags to all trials" : "Remove tags from all trials"}</Button>
        </>
    }

    return (
        <Modal size="xl" show={show} onHide={hideModal}>
            <Modal.Header closeButton>
                <Modal.Title>
                    <i className="mdi mdi-wrench me-1"></i> {addTags ? "Add" : "Remove"} Tags {addTags ? "to" : "from"} All Trials
                </Modal.Title>
            </Modal.Header>
            <Modal.Body>
                {body}
            </Modal.Body>
        </Modal>
    );
});

export default MocapTagModal;
