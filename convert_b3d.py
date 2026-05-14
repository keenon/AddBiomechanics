#!/usr/bin/env python3
"""
convert_b3d.py — Convert an AddBiomechanics .b3d file to OpenSim formats.

Usage
-----
    python convert_b3d.py <path_to_file.b3d> [options]

Options
-------
    -o / --output DIR     Directory to write output files (default: next to the .b3d file)
    --name MODEL_NAME     Base name for the .osim model files (default: subject)
    --trial TRIAL_NAME    Convert only this trial (default: convert all trials)
    --geodir PATH         Path to OpenSim Geometry folder (rarely needed)
    --degrees             Write IK angles in degrees instead of radians
    -h / --help           Show this message and exit

Output structure
----------------
    <output_dir>/
        Models/
            subject_kinematics.osim
            subject_lowpass.osim
            subject_dynamics.osim      (if dynamics pass present)
        IK/
            <trial>_kinematics_ik.mot
            <trial>_kinematics_ik_setup.xml
            ...
        ID/
            <trial>_kinematics_grf.mot
            <trial>_kinematics_id.sto
            ...
        MarkerData/
            <trial>.trc
        tags.json

Each .b3d file stores one or more processing passes (kinematics, low-pass
filter, dynamics).  A matching set of IK .mot, GRF .mot, and .osim files is
written for every pass.

Requirements
------------
    pip install nimblephysics numpy

Examples
--------
    # Convert all trials, output next to the .b3d file
    python convert_b3d.py subject1.b3d

    # Custom output directory
    python convert_b3d.py subject1.b3d -o ./opensim_files

    # Convert only one trial
    python convert_b3d.py subject1.b3d --trial walking_01

    # Write angles in degrees
    python convert_b3d.py subject1.b3d --degrees
"""

import argparse
import os
import sys

# ---------------------------------------------------------------------------
# Make sure the server/engine/src utilities are importable regardless of where
# this script lives relative to the repo root.
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_REPO_ROOT, 'server', 'engine', 'src'))

try:
    from utilities.b3d_to_osim import B3DConverter
