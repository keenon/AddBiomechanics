"""
testing.py
----------
Description: Testing for the AddBiomechanics processing engine.
Author(s): Nicholas Bianco
"""

import os
import unittest
import nimblephysics as nimble
from typing import List
import numpy as np
from nimblephysics.loader import absPath
from engine import Engine
import shutil
import json
from helpers import detect_nonzero_force_segments, filter_nonzero_force_segments, \
                    reconcile_markered_and_nonzero_force_segments
from exceptions import Error

DATA_FOLDER_PATH = absPath('../data')
GEOMETRY_FOLDER_PATH = absPath('Geometry')


class TestTrialSegmentation(unittest.TestCase):
    def test_detectNonZeroForceSegments(self):
        # Create force plate data with intermittent loads.
        timestamps = np.linspace(0, 6.0, 601)
        totalLoad = np.zeros(len(timestamps))

        # Add a legitimate load segment.
        totalLoad[50:100] = 1.0
        # Add a load segment that is too short.
        totalLoad[250:254] = 1.0
        # Add two load segments that should be merged together.
        totalLoad[300:340] = 1.0
        totalLoad[360:400] = 1.0
        # Add a segment that has load up until the final time point.
        totalLoad[550:601] = 1.0

        # Detect the non-zero force segments.
        nonzeroForceSegments = detect_nonzero_force_segments(timestamps, totalLoad)

        # Check that the correct segments were detected, before filtering.
        self.assertEqual(len(nonzeroForceSegments), 5)
        self.assertEqual(nonzeroForceSegments[0], (0.5, 1.0))
        self.assertEqual(nonzeroForceSegments[1][0], 2.5)
        self.assertAlmostEqual(nonzeroForceSegments[1][1], 2.54, places=5)
        self.assertEqual(nonzeroForceSegments[2], (3.0, 3.4))
        self.assertEqual(nonzeroForceSegments[3], (3.6, 4.0))
        self.assertEqual(nonzeroForceSegments[4], (5.5, 6.0))

        # Now filter the segments.
        nonzeroForceSegments = filter_nonzero_force_segments(nonzeroForceSegments, 0.05, 1.0)

        # Check that the correct segments were detected, after filtering.
        self.assertEqual(len(nonzeroForceSegments), 3)
        self.assertEqual(nonzeroForceSegments[0], (0.5, 1.0))
        self.assertEqual(nonzeroForceSegments[1], (3.0, 4.0))
        self.assertEqual(nonzeroForceSegments[2], (5.5, 6.0))

    def test_Camargo2021(self):
        # Load the data.
        trcFilePath = DATA_FOLDER_PATH + '/Camargo2021/levelground_ccw_fast_01_01.trc'
        grfFilePath = DATA_FOLDER_PATH + '/Camargo2021/levelground_ccw_fast_01_01_grf.mot'
        trcFile: nimble.biomechanics.OpenSimTRC = nimble.biomechanics.OpenSimParser.loadTRC(trcFilePath)
        forcePlates: List[nimble.biomechanics.ForcePlate] = nimble.biomechanics.OpenSimParser.loadGRF(
            grfFilePath, trcFile.framesPerSecond)

        # Compute the total load.
        totalLoad = np.zeros(len(forcePlates[0].timestamps))
        for itime in range(len(totalLoad)):
            totalForce = 0
            totalMoment = 0
            for forcePlate in forcePlates:
                totalForce += np.linalg.norm(forcePlate.forces[itime])
                totalMoment += np.linalg.norm(forcePlate.moments[itime])
            totalLoad[itime] = totalForce + totalMoment

        # Detect the non-zero force segments.
        nonzeroForceSegments = detect_nonzero_force_segments(forcePlates[0].timestamps, totalLoad)

        # Filter the segments.
        nonzeroForceSegments = filter_nonzero_force_segments(nonzeroForceSegments, 0.05, 1.0)

        # Check that the correct segments were detected.
        self.assertEqual(len(nonzeroForceSegments), 3)
        self.assertEqual(nonzeroForceSegments[0], (0.005, 5.92))
        self.assertEqual(nonzeroForceSegments[1], (7.365, 8.455))
        self.assertEqual(nonzeroForceSegments[2], (11.895, 15.335))

    def test_reconcileMarkeredAndNonzeroForceSegments(self):
        # Create force plate data with intermittent loads.
        timestamps = np.linspace(0, 10.0, 1001)

        # Create marker segments
        markerSegments = list()
        markerSegments.append(timestamps[0:200])
        markerSegments.append(timestamps[500:600])
        markerSegments.append(timestamps[800:1000])

        # Create force segments
        forceSegments = list()
        forceSegments.append(timestamps[100:300])
        forceSegments.append(timestamps[350:400])
        forceSegments.append(timestamps[550:600])
        forceSegments.append(timestamps[700:950])

        # Reconcile the segments.
        finalSegments = reconcile_markered_and_nonzero_force_segments(timestamps, markerSegments, forceSegments)

        # Check that the correct segments were detected.
        self.assertEqual(len(finalSegments), 3)
        self.assertEqual(finalSegments[0], (1.0, 2.0))
        self.assertEqual(finalSegments[1], (5.5, 6.0))
        self.assertEqual(finalSegments[2], (8.0, 9.5))


