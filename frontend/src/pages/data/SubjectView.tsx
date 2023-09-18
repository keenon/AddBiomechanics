import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Table, Button, ProgressBar, Form, Collapse } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import UserHomeDirectory, { SubjectContents, TrialSegmentContents } from "../../model/UserHomeDirectory";
import DropFile from "../../components/DropFile";
import TagEditor from '../../components/TagEditor';
import Session from "../../model/Session";
import { Link } from "react-router-dom";
import { getOpenSimBodyList } from "../../model/OpenSimUtils";
import Dropzone from "react-dropzone";

type SubjectViewProps = {
    home: UserHomeDirectory;
    currentLocationUserId: string;
    path: string;
};

type SegmentResultsJSON = {
    trialName: string;
    start_frame: number;
    start: number;
    end_frame: number;
    end: number;
    kinematicsStatus: "NOT_STARTED" | "FINISHED" | "ERROR";
    kinematicsAvgRMSE: number;
    kinematicsAvgMax: number;
};

type TrialResultsJSON = {
    segments: SegmentResultsJSON[]
};

type SubjectResultsJSON = {
    [trialName: string]: TrialResultsJSON
};

const SubjectView = observer((props: SubjectViewProps) => {
    const location = useLocation();
    const navigate = useNavigate();
    const home = props.home;
    const path = props.path;

    const subjectContents: SubjectContents = home.getSubjectContents(path);
    const subjectJson = subjectContents.subjectJson;
    const readyFlagFile = subjectContents.readyFlagFile;
    const processingFlagFile = subjectContents.processingFlagFile;
    const errorFlagFile = subjectContents.errorFlagFile;

    // Check on the value of the key _subject.json attributes unconditionally, to ensure that MobX updates if the attributes change
    const subjectConsent: boolean | null = subjectJson.getAttribute("subjectConsent", null);
    const subjectHeightM: number = subjectJson.getAttribute("heightM", "");
    const [subjectHeightComplete, setSubjectHeightComplete] = useState(true);
    const subjectMassKg: number = subjectJson.getAttribute("massKg", "");
    const [subjectMassComplete, setSubjectMassComplete] = useState(true);
    const subjectSex: '' | 'male' | 'female' | 'unknown' = subjectJson.getAttribute("sex", "");
    const subjectAgeYears: number = subjectJson.getAttribute("ageYears", "");
    const [subjectAgeComplete, setSubjectAgeComplete] = useState(true);
    const subjectModel: '' | 'custom' | 'vicon' | 'cmu' = subjectJson.getAttribute("skeletonPreset", "");
    const disableDynamics: boolean | null = subjectJson.getAttribute("disableDynamics", null);
    const footBodyNames = subjectJson.getAttribute("footBodyNames", []);
    const runMoco: boolean | null = subjectJson.getAttribute("runMoco", null);

    // Get the details we'll need for custom OpenSim models unconditionaly, to ensure that MobX updates if the attributes change
    const pathWithSlash = path + (path.endsWith('/') ? '' : '/');
    const customOpensimModelPathData = home.getPath(pathWithSlash + "unscaled_generic.osim", false);
    const [availableBodyList, setAvailableBodyList] = useState<string[]>([]);
    useEffect(() => {
        if (!customOpensimModelPathData.loading && customOpensimModelPathData.files.length > 0) {
            home.dir.downloadText(customOpensimModelPathData.path).then((openSimText) => {
                setAvailableBodyList(getOpenSimBodyList(openSimText));
            }).catch((e) => {
                console.error("Error downloading OpenSim model text from " + customOpensimModelPathData.path + ": ", e);
            });
        }
    }, [subjectModel, customOpensimModelPathData.files, customOpensimModelPathData.loading]);

    // This allows us to have bulk-uploading of files from the drag and drop interface
    const [uploadFiles, setUploadFiles] = useState({} as { [key: string]: File; });

    // Check on the existence of each flag unconditionally, to ensure that MobX updates if the flags change
    const resultsExist = subjectContents.resultsExist;
    const readyFlagExists = readyFlagFile.exists && !readyFlagFile.loading;
    const errorFlagExists = errorFlagFile.exists && !errorFlagFile.loading;
    const processingFlagExists = processingFlagFile.exists && !processingFlagFile.loading;

    // Create state to manage the collapse state of the wizard
    const [wizardCollapsed, setWizardCollapsed] = useState(readyFlagExists);

    // Manage the results JSON blob
    const [parsedResultsJSON, setParsedResultsJSON] = useState<SubjectResultsJSON>({});
    useEffect(() => {
        if (resultsExist) {
            home.dir.downloadText(path + "/_results.json").then((resultsText) => {
                setParsedResultsJSON(JSON.parse(resultsText));
            }).catch((e) => {
                console.error("Error downloading _results.json from " + path + ": ", e);
            });
        }
    }, [resultsExist]);

    /////////////////////////////////////////////////////////////////////////
    // There are several states a subject can be in:
    // 0. Still loading, we're not sure what state we're in yet.
    // 1. Just created, so _subject.json is missing values or there are no trials. In this case, we want to show a wizard.
    // 2. User has indicated processing is ready, but we haven't finished processing yet. In this case, we want to show a status page.
    // 3. Processing finished, in which case we want to show results on the subject page.
    /////////////////////////////////////////////////////////////////////////

    // 0. We're still loading
    if (subjectContents.loading || subjectJson.isLoadingFirstTime() || readyFlagFile.loading || processingFlagFile.loading) {
        return <div>Loading...</div>;
    }

    // 1. Create a wizard form for the _subject.json values, populated to the point in the journey that the user has reached.
    let formElements: JSX.Element[] = [
        <div key="title">
            <h3>Subject {subjectContents.name} Metrics:</h3>
        </div>
    ];
    let formCompleteSoFar: boolean = true;
    let completedFormElements: number = 0;
    let totalFormElements: number = 0;

    //////////////////////////////////////////////////////////////////
    // 1.0. Create the entry for checking if the subject consented to have their data uploaded
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
            formElements.push(<div>
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
            formElements.push(<div>
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
                className={"form-control" + ((subjectAgeYears === 0 || !subjectAgeComplete) ? " border-primary border-2" : "")}
                aria-describedby="ageHelp"
                value={subjectAgeYears}
                autoFocus={subjectAgeYears === 0 || !subjectAgeComplete}
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

        if (subjectAgeYears === 0 || !subjectAgeComplete) {
            if (subjectAgeComplete) {
                setSubjectAgeComplete(false);
            }
            formCompleteSoFar = false;
            formElements.push(<div>
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
                <DropFile pathData={customOpensimModelPathData} accept=".osim" upload={(file, progressCallback) => {
                    return home.dir.uploadFile(customOpensimModelPathData.path, file, progressCallback).then(() => {
                        home.dir.downloadText(customOpensimModelPathData.path).then((openSimText) => {
                            setAvailableBodyList(getOpenSimBodyList(openSimText));
                        }).catch((e) => {
                            console.error("Error downloading OpenSim model text from " + customOpensimModelPathData.path + ": ", e);
                        });
                    });
                }} download={() => {
                    return home.dir.downloadFile(customOpensimModelPathData.path);
                }}></DropFile>
                <div id="customModelHelp" className="form-text">Custom OpenSim file to scale for the subject.</div>
            </div>);

            if (customOpensimModelPathData.files.length === 0) {
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
                    tagSet={availableBodyList}
                    tags={footBodyNames}
                    readonly={false}
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
                formElements.push(<div className="alert alert-dark mt-2" role="alert" key="modelExplanation">
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
                formElements.push(<div className="alert alert-dark mt-2" role="alert" key="modelExplanation">
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

    let mocapFilesTable = null;
    if (subjectContents.trials.length > 0) {
        mocapFilesTable = <table className="table">
            <thead>
                <tr>
                    <th scope="col">Name</th>
                    <th scope="col" colSpan={disableDynamics ? 1 : 2}>Marker {disableDynamics ? '' : ' and Forces'} Data</th>
                    <th scope="col">Delete?</th>
                </tr>
            </thead>
            <tbody>
                {subjectContents.trials.map((trial) => {
                    const uploadMarkerFile = (file: File, progressCallback: (progress: number) => void) => {
                        if (file.name.endsWith('.c3d')) {
                            return home.dir.uploadFile(trial.c3dFilePath, file, progressCallback).then(() => {
                                // Delete the old TRC file, if there is one
                                if (trial.trcFileExists) {
                                    return home.dir.delete(trial.trcFilePath);
                                }
                                else {
                                    return Promise.resolve();
                                }
                            });
                        }
                        else if (file.name.endsWith('.trc')) {
                            return home.dir.uploadFile(trial.trcFilePath, file, progressCallback).then(() => {
                                // Delete the old C3D file, if there is one
                                if (trial.c3dFileExists) {
                                    return home.dir.delete(trial.c3dFilePath);
                                }
                                else {
                                    return Promise.resolve();
                                }
                            });
                        }
                        else {
                            return Promise.reject("Unsupported marker file type");
                        }
                    };

                    let dataFiles = [];
                    let uploadOnMount: File | undefined = uploadFiles[trial.name];
                    if (!trial.c3dFileExists && !trial.trcFileExists) {
                        const trialC3dPathData = home.getPath(trial.c3dFilePath, false);
                        dataFiles.push(
                            <td key='c3d' colSpan={disableDynamics ? 1 : 2}>
                                <DropFile pathData={trialC3dPathData} accept=".c3d,.trc" upload={uploadMarkerFile} download={() => {
                                    return home.dir.downloadFile(trialC3dPathData.path);
                                }} uploadOnMount={uploadOnMount} />
                            </td>
                        );
                    }
                    else if (trial.c3dFileExists) {
                        const trialC3dPathData = home.getPath(trial.c3dFilePath, false);
                        dataFiles.push(
                            <td key='c3d' colSpan={disableDynamics ? 1 : 2}>
                                <DropFile pathData={trialC3dPathData} accept=".c3d,.trc" upload={uploadMarkerFile} download={() => {
                                    return home.dir.downloadFile(trialC3dPathData.path);
                                }} uploadOnMount={uploadOnMount} />
                            </td>
                        );
                    }
                    else {
                        // Then the TRC file must exist
                        const trialTrcPathData = home.getPath(trial.trcFilePath, false);
                        dataFiles.push(
                            <td>
                                <DropFile pathData={trialTrcPathData} accept=".trc,.c3d" upload={uploadMarkerFile} download={() => {
                                    return home.dir.downloadFile(trialTrcPathData.path);
                                }} uploadOnMount={uploadOnMount} />
                            </td>
                        );
                        if (!disableDynamics) {
                            const trialGrfMotPathData = home.getPath(trial.grfMotFilePath, false);
                            dataFiles.push(
                                <td>
                                    <DropFile pathData={trialGrfMotPathData} accept=".mot" text="GRF *.mot file" upload={(file, progressCallback) => {
                                        return home.dir.uploadFile(trialGrfMotPathData.path, file, progressCallback);
                                    }} download={() => {
                                        return home.dir.downloadFile(trialGrfMotPathData.path);
                                    }} />
                                </td>
                            );
                        }
                    }


                    return <tr key={trial.name}>
                        <td>{trial.name}</td>
                        {dataFiles}
                        <td><button className="btn btn-dark" onClick={(e) => {
                            e.preventDefault();
                            e.stopPropagation();
                            if (window.confirm("Are you sure you want to delete trial \"" + trial.name + "\"?")) {
                                home.deleteFolder(trial.path);
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
            <button className="btn btn-lg btn-primary mt-2" disabled={subjectContents.trials.length === 0} style={{ width: '100%' }} onClick={(e) => {
                e.preventDefault();
                e.stopPropagation();
                readyFlagFile.upload().then(() => {
                    setWizardCollapsed(true);
                });
            }}>Submit for Processing</button>;
    }

    const trialsUploadSection = <>
        <h3>Motion Capture Files:</h3>
        {mocapFilesTable}
        <Dropzone
            {...props}
            accept=".c3d,.trc"
            onDrop={(acceptedFiles: File[]) => {
                let trialNames: string[] = [];

                let updatedUploadFiles = { ...uploadFiles };
                for (let i = 0; i < acceptedFiles.length; i++) {
                    const name = acceptedFiles[i].name.split('.')[0];
                    trialNames.push(name);
                    updatedUploadFiles[name] = acceptedFiles[i];
                }
                setUploadFiles(updatedUploadFiles);

                trialNames.forEach((name) => {
                    props.home.createTrial(path, name);
                });
            }}
        >
            {({ getRootProps, getInputProps, isDragActive }) => {
                const rootProps = getRootProps();
                const inputProps = getInputProps();
                return <div className={"dropzone" + (isDragActive ? ' dropzone-hover' : '')} {...rootProps}>
                    <div className="dz-message needsclick">
                        <input {...inputProps} />
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
            }}
        </Dropzone>
        {submitButton}
        {mocapHelpText}
    </>;

    let statusSection = null;
    if (readyFlagExists) {
        if (errorFlagExists) {
            statusSection = <div>
                <h3>Status: Error</h3>
                <button className="btn btn-primary" onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    errorFlagFile.delete();
                    processingFlagFile.delete();
                }}>Reprocess</button>
            </div>;
        }
        else if (resultsExist) {
            statusSection = <div>
                <h3>Status: Finished!</h3>
            </div>;
        }
        else if (processingFlagExists) {
            statusSection = <div>
                <h3>Status: Processing</h3>
                <button className="btn btn-primary" onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    processingFlagFile.delete();
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
        const trialNames: string[] = subjectContents.trials.map((trial) => trial.name);

        resultsSection = <div>
            <h3>Results:</h3>
            <table className="table">
                <thead>
                    <tr>
                        <th scope="col">Trial Segment</th>
                        <th scope="col">Kinematics Error</th>
                        <th scope="col">Dynamics Error</th>
                    </tr>
                </thead>
                <tbody>
                    {
                        subjectContents.trials.flatMap((trial) => {
                            if (trial.name in parsedResultsJSON) {
                                const trialResults = parsedResultsJSON[trial.name];
                                return trial.segments.map((segment, index) => {
                                    const segmentResults = trialResults.segments[index];
                                    return <tr key={segment.path}>
                                        <td><Link to={Session.getDataURL(props.currentLocationUserId, segment.path)}>{trial.name} {segmentResults.start}s to {segmentResults.end}s</Link></td>
                                        <td>{segmentResults.kinematicsAvgRMSE == null ? 'NaN' : segmentResults.kinematicsAvgRMSE.toFixed(2)} cm RMSE</td>
                                        <td>Did not run</td>
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