import os
import shutil
import unittest
from typing import Dict, List, Any
from inspect import getsourcefile

import numpy as np
import opensim as osim
import nimblephysics as nimble

from kinematics_pass.subject import Subject
from dynamics_pass.acceleration_minimizing_pass import add_acceleration_minimizing_pass
from dynamics_pass.classification_pass import classification_pass
from dynamics_pass.missing_grf_detection import missing_grf_detection
from dynamics_pass.dynamics_pass import dynamics_pass
from moco_pass.moco_pass import moco_pass
from writers.opensim_writer import write_opensim_results


TESTS_PATH = os.path.dirname(getsourcefile(lambda:0))
TEST_DATA_PATH = os.path.join(TESTS_PATH, 'data')
DATA_FOLDER_PATH = os.path.join(TESTS_PATH, '..', '..', 'data')
GEOMETRY_FOLDER_PATH = os.path.join(TESTS_PATH, '..', 'Geometry')


def reset_test_data(name: str):
    original_path = os.path.join(TEST_DATA_PATH, f'{name}_original')
    live_path = os.path.join(TEST_DATA_PATH, name)
    if os.path.exists(live_path):
        shutil.rmtree(live_path)
    shutil.copytree(original_path, live_path)


# class TestSubject(unittest.TestCase):
#     def test_parse_json(self):
#         subject = Subject()
#         json_blob: Dict[str, Any] = {}
#         json_blob['massKg'] = 42.0
#         json_blob['heightM'] = 2.0
#         subject.parse_subject_json(json_blob)
#         self.assertEqual(42.0, subject.massKg)
#         self.assertEqual(2.0, subject.heightM)

#     def test_load_subject_json(self):
#         subject = Subject()
#         reset_test_data('opencap_test')
#         subject.load_subject_json(os.path.join(TEST_DATA_PATH, 'opencap_test', '_subject.json'))

#     def test_load_subject(self):
#         subject = Subject()
#         reset_test_data('opencap_test')
#         subject.skeletonPreset = 'custom'
#         subject.load_model_files(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_FOLDER_PATH)
#         self.assertIsNotNone(subject.customOsim)
#         self.assertIsNotNone(subject.skeleton)
#         self.assertIsNotNone(subject.markerSet)
#         has_custom_joint = False
#         for i in range(subject.skeleton.getNumJoints()):
#             joint = subject.skeleton.getJoint(i)
#             if nimble.dynamics.CustomJoint1.getStaticType() == joint.getType() or nimble.dynamics.CustomJoint2.getStaticType() == joint.getType():
#                 has_custom_joint = True
#         self.assertTrue(has_custom_joint)

#     def test_load_subject_simplified(self):
#         subject = Subject()
#         reset_test_data('opencap_test')
#         subject.skeletonPreset = 'custom'
#         # If we trigger to export either an SDF or an MJCF, we use simplified joint definitions, so we run a
#         # pre-processing step on the data.
#         subject.exportSDF = True
#         subject.load_model_files(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_FOLDER_PATH)
#         self.assertIsNotNone(subject.customOsim)
#         self.assertIsNotNone(subject.skeleton)
#         self.assertIsNotNone(subject.markerSet)
#         for i in range(subject.skeleton.getNumJoints()):
#             joint = subject.skeleton.getJoint(i)
#             self.assertNotEqual(nimble.dynamics.CustomJoint1.getStaticType(), joint.getType())
#             self.assertNotEqual(nimble.dynamics.CustomJoint2.getStaticType(), joint.getType())

#     def test_load_trial(self):
#         subject = Subject()
#         reset_test_data('opencap_test')
#         subject.load_trials(os.path.join(TEST_DATA_PATH, 'opencap_test', 'trials'))
#         self.assertEqual(4, len(subject.trials))

#     def test_load_folder(self):
#         subject = Subject()
#         reset_test_data('opencap_test')
#         subject.load_folder(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_FOLDER_PATH)
#         self.assertIsNotNone(subject.customOsim)
#         self.assertIsNotNone(subject.skeleton)
#         self.assertIsNotNone(subject.markerSet)
#         self.assertEqual(4, len(subject.trials))

#     def test_segment_trials(self):
#         subject = Subject()
#         reset_test_data('opencap_test')
#         subject.load_folder(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_FOLDER_PATH)
#         subject.segment_trials()
#         for trial in subject.trials:
#             for segment in trial.segments:
#                 for force_plate in segment.force_plates:
#                     self.assertGreater(len(segment.original_marker_observations), 0)
#                     self.assertEqual(len(segment.original_marker_observations), len(force_plate.forces))
#                     self.assertEqual(len(segment.original_marker_observations), len(force_plate.moments))
#                     self.assertEqual(len(segment.original_marker_observations), len(force_plate.centersOfPressure))

#     def test_kinematics_fit(self):
#         subject = Subject()
#         reset_test_data('opencap_test')
#         subject.load_folder(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_FOLDER_PATH)
#         subject.segment_trials()
#         subject.kinematicsIterations = 20
#         subject.initialIKRestarts = 3
#         subject.run_kinematics_pass(DATA_FOLDER_PATH)
#         subject_on_disk = subject.create_subject_on_disk('<href>')
#         self.assertIsNotNone(subject_on_disk)


