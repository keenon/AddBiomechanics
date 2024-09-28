import os
import nimblephysics as nimble
import shutil
from typing import List, Optional, Dict, Any, Tuple
import json
import textwrap
import numpy as np


def get_segment_results_json(trial_proto: nimble.biomechanics.SubjectOnDiskTrial) -> Dict[str, Any]:
    trial_passes = trial_proto.getPasses()

    kinematics_pass = -1
    dynamics_pass = -1
    for p in range(len(trial_passes)):
        if trial_passes[p].getType() == nimble.biomechanics.ProcessingPassType.KINEMATICS:
            kinematics_pass = p
        elif trial_passes[p].getType() == nimble.biomechanics.ProcessingPassType.DYNAMICS:
            dynamics_pass = p
    missing_grf = trial_proto.getMissingGRFReason()
    num_not_missing_grf = sum([1 for r in missing_grf if r == nimble.biomechanics.MissingGRFReason.notMissingGRF])
    num_missing_grf = sum([1 for r in missing_grf if r != nimble.biomechanics.MissingGRFReason.notMissingGRF])

    # Compute the linear and angular residuals only on the frames where we have GRF data
    linear_residual = 0.0
    angular_residual = 0.0
    if dynamics_pass != -1:
        linear_residual_frames = trial_passes[dynamics_pass].getLinearResidual()
        angular_residual_frames = trial_passes[dynamics_pass].getAngularResidual()
        for i in range(len(missing_grf)):
            if missing_grf[i] == nimble.biomechanics.MissingGRFReason.notMissingGRF:
                linear_residual += linear_residual_frames[i]
                angular_residual += angular_residual_frames[i]
    if num_not_missing_grf > 0:
        linear_residual /= num_not_missing_grf
        angular_residual /= num_not_missing_grf

    results: Dict[str, Any] = {
        'trialName': trial_proto.getOriginalTrialName(),
        'start_frame': trial_proto.getOriginalTrialStartFrame(),
        'start': trial_proto.getOriginalTrialStartTime(),
        'end_frame': trial_proto.getOriginalTrialEndFrame(),
        'end': trial_proto.getOriginalTrialEndTime(),
        # Kinematics fit marker error results, if present
        'kinematicsStatus': 'FINISHED' if kinematics_pass != -1 else 'ERROR',
        'kinematicsAvgRMSE': np.mean(trial_passes[kinematics_pass].getMarkerRMS()) if kinematics_pass != -1 else None,
        'kinematicsAvgMax': np.mean(trial_passes[kinematics_pass].getMarkerMax()) if kinematics_pass != -1 else None,
        'kinematicsPerMarkerRMSE': None,
        # Dynamics fit results, if present
        'dynamicsStatus': 'FINISHED' if dynamics_pass != -1 else 'NOT_STARTED',
        'dynanimcsAvgRMSE': np.mean(trial_passes[dynamics_pass].getMarkerRMS()) if dynamics_pass != -1 else None,
        'dynanimcsAvgMax': np.mean(trial_passes[dynamics_pass].getMarkerMax()) if dynamics_pass != -1 else None,
        'dynanimcsPerMarkerRMSE': None,
        'linearResiduals': linear_residual if dynamics_pass != -1 else None,
        'angularResiduals': angular_residual if dynamics_pass != -1 else None,
        'totalTimestepsWithGRF': num_not_missing_grf,
        'totalTimestepsMissingGRF': num_missing_grf,
        # Hand scaled marker error results, if present
        'goldAvgRMSE': None,
        'goldAvgMax': None,
        'goldPerMarkerRMSE': None,
        # Details for helping report malformed uploads
        'hasMarkers': True,
        'hasForces': True,
        'hasError': False,
        'errorMsg': "",
        'hasMarkerWarnings': False
    }
    return results


