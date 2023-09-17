import React, { useEffect, useRef, useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { Table, Button, ProgressBar, Form } from "react-bootstrap";
import { observer } from "mobx-react-lite";
import UserHomeDirectory, { SubjectContents, TrialSegmentContents } from "../../model/UserHomeDirectory";
import DropFile from "../../components/DropFile";
import TagEditor from '../../components/TagEditor';
import Session from "../../model/Session";
import { Link } from "react-router-dom";
import { getOpenSimBodyList } from "../../model/OpenSimUtils";
import LiveJsonFile from "../../model/LiveJsonFile";

type SubjectViewProps = {
    home: UserHomeDirectory;
    currentLocationUserId: string;
    path: string;
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

    // Check on the value of the key _subject.json attributes unconditionally, to ensure that MobX updates if the attributes change
    const subjectHeightM: number = subjectJson.getAttribute("heightM", "");
    const [subjectHeightComplete, setSubjectHeightComplete] = useState(true);
    const subjectMassKg: number = subjectJson.getAttribute("massKg", "");
    const [subjectMassComplete, setSubjectMassComplete] = useState(true);
    const subjectSex: '' | 'male' | 'female' | 'unknown' = subjectJson.getAttribute("sex", "");
    const subjectAgeYears: number = subjectJson.getAttribute("ageYears", "");
    const [subjectAgeComplete, setSubjectAgeComplete] = useState(true);
    const subjectModel: '' | 'custom' | 'vicon' | 'cmu' = subjectJson.getAttribute("model", "");
    const disableDynamics: boolean | null = subjectJson.getAttribute("disableDynamics", null);
    const footBodyNames = subjectJson.getAttribute("footBodyNames", []);
    const runMoco: boolean | null = subjectJson.getAttribute("runMoco", null);

    const customOpensimModelPathData = home.getPath(path + "/unscaled_generic.osim", false);
    const [availableBodyList, setAvailableBodyList] = useState<string[]>([]);
    useEffect(() => {
        if (customOpensimModelPathData.files.length > 0) {
            home.dir.downloadText(path + '/unscaled_generic.osim').then((openSimText) => {
                setAvailableBodyList(getOpenSimBodyList(openSimText));
            });
        }
    }, [subjectModel, customOpensimModelPathData.files]);

    // Check on the existence of each flag unconditionally, to ensure that MobX updates if the flags change
    const readyFlagExists = readyFlagFile.exists && !readyFlagFile.loading;
    const processingFlagExists = processingFlagFile.exists && !processingFlagFile.loading;

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
                className={"form-control" + ((subjectSex == '') ? " border-primary border-2" : "")}
                autoFocus={subjectSex == ''}
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

        if (subjectSex == '') {
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
                className={"form-control" + ((subjectAgeYears == 0 || !subjectAgeComplete) ? " border-primary border-2" : "")}
                aria-describedby="ageHelp"
                value={subjectAgeYears}
                autoFocus={subjectAgeYears != 0 || !subjectAgeComplete}
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

        if (subjectAgeYears == 0 || !subjectAgeComplete) {
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
                    subjectJson.setAttribute("model", e.target.value);
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
                    If you are not familiar with <a href="https://simtk.org/projects/opensim" target="_blank">OpenSim</a>, a good default model is the <a href="https://simtk.org/projects/full_body" target="_blank">Rajagopal 2016</a> model.
                    We offer a Rajagopal 2016 model with a few different common markersets as a convenience, if you don't want to upload your own model.
                    <ul>
                        <li>The <a href="https://simtk.org/projects/full_body" target="_blank">Rajagopal 2016</a> model with a <a href="https://docs.vicon.com/download/attachments/133828966/Plug-in%20Gait%20Reference%20Guide.pdf?version=2&modificationDate=1637681079000&api=v2" target="_blank">standard Vicon markerset</a></li>
                        <li>The <a href="https://simtk.org/projects/full_body" target="_blank">Rajagopal 2016</a> model with a <a href="http://mocap.cs.cmu.edu/markerPlacementGuide.pdf" target="_blank">CMU markerset</a></li>
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
                    return home.dir.uploadFile(customOpensimModelPathData.path, file, progressCallback);
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

    let subjectForm = <Form onSubmit={(e) => {
        e.preventDefault();
        e.stopPropagation();
    }}>
        {formElements}
        <hr />
        <ProgressBar now={completedFormElements} max={totalFormElements} />
        <p>
            {completedFormElements} of {totalFormElements} fields complete.
        </p>
    </Form>;

    /*
    const uploadPath = path + "/test.c3d";
    const pathData = home.getPath(uploadPath, false);
    const uploadTest = (
        <div>
            <DropFile
                pathData={pathData}
                accept=".c3d"
                upload={(file: File, progressCallback: (progress: number) => void) => {
                    if (home == null) {
                        throw new Error("No directory");
                    }
                    return home.dir.uploadFile(uploadPath, file, progressCallback);
                }}
                download={() => {
                    if (home == null) {
                        throw new Error("No directory");
                    }
                    // dir.downloadFile(uploadPath);
                    console.log("Download TODO");
                }}
                required={false} />
        </div>
    );
    */

    let trialsView = null;
    if (formCompleteSoFar) {
        trialsView = <>
            <h2>Trials:</h2>
            <ul>
                {subjectContents.trials.map(({ name, path }) => {
                    return <li key={name}>Trial: <Link to={Session.getDataURL(props.currentLocationUserId, path)}>{name}</Link></li>;
                })}
            </ul>
        </>;
    }

    return <div className='container'>
        {subjectForm}
        {trialsView}
    </div>
});

export default SubjectView;