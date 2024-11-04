import os
import nimblephysics as nimble
import shutil
from typing import List, Optional
from plotting import plot_ik_results, plot_id_results, plot_marker_errors, plot_grf_data
import numpy as np

GENERIC_OSIM_NAME = 'unscaled_generic.osim'
KINEMATIC_OSIM_NAME = 'match_markers_but_ignore_physics.osim'
DYNAMICS_OSIM_NAME = 'match_markers_and_physics.osim'


def write_opensim_results(subject: nimble.biomechanics.SubjectOnDisk,
                          path: str, output_name: str,                           
                          original_geometry_folder_path: Optional[str] = None):
    
    output_folder = os.path.join(path, output_name)
    if not output_folder.endswith('/'):
        output_folder += '/'

    print('Writing the OpenSim result files...', flush=True)

    # Create result directories.
    if not os.path.exists(output_folder):
        os.mkdir(output_folder)
    if not os.path.exists(output_folder + 'IK'):
        os.mkdir(output_folder + 'IK')
    if not os.path.exists(output_folder + 'ID'):
        os.mkdir(output_folder + 'ID')
    if not os.path.exists(output_folder + 'Models'):
        os.mkdir(output_folder + 'Models')
    if not os.path.exists(output_folder + 'MarkerData'):
        os.mkdir(output_folder + 'MarkerData')

    # Copy the generic model to the output folder.
    shutil.copyfile(os.path.join(path, GENERIC_OSIM_NAME), 
                    output_folder + 'Models/' + GENERIC_OSIM_NAME)

    # Write the OpenSim model files to the output folder.
    for ipass in range(subject.getNumProcessingPasses()):
        if subject.getProcessingPassType(ipass) == nimble.biomechanics.ProcessingPassType.KINEMATICS:
            model_text = subject.getOpensimFileText(ipass)
            with open(output_folder + 'Models/' + KINEMATIC_OSIM_NAME, 'w') as f:
                f.write(model_text)

        if subject.getProcessingPassType(ipass) == nimble.biomechanics.ProcessingPassType.DYNAMICS:
            model_text = subject.getOpensimFileText(ipass)
            with open(output_folder + 'Models/' + DYNAMICS_OSIM_NAME, 'w') as f:
                f.write(model_text)

    osim_path: str = 'Models/' + KINEMATIC_OSIM_NAME

    # Copy over the geometry files, so the model can be loaded directly in OpenSim without chasing down
    # Geometry files somewhere else.
    if original_geometry_folder_path is not None:
        shutil.copytree(original_geometry_folder_path, output_folder + 'Models/Geometry')

    # Load the OpenSim file
    osim = subject.readOpenSimFile(subject.getNumProcessingPasses()-1, ignoreGeometry=True)
    marker_names: List[str] = list(osim.markersMap.keys())

    # 9.9. Write the results to disk.
    trial_protos = subject.getHeaderProto().getTrials()
    for i in range(subject.getNumTrials()):
        trial_proto = trial_protos[i]
        trial_name = subject.getTrialName(i)
        print('Writing OpenSim output for trial ' + trial_name, flush=True)

        trial_passes = trial_proto.getPasses()
        any_dynamics_passes = any([p.getType() == nimble.biomechanics.ProcessingPassType.DYNAMICS for p in trial_passes])
        any_kinematics_passes = any([p.getType() == nimble.biomechanics.ProcessingPassType.KINEMATICS for p in trial_passes])

        ik_fpath = ''
        id_fpath = ''
        grf_fpath = ''
        grf_raw_fpath = ''
        # Write out the result data files.
        result_ik: Optional[nimble.biomechanics.IKErrorReport] = None
        marker_observations = None
        if any_dynamics_passes:
            last_pass = trial_passes[-1]
            poses = last_pass.getPoses()
            taus = last_pass.getTaus()
            marker_observations = trial_proto.getMarkerObservations()
            print(f'Writing OpenSim ID file, shape={str(poses.shape)}', flush=True)
            timestamps = np.array(list(range(poses.shape[1]))) * subject.getTrialTimestep(i)

            # Write out the inverse kinematics results,
            ik_fpath = f'{output_folder}IK/{trial_name}_ik.mot'
            print(f'Writing OpenSim {ik_fpath} file, shape={str(poses.shape)}', flush=True)
            nimble.biomechanics.OpenSimParser.saveMot(osim.skeleton,
                                                      ik_fpath,
                                                      timestamps,
                                                      poses)
            # Write the inverse dynamics results.
            id_fpath = f'{output_folder}ID/{trial_name}_id.sto'
            nimble.biomechanics.OpenSimParser.saveIDMot(osim.skeleton,
                                                        id_fpath,
                                                        timestamps,
                                                        taus)
            # Create the IK error report for this segment
            result_ik = nimble.biomechanics.IKErrorReport(
                osim.skeleton,
                osim.markersMap,
                poses,
                marker_observations)
            # Write out the OpenSim ID files:
            grf_fpath = f'{output_folder}ID/{trial_name}_grf.mot'
            grf_raw_fpath = f'{output_folder}ID/{trial_name}_grf_raw.mot'

            force_plates = last_pass.getProcessedForcePlates()

            nimble.biomechanics.OpenSimParser.saveProcessedGRFMot(
                grf_fpath,
                timestamps,
                [osim.skeleton.getBodyNode(name) for name in subject.getGroundForceBodies()],
                osim.skeleton,
                poses,
                force_plates,
                last_pass.getGroundBodyWrenches())
            nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsProcessedForcesXMLFile(
                trial_name,
                [osim.skeleton.getBodyNode(name) for name in subject.getGroundForceBodies()],
                trial_name + '_grf.mot',
                output_folder + 'ID/' + trial_name + '_external_forces.xml')

            # TODO: update to use the subject's ground force bodies.
            # nimble.biomechanics.OpenSimParser.saveRawGRFMot(grf_raw_fpath, timestamps, force_plates)
            # nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsRawForcesXMLFile(
            #     trial_name,
            #     osim.skeleton,
            #     poses,
            #     force_plates,
            #     trial_name + '_grf_raw.mot',
            #     output_folder + 'ID/' + trial_name + '_external_forces_raw.xml')
            # nimble.biomechanics.OpenSimParser.saveOsimInverseDynamicsXMLFile(
            #     trial_name,
            #     '../Models/' + DYNAMICS_OSIM_NAME,
            #     '../IK/' + trial_name + '_ik.mot',
            #     trial_name + '_external_forces_raw.xml',
            #     trial_name + '_id.sto',
            #     trial_name + '_id_body_forces.sto',
            #     output_folder + 'ID/' + trial_name + '_id_setup.xml',
            #     min(timestamps), max(timestamps))

        elif any_kinematics_passes:
            # Write out the inverse kinematics results,
            ik_fpath = f'{output_folder}IK/{trial_name}_ik.mot'
            last_pass = trial_passes[-1]
            poses = last_pass.getPoses()
            marker_observations = trial_proto.getMarkerObservations()
            timestamps = np.array(range(poses.shape[1])) * subject.getTrialTimestep(i)
            print(f'Writing OpenSim {ik_fpath} file, shape={str(poses.shape)}', flush=True)
            nimble.biomechanics.OpenSimParser.saveMot(osim.skeleton, ik_fpath, timestamps,
                                                      poses)
            # Create the IK error report for this segment
            result_ik = nimble.biomechanics.IKErrorReport(
                osim.skeleton, osim.markersMap, poses, marker_observations)

        if result_ik is not None:
            # Save OpenSim setup files to make it easy to (re)run IK on the results in OpenSim
            nimble.biomechanics.OpenSimParser.saveOsimInverseKinematicsXMLFile(
                trial_name,
                marker_names,
                f'../{osim_path}',
                f'../MarkerData/{trial_name}.trc',
                f'{trial_name}_ik_by_opensim.mot',
                f'{output_folder}IK/{trial_name}_ik_setup.xml')

        if marker_observations is not None:
            # Write out the marker trajectories.
            markers_fpath = f'{output_folder}MarkerData/{trial_name}.trc'
            print('Saving TRC for trial ' + trial_name, flush=True)
            timestamps = np.array(range(len(marker_observations))) * subject.getTrialTimestep(i)
            nimble.biomechanics.OpenSimParser.saveTRC(
                markers_fpath, timestamps, marker_observations)
            print('Saved', flush=True)

        # Write out the marker errors.
        if result_ik is not None:
            marker_errors_fpath = f'{output_folder}IK/{trial_name}_marker_errors.csv'
            result_ik.saveCSVMarkerErrorReport(marker_errors_fpath)

        # 9.9.11. Plot results.
        print(f'Plotting results for trial {trial_name}')
        if ik_fpath and os.path.exists(ik_fpath):
            plot_ik_results(ik_fpath)
            plot_marker_errors(marker_errors_fpath, ik_fpath)

        if id_fpath and os.path.exists(id_fpath):
            plot_id_results(id_fpath)

        if grf_fpath and os.path.exists(grf_fpath):
            plot_grf_data(grf_fpath)

        if os.path.exists(grf_raw_fpath):
            plot_grf_data(grf_raw_fpath)


