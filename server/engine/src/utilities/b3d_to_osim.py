import contextlib
import json
import os
import nimblephysics as nimble
import numpy as np
from typing import Dict, List, Optional


@contextlib.contextmanager
def _suppress_cpp_stderr():
    """Redirect C-level stderr to /dev/null for the duration of the block.

    nimblephysics prints DART/ASSIMP 'missing mesh file' warnings directly to
    file descriptor 2, which Python's warnings module cannot intercept.
    """
    devnull_fd = os.open(os.devnull, os.O_WRONLY)
    saved_fd   = os.dup(2)
    os.dup2(devnull_fd, 2)
    try:
        yield
    finally:
        os.dup2(saved_fd, 2)
        os.close(saved_fd)
        os.close(devnull_fd)

# Pass type labels matching nimble.biomechanics.ProcessingPassType
_PASS_TYPE_NAMES = {
    nimble.biomechanics.ProcessingPassType.KINEMATICS: 'kinematics',
    nimble.biomechanics.ProcessingPassType.LOW_PASS_FILTER: 'lowpass',
    nimble.biomechanics.ProcessingPassType.DYNAMICS: 'dynamics',
}


class B3DConverter:
    """
    Converts .b3d files (AddBiomechanics format) to OpenSim-compatible files.

    Produces matching IK .mot, GRF .mot, and .osim files for each processing
    pass stored in the .b3d file (e.g. kinematics, lowpass, dynamics).

    Output structure mirrors opensim_writer.py:
        <out_dir>/
            Models/   -> one .osim per pass
            IK/       -> one _ik.mot per (trial, pass)
            ID/       -> one _grf.mot per (trial, pass) when dynamics pass present

    Code written by Matthew Petrucci with help from GitHub Copilot. 02-19-2026
    """

    def __init__(self, data_path: str, geodir: str = ""):
        self.data_path = data_path
        self.geodir = geodir
        self.subj = nimble.biomechanics.SubjectOnDisk(data_path)

    # ------------------------------------------------------------------
    # Pass metadata helpers
    # ------------------------------------------------------------------

    def get_pass_label(self, pass_idx: int) -> str:
        """Human-readable label for a processing pass (e.g. 'kinematics', 'dynamics')."""
        pass_type = self.subj.getProcessingPassType(pass_idx)
        return _PASS_TYPE_NAMES.get(pass_type, f'pass{pass_idx}')

    def get_num_passes(self) -> int:
        return self.subj.getNumProcessingPasses()

    # ------------------------------------------------------------------
    # Core per-pass, per-trial data extraction
    # ------------------------------------------------------------------

    def _read_trial_frames(self, trial_name: str):
        trial_index = self._trial_index(trial_name)
        return self.subj.readFrames(trial_index, 0, self.subj.getTrialLength(trial_index))

    def _trial_index(self, trial_name: str) -> int:
        return [self.subj.getTrialName(i) for i in range(self.subj.getNumTrials())].index(trial_name)

    def _read_trial_dof_names(self, pass_idx: int) -> List[str]:
        """Return DOF names for the given pass by reading the embedded .osim XML."""
        with _suppress_cpp_stderr():
            osim = self.subj.readOpenSimFile(pass_idx, ignoreGeometry=True)
        skel = osim.skeleton
        return [skel.getDofByIndex(i).getName() for i in range(skel.getNumDofs())]

    def _build_out_data(self, trial_name: str, pass_idx: int) -> Dict:
        trial_index = self._trial_index(trial_name)
        frames = self.subj.readFrames(trial_index, 0, self.subj.getTrialLength(trial_index))
        pp = frames[0].processingPasses

        out_data = {
            'pos':     np.array([f.processingPasses[pass_idx].pos for f in frames]),
            'forces':  np.array([f.processingPasses[pass_idx].groundContactForce for f in frames]),
            'cops':    np.array([f.processingPasses[pass_idx].groundContactCenterOfPressure for f in frames]),
            'torques': np.array([f.processingPasses[pass_idx].groundContactTorque for f in frames]),
            # tau (joint torques) — populated only on dynamics passes; zeros otherwise
            'tau':     np.array([f.processingPasses[pass_idx].tau for f in frames]),
            # per-frame marker observations as list-of-dicts (for saveTRC)
            'marker_observations': [dict(f.markerObservations) for f in frames],
        }

        timestep = self.subj.getTrialTimestep(trial_index)
        out_data['time_arr'] = np.arange(len(frames)) * timestep

        out_data['dof_names'] = self._read_trial_dof_names(pass_idx)

        return out_data

    # ------------------------------------------------------------------
    # Individual file writers
    # ------------------------------------------------------------------

    def write_ik_mot(self, trial_name: str, out_dir: str,
                     in_degrees: bool = False, pass_idx: int = None) -> Dict[int, str]:
        """
        Write IK .mot file(s) for a trial. If pass_idx is None, writes one file
        per processing pass. Returns dict mapping pass_idx -> file path.
        """
        passes = [pass_idx] if pass_idx is not None else range(self.get_num_passes())
        paths = {}
        for i in passes:
            label = self.get_pass_label(i)
            out_data = self._build_out_data(trial_name, i)
            fname = f"{trial_name}_{label}_ik.mot"
            fpath = os.path.join(out_dir, fname)
            os.makedirs(out_dir, exist_ok=True)
            _write_ik_mot_file(out_data, fpath, in_degrees)
            paths[i] = fpath
        return paths

    def write_trc(self, trial_name: str, out_dir: str,
                  pass_idx: int = 0) -> str:
        """
        Write a .trc marker trajectory file for a trial.

        Marker observations are read directly from
        ``frame.markerObservations`` (populated by ``readFrames()``).
        The file is written with a manual writer because
        ``OpenSimParser.saveTRC()`` segfaults in nimblephysics 0.10.52
        when called outside of a live processing run (same root cause as
        ``saveMot()`` — see ``SAVEMOT_INVESTIGATION.md``).

        Returns the path to the written file.
        """
        trial_index = self._trial_index(trial_name)
        frames = self.subj.readFrames(trial_index, 0, self.subj.getTrialLength(trial_index))
        timestep = self.subj.getTrialTimestep(trial_index)
        timestamps = [i * timestep for i in range(len(frames))]
        # Each frame's markerObservations is a list of (name, pos) tuples
        marker_observations = [dict(f.markerObservations) for f in frames]
        os.makedirs(out_dir, exist_ok=True)
        fname = f"{trial_name}.trc"
        fpath = os.path.join(out_dir, fname)
        _write_trc_file(marker_observations, timestamps, fpath)
        return fpath

    def write_ik_setup_xml(self, trial_name: str, ik_dir: str, model_dir: str,
                           marker_dir: str, pass_idx: int = 0,
                           model_name: str = "model") -> str:
        """
        Write an OpenSim IK setup XML file for a trial using
        ``OpenSimParser.saveOsimInverseKinematicsXMLFile()``.

        The XML references relative paths so the output folder can be
        moved freely.

        Returns the path to the written file.
        """
        label = self.get_pass_label(pass_idx)

        # Read marker names from the embedded osim file
        with _suppress_cpp_stderr():
            osim = self.subj.readOpenSimFile(pass_idx, ignoreGeometry=True)
        marker_names = list(osim.markersMap.keys())

        osim_rel_path   = os.path.join('..', 'Models', f"{model_name}_{label}.osim")
        trc_rel_path    = os.path.join('..', 'MarkerData', f"{trial_name}.trc")
        out_mot_rel     = f"{trial_name}_{label}_ik_by_opensim.mot"
        fname           = f"{trial_name}_{label}_ik_setup.xml"
        fpath           = os.path.join(ik_dir, fname)
        os.makedirs(ik_dir, exist_ok=True)

        nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
            trial_name,
            marker_names,
            osim_rel_path,
            trc_rel_path,
            out_mot_rel,
            fpath,
        )
        print(f"Wrote {fname}")
        return fpath

    def write_id_sto(self, trial_name: str, out_dir: str,
                     pass_idx: int = None) -> Dict[int, str]:
        """
        Write inverse-dynamics .sto file(s) for a trial using joint torques
        (``frame.processingPasses[i].tau``) read via ``readFrames()``.

        Only dynamics passes contain meaningful tau values; kinematics/lowpass
        passes store zeros.  Files are written for all requested passes so the
        caller can decide which to use.

        Returns dict mapping pass_idx -> file path.
        """
        passes = [pass_idx] if pass_idx is not None else range(self.get_num_passes())
        paths = {}
        for i in passes:
            label = self.get_pass_label(i)
            out_data = self._build_out_data(trial_name, i)
            fname = f"{trial_name}_{label}_id.sto"
            fpath = os.path.join(out_dir, fname)
            os.makedirs(out_dir, exist_ok=True)
            _write_id_sto_file(out_data, fpath)
            paths[i] = fpath
        return paths


    def write_grf_mot(self, trial_name: str, out_dir: str,
                      pass_idx: int = None) -> Dict[int, str]:
        """
        Write GRF .mot file(s) for a trial. If pass_idx is None, writes one file
        per processing pass. Returns dict mapping pass_idx -> file path.
        """
        passes = [pass_idx] if pass_idx is not None else range(self.get_num_passes())
        paths = {}
        for i in passes:
            label = self.get_pass_label(i)
            out_data = self._build_out_data(trial_name, i)
            fname = f"{trial_name}_{label}_grf.mot"
            fpath = os.path.join(out_dir, fname)
            os.makedirs(out_dir, exist_ok=True)
            _write_grf_mot_file(out_data, fpath)
            paths[i] = fpath
        return paths

    def write_osim(self, out_dir: str, model_name: str = "model",
                   pass_idx: int = None) -> Dict[int, str]:
        """
        Write .osim model file(s). If pass_idx is None, writes one file per
        processing pass, named by pass type (e.g. model_kinematics.osim).
        Returns dict mapping pass_idx -> file path.
        """
        os.makedirs(out_dir, exist_ok=True)
        passes = [pass_idx] if pass_idx is not None else range(self.get_num_passes())
        paths = {}
        for i in passes:
            label = self.get_pass_label(i)
            osim_xml = self.subj.getOpensimFileText(i)
            fname = f"{model_name}_{label}.osim"
            fpath = os.path.join(out_dir, fname)
            with open(fpath, 'w') as f:
                f.write(osim_xml)
            print(f"Wrote {fname} (pass {i}: {label}, {len(osim_xml)} bytes)")
            paths[i] = fpath
        return paths

    # ------------------------------------------------------------------
    # Tags
    # ------------------------------------------------------------------

    def write_tags_json(self, out_dir: str,
                        filename: str = "tags.json") -> str:
        """
        Write a JSON file containing the subject tags, trial tags, and
        subject-level demographics/metadata available from the
        ``SubjectOnDisk`` API.

        Output format::

            {
                "subject_tags": ["healthy", ...],
                "height_m": 1.96,
                "mass_kg": 78.2,
                "biological_sex": "male",
                "age_years": 0,
                "quality": "PILOT_DATA",
                "notes": "Generated by AddBiomechanics",
                "href": "https://...",
                "ground_force_bodies": ["calcn_r", "calcn_l"],
                "trials": {
                    "walking1_segment_0": ["overground", ...],
                    ...
                }
            }

        Returns the path to the written file.
        """
        os.makedirs(out_dir, exist_ok=True)

        trial_tags = {
            self.subj.getTrialName(i): list(self.subj.getTrialTags(i))
            for i in range(self.subj.getNumTrials())
        }

        payload = {
            "subject_tags":       list(self.subj.getSubjectTags()),
            "height_m":           self.subj.getHeightM(),
            "mass_kg":            self.subj.getMassKg(),
            "biological_sex":     self.subj.getBiologicalSex(),
            "age_years":          self.subj.getAgeYears(),
            "quality":            str(self.subj.getQuality()).split('.')[-1],
            "notes":              self.subj.getNotes(),
            "href":               self.subj.getHref(),
            "ground_force_bodies": list(self.subj.getGroundForceBodies()),
            "trials":             trial_tags,
        }

        fpath = os.path.join(out_dir, filename)
        with open(fpath, 'w') as f:
            json.dump(payload, f, indent=2)
        print(f"Wrote {filename} "
              f"({len(payload['subject_tags'])} subject tag(s), "
              f"{sum(len(v) for v in trial_tags.values())} trial tag(s) "
              f"across {len(trial_tags)} trial(s))")
        return fpath

    # ------------------------------------------------------------------
    # High-level converter: mirrors opensim_writer.py folder structure
    # ------------------------------------------------------------------

    def convert_trial(self, trial_name: str, out_dir: str,
                      model_name: str = "model") -> Dict:
        """
        Convert a single trial to the full OpenSim output structure:

            <out_dir>/Models/      -> .osim per pass
            <out_dir>/IK/          -> _ik.mot per pass, _ik_setup.xml per pass
            <out_dir>/ID/          -> _id.sto per pass, _grf.mot per pass
            <out_dir>/MarkerData/  -> .trc marker trajectories

        Returns a dict with keys 'models', 'ik', 'id', 'grf', 'trc', 'ik_setup',
        each mapping pass_idx -> file path (or a single path for 'trc').
        """
        ik_dir         = os.path.join(out_dir, 'IK')
        id_dir         = os.path.join(out_dir, 'ID')
        model_dir      = os.path.join(out_dir, 'Models')
        marker_dir     = os.path.join(out_dir, 'MarkerData')

        # Write TRC once (marker data is pass-independent)
        trc_path = self.write_trc(trial_name, marker_dir)

        # Write IK setup XML once per pass
        ik_setup_paths = {
            i: self.write_ik_setup_xml(trial_name, ik_dir, model_dir, marker_dir,
                                       pass_idx=i, model_name=model_name)
            for i in range(self.get_num_passes())
        }

        return {
            'models':   self.write_osim(model_dir, model_name),
            'ik':       self.write_ik_mot(trial_name, ik_dir),
            'id':       self.write_id_sto(trial_name, id_dir),
            'grf':      self.write_grf_mot(trial_name, id_dir),
            'trc':      trc_path,
            'ik_setup': ik_setup_paths,
            'tags':     self.write_tags_json(out_dir),
        }

    def convert_all_trials(self, out_dir: str, model_name: str = "model") -> Dict:
        """
        Convert every trial in the .b3d file. Returns a dict keyed by trial name.
        Models and tags.json are written once (shared across all trials).
        """
        model_dir = os.path.join(out_dir, 'Models')
        model_paths = self.write_osim(model_dir, model_name)
        tags_path = self.write_tags_json(out_dir)

        results = {}
        for i in range(self.subj.getNumTrials()):
            trial_name = self.subj.getTrialName(i)
            print(f"\nConverting trial: {trial_name}")
            ik_dir     = os.path.join(out_dir, 'IK')
            id_dir     = os.path.join(out_dir, 'ID')
            marker_dir = os.path.join(out_dir, 'MarkerData')
            trc_path   = self.write_trc(trial_name, marker_dir)
            ik_setup_paths = {
                j: self.write_ik_setup_xml(trial_name, ik_dir, model_dir, marker_dir,
                                           pass_idx=j, model_name=model_name)
                for j in range(self.get_num_passes())
            }
            results[trial_name] = {
                'models':   model_paths,
                'ik':       self.write_ik_mot(trial_name, ik_dir),
                'id':       self.write_id_sto(trial_name, id_dir),
                'grf':      self.write_grf_mot(trial_name, id_dir),
                'trc':      trc_path,
                'ik_setup': ik_setup_paths,
                'tags':     tags_path,
            }
        return results
    