def save_segment_to_gui(trial_proto: nimble.biomechanics.SubjectOnDiskTrial,
                        gui_file_path: str,
                        kinematics_pass_index: int = -1,
                        kinematics_osim: Optional[nimble.biomechanics.OpenSimFile] = None,
                        dynamics_pass_index: int = -1,
                        dynamics_osim: Optional[nimble.biomechanics.OpenSimFile] = None):
    """
    Write this trial segment to a file that can be read by the 3D web GUI
    """
    dt = trial_proto.getTimestep()
    marker_observations = trial_proto.getMarkerObservations()

    gui = nimble.server.GUIRecording()
    gui.setFramesPerSecond(int(1.0 / dt))

    markers_layer_name: str = 'Markers'
    warnings_layer_name: str = 'Warnings'
    force_plate_layer_name: str = 'Force Plates'
    kinematics_fit_layer_name: str = 'Kinematics Fit'
    dynamics_fit_layer_name: str = 'Dynamics Fit'

    force_plates = trial_proto.getForcePlates()
    force_plate_raw_cops = [fp.centersOfPressure for fp in force_plates]
    force_plate_raw_forces = [fp.forces for fp in force_plates]
    force_plate_raw_moments = [fp.moments for fp in force_plates]

    trial_passes = trial_proto.getPasses()

    kinematics_poses = None
    if -1 < kinematics_pass_index < len(trial_passes):
        kinematics_poses = trial_passes[kinematics_pass_index].getPoses()

    dynamics_poses = None
    if -1 < dynamics_pass_index < len(trial_passes):
        dynamics_poses = trial_passes[dynamics_pass_index].getPoses()

    has_kinematics_pass = kinematics_osim is not None and kinematics_pass_index > -1 and kinematics_poses is not None
    has_dynamics_pass = dynamics_osim is not None and dynamics_pass_index > -1 and dynamics_poses is not None

    # 1.1. Set up the layers
    # We want to show the markers and warnings by default if the processing steps all failed
    default_show_markers_and_warnings = True
    if has_kinematics_pass or has_dynamics_pass:
        default_show_markers_and_warnings = False
    gui.createLayer(markers_layer_name, [0.5, 0.5, 0.5, 1.0], defaultShow=default_show_markers_and_warnings)
    gui.createLayer(warnings_layer_name, [1.0, 0.0, 0.0, 1.0], defaultShow=default_show_markers_and_warnings)
    gui.createLayer(force_plate_layer_name, [1.0, 0.0, 0.0, 1.0], defaultShow=True)

    if has_kinematics_pass:
        # Default to showing kinematics only if dynamics didn't finish
        gui.createLayer(kinematics_fit_layer_name,
                        defaultShow=(not has_dynamics_pass))
    if has_dynamics_pass:
        # Default to showing dynamics if it finished
        gui.createLayer(dynamics_fit_layer_name, defaultShow=True)

    # 1.2. Create the marker set objects, so we don't recreate them every frame
    render_markers_set = set()
    for obs in marker_observations:
        for key in obs:
            render_markers_set.add(key)
    for marker in render_markers_set:
        gui.createBox('marker_' + str(marker),
                      np.ones(3, dtype=np.float64) * 0.02,
                      np.zeros(3, dtype=np.float64),
                      np.zeros(3, dtype=np.float64),
                      [0.5, 0.5, 0.5, 1.0],
                      layer=markers_layer_name)
        gui.setObjectTooltip('marker_' + str(marker), str(marker))

    for t in range(len(marker_observations)):
        if t % 50 == 0:
            print(f'> Rendering frame {t} of {len(marker_observations)}')

        # 2. Always render the markers, even if we don't have kinematics or dynamics
        for marker in render_markers_set:
            if marker in marker_observations[t]:
                # Render all the marker observations
                gui.createBox('marker_' + str(marker),
                              np.ones(3, dtype=np.float64) * 0.02,
                              marker_observations[t][marker],
                              np.zeros(3, dtype=np.float64),
                              [0.5, 0.5, 0.5, 1.0],
                              layer=markers_layer_name)
            else:
                gui.deleteObject('marker_' + str(marker))

            # Render any marker warnings
            # if self.marker_error_report is not None:
            #     renamed_from_to: Set[Tuple[str, str]] = set(self.marker_error_report.markersRenamedFromTo[t])
            #     for from_marker, to_marker in renamed_from_to:
            #         from_marker_location = None
            #         if from_marker in self.marker_observations[t]:
            #             from_marker_location = self.marker_observations[t][from_marker]
            #         to_marker_location = None
            #         if to_marker in self.marker_observations[t]:
            #             to_marker_location = self.marker_observations[t][to_marker]
            #
            #         if to_marker_location is not None and from_marker_location is not None:
            #             gui.createLine('marker_renamed_' + str(from_marker) + '_to_' + str(to_marker), [to_marker_location, from_marker_location], [1.0, 0.0, 0.0, 1.0], layer=warnings_layer_name)
            #         gui.setObjectWarning('marker_'+str(to_marker), 'warning_marker_renamed_' + str(from_marker) + '_to_' + str(to_marker), 'Marker ' + str(to_marker) + ' was originally named ' + str(from_marker), warnings_layer_name)
            #     for from_marker, to_marker in self.render_markers_renamed_set:
            #         if (from_marker, to_marker) not in renamed_from_to:
            #             gui.deleteObject('marker_renamed_' + str(from_marker) + '_to_' + str(to_marker))
            #         gui.deleteObjectWarning('marker_'+str(to_marker), 'warning_marker_renamed_' + str(from_marker) + '_to_' + str(to_marker))

        # 3. Always render the force plates if we've got them, even if we don't have kinematics or dynamics
        for i, force_plate in enumerate(force_plates):
            # IMPORTANT PERFORMANCE NOTE: Every time force_plate.forces is referenced, it copies the ENTIRE ARRAY from
            # C++ to Python, even if we're only asking for force_plate.forces[i]. So to avoid the performance hit, we
            # need to use copies of these values that are already accessible from Python
            if len(force_plate_raw_cops[i]) > t and len(force_plate_raw_forces[i]) > t and len(
                    force_plate_raw_moments[i]) > t:
                cop = force_plate_raw_cops[i][t]
                force = force_plate_raw_forces[i][t]
                moment = force_plate_raw_moments[i][t]
                line = [cop, cop + force * 0.001]
                gui.createLine('force_plate_' + str(i), line, [1.0, 0.0, 0.0, 1.0], layer=force_plate_layer_name,
                               width=[2.0, 1.0])

        # 4. Render the kinematics skeleton, if we have it
        if has_kinematics_pass:
            kinematics_osim.skeleton.setPositions(kinematics_poses[:, t])
            gui.renderSkeleton(kinematics_osim.skeleton, prefix='kinematics_', layer=kinematics_fit_layer_name)

        # 5. Render the dynamics skeleton, if we have it
        if has_dynamics_pass:
            dynamics_osim.skeleton.setPositions(dynamics_poses[:, t])
            gui.renderSkeleton(dynamics_osim.skeleton, prefix='dynamics_', layer=dynamics_fit_layer_name)
        gui.saveFrame()

    gui.writeFramesJson(gui_file_path)


