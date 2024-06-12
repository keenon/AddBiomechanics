import nimblephysics as nimble
import numpy as np
import matplotlib.pyplot as plt

files = [
    'AB06_ground_truth.b3d',
    'AB06_hidden_steps.b3d',
    'AB06_independent_segments_baseline.b3d'
]

knee_torques = []
start_ends = []
all_timestamps = []

for file in files:
    subject = nimble.biomechanics.SubjectOnDisk(file)

    skel = subject.readSkel(2, ignoreGeometry=True)
    for d in range(skel.getNumDofs()):
        print(skel.getDofByIndex(d).getName())
    right_knee_index = skel.getDof("knee_angle_l").getIndexInSkeleton()

    marker_rmss = []
    linear_residuals = []
    subject_knee_torques = []
    subject_timestamps = []
    subject_start_ends = []
    for trial in range(subject.getNumTrials()):
        trial_start_ends = []
        selected = [reason == nimble.biomechanics.MissingGRFReason.notMissingGRF for reason in subject.getMissingGRF(trial)]
        marker_rms = np.mean(np.array(subject.getTrialMarkerRMSs(trial, 2))[selected])
        linear_residual = np.mean(np.array(subject.getTrialLinearResidualNorms(trial, 2))[selected])
        print(f"Trial: {trial} Marker RMS: {marker_rms} Linear Residual: {linear_residual}")
        marker_rmss.append(marker_rms)
        linear_residuals.append(linear_residual)
        frames = subject.readFrames(trial, 0, subject.getTrialLength(trial))
        tau_recovered = np.array([frame.processingPasses[2].tau[right_knee_index] for frame in frames])
        timestamps = np.array([frame.t * subject.getTrialTimestep(trial) for frame in frames])
        start = -1
        for i in range(len(tau_recovered)):
            if np.isnan(tau_recovered[i]) or selected[i] == False:
                tau_recovered[i] = np.nan
                if start == -1:
                    start = i * subject.getTrialTimestep(trial)
            else:
                if start != -1:
                    trial_start_ends.append((start, i * subject.getTrialTimestep(trial)))
                    start = -1
            if tau_recovered[i] > 100:
                tau_recovered[i] = 100
            if tau_recovered[i] < -100:
                tau_recovered[i] = -100
        subject_knee_torques.append(tau_recovered)
        subject_timestamps.append(timestamps)
        subject_start_ends.append(trial_start_ends)
    knee_torques.append(subject_knee_torques)
    start_ends.append(subject_start_ends)
    all_timestamps.append(subject_timestamps)

    print(f"File: {file}")
    print(f"Marker RMS: {np.mean(marker_rmss)} +/- {np.std(marker_rmss)}")
    print(f"Linear Residuals: {np.mean(linear_residuals)} +/- {np.std(linear_residuals)}")

# Compute RMS of knee torques compared to the first one
for i in range(1, len(files)):
    rms = np.mean(np.sqrt(np.mean((knee_torques[i][0] - knee_torques[0][0])**2, axis=0)))
    print(f"RMS of knee torques compared to {files[0]}: {rms}")

# Plot knee torques
labels = ['Oracle', 'Our Method', 'Piecewise Baseline']
plt.figure()
x_axis = all_timestamps[0][0]
for i, file in enumerate(files):
    plt.plot(all_timestamps[i][0], knee_torques[i][0], label=labels[i])
    # plt.plot(knee_torques[i][0], label=labels[i])
plt.ylabel('Knee torque (Nm)')
plt.xlabel('Time (s)')

# Shade the background between specific timesteps
for start_time, end_time in start_ends[1][0]:
    print(start_time, end_time)
    plt.axvspan(start_time, end_time, color='grey', alpha=0.5)

plt.legend()
plt.show()