def _write_trc_file(marker_observations: List[Dict], timestamps: List[float], fpath: str):
    """
    Write an OpenSim .trc marker trajectory file.

    ``OpenSimParser.saveTRC()`` segfaults in nimblephysics 0.10.52 when
    called outside a live processing run, so we write the file manually.
    The TRC format is the standard OpenSim tab-separated format version 4.

    Parameters
    ----------
    marker_observations : list of dict  {marker_name -> np.ndarray shape (3,)}
    timestamps          : list of float  (seconds)
    fpath               : destination file path
    """
    num_frames = len(marker_observations)
    if num_frames == 0:
        return

    # Collect stable marker order from first non-empty frame
    marker_names: List[str] = []
    for obs in marker_observations:
        if obs:
            marker_names = list(obs.keys())
            break
    num_markers = len(marker_names)

    data_rate = 1.0 / float(np.mean(np.diff(timestamps))) if len(timestamps) > 1 else 1.0

    os.makedirs(os.path.dirname(fpath) or '.', exist_ok=True)
    with open(fpath, 'w') as f:
        # --- header block ---
        f.write(f"PathFileType\t4\t(X/Y/Z)\t{os.path.basename(fpath)}\n")
        f.write("DataRate\tCameraRate\tNumFrames\tNumMarkers\tUnits\t"
                "OrigDataRate\tOrigDataStartFrame\tOrigNumFrames\n")
        f.write(f"{data_rate:.6f}\t{data_rate:.6f}\t{num_frames}\t{num_markers}\t"
                f"m\t{data_rate:.6f}\t1\t{num_frames}\n")
        # --- column headers (row 1: marker names, row 2: X/Y/Z labels) ---
        marker_header = ['Frame#', 'Time']
        for name in marker_names:
            marker_header += [name, '', '']
        f.write('\t'.join(marker_header) + '\n')
        xyz_header = ['', '']
        for i in range(num_markers):
            xyz_header += [f'X{i+1}', f'Y{i+1}', f'Z{i+1}']
        f.write('\t'.join(xyz_header) + '\n')
        f.write('\n')  # blank line expected by OpenSim
        # --- data rows ---
        for frame_idx, (t, obs) in enumerate(zip(timestamps, marker_observations)):
            row = [str(frame_idx + 1), f"{t:.8f}"]
            for name in marker_names:
                if name in obs:
                    pos = obs[name]
                    row += [f"{pos[0]:.8f}", f"{pos[1]:.8f}", f"{pos[2]:.8f}"]
                else:
                    row += ['', '', '']
            f.write('\t'.join(row) + '\n')

    hz = data_rate
    print(f"Wrote {os.path.basename(fpath)} ({num_frames} frames, {num_markers} markers, {hz:.2f} Hz)")


