"""
exceptions.py
-------------
Description: Custom exception classes for use in the AddBiomechanics processing engine.
Author(s): Nicholas Bianco
"""

import textwrap


class Error(Exception):
    """Base class for exceptions used in the AddBiomechanics engine."""
    def __init__(self, original_message):
        self.message = f'{self.get_message()} Below is the original error message, which main contain useful ' \
                       f'information about your issue. If you are unable to resolve the issue, please submit a ' \
                       f'forum post at https://simtk.org/projects/addbiomechanics or a submit a GitHub Issue at ' \
                       f'https://github.com/keenon/AddBiomechanics/issues with all error messages included.'
        self.original_message = f'\n\n{textwrap.indent(original_message, " " * 4)}\n\n'
        self.type = self.get_type()

        super().__init__(self.message)

    def get_message(self):
        raise NotImplementedError("Subclasses must implement the 'get_message' method.")

    def get_type(self):
        return self.__class__.__name__

    def get_error_dict(self):
        return {
            "type": self.type,
            "message": self.message,
            "original_message": self.original_message
        }


class PathError(Error):
    """Raised when a input data path is invalid."""
    def get_message(self):
        return "PathError: Error encountered when detecting the Geometry folder, subject JSON file, and trials " \
               "directory. These files and/or folder may be missing or invalid."


class SubjectConfigurationError(Error):
    """Raised when a the provided subject information is missing or malformed.."""
    def get_message(self):
        return "SubjectConfigurationError: Error encountered when reading in subject-specific information. Please " \
               "check that the height, weight, sex, and model file for the subject are all provided and correct."


class ModelFileError(Error):
    """Raised when the provided model file is missing or malformed."""
    def get_message(self):
        return "ModelFileError: Error encountered when loading preset or custom model file(s). Please check that you " \
               "have provided a valid OpenSim Model file and that the file is not corrupted (e.g., by trying to load " \
               "it into the OpenSim GUI). If you are using a model with a custom markerset, please check that the " \
               "markers are attached to the correct bodies and correspond to the experimental marker trajectories " \
               "you have provided."


class TrialPreprocessingError(Error):
    """Raised when an error occurs during the trial segmentation step."""
    def get_message(self):
        return "TrialPreprocessingError: Error encountered when preprocessing the marker and/or ground " \
               "reaction force data. Please check that your data files do not contain any NaN or other invalid " \
               "values. It is also recommend to check that certainty quantities have zero or non-zero value when " \
               "you expect them to be zero or non-zero, respectively. If you have provided both marker and ground " \
               "reaction force data, please check that the number of frames in each file is the same and that the " \
               "time stamps are consistent. If you have enabled automatic trial segmentation, try disabling this " \
               "option and manually trimming the data for each trial."


class MarkerFitterError(Error):
    """Raised when an error occurs during the marker fitting step."""
    def get_message(self):
        return "MarkerFitterError: Error encountered when running the marker fitting step. This step is highly " \
               "dependent on the quality of the marker data provided. Please check that the marker trajectories are " \
               "smooth and do not contain any large gaps or other artifacts (e.g., due to filtering). Check that " \
               "markers are labeled correctly and that the marker set is consistent across trials. Try visualizing " \
               "the marker trajectories in the OpenSim GUI to check for any obvious issues (e.g., markers swapping " \
               "segments at different frames)."


class DynamicsFitterError(Error):
    """Raised when an error occurs during the dynamics fitting step."""
    def get_message(self):
        return "DynamicsFitterError: Error encountered when running the dynamics fitting step. This step is highly " \
               "dependent on the quality of the ground reaction force data provided and its consistency with the " \
               "marker data. Please check that the ground reaction force data is smooth and does not contain any " \
               "unexpected large gaps or other artifacts (e.g., due to filtering). Check that the force labels are " \
               "are consistent with the standard for OpenSim ExternalLoads files. Try visualizing the ground " \
               "reaction force data in the OpenSim GUI to check for any obvious issues (e.g., forces switching " \
               "between feet or not aligning with the feet at all)."


class WriteError(Error):
    """Raised when an error occurs when writing out the results."""
    def get_message(self):
        return "WriteResultsError: Error encountered when writing out the result files."
