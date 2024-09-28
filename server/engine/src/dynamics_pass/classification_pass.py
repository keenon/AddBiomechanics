import nimblephysics as nimble
from typing import List, Tuple
import numpy as np


def get_num_steps(raw_force_plate_forces: List[List[np.ndarray]],
                  raw_force_plate_cops: List[List[np.ndarray]]) -> Tuple[int, List[int]]:
    num_force_plates = len(raw_force_plate_forces)
    trial_len = len(raw_force_plate_forces[0])
    num_steps = 0
    num_steps_per_force_plate = [0 for _ in range(num_force_plates)]
    last_in_contact = [False for _ in range(num_force_plates)]
    for t in range(trial_len):
        forces = [raw_force_plate_forces[f][t] for f in range(num_force_plates)]
        for f in range(len(forces)):
            force = forces[f]
            if np.linalg.norm(force) > 10.0:
                if not last_in_contact[f]:
                    last_in_contact[f] = True
            else:
                if last_in_contact[f]:
                    last_in_contact[f] = False
                    num_steps += 1
                    num_steps_per_force_plate[f] += 1
                last_in_contact[f] = False
    for f in range(num_force_plates):
        if last_in_contact[f]:
            num_steps += 1
            num_steps_per_force_plate[f] += 1
    return num_steps, num_steps_per_force_plate


def get_foot_travel_distance_in_contact(skel: nimble.dynamics.Skeleton,
                                        ground_bodies: List[nimble.dynamics.BodyNode],
                                        positions: np.ndarray,
                                        raw_force_plate_forces: List[List[np.ndarray]],
                                        raw_force_plate_cops: List[List[np.ndarray]]) -> List[float]:
    trial_len = len(raw_force_plate_forces[0])
    num_contact_bodies = len(ground_bodies)
    body_last_in_contact = [False for _ in range(num_contact_bodies)]
    body_started_contact = [np.zeros(3) for _ in range(num_contact_bodies)]
    body_last_position = [np.zeros(3) for _ in range(num_contact_bodies)]
    step_travel_distances = []
    for t in range(trial_len):
        skel.setPositions(positions[:, t])
        ground_body_locations = [body.getWorldTransform().translation() for body in ground_bodies]
        forces = [raw_force_plate_forces[f][t] for f in range(len(raw_force_plate_forces))]
        for f in range(len(ground_body_locations)):
            force = forces[f * 3:f * 3 + 3]
            if np.linalg.norm(force) > 10.0:
                body_last_position[f] = ground_body_locations[f]
                if not body_last_in_contact[f]:
                    body_started_contact[f] = ground_body_locations[f]
                    body_last_in_contact[f] = True
            else:
                if body_last_in_contact[f]:
                    body_last_in_contact[f] = False
                    step_travel_distances.append(np.linalg.norm(body_last_position[f] - body_started_contact[f]))
    for f in range(num_contact_bodies):
        if body_last_in_contact[f]:
            step_travel_distances.append(np.linalg.norm(body_last_position[f] - body_started_contact[f]))
    return step_travel_distances


def get_root_box_volume(positions: np.ndarray):
    # Compute the root box volumes
    root_translation = positions[3:6, :]
    root_box_lower_bound = np.min(root_translation, axis=1)
    root_box_upper_bound = np.max(root_translation, axis=1)
    root_box_volume = np.sum(root_box_upper_bound - root_box_lower_bound)
    return root_box_volume


def estimate_trial_type(skel: nimble.dynamics.Skeleton,
                        foot_bodies: List[nimble.dynamics.BodyNode],
                        positions: np.ndarray,
                        velocities: np.ndarray,
                        raw_force_plate_forces: List[List[np.ndarray]],
                        raw_force_plate_cops: List[List[np.ndarray]]) -> nimble.biomechanics.BasicTrialType:
    num_force_plates = len(raw_force_plate_forces)
    num_steps, _ = get_num_steps(raw_force_plate_forces, raw_force_plate_cops)
    step_travel_distances = get_foot_travel_distance_in_contact(skel, foot_bodies, positions,
                                                                raw_force_plate_forces, raw_force_plate_cops)
    root_box_volume = get_root_box_volume(positions)
    max_root_rot_vel = np.max(np.abs(velocities[0:3, :]))

    if root_box_volume < 0.06 or max_root_rot_vel < 0.1:
        return nimble.biomechanics.BasicTrialType.STATIC_TRIAL
    if root_box_volume > 0.8:
        return nimble.biomechanics.BasicTrialType.OVERGROUND
    if len(step_travel_distances) > 0 and np.max(step_travel_distances) > 0.4 and num_force_plates == 2:
        return nimble.biomechanics.BasicTrialType.TREADMILL
    if num_steps > 15 and num_force_plates == 2:
        return nimble.biomechanics.BasicTrialType.TREADMILL
    return nimble.biomechanics.BasicTrialType.OVERGROUND


def classification_pass(subject: nimble.biomechanics.SubjectOnDisk):
    """
    This
    """
    header_proto = subject.getHeaderProto()
    trial_protos = header_proto.getTrials()

    skel = subject.readSkel(0, ignoreGeometry=True)
    foot_bodies = [skel.getBodyNode(body_name) for body_name in subject.getGroundForceBodies()]

    for i in range(subject.getNumTrials()):
        trial_proto = trial_protos[i]
        passes = trial_proto.getPasses()

        if len(passes) > 0:
            raw_force_plates: List[nimble.biomechanics.ForcePlate] = trial_proto.getForcePlates()
            raw_force_plate_forces: List[List[np.ndarray]] = [plate.forces for plate in raw_force_plates]
            raw_force_plate_cops: List[List[np.ndarray]] = [plate.centersOfPressure for plate in raw_force_plates]

            positions = passes[-1].getPoses()
            vels = passes[-1].getVels()

            estimated_type = estimate_trial_type(skel, foot_bodies, positions, vels, raw_force_plate_forces, raw_force_plate_cops)

            trial_proto.setBasicTrialType(estimated_type)
