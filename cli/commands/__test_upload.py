import os
import unittest
from commands.upload import ParserFolderStructure
from typing import List, Tuple, Dict


class TestParserFolderStructure(unittest.TestCase):
    def test_preformatted_folder(self):
        files = ['_subject.json',
                 'trials/T1/markers.trc',
                 'trials/T1/grf.mot',
                 'trials/T2/markers.trc',
                 'trials/T2/grf.mot',
                 'unscaled_generic.osim']
        file_prefix = '/Users/test/Desktop/data/NMBL/Hamner2010/subject10/'
        files = [file_prefix + f for f in files]
        folder_structure = ParserFolderStructure(files)
        self.assertTrue(
            folder_structure.attempt_parse_as_preformatted_dataset(verbose=True, dont_read_files=True))
        self.assertTrue(
            folder_structure.inferred_as_single_subject)
        self.assertEquals(folder_structure.inferred_dataset_name, 'Hamner2010')
        self.assertEquals(folder_structure.inferred_subject_name, 'subject10')
        print(folder_structure.s3_to_local_file)
