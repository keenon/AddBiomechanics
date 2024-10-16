import shutil
import unittest
from src.kinematics_pass.subject import Subject
from src.kinematics_pass.trial import TrialSegment, Trial
from typing import Dict, List, Any
import os
import nimblephysics as nimble
from inspect import getsourcefile

TESTS_PATH = os.path.dirname(getsourcefile(lambda:0))
DATA_PATH = os.path.join(TESTS_PATH, '..', '..', 'data')
TEST_DATA_PATH = os.path.join(TESTS_PATH, '..', 'test_data')

def reset_test_data(name: str):
    original_path = os.path.join(TEST_DATA_PATH, f'{name}_original')
    live_path = os.path.join(TEST_DATA_PATH, name)
    if os.path.exists(live_path):
        shutil.rmtree(live_path)
    shutil.copytree(original_path, live_path)


class TestSubject(unittest.TestCase):
    def test_parse_json(self):
        subject = Subject()
        json_blob: Dict[str, Any] = {}
        json_blob['massKg'] = 42.0
        json_blob['heightM'] = 2.0
        subject.parse_subject_json(json_blob)
        self.assertEqual(42.0, subject.massKg)
        self.assertEqual(2.0, subject.heightM)

    def test_load_subject_json(self):
        subject = Subject()
        reset_test_data('opencap_test')
        subject.load_subject_json(os.path.join(TEST_DATA_PATH, 'opencap_test', '_subject.json'))

    def test_load_subject(self):
        subject = Subject()
        reset_test_data('opencap_test')
        subject.skeletonPreset = 'custom'
        subject.load_model_files(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_PATH)
        self.assertIsNotNone(subject.customOsim)
        self.assertIsNotNone(subject.skeleton)
        self.assertIsNotNone(subject.markerSet)
        has_custom_joint = False
        for i in range(subject.skeleton.getNumJoints()):
            joint = subject.skeleton.getJoint(i)
            if nimble.dynamics.CustomJoint1.getStaticType() == joint.getType() or nimble.dynamics.CustomJoint2.getStaticType() == joint.getType():
                has_custom_joint = True
        self.assertTrue(has_custom_joint)

    def test_load_subject_simplified(self):
        subject = Subject()
        reset_test_data('opencap_test')
        subject.skeletonPreset = 'custom'
        # If we trigger to export either an SDF or an MJCF, we use simplified joint definitions, so we run a
        # pre-processing step on the data.
        subject.exportSDF = True
        subject.load_model_files(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_PATH)
        self.assertIsNotNone(subject.customOsim)
        self.assertIsNotNone(subject.skeleton)
        self.assertIsNotNone(subject.markerSet)
        for i in range(subject.skeleton.getNumJoints()):
            joint = subject.skeleton.getJoint(i)
            self.assertNotEqual(nimble.dynamics.CustomJoint1.getStaticType(), joint.getType())
            self.assertNotEqual(nimble.dynamics.CustomJoint2.getStaticType(), joint.getType())

    def test_load_trial(self):
        subject = Subject()
        reset_test_data('opencap_test')
        subject.load_trials(os.path.join(TEST_DATA_PATH, 'opencap_test', 'trials'))
        self.assertEqual(4, len(subject.trials))

    def test_load_folder(self):
        subject = Subject()
        reset_test_data('opencap_test')
        subject.load_folder(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_PATH)
        self.assertIsNotNone(subject.customOsim)
        self.assertIsNotNone(subject.skeleton)
        self.assertIsNotNone(subject.markerSet)
        self.assertEqual(4, len(subject.trials))

    def test_segment_trials(self):
        subject = Subject()
        reset_test_data('opencap_test')
        subject.load_folder(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_PATH)
        subject.segment_trials()
        for trial in subject.trials:
            for segment in trial.segments:
                for force_plate in segment.force_plates:
                    self.assertGreater(len(segment.original_marker_observations), 0)
                    self.assertEqual(len(segment.original_marker_observations), len(force_plate.forces))
                    self.assertEqual(len(segment.original_marker_observations), len(force_plate.moments))
                    self.assertEqual(len(segment.original_marker_observations), len(force_plate.centersOfPressure))

    def test_kinematics_fit(self):
        subject = Subject()
        reset_test_data('opencap_test')
        subject.load_folder(os.path.join(TEST_DATA_PATH, 'opencap_test'), DATA_PATH)
        subject.segment_trials()
        subject.kinematicsIterations = 20
        subject.initialIKRestarts = 3
        subject.run_kinematics_pass(DATA_PATH)
        subject_on_disk = subject.create_subject_on_disk('<href>')
        self.assertIsNotNone(subject_on_disk)

