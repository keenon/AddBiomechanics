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

    if (rootNode.nodeName === "parsererror") {
      const errorMsg = rootNode.textContent || "Unknown parser error"; // Extract the error message from the node's text content
      console.error("Error parsing XML:", errorMsg, opensimFileText.substring(0, 100)+'...');
      return [];
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

export { getOpenSimBodyList, validateOpenSimFile };