def save_segment_csv(
        trial_proto: nimble.biomechanics.SubjectOnDiskTrial,
        csv_file_path: str,
        final_skeleton: Optional[nimble.dynamics.Skeleton] = None):
    if len(trial_proto.getPasses()) == 0:
        return

    # Finite difference out the joint quantities we care about
    final_pass = trial_proto.getPasses()[-1]
    poses: np.ndarray = final_pass.getPoses()
    vels: np.ndarray = final_pass.getVels()
    accs: np.ndarray = final_pass.getAccs()
    taus: np.ndarray = final_pass.getTaus()
    marker_observations = trial_proto.getMarkerObservations()
    dt = trial_proto.getTimestep()
    missing_grf_reason = trial_proto.getMissingGRFReason()

    # Write the CSV file
    with open(csv_file_path, 'w') as f:
        f.write('timestamp')
        if final_skeleton is not None:
            # Joint positions
            for i in range(final_skeleton.getNumDofs()):
                f.write(',' + final_skeleton.getDofByIndex(i).getName() + '_pos')
            # Joint velocities
            for i in range(final_skeleton.getNumDofs()):
                f.write(',' + final_skeleton.getDofByIndex(i).getName() + '_vel')
            # Joint accelerations
            for i in range(final_skeleton.getNumDofs()):
                f.write(',' + final_skeleton.getDofByIndex(i).getName() + '_acc')
            # Joint torques
            for i in range(final_skeleton.getNumDofs()):
                f.write(',' + final_skeleton.getDofByIndex(i).getName() + '_tau')
            f.write(',missing_grf_data')
        f.write('\n')

        for t in range(len(marker_observations)):
            timestamp = t * dt + trial_proto.getOriginalTrialStartTime()
            f.write(str(timestamp))
            if final_skeleton is not None:
                # Joint positions
                for i in range(final_skeleton.getNumDofs()):
                    f.write(',' + str(poses[i, t]))
                # Joint velocities
                for i in range(final_skeleton.getNumDofs()):
                    f.write(',' + str(vels[i, t]))
                # Joint accelerations
                for i in range(final_skeleton.getNumDofs()):
                    f.write(',' + str(accs[i, t]))
                # Joint torques
                for i in range(final_skeleton.getNumDofs()):
                    f.write(',' + str(taus[i, t]))
                f.write(',' + str(missing_grf_reason[t] != nimble.biomechanics.MissingGRFReason.notMissingGRF))
            f.write('\n')


