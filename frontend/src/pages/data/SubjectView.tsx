import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ProgressBar, Form } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import UserHomeDirectory from "../../model/UserHomeDirectory";
import DropFile from "../../components/DropFile";
import TagEditor from '../../components/TagEditor';
import Session from "../../model/Session";
import SubjectViewState from "../../model/SubjectViewState";
import LiveFile from "../../model/LiveFile";
import { parseLinks, showToast } from "../../utils"
import { toast } from 'react-toastify';
import { action } from "mobx";


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
    const incompleteSubjectFlagFile = subjectState.incompleteSubjectFlagFile;
    const processingFlagFile = subjectState.processingFlagFile;
    const slurmFlagFile = subjectState.slurmFlagFile;
    const errorFlagFile = subjectState.errorFlagFile;

    // Show or hide extended log.
    const [showLog, setShowLog] = useState<boolean>(false);

    // Informative toast
    // showToast(
    //   "Scheduled Maintenance: AddBiomechanics will be unavailable on Tuesday, February 4, 2025, from 8:00 AM to 6:00 PM due to maintenance of the Stanford Computing Cluster. Tasks queued during this time will be paused and resume automatically afterward. Thank you for your understanding.",
    //   "warning",
    //   "processing",
    //   toast.POSITION.BOTTOM_CENTER,
    //   false
    // );

    // Check on the value of the key _subject.json attributes unconditionally, to ensure that MobX updates if the attributes change
    let subjectDataSource: '' | 'public' | 'pilot' | 'study' = subjectJson.getAttribute("dataSource", "");
    if (subjectDataSource as any === 'published') {
        // If the user has an old version of _subject.json, update it to the new format
        subjectDataSource = 'public';
        if (!props.readonly) {
            subjectJson.setAttribute("dataSource", 'public');
        }
    }
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
    const incompleteSubjectFlagExists = incompleteSubjectFlagFile.exists && !incompleteSubjectFlagFile.loading;
    const errorFlagExists = errorFlagFile.exists && !errorFlagFile.loading;
    const processingFlagExists = processingFlagFile.exists && !processingFlagFile.loading;
    const slurmFlagExists = slurmFlagFile.exists && !slurmFlagFile.loading;

    // Create state to manage the file drop zone
    const [dropZoneActive, setDropZoneActive] = useState(false);

    // Handle checkbox change for dismissing warnings.
    const handleCheckboxChange = (segment: any) => (event: any) => {
        const isChecked = event.target.checked;
        if (isChecked) {
            if (!segment.reviewFlagExists) {
                home.dir.uploadText(segment.reviewFlagPath, "").then(() => {
                    action(() => {
                        segment.reviewFlagExists = false;
                    })();
                });
            }
        } else {
            if (segment.reviewFlagExists) {
                home.dir.delete(segment.reviewFlagPath).then(() => {
                    action(() => {
                        segment.reviewFlagExists = false;
                    })();
                });
            }
        }
    };

    /////////////////////////////////////////////////////////////////////////
    // There are several states a subject can be in:
    // 0. Still loading, we're not sure what state we're in yet.
    // 1. Just created, so _subject.json is missing values or there are no trials. In this case, we want to show a wizard.
    // 2. User has indicated processing is ready, but we haven't finished processing yet. In this case, we want to show a status page.
    // 3. Processing finished, in which case we want to show results on the subject page.
    /////////////////////////////////////////////////////////////////////////

    // 0. We're still loading
    if (subjectState.loading || subjectJson.isLoadingFirstTime() || readyFlagFile.loading || processingFlagFile.loading || incompleteSubjectFlagFile.loading) {
        return <div>Loading...</div>;
    }

    // 1. Create a wizard form for the _subject.json values, populated to the point in the journey that the user has reached.
    let formElements: JSX.Element[] = [
        <div key="title">
            <h3>Subject <code>{subjectState.name}</code> Metrics:</h3>
        </div>
    ];
    let formCompleteSoFar: boolean = true;
    let completedFormElements: number = 0;
    let totalFormElements: number = 0;

    //////////////////////////////////////////////////////////////////
    // 1.1. Create the entry for the subject height
    totalFormElements++;
    if (formCompleteSoFar) {
        const showHeightBoundsWarning = subjectHeightM < 0.8 || subjectHeightM > 2.5;
        formElements.push(<div key="height" className="mb-3">
            <label htmlFor="heightInput" className="form-label">Height (m):</label>
            <input
                type="number"
                id="heightInput"
                className={"form-control" + ((subjectHeightM <= 0 || !subjectHeightComplete) ? " border-primary border-2" : "") + (showHeightBoundsWarning ? " border-danger border-2" : "")}
                aria-describedby="heightHelp"
                value={subjectHeightM}
                autoFocus={subjectHeightM <= 0 || !subjectHeightComplete}
                onFocus={() => {
                    subjectJson.onFocusAttribute("heightM");
                }}
                onBlur={() => subjectJson.onBlurAttribute("heightM")}
                disabled={props.readonly}
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
            <div id="massHelp" className="form-text">The height of the subject, in meters.
                {showHeightBoundsWarning && <span className="text-danger"> Please check that this value is reasonable for a human subject.</span>}
            </div>
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
        const showMassBoundsWarning = (subjectMassKg < 30 || subjectMassKg > 150) && subjectMassKg !== -1;

        formElements.push(<div key="mass" className="mb-3">
            <label htmlFor="massInput" className="form-label">Mass (kg):</label>
            <input
                type="number"
                id="massInput"
                className={"form-control" + (((subjectMassKg <= 0 && subjectMassKg !== -1) || !subjectMassComplete) ? " border-primary border-2" : "") + (showMassBoundsWarning ? " border-danger border-2" : "")}
                aria-describedby="massHelp"
                value={subjectMassKg}
                autoFocus={subjectMassKg <= 0 || !subjectMassComplete}
                onFocus={() => subjectJson.onFocusAttribute("massKg")}
                onBlur={() => subjectJson.onBlurAttribute("massKg")}
                disabled={props.readonly}
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
            <div id="massHelp" className="form-text">
                The approximate mass of the subject, in kilograms.
                {showMassBoundsWarning && <span className="text-danger"> Please check that this value is reasonable for a human subject.</span>}
            </div>
        </div>);

        if ((subjectMassKg <= 0 && subjectMassKg !== -1) || !subjectMassComplete) {
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
                disabled={props.readonly}
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
                disabled={props.readonly}
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
                error={subjectTags.length === 0}
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

        if (subjectTags.length === 0) {
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
                className={"form-control" + ((subjectModel === '') ? " border-primary border-2" : "")}
                autoFocus={subjectModel === ''}
                aria-describedby="modelHelp"
                disabled={props.readonly}
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

        if (subjectModel === '') {
            formCompleteSoFar = false;
            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="modelExplanation">
                <h4 className="alert-heading">How do I choose which OpenSim model to use?</h4>
                <p>
                    AddBiomechanics personalizes the OpenSim musculoskeletal model you provide to match your subject's capture data as closely as possible.
                    The OpenSim model you choose <b>must have markers whose names match the ones in the motion capture files you upload. </b>
                    It's ok if the model has more markers than the motion capture files, as additional markers will be ignored.
                </p>
                <p>
                    If you are not familiar with <a href="https://simtk.org/projects/opensim" rel="noreferrer" target="_blank">OpenSim</a>, a good default model is the <a href="https://simtk.org/projects/full_body" target="_blank" rel="noreferrer">Rajagopal 2016</a> model.
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
                disabled={props.readonly}
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
            //            let footErrorMessage = null;
            //            if (footBodyNames.length < 2) {
            //                footErrorMessage = (
            //                    <div className="invalid-feedback">
            //                        To fit dynamics to your data, please specify at least two body nodes that we can treat as "feet", and send ground reaction forces through.
            //                    </div>
            //                );
            //            }
            //            else if (footBodyNames.length > 2) {
            //                footErrorMessage = (
            //                    <div className="invalid-feedback">
            //                        Currently AddBiomechanics dynamics fitter only supports treating each foot as a single body segment. Please don't include multiple segments from each foot.
            //                    </div>
            //                );
            //            }

            formElements.push(<div key="feet" className="mb-3">
                <label>Specify Two Feet in Custom OpenSim Model:</label>
                <TagEditor
                    error={footBodyNames.length < 2}
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

            if (footBodyNames.length < 2) {
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
                    disabled={props.readonly}
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
                className={"form-control" + ((subjectDataSource === '') ? " border-primary border-2" : "")}
                autoFocus={subjectDataSource === ''}
                disabled={props.readonly}
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

        if (subjectDataSource === '') {
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
                className={"form-control" + ((subjectConsent === null) ? " border-primary border-2" : "") + ((subjectConsent === false) ? " border-danger border-2" : "")}
                autoFocus={subjectConsent == null}
                aria-describedby="consentHelp"
                disabled={props.readonly}
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
    // 1.12. Create the entry for citation ifo
    //    totalFormElements++;
    //    if (formCompleteSoFar) {
    //        formElements.push(<div key="citation" className="mb-3">
    //            <label>Desired Citation:</label>
    //            <textarea
    //                id="citation"
    //                value={subjectCitation == null ? "" : subjectCitation}
    //                className={"form-control" + ((subjectCitation == null) ? " border-primary border-2" : "")}
    //                autoFocus={subjectCitation == null || !subjectCitationComplete}
    //                aria-describedby="citeHelp"
    //                onKeyDown={(e) => {
    //                    if (e.key === 'Enter' || e.key === 'Tab') {
    //                        if (subjectCitation == null) {
    //                            subjectJson.setAttribute("citation", "");
    //                        }
    //                        setSubjectCitationComplete(true);
    //                        const input = e.target as HTMLInputElement;
    //                        input.blur();
    //                    }
    //                }}
    //                disabled={props.readonly}
    //                onFocus={() => {
    //                    subjectJson.onFocusAttribute("citation");
    //                }}
    //                onBlur={() => {
    //                    subjectJson.onBlurAttribute("citation");
    //                }}
    //                onChange={(e) => {
    //                    subjectJson.setAttribute("citation", e.target.value);
    //                }}>
    //            </textarea>
    //            <div id="citeHelp" className="form-text">How do you want this data to be cited?</div>
    //        </div>);
    //
    //        if (subjectCitation == null || !subjectCitationComplete) {
    //            if (subjectCitationComplete) {
    //                setSubjectCitationComplete(false);
    //            }
    //            formCompleteSoFar = false;
    //            formElements.push(<div key='citationConfirm'>
    //                <button type="button" className="btn btn-primary" onClick={() => setSubjectCitationComplete(true)}>Confirm Citation</button> (or press Enter or Tab)
    //            </div>);
    //            formElements.push(<div className="alert alert-dark mt-2" role="alert" key="citationExplanation">
    //                <h4 className="alert-heading">What should I put for my citation?</h4>
    //                <p>
    //                    It's fine to leave this blank, if you don't have a preferred citation. If you do, please include it here.
    //                </p>
    //                <p>
    //                    You can include your citation in any format you like, just note that this information is public.
    //                </p>
    //                <h5>IMPORTANT: NEVER INCLUDE PATIENT IDENTIFYING INFORMATION IN YOUR CITATION!</h5>
    //                <p>
    //                    Definitely do not put something like "Keenon Werling's gait data" in the citation field, unless
    //                    your subject has explicitly given informed consent to be identified and has requested that users
    //                    of the data cite them by name.
    //                </p>
    //            </div>);
    //        }
    //        else {
    //            completedFormElements++;
    //        }
    //    }
    if (subjectCitation !== null && subjectCitation !== "") {
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
                disabled={true}
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
            <div id="citeHelp" className="form-text">We are replacing citations for individual subjects with dataset citations. Please add a citation for the full dataset and remove the subject citations.</div>
            <button disabled={props.readonly} className="btn btn-warning" onClick={async (e) => {
                subjectJson.setAttribute("citation", "");
            }}>Remove Citation</button>
        </div>)
    };

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
        subjectState.markIncomplete()
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
        mocapFilesTable = <table className="table" style={{ width: '100%', overflow: 'hidden', tableLayout: 'fixed' }}>
            <thead>
                <tr>
                    <th scope="col" style={{ width: '100px', maxWidth: '30%' }}>Name</th>
                    <th scope="col">Marker and Forces Data</th>
                    <th scope="col">Tags</th>
                    <th scope="col" style={{ width: '100px' }}>Delete?</th>
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
                    if (trial.trcFileExists && !trial.c3dFileExists) {
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
                        <td align="right">
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
    if (!readyFlagExists && !props.readonly) {
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
        if (subjectState.canProcess()) {
            subjectState.markReadyForProcess()
            submitButton =
                <button className="btn btn-lg btn-primary mt-2" style={{ width: '100%' }} onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();

                    if (disableDynamics) {
                        alert(
                            'Looks like you uploaded GRF data (.mot) files, but you selected "Do not Fit Physics". GRF data will be ignored.'
                        );
                    }

                    subjectState.submitForProcessing();
                }}>Submit for Processing</button>;
        }
        else {
            subjectState.markIncomplete()
            submitButton = <div>
                <div>
                    <button className="btn btn-lg btn-primary mt-2" disabled style={{ width: '100%' }} onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        alert("Cannot submit for processing: Some trial(s) are missing markers. Please either upload marker data or detele trials.");
                    }}>Submit for Processing</button>
                </div>
                <div>
                    {subjectState.trials.length === 0 ? (
                        <span className="text-danger">Cannot submit for processing: There are no trials to process. Please upload marker data (trc or c3d).</span>
                    ) : (
                        <span className="text-danger">Cannot submit for processing: Some trial(s) are missing markers. Please either upload marker data (trc or c3d) or delete trials with missing markers.</span>
                    )}
                </div>
            </div>
        }
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

        subjectState.dropFilesToUpload(acceptedFiles, subjectState.trials.map(obj => obj.name)).then(excludedNames => {
        if (excludedNames.length > 0)
            alert("The following .mot files that you tried to upload have no .trc or .c3d file associated: " + excludedNames.map(name => name + ".mot").join(", ") + ". Please, assign the same name to associated .trc/.c3d and .mot files." );
        });
    };

    const handleFileSelect = () => {
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.multiple = true; // Allow multiple file selection
        fileInput.addEventListener('change', (event) => {
            const inputElement = event.target as HTMLInputElement;

            let acceptedFiles: File[] = [];
            if (inputElement.files) {
                const files = Array.from(inputElement.files);
                files.forEach((file) => {
                    acceptedFiles.push(file);
                });

                subjectState.dropFilesToUpload(acceptedFiles);
            }
        });
        fileInput.click();
    };

    let uploadTrialsDropZone = null;
    if (!props.readonly) {
        uploadTrialsDropZone = (
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
                }}
                onClick={handleFileSelect}>
                <div className="dz-message needsclick">
                    <i className="h3 text-muted dripicons-cloud-upload"></i>
                    <h5>
                        "Drop C3D or TRC files here to create trials. You can also drop MOT files, but they must have a TRC or C3D file associated (same name)."
                    </h5>
                    <span className="text-muted font-13">
                        (You can drop multiple files at once to create multiple
                        trials simultaneously)
                    </span>
                </div>
            </div>
        );
    }

    const trialsUploadSection = <>
        <h3>Motion Capture Files:</h3>
        {mocapFilesTable}
        {uploadTrialsDropZone}
        {submitButton}
        {mocapHelpText}
    </>;

    let statusSection = null;
    let errorsSection = null;
    let waitingForServer = false;
    if (readyFlagExists) {
        if (errorFlagExists) {

            let guessedError = <li>
                <p>
                    <strong>{subjectState.parsedErrorsJson.type} - </strong>
                    {parseLinks(subjectState.parsedErrorsJson.message)}
                </p>
                <p>
                    {parseLinks(subjectState.parsedErrorsJson.original_message)}
                </p>
            </li>

            if (Object.keys(subjectState.parsedErrorsJson).length > 0) {
                errorsSection = <div>
                    <h3>Status: <div className="badge bg-danger ">Error</div></h3>
                    <div className="alert alert-danger my-2">
                        <h4><i className="mdi mdi-alert me-2 vertical-middle"></i>  Detected errors while processing the data!</h4>
                        <p>
                            There were some errors while processing the data. See our <a href="https://addbiomechanics.org/instructions.html" target="_blank" rel="noreferrer">Tips and Tricks page</a> for more suggestions, ask a question in our <a href="https://simtk.org/plugins/phpBB/indexPhpbb.php?group_id=2402" target="_blank" rel="noreferrer">Forum</a> or submit an issue to our <a href="https://github.com/keenon/AddBiomechanics/issues" target="_blank" rel="noreferrer">GitHub Repository</a>.
                        </p>
                        <hr />
                        <ul>
                            {guessedError}
                        </ul>
                        <hr />
                        <p>
                            Please, fix the errors and update your data and/or your OpenSim Model and Markerset and then hit "Reprocess" (below in blue) to fix the problem.
                        </p>
                        <button className="btn btn-secondary" onClick={() => setShowLog(!showLog)}>
                            {showLog ? "Hide Processing Log" : "Show Processing Log"}
                        </button>
                        {showLog && (
                            <pre className="alert alert-light my-2">
                                {subjectState.logText}
                            </pre>
                        )}
                    </div>
                </div>;
            }

            if (!props.readonly) {
                statusSection = <div>
                    <button className="btn btn-primary" onClick={async (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        return subjectState.reprocess();
                    }}>Reprocess</button>
                </div>;
            }
            else {
                statusSection = <div>
                    <h3>Status: <div className="badge bg-danger ">Error</div></h3>
                    <h3>Processing log contents:</h3>
                    <pre>
                        {subjectState.logText}
                    </pre>
                </div>;
            }
        }
        else if (resultsExist) {
            let reprocessButton = null;
            if (!props.readonly) {
                reprocessButton = (
                    <p>
                        <button className="btn btn-warning" onClick={async (e) => {
                            if (window.confirm("Are you sure you want to reprocess the data? That will delete your current results.")) {
                                e.preventDefault();
                                e.stopPropagation();
                                await subjectState.reprocess();
                            }
                        }}>Reprocess</button>
                    </p>
                );
            }
            statusSection = <>
                <div className='row mt-2'>
                    <h3>Status: <div className="badge bg-success ">Finished!</div></h3>
                </div>
                <div className='row'>
                    <div className='col-md-12'>
                        <p>
                            <button className="btn btn-primary" onClick={async (e) => {
                                var t_id = showToast("Preparing download of results in OpenSim format....", "info", "Download", toast.POSITION.BOTTOM_CENTER, false)
                                props.home.dir.downloadFile(subjectState.resultsOsimZipPath, "", false, t_id);

                            }}>Download Results, OpenSim Format</button>
                        </p>
                        <p>
                            <button className="btn btn-primary" onClick={async (e) => {
                                var t_id = showToast("Preparing download of results in B3D format....", "info", "Download", toast.POSITION.BOTTOM_CENTER, false)
                                props.home.dir.downloadFile(subjectState.resultsB3dPath, "", false, t_id);
                            }}>Download Results, B3D Format</button>
                        </p>
                        <p>
                            <button className="btn btn-secondary" onClick={async (e) => {
                                var t_id = showToast("Preparing download of log file....", "info", "Download", toast.POSITION.BOTTOM_CENTER, false)
                                props.home.dir.downloadFile(subjectState.logPath, "", false, t_id);
                            }}>Download Processing Logs</button>
                        </p>
                        {reprocessButton}
                    </div>
                </div>
            </>;
        }
        else if (processingFlagExists) {
            if (!props.readonly) {
                statusSection = <div>
                    <h3>Status: <div className="badge bg-warning ">Processing</div></h3>
                    <button className="btn btn-primary" onClick={async (e) => {
                        if (window.confirm("Are you sure you want to force the reprocessing of your data? If it is still processing, this may result in double-processing the same data.")) {
                            e.preventDefault();
                            e.stopPropagation();
                            await subjectState.reprocess();
                        }
                    }}>Force Reprocess</button>
                </div>;
            }
            else {
                statusSection = <div>
                    <h3>Status: <div className="badge bg-warning ">Processing</div></h3>
                </div>;
            }
        }
        else if (slurmFlagExists) {
            if (!props.readonly) {
                statusSection = <div>
                    <h3>Status: <div className="badge bg-warning ">Queued on <a href="https://www.sherlock.stanford.edu/docs/" target="_blank" rel="noreferrer">Sherlock</a></div></h3>
                    <button className="btn btn-primary" onClick={async (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        if (window.confirm("Are you sure you want to force the reprocessing of your data? If it is still processing, this may result in double-processing the same data.")) {
                            e.preventDefault();
                            e.stopPropagation();
                            await subjectState.reprocess();
                        }
                    }}>Force Reprocess</button>
                </div>;
            }
            else {
                statusSection = <div>
                    <h3>Status: <div className="badge bg-warning ">Queued on <a href="https://www.sherlock.stanford.edu/docs/" target="_blank" rel="noreferrer">Sherlock</a></div></h3>
                </div>;
            }
        }
        else {
            waitingForServer = true

            statusSection = <>
                <button className="btn btn-primary" onClick={async (e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    if (window.confirm("Are you sure you want to force the reprocessing of your data? If it is still processing, this may result in double-processing the same data.")) {
                        e.preventDefault();
                        e.stopPropagation();
                        await subjectState.reprocess();
                    }
                }}>Force Reprocess</button>
                <div>
                    <h3>Status: <div className="badge bg-secondary">Waiting for server</div></h3>
                </div>
            </>;
        }

        if (readyFlagExists || incompleteSubjectFlagExists || processingFlagExists || slurmFlagExists || waitingForServer) {
            // Check if flags were created less than 6 hours ago.
            let possibleProcessingProblem = false

            let readyFlagFileModified = readyFlagFile.metadata?.lastModified
            let processingFlagFileModified = processingFlagFile.metadata?.lastModified
            let slurmFlagFileModified = slurmFlagFile.metadata?.lastModified
            let aDayAgo = new Date()
            aDayAgo.setHours(new Date().getHours() - 24);
            const pacificTimeOptions = { timeZone: 'America/Los_Angeles' };
            aDayAgo = new Date(aDayAgo.toLocaleString('en-US', pacificTimeOptions));

            if (readyFlagExists && !incompleteSubjectFlagExists && !resultsExist && !errorFlagExists && !processingFlagExists && !slurmFlagExists) {
                if (readyFlagFileModified) {
                    possibleProcessingProblem = readyFlagFileModified < aDayAgo
                    console.log(readyFlagFileModified)
                    console.log(readyFlagFileModified < aDayAgo)
                }
                console.log("READY")
                console.log(readyFlagFileModified)
                console.log(aDayAgo)
            }

            if (processingFlagExists && !resultsExist && !errorFlagExists) {
                if (processingFlagFileModified) {
                    possibleProcessingProblem = processingFlagFileModified < aDayAgo
                    console.log(processingFlagFileModified < aDayAgo)
                }
                console.log("PROCESSING")
                console.log(processingFlagFileModified)
                console.log(aDayAgo)
            }

            if (slurmFlagExists && !resultsExist && !errorFlagExists) {
                if (slurmFlagFileModified) {
                    possibleProcessingProblem = slurmFlagFileModified < aDayAgo
                    console.log(slurmFlagFileModified < aDayAgo)
                }
                console.log("SLURM")
                console.log(slurmFlagFileModified)
                console.log(aDayAgo)
            }

            if (possibleProcessingProblem)
                showToast("Your data is taking too much time to process. Please click on reprocess to try again.", "warning", "reprocess", toast.POSITION.BOTTOM_CENTER, false)
            else if (!resultsExist && !errorFlagExists)
                showToast("Your data is being processed. Please come back later", "info", "processing", toast.POSITION.BOTTOM_CENTER, false)

        }
    }

    let resultsSection = null;
    if (resultsExist) {
        let reviewControls = null;
        if (!props.readonly) {
            reviewControls = <div>
                <h3>Bulk Review Actions:</h3>
                <div>
                    <button className="btn btn-success mt-2" onClick={async (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        await subjectState.markAllTrialsReviewed();
                    }}>Mark All Reviewed</button>
                </div>
                <div>
                    <button className="btn btn-warning mt-2" onClick={async (e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        await subjectState.markAllTrialsUnreviewed();
                    }}>Mark All Unreviewed</button>
                </div>
                <div>
                    {subjectJson.getAttribute("showReviewedWarnings", false) ? (
                        <button className="btn btn-info mt-2 mb-2" onClick={
                            () => {
                                subjectJson.setAttribute("showReviewedWarnings", false)
                            }}>Hide Reviewed Warnings</button>
                    ) : (
                        <button className="btn btn-info mt-2" onClick={
                            () => {
                                subjectJson.setAttribute("showReviewedWarnings", true)
                            }}>Show Reviewed Warnings</button>
                    )}
                </div>
            </div>;
        }

        resultsSection = <div>
            <h3>Results:</h3>
            <table className="table">
                <thead>
                    <tr>
                        <th scope="col">Trial Segment</th>
                        <th scope="col">Marker Status</th>
                        <th scope="col">Forces Status</th>
                        <th scope="col">Reviewed?</th>
                    </tr>
                </thead>
                <tbody>
                    {
                        subjectState.trials.flatMap((trial) => {
                            if (trial.name in subjectState.parsedResultsJson) {
                                const trialResults = subjectState.parsedResultsJson[trial.name];

                                return trial.segments.map((segment, index) => {
                                    let hasErrors = false;

                                    // console.log(segment.path + + " " + index + " " + trialResults.segments[index].start + " " + trialResults.segments[index].end)

                                    if (!('segments' in trialResults) || trialResults.segments.length <= index) {
                                        return <tr key={segment.path} className='table-danger'>
                                            <td><button className="btn btn-dark" onClick={() => {
                                                navigate(Session.getDataURL(props.currentLocationUserId, segment.path));
                                            }}>
                                                View (Error) Segment
                                            </button></td>
                                            <td><span className='text-danger'>Error</span></td>
                                            <td><span className='text-danger'>Error</span></td>
                                            <td><span className='text-danger'>Error</span></td>
                                        </tr>
                                    }

                                    const segmentResults = trialResults.segments[index];
                                    let kinematicsResults: string | React.ReactFragment = '';
                                    if (segmentResults.kinematicsStatus === 'FINISHED') {
                                        kinematicsResults = (segmentResults.kinematicsAvgRMSE == null ? 'NaN' : (segmentResults.kinematicsAvgRMSE * 100).toFixed(2)) + ' cm RMSE';
                                    }
                                    else if (segmentResults.kinematicsStatus === 'ERROR') {
                                        hasErrors = true;
                                        kinematicsResults = <span className='text-danger'><b>Error</b> {segmentResults.errorMsg}</span>;
                                    }
                                    else if (segmentResults.kinematicsStatus === 'NOT_STARTED') {
                                        kinematicsResults = 'Not run';
                                    }

                                    let dynamicsResults: string | React.ReactFragment = '';
                                    if (segmentResults.dynamicsStatus === 'FINISHED') {
                                        dynamicsResults = (segmentResults.linearResiduals == null ? 'NaN' : segmentResults.linearResiduals.toFixed(2)) + ' N, ' + (segmentResults.angularResiduals == null ? 'NaN' : segmentResults.angularResiduals.toFixed(2)) + ' Nm';
                                    }
                                    else if (segmentResults.dynamicsStatus === 'ERROR') {
                                        hasErrors = true;
                                        dynamicsResults = <span className='text-danger'>Error</span>;
                                    }
                                    else if (segmentResults.dynamicsStatus === 'NOT_STARTED') {
                                        dynamicsResults = 'Not run';
                                    }

                                    let reviewStatus: string | React.ReactFragment = '';
                                    if (segment.reviewFlagExists) {
                                        reviewStatus = <span className='badge bg-success'>Reviewed</span>;
                                        if (!props.readonly) {
                                            reviewStatus = <label className='badge bg-success' style={{ cursor: 'pointer' }}>
                                                Reviewed
                                                <input
                                                    type="checkbox"
                                                    onClick={handleCheckboxChange(segment)}
                                                    checked={segment.reviewFlagExists}
                                                    style={{ marginLeft: '10px' }}
                                                />
                                            </label>
                                        }
                                    }
                                    else if (!segment.loading) {
                                        reviewStatus = <><span className='badge bg-warning'>Needs Review
                                        </span></>
                                        if (!props.readonly) {
                                            reviewStatus = <label className='badge bg-warning' style={{ cursor: 'pointer' }}>
                                                Needs Review
                                                <input
                                                    type="checkbox"
                                                    onClick={handleCheckboxChange(segment)}
                                                    checked={segment.reviewFlagExists}
                                                    style={{ marginLeft: '10px' }}
                                                />
                                            </label>
                                        }
                                    }
                                    else {
                                        reviewStatus = <span className='badge bg-secondary'>Loading</span>;
                                    }

                                    if (hasErrors) {
                                        return <tr key={segment.path} className='table-danger'>
                                            <td><button className="btn btn-dark" onClick={() => {
                                                navigate(Session.getDataURL(props.currentLocationUserId, segment.path));
                                            }}>
                                                View Error Results "{trial.name}" {segmentResults.start.toFixed(2)}s to {segmentResults.end.toFixed(2)}s
                                            </button></td>
                                            <td>{kinematicsResults}</td>
                                            <td>{dynamicsResults}</td>
                                            <td>{reviewStatus}</td>
                                        </tr>
                                    }

                                    let hasWarnings = false;
                                    let errorMsg = ''
                                    if (segmentResults.hasMarkerWarnings) {
                                        hasWarnings = true;
                                        errorMsg = "We've identified warnings in your code regarding your markers. We're actively developing more detailed warnings, which will be included in the next release."
                                    }

                                    if (hasWarnings) {
                                        //                                        return <tr key={segment.path} className='table-warning' style={{display: isHiddenCheckboxWarning(String(trial.name + "_" + segment.name)) ? "none" : "table-row"}}>
                                        return <tr key={segment.path} className='table-warning' style={{ display: subjectJson.getAttribute("showReviewedWarnings", false) || !segment.reviewFlagExists ? "table-row" : "none" }}>
                                            <td><button className="btn btn-dark" onClick={() => {
                                                navigate(Session.getDataURL(props.currentLocationUserId, segment.path));
                                            }}>
                                                View Error Results "{trial.name}" {segmentResults.start.toFixed(2)}s to {segmentResults.end.toFixed(2)}s
                                            </button></td>
                                            <td>{errorMsg}</td>
                                            <td>{dynamicsResults}</td>
                                            <td>{reviewStatus}</td>
                                        </tr>
                                    }


                                    else {
                                        return <tr key={segment.path}>
                                            <td><button className="btn btn-primary" onClick={() => {
                                                navigate(Session.getDataURL(props.currentLocationUserId, segment.path));
                                            }}>
                                                View "{trial.name}" {segmentResults.start.toFixed(2)}s to {segmentResults.end.toFixed(2)}s
                                            </button></td>
                                            <td>{kinematicsResults}</td>
                                            <td>{dynamicsResults}</td>
                                            <td>{reviewStatus}</td>
                                        </tr>
                                    }
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
            {reviewControls}
        </div>
    }

    return <div className='container'>
        {subjectForm}
        {trialsUploadSection}
        {errorsSection}
        {statusSection}
        {resultsSection}
    </div>
});

export default SubjectView;
