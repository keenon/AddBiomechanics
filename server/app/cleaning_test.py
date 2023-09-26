import nimblephysics as nimble
import os
import argparse


def main(args: argparse.Namespace) -> bool:
    subj_path: str = args.subj_path

    # Add a pointer to the standard skeleton geometry folder
    geometry_path = '/Users/janellekaneda/Documents/InferBiomechanics/data/Geometry'
    os.symlink(geometry_path, subj_path + '/Geometry')

    # # Load the subject
    # Get the .bin file path
    for file_name in os.listdir(subj_path):
        if file_name.endswith('.bin'):
            subj_bin = os.path.join(subj_path, file_name)
    subj = nimble.biomechanics.SubjectOnDisk(subj_bin)

    # Get the raw .osim file contents and write to file
    og_model_path = os.path.join(subj_path, 'original_model.osim')
    og_model_contents = subj.readRawOsimFileText()
    with open(og_model_path, 'w') as file:
        file.write(og_model_contents)

    # Get the target skeleton
    target_skeleton_path = '/Users/janellekaneda/Documents/AddBiomechanics/server/app/test_data/skeleton_bug/Rajagopal2015_passiveCal_hipAbdMoved_noArms.osim'

    # Get the output path
    unscaled_generic_path = os.path.join(subj_path, 'unscaled_generic.osim')

    # Use translateOsimMarkers
    markers_guessed, markers_missing = nimble.biomechanics.OpenSimParser.translateOsimMarkers(
        og_model_path,
        target_skeleton_path,
        unscaled_generic_path,
        verbose=True)
    print('Markers guessed: ' + str(markers_guessed))
    print('Markers missing: ' + str(markers_missing))


if __name__ == "__main__":
    # Initialize argparse
    parser = argparse.ArgumentParser(description='Evaluate standardizing skeleton bug.')

    # Add arguments
    parser.add_argument(
        '--subj_path', help='File path to the subject folder containing a .bin')

    args = parser.parse_args()
    main(args)
