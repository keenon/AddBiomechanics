#!/usr/bin/python3
"""
engine.py
---------
Description: The main pipeline that servers as the "engine" for the AddBiomechanics data 
             processing software.
Author(s): Keenon Werling, Nicholas Bianco
"""

import sys
import os
import json
import shutil
import traceback
import textwrap
import numpy as np
import nimblephysics as nimble
from nimblephysics.loader import absPath

from kinematics_pass.subject import Subject
from dynamics_pass.acceleration_minimizing_pass import add_acceleration_minimizing_pass
from dynamics_pass.classification_pass import classification_pass
from dynamics_pass.missing_grf_detection import missing_grf_detection
from dynamics_pass.dynamics_pass import dynamics_pass
from moco_pass.moco_pass import moco_pass
from writers.opensim_writer import write_opensim_results
from writers.web_results_writer import write_web_results
from exceptions import Error, LoadingError, TrialPreprocessingError, MarkerFitterError, \
                       DynamicsFitterError, MocoError, WriteError


# Global paths to the geometry and data folders.
GEOMETRY_FOLDER_PATH = absPath('Geometry') + '/'
DATA_FOLDER_PATH = absPath('../../data')

# This metaclass wraps all methods in the Subject class with a try-except block, 
# except for the __init__ method.
class ExceptionHandlingMeta(type):
    # Only the methods in this map will be wrapped with a try-except block.
    EXCEPTION_MAP = {
        'run_loading': LoadingError,
        'run_preprocessing': TrialPreprocessingError,
        'run_kinematics_fitting': MarkerFitterError,
        'run_dynamics_fitting': DynamicsFitterError,
        'run_write_openim': WriteError,
        'run_moco': MocoError,
        'run_zip_opensim': WriteError,
        'run_write_web': WriteError,
        'run_write_b3d': WriteError
    }

    def __new__(cls, name, bases, attrs):
        for attr_name, attr_value in attrs.items():
            if attr_name not in cls.EXCEPTION_MAP:
                continue
            if callable(attr_value):
                attrs[attr_name] = cls.wrap_method(attr_value)
        return super().__new__(cls, name, bases, attrs)

    @staticmethod
    def wrap_method(method):
        def wrapper(*args, **kwargs):
            try:
                method(*args, **kwargs)
            except Exception as e:
                stack_trace = textwrap.indent('\n'.join(traceback.format_stack()), '  ')
                msg = f"Exception caught in {method.__name__}: {e} {stack_trace}"
                exc_type = ExceptionHandlingMeta.EXCEPTION_MAP.get(method.__name__, 
                                                                   Exception)
                raise exc_type(msg)

        return wrapper
    

