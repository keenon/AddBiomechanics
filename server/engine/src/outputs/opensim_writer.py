import os
import nimblephysics as nimble
import shutil
from typing import List, Optional
from plotting import plot_ik_results, plot_id_results, plot_marker_errors, plot_grf_data

KINEMATIC_OSIM_NAME = 'match_markers_but_ignore_physics.osim'
DYNAMICS_OSIM_NAME = 'match_markers_and_physics.osim'


def write_opensim_results(self,
                          results_path: str,
                          data_folder_path: str):
    if not results_path.endswith('/'):
        results_path += '/'
    if not data_folder_path.endswith('/'):
        data_folder_path += '/'

    print('Writing the OpenSim result files...', flush=True)

    # 9.1. Create result directories.
    if not os.path.exists(results_path):
        os.mkdir(results_path)
    if not os.path.exists(results_path + 'IK'):
        os.mkdir(results_path + 'IK')
    if not os.path.exists(results_path + 'ID'):
        os.mkdir(results_path + 'ID')
    if not os.path.exists(results_path + 'C3D'):
        os.mkdir(results_path + 'C3D')
    if not os.path.exists(results_path + 'Models'):
        os.mkdir(results_path + 'Models')
    if self.exportMJCF and not os.path.exists(results_path + 'MuJoCo'):
        os.mkdir(results_path + 'MuJoCo')
    if self.exportSDF and not os.path.exists(results_path + 'SDF'):
        os.mkdir(results_path + 'SDF')
    if not os.path.exists(results_path + 'MarkerData'):
        os.mkdir(results_path + 'MarkerData')
    if os.path.exists(self.subject_path + 'unscaled_generic.osim'):
        shutil.copyfile(self.subject_path + 'unscaled_generic.osim', results_path +
                        'Models/unscaled_generic.osim')

    osim_path: str = 'Models/' + KINEMATIC_OSIM_NAME

    # Create the kinematics model file
    if self.kinematics_skeleton is not None:
        osim_path = 'Models/' + KINEMATIC_OSIM_NAME
        self.scale_osim(
            self.subject_path + 'unscaled_generic.osim',
            results_path + osim_path,
            self.kinematics_skeleton,
            self.kinematics_markers)

    # Create the dynamics model file
    if self.dynamics_skeleton is not None:
        osim_path = 'Models/' + DYNAMICS_OSIM_NAME
        self.scale_osim(
            self.subject_path + 'unscaled_generic.osim',
            results_path + osim_path,
            self.dynamics_skeleton,
            self.dynamics_markers)

    # Copy over the manually scaled model file, if it exists.
    if os.path.exists(self.subject_path + 'manually_scaled.osim'):
        shutil.copyfile(self.subject_path + 'manually_scaled.osim', results_path + 'Models/manually_scaled.osim')

    # Copy over the geometry files, so the model can be loaded directly in OpenSim without chasing down
    # Geometry files somewhere else.
    shutil.copytree(data_folder_path + 'OriginalGeometry', results_path + 'Models/Geometry')

    marker_names: List[str] = []
    for k in self.kinematics_markers:
        marker_names.append(k)

    # 9.9. Write the results to disk.
    for trial in self.trials:
        print('Writing OpenSim output for trial ' + trial.trial_name, flush=True)

        # Write out the original C3D file, if present
        print('Copying original C3D file for trial ' + trial.trial_name + '...', flush=True)
        c3d_fpath = f'{results_path}C3D/{trial.trial_name}.c3d'
        if trial.c3d_file is not None:
            shutil.copyfile(trial.trial_path + 'markers.c3d', c3d_fpath)
        print('Copied', flush=True)

        # Write out all the data from the trial segments
        for i in range(len(trial.segments)):
            print('Writing OpenSim output for trial ' + trial.trial_name + ' segment ' + str(i) + ' of ' + str(
                len(trial.segments)), flush=True)
            ik_fpath = ''
            id_fpath = ''
            grf_fpath = ''
            grf_raw_fpath = ''
            segment = trial.segments[i]
            segment_name = trial.trial_name + '_segment_' + str(i)
            # Write out the IK for the manually scaled skeleton, if appropriate
            if segment.manually_scaled_ik_poses is not None and self.goldOsim is not None:
                nimble.biomechanics.OpenSimParser.saveMot(
                    self.goldOsim.skeleton,
                    results_path + 'IK/' + segment_name + '_manual_ik.mot',
                    segment.timestamps,
                    segment.manually_scaled_ik_poses)
                nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                    trial.trial_name,
                    marker_names,
                    '../Models/manually_scaled.osim',
                    f'../MarkerData/{segment_name}.trc',
                    f'{segment_name}_ik_on_manual_scaling_by_opensim.mot',
                    f'{results_path}IK/{segment_name}_ik_on_manually_scaled_setup.xml')

            # Write out the result data files.
            result_ik: Optional[nimble.biomechanics.IKErrorReport] = None
            if segment.dynamics_status == ProcessingStatus.FINISHED:
                assert (segment.dynamics_poses is not None)
                assert (segment.dynamics_taus is not None)
                # Write out the inverse kinematics results,
                ik_fpath = f'{results_path}IK/{segment_name}_ik.mot'
                print(f'Writing OpenSim {ik_fpath} file, shape={str(segment.dynamics_poses.shape)}', flush=True)
                nimble.biomechanics.OpenSimParser.saveMot(self.skeleton, ik_fpath, segment.timestamps,
                                                          segment.dynamics_poses)
                # Write the inverse dynamics results.
                id_fpath = f'{results_path}ID/{segment_name}_id.sto'
                nimble.biomechanics.OpenSimParser.saveIDMot(self.skeleton, id_fpath, segment.timestamps,
                                                            segment.dynamics_taus)
                # Create the IK error report for this segment
                result_ik = nimble.biomechanics.IKErrorReport(
                    self.skeleton, self.fitMarkers, segment.dynamics_poses, segment.marker_observations)
                # Write out the OpenSim ID files:
                grf_fpath = f'{results_path}ID/{segment_name}_grf.mot'
                grf_raw_fpath = f'{results_path}ID/{segment_name}_grf_raw.mot'

                nimble.biomechanics.OpenSimParser.saveProcessedGRFMot(
                    grf_fpath,
                    segment.timestamps,
                    [self.skeleton.getBodyNode(name) for name in self.footBodyNames],
                    self.skeleton,
                    segment.dynamics_poses,
                    segment.force_plates,
                    segment.foot_body_wrenches)
                nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsProcessedForcesXMLFile(
                    segment_name,
                    [self.skeleton.getBodyNode(name) for name in self.footBodyNames],
                    segment_name + '_grf.mot',
                    results_path + 'ID/' + segment_name + '_external_forces.xml')
                nimble.biomechanics.OpenSimParser.saveRawGRFMot(grf_fpath, segment.timestamps, segment.force_plates)
                nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsRawForcesXMLFile(
                    segment_name,
                    self.skeleton,
                    segment.dynamics_poses,
                    segment.force_plates,
                    segment_name + '_grf.mot',
                    results_path + 'ID/' + segment_name + '_external_forces.xml')
                nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
                    segment_name,
                    '../Models/' + DYNAMICS_OSIM_NAME,
                    '../IK/' + segment_name + '_ik.mot',
                    segment_name + '_external_forces.xml',
                    segment_name + '_id.sto',
                    segment_name + '_id_body_forces.sto',
                    results_path + 'ID/' + segment_name + '_id_setup.xml',
                    min(segment.timestamps), max(segment.timestamps))

            elif segment.kinematics_status == ProcessingStatus.FINISHED:
                assert (segment.kinematics_poses is not None)
                # Write out the inverse kinematics results,
                ik_fpath = f'{results_path}IK/{segment_name}_ik.mot'
                print(f'Writing OpenSim {ik_fpath} file, shape={str(segment.kinematics_poses.shape)}', flush=True)
                nimble.biomechanics.OpenSimParser.saveMot(self.skeleton, ik_fpath, segment.timestamps,
                                                          segment.kinematics_poses)
                # Create the IK error report for this segment
                result_ik = nimble.biomechanics.IKErrorReport(
                    self.skeleton, self.fitMarkers, segment.kinematics_poses, segment.marker_observations)

            if result_ik is not None:
                # Save OpenSim setup files to make it easy to (re)run IK on the results in OpenSim
                nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                    segment_name,
                    marker_names,
                    f'../{osim_path}',
                    f'../MarkerData/{segment_name}.trc',
                    f'{segment_name}_ik_by_opensim.mot',
                    f'{results_path}IK/{segment_name}_ik_setup.xml')

            if segment.marker_observations is not None:
                # Write out the marker trajectories.
                markers_fpath = f'{results_path}MarkerData/{segment_name}.trc'
                print('Saving TRC for trial ' + trial.trial_name + ' segment ' + str(i), flush=True)
                print(len(segment.marker_observations))
                print(len(segment.timestamps))
                nimble.biomechanics.OpenSimParser.saveTRC(
                    markers_fpath, segment.timestamps, segment.marker_observations)
                print('Saved', flush=True)

            # Write out the marker errors.
            if result_ik is not None:
                marker_errors_fpath = f'{results_path}IK/{segment_name}_marker_errors.csv'
                result_ik.saveCSVMarkerErrorReport(marker_errors_fpath)

            # 9.9.11. Plot results.
            print(f'Plotting results for trial segment {segment_name}')
            if ik_fpath and os.path.exists(ik_fpath):
                plot_ik_results(ik_fpath)
                plot_marker_errors(marker_errors_fpath, ik_fpath)

            if id_fpath and os.path.exists(id_fpath):
                plot_id_results(id_fpath)

            if grf_fpath and os.path.exists(grf_fpath):
                plot_grf_data(grf_fpath)

            if os.path.exists(grf_raw_fpath):
                plot_grf_data(grf_raw_fpath)

    print('Zipping up OpenSim files...', flush=True)
    shutil.make_archive(results_path, 'zip', results_path, results_path)
    print('Finished outputting OpenSim files.', flush=True)