except ImportError as e:
    print(f"[ERROR] Could not import B3DConverter: {e}")
    print("Make sure you are running this script from the AddBiomechanics repo root,")
    print("or that server/engine/src is on your PYTHONPATH.")
    sys.exit(1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_subject_info(converter: B3DConverter) -> None:
    subj = converter.subj
    num_passes = converter.get_num_passes()
    num_trials = subj.getNumTrials()

    print(f"  Processing passes : {num_passes}")
    for i in range(num_passes):
        label = converter.get_pass_label(i)
        print(f"    Pass {i}: {label}")

    print(f"  Trials            : {num_trials}")
    for i in range(num_trials):
        name   = subj.getTrialName(i)
        length = subj.getTrialLength(i)
        dt     = subj.getTrialTimestep(i)
        hz     = 1.0 / dt if dt > 0 else 0.0
        print(f"    [{i}] {name!r:40s} {length:5d} frames  {hz:.1f} Hz")


def _convert(converter: B3DConverter, trial_name: str,
             out_dir: str, model_name: str, in_degrees: bool) -> None:
    """Convert a single trial and print a summary of written files."""
    ik_dir     = os.path.join(out_dir, 'IK')
    id_dir     = os.path.join(out_dir, 'ID')
    model_dir  = os.path.join(out_dir, 'Models')
    marker_dir = os.path.join(out_dir, 'MarkerData')

    ik_paths    = converter.write_ik_mot(trial_name, ik_dir, in_degrees=in_degrees)
    id_paths    = converter.write_id_sto(trial_name, id_dir)
    grf_paths   = converter.write_grf_mot(trial_name, id_dir)
    model_paths = converter.write_osim(model_dir, model_name)
    trc_path    = converter.write_trc(trial_name, marker_dir)
    ik_setup_paths = {
        i: converter.write_ik_setup_xml(trial_name, ik_dir, model_dir, marker_dir,
                                        pass_idx=i, model_name=model_name)
        for i in range(converter.get_num_passes())
    }
    # tags.json is per-subject: written once to out_dir root
    tags_path   = converter.write_tags_json(out_dir)

    print(f"\n  Output for trial '{trial_name}':")
    for i in sorted(ik_paths):
        label = converter.get_pass_label(i)
        print(f"    [{label}]")
        print(f"      IK mot      : {os.path.relpath(ik_paths[i], out_dir)}")
        if i in id_paths:
            print(f"      ID sto      : {os.path.relpath(id_paths[i], out_dir)}")
        print(f"      GRF mot     : {os.path.relpath(grf_paths[i], out_dir)}")
        print(f"      OSIM        : {os.path.relpath(model_paths[i], out_dir)}")
        if i in ik_setup_paths:
            print(f"      IK setup XML: {os.path.relpath(ik_setup_paths[i], out_dir)}")
    print(f"    Markers (TRC): {os.path.relpath(trc_path, out_dir)}")
    print(f"    Tags         : {os.path.relpath(tags_path, out_dir)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog='convert_b3d',
        description='Convert an AddBiomechanics .b3d file to OpenSim formats.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split('Requirements')[0].rstrip()
    )
    parser.add_argument('b3d_file', help='Path to the .b3d file to convert')
    parser.add_argument('-o', '--output', default=None,
                        help='Output directory (default: <b3d_dir>/opensim_output)')
    parser.add_argument('--name', default='subject', metavar='MODEL_NAME',
                        help='Base name for .osim files (default: subject)')
    parser.add_argument('--trial', default=None, metavar='TRIAL_NAME',
                        help='Convert only this trial (default: all trials)')
    parser.add_argument('--geodir', default='', metavar='PATH',
                        help='Path to OpenSim Geometry folder (rarely needed)')
    parser.add_argument('--degrees', action='store_true',
                        help='Write IK angles in degrees (default: radians)')
    args = parser.parse_args()

    # ---- validate input ----
    b3d_path = os.path.abspath(args.b3d_file)
    if not os.path.isfile(b3d_path):
        print(f"[ERROR] File not found: {b3d_path}")
        sys.exit(1)
    if not b3d_path.endswith('.b3d'):
        print(f"[WARNING] File does not have a .b3d extension: {b3d_path}")

    # ---- output directory ----
    out_dir = args.output if args.output else os.path.join(os.path.dirname(b3d_path), 'opensim_output')
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    # ---- load subject ----
    print(f"\nLoading {b3d_path} ...")
    try:
        converter = B3DConverter(b3d_path, geodir=args.geodir)
    except Exception as e:
        print(f"[ERROR] Failed to load .b3d file: {e}")
        sys.exit(1)

    print("\nSubject info:")
    _print_subject_info(converter)

    # ---- select trials ----
    num_trials = converter.subj.getNumTrials()
    all_trial_names = [converter.subj.getTrialName(i) for i in range(num_trials)]

    if args.trial:
        if args.trial not in all_trial_names:
            print(f"\n[ERROR] Trial '{args.trial}' not found.")
            print(f"Available trials: {all_trial_names}")
            sys.exit(1)
        trial_names = [args.trial]
    else:
        trial_names = all_trial_names

    # ---- convert ----
    print(f"\nWriting output to: {out_dir}")
    print(f"{'='*60}")

    failed = []
    for trial_name in trial_names:
        print(f"\nConverting trial: '{trial_name}'")
        try:
            _convert(converter, trial_name, out_dir, args.name, args.degrees)
        except Exception as e:
            print(f"  [ERROR] {e}")
            failed.append(trial_name)

    # ---- summary ----
    print(f"\n{'='*60}")
    converted = len(trial_names) - len(failed)
    print(f"Done. {converted}/{len(trial_names)} trial(s) converted successfully.")
    if failed:
        print(f"Failed trials: {failed}")
    print(f"Output directory: {out_dir}")


if __name__ == '__main__':
    main()
