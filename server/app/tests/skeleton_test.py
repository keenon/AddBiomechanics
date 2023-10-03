import unittest
import nimblephysics as nimble
import os


class TranslateSkeletonTest(unittest.TestCase):
    def test_translate_skeleton(self):

        # Get the raw .osim file
        og_model_path = os.path.abspath('../test_data/skeleton_test/original_model.osim')

        # Get the target skeleton
        target_skeleton_path = os.path.abspath('../test_data/skeleton_test/Rajagopal2015_passiveCal_hipAbdMoved_noArms.osim')

        # Get the output path
        unscaled_generic_path = os.path.abspath('../test_data/skeleton_test/unscaled_generic.osim')

        # Use translateOsimMarkers
        markers_guessed, markers_missing = nimble.biomechanics.OpenSimParser.translateOsimMarkers(
            og_model_path,
            target_skeleton_path,
            unscaled_generic_path,
            verbose=True)
        print('Markers guessed: ' + str(markers_guessed))
        print('Markers missing: ' + str(markers_missing))

        # Check if the final skeleton has arms. It shouldn't, even though the original skeleton has arms.
        # Load the final skeleton
        osimfile_path = os.path.abspath('../test_data/skeleton_test/unscaled_generic.osim')
        osimfile = nimble.biomechanics.OpenSimParser.parseOsim(osimfile_path)
        skel = osimfile.skeleton
        self.assertFalse(self, nimble.biomechanics.OpenSimParser.hasArms(skel))


if __name__ == "__main__":
    unittest.main()
