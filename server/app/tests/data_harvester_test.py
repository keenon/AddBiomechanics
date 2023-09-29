import unittest
import os
from typing import List
from src.data_harvester import SubjectSnapshot

class DataHarvesterTest(unittest.TestCase):

    def test_discard_short_trials(self):

        # Dir for all short trials
        datadir = '/Users/janellekaneda/Documents/AddBiomechanics/server/app/test_data/data_harvester_test_short'
        trials_to_remove = SubjectSnapshot.id_short_trials(datadir)

        # Assert that the short trial paths are in the list
        # Get all the short trial paths
        true_trials: List[str] = []
        for root, _, files in os.walk(datadir):
            for file in files:
                if file.endswith('.trc') or file.endswith('.c3d'):
                    true_trials.append(os.path.join(root, file))

        self.assertCountEqual(trials_to_remove, true_trials)

    def test_keep_long_trials(self):

        # Dir for all long trials
        datadir = '/Users/janellekaneda/Documents/AddBiomechanics/server/app/test_data/data_harvester_test_long'
        trials_to_remove = SubjectSnapshot.id_short_trials(datadir)

        # The list should be empty because we should not be removing any.
        self.assertCountEqual(trials_to_remove, [])



if __name__ == '__main__':
    unittest.main()