def _write_id_sto_file(out_data: Dict, fpath: str):
    """
    Write an OpenSim inverse-dynamics .sto file to *fpath* using joint
    torques from ``frame.processingPasses[pass_idx].tau``.

    Note: tau values are non-zero only on DYNAMICS processing passes.
    Kinematics and low-pass passes store zeros.
    """
    tau  = out_data['tau']       # shape (T, num_dofs)
    time = out_data['time_arr']  # shape (T,)
    nRows, nDofs = tau.shape

    header = [
        "Inverse Dynamics Generalized Forces",
        "version=1",
        f"nRows={nRows}",
        f"nColumns={nDofs + 1}",
        "inDegrees=no",
        "",
        "Units are S.I. units (second, meters, Newtons, ...)",
        "",
        "endheader",
    ]
    columns = ['time'] + [f"{name}_moment" for name in out_data['dof_names']]
    os.makedirs(os.path.dirname(fpath) or '.', exist_ok=True)
    with open(fpath, 'w') as f:
        for line in header:
            f.write(line + '\n')
        f.write('\t'.join(columns) + '\n')
        for t, row in zip(time, tau):
            f.write(f"{t:.8f}\t" + '\t'.join(f"{v:.8f}" for v in row) + '\n')
    hz = 1.0 / float(np.mean(np.diff(time))) if len(time) > 1 else 0.0
    print(f"Wrote {os.path.basename(fpath)} ({nRows} frames, {hz:.2f} Hz)")


