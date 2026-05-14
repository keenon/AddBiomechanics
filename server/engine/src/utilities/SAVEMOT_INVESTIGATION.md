# Investigation: Using `OpenSimParser.saveMot()` in `b3d_to_osim.py`

**Date:** May 14, 2026  
**Investigator:** Matthew Petrucci / GitHub Copilot

---

## Background

The `b3d_to_osim.py` converter uses a manually-written `.mot` file writer rather than
calling `nimble.biomechanics.OpenSimParser.saveMot()`. This document records the
attempts made to use the official API and explains why each failed.

---

## What `opensim_writer.py` (the server) does

The production server code in `server/engine/src/writers/opensim_writer.py` successfully
calls `saveMot` like this:

```python
osim = subject.readOpenSimFile(subject.getNumProcessingPasses()-1, ignoreGeometry=True)
# ...
poses = last_pass.getPoses()           # shape: (num_dofs, T)
timestamps = [start_time + i*dt for i in range(num_steps)]
nimble.biomechanics.OpenSimParser.saveMot(osim.skeleton, ik_fpath, timestamps, poses)
```

The key difference is that in the server, the `SubjectOnDisk` object is written and
then immediately read back **within the same process**, so the skeleton is freshly
constructed in memory. The poses also come from `trial_proto.getPoses()` which works
in that context.

---

## Attempt 1 — `readSkel()` + `saveMot()`

**What we tried:**

```python
skel = subj.readSkel(pass_idx, geodir)
poses = np.array([f.processingPasses[pass_idx].pos for f in frames]).T  # (num_dofs, T)
timestamps = [i * dt for i in range(n)]
nimble.biomechanics.OpenSimParser.saveMot(skel, fpath, timestamps, poses)
```

**Result:** Segmentation fault (core dumped)

**Why it failed:**  
`readSkel()` deserializes the skeleton from the `.b3d` binary file. The resulting
skeleton object appears to be missing internal state that `saveMot()` requires (likely
body node mesh geometry references or DART physics world registration). When `saveMot`
tries to iterate over body nodes to write DOF names and convert units, it dereferences
a null or dangling pointer.

---

## Attempt 2 — `loadAllFrames()` then `readSkel()` + `saveMot()`

**Hypothesis:** Maybe the skeleton needs all frame data loaded into memory first.

**What we tried:**

```python
subj.loadAllFrames(True)
skel = subj.readSkel(pass_idx)
nimble.biomechanics.OpenSimParser.saveMot(skel, fpath, timestamps, poses)
```

**Result:** Segmentation fault (core dumped)

**Why it failed:**  
`loadAllFrames()` populates frame data in the `SubjectOnDisk` buffer but does not
affect the skeleton object returned by `readSkel()`. The skeleton is still deserialized
in the same incomplete state. The segfault is not related to frame data availability.

---

## Attempt 3 — `readOpenSimFile()` + `saveMot()`

**Hypothesis:** The server uses `readOpenSimFile()` not `readSkel()`. Maybe that returns
a more complete skeleton object that `saveMot()` can use.

**What we tried:**

```python
osim = subj.readOpenSimFile(pass_idx, ignoreGeometry=True)
skel = osim.skeleton
poses = np.array([f.processingPasses[pass_idx].pos for f in frames]).T
nimble.biomechanics.OpenSimParser.saveMot(skel, fpath, timestamps, poses)
```

**Result:** Segmentation fault (core dumped)

**Why it failed:**  
`readOpenSimFile()` parses the embedded `.osim` XML text from the `.b3d` file and
constructs a skeleton, but it still does not reproduce the full in-memory state that
the server has when it builds the skeleton live during processing. The `ignoreGeometry=True`
flag avoids mesh-loading crashes but the resulting skeleton is still insufficient for
`saveMot()`. The crash location in C++ is the same.

---

## Root Cause

`OpenSimParser.saveMot()` is only safe to call on a skeleton that was **built
in-memory during the same processing run** (i.e., by `MarkerFitter`, `DynamicsFitter`,
etc.). When a skeleton is deserialized from a `.b3d` file — via any of the three
read methods above — it lacks the internal DART physics world registration and/or
body node state that `saveMot()` assumes. This is a bug or limitation in
nimblephysics; there is no Python-level workaround because the crash happens in
native C++ code and cannot be caught with `try/except`.

---

## Attempt 4 — `OpenSimParser.saveTRC()`

**Hypothesis:** `saveTRC()` writes marker data, not skeleton data. Maybe it avoids the
skeleton-state issue entirely.

**What we tried:**

```python
marker_observations = [{name: pos.reshape(3, 1) for name, pos in f.markerObservations} for f in frames]
nimble.biomechanics.OpenSimParser.saveTRC(fpath, timestamps, marker_observations)
```

Also tried with flat `(3,)` arrays and with minimal synthetic data (no b3d file at all).

**Result:** Segmentation fault (core dumped)

**Why it failed:**  
`saveTRC()` segfaults even with entirely synthetic data, suggesting a bug in the
pybind11 binding for this function unrelated to the skeleton-state issue. The crash
occurs on the first call regardless of input.

---

## Attempt 5 — `OpenSimParser.saveOsimInverseKinematicsXMLFile()`

**Hypothesis:** This function only writes XML strings and file paths — no skeleton or
frame data involved. It should be safe.

**What we tried:**

```python
nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
    trial_name, marker_names, osim_rel_path, trc_rel_path, out_mot_rel, fpath)
```

**Result:** ✅ **Works correctly.** Writes a valid OpenSim IK setup XML file.

---

## Summary of Working vs Broken API Calls (disk-loaded subjects)

| API Call | Status | Notes |
|----------|--------|-------|
| `OpenSimParser.saveMot()` | ❌ Segfault | Needs live in-memory skeleton |
| `OpenSimParser.saveTRC()` | ❌ Segfault | pybind11 binding bug, even synthetic data |
| `OpenSimParser.saveIDMot()` | ❌ Segfault | Needs skeleton |
| `OpenSimParser.saveProcessedGRFMot()` | ❌ Segfault | Needs skeleton + BodyNode objects |
| `OpenSimParser.saveOsimInverseKinematicsXMLFile()` | ✅ Works | String-only, no skeleton |
| `SubjectOnDisk.readOpenSimFile().skeleton` | ✅ Works | Read-only DOF/marker names |
| `SubjectOnDisk.readFrames()` | ✅ Works | All frame data including tau, markers |
| `SubjectOnDisk.getOpensimFileText()` | ✅ Works | Raw .osim XML text |
| `SubjectOnDisk.getGroundForceBodies()` | ✅ Works | Returns body name strings |
| `SubjectOnDisk.get{HeightM,MassKg,BiologicalSex,...}` | ✅ Works | Subject demographics |

---

## Current Solution

`b3d_to_osim.py` uses pure-Python manual writers for all data files:
- `_write_ik_mot_file()` — IK `.mot` files
- `_write_grf_mot_file()` — GRF `.mot` files
- `_write_id_sto_file()` — ID `.sto` files (joint torques from `frame.tau`)
- `_write_trc_file()` — `.trc` marker trajectory files

The one nimblephysics `OpenSimParser` call that works is:
- `OpenSimParser.saveOsimInverseKinematicsXMLFile()` — used in `write_ik_setup_xml()`
