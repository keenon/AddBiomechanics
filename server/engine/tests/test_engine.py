import shutil
import unittest
from engine import Engine   
import os
from inspect import getsourcefile
import opensim as osim

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


class TestEngine(unittest.TestCase):
    def test_engine(self):
        reset_test_data('rajagopal2015')
        path = os.path.join(TEST_DATA_PATH, 'rajagopal2015')
        if not path.endswith('/'):
            path += '/'
        output_name = 'osim_results'

        engine = Engine(path, output_name, '<href>')
        engine.run()

        solution_fpath = os.path.join(path, output_name, 'Moco', 
                                      f'walk_segement_0_moco.sto')
        solution = osim.TimeSeriesTable(solution_fpath)
        self.assertEqual(solution.getTableMetaDataString('success'), 'true')
        self.assertEqual(solution.getTableMetaDataString('status'), 'Solve_Succeeded')
