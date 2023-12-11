import nimblephysics as nimble
import argparse
from typing import Dict, List, Optional
import os
import numpy as np


def export_csv_from_b3d(file_path: str,
                        trials: List[int],
                        geometry: Optional[str] = None):
    if geometry is None:
        # Check if the "./Geometry" folder exists, and if not, download it
        if not os.path.exists('./Geometry'):
            print('Downloading the Geometry folder from https://addbiomechanics.org/resources/Geometry.zip')
            exit_code = os.system('wget https://addbiomechanics.org/resources/Geometry.zip')
            if exit_code != 0:
                print('ERROR: Failed to download Geometry.zip. You may need to install wget. If you are on a Mac, '
                      'try running "brew install wget"')
                return False
            os.system('unzip ./Geometry.zip')
            os.system('rm ./Geometry.zip')
        geometry = './Geometry'
    print('Using Geometry folder: ' + geometry)
    geometry = os.path.abspath(geometry)
    if not geometry.endswith('/'):
        geometry += '/'
    print(' > Converted to absolute path: ' + geometry)

    print('Reading SubjectOnDisk at ' + file_path + '...')
    subject: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(file_path)

    skel = subject.readSkel(0, geometry)

    mesh_paths: Dict[str, (str, np.ndarray)] = {}
    body_names: List[str] = []
    for b in range(0, skel.getNumBodyNodes()):
        body_node: nimble.dynamics.BodyNode = skel.getBodyNode(b)
        for k in range(body_node.getNumShapeNodes()):
            name = str(b) + '_' + str(k)
            body_names.append(name)
            shape_node: nimble.dynamics.ShapeNode = body_node.getShapeNode(k)
            shape: nimble.dynamics.Shape = shape_node.getShape()
            mesh_shape: nimble.dynamics.MeshShape = shape.asMeshShape()
            mesh_paths[name] = (mesh_shape.getMeshPath(), mesh_shape.getScale())
    # Save the mesh paths to a CSV file
    with open('mesh_paths.csv', 'w') as f:
        f.write('name,path,scale_x,scale_y,scale_z\n')
        for key in mesh_paths.keys():
            path, scale = mesh_paths[key]
            f.write("%s,%s," % (key, path))
            f.write("%f,%f,%f\n" % (scale[0], scale[1], scale[2]))

    loaded: List[nimble.biomechanics.Frame] = []
    print('Reading frames...')
    for trial in trials:
        print('DT = ' + str(subject.getTrialTimestep(trial)))
        print('Name = ' + subject.getTrialName(trial))

        loaded.extend(subject.readFrames(
            trial,
            0,
            subject.getTrialLength(trial),
            True,
            True))

    # if len(loaded) > 800:
    #     loaded = loaded[0:800]

    rotation = np.zeros((3, 3))
    rotation[0, 0] = 1
    rotation[1, 2] = -1
    rotation[2, 1] = 1

    with open('frames.csv', 'w') as f:
        for i, body in enumerate(body_names):
            f.write('t,')
            f.write(body + '_x,' + body + '_y,' + body + '_z,')
            f.write(body + '_rx,' + body + '_ry,' + body + '_rz')
            if i < len(body_names) - 1:
                f.write(',')
        f.write('\n')

        for frame in range(len(loaded)):
            skel.setPositions(loaded[frame].processingPasses[0].pos)

            # Render assigned force plates
            # for i in range(0, subject.getNumForcePlates(trial)):
            #     cop = loaded[frame].rawForcePlateCenterOfPressures[i]
            #     force: np.ndarray = loaded[frame].rawForcePlateForces[i] * 0.001
            #     color: np.ndarray = np.array([1, 1, 0, 1])

            f.write(str(frame) + ',')
            for b in range(0, skel.getNumBodyNodes()):
                body_node: nimble.dynamics.BodyNode = skel.getBodyNode(b)
                for k in range(body_node.getNumShapeNodes()):
                    shape_node: nimble.dynamics.ShapeNode = body_node.getShapeNode(k)
                    world_transform: nimble.math.Isometry3 = shape_node.getWorldTransform()
                    pos: np.ndarray = rotation @ world_transform.translation()
                    rot: np.ndarray = rotation @ world_transform.rotation()
                    euler_angles: np.ndarray = nimble.math.matrixToEulerXYZ(rot)
                    f.write(str(pos[0]) + ',' + str(pos[1]) + ',' + str(pos[2]) + ',')
                    f.write(str(euler_angles[0]) + ',' + str(euler_angles[1]) + ',' + str(euler_angles[2]))
                    if b == skel.getNumBodyNodes() - 1 and k == body_node.getNumShapeNodes() - 1:
                        f.write('\n')
                    else:
                        f.write(',')

    with open('forces.csv', 'w') as f:
        use_contact_bodies: bool = False
        if use_contact_bodies:
            contact_bodies = subject.getGroundForceBodies()
            f.write('t,')
            for i in range(0, len(contact_bodies)):
                f.write(contact_bodies[i] + '_x1,' + contact_bodies[i] + '_y1,' + contact_bodies[i] + '_z1,')
                f.write(contact_bodies[i] + '_x2,' + contact_bodies[i] + '_y2,' + contact_bodies[i] + '_z2')
                if i < len(contact_bodies) - 1:
                    f.write(',')
            f.write('\n')
            for frame in range(len(loaded)):
                f.write(str(frame) + ',')
                for i in range(0, len(contact_bodies)):
                    cop = rotation @ loaded[frame].processingPasses[-1].groundContactCenterOfPressure[i * 3:(i + 1) * 3]
                    force = rotation @ loaded[frame].processingPasses[-1].groundContactForce[i * 3:(i + 1) * 3] * 0.001
                    end = cop + force
                    f.write(str(cop[0]) + ',' + str(cop[1]) + ',' + str(cop[2]) + ',')
                    f.write(str(end[0]) + ',' + str(end[1]) + ',' + str(end[2]))
                    if i < len(contact_bodies) - 1:
                        f.write(',')
                f.write('\n')
        else:
            num_force_plates: int = max([subject.getNumForcePlates(trial) for trial in trials])
            f.write('t,')
            for i in range(0, num_force_plates):
                f.write(str(i) + '_x1,' + str(i) + '_y1,' + str(i) + '_z1,')
                f.write(str(i) + '_x2,' + str(i) + '_y2,' + str(i) + '_z2')
                if i < num_force_plates - 1:
                    f.write(',')
            f.write('\n')
            for frame in range(len(loaded)):
                f.write(str(frame) + ',')
                for p in range(0, num_force_plates):
                    if p < len(loaded[frame].rawForcePlateCenterOfPressures):
                        cop = rotation @ loaded[frame].rawForcePlateCenterOfPressures[p]
                        force = rotation @ loaded[frame].rawForcePlateForces[p] * 0.001
                    else:
                        cop = np.zeros(3)
                        force = np.zeros(3)
                    end = cop + force
                    f.write(str(cop[0]) + ',' + str(cop[1]) + ',' + str(cop[2]) + ',')
                    f.write(str(end[0]) + ',' + str(end[1]) + ',' + str(end[2]))
                    if p < num_force_plates - 1:
                        f.write(',')
                f.write('\n')



def main():
    # Create the parser
    parser = argparse.ArgumentParser(description="Export a B3D to a CSV format that can be read in from Blender.")

    # Add arguments
    parser.add_argument("--file-path", type=str, help="Path to the B3D file to export", default="./data/falisse_subject_1.b3d")
    parser.add_argument("-t", "--trials", type=int, help="Trials to export", nargs='+', default=[22,23])
    parser.add_argument("-g", "--geometry", type=str, help="Path to the Geometry folder", default=None)

    # Parse arguments
    args = parser.parse_args()

    # Accessing arguments
    file_path: str = os.path.abspath(args.file_path)
    trials: List[int] = args.trials
    geometry: Optional[str] = args.geometry

    export_csv_from_b3d(file_path, trials, geometry)


# Standard boilerplate to call the main() function
if __name__ == "__main__":
    main()