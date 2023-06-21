from addbiomechanics.commands.abtract_command import AbstractCommand
import argparse
from addbiomechanics.auth import AuthContext
import os

def get_absolute_path(user_input):
    # Check if the user input is already an absolute path
    if os.path.isabs(user_input):
        return user_input

    # If the user input is a relative path, convert it to an absolute path
    current_dir = os.getcwd()  # Get the current working directory
    absolute_path = os.path.join(current_dir, user_input)

    return os.path.abspath(absolute_path)

# This command will take as input an arbitrary OSIM file with an arbitrary markerset, and another
# arbitrary "target" OSIM file, and will output a new OSIM file which is the same as the "target" OSIM skeleton, but
# with the markerset from the first OSIM file. This uses a combination of the following techniques:
# - Aligning markers based on shared Geometry (meshes reused between models are a great clue about structure)
# - Aligning based on common joint structure (once joints are aligned, then marker attach points can often be guessed)

# THIS IS HEURISTIC! You should still check the output of this command to make sure it makes sense. Open up the OSIM
# files that you get to make sure that they're not putting markers in crazy places.

class TransferMarkersetCommand(AbstractCommand):
    def register_subcommand(self, subparsers: argparse._SubParsersAction):
        parser = subparsers.add_parser(
            'transfer_markerset', help='The purpose of this utility is to help with creating aggregated datasets which '
                                       'all use the same OSIM file. The utility takes three arguments:'
                                       '1. The path to the OSIM file which contains the markerset you want to transfer.'
                                       '2. The path to the OSIM file which contains the skeleton you want to transfer '
                                       '    the markerset to.'
                                       '3. The path to the output OSIM file which will contain the skeleton from the '
                                       '    second OSIM file, but with the markerset from the first OSIM file.')
        parser.add_argument('source_osim_with_markerset', type=str)
        parser.add_argument('target_osim', type=str)
        parser.add_argument('output_path', type=str)

    def run(self, ctx: AuthContext, args: argparse.Namespace):
        if args.command != 'transfer_markerset':
            return

        try:
            import nimblephysics as nimble
        except ImportError:
            print("The required library 'nimblephysics' is not installed. Please install it and try this command again.")
            return
        try:
            import numpy as np
        except ImportError:
            print("The required library 'numpy' is not installed. Please install it and try this command again.")
            return

        source_osim_with_markerset: str = get_absolute_path(args.source_osim_with_markerset)
        target_osim: str = get_absolute_path(args.target_osim)
        output_path: str = get_absolute_path(args.output_path)

        guessed, missing = nimble.biomechanics.OpenSimParser.translateOsimMarkers(source_osim_with_markerset,
                                                                      target_osim,
                                                                      output_path, verbose=True)

        if len(guessed) == 0 and len(missing) == 0:
            print('SUCCESS! The conversion was able to transfer all the markers using shared Geometry. '
                  'This is best-case-scenario, and means that the markers will be in the correct place.')
        else:
            print('WARNING: HEURISTICS APPLIED! The conversion was not able to transfer all the markers using shared '
                  'Geometry. This means that some markers may be in the wrong place. Please check the output file to '
                  'verify that things are working correctly.')
            print('The following markers were placed with guessed locations:')
            for marker in guessed:
                print(f' > {marker}')
            print('The following markers were not guessed (perhaps they were arm markers, transferring to an armless '
                  'model?):')
            for marker in missing:
                print(f' > {marker}')