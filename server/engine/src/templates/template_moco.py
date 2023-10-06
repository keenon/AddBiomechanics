import opensim as osim
import matplotlib
matplotlib.use('Agg')

# Update the model.
# -----------------
# Replace locked coordinates with weld joints.
model = osim.Model('../Models/final.osim')
model.initSystem()
coordinates = model.getCoordinateSet()
locked_joints = list()
locked_coordinates = list()
for icoord in range(coordinates.getSize()):
    coord = coordinates.get(icoord)
    if coord.get_locked():
        locked_coordinates.append(coord.getName())
        locked_joints.append(coord.getJoint().getName())

# Remove actuators associated with locked coordinates.
for coordinate in locked_coordinates:
    forceSet = model.updForceSet()
    for iforce in range(forceSet.getSize()):
        force = forceSet.get(iforce)
        if force.getConcreteClassName().endswith('CoordinateActuator'):
            actu = osim.CoordinateActuator.safeDownCast(force)
            if actu.get_coordinate() == coordinate:
                forceSet.remove(iforce)
                break

model.finalizeConnections()
model.initSystem()

# Construct a ModelProcessor. The default muscles in the model are replaced with
# optimization-friendly DeGrooteFregly2016Muscles, and adjustments are made to the
# default muscle parameters. We also add reserve actuators to the model and apply
# the external loads.
modelProcessor = osim.ModelProcessor(model)
modelProcessor.append(osim.ModOpReplaceJointsWithWelds(locked_joints))
modelProcessor.append(osim.ModOpAddExternalLoads('../ID/@TRIAL@_external_forces.xml'))
modelProcessor.append(osim.ModOpIgnoreTendonCompliance())
modelProcessor.append(osim.ModOpReplaceMusclesWithDeGrooteFregly2016())
modelProcessor.append(osim.ModOpIgnorePassiveFiberForcesDGF())
modelProcessor.append(osim.ModOpAddReserves(50.0))

# Construct the MocoInverse tool.
# -------------------------------
inverse = osim.MocoInverse()

# Set the model processor and time bounds.
inverse.setModel(modelProcessor)
inverse.set_initial_time(@INITIAL_TIME@)
inverse.set_final_time(@FINAL_TIME@)

# Load the kinematics data source.
# Add in the Rajagopal2015 patella coordinates to the kinematics table, if missing.
table = osim.TimeSeriesTable('../IK/@TRIAL@_ik.mot')
labels = table.getColumnLabels()
if 'knee_angle_r' in labels and 'knee_angle_r_beta' not in labels:
    table.appendColumn('knee_angle_r_beta', table.getDependentColumn('knee_angle_r'))
if 'knee_angle_l' in labels and 'knee_angle_l_beta' not in labels:
    table.appendColumn('knee_angle_l_beta', table.getDependentColumn('knee_angle_l'))

# Construct a TableProcessor to update the kinematics table labels to use absolute path names.
# Add the kinematics to the MocoInverse tool.
tableProcessor = osim.TableProcessor(table)
tableProcessor.append(osim.TabOpUseAbsoluteStateNames())
inverse.setKinematics(tableProcessor)

# Configure additional settings for the MocoInverse problem including the mesh
# interval, convergence tolerance, constraint tolerance, and max number of iterations.
inverse.set_mesh_interval(0.02)
inverse.set_convergence_tolerance(1e-5)
inverse.set_constraint_tolerance(1e-5)
inverse.set_max_iterations(2000)
# Skip any extra columns in the kinematics data source.
inverse.set_kinematics_allow_extra_columns(True)

# Solve the problem.
# ------------------
# Solve the problem and write the solution to a Storage file.
solution = inverse.solve()
solution.getMocoSolution().write('@TRIAL@_moco.sto')

# Generate a PDF with plots for the solution trajectory.
model = modelProcessor.process()
report = osim.report.Report(model,
                            '@TRIAL@_moco.sto',
                            output='@TRIAL@_moco.pdf',
                            bilateral=True)
# The PDF is saved to the working directory.
report.generate()
