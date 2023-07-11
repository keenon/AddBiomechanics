import React, { useEffect, useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { observer } from "mobx-react-lite";
import "./MocapView.scss";
import {
  Button,
  ButtonGroup,
  Dropdown,
  Spinner,
  Table,
  OverlayTrigger,
  Tooltip,
  Form
} from "react-bootstrap";
import DropFile from "../../components/DropFile";
import Dropzone from "react-dropzone";
import MocapTrialModal from "./MocapTrialModal";
import MocapLogModal from "./MocapLogModal";
import MocapTagModal from "./MocapTagModal";
import MocapS3Cursor from '../../state/MocapS3Cursor';
import TagEditor from '../../components/TagEditor';
import { attachEventProps } from "@aws-amplify/ui-react/lib-esm/react-component-lib/utils";
import { AnyMessageParams } from "yup/lib/types";
import { parseLinks } from "../../utils"

type ProcessingResultsJSON = {
  autoAvgMax: number;
  autoAvgRMSE: number;
  goldAvgMax: number;
  goldAvgRMSE: number;
};

type MocapTrialRowViewProps = {
  index: number;
  name: string;
  cursor: MocapS3Cursor;
  showViewerHint: boolean;
  hideViewerHint: () => void;
  uploadC3D: File | undefined;
  uploadTRC: File | undefined;
  uploadGRF: File | undefined;
  uploadIK: File | undefined;
  onMultipleManualIK: (files: File[]) => void;
  onMultipleGRF: (files: File[]) => void;
};



const MocapTrialRowView = observer((props: MocapTrialRowViewProps) => {
  const navigate = useNavigate();
  let manualIKRow = null;
  if (props.cursor.getShowValidationControls()) {
    manualIKRow = (
      <td>
        <DropFile cursor={props.cursor} text={"Gold IK, *.mot or *.sto"} path={"trials/" + props.name + "/manual_ik.mot"} uploadOnMount={props.uploadIK} accept=".mot,.sto" onMultipleFiles={props.onMultipleManualIK} hideDate />
      </td>
    );
  }
  let fileData = null;

  let trcMetadata = props.cursor.rawCursor.getChildMetadata("trials/" + props.name + "/markers.trc");
  if (trcMetadata != null || props.uploadTRC != null) {
    fileData = <>
      <td>
        <DropFile cursor={props.cursor} path={"trials/" + props.name + "/markers.trc"} uploadOnMount={props.uploadTRC} accept=".trc,.sto" hideDate required />
      </td>
      <td>
        <DropFile cursor={props.cursor} text={"GRF, *.mot or *.sto"} path={"trials/" + props.name + "/grf.mot"} hideDate uploadOnMount={props.uploadGRF} accept=".mot,.sto" onMultipleFiles={props.onMultipleGRF} />
      </td>
    </>
  }
  else {
    fileData = (
      <td colSpan={2}>
        <DropFile cursor={props.cursor} path={"trials/" + props.name + "/markers.c3d"} uploadOnMount={props.uploadC3D} accept=".c3d,.trc" hideDate required keepFileExtension />
      </td>
    );
  }

  let nameLink;
  if (props.showViewerHint) {
    nameLink =
      <div ref={(r: HTMLDivElement | null) => {
        if (r != null) {
          console.log(r);
          const rect = r.getBoundingClientRect();
          window.scrollTo({
            top: rect.top - 40 + window.scrollY,
            left: rect.left + window.scrollX,
            behavior: 'smooth'
          });
        }
      }} className="MocapView__link_tip_holder">
        <Link
          to={{
            search: "?show-trial=" + props.index,
          }}
          replace
          onClick={() => {
            props.hideViewerHint();
          }}
        >
          {props.name}
        </Link>
        <div className="MocapView__link_tip">
          <i className="mdi mdi-eye me-1 vertical-middle"></i>
          <b>Tip:</b> Click on a trial name to view it in the 3D viewer
        </div>
      </div>;
  }
  else {
    nameLink =
      <Link
        to={{
          search: "?show-trial=" + props.index,
        }}
        replace
        onClick={() => {
          props.hideViewerHint();
        }}
      >
        {props.name}
      </Link>;
  }

  const tagsFile = props.cursor.getTrialTagFile(props.name);
  const tagList = tagsFile.getAttribute("tags", [] as string[]);
  const tagValues = tagsFile.getAttribute("tagValues", {} as { [key: string]: number });

  return (
    <tr>
      <td>
        {nameLink}
      </td>
      {fileData}
      {manualIKRow}
      <td>
        <TagEditor
          tagSet='trial'
          tags={tagList}
          readonly={props.cursor.dataIsReadonly()}
          onTagsChanged={(newTags) => {
            tagsFile.setAttribute("tags", newTags);
          }}
          tagValues={tagValues}
          onTagValuesChanged={(newTagValues) => {
            tagsFile.setAttribute("tagValues", newTagValues);
          }}
          onFocus={() => {
            tagsFile.onFocusAttribute("tags");
          }}
          onBlur={() => {
            tagsFile.onBlurAttribute("tags");
          }}
        />
      </td>
      {!props.cursor.canEdit() ? null : (
        <td>
          <ButtonGroup className="d-block mb-2">
            <Dropdown>
              <Dropdown.Toggle className="table-action-btn dropdown-toggle arrow-none btn btn-light btn-xs">
                <i className="mdi mdi-dots-horizontal"></i>
              </Dropdown.Toggle>
              <Dropdown.Menu>
                <Dropdown.Item
                  onClick={() => {
                    navigate({
                      search: "?show-trial=" + props.index,
                    });
                  }}
                >
                  <i className="mdi mdi-eye me-2 text-muted vertical-middle"></i>
                  Preview
                </Dropdown.Item>
                <Dropdown.Item
                  onClick={() => {
                    props.cursor.rawCursor.deleteByPrefix("trials/" + props.name);
                    props.cursor.rawCursor.deleteChild("trials/" + props.name);
                  }}
                >
                  <i className="mdi mdi-delete me-2 text-muted vertical-middle"></i>
                  Delete
                </Dropdown.Item>
              </Dropdown.Menu>
            </Dropdown>
          </ButtonGroup>
        </td>
      )}
    </tr>
  );
});

type MocapSubjectViewProps = {
  cursor: MocapS3Cursor;
};

function getChildByType(node: Node, type: string): Node | null {
  for (let i = 0; i < node.childNodes.length; i++) {
    let childNode = node.childNodes[i];
    if (childNode.nodeType === Node.TEXT_NODE) {
      // Skip these
    }
    else if (childNode.nodeName === type) {
      return childNode;
    }
  }
  return null;
}

function countChildrenByType(node: Node, type: string): number {
  let count = 0;
  for (let i = 0; i < node.childNodes.length; i++) {
    let childNode = node.childNodes[i];
    if (childNode.nodeType === Node.TEXT_NODE) {
      // Skip these
    }
    else if (childNode.nodeName === type) {
      count++;
    }
  }
  return count;
}

function getChildrenByType(node: Node, type: string): Node[] {
  let nodes: Node[] = [];
  for (let i = 0; i < node.childNodes.length; i++) {
    let childNode = node.childNodes[i];
    if (childNode.nodeType === Node.TEXT_NODE) {
      // Skip these
    }
    else if (childNode.nodeName === type) {
      nodes.push(childNode);
    }
  }
  return nodes;
}

function getNotTextChildren(node: Node): Node[] {
  let nodes: Node[] = [];
  for (let i = 0; i < node.childNodes.length; i++) {
    let childNode = node.childNodes[i];
    if (childNode.nodeType === Node.TEXT_NODE) {
      // Skip these
    }
    else {
      nodes.push(childNode);
    }
  }
  return nodes;
}

function getJointError(joint: Node): string | null {
  let jointChildren = getNotTextChildren(joint);
  if (jointChildren.length === 1) {
    let specificJoint = jointChildren[0];
    if (specificJoint.nodeName === 'CustomJoint') {
      let customJoint = specificJoint;

      let spatialTransform = getChildByType(customJoint, "SpatialTransform");
      if (spatialTransform != null) {
        const transformChildren = getChildrenByType(spatialTransform, "TransformAxis");
        for (let i = 0; i < transformChildren.length; i++) {
          const transformAxis = transformChildren[i];

          let func = getChildByType(transformAxis, "function");
          // On v3 files, there is no "function" wrapper tag
          if (func == null) {
            func = transformAxis;
          }

          let linearFunction = getChildByType(func, "LinearFunction");
          let simmSpline = getChildByType(func, "SimmSpline");
          let polynomialFunction = getChildByType(func, "PolynomialFunction");
          let constant = getChildByType(func, "Constant");
          let multiplier = getChildByType(func, "MultiplierFunction");

          if (linearFunction == null && simmSpline == null && polynomialFunction == null && constant == null && multiplier == null) {
            console.log(spatialTransform);
            return "This OpenSim file has a <CustomJoint> with an unsupported function type in its <TransformAxis>. Currently supported types are <LinearFunction>, <SimmSpline>, <PolynomialFunction>, <Constant>, and <MultiplierFunction>. Anything else will lead to a crash during processing.";
          }
        }
      }
      else {
        return "This OpenSim file has a <CustomJoint> with no <SpatialTransform> tag as a child.";
      }
    }
    else if (specificJoint.nodeName === 'WeldJoint') {
      // These are fine, nothing to verify
      // let weldJoint = getChildByType(joint, "WeldJoint");
    }
    else if (specificJoint.nodeName === 'PinJoint') {
      // These are fine, nothing to verify
      // let pinJoint = getChildByType(joint, "PinJoint");
    }
    else if (specificJoint.nodeName === 'UniversalJoint') {
      // These are fine, nothing to verify
      // let universalJoint = getChildByType(joint, "UniversalJoint");
    }
    else {
      return "This OpenSim file has a Joint type we don't yet support: <" + specificJoint.nodeName + ">. The currently supported types are <CustomJoint>, <WeldJoint>, <PinJoint>, and <UniversalJoint>";
    }
  }
  return null;
}

function getOpenSimBodyList(opensimFileText: string | null): string[] {
  if (opensimFileText == null) return [];

  const text: string = opensimFileText;
  const parser = new DOMParser();
  const xmlDoc: Document = parser.parseFromString(text, "text/xml");

  let rootNode: Node = xmlDoc.getRootNode();
  if (rootNode.nodeName === '#document') {
    rootNode = rootNode.childNodes[0];
  }

  if (rootNode.nodeName !== "OpenSimDocument") {
    console.error("Error getting body list! Malformed *.osim file! Root node of XML file isn't an <OpenSimDocument>, instead it's <" + rootNode.nodeName + ">");
    return [];
  }
  const modelNode = getChildByType(rootNode, "Model");
  if (modelNode == null) {
    console.error("Error getting body list! Malformed *.osim file! There isn't a <Model> tag as a child of the <OpenSimDocument>");
    return [];
  }

  const bodySet = getChildByType(modelNode, "BodySet");
  if (bodySet == null) {
    console.error("Error getting body list! This OpenSim file is missing a BodySet! No <BodySet> tag found");
    return [];
  }
  const bodySetObjects = getChildByType(bodySet, "objects");
  if (bodySetObjects == null) {
    console.error("Error getting body list! This OpenSim file is missing an <objects> child tag inside the <BodySet> tag!");
    return [];
  }

  let bodyNames: string[] = [];
  const bodyNodes = getChildrenByType(bodySetObjects, "Body");
  for (let i = 0; i < bodyNodes.length; i++) {
    const bodyNode = bodyNodes[i];
    const bodyName = (bodyNode as any).getAttribute('name');
    bodyNames.push(bodyName);
  }
  return bodyNames;
}

function validateOpenSimFile(file: File): Promise<null | string> {
  return new Promise<null | string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e: any) => {
      const text: string = e.target.result;
      const parser = new DOMParser();
      const xmlDoc: Document = parser.parseFromString(text, "text/xml");

      let rootNode: Node = xmlDoc.getRootNode();
      if (rootNode.nodeName === '#document') {
        rootNode = rootNode.childNodes[0];
      }
      if (rootNode.nodeName !== "OpenSimDocument") {
        resolve("Malformed *.osim file! Root node of XML file isn't an <OpenSimDocument>, instead it's <" + rootNode.nodeName + ">");
        return;
      }
      const modelNode = getChildByType(rootNode, "Model");
      if (modelNode == null) {
        resolve("Malformed *.osim file! There isn't a <Model> tag as a child of the <OpenSimDocument>");
        return;
      }

      const bodySet = getChildByType(modelNode, "BodySet");
      if (bodySet == null) {
        resolve("This OpenSim file is missing a BodySet! No <BodySet> tag found");
        return;
      }
      const bodySetObjects = getChildByType(bodySet, "objects");
      if (bodySetObjects == null) {
        resolve("This OpenSim file is missing an <objects> child tag inside the <BodySet> tag!");
        return;
      }
      const bodyNodes = getChildrenByType(bodySetObjects, "Body");
      for (let i = 0; i < bodyNodes.length; i++) {
        const bodyNode = bodyNodes[i];

        // Check the attached geometry
        const attachedGeometry = getChildByType(bodyNode, "attached_geometry");
        if (attachedGeometry != null) {
          const meshes = getChildrenByType(attachedGeometry, "Mesh");
          for (let j = 0; j < meshes.length; j++) {
            const mesh = meshes[j];
            const meshFile = getChildByType(mesh, "mesh_file");
            if (meshFile != null && meshFile.textContent != null) {
              const meshName: string = meshFile.textContent;
              console.log(meshName);
            }
          }
        }

        // Check if joints are attached, and if so check that they're supported and won't crash the backend
        const joint = getChildByType(bodyNode, "Joint");
        if (joint != null) {
          const jointError = getJointError(joint);
          if (jointError != null) {
            resolve(jointError);
            return;
          }
        }
      }

      // This can be null in newer OpenSim files
      const jointSet = getChildByType(modelNode, "JointSet");
      if (jointSet != null) {
        const jointSetObjects = getChildByType(jointSet, "objects");
        if (jointSetObjects == null) {
          resolve("This OpenSim file is missing a <objects> tag under its <JointSet> tag.");
          return;
        }

        const joints = getChildrenByType(jointSetObjects, "Joint");
        for (let i = 0; i < joints.length; i++) {
          const jointError = getJointError(joints[i]);
          if (jointError != null) {
            resolve(jointError);
            return;
          }
        }
      }

      const markerSet = getChildByType(modelNode, "MarkerSet");
      if (markerSet == null) {
        console.log(rootNode);
        resolve("This OpenSim file is missing a MarkerSet! No <MarkerSet> tag found");
        return;
      }

      const markerSetObjects = getChildByType(markerSet, "objects");
      if (markerSetObjects == null) {
        resolve("You're trying to upload a file that doesn't have any markers! This OpenSim file is missing a <objects> list inside its <MarkerSet> tag");
        return;
      }

      let numMarkers = countChildrenByType(markerSetObjects, "Marker");
      if (numMarkers < 5) {
        resolve("You're trying to upload a file with " + numMarkers + " <Marker> descriptions inside the <MarkerSet> tag. Please ensure you specify your whole markerset in your OpenSim files.");
        return;
      }

      // If none of the other checks tripped, then we're good to go!
      resolve(null);
    }
    reader.readAsText(file);
  });
}