def _write_ik_mot_file(out_data: Dict, fpath: str, in_degrees: bool = False):
    """Write an OpenSim IK .mot file to *fpath* from pre-built out_data dict."""
    pos = out_data['pos']
    time = out_data['time_arr']
    nRows, nColumns = pos.shape
    in_degrees_line = "yes" if in_degrees else "no"
    header = [
        "Coordinates",
        "version=1",
        f"nRows={nRows}",
        f"nColumns={nColumns + 1}",
        f"inDegrees={in_degrees_line}",
        "",
        "Units are S.I. units (second, meters, Newtons, ...)",
        "If the header above contains a line with 'inDegrees', this indicates whether rotational values are in degrees (yes) or radians (no).",
        "",
        "endheader",
    ]
    columns = ['time'] + out_data['dof_names']
    os.makedirs(os.path.dirname(fpath) or '.', exist_ok=True)
    with open(fpath, 'w') as f:
        for line in header:
            f.write(line + '\n')
        f.write('\t'.join(columns) + '\n')
        for t, row in zip(time, pos):
            f.write(f"{t:.8f}\t" + '\t'.join(f"{v:.8f}" for v in row) + '\n')
    hz = 1.0 / float(np.mean(np.diff(time))) if len(time) > 1 else 0.0
    print(f"Wrote {os.path.basename(fpath)} ({nRows} frames, {hz:.2f} Hz)")