class Engine(metaclass=ExceptionHandlingMeta):
    def __init__(self, path, output_name, href):
        self.path = path
        self.output_name = output_name
        self.href = href
        self.subject = Subject()
        self.subject_on_disk: nimble.biomechanics.SubjectOnDisk = None

    def run_loading(self):
        print('Loading folder ' + self.path, flush=True)
        self.subject.load_folder(self.path, DATA_FOLDER_PATH)

    def run_preprocessing(self):
        # This will attempt to un-swap the marker data, by using a number of beam 
        # search heuristics.
        print('Cleaning marker data', flush=True)
        self.subject.clean_marker_traces()
        # This auto-segments the trials, without throwing away any segments. The 
        # segments are split based on which parts of the trial have GRF data, and also 
        # based on ensuring that the segments don't get beyond a certain length.
        print('Segmenting trials', flush=True)
        self.subject.segment_trials()

    def run_kinematics_fitting(self):
        # The kinematics fit will fit the body scales, marker offsets, and motion of the 
        # subject, to all the trial segments that have not yet thrown an error during 
        # loading.
        print('Running kinematics fit', flush=True)
        self.subject.run_kinematics_pass(DATA_FOLDER_PATH)

        # This will create a B3D object in memory for the current fit of the subject. 
        # This can be used at any point to write out the B3D file, but also can be used 
        # as our working object as we run subsequent pipeline steps.
        self.subject_on_disk = self.subject.create_subject_on_disk(self.href)

    def run_dynamics_fitting(self):
        print('Running acceleration minimizing pass...', flush=True)
        print('-> This pass runs a simple least-squares optimization to minimize the '
              'acceleration of each DOF for the subject over each trial, subject to '
              'also tracking the original trajectory closely. This is akin to a '
              'Butterworth lowpass filtering step, except that it is better able to '
              'ensure that the high frequency noise in the finite-differenced '
              'accelerations is knocked down, which makes the torque plots smoother.', 
              flush=True)
        add_acceleration_minimizing_pass(self.subject_on_disk)

        print('Heuristically classifying trials...', flush=True)
        print('-> This runs a set of heuristics to classify trials as overground, '
              'treadmill, static, or other. This coarse classification is useful for '
              'subsequent stages in the pipeline, like the missing GRF detector, '
              'and may be useful for downstream data science as well.', flush=True)
        classification_pass(self.subject_on_disk)

        if not self.subject.disableDynamics:
            print('Detecting missing GRF frames...', flush=True)
            print('-> This runs a set of heuristics to detect frames in the input data '
                  'where we believe the subject is in contact with the ground, but '
                  'there is no force plate data. These heuristics are deliberately a '
                  'bit too aggressive in marking frames as "missing GRF", in order to '
                  'make sure we get almost all the frames where there actually is '
                  'missing GRF labeled correctly. This means the dataset of frames '
                  'which are marked as not missing GRF are going to be very clean, but '
                  'smaller than we might have with more selective heuristics.', 
                  flush=True)
            missing_grf_detection(self.subject_on_disk)

            print('Running dynamics pass...', flush=True)
            print('-> This pass runs the dynamics pipeline on the subject, which '
                  'jointly optimizes a bunch of properties just like the kinematics '
                  'pass, except now we will balance the marker RMS _and_ the residual '
                  'RMS.', flush=True)
            dynamics_pass(self.subject_on_disk)

    def run_write_openim(self):
        # This will write out a folder of OpenSim results files.
        print('Writing OpenSim results', flush=True)
        write_opensim_results(self.subject_on_disk, self.path, self.output_name, 
                              GEOMETRY_FOLDER_PATH)

    def run_moco(self):
        if self.subject.runMoco:
            print('Running Moco optimization pass...', flush=True)
            print('-> This pass utilizes the results from the kinematics and dynamics '
                  'pass as inputs to a trajectory optimization problem solved by '
                  'OpenSim Moco. This problem solves for the muscle excitations and '
                  'activations that best match the observed motion and ground reaction '
                  'forces.', flush=True)
            moco_pass(self.subject_on_disk, self.path, self.output_name, 
                      self.subject.genericMassKg, self.subject.genericHeightM)

    def run_zip_opensim(self):
        print('Zipping up OpenSim files...', flush=True)
        shutil.make_archive(self.path + self.output_name, 'zip', root_dir=self.path, 
                            base_dir=self.output_name)
        print('Finished outputting OpenSim files.', flush=True)

    def run_write_web(self):
        # This will write out all the results to display in the web UI back into the 
        # existing folder structure
        print('Writing web visualizer results', flush=True)
        write_web_results(self.subject_on_disk, GEOMETRY_FOLDER_PATH, self.path)

    def run_write_b3d(self):
        # This will write out a B3D file
        print('Writing B3D file encoded results', flush=True)
        nimble.biomechanics.SubjectOnDisk.writeB3D(self.path + self.output_name + '.b3d', 
                                                   self.subject_on_disk.getHeaderProto())

        # Check if we have any dynamics trials
        pass_index = -1
        for p in range(self.subject_on_disk.getNumProcessingPasses()):
            if (self.subject_on_disk.getProcessingPassType(p) == 
                nimble.biomechanics.ProcessingPassType.DYNAMICS):
                pass_index = p

        num_dynamics_trials = 0
        include_dynamics_trials = []
        if pass_index > -1:
            for trial in range(self.subject_on_disk.getNumTrials()):
                if self.subject_on_disk.getTrialNumProcessingPasses(trial) > pass_index:
                    include_dynamics_trials.append(True)
                    num_dynamics_trials += 1
                else:
                    include_dynamics_trials.append(False)

        if num_dynamics_trials > 0:
            print('Writing B3D file encoded results which have been filtered to only '
                  'include dynamics trials', flush=True)
            self.subject_on_disk.getHeaderProto().filterTrials(include_dynamics_trials)
            nimble.biomechanics.SubjectOnDisk.writeB3D(
                self.path + self.output_name + '_dynamics_trials_only.b3d', 
                self.subject_on_disk.getHeaderProto())
        else:
            print('No dynamics trials found', flush=True)
            # Write a flag file to the output directory to indicate that no dynamics 
            # trials were found.
            with open(self.path + 'NO_DYNAMICS_TRIALS', 'w') as f:
                f.write('No dynamics trials found')

    def run(self):
        try:
            self.run_loading()
            self.run_preprocessing()
            self.run_kinematics_fitting()
            self.run_dynamics_fitting()
            self.run_write_openim()
            self.run_moco()
            self.run_zip_opensim()
            self.run_write_web()
            self.run_write_b3d()

        except Error as e:
            # If we failed, write a JSON file with the error information.
            print(e, flush=True)
            json_data = json.dumps(e.get_error_dict(), indent=4)
            with open(self.path + '_errors.json', "w") as json_file:
                print('ERRORS:', flush=True)
                print(json_data, flush=True)
                json_file.write(json_data)
            # Return a non-zero exit code to tell the `mocap_server.py` that we failed, 
            # so it can write an ERROR flag
            exit(1)


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

    # Run the engine.
    engine = Engine(path, output_name, href)
    engine.run()

if __name__ == "__main__":
    main()