class TestRajagopal2015(unittest.TestCase):
    def test_Rajagopal2015(self):

        # Copy the data to the local folder.
        # ----------------------------------
        data_fpath = '../data/Rajagopal2015'
        processed_fpath = os.path.join(data_fpath, 'processed')
        if not os.path.isdir(processed_fpath):
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

        # Main path.
        path = os.path.join(data_fpath, 'processed')
        if not path.endswith('/'):
            path += '/'

        # Construct the engine.
        # ---------------------
        engine = Engine(path=absPath(path),
                        output_name='osim_results',
                        href='')

        # Run the pipeline.
        # -----------------
        try:
            engine.validate_paths()
            engine.parse_subject_json()
            engine.load_model_files()
            engine.configure_marker_fitter()
            engine.preprocess_trials()
            engine.run_marker_fitting()
            if engine.fitDynamics:
                engine.run_dynamics_fitting()
            engine.write_result_files()
            engine.generate_readme()
            engine.create_output_folder()

            # If we succeeded, write an empty JSON file.
            with open(engine.errors_json_path, "w") as json_file:
                json_file.write("{}")

        except Error as e:
            # If we failed, write a JSON file with the error information.
            json_data = json.dumps(e.get_error_dict(), indent=4)
            with open(engine.errors_json_path, "w") as json_file:
                json_file.write(json_data)

        # Check the results
        # -----------------
        results_fpath = os.path.join(processed_fpath, '_results.json')
        with open(results_fpath) as file:
            results = json.loads(file.read())

        self.assertAlmostEqual(results['autoAvgRMSE'], 0.0175, delta=0.002)
        self.assertAlmostEqual(results['autoAvgMax'], 0.043, delta=0.005)
        self.assertAlmostEqual(results['linearResidual'], 3.0, delta=5)
        self.assertAlmostEqual(results['angularResidual'], 1.0, delta=5)


class TestErrorReporting(unittest.TestCase):
    def test_ErrorReportingBasics(self):
        testing_dir = os.path.join('testing')
        if not os.path.isdir(testing_dir):
            os.mkdir(testing_dir)
        empty_subject_folder = os.path.join(testing_dir, 'empty_subject')
        if not os.path.isdir(empty_subject_folder):
            os.mkdir(empty_subject_folder)
        empty_subject_folder += '/'
        engine = Engine(path=absPath(empty_subject_folder),
                        output_name='osim_results',
                        href='')

        # Run the pipeline.
        # -----------------
        try:
            engine.validate_paths()
        except Error as e:
            # If we failed, write a JSON file with the error information.
            json_data = json.dumps(e.get_error_dict(), indent=4)
            with open(engine.errors_json_path, "w") as json_file:
                json_file.write(json_data)

        # Check the results
        # -----------------
        errors_fpath = os.path.join(empty_subject_folder, '_errors.json')
        with open(errors_fpath) as file:
            errors = json.loads(file.read())

        self.assertTrue(len(errors) == 3)
        self.assertEqual(errors['type'], 'PathError')


if __name__ == '__main__':
    unittest.main()
