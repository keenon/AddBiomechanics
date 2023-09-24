import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Table, Button, ProgressBar, Form, Collapse } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import UserHomeDirectory, { SubjectContents, TrialSegmentContents } from "../../model/UserHomeDirectory";
import DropFile from "../../components/DropFile";
import TagEditor from '../../components/TagEditor';
import Session from "../../model/Session";
import { Link } from "react-router-dom";
import SubjectViewState, { SubjectResultsJSON } from "../../model/SubjectViewState";
import LiveFile from "../../model/LiveFile";

type SubjectViewProps = {
    home: UserHomeDirectory;
    currentLocationUserId: string;
    path: string;
    readonly: boolean;
};

const SubjectView = observer((props: SubjectViewProps) => {
    const home = props.home;
    const path = props.path;
    const navigate = useNavigate();

    const subjectState: SubjectViewState = home.getSubjectViewState(path);
    const subjectJson = subjectState.subjectJson;
    const readyFlagFile = subjectState.readyFlagFile;
    const processingFlagFile = subjectState.processingFlagFile;
    const errorFlagFile = subjectState.errorFlagFile;

    // Check on the value of the key _subject.json attributes unconditionally, to ensure that MobX updates if the attributes change
    const subjectDataSource: '' | 'published' | 'pilot' | 'study' = subjectJson.getAttribute("dataSource", "");
    const subjectConsent: boolean | null = subjectJson.getAttribute("subjectConsent", null);
    const subjectHeightM: number = subjectJson.getAttribute("heightM", "");
    const [subjectHeightComplete, setSubjectHeightComplete] = useState(true);
    const subjectMassKg: number = subjectJson.getAttribute("massKg", "");
    const [subjectMassComplete, setSubjectMassComplete] = useState(true);
    const subjectSex: '' | 'male' | 'female' | 'unknown' = subjectJson.getAttribute("sex", "");
    const subjectAgeYears: number | '' = subjectJson.getAttribute("ageYears", '');
    const [subjectAgeComplete, setSubjectAgeComplete] = useState(true);
    const subjectModel: '' | 'custom' | 'vicon' | 'cmu' = subjectJson.getAttribute("skeletonPreset", "");
    const disableDynamics: boolean | null = subjectJson.getAttribute("disableDynamics", null);
    const footBodyNames = subjectJson.getAttribute("footBodyNames", []);
    const subjectTags = subjectJson.getAttribute("subjectTags", []);
    const subjectTagValues = subjectJson.getAttribute("subjectTagValues", {} as { [key: string]: number });
    const runMoco: boolean | null = subjectJson.getAttribute("runMoco", null);
    const subjectCitation: string | null = subjectJson.getAttribute("citation", null);
    const [subjectCitationComplete, setSubjectCitationComplete] = useState(true);

    // Check on the existence of each flag unconditionally, to ensure that MobX updates if the flags change
    const resultsExist = subjectState.resultsExist;
    const readyFlagExists = readyFlagFile.exists && !readyFlagFile.loading;
    const errorFlagExists = errorFlagFile.exists && !errorFlagFile.loading;
    const processingFlagExists = processingFlagFile.exists && !processingFlagFile.loading;

    // Create state to manage the file drop zone
    const [dropZoneActive, setDropZoneActive] = useState(false);

    /////////////////////////////////////////////////////////////////////////
    // There are several states a subject can be in:
    // 0. Still loading, we're not sure what state we're in yet.
    // 1. Just created, so _subject.json is missing values or there are no trials. In this case, we want to show a wizard.
    // 2. User has indicated processing is ready, but we haven't finished processing yet. In this case, we want to show a status page.
    // 3. Processing finished, in which case we want to show results on the subject page.
    /////////////////////////////////////////////////////////////////////////

    // 0. We're still loading
    if (subjectState.loading || subjectJson.isLoadingFirstTime() || readyFlagFile.loading || processingFlagFile.loading) {
        return <div>Loading...</div>;
    }

    // 1. Create a wizard form for the _subject.json values, populated to the point in the journey that the user has reached.
    let formElements: JSX.Element[] = [
        <div key="title">
            <h3>Subject {subjectState.name} Metrics:</h3>
        </div>
    ];
    let formCompleteSoFar: boolean = true;
    let completedFormElements: number = 0;
    let totalFormElements: number = 0;

    //////////////////////////////////////////////////////////////////
    // 1.1. Create the entry for the subject height
    totalFormElements++;
    if (formCompleteSoFar) {
        formElements.push(<div key="height" className="mb-3">
            <label htmlFor="heightInput" className="form-label">Height (m):</label>
            <input
                type="number"
                id="heightInput"
                className={"form-control" + ((subjectHeightM <= 0 || !subjectHeightComplete) ? " border-primary border-2" : "")}
                aria-describedby="heightHelp"
                value={subjectHeightM}
                autoFocus={subjectHeightM <= 0 || !subjectHeightComplete}
                onFocus={() => {
                    subjectJson.onFocusAttribute("heightM");
                }}
                onBlur={() => subjectJson.onBlurAttribute("heightM")}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === 'Tab') {
                        setSubjectHeightComplete(true);
                    }
                }}
                onChange={(e) => {
                    if (e.target.value === '') {
                        subjectJson.setAttribute("heightM", null);
                    }
                    else {
                        subjectJson.setAttribute("heightM", parseFloat(e.target.value));
                    }
                }}></input>
            <div id="massHelp" className="form-text">The height of the subject, in meters.</div>
        </div>);

        if (subjectHeightM <= 0 || !subjectHeightComplete) {
            if (subjectHeightComplete) {
                setSubjectHeightComplete(false);
            }
            formCompleteSoFar = false;
            formElements.push(<div key='heightConfirm'>
                <button type="button" className="btn btn-primary" onClick={() => setSubjectHeightComplete(true)}>Confirm Height</button> (or press Enter or Tab)
            </div>);
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="heightExplanation">
                <h4 className="alert-heading">How does AddBiomechanics use height?</h4>
                <p>AddBiomechanics uses this information to help scale the subject's model to the correct size. We enforce height as a constraint when fitting the model.</p>
                <hr />
                <p className="mb-0">If you don't know the subject height, it's ok to guess something (like ~1.65m) and tweak later if the results look funny.</p>
            </div>);
        }
        else {
            completedFormElements++;
        }
    }
    //////////////////////////////////////////////////////////////////
    // 1.2. Create the entry for the subject mass
    totalFormElements++;
    if (formCompleteSoFar) {
        formElements.push(<div key="mass" className="mb-3">
            <label htmlFor="massInput" className="form-label">Mass (kg):</label>
            <input
                type="number"
                id="massInput"
                className={"form-control" + ((subjectMassKg <= 0 || !subjectMassComplete) ? " border-primary border-2" : "")}
                aria-describedby="massHelp"
                value={subjectMassKg}
                autoFocus={subjectMassKg <= 0 || !subjectMassComplete}
                onFocus={() => subjectJson.onFocusAttribute("massKg")}
                onBlur={() => subjectJson.onBlurAttribute("massKg")}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === 'Tab') {
                        setSubjectMassComplete(true);
                    }
                }}
                onChange={(e) => {
                    if (e.target.value === '') {
                        subjectJson.setAttribute("massKg", null);
                    }
                    else {
                        subjectJson.setAttribute("massKg", parseFloat(e.target.value));
                    }
                }}></input>
            <div id="massHelp" className="form-text">The approximate mass of the subject, in kilograms.</div>
        </div>);

        if (subjectMassKg <= 0 || !subjectMassComplete) {
            if (subjectMassComplete) {
                setSubjectMassComplete(false);
            }
            formCompleteSoFar = false;
            formElements.push(<div key='massConfirm'>
                <button type="button" className="btn btn-primary" onClick={() => setSubjectMassComplete(true)}>Confirm Mass</button> (or press Enter or Tab)
            </div>);
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="heightExplanation">
                <h4 className="alert-heading">How does AddBiomechanics use mass?</h4>
                <p>If you have force plate data, AddBiomechanics will fine-tune subject mass based on physical consistency, so mass here is <b>just an initial guess</b>. Even if you do not have force plate data, AddBiomechanics also uses this information to to condition a statistical prior about the subject's anthropometric dimensions. The prior is based on the <a href="https://www.openlab.psu.edu/ansur2/">ANSUR II dataset</a>, which covers a population of healthy adults (who were serving in the military when the dataset was collected).</p>
                <hr />
                <p className="mb-0">If you don't know, it's ok to put in the population average, 68kg.</p>
            </div>);
        }
        else {
            completedFormElements++;
        }
    }
    //////////////////////////////////////////////////////////////////
    // 1.3. Create the entry for the subject's biological sex
    totalFormElements++;
    if (formCompleteSoFar) {
        formElements.push(<div key="sex" className="mb-3">
            <label>Biological Sex:</label>
            <select
                id="sex"
                value={subjectSex}
                className={"form-control" + ((subjectSex === '') ? " border-primary border-2" : "")}
                autoFocus={subjectSex === ''}
                aria-describedby="sexHelp"
                onChange={(e) => {
                    subjectJson.setAttribute("sex", e.target.value);
                }}
                onFocus={(e) => {
                    subjectJson.onFocusAttribute("sex");
                }}
                onBlur={(e) => {
                    subjectJson.onBlurAttribute("sex");
                }}>
                <option value="">Needs selection</option>
                <option value="unknown">Unknown</option>
                <option value="male">Male</option>
                <option value="female">Female</option>
            </select>
            <div id="sexHelp" className="form-text">The biological sex of the subject, if available.</div>
        </div>);

        if (subjectSex === '') {
            formCompleteSoFar = false;
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="sexExplanation">
                <h4 className="alert-heading">How does AddBiomechanics use biological sex?</h4>
                <p>AddBiomechanics uses biological sex information, when available, to to condition a statistical prior about the subject's anthropometric dimensions. The prior is based on the <a href="https://www.openlab.psu.edu/ansur2/">ANSUR II dataset</a>, which covers a population of healthy adults (who were serving in the military when the dataset was collected).</p>
                <hr />
                <p className="mb-0">If you don't know, it's ok to put "Unknown", and AddBiomechanics will only condition the prior on the subject's height and mass.</p>
            </div>);
        }
        else {
            completedFormElements++;
        }
    }
    //////////////////////////////////////////////////////////////////
    // 1.4. Create the entry for the subject age in years
    totalFormElements++;
    if (formCompleteSoFar) {
        formElements.push(<div key="age" className="mb-3">
            <label htmlFor="ageInput" className="form-label">Age (years):</label>
            <input
                type="number"
                id="ageInput"
                className={"form-control" + ((subjectAgeYears === "" || !subjectAgeComplete) ? " border-primary border-2" : "")}
                aria-describedby="ageHelp"
                value={subjectAgeYears}
                autoFocus={subjectAgeYears === "" || !subjectAgeComplete}
                onFocus={() => subjectJson.onFocusAttribute("ageYears")}
                onBlur={() => subjectJson.onBlurAttribute("ageYears")}
                onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === 'Tab') {
                        setSubjectAgeComplete(true);
                    }
                }}
                onChange={(e) => {
                    if (e.target.value === '') {
                        subjectJson.setAttribute("ageYears", null);
                    }
                    else {
                        subjectJson.setAttribute("ageYears", parseInt(e.target.value));
                    }
                }}></input>
            <div id="ageHelp" className="form-text">The age of the subject, in years. -1 if not known.</div>
        </div>);

        if (subjectAgeYears === '' || !subjectAgeComplete) {
            if (subjectAgeComplete) {
                setSubjectAgeComplete(false);
            }
            formCompleteSoFar = false;
            formElements.push(<div key='ageConfirm'>
                <button type="button" className="btn btn-primary" onClick={() => setSubjectAgeComplete(true)}>Confirm Age</button> (or press Enter or Tab)
            </div>);
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="heightExplanation">
                <h4 className="alert-heading">How does AddBiomechanics use age?</h4>
                <p>Currently, AddBiomechanics does not use the age value in the scaling process, though it may in the future. This field is included to allow large N studies of the effect of age on movement using AddBiomechanics data.</p>
                <hr />
                <p className="mb-0">If you don't know, please put -1.</p>
            </div>);
        }
        else {
            completedFormElements++;
        }
    }
    //////////////////////////////////////////////////////////////////
    // 1.5. Create the entry for the subject tags
    totalFormElements++;
    if (formCompleteSoFar) {
        formElements.push(<div key="tags" className="mb-3">
            <label>Subject Tags:</label>
            <TagEditor
                tagSet='subject'
                error={subjectTags.length == 0}
                tags={subjectTags}
                readonly={props.readonly}
                onTagsChanged={(newTags) => {
                    subjectJson.setAttribute("subjectTags", newTags);
                }}
                tagValues={subjectTagValues}
                onTagValuesChanged={(newTagValues) => {
                    subjectJson.setAttribute("subjectTagValues", newTagValues);
                }}
                onFocus={() => {
                    subjectJson.onFocusAttribute("subjectTags");
                }}
                onBlur={() => {
                    subjectJson.onBlurAttribute("subjectTags");
                }}
            />
        </div>);

        if (subjectTags.length == 0) {
            formCompleteSoFar = false;
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="modelExplanation">
                <h4 className="alert-heading">Why do I need to tag my subject?</h4>
                <p>
                    Data uploaded to AddBiomechanics is periodically shared in large public releases. The data is vastly more useful 
                    if it is tagged with some characteristics of the subject. When you download large public releases to ask "big N 
                    questions" about populations, you will thank yourself (and everyone else) for tagging your data!
                </p>
                <hr />
                <p className="mb-0">
                    If there isn't any other available tag to use, you can specify "Unimpaired".
                </p>
            </div>);
        }
        else {
            completedFormElements++;
        }
    }
    //////////////////////////////////////////////////////////////////
    // 1.5. Create the entry for the OpenSim model we want to use
    totalFormElements++;
    if (formCompleteSoFar) {
        formElements.push(<div key="model" className="mb-3">
            <label>OpenSim Model to Personalize:</label>
            <select
                id="model"
                value={subjectModel}
                className={"form-control" + ((subjectModel == '') ? " border-primary border-2" : "")}
                autoFocus={subjectModel == ''}
                aria-describedby="modelHelp"
                onChange={(e) => {
                    subjectJson.setAttribute("skeletonPreset", e.target.value);
                }}>
                <option value="">Needs selection</option>
                <option value="custom">Upload my own model</option>
                <option value="vicon">Rajagopal 2016 with Vicon Markerset</option>
                <option value="cmu">Rajagopal 2016 with CMU Markerset</option>
            </select>
            <div id="modelHelp" className="form-text">Musculoskeletal model to use as a starting point to personalize for the subject.</div>
        </div>);

        if (subjectModel == '') {
            formCompleteSoFar = false;
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="modelExplanation">
                <h4 className="alert-heading">How do I choose which OpenSim model to use?</h4>
                <p>
                    AddBiomechanics personalizes the OpenSim musculoskeletal model you provide to match your subject's capture data as closely as possible.
                    The OpenSim model you choose <b>must have markers whose names match the ones in the motion capture files you upload. </b>
                    It's ok if the model has more markers than the motion capture files, as additional markers will be ignored.
                </p>
                <p>
                    If you are not familiar with <a href="https://simtk.org/projects/opensim" rel="noreferrer" target="_blank">OpenSim</a>, a good default model is the <a href="https://simtk.org/projects/full_body" target="_blank">Rajagopal 2016</a> model.
                    We offer a Rajagopal 2016 model with a few different common markersets as a convenience, if you don't want to upload your own model.
                    <ul>
                        <li>The <a href="https://simtk.org/projects/full_body" rel="noreferrer" target="_blank">Rajagopal 2016</a> model with a <a href="https://docs.vicon.com/download/attachments/133828966/Plug-in%20Gait%20Reference%20Guide.pdf?version=2&modificationDate=1637681079000&api=v2" rel="noreferrer" target="_blank">standard Vicon markerset</a></li>
                        <li>The <a href="https://simtk.org/projects/full_body" rel="noreferrer" target="_blank">Rajagopal 2016</a> model with a <a href="http://mocap.cs.cmu.edu/markerPlacementGuide.pdf" rel="noreferrer" target="_blank">CMU markerset</a></li>
                        <li>Upload your own custom OpenSim model</li>
                    </ul>
                </p>
            </div>);
        }
        else {
            completedFormElements++;
        }
    }

    //////////////////////////////////////////////////////////////////
    // 1.6. Create the entry for uploading a custom OpenSim model, if needed
    if (subjectModel === 'custom') {
        totalFormElements++;
        if (formCompleteSoFar) {
            formElements.push(<div key="customModel" className="mb-3">
                <label>Upload Custom OpenSim Model:</label>
                <DropFile file={subjectState.customOpensimModel} accept=".osim" onDrop={subjectState.dropOpensimFile} readonly={props.readonly}></DropFile>
                <div id="customModelHelp" className="form-text">Custom OpenSim file to scale for the subject.</div>
            </div>);

            if (!subjectState.customOpensimModel.exists) {
                formCompleteSoFar = false;
                formElements.push(<div className="alert alert-dark mt-2" role="alert" key="customModelExplanation">
                    <h4 className="alert-heading">What kinds of custom OpenSim models are supported?</h4>
                    <p>
                        AddBiomechanics personalizes the OpenSim musculoskeletal model you provide to match your subject's capture data as closely as possible.
                        The OpenSim model you choose <b>must have markers whose names match the ones in the motion capture files you upload. </b>
                        It's ok if the model has more markers than the motion capture files, as additional markers will be ignored.
                        Also, AddBiomechanics currently <b>only supports full-body human models</b>! Otherwise, the statistical priors we use to help fit the model will be invalid.
                    </p>
                </div>);
            }
            else {
                completedFormElements++;
            }
        }
    }

    //////////////////////////////////////////////////////////////////
    // 1.7. Create the entry for if the user wants to fit dynamics
    totalFormElements++;
    if (formCompleteSoFar) {
        formElements.push(<div key="physics" className="mb-3">
            <label>Fit Physics Data:</label>
            <select
                id="physics"
                value={disableDynamics == null ? "" : (disableDynamics ? "true" : "false")}
                className={"form-control" + ((disableDynamics == null) ? " border-primary border-2" : "")}
                autoFocus={disableDynamics == null}
                aria-describedby="physicsHelp"
                onChange={(e) => {
                    subjectJson.setAttribute("disableDynamics", e.target.value === '' ? null : (e.target.value === 'true' ? true : false));
                }}>
                <option value="">Needs selection</option>
                <option value="false">Fit Physics</option>
                <option value="true">Do Not Fit Physics</option>
            </select>
            <div id="physicsHelp" className="form-text">Should AddBiomechanics use ground reaction force data?</div>
        </div>);

        if (disableDynamics == null) {
            formCompleteSoFar = false;
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="modelExplanation">
                <h4 className="alert-heading">Should I Fit Physics Data?</h4>
                <p>
                    AddBiomechanics personalizes the OpenSim musculoskeletal model you provide to match your subject's capture data as closely as possible.
                </p>
                <p>
                    If you ask AddBiomechanics to fit physics data by selecting "Fit Physics", it will use any portions of the trials you upload that have ground reaction force data to tune the model's mass and inertial properties, and to fine tune the motion of the subject.
                    AddBiomechanics will also run inverse dynamics, and report joint torques it has found.
                </p>
                <p>
                    You can disable this behavior by selecting "Do Not Fit Physics".
                </p>
            </div>);
        }
        else {
            completedFormElements++;
        }
    }

    //////////////////////////////////////////////////////////////////
    // 1.8. If necessary, create the selector for which bodies to apply GRF to
    if (!disableDynamics && subjectModel === 'custom') {
        totalFormElements++;
        if (formCompleteSoFar) {
            let footErrorMessage = null;
            if (footBodyNames.length < 2) {
                footErrorMessage = (
                    <div className="invalid-feedback">
                        To fit dynamics to your data, please specify at least two body nodes that we can treat as "feet", and send ground reaction forces through.
                    </div>
                );
            }
            else if (footBodyNames.length > 2) {
                footErrorMessage = (
                    <div className="invalid-feedback">
                        Currently AddBiomechanics dynamics fitter only supports treating each foot as a single body segment. Please don't include multiple segments from each foot.
                    </div>
                );
            }

            formElements.push(<div key="feet" className="mb-3">
                <label>Specify Two Feet in Custom OpenSim Model:</label>
                <TagEditor
                    error={footBodyNames.length != 2}
                    tagSet={subjectState.availableBodyNodes}
                    tags={footBodyNames}
                    readonly={props.readonly}
                    onTagsChanged={(newTags) => {
                        subjectJson.setAttribute("footBodyNames", newTags);
                    }}
                    tagValues={{}}
                    onTagValuesChanged={(newTagValues) => {
                        // Do nothing
                    }}
                    onFocus={() => {
                        subjectJson.onFocusAttribute("footBodyNames");
                    }}
                    onBlur={() => {
                        subjectJson.onBlurAttribute("footBodyNames");
                    }}
                />
            </div>);

            if (footBodyNames.length != 2) {
                formCompleteSoFar = false;
                formElements.push(<div className="alert alert-dark mt-2" role="alert" key="footExplanation">
                    <h4 className="alert-heading">Why do I need to specify two feet in my Custom OpenSim Model?</h4>
                    <p>
                        When AddBiomechanics is fitting physics to your model, it assumes every measured ground reaction force goes through one of the "foot" segments of your model. AddBiomechanics will automatically assign forces on each from to the appropriate foot segment based on their spatial location. The tool currently works best if you select only two segments to serve as "feet", even if your feet are modeled as articulated bodies.
                    </p>
                    <hr />
                    <p className="mb-0">If you don't have a good reason not to, on most full body OpenSim models a good default choice is "calcn_l" and "calcn_r".</p>
                </div>);
            }
            else {
                completedFormElements++;
            }
        }
    }

    //////////////////////////////////////////////////////////////////
    // 1.9. Create the entry for if the user wants to run a Moco problem after the fact
    if (!disableDynamics) {
        totalFormElements++;
        if (formCompleteSoFar) {
            formElements.push(<div key="moco" className="mb-3">
                <label>Solve For Muscle Activations:</label>
                <select
                    id="moco"
                    value={runMoco == null ? "" : (runMoco ? "true" : "false")}
                    className={"form-control" + ((runMoco == null) ? " border-primary border-2" : "")}
                    autoFocus={runMoco == null}
                    aria-describedby="mocoHelp"
                    onChange={(e) => {
                        subjectJson.setAttribute("runMoco", e.target.value === '' ? null : (e.target.value === 'true' ? true : false));
                    }}>
                    <option value="">Needs selection</option>
                    <option value="true">Solve for Muscles</option>
                    <option value="false">Do Not Solve for Muscles</option>
                </select>
                <div id="mocoHelp" className="form-text">Should AddBiomechanics run a Moco optimization to solve for muscle activations?</div>
            </div>);

            if (runMoco == null) {
                formCompleteSoFar = false;
                formElements.push(<div className="alert alert-dark mt-2" role="alert" key="mocoExplanation">
                    <h4 className="alert-heading">Should I Solve for Muscle Activations?</h4>
                    <p>
                        AddBiomechanics integrates with the powerful <a href="https://opensim-org.github.io/opensim-moco-site/">OpenSim Moco software</a> (created by Nick Bianco and Chris Dembia) to solve for muscle activations that are consistent with the physical motion that AddBiomechanics finds for your data.
                        This adds a significant amount of time to the processing, but can be useful if you want to use the results of your motion capture data to analyze muscle activations.
                    </p>
                    <hr />
                    <p className="mb-0">If you're not sure, you should select "Do Not Solve for Muscles" and you can always come back and run this later.</p>
                </div>);
            }
            else {
                completedFormElements++;
            }
        }
    }
    //////////////////////////////////////////////////////////////////
    // 1.10. Create an entry for the state of this data
    totalFormElements++;
    if (formCompleteSoFar) {
        formElements.push(<div key="data" className="mb-3">
            <label>Quality of Raw Mocap Data:</label>
            <select
                id="data"
                value={subjectDataSource}
                className={"form-control" + ((subjectDataSource == '') ? " border-primary border-2" : "")}
                autoFocus={subjectDataSource == ''}
                aria-describedby="dataHelp"
                onChange={(e) => {
                    subjectJson.setAttribute("dataSource", e.target.value);
                }}>
                <option value="">Needs selection</option>
                <option value="pilot">Just experimenting - rough pilot data</option>
                <option value="study">Study data - carefully collected</option>
                <option value="public">Found on the internet - unknown quality</option>
            </select>
            <div id="dataHelp" className="form-text">We treat different kinds of data differently</div>
        </div>);

        if (subjectDataSource == '') {
            formCompleteSoFar = false;
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="modelExplanation">
                <h4 className="alert-heading">How do I choose which "Quality of Data" to say?</h4>
                <p>
                    AddBiomechanics treats different kinds of data differently. By telling us how confident you 
                    are in the data, we can modulate how much computation to use producing a result.
                </p>
                <p>
                    This tag also helps us to determine what data needs extra quality checks before getting 
                    included in any large public dataset releases.
                </p>
                <p>
                    Here's what each option means:
                    <ul>
                        <li>
                            <h5>Just experimenting:</h5>
                            This is data you collected quickly, perhaps without 
                            super careful marker placement, and maybe while still debugging the protocol for your 
                            study. We will <b>use fewer optimization iterations</b> to process your data.
                            We will also treat it with extreme caution when evaluating for inclusion in public 
                            dataset releases.
                        </li>
                        <li>
                            <h5>Study data:</h5>
                            This is data you collected carefully. We will <b>use more 
                            optimization iterations</b> to process your data to get the highest quality results.
                        </li>
                        <li>
                            <h5>Found on the internet:</h5>
                            This is not data you collected yourself. It could be very high 
                            quality, or it could be bad -- and you're about to find out! AddBiomechanics will be optimistic 
                            and use <b>more optimization iterations</b> to try to get the highest quality results.
                        </li>
                    </ul>
                </p>
            </div>);
        }
        else {
            completedFormElements++;
        }
    }
    //////////////////////////////////////////////////////////////////
    // 1.11. Create the entry for checking if the subject consented to have their data uploaded
    totalFormElements++;
    if (formCompleteSoFar) {
        formElements.push(<div key="consent" className="mb-3">
            <label>Subject Consent:</label>
            <select
                id="consent"
                value={subjectConsent == null ? "" : (subjectConsent ? "true" : "false")}
                className={"form-control" + ((subjectConsent == null) ? " border-primary border-2" : "") + ((subjectConsent == false) ? " border-danger border-2" : "")}
                autoFocus={subjectConsent == null}
                aria-describedby="consentHelp"
                onChange={(e) => {
                    subjectJson.setAttribute("subjectConsent", e.target.value === '' ? null : (e.target.value === 'true' ? true : false));
                }}>
                <option value="">Needs selection</option>
                <option value="true">Subject Consented to Share Data</option>
                <option value="false">Subject Did Not Consent</option>
            </select>
            <div id="consentHelp" className="form-text">All data uploaded to AddBiomechanics is publicly accessible, so subject consent is required</div>
        </div>);

        if (subjectConsent == null || subjectConsent === false) {
            formCompleteSoFar = false;
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="modelExplanation">
                <h4 className="alert-heading">Do I need subject consent to upload?</h4>
                <p>
                    Yes! Data processed on AddBiomechanics is shared with the community, so you need to make sure that the subject has consented to sharing their anonymized motion data before proceeding.
                </p>
                <p>
                    <b>What should I put in my IRB?</b> You could use language like the following in your consent (IRB) forms to inform participants about how you will share their
                    data, and give them the option to opt out.
                </p>
                <ul>
                    <li><i>Consent forms example:</i> "I understand that my motion capture data (i.e., the time-history of how my body segments are moving when I walk or
                        perform other movements) will be shared in a public repository. Sharing my data will enable others to replicate the
                        results of this study, and enable future progress in human motion science. This motion data will not be linked with any
                        other identifiable information about me."</li>
                    <li><i>IRB paragraph example:</i> "Biomechanics data are processed using the AddBiomechanics web application and stored in Amazon Web Services (AWS) S3
                        instances. All drafted and published data stored in these instances are publicly accessible to AddBiomechanics users. Public data
                        will be accessible through the web interface and through aggregated data distributions."</li>
                </ul>
                <p>
                    <b>If the data you are uploading comes from an existing public motion capture database,</b> it is fine to assume that the original publishers of that data got subject consent.
                </p>
            </div>);
        }
        else {
            completedFormElements++;
        }
    }
    //////////////////////////////////////////////////////////////////
    // 1.12. Create the entry for citation info
    totalFormElements++;
    if (formCompleteSoFar) {
        formElements.push(<div key="citation" className="mb-3">
            <label>Desired Citation:</label>
            <textarea
                id="citation"
                value={subjectCitation == null ? "" : subjectCitation}
                className={"form-control" + ((subjectCitation == null) ? " border-primary border-2" : "")}
                autoFocus={subjectCitation == null || !subjectCitationComplete}
                aria-describedby="citeHelp"
                onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === 'Tab') {
                        if (subjectCitation == null) {
                            subjectJson.setAttribute("citation", "");
                        }
                        setSubjectCitationComplete(true);
                        const input = e.target as HTMLInputElement;
                        input.blur();
                    }
                }}
                onFocus={() => {
                    subjectJson.onFocusAttribute("citation");
                }}
                onBlur={() => {
                    subjectJson.onBlurAttribute("citation");
                }}
                onChange={(e) => {
                    subjectJson.setAttribute("citation", e.target.value);
                }}>
            </textarea>
            <div id="citeHelp" className="form-text">How do you want this data to be cited?</div>
        </div>);

        if (subjectCitation == null || !subjectCitationComplete) {
            if (subjectCitationComplete) {
                setSubjectCitationComplete(false);
            }
            formCompleteSoFar = false;
            formElements.push(<div key='citationConfirm'>
                <button type="button" className="btn btn-primary" onClick={() => setSubjectCitationComplete(true)}>Confirm Citation</button> (or press Enter or Tab)
            </div>);
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="citationExplanation">
                <h4 className="alert-heading">What should I put for my citation?</h4>
                <p>
                    It's fine to leave this blank, if you don't have a preferred citation. If you do, please include it here.
                </p>
                <p>
                    You can include your citation in any format you like, just note that this information is public.
                </p>
                <h5>IMPORTANT: NEVER INCLUDE PATIENT IDENTIFYING INFORMATION IN YOUR CITATION!</h5>
                <p>
                    Definitely do not put something like "Keenon Werling's gait data" in the citation field, unless 
                    your subject has explicitly given informed consent to be identified and has requested that users 
                    of the data cite them by name.
                </p>
            </div>);
        }
        else {
            completedFormElements++;
        }
    }


    const subjectForm = (
        <Form onSubmit={(e) => {
            e.preventDefault();
            e.stopPropagation();
        }}>
            {formElements}
        </Form>
    );
    // If we haven't completed the form yet, then that's the only thing we need to render, along with a progress bar for filling out the form
    if (completedFormElements < totalFormElements) {
        return <div className='container'>
            {subjectForm}
            <hr />
            <ProgressBar now={completedFormElements} max={totalFormElements} />
            <p>
                {completedFormElements} of {totalFormElements} fields complete.
            </p>
        </div>
    }

    const markerLiveFiles: LiveFile[] = [];
    for (let i = 0; i < subjectState.trials.length; i++) {
        markerLiveFiles.push(subjectState.getLiveFileForTrialMarkers(subjectState.trials[i]));
    }

    let mocapFilesTable = null;
    if (subjectState.trials.length > 0) {
        mocapFilesTable = <table className="table" style={{width: '100%', overflow: 'hidden', tableLayout: 'fixed'}}>
            <thead>
                <tr>
                    <th scope="col" style={{width: '100px', maxWidth: '30%'}}>Name</th>
                    <th scope="col">Marker {disableDynamics ? '' : ' and Forces'} Data</th>
                    <th scope="col">Tags</th>
                    <th scope="col" style={{width: '100px'}}>Delete?</th>
                </tr>
            </thead>
            <tbody>
                {subjectState.trials.map((trial, i: number) => {
                    const markerLiveFile = markerLiveFiles[i];
                    let dataFiles: React.ReactElement[] = [];

                    dataFiles.push(
                        <div key='markers'>
                            <DropFile file={markerLiveFile} accept=".c3d,.trc" readonly={props.readonly} onDrop={(files: File[]) => subjectState.dropMarkerFiles(trial, files)} />
                        </div>
                    );
                    if (trial.trcFileExists && !trial.c3dFileExists && !disableDynamics) {
                        const grfMotLiveFile = home.dir.getLiveFile(trial.grfMotFilePath);
                        dataFiles.push(
                            <div key='grf' className="mt-2">
                                <DropFile file={grfMotLiveFile} accept=".mot" text="GRF *.mot file" readonly={props.readonly} onDrop={(files: File[]) => subjectState.dropGRFFiles(trial, files)} />
                            </div>
                        );
                    }

                    const trialTags = trial.trialJson.getAttribute("trialTags", []);
                    const trialTagValues = subjectJson.getAttribute("trialTagValues", {} as { [key: string]: number });
                    return <tr key={trial.name}>
                        <td>{trial.name}</td>
                        <td>
                            {dataFiles}
                        </td>
                        <td style={{
                            minWidth: '200px'
                        }}>
                            <TagEditor 
                                tagSet='trial' 
                                error={false}
                                tags={trialTags}
                                readonly={props.readonly} 
                                onTagsChanged={(newTags) => {
                                    trial.trialJson.setAttribute("trialTags", newTags);
                                }}
                                tagValues={trialTagValues}
                                onTagValuesChanged={(newTagValues) => {
                                    trial.trialJson.setAttribute("trialTagValues", trialTagValues);
                                }}
                                onFocus={() => {
                                    trial.trialJson.onFocusAttribute("trialTags");
                                }}
                                onBlur={() => {
                                    trial.trialJson.onBlurAttribute("trialTags");
                                }}
                            />
                        </td>
                        <td><button className="btn btn-dark" onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            if (window.confirm("Are you sure you want to delete trial \"" + trial.name + "\"?")) {
                                subjectState.deleteTrial(trial);
                            }
                        }}>Delete</button></td>
                    </tr>;
                })}
            </tbody>
        </table>
    }

    let mocapHelpText = null;
    let submitButton = null;
    if (!readyFlagExists) {
        mocapHelpText = <div className="alert alert-dark mt-2" role="alert">
            <h4 className="alert-heading">How do I add motion capture trials?</h4>
            <p>
                You can drag and drop <code>*.c3d</code> or <code>*.trc</code> files onto the dropzone above to create trials. We recommend you use <code>*.c3d</code> files when possible. Trials will be created which match the names of the files you upload.
            </p>
            {disableDynamics ? null :
                <p>
                    Because you are fitting physics, you will need to upload ground reaction force data. Forces come bundled in <code>*.c3d</code> files, so those require no extra steps. If instead you choose to use <code>*.trc</code> files for your markers, then you will also need to upload <code>*.mot</code> files containing ground reaction force data for each trial. These files should be named the same as the trial files, but with the <code>*.mot</code> extension.
                </p>
            }
            <p>
                When you've uploaded all the files you want, click the "Submit for Processing" button below.
            </p>
        </div>;
        submitButton =
            <button className="btn btn-lg btn-primary mt-2" disabled={subjectState.trials.length === 0} style={{ width: '100%' }} onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                subjectState.submitForProcessing();
            }}>Submit for Processing</button>;
    }

    const onDrop = (e: DragEvent) => {
        setDropZoneActive(false);
        e.preventDefault();

        let acceptedFiles: File[] = [];
        if (e.dataTransfer && e.dataTransfer.items) {
            for (let i = 0; i < e.dataTransfer.items.length; i++) {
                if (e.dataTransfer.items[i].kind === 'file') {
                    const file = e.dataTransfer.items[i].getAsFile();
                    if (file) {
                        acceptedFiles.push(file);
                    }
                }
            }
        }

        subjectState.dropFilesToUpload(acceptedFiles);
    };

    const trialsUploadSection = <>
        <h3>Motion Capture Files:</h3>
        {mocapFilesTable}
        <div className={"dropzone" + (dropZoneActive ? ' dropzone-hover' : '')}
             onDrop={onDrop as any}
             onDragOver={(e) => {
                e.preventDefault();
             }}
             onDragEnter={() => {
                setDropZoneActive(true);
             }}
             onDragLeave={() => {
                setDropZoneActive(false);
             }}>
            <div className="dz-message needsclick">
                <i className="h3 text-muted dripicons-cloud-upload"></i>
                <h5>
                    Drop C3D or TRC files here to create trials.
                </h5>
                <span className="text-muted font-13">
                    (You can drop multiple files at once to create multiple
                    trials simultaneously)
                </span>
            </div>
        </div>
        {submitButton}
        {mocapHelpText}
    </>;

    let statusSection = null;
    if (readyFlagExists) {
        if (errorFlagExists) {
            statusSection = <div>
                <h3>Status: Error</h3>
                <button className="btn btn-primary" onClick={async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    await errorFlagFile.delete();
                    await processingFlagFile.delete();
                }}>Reprocess</button>
            </div>;
        }
        else if (resultsExist) {
            statusSection = <div>
                <h3>Status: Finished!</h3>
                <button className="btn btn-warning" onClick={async (e) => {
                    if (window.confirm("Are you sure you want to reprocess the data? That will delete your current results.")) {
                        e.preventDefault();
                        e.stopPropagation();
                        await props.home.dir.delete(subjectState.resultsJsonPath);
                        await errorFlagFile.delete();
                        await processingFlagFile.delete();
                    }
                }}>Reprocess</button>
            </div>;
        }
        else if (processingFlagExists) {
            statusSection = <div>
                <h3>Status: Processing</h3>
                <button className="btn btn-primary" onClick={async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    await processingFlagFile.delete();
                }}>Force Reprocess</button>
            </div>;
        }
        else {
            statusSection = <div>
                <h3>Status: Waiting for server</h3>
            </div>;
        }
    }

    let resultsSection = null;
    if (resultsExist) {
        const trialNames: string[] = subjectState.trials.map((trial) => trial.name);

        resultsSection = <div>
            <h3>Results:</h3>
            <table className="table">
                <thead>
                    <tr>
                        <th scope="col">Trial Segment</th>
                        <th scope="col">Marker Error</th>
                        <th scope="col">Forces Error</th>
                    </tr>
                </thead>
                <tbody>
                    {
                        subjectState.trials.flatMap((trial) => {
                            if (trial.name in subjectState.parsedResultsJson) {
                                const trialResults = subjectState.parsedResultsJson[trial.name];
                                return trial.segments.map((segment, index) => {
                                    const segmentResults = trialResults.segments[index];
                                    let kinematicsResults: string = '';
                                    if (segmentResults.kinematicsStatus === 'FINISHED') {
                                        kinematicsResults = (segmentResults.kinematicsAvgRMSE == null ? 'NaN' : segmentResults.kinematicsAvgRMSE.toFixed(2)) + ' cm RMSE';
                                    }
                                    else if (segmentResults.kinematicsStatus === 'ERROR') {
                                        kinematicsResults = 'Error';
                                    }
                                    else if (segmentResults.kinematicsStatus === 'NOT_STARTED') {
                                        kinematicsResults = 'Not run';
                                    }

                                    let dynamicsResults: string = '';
                                    if (segmentResults.dynamicsStatus === 'FINISHED') {
                                        dynamicsResults = (segmentResults.linearResiduals == null ? 'NaN' : segmentResults.linearResiduals.toFixed(2)) + ' N, ' + (segmentResults.angularResiduals == null ? 'NaN' : segmentResults.angularResiduals.toFixed(2)) + ' Nm';
                                    }
                                    else if (segmentResults.dynamicsStatus === 'ERROR') {
                                        dynamicsResults = 'Error';
                                    }
                                    else if (segmentResults.dynamicsStatus === 'NOT_STARTED') {
                                        dynamicsResults = 'Not run';
                                    }

                                    return <tr key={segment.path}>
                                        <td><button className="btn btn-primary" onClick={() => {
                                            navigate(Session.getDataURL(props.currentLocationUserId, segment.path));
                                        }}>
                                            View "{trial.name}" {segmentResults.start}s to {segmentResults.end}s
                                        </button></td>
                                        <td>{kinematicsResults}</td>
                                        <td>{dynamicsResults}</td>
                                    </tr>
                                });
                            }
                            else {
                                return [<tr key={trial.name}>
                                    <td>{trial.name} Loading...</td>
                                    <td></td>
                                    <td></td>
                                </tr>]
                            }
                        })
                    }
                </tbody>
            </table>
        </div>
    }

    return <div className='container'>
        {subjectForm}
        {trialsUploadSection}
        {statusSection}
        {resultsSection}
    </div>
});

export default SubjectView;