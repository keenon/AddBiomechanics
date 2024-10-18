# import opensim as osim
# import matplotlib.pyplot as plt
# import numpy as np

# grf = osim.TimeSeriesTable(os.path.join(TEST_DATA_PATH, 'rajagopal2015', 'trials', 'walk', 'grf.mot'))
# markers = osim.TimeSeriesTableVec3(os.path.join(TEST_DATA_PATH, 'rajagopal2015', 'trials', 'walk', 'markers.trc'))
# marker_times = markers.getIndependentColumn()
# grf_r_vy = grf.getDependentColumn('ground_force_r_vy')
# grf_l_vy = grf.getDependentColumn('ground_force_l_vy')

# plt.plot(grf_r_vy, label='Right')
# plt.plot(grf_l_vy, label='Left')
# plt.xlabel('Time (s)')
# plt.ylabel('Vertical GRF (N)')
# plt.legend()

# header_proto = subject_on_disk.getHeaderProto()
# trial_protos = header_proto.getTrials()
# for i in range(subject_on_disk.getNumTrials()):
#     missingGRFReasons = trial_protos[i].getMissingGRFReason()
#     for itime in range(len(missingGRFReasons)):
#         print(f"Trial {i} frame {itime} missing GRF: {missingGRFReasons[itime]}")
#         if not missingGRFReasons[itime] == nimble.biomechanics.MissingGRFReason.notMissingGRF:
#             time = marker_times[itime]
#             igrf = grf.getNearestRowIndexForTime(time)
#             plt.axvline(x=igrf, color='red', linestyle='--')
# plt.show()