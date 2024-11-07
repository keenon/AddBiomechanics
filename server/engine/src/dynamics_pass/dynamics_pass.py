import nimblephysics as nimble
import numpy as np
from typing import List, Tuple
from utilities.scale_opensim_model import scale_opensim_model


def dynamics_pass(subject: nimble.biomechanics.SubjectOnDisk):
    """
    This function is responsible for running the dynamics pass on the subject. It assumes that we already have a
    reasonably accurate guess for the subject's body scales, marker offsets, and motion. This function will then
    do the following:
    - Run a center-of-mass trajectory initialization, which will attempt to fit the subject's COM acceleration to the
    observed GRF data, while smoothing the motion that does not have observed GRF data.
    - Run a full "kitchen sink" optimization to further refine everything about that initial guess, and improve metrics
    on average around 20%.
    """
    header_proto = subject.getHeaderProto()
    trial_protos = header_proto.getTrials()
    num_trials = subject.getNumTrials()

    osim = subject.readOpenSimFile(subject.getNumProcessingPasses()-1, ignoreGeometry=True)
    skel = osim.skeleton
    markers_map = osim.markersMap

    dynamics_trials: List[int] = []
    for i in range(subject.getNumTrials()):
        missing_grf = trial_protos[i].getMissingGRFReason()
        num_not_missing = sum(
            [missing == nimble.biomechanics.MissingGRFReason.notMissingGRF for missing in missing_grf])
        print(f"Trial {i} has {num_not_missing} frames of good GRF data")
        if num_not_missing < 5:
            print(f"Trial {i} has less than 5 frames of good GRF data. Skipping dynamics optimization.")
            continue
        # Run the dynamics optimization
        print('Running dynamics optimization on trial ' + str(i) + '/' + str(num_trials))
        dynamics_trials.append(i)

    #######################################################################################################
    # Actually run the dynamics fitting problem
    #######################################################################################################
    if len(dynamics_trials) > 0:
        foot_bodies = [skel.getBodyNode(body) for body in subject.getGroundForceBodies()]

        dynamics_fitter = nimble.biomechanics.DynamicsFitter(
            skel, foot_bodies, osim.trackingMarkers)

        dynamics_prefit_poses = []
        dynamics_prefit_trials = []
        for trial in dynamics_trials:
            trial_len = subject.getTrialLength(trial)
            missing_grf = subject.getMissingGRF(trial)
            track_indices = [missing_reason == nimble.biomechanics.MissingGRFReason.notMissingGRF for missing_reason in
                             missing_grf]

            num_tracked = sum(track_indices)
            if num_tracked == 0 or trial_len < 10:
                continue

            ##########################################################################################################
            # Stage 1: Initialize with a center-of-mass trajectory fit
            ##########################################################################################################

            print("Fitting COM acceleration on trial: " + str(trial))

            trial_proto = trial_protos[trial]
            smoothed_pass = trial_proto.getPasses()[1]
            poses = smoothed_pass.getPoses()
            root_poses = poses[3:6, :]
            accs = smoothed_pass.getAccs()
            root_linear_accs = accs[3:6, :]
            com_accs = smoothed_pass.getComAccs()
            acc_offsets = com_accs - root_linear_accs

            total_forces = np.zeros((3, trial_len))
            cop_torque_force_in_root = smoothed_pass.getGroundBodyCopTorqueForce()
            num_force_plates = int(cop_torque_force_in_root.shape[0] / 9)
            for j in range(num_force_plates):
                total_forces += cop_torque_force_in_root[j * 9 + 6:j * 9 + 9, :]

            # We want our root linear acceleration to offset enough to match the total forces
            goal_com_accs = total_forces / subject.getMassKg()
            com_acc_errors = goal_com_accs - com_accs

            target_root_linear_accs = root_linear_accs + com_acc_errors

            # Now we want to try to find a set of root translations that match the target root linear accs on
            # the frames with observed forces, and otherwise revert to our classic
            # AccelerationMinimizingSmoother.

            dt = subject.getTrialTimestep(trial)
            zero_unobserved_acc_weight = 1.0
            track_observed_acc_weight = 100.0
            regularization_weight = 1000.0
            smooth_and_track = nimble.utils.AccelerationTrackAndMinimize(len(track_indices), track_indices,
                                                                         zeroUnobservedAccWeight=zero_unobserved_acc_weight,
                                                                         trackObservedAccWeight=track_observed_acc_weight,
                                                                         regularizationWeight=regularization_weight, dt=dt)

            output_root_poses = np.zeros((3, trial_len))
            for index in range(3):
                root_pose = root_poses[index, :]
                target_accs = target_root_linear_accs[index, :]
                for t in range(trial_len):
                    if not track_indices[t]:
                        target_accs[t] = 0.0
                output = smooth_and_track.minimize(root_pose, target_accs)
                output_root_poses[index, :] = output.series
                offset = output.accelerationOffset

                input_acc = np.zeros(trial_len)
                output_acc = np.zeros(trial_len)
                for t in range(1, trial_len - 1):
                    input_acc[t] = (root_pose[t + 1] - 2 * root_pose[t] + root_pose[t - 1]) / (dt * dt)
                    output_acc[t] = (output.series[t + 1] - 2 * output.series[t] + output.series[t - 1]) / (dt * dt)
                if trial_len > 2:
                    input_acc[0] = input_acc[1]
                    input_acc[trial_len - 1] = input_acc[trial_len - 2]
                    output_acc[0] = output_acc[1]
                    output_acc[trial_len - 1] = output_acc[trial_len - 2]

            output_root_acc = np.zeros((3, trial_len))
            for t in range(1, trial_len - 1):
                output_root_acc[:, t] = (output_root_poses[:, t + 1] - 2 * output_root_poses[:, t] + output_root_poses[:,
                                                                                                     t - 1]) / (dt * dt)
            if trial_len > 2:
                output_root_acc[:, 0] = output_root_acc[:, 1]
                output_root_acc[:, trial_len - 1] = output_root_acc[:, trial_len - 2]
            # print("Output root linear accs: " + str(np.mean(output_root_acc, axis=1)))

            average_root_offset_distance = np.mean(np.linalg.norm(output_root_poses - root_poses, axis=0))
            if average_root_offset_distance < 0.03:
                print("Average root offset distance: " + str(average_root_offset_distance))
                updated_poses = poses.copy()
                updated_poses[3:6, :] = output_root_poses
                dynamics_prefit_poses.append(updated_poses)
                dynamics_prefit_trials.append(trial)
            else:
                print("Average root offset distance too large, not applying dynamics to this trial: " + str(
                    average_root_offset_distance))

        ##########################################################################################################
        # Stage 2: Full "kitchen sink" optimization
        ##########################################################################################################

        if len(dynamics_prefit_trials) > 0:
            dynamics_trials = dynamics_prefit_trials

            # Create new force plates, to reflect the smoothed contact data
            trial_foot_force_plates = []
            for trial in dynamics_trials:
                cop_torque_force_world = trial_protos[trial].getPasses()[1].getGroundBodyCopTorqueForce()
                num_plates = int(cop_torque_force_world.shape[0] / 9)
                force_plate_list = []
                for i in range(num_plates):
                    force_plate = nimble.biomechanics.ForcePlate()
                    forces: List[np.ndarray] = []
                    moments: List[np.ndarray] = []
                    centers_of_pressure: List[np.ndarray] = []
                    for t in range(subject.getTrialLength(trial)):
                        forces.append(cop_torque_force_world[i * 9 + 6:i * 9 + 9, t])
                        moments.append(cop_torque_force_world[i * 9 + 3:i * 9 + 6, t])
                        centers_of_pressure.append(cop_torque_force_world[i * 9:i * 9 + 3, t])
                    force_plate.forces = forces
                    force_plate.moments = moments
                    force_plate.centersOfPressure = centers_of_pressure
                    force_plate_list.append(force_plate)
                trial_foot_force_plates.append(force_plate_list)

            dynamics_fitter.setCOMHistogramClipBuckets(1)
            dynamics_fitter.setFillInEndFramesGrfGaps(50)
            dynamics_init: nimble.biomechanics.DynamicsInitialization = \
                nimble.biomechanics.DynamicsFitter.createInitialization(
                    skel,
                    markers_map,
                    osim.trackingMarkers,
                    foot_bodies,
                    trial_foot_force_plates,
                    dynamics_prefit_poses,
                    [int(1.0 / trial_protos[trial].getTimestep()) for trial in dynamics_trials],
                    [trial_protos[trial].getMarkerObservations() for trial in dynamics_trials],
                    [],
                    [[
                         nimble.biomechanics.MissingGRFStatus.no if reason == nimble.biomechanics.MissingGRFReason.notMissingGRF else nimble.biomechanics.MissingGRFStatus.yes
                         for reason in trial_protos[trial].getMissingGRFReason()] for trial in dynamics_trials])

            good_frames_count = 0
            total_frames_count = 0
            for trialMissingGRF in dynamics_init.probablyMissingGRF:
                good_frames_count += sum(
                    [0 if missing == nimble.biomechanics.MissingGRFStatus.yes else 1 for missing in
                     trialMissingGRF])
                total_frames_count += len(trialMissingGRF)
            bad_frames_count = total_frames_count - good_frames_count
            print('Detected missing/bad GRF data on ' + str(bad_frames_count) + '/' + str(
                total_frames_count) + ' frames',
                  flush=True)
            if good_frames_count == 0:
                print('ERROR: we have no good frames of GRF data left after filtering out suspicious GRF '
                      'frames. This probably means input GRF data is badly miscalibrated with respect to '
                      'marker data (maybe they are in different coordinate frames?), or there are unmeasured '
                      'external forces acting on your subject. Aborting the physics fitter!', flush=True)
            else:
                # Run an optimization to figure out the model parameters
                dynamics_fitter.setIterationLimit(200)
                dynamics_fitter.setLBFGSHistoryLength(20)

                dynamics_fitter.runIPOPTOptimization(
                    dynamics_init,
                    nimble.biomechanics.DynamicsFitProblemConfig(skel)
                    .setDefaults(True)
                    .setResidualWeight(1e-2)
                    .setMaxNumTrials(4)
                    .setConstrainResidualsZero(False)
                    .setMaxNumBlocksPerTrial(20)
                    # .setIncludeInertias(True)
                    # .setIncludeCOMs(True)
                    .setIncludeBodyScales(True)
                    .setIncludeMarkerOffsets(False)
                    .setIncludePoses(True)
                    .setJointWeight(0.0)  # We have to disable this, because we don't have the joint info
                    .setMarkerWeight(50.0)
                    # .setRegularizeAnatomicalMarkerOffsets(0.1)
                    # .setRegularizeTrackingMarkerOffsets(0.01)
                    # .setRegularizeBodyScales(1.0)
                    .setRegularizeBodyScales(1.0)
                    .setRegularizePoses(0.01)
                    .setRegularizeJointAcc(1e-6))

                dynamics_pass = subject.getHeaderProto().addProcessingPass()
                dynamics_fitter.applyInitToSkeleton(skel, dynamics_init)
                osim_file_xml = scale_opensim_model(
                    subject.getOpensimFileText(0),
                    skel,
                    skel.getMass(),
                    subject.getHeightM(),
                    dynamics_init.updatedMarkerMap)
                dynamics_pass.setOpenSimFileText(osim_file_xml)
                dynamics_pass.setProcessingPassType(
                    nimble.biomechanics.ProcessingPassType.DYNAMICS)

                # Now re-run a position-only optimization on every trial in the dataset
                for segment in range(len(dynamics_init.poseTrials)):
                    if len(dynamics_init.probablyMissingGRF[segment]) < 1000:
                        dynamics_fitter.setIterationLimit(200)
                        dynamics_fitter.setLBFGSHistoryLength(20)
                    elif len(dynamics_init.probablyMissingGRF[segment]) < 5000:
                        dynamics_fitter.setIterationLimit(100)
                        dynamics_fitter.setLBFGSHistoryLength(15)
                    else:
                        dynamics_fitter.setIterationLimit(50)
                        dynamics_fitter.setLBFGSHistoryLength(3)

                    dynamics_fitter.runIPOPTOptimization(
                        dynamics_init,
                        nimble.biomechanics.DynamicsFitProblemConfig(
                            skel)
                        .setDefaults(True)
                        .setOnlyOneTrial(segment)
                        .setResidualWeight(1e-2)
                        .setConstrainResidualsZero(False)
                        .setIncludePoses(True)
                        .setJointWeight(0.0)  # We have to disable this, because we don't have the joint info
                        .setMarkerWeight(50.0)
                        .setRegularizePoses(0.01)
                        .setRegularizeJointAcc(1e-6))

                    dynamics_positions = dynamics_init.poseTrials[segment]

                    trial_proto = trial_protos[dynamics_trials[segment]]
                    marker_observations = trial_proto.getMarkerObservations()

                    dynamics_ik_error_report = nimble.biomechanics.IKErrorReport(
                        skel,
                        markers_map,
                        dynamics_positions,
                        marker_observations)

                    trial_dynamics_data = trial_proto.addPass()
                    trial_dynamics_data.setType(nimble.biomechanics.ProcessingPassType.DYNAMICS)
                    trial_dynamics_data.setDofPositionsObserved([True for _ in range(skel.getNumDofs())])
                    trial_dynamics_data.setDofVelocitiesFiniteDifferenced(
                        [True for _ in range(skel.getNumDofs())])
                    trial_dynamics_data.setDofAccelerationFiniteDifferenced(
                        [True for _ in range(skel.getNumDofs())])
                    trial_dynamics_data.computeValuesFromForcePlates(skel,
                                                                     subject.getTrialTimestep(dynamics_trials[segment]),
                                                                     dynamics_positions,
                                                                     subject.getGroundForceBodies(),
                                                                     trial_foot_force_plates[segment])
                    trial_dynamics_data.setMarkerRMS(dynamics_ik_error_report.rootMeanSquaredError)
                    trial_dynamics_data.setMarkerMax(dynamics_ik_error_report.maxError)
                    any_good_dynamics_trials = True
