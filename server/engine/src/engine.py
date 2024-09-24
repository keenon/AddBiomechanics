#!/usr/bin/python3
"""
engine.py
---------
Description: The main pipeline that servers as the "engine" for the AddBiomechanics data processing software.
Author(s): Keenon Werling, Nicholas Bianco
"""

import sys
import os
from nimblephysics.loader import absPath
import json
from exceptions import Error
from kinematics_pass.subject import Subject, ProcessingStatus
from passes.acc_minimize_pass_debug import add_acc_minimize_pass
from passes.missing_grf_detection_pass import missing_grf_detection_pass
from passes.dynamics_pass import dynamics_pass

import numpy as np
import nimblephysics as nimble

# Global paths to the geometry and data folders.
GEOMETRY_FOLDER_PATH = absPath('Geometry')
DATA_FOLDER_PATH = absPath('../../data')

def main():
    # Process input arguments.
    # ------------------------
    print(sys.argv, flush=True)
    if len(sys.argv) < 2:
        raise RuntimeError('Must provide a path to a subject folder.')

    # Subject folder path.
    path = os.path.abspath(sys.argv[1])
    if not path.endswith('/'):
        path += '/'

    # Output name.
    output_name = sys.argv[2] if len(sys.argv) > 2 else 'osim_results'

    # Subject href.
    href = sys.argv[3] if len(sys.argv) > 3 else ''

    # Construct the subject
    # ---------------------
    subject = Subject()
    try:
        print('Loading folder ' + path, flush=True)
        subject.load_folder(path, DATA_FOLDER_PATH)
        # This auto-segments the trials, without throwing away any segments. The segments are split based on which parts
        # of the trial have GRF data, and also based on ensuring that the segments don't get beyond a certain length.
        print('Segmenting trials', flush=True)
        subject.segment_trials()
        # The kinematics fit will fit the body scales, marker offsets, and motion of the subject, to all the trial
        # segments that have not yet thrown an error during loading.
        print('Running kinematics fit', flush=True)
        subject.run_kinematics_fit(DATA_FOLDER_PATH)
        # This will create a B3D object in memory for the current fit of the subject. This can be used at any point to
        # write out the B3D file, but also can be used as our working object as we run subsequent pipeline steps.
        subject_on_disk: nimble.biomechanics.SubjectOnDisk = subject.create_subject_on_disk(href)

        print('Writing B3D file encoded kinematics results', flush=True)
        nimble.biomechanics.SubjectOnDisk.writeB3D(path + output_name + '_kinematics.b3d', subject_on_disk.getHeaderProto())

        print('Trying to read back the kinematics results', flush=True)
        read_back_subject: nimble.biomechanics.SubjectOnDisk = nimble.biomechanics.SubjectOnDisk(path + output_name + '_kinematics.b3d')
        read_back_subject.loadAllFrames(doNotStandardizeForcePlateData=True)
        print('Running acc minimizing pass on read back subject', flush=True)
        add_acc_minimize_pass(read_back_subject)

        print('Running acc minimizing pass on in memory subject', flush=True)
        add_acc_minimize_pass(subject_on_disk)

        print('Writing B3D file encoded acc minimizing results', flush=True)
        nimble.biomechanics.SubjectOnDisk.writeB3D(path + output_name + '_acc_min.b3d', subject_on_disk.getHeaderProto())

        missing_grf_detection_pass(subject_on_disk)

        print('Writing B3D file encoded GRF detection results', flush=True)
        nimble.biomechanics.SubjectOnDisk.writeB3D(path + output_name + '_missing_grf.b3d', subject_on_disk.getHeaderProto())

        dynamics_pass(subject_on_disk)

        # # This will write out a folder of OpenSim results files.
        # print('Writing OpenSim results', flush=True)
        # subject.write_opensim_results(path + output_name,
        #                               DATA_FOLDER_PATH)
        # # This will write out all the results to display in the web UI back into the existing folder structure
        # print('Writing web visualizer results', flush=True)
        # subject.write_web_results(path)

        # # This will write out a B3D file
        print('Writing B3D file encoded results', flush=True)
        nimble.biomechanics.SubjectOnDisk.writeB3D(path + output_name + '.b3d', subject_on_disk.getHeaderProto())
    except Error as e:
        # If we failed, write a JSON file with the error information.
        print(e, flush=True)
        json_data = json.dumps(e.get_error_dict(), indent=4)
        with open(path + '_errors.json', "w") as json_file:
            print('ERRORS:', flush=True)
            print(json_data, flush=True)
            json_file.write(json_data)
        # Return a non-zero exit code to tell the `mocap_server.py` that we failed, so it can write an ERROR flag
        exit(1)


if __name__ == "__main__":
    main()