const MocapSubjectView = observer((props: MocapSubjectViewProps) => {
  const [uploadFiles, setUploadFiles] = useState({} as { [key: string]: File; });
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [showViewerHint, setShowViewerHint] = useState(false);
  const [error, setError] = useState<React.ReactElement | null>(null);

  // List of warnings to dismiss.
  const [dismissed_warning, setDismissedWarning] = useState<Array<string>>([])

  // Checkbox to show all warnings.
  const [showAllWarnings, setShowAllWarnings] = useState(false)

  const navigate = useNavigate();


  // Handle checkbox change for dismissing warnings.
  const handleCheckboxChange = (itemId:string) => (event:any) => {
    const liElement = document.getElementById(itemId);
    const isChecked = event.target.checked;

    // If checked, add to dismished warnings.
    if (isChecked) {
      dismissed_warning.push(itemId);
      setDismissedWarning((dismissed_warning) => [
        ...dismissed_warning,
        itemId,
      ]);
      // Upload dismissed warnings json.
      props.cursor.warningPreferencesJson.setAttribute(itemId, isChecked)
    }
    // If unchecked, show.
    else if(!isChecked) {
      if (liElement) {
        dismissed_warning.splice(dismissed_warning.indexOf(itemId), 1);
        setDismissedWarning((dismissed_warning) =>
          dismissed_warning.filter((item) => item !== itemId)
        );
        // Upload dismissed warnings json.
        props.cursor.warningPreferencesJson.setAttribute(itemId, isChecked)
      }
    }
  };

  const isHiddenCheckboxWarning = (itemId: string): boolean | undefined => {
    return dismissed_warning.includes(itemId) && !showAllWarnings;
  };

  // Checkbox component props.
  interface CheckBoxWarningDismissProps {
    // Id of the specific warning.
    itemId: string;
    // Label of the warning. It can be a string, or a JSX component.
    label: JSX.Element | string;
  }

  // Reusable checkbox component to dismiss warnings.
  const CheckBoxWarningDismiss = ({itemId, label}: CheckBoxWarningDismissProps) => (
    <Form.Group>
      <Form.Check>
        <OverlayTrigger
          placement="right"
          delay={{ show: 50, hide: 400 }}
          overlay={(props) => (
            <Tooltip id="button-tooltip" {...props}>
              You can click this checkbox to dismiss this warning. To show all of the warnings, go to the bottom of the warning section and click on "Show all warnings".
            </Tooltip>
          )}>
            <Form.Check.Input
              type="checkbox"
              checked={dismissed_warning.includes(itemId)}
              onChange={handleCheckboxChange(itemId)}
            />
          </OverlayTrigger>
          <Form.Check.Label>
            <div>
              <span>{label}</span>
            </div>
          </Form.Check.Label>
        </Form.Check>
    </Form.Group>
  );

  useEffect(() => {
    if (props.cursor.hasErrorsFile()) {
      props.cursor.getErrorsFileText().then((text: string) => {
        var jsonError = JSON.parse(text);
        setError(<li>
                  <p>
                    <strong>{jsonError.type} - </strong>
                    {parseLinks(jsonError.message)}
                  </p>
                  <p>
                    {parseLinks(jsonError.original_message)}
                  </p>
                </li>);
      });
    }
    if (props.cursor.hasWarningsPreferenceFile()) {
      props.cursor.getWarningsPreferenceFile().then((text: string) => {
        var jsonWarningPreferences = JSON.parse(text);
        // Iterate over keys to set default values.
        Object.keys(jsonWarningPreferences).forEach(function(key) {
          //if(key === "showAllWarnings")
          //  setShowAllWarnings(jsonWarningPreferences[key])
          //else
          if(jsonWarningPreferences[key])
            setDismissedWarning((dismissed_warning) => [
              ...dismissed_warning,
              key,
            ]);
        })
      });
    }
  }, []);

  let trialViews: any[] = [];

  let trials = props.cursor.getTrials();
  for (let i = 0; i < trials.length; i++) {
    trialViews.push(
      <MocapTrialRowView
        cursor={props.cursor}
        index={i}
        key={trials[i].key}
        name={trials[i].key}
        showViewerHint={i == 0 && showViewerHint}
        hideViewerHint={() => setShowViewerHint(false)}
        uploadC3D={uploadFiles[trials[i].key + ".c3d"]}
        uploadTRC={uploadFiles[trials[i].key + ".trc"]}
        uploadGRF={uploadFiles[trials[i].key + "_grf.mot"]}
        uploadIK={uploadFiles[trials[i].key + "_ik.mot"]}
        onMultipleManualIK={(files: File[]) => {
          // This allows us to store that we'd like to auto-upload these files once the trials with matching names are created
          let updatedUploadFiles = { ...uploadFiles };
          for (let i = 0; i < files.length; i++) {
            updatedUploadFiles[files[i].name.replace(".mot", "_ik.mot").replace(".sto", "_ik.mot")] = files[i];
          }
          setUploadFiles(updatedUploadFiles);
        }}
        onMultipleGRF={(files: File[]) => {
          // This allows us to store that we'd like to auto-upload these files once the trials with matching names are created
          let updatedUploadFiles = { ...uploadFiles };
          for (let i = 0; i < files.length; i++) {
            updatedUploadFiles[files[i].name.replace(".mot", "_grf.mot").replace(".sto", "_grf.mot")] = files[i];
          }
          setUploadFiles(updatedUploadFiles);
        }}
      />
    );
  }
  if (props.cursor.canEdit()) {
    trialViews.push(
      <tr key="upload">
        <td colSpan={6}>
          <Dropzone
            {...props}
            accept=".c3d,.mot,.trc,.sto"
            onDrop={(acceptedFiles) => {
              // This allows us to store that we'd like to auto-upload these files once the trials with matching names are created
              let updatedUploadFiles = { ...uploadFiles };
              let fileNames: string[] = [];
              for (let i = 0; i < acceptedFiles.length; i++) {
                fileNames.push(acceptedFiles[i].name);
                updatedUploadFiles[acceptedFiles[i].name] = acceptedFiles[i];

                if (!acceptedFiles[i].name.endsWith(".c3d") && !acceptedFiles[i].name.endsWith(".trc")) {
                  alert("You can only bulk create trials with *.c3d or *.trc files. To bulk upload other types of files (like *.mot or *.sto for IK) please create the trials first, then drag a group of *.mot or *.sto files to one of the IK upload slots (doesn't matter which trial, files will be matched by name).");
                  return;
                }
              }
              setUploadFiles(updatedUploadFiles);
              props.cursor.bulkCreateTrials(fileNames);
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
                    Drop C3D or TRC files here (or just click here) to bulk upload trials.
                  </h5>
                  <span className="text-muted font-13">
                    (You can drop multiple files at once to create multiple
                    trials simultaneously)
                  </span>
                </div>
              </div>
            }}
          </Dropzone>
        </td>
      </tr>
    );
  }

  let showValidationControls = props.cursor.getShowValidationControls();

  let manuallyScaledOpensimUpload = null;
  let manualIkRowHeader = null;
  if (showValidationControls) {
    manuallyScaledOpensimUpload = (
      <div>
        <h5>Manually Scaled OpenSim</h5>
        <DropFile cursor={props.cursor} path={"manually_scaled.osim"} accept=".osim" validateFile={validateOpenSimFile} />
      </div>
    );
    manualIkRowHeader = (
      <th className="border-0">Gold IK</th>
    );
  }

  let weightValue = props.cursor.subjectJson.getAttribute("massKg", 0.0);
  let heightValue = props.cursor.subjectJson.getAttribute("heightM", 0.0);
  let sexValue = props.cursor.subjectJson.getAttribute("sex", "unknown");
  let skeletonPreset = props.cursor.subjectJson.getAttribute("skeletonPreset", props.cursor.hasModelFile() ? "custom" : "vicon");
  let subjectTags = props.cursor.subjectJson.getAttribute("subjectTags", [] as string[]);
  let subjectTagValues = props.cursor.subjectJson.getAttribute("subjectTagValues", {} as { [key: string]: number });

  let autoAvgRMSE = props.cursor.resultsJson.getAttribute("autoAvgRMSE", 0.0);
  let linearResidual: number | false = props.cursor.resultsJson.getAttribute("linearResidual", false);
  let angularResidual: number | false = props.cursor.resultsJson.getAttribute("angularResidual", false);
  let guessedTrackingMarkers = props.cursor.resultsJson.getAttribute("guessedTrackingMarkers", 0.0);
  let trialMarkerSets = props.cursor.resultsJson.getAttribute("trialMarkerSets", {});
  let trialWarnings = props.cursor.resultsJson.getAttribute("trialWarnings", {});
  let fewFramesWarning = props.cursor.resultsJson.getAttribute("fewFramesWarning", false);
  let jointLimitsHits = props.cursor.resultsJson.getAttribute("jointLimitsHits", {});
  let osimMarkers: string[] = props.cursor.resultsJson.getAttribute("osimMarkers", {});

  let status: 'done' | 'processing' | 'could-process' | 'error' | 'waiting' | 'slurm' | 'empty' = props.cursor.getSubjectStatus();
  let statusBadge = null;
  let statusDetails = null;
  if (status === "done") {
    let downloadOpenSim = null;
    if (props.cursor.hasResultsArchive()) {
      downloadOpenSim = (
        <div style={{ 'marginBottom': '5px' }}>
          <Button onClick={() => props.cursor.downloadResultsArchive()}>
            <i className="mdi mdi-download me-2 vertical-middle"></i>
            Download OpenSim Results
            <OverlayTrigger
              placement="right"
              delay={{ show: 50, hide: 400 }}
              overlay={(props) => (
                <Tooltip id="button-tooltip" {...props}>
                  This is a zip ball of a folder hierarchy with OpenSim files in a standard layout.
                </Tooltip>
              )}
            >
              <i className="mdi mdi-help-circle-outline vertical-middle" style={{ marginLeft: '5px' }}></i>
            </OverlayTrigger>
          </Button>
        </div>
      );
    }
    let downloadSubjectOnDisk = null;
    if (props.cursor.hasSubjectOnDisk()) {
      downloadSubjectOnDisk = (
        <div style={{ 'marginBottom': '5px' }}>
          <Button onClick={() => props.cursor.downloadSubjectOnDisk()}>
            <i className="mdi mdi-download me-2 vertical-middle"></i>
            Download Nimble Physics &amp; PyTorch Data File
            <OverlayTrigger
              placement="right"
              delay={{ show: 50, hide: 400 }}
              overlay={(props) => (
                <Tooltip id="button-tooltip" {...props}>
                  This binary file can be efficiently read by Nimble Physics to train PyTorch models. See the Nimble documentation for details.
                </Tooltip>
              )}
            >
              <i className="mdi mdi-help-circle-outline vertical-middle" style={{ marginLeft: '5px' }}></i>
            </OverlayTrigger>
          </Button>
        </div>
      );
    }

    let warningList = [];

    if (guessedTrackingMarkers == true) {
      let markerText = '<Marker name="RSH">';
      markerText += '\n  <socket_parent_frame>/bodyset/torso</socket_parent_frame>';
      markerText += '\n  <location> -0.03 0.42 0.15 </location>';
      let markerText2 = '  <fixed>true</fixed>';
      let markerText3 = '</Marker>';

      warningList.push(<li key='guessed_tracking' id={'guessed_tracking'} hidden={isHiddenCheckboxWarning('guessed_tracking')}>

        <CheckBoxWarningDismiss
          itemId="guessed_tracking"
          label={
            <>
              <p>
                The optimizer had to guess which of your markers were placed on bony landmarks, and which were not. This is probably because in the unscaled OpenSim model you uploaded, all or most of your markers were listed as <code>&lt;fixed&gt;<b>false</b>&lt;/fixed&gt;</code>, or they were all <code>&lt;fixed&gt;<b>true</b>&lt;/fixed&gt;</code>.
                You may achieve higher quality results if you specify all the markers placed on <b><i>bony landmarks (i.e. "anatomical markers")</i></b> as <code>&lt;fixed&gt;<b>true</b>&lt;/fixed&gt;</code>, and all the markers placed on <b><i>soft tissue (i.e. "tracking markers")</i></b> as <code>&lt;fixed&gt;<b>false</b>&lt;/fixed&gt;</code>.
              </p>
              <p>Here's an example marker that's been correctly specified as <code>&lt;fixed&gt;<b>true</b>&lt;/fixed&gt;</code>:
              </p>
              <p>
                <code>
                  <pre style={{ marginBottom: 0 }}>
                    {markerText}
                  </pre>
                  <b><pre style={{ marginBottom: 0 }}>
                    {markerText2}
                  </pre></b>
                  <pre>
                    {markerText3}
                  </pre>
                </code>
              </p>
            </>
          }
        />
      </li>);
    }

    if (trialMarkerSets != null) {
      let trials = Object.keys(trialMarkerSets);

      let trialOnly: string[] = [];
      let shared: string[] = [];

      for (let key of trials) {
        let trialMarkerSet: string[] = trialMarkerSets[key];

        for (let tm of trialMarkerSet) {
          if (osimMarkers.indexOf(tm) === -1) {
            if (trialOnly.indexOf(tm) === -1) {
              trialOnly.push(tm);
            }
          }
          else {
            if (shared.indexOf(tm) === -1) {
              shared.push(tm);
            }
          }
        }
      }
      if (trialOnly.length > 0) {
        warningList.push(<li key={'unused-markers'} id={'unused-markers'} hidden={isHiddenCheckboxWarning('unused-markers')}>

          <CheckBoxWarningDismiss
            itemId="unused-markers"
            label={<p>There were <b><i>{trialOnly.length} markers</i></b> in the mocap file(s) that were ignored by the optimizer, because they weren't in the unscaled OpenSim model you uploaded: <b><i>{trialOnly.join(', ')}</i></b>. These appear as "Unused Markers" in the visualizer - you can mouse over them to see which one is which.</p>}
          />
        </li>);
      }
    }
    if (Object.keys(trialWarnings).length > 0) {
      /*
      let warningsBlocks = [];
      for (let key in trialWarnings) {
        warningsBlocks.push(<p key={key}>
          <b>{key}:</b>
          <ul>
            {trialWarnings[key].map((v: string) => {
              return <li key={v}>{v}</li>
            })}
          </ul>
        </p>)
      }
      */
      warningList.push(<li key={"markerCleanupWarnings"} id={"markerCleanupWarnings"} hidden={isHiddenCheckboxWarning('markerCleanupWarnings')}>
          <CheckBoxWarningDismiss
            itemId="markerCleanupWarnings"
            label={ <p>There were some glitches / mislabelings detected in the uploaded marker data. We've attempted to patch it with heuristics, but you may want to review by hand. See the README in the downloaded results folder for details.</p>}
          />
      </li>);
    }
    if (fewFramesWarning) {
      warningList.push(<li key={"fewFrames"} id={"fewFrames"} hidden={isHiddenCheckboxWarning('fewFrames')}>

        <CheckBoxWarningDismiss
          itemId="fewFrames"
          label={<p>The trials you uploaded didn't include very many frames! The optimizer relies on motion of the body to find optimal scalings, so you will get better results with more data from this subject.</p>}
          />
      </li>);
    }
    if (Object.keys(jointLimitsHits).length > 0) {
      let warningsBlocks = [];
      let jointNames = Object.keys(jointLimitsHits);
      let max = 0;
      for (let key of jointNames) {
        if (jointLimitsHits[key] > max) {
          max = jointLimitsHits[key];
        }
      }

      jointNames.sort((a: string, b: string) => {
        return jointLimitsHits[b] - jointLimitsHits[a];
      });
      for (let key of jointNames) {
        const percentage = jointLimitsHits[key] / max;
        if (percentage > 0.0) {
          warningsBlocks.push(<li key={key}>
            <b>{key}</b> was at its limit on {jointLimitsHits[key]} frames.
          </li>);
        }
      }
      warningList.push(<li key={"jointLimits"}  id={"jointLimits"} hidden={isHiddenCheckboxWarning('jointLimits')} style={{verticalAlign: "text-top"}}>

          <CheckBoxWarningDismiss
            itemId="jointLimits"
            label={<>
                    <p>The OpenSim skeleton hit its joint limits during the trial. This may lead to poor/jittery IK results. Here are joints to investigate:</p>
                      <ul>
                        {warningsBlocks}
                      </ul>
                   </>
                  }
          />

      </li>);
    }

    let guessedMarkersWarning = null;
    if (warningList.length > 0) {
      guessedMarkersWarning = <div className="alert alert-warning">
        <h4><i className="mdi mdi-alert me-2 vertical-middle"></i> Warning: Results may be suboptimal!</h4>
        <p>
          The optimizer detected some issues in the uploaded files. We can't detect everything automatically, so see our <a href="https://addbiomechanics.org/instructions.html" target="_blank">Tips and Tricks page</a> for more suggestions.
        </p>
        <hr />
        <ul style={{ listStyleType: 'none', paddingLeft: '1.5em'}}>
          {warningList}
        </ul>
        <hr />
        <p>
          You can ignore these warnings if you are happy with your results, or you update your data and/or your OpenSim Model and Markerset and then hit "Reprocess" (below in yellow) to fix the problem.
        </p>
          <OverlayTrigger
            placement="right"
            delay={{ show: 50, hide: 400 }}
            overlay={(props) => (
              <Tooltip id="button-tooltip" {...props}>
                Click this checkbox to show/hide dismissed warnings.
              </Tooltip>
            )}>
            <Form.Check
              type="checkbox"
              label="Show all warnings"
              checked={showAllWarnings}
              disabled={dismissed_warning.length == 0}
              onChange={(event) => {
                setShowAllWarnings(!showAllWarnings)
                // If checked, show dismissed warning..
                if (event.target.checked) {
                  dismissed_warning.forEach((dismissed_warning_id) => {
                    const liElement = document.getElementById(dismissed_warning_id);
                  })
                // If unchecked, hide dismissed warning.
                } else {
                  dismissed_warning.forEach((dismissed_warning_id) => {
                    const liElement = document.getElementById(dismissed_warning_id);
                  })
                }
                // Save preferences in json file.
                props.cursor.warningPreferencesJson.setAttribute("showAllWarnings", event.target.checked)
              }}
            />
          </OverlayTrigger>
      </div>;
    }

    statusBadge = <span className="badge bg-primary">Processed</span>;

    let residualText = "";
    if (linearResidual && angularResidual) {
      residualText += " (";
      if (linearResidual >= 100 || linearResidual < 0.1) {
        residualText += linearResidual.toExponential(2);
      }
      else {
        residualText += linearResidual.toFixed(2);
      }
      residualText += "N, ";
      if (angularResidual >= 100 || angularResidual < 0.1) {
        residualText += angularResidual.toExponential(2);
      }
      else {
        residualText += angularResidual.toFixed(2);
      }
      residualText += "Nm residuals)";
    }
    statusDetails = <>
      <h4>Results: {(autoAvgRMSE * 100 ?? 0.0).toFixed(2)} cm RMSE {residualText}</h4>
      {guessedMarkersWarning}
      {downloadOpenSim}
      {downloadSubjectOnDisk}
      <div style={{ 'marginBottom': '5px' }}>
        <Button variant="success" onClick={() => { setShowViewerHint(true) }}>
          <i className="mdi mdi-eye me-2 vertical-middle"></i>
          View Results in 3D Visualizer
        </Button>
      </div>
      <Button variant="warning" onClick={props.cursor.requestReprocessSubject}>
        <i className="mdi mdi-refresh me-2 vertical-middle"></i>
        Reprocess
      </Button>
      <Link
        style={{
          marginLeft: '7px'
        }}
        to={{
          search: "?logs=true"
        }}
        replace
      >View Processing Logs</Link>
    </>;
  }
  else if (status === "error") {
    // var text = '{"type": "PathError", "message": "PathError: This is a custom message. Below is the original error message, which may contain useful information about your issue. If you are unable to resolve the issue, please, submit a forum post at https://simtk.org/projects/addbiomechanics or submit a GitHub issue at https://github.com/keenon/AddBiomechanics/issues with all error message included.", "original_message": "Exception caught in validate_paths: This is a test exception."}'
    // var jsonError = JSON.parse(text);
    // error = <li>
    //           <p>
    //             <strong>{jsonError.type} - </strong>
    //             {parseLinks(jsonError.message)}
    //           </p>
    //           <p>
    //             {parseLinks(jsonError.original_message)}
    //           </p>
    //         </li>

    let guessedErrors = null;
    if (error != null) {
      guessedErrors = <div className="alert alert-danger">
        <h4><i className="mdi mdi-alert me-2 vertical-middle"></i>  Detected errors while processing the data!</h4>
        <p>
          There were some errors while processing the data. See our <a href="https://addbiomechanics.org/instructions.html" target="_blank">Tips and Tricks page</a> for more suggestions.
        </p>
        <hr />
        <ul>
          {error}
        </ul>
        <hr />
        <p>
          Please, fix the errors and update your data and/or your OpenSim Model and Markerset and then hit "Reprocess" (below in yellow) to fix the problem.
        </p>
      </div>;
    }

    statusBadge = <span className="badge bg-danger">Error</span>;
    statusDetails = <>
      {guessedErrors}
      <Button variant="warning" onClick={props.cursor.requestReprocessSubject}>
        <i className="mdi mdi-refresh me-2 vertical-middle"></i>
        Reprocess
      </Button>
      <Link
        style={{
          marginLeft: '7px'
        }}
        to={{
          search: "?logs=true"
        }}
        replace
      >View Processing Logs</Link>
    </>;
  }
  else if (status === "processing") {
    let advancedOptions = null;
    if (props.cursor.canEdit()) {
      advancedOptions = (
        <div className="mt-2 mb-2">
          <Dropdown>
            <Dropdown.Toggle size="sm" variant="light" id="dropdown-basic">
              Advanced Options
            </Dropdown.Toggle>

            <Dropdown.Menu>
              <Dropdown.Item variant="danger" onClick={() => {
                if (window.confirm("DANGER! Only do this if your processing server has crashed. You can check under \"Processing Server Status\" to make sure. Are you fairly confident your processing server crashed?")) {
                  props.cursor.requestReprocessSubject();
                }
              }}>DANGER: Reprocess now, ignoring current processing attempt</Dropdown.Item>
            </Dropdown.Menu>
          </Dropdown>
        </div>
      )
    }
    statusBadge = <span className="badge bg-warning">Processing</span>;
    statusDetails =
      <>
        <div>
          <Link
            style={{
              marginLeft: '7px'
            }}
            to={{
              search: "?logs=true"
            }}
            replace
          >Watch Live Processing Logs</Link>
        </div>
        {advancedOptions}
        <div>
          We'll send you an email when your data has finished processing!
        </div>
      </>;
  }
  else if (status === "could-process") {
    if (props.cursor.canEdit()) {
      statusDetails = <Button onClick={() => {
        props.cursor.subjectJson.setAttribute("skeletonPreset", skeletonPreset);
        props.cursor.markReadyForProcessing();
      }}>Process And Share</Button>;
    }
    else {
      statusBadge = <span className="badge bg-secondary">Waiting for owner to process</span>;
    }
  }
  else if (status === "waiting") {
    statusBadge = <span className="badge bg-secondary">Waiting for server</span>;
    statusDetails = <div>
      <div className="mb-1">
        <Link
          to={"/server_status"}
        >See what the processing servers are working on</Link>
      </div>
      We'll send you an email when your data has finished processing!
    </div>
  }
  else if (status === "slurm") {
    statusBadge = <span className="badge bg-secondary">Queued on SLURM cluster</span>;
    statusDetails = <div>
      <div>
        We'll send you an email when your data has finished processing!
      </div>
      <Dropdown>
        <Dropdown.Toggle size="sm" variant="light" id="dropdown-basic">
          Advanced Options
        </Dropdown.Toggle>

        <Dropdown.Menu>
          <Dropdown.Item variant="danger" onClick={() => {
            if (window.confirm("DANGER! Only do this if your processing server has crashed. Are you fairly confident your processing server crashed?")) {
              props.cursor.requestReprocessSubject();
            }
          }}>DANGER: Reprocess now, ignoring current processing attempt</Dropdown.Item>
        </Dropdown.Menu>
      </Dropdown>
    </div>
  }
  else if (status === 'empty') {
    statusBadge = <span className="badge bg-danger">Missing required data</span>;
    statusDetails = <div>
      Missing data is highlighted below in red. Please input the data (or if it's a trial that's missing data, you can also delete the trial).
    </div>
  }

  let advancedOptions = null;
  let exportSDF = props.cursor.subjectJson.getAttribute("exportSDF", false);
  let exportMJCF = props.cursor.subjectJson.getAttribute("exportMJCF", false);
  let ignoreJointLimits = props.cursor.subjectJson.getAttribute("ignoreJointLimits", false);
  let disableDynamics = props.cursor.subjectJson.getAttribute("disableDynamics", false);
  let residualsToZero = props.cursor.subjectJson.getAttribute("residualsToZero", false);
  let tuneResidualLoss = props.cursor.subjectJson.getAttribute("tuneResidualLoss", 1.0);
  let runMoco = props.cursor.subjectJson.getAttribute("runMoco", false);
  let exportMoco = props.cursor.subjectJson.getAttribute("exportMoco", false);

  let openSimText = props.cursor.customModelFile.getText();
  console.log("OpenSim text: " + openSimText);
  const availableBodyList = getOpenSimBodyList(openSimText);
  let footBodyNames = props.cursor.subjectJson.getAttribute("footBodyNames", []);

  if (true) {
    let dynamicsOptions = <></>;
    if (!disableDynamics) {
      dynamicsOptions = <>
        <div className="mb-15">
          <p>
            Change the weight of residuals in the main optimization (tuning joint poses, body scales, marker offsets, body COMs, body masses, and body inertia properties):{" "}
            <br />
            <small>
              Note: This weighting is relative to the other terms in the optimization - 1.0 is default weighting, lower will prefer optimizing other terms (mostly marker RMSE), higher will prefer optimizing residuals.
            </small>
          </p>
          <input type="number" value={tuneResidualLoss} onChange={(e) => {
            props.cursor.subjectJson.setAttribute("tuneResidualLoss", parseFloat(e.target.value));
          }} onFocus={() => props.cursor.subjectJson.onFocusAttribute("tuneResidualLoss")} onBlur={() => props.cursor.subjectJson.onBlurAttribute("tuneResidualLoss")}></input>
        </div>
        <div className="mb-15">
          <p>
            Run a last optimization pass to attempt to drive residuals to exactly zero at the end of the optimization, at the cost of more marker error:{" "}
            <br />
            <small>
              Note: This optimization is non-convex and does not always succeed, and if it does not it will return results as if you hadn't enabled it.
            </small>
          </p>
          <input type="checkbox" checked={residualsToZero} onChange={(e) => {
            props.cursor.subjectJson.setAttribute("residualsToZero", e.target.checked);
          }}></input>
        </div>
        <div className="mb-15">
          <p>
            Run a Moco Inverse problem to get muscle forces, after the dynamics optimization is complete:{" "}
          </p>
          <input type="checkbox" checked={runMoco} onChange={(e) => {
            props.cursor.subjectJson.setAttribute("runMoco", e.target.checked);
          }}></input>
        </div>
        <div className="mb-15">
          <p>
            Export a Python script to allow you to run a local Moco Inverse problem to get muscle forces, using the results of the dynamics optimization:{" "}
          </p>
          <input type="checkbox" checked={exportMoco || runMoco} onChange={(e) => {
            if (e.target.checked) {
              props.cursor.subjectJson.setAttribute("exportMoco", true);
            }
            else {
              props.cursor.subjectJson.setAttribute("exportMoco", false);
              props.cursor.subjectJson.setAttribute("runMoco", false);
            }
          }}></input>
        </div>
      </>;
    }

    advancedOptions = <>
      <hr />
      <button className="btn" type="button" onClick={() => setShowAdvanced(!showAdvanced)}>
        <i className={"mdi mdi-arrow-" + (showAdvanced ? "down" : "right") + "-drop-circle-outline me-1 text-muted vertical-middle"}></i>
        {showAdvanced ? "Hide" : "Show"} Advanced Options
      </button>
      <div className={"collapse" + (showAdvanced ? " show" : "")}>
        <h4>
          <i className="mdi mdi-alert me-1 text-muted vertical-middle"></i>
          Advanced Options
        </h4>
        <div className="card card-body">
          <div className="mb-15">
            Use heuristics to clean up marker data:{" "}<input type="checkbox" checked disabled></input>
          </div>
          <div className="mb-15">
            Export PyBullet compatible SDF files:{" "}
            <input type="checkbox" checked={exportSDF} onChange={(e) => {
              props.cursor.subjectJson.setAttribute("exportSDF", e.target.checked);
            }}></input>
          </div>
          <div className="mb-15">
            Export MuJoCo files:{" "}
            <input type="checkbox" checked={exportMJCF} onChange={(e) => {
              props.cursor.subjectJson.setAttribute("exportMJCF", e.target.checked);
            }}></input>
          </div>
          <div className="mb-15">
            Ignore joint limits:{" "}
            <input type="checkbox" checked={ignoreJointLimits} onChange={(e) => {
              props.cursor.subjectJson.setAttribute("ignoreJointLimits", e.target.checked);
            }}></input>
          </div>
          <div className="mb-15">Compare optimized skeleton with hand-scaled version:{" "}<input type="checkbox" checked={showValidationControls} onChange={(e) => {
            props.cursor.setShowValidationControls(e.target.checked);
          }} />
          </div>
          <div className="mb-15">
            <label>
              Static Trial:
            </label>
            <OverlayTrigger
              placement="right"
              delay={{ show: 50, hide: 400 }}
              overlay={(props) => (
                <Tooltip id="button-tooltip" {...props}>
                  This is a short trial where the model's joints are known to be in the neutral position. If you have uploaded a custom OpenSim file, this is currently assumed to be all joints set to zero.
                  Using a static trial can be helpful for enforcing tradeoffs between joint angle changes and corresponding marker offsets that can otherwise be somewhat ambiguous, such as pelvis rotation and ankle extension.
                </Tooltip>
              )}
            >
              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
            </OverlayTrigger>
            <DropFile cursor={props.cursor} path={"trials/static/markers"} text="Drop a .trc or .c3d file here for your static trial" accept=".trc,.c3d" keepFileExtension={true} />
          </div>
          <div className="">
            <div className="alert alert-warning" role="alert">
              Skip Dynamics Fit:{" "}
              <input type="checkbox" checked={disableDynamics} onChange={(e) => {
                props.cursor.subjectJson.setAttribute("disableDynamics", e.target.checked);
              }}></input>
              <OverlayTrigger
                placement="right"
                delay={{ show: 50, hide: 400 }}
                overlay={(props) => (
                  <Tooltip id="button-tooltip" {...props}>
                    This will ignore any ground-reaction-force data that you have provided, and will not attempt to fit any dynamics parameters. This is useful if you are only interested in fitting the skeleton and marker positions.
                  </Tooltip>
                )}
              >
                <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
              </OverlayTrigger>
            </div>
          </div>
          {dynamicsOptions}
        </div>
      </div>
    </>;
  }

  let skeletonDetails = null;
  if (skeletonPreset === 'vicon') {
    skeletonDetails = <div className="alert alert-secondary mb-15">The Rajagopal 2015 skeleton is from <a href="https://simtk.org/projects/full_body" target="_blank">here</a>. The Vicon Plug-In Gait Markerset is described <a href="https://docs.vicon.com/download/attachments/133828966/Plug-in%20Gait%20Reference%20Guide.pdf?version=2&modificationDate=1637681079000&api=v2" target="_blank">here</a>. Your data must match the marker names exactly!</div>
  }
  else if (skeletonPreset === 'cmu') {
    skeletonDetails = <div className="alert alert-secondary mb-15">The Rajagopal 2015 skeleton is from <a href="https://simtk.org/projects/full_body" target="_blank">here</a>. The CMU Markerset is described <a href="http://mocap.cs.cmu.edu/markerPlacementGuide.pdf" target="_blank">here</a>. Your data must match the marker names exactly!</div>
  }
  else if (skeletonPreset === 'complete') {
    skeletonDetails = <div className="alert alert-secondary mb-15">The DEVELOPER PREVIEW full body model is unpublished work from Keenon Werling, Carmichael Ong, and Marilyn Keller. USE AT YOUR OWN RISK!</div>
  }
  if (skeletonPreset === 'custom') {
    skeletonDetails = <div>
      <DropFile cursor={props.cursor} path={"unscaled_generic.osim"} accept=".osim" validateFile={validateOpenSimFile} required />
    </div>;
  }

  let footSelector = null;
  if (!disableDynamics && skeletonPreset === 'custom') {
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

    footSelector = (<>
      <div className="row mb-15">
        <label htmlFor="footBodyNames" className="form-label is-invalid">
          Foot Body Names in Custom OpenSim Model:
          <OverlayTrigger
            placement="right"
            delay={{ show: 50, hide: 400 }}
            overlay={(props) => (
              <Tooltip id="button-tooltip" {...props}>
                We assume measured ground reaction forces goes through these bodies. The tool currently works best if you select only two bodies to serve as "feet", even if your feet are modeled as articulated bodies.
              </Tooltip>
            )}
          >
            <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
          </OverlayTrigger>
        </label>
        <TagEditor
          error={footBodyNames.length != 2}
          tagSet={availableBodyList}
          tags={footBodyNames}
          readonly={props.cursor.dataIsReadonly()}
          onTagsChanged={(newTags) => {
            props.cursor.subjectJson.setAttribute("footBodyNames", newTags);
          }}
          tagValues={{}}
          onTagValuesChanged={(newTagValues) => {
            // Do nothing
          }}
          onFocus={() => {
            props.cursor.subjectJson.onFocusAttribute("footBodyNames");
          }}
          onBlur={() => {
            props.cursor.subjectJson.onBlurAttribute("footBodyNames");
          }}
        />
        {footErrorMessage}
      </div>
    </>);
  }

  let header = null;
  if (props.cursor.subjectJson.isLoadingFirstTime()) {
    header = <>
      <div className="mb-15">
        <h5>Status <span className="badge bg-secondary">Loading</span></h5>
      </div>
      <div className="row g-3">
        <div className="col-md-4">
          <Spinner animation='border' />
        </div>
      </div>
    </>;
  }
  else {
    header = <>
      <div className="mb-15">
        <h5>Status {statusBadge}</h5>
        <div className="mb-15">{statusDetails}</div>
      </div>
      <div className="row">
        <label htmlFor="skeletonPreset" className="form-label">
          OpenSim Model and Markerset:
        </label>
        <div className="col-md-6">
          <select id="skeletonPreset" className="form-select mb-3" value={skeletonPreset} disabled={props.cursor.dataIsReadonly()} onChange={(e) => {
            if (e.target.value === 'custom') {
              props.cursor.markCustomOsim();
            }
            else {
              props.cursor.clearCustomOsim();
            }
            props.cursor.subjectJson.setAttribute("skeletonPreset", e.target.value);
          }}>
            <option value="vicon" selected>Rajagopal 2015, Vicon Plug-In Gait Markerset</option>
            <option value="cmu">Rajagopal 2015, CMU Markerset</option>
            <option value="complete">Complete Body Model 2022, DEVELOPER PREVIEW</option>
            <option value="custom">Custom OpenSim Model, Custom Markerset</option>
          </select>
        </div>
        <div className="col-md-6">
          {skeletonDetails}
        </div>
      </div>
      {footSelector}
      <form className="row g-3 mb-15">
        <div className="col-md-4">
          <label htmlFor="heightM" className="form-label">
            Height without shoes (m):
            <OverlayTrigger
              placement="right"
              delay={{ show: 50, hide: 400 }}
              overlay={(props) => (
                <Tooltip id="button-tooltip" {...props}>
                  We use this (in addition to weight and biological sex) to condition the statistical prior for bone dimensions. Approximate values are ok.
                </Tooltip>
              )}
            >
              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
            </OverlayTrigger>
          </label>
          <input type="number" disabled={props.cursor.dataIsReadonly()} className={"form-control" + ((heightValue < 0.1 || heightValue > 3.0) ? " is-invalid" : "") + ((heightValue >= 0.1 && heightValue < 1.3) ? " is-warning" : "")} id="heightM" value={heightValue} onChange={(e) => {
            props.cursor.subjectJson.setAttribute("heightM", e.target.value);
          }} onFocus={(e) => {
            props.cursor.subjectJson.onFocusAttribute("heightM");
          }} onBlur={(e) => {
            props.cursor.subjectJson.onBlurAttribute("heightM");
          }} />
          {(() => {
            if (heightValue < 0.1) {
              return (
                <div className="invalid-feedback">
                  Humans are generally not less than 0.1 meters tall.
                </div>
              );
            }
            else if (heightValue < 1.3) {
              return (
                <div className="warning-feedback">
                  Our algorithm scales partially based on statistics generated from healthy adults. Results in children may not be accurate.
                </div>
              );
            }
            else if (heightValue > 3.0) {
              return (
                <div className="invalid-feedback">
                  Humans are generally not more than 3 meters tall.
                </div>
              );
            }
          })()}
        </div>
        <div className="col-md-4">
          <label htmlFor="weightKg" className="form-label">
            Weight (kg):
            <OverlayTrigger
              placement="right"
              delay={{ show: 50, hide: 400 }}
              overlay={(props) => (
                <Tooltip id="button-tooltip" {...props}>
                  We use this (in addition to height and biological sex) to condition the statistical prior for bone dimensions. Approximate values are ok.
                </Tooltip>
              )}
            >
              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
            </OverlayTrigger>
          </label>
          <input type="number" className={"form-control" + ((weightValue < 5 || weightValue > 700) ? " is-invalid" : "") + ((weightValue >= 5 && weightValue < 30) ? " is-warning" : "")} disabled={props.cursor.dataIsReadonly()} id="weightKg" value={weightValue} onChange={(e) => {
            props.cursor.subjectJson.setAttribute("massKg", e.target.value);
          }} onFocus={(e) => {
            props.cursor.subjectJson.onFocusAttribute("massKg");
          }} onBlur={(e) => {
            props.cursor.subjectJson.onBlurAttribute("massKg");
          }} />
          {(() => {
            if (weightValue < 5) {
              return (
                <div className="invalid-feedback">
                  Humans are generally not less than 5 kilograms.
                </div>
              );
            }
            else if (weightValue < 30) {
              return (
                <div className="warning-feedback">
                  Our algorithm scales partially based on statistics generated from healthy adults. Results in children may not be accurate.
                </div>
              );
            }
            else if (weightValue > 700) {
              return (
                <div className="invalid-feedback">
                  Humans are generally not more than 700 kilograms.
                </div>
              );
            }
          })()}
        </div>
        <div className="col-md-4">
          <label htmlFor="weightKg" className="form-label">
            Biological Sex:
            <OverlayTrigger
              placement="right"
              delay={{ show: 50, hide: 400 }}
              overlay={(props) => (
                <Tooltip id="button-tooltip" {...props}>
                  We use this (in addition to height and weight) to condition the statistical prior for bone dimensions, if subject sex is available.
                </Tooltip>
              )}
            >
              <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
            </OverlayTrigger>
          </label>
          <select className="form-control" id="sex" disabled={props.cursor.dataIsReadonly()} value={sexValue} onChange={(e) => {
            props.cursor.subjectJson.setAttribute("sex", e.target.value);
          }} onFocus={(e) => {
            props.cursor.subjectJson.onFocusAttribute("sex");
          }} onBlur={(e) => {
            props.cursor.subjectJson.onBlurAttribute("sex");
          }}>
            <option value="unknown">Unknown</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
          </select>
        </div>
      </form>
      <div className="mb-15">
        <label>
          Subject Tags:
        </label>
        <OverlayTrigger
          placement="right"
          delay={{ show: 50, hide: 400 }}
          overlay={(props) => (
            <Tooltip id="button-tooltip" {...props}>
              These tags are not used in data processing, but can help your users once the data is published. We use structured tags, instead of free form text notes, to avoid accidentally hosting Personally Identifiable Information (PII) on the platform. If you don't find the tags you need, feel free to email keenon@cs.stanford.edu and suggest new tags!
            </Tooltip>
          )}
        >
          <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
        </OverlayTrigger>
        <TagEditor
          tagSet='subject'
          tags={subjectTags}
          readonly={props.cursor.dataIsReadonly()}
          onTagsChanged={(newTags) => {
            props.cursor.subjectJson.setAttribute("subjectTags", newTags);
          }}
          tagValues={subjectTagValues}
          onTagValuesChanged={(newTagValues) => {
            props.cursor.subjectJson.setAttribute("subjectTagValues", newTagValues);
          }}
          onFocus={() => {
            props.cursor.subjectJson.onFocusAttribute("subjectTags");
          }}
          onBlur={() => {
            props.cursor.subjectJson.onBlurAttribute("subjectTags");
          }}
        />
      </div>
    </>
  }

  const nameWidth = 120;
  const fileWidthPart1 = 100;
  const fileWidthPart2 = 100;
  const actionWidth = props.cursor.canEdit() ? 100 : 0;

  const remainingWidth = '100%'; // 'calc(100% - ' + (nameWidth + fileWidthPart1 + fileWidthPart2 + actionWidth) + 'px)';

  return (
    <div className="MocapView">
      <MocapTrialModal cursor={props.cursor} />
      <MocapLogModal cursor={props.cursor} />
      <MocapTagModal cursor={props.cursor} />
      <h3>
        <i className="mdi mdi-walk me-1 text-muted vertical-middle"></i>
        Subject: {props.cursor.getCurrentFileName()}{" "}
        {/*<span className="badge bg-secondary">{"TODO"}</span>*/}
      </h3>
      {header}
      {manuallyScaledOpensimUpload}
      <div>
        <Table
          responsive={trials.length > 2}
          className="table table-centered table-nowrap mb-0 mt-2"
          style={{
            tableLayout: 'fixed',
            width: '100%'
          }}
        >
          <colgroup>
            <col width={nameWidth + 'px'} />
            <col width={fileWidthPart1 + 'px'} />
            <col width={fileWidthPart2 + 'px'} />
            {showValidationControls ? <col width={((100 - 20 - (props.cursor.canEdit() ? 15 : 0)) / 4) + "%"} /> : null}
            <col width={remainingWidth} />
            {props.cursor.canEdit() ? (
              <col width={actionWidth} />
            ) : null}
          </colgroup>
          <thead className="table-light">
            <tr>
              <th className="border-0" >Trial Name</th>
              <th className="border-0" colSpan={2}>Mocap File</th>
              {manualIkRowHeader}
              <th className="border-0" >
                Trial Tags
                {(() => {
                  if (!props.cursor.dataIsReadonly()) {
                    return (<Dropdown style={{ display: 'inline-block' }}>
                      <Dropdown.Toggle className="dropdown-toggle arrow-none btn btn-light btn-xs">
                        <i className="mdi mdi-wrench"></i>
                      </Dropdown.Toggle>
                      <Dropdown.Menu>
                        <Dropdown.Item
                          onClick={() => {
                            navigate({ search: "?bulk-tags=add" })
                          }}
                        >
                          <i className="mdi mdi-plus me-2 text-muted vertical-middle"></i>
                          Add tags to all
                        </Dropdown.Item>
                        <Dropdown.Item
                          onClick={() => {
                            navigate({ search: "?bulk-tags=remove" })
                          }}
                        >
                          <i className="mdi mdi-minus me-2 text-muted vertical-middle"></i>
                          Remove tags from all
                        </Dropdown.Item>
                      </Dropdown.Menu>
                    </Dropdown>);
                  }
                })()}
                <OverlayTrigger
                  placement="right"
                  delay={{ show: 50, hide: 400 }}
                  overlay={(props) => (
                    <Tooltip id="button-tooltip" {...props}>
                      These tags are not used in data processing, but can help your users once the data is published. We use structured tags, instead of free form text notes, to avoid accidentally hosting Personally Identifiable Information (PII) on the platform. If you don't find the tags you need, feel free to email keenon@cs.stanford.edu and suggest new tags!
                    </Tooltip>
                  )}
                >
                  <i className="mdi mdi-help-circle-outline text-muted vertical-middle" style={{ marginLeft: '5px' }}></i>
                </OverlayTrigger>
              </th>
              {props.cursor.canEdit() ? (
                <th className="border-0">
                  Action
                </th>
              ) : null}
            </tr>
          </thead>
          <tbody>{trialViews}</tbody>
        </Table>
        <Button onClick={() => navigate({ search: "?new-trial" })}>Create new trial</Button>
        {advancedOptions}
      </div>
    </div >
  );
});

export default MocapSubjectView;