def get_overall_results_json(subject: nimble.biomechanics.SubjectOnDisk) -> Dict[str, Any]:
    overall_results: Dict[str, Any] = {}
    trial_protos = subject.getHeaderProto().getTrials()
    trial_results_by_original_trial_name: Dict[str, List[Dict[str, Any]]] = {}
    for i in range(subject.getNumTrials()):
        trial_proto: nimble.biomechanics.SubjectOnDiskTrial = trial_protos[i]
        if trial_proto.getOriginalTrialName() not in trial_results_by_original_trial_name:
            trial_results_by_original_trial_name[trial_proto.getOriginalTrialName()] = []
        trial_results_by_original_trial_name[trial_proto.getOriginalTrialName()].append(get_segment_results_json(trial_proto))
    for original_trial in trial_results_by_original_trial_name:
        trial_results: Dict[str, Any] = {'segments': trial_results_by_original_trial_name[original_trial]}
        overall_results[original_trial] = trial_results
    return overall_results


def generate_readme() -> str:
    # 11. Generate the README file.
    # -----------------------------
    print('Generating README file...')

    text = ''
    text += "*** This data was generated with AddBiomechanics (www.addbiomechanics.org) ***\n"
    text += "AddBiomechanics was written by Keenon Werling.\n"
    text += "\n"
    text += textwrap.fill(
        "Please visit our forums on SimTK for help using the tool: "
        "https://simtk.org/plugins/phpBB/indexPhpbb.php?group_id=2402&pluginname=phpBB")

    # TODO: Add the rest of the autogenerated README file

    return text


def write_web_results(
        subject: nimble.biomechanics.SubjectOnDisk,
        geometry_folder: str,
        output_folder: str):
    if not output_folder.endswith('/'):
        output_folder += '/'
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)

    overall_results = get_overall_results_json(subject)
    with open(output_folder + '_results.json', 'w') as f:
        json.dump(overall_results, f, indent=4)
        print('Wrote JSON results to ' + output_folder + '_results.json', flush=True)

    trials_folder_path = output_folder + 'trials/'
    if not os.path.exists(trials_folder_path):
        os.mkdir(trials_folder_path)

    trial_protos = subject.getHeaderProto().getTrials()

    trial_names_to_segments: Dict[str, List[int]] = {}
    for i in range(subject.getNumTrials()):
        original_trial_name = trial_protos[i].getOriginalTrialName()
        if original_trial_name not in trial_names_to_segments:
            trial_names_to_segments[original_trial_name] = []
        trial_names_to_segments[original_trial_name].append(i)

    kinematics_osim: Optional[nimble.biomechanics.OpenSimFile] = None
    kinematics_pass_index = -1
    dynamics_osim: Optional[nimble.biomechanics.OpenSimFile] = None
    dynamics_pass_index = -1

    for p in range(subject.getNumProcessingPasses()):
        if subject.getProcessingPassType(p) == nimble.biomechanics.ProcessingPassType.KINEMATICS:
            kinematics_osim = subject.readOpenSimFile(p, geometryFolder=geometry_folder)
            kinematics_pass_index = p
        elif subject.getProcessingPassType(p) == nimble.biomechanics.ProcessingPassType.DYNAMICS:
            dynamics_osim = subject.readOpenSimFile(p, geometryFolder=geometry_folder)
            dynamics_pass_index = p

    for trial_name in trial_names_to_segments:
        trial_path = output_folder + 'trials/' + trial_name + '/'
        if not os.path.exists(trial_path):
            os.mkdir(trial_path)

        for i, segment_index in enumerate(sorted(trial_names_to_segments[trial_name])):
            trial_proto = trial_protos[segment_index]
            segment_path = trial_path + 'segment_' + str(i + 1) + '/'
            if not os.path.exists(segment_path):
                os.mkdir(segment_path)
            # Write out the result summary JSON
            print('Writing JSON result to ' + segment_path + '_results.json', flush=True)
            segment_json = get_segment_results_json(trial_proto)
            with open(segment_path + '_results.json', 'w') as f:
                json.dump(segment_json, f, indent=4)
            # Write out the animation preview binary
            save_segment_to_gui(
                trial_proto,
                segment_path + 'preview.bin',
                kinematics_pass_index,
                kinematics_osim,
                dynamics_pass_index,
                dynamics_osim)
            # Write out the data CSV for the plotting software to synchronize on the frontend
            save_segment_csv(
                trial_proto,
                segment_path + 'data.csv',
                dynamics_osim.skeleton if dynamics_pass_index != -1 else kinematics_osim.skeleton)