def _write_grf_mot_file(out_data: Dict, fpath: str):
    """Write an OpenSim GRF .mot file to *fpath* from pre-built out_data dict."""
    forces  = out_data['forces']
    cops    = out_data['cops']
    torques = out_data['torques']
    time    = out_data['time_arr']
    nRows = forces.shape[0]

    R_grf, L_grf       = forces[:, 0:3],  forces[:, 3:6]
    R_cop, L_cop        = cops[:, 0:3],    cops[:, 3:6]
    R_torque, L_torque  = torques[:, 0:3], torques[:, 3:6]

    data = np.hstack([time[:, None],
                      R_grf, R_cop, R_torque,
                      L_grf, L_cop, L_torque])
    nColumns = data.shape[1]

    col_headers = [
        "time",
        "R_ground_force_vx", "R_ground_force_vy", "R_ground_force_vz",
        "R_ground_force_px", "R_ground_force_py", "R_ground_force_pz",
        "R_ground_torque_x", "R_ground_torque_y", "R_ground_torque_z",
        "L_ground_force_vx", "L_ground_force_vy", "L_ground_force_vz",
        "L_ground_force_px", "L_ground_force_py", "L_ground_force_pz",
        "L_ground_torque_x", "L_ground_torque_y", "L_ground_torque_z",
    ]

    os.makedirs(os.path.dirname(fpath) or '.', exist_ok=True)
    with open(fpath, 'w') as f:
        f.write(f"nColumns={nColumns}\n")
        f.write(f"nRows={nRows}\n")
        f.write("DataType=double\n")
        f.write("version=3\n")
        f.write("OpenSimVersion=4.1\n")
        f.write("endheader\n")
        f.write('\t'.join(col_headers) + '\n')
        for row in data:
            f.write('\t'.join(f"{v:.8f}" for v in row) + '\n')
    hz = 1.0 / float(np.mean(np.diff(time))) if len(time) > 1 else 0.0
    print(f"Wrote {os.path.basename(fpath)} ({nRows} frames, {hz:.2f} Hz)")