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
from subject import Subject, ProcessingStatus

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

        # This plausibly skips kinematics, with placeholder 0s for (most of) the necessary kinematics results.
        # for trial in subject.trials:
        #     for segment in trial.segments:
        #         segment.kinematics_status = ProcessingStatus.FINISHED
        #         num_steps = len(segment.marker_observations)
        #         segment.kinematics_poses = np.zeros((subject.skeleton.getNumDofs(), num_steps))
        #         dummy_results: nimble.biomechanics.MarkerInitialization = nimble.biomechanics.MarkerInitialization()
        #         dummy_results.poses = segment.kinematics_poses
        #         dummy_results.updatedMarkerMap = subject.markerSet
        #         dummy_results.groupScales = subject.skeleton.getGroupScales()
        #         dummy_results.joints = []
        #         dummy_results.jointWeights = np.zeros(0)
        #         dummy_results.axisWeights = np.zeros(0)
        #         dummy_results.jointAxis = np.zeros((0, num_steps))
        #         dummy_results.jointCenters = np.zeros((0, num_steps))
        #         segment.marker_fitter_result = dummy_results

        # This will lowpass filter all the input kinematics data
        print('Running lowpass filter', flush=True)
        subject.lowpass_filter()

        # The dynamics fit will fit the dynamics parameters of the subject, to all the trial segments that have not yet
        # thrown an error during loading or kinematics fitting.
        if not subject.disableDynamics:
            print('Running dynamics fit', flush=True)
            subject.run_dynamics_fit()
        # This will write out a folder of OpenSim results files.
        print('Writing OpenSim results', flush=True)
        subject.write_opensim_results(path + output_name,
                                      DATA_FOLDER_PATH)
        # This will write out all the results to display in the web UI back into the existing folder structure
        print('Writing web visualizer results', flush=True)
        subject.write_web_results(path)
        # This will write out a B3D file
        print('Writing B3D file encoded results', flush=True)
        subject.write_b3d_file(path + output_name + '.b3d', path + output_name, href)
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