# class TestLoadingNoData(unittest.TestCase):
#     def test_load_trial(self):
#         subject = Subject()
#         reset_test_data('rajagopal2015_no_data')
#         try:
#             subject.load_trials(os.path.join(TEST_DATA_PATH, 
#                                              'rajagopal2015_no_data', 'trials'))
#         except Exception as e:
#             expected = 'tests/data/rajagopal2015_no_data/trials/" does not exist'
#             self.assertTrue(expected in str(e))     

#     def test_load_folder(self):
#         subject = Subject()
#         reset_test_data('rajagopal2015_no_data')
#         try:    
#             subject.load_folder(os.path.join(TEST_DATA_PATH, 
#                                              'rajagopal2015_no_data'), DATA_FOLDER_PATH)
#         except Exception as e:
#             self.assertEqual("LoadingError", e.type)
#             expected = 'tests/data/rajagopal2015_no_data/trials/" does not exist'
#             self.assertTrue(expected in e.original_message)    


class TestRajagopal2015(unittest.TestCase):
    def test_Rajagopal2015(self):
        reset_test_data('rajagopal2015')
        path = os.path.join(TEST_DATA_PATH, 'rajagopal2015')
        if not path.endswith('/'):
            path += '/'
        output_name = 'osim_results'

        subject = Subject()
        subject.load_folder(os.path.join(TEST_DATA_PATH, 'rajagopal2015'), DATA_FOLDER_PATH)
        subject.segment_trials()
        import pdb; pdb.set_trace()

        subject.run_kinematics_pass(DATA_FOLDER_PATH)
        subject_on_disk = subject.create_subject_on_disk('<href>')
        add_acceleration_minimizing_pass(subject_on_disk)
        classification_pass(subject_on_disk)
    
        # The "missing GRF detection" step removes many valid timesteps due to the set 
        # ground reaction force heuristics. Manually set the valid ground reactions 
        # time range to [0.6, 1.75].
        # header_proto = subject_on_disk.getHeaderProto()
        # trial_protos = header_proto.getTrials()
        # dt = trial_protos[0].getTimestep()
        # start_time = trial_protos[0].getOriginalTrialStartTime()
        # end_time = trial_protos[0].getOriginalTrialEndTime()
        # times = np.arange(start_time, end_time, dt)

        # missing_grf: List[nimble.biomechanics.MissingGRFReason] = []
        # for time in times:
        #     if time > 0.6 and time < 1.75:
        #         missing_grf.append(nimble.biomechanics.MissingGRFReason.notMissingGRF)
        #     else:
        #         missing_grf.append(nimble.biomechanics.MissingGRFReason.zeroForceFrame)
        # trial_protos[0].setMissingGRFReason(missing_grf)

        # Run the dynamics and Moco pass.
        missing_grf_detection(subject_on_disk)

        dynamics_pass(subject_on_disk)
        # b3d_path = os.path.join(path, 'rajagopal2015.b3d')
        # subject_on_disk.writeB3D(b3d_path, subject_on_disk.getHeaderProto())
        # subject_on_disk = nimble.biomechanics.SubjectOnDisk(b3d_path)
        # subject_on_disk.loadAllFrames(True)
        write_opensim_results(subject_on_disk, path, output_name, GEOMETRY_FOLDER_PATH)
        moco_pass(subject_on_disk, path, output_name, subject.genericMassKg, 
                      subject.genericHeightM)
        
        # Load the Moco results.
        header_proto = subject_on_disk.getHeaderProto()
        trial_protos = header_proto.getTrials()
        trial_name = trial_protos[0].getName()
        solution_fpath = os.path.join(path, output_name, 'Moco', 
                                      f'{trial_name}_moco.sto')
        solution = osim.TimeSeriesTable(solution_fpath)
        self.assertEqual(solution.getTableMetaDataString('success'), 'true')
        self.assertEqual(solution.getTableMetaDataString('status'), 'Solve_Succeeded')

# TODO: enable when we add support for muscle paths dependent on more than 6
#       coordinates.
# class TestOpenCap(unittest.TestCase):
#     def test_TestOpenCap(self):
#         reset_test_data('opencap_test')
#         path = os.path.join(TEST_DATA_PATH, 'opencap_test')
#         if not path.endswith('/'):
#             path += '/'
#         output_name = 'osim_results'

#         subject = Subject()
#         subject.load_folder(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_FOLDER_PATH)
#         subject.segment_trials()
#         subject.run_kinematics_pass(DATA_FOLDER_PATH)
#         subject_on_disk = subject.create_subject_on_disk('<href>')
#         add_acceleration_minimizing_pass(subject_on_disk)
#         classification_pass(subject_on_disk)
#         missing_grf_detection(subject_on_disk)
#         dynamics_pass(subject_on_disk)
#         write_opensim_results(subject_on_disk, path, output_name, GEOMETRY_FOLDER_PATH)
#         moco_pass(subject_on_disk, path, output_name, subject.genericMassKg, 
#                   subject.genericHeightM)