class TestRajagopal2015(unittest.TestCase):
    def test_Rajagopal2015(self):
        import opensim as osim

        # Copy the data to the local folder.
        # ----------------------------------
        data_fpath = '../data/Rajagopal2015'
        processed_fpath = os.path.join(data_fpath, 'processed')
        if os.path.isdir(processed_fpath):
            shutil.rmtree(processed_fpath)
        os.mkdir(processed_fpath)
        model_src = os.path.join(data_fpath, 'raw', 'Rajagopal2015_CustomMarkerSet.osim')
        model_dst = os.path.join(data_fpath, 'processed', 'unscaled_generic.osim')
        shutil.copyfile(model_src, model_dst)

        json_src = os.path.join(data_fpath, 'raw', '_subject.json')
        json_dst = os.path.join(processed_fpath, '_subject.json')
        shutil.copyfile(json_src, json_dst)

        trials_fpath = os.path.join(processed_fpath, 'trials')
        if not os.path.isdir(trials_fpath):
            os.mkdir(trials_fpath)
        trial_fpath = os.path.join(trials_fpath, 'walk')
        if not os.path.isdir(trial_fpath):
            os.mkdir(trial_fpath)

        trc_src = os.path.join(data_fpath, 'raw', 'motion_capture_walk.trc')
        trc_dst = os.path.join(trial_fpath, 'markers.trc')
        shutil.copyfile(trc_src, trc_dst)

        grf_src = os.path.join(data_fpath, 'raw', 'grf_walk.mot')
        grf_dst = os.path.join(trial_fpath, 'grf.mot')
        shutil.copyfile(grf_src, grf_dst)

        self.assertTrue(subject_on_disk)

        # # Main path.
        # path = os.path.join(data_fpath, 'processed')
        # if not path.endswith('/'):
        #     path += '/'

        # # Construct the engine.
        # # ---------------------
        # engine = Engine(path=absPath(path),
        #                 output_name='osim_results',
        #                 href='')

        # # Run the pipeline.
        # # -----------------
        # try:
        #     engine.validate_paths()
        #     engine.parse_subject_json()
        #     engine.load_model_files()
        #     engine.configure_marker_fitter()
        #     engine.preprocess_trials()
        #     engine.run_marker_fitting()
        #     if engine.fitDynamics:
        #         engine.run_dynamics_fitting()
        #     engine.write_result_files()
        #     if engine.exportMoco:
        #         engine.run_moco()
        #     engine.generate_readme()
        #     engine.create_output_folder()

        #     # If we succeeded, write an empty JSON file.
        #     with open(engine.errors_json_path, "w") as json_file:
        #         json_file.write("{}")

        # except Error as e:
        #     # If we failed, write a JSON file with the error information.
        #     json_data = json.dumps(e.get_error_dict(), indent=4)
        #     with open(engine.errors_json_path, "w") as json_file:
        #         json_file.write(json_data)

        # # Check the results
        # # -----------------
        # results_fpath = os.path.join(processed_fpath, '_results.json')
        # with open(results_fpath) as file:
        #     results = json.loads(file.read())

        # self.assertAlmostEqual(results['autoAvgRMSE'], 0.014, delta=0.01)
        # self.assertAlmostEqual(results['autoAvgMax'], 0.035, delta=0.01)
        # self.assertAlmostEqual(results['linearResidual'], 3, delta=5)
        # self.assertAlmostEqual(results['angularResidual'], 7, delta=5)

        # # Load the Moco results.
        # moco_results_fpath = os.path.join(processed_fpath, 'osim_results', 'Moco', 'walk_moco.sto')
        # moco_results = osim.TimeSeriesTable(moco_results_fpath)
        # time = moco_results.getIndependentColumn()
        # self.assertEqual(time[0], 0.45)
        # self.assertEqual(time[-1], 2.0)