import opensim as osim
import matplotlib; matplotlib.use('Agg')

# Construct the MocoInverse tool.
# -------------------------------
inverse = osim.MocoInverse()

# Set the model processor and time bounds.
modelProcessor = osim.ModelProcessor('../Models/match_markers_and_physics_moco.osim')
modelProcessor.append(osim.ModOpAddExternalLoads('../ID/@TRIAL@_external_forces.xml'))
modelProcessor.append(osim.ModOpIgnoreTendonCompliance())
modelProcessor.append(osim.ModOpReplaceMusclesWithDeGrooteFregly2016())
modelProcessor.append(osim.ModOpIgnorePassiveFiberForcesDGF())
modelProcessor.append(osim.ModOpScaleMaxIsometricForce(2.0))
modelProcessor.append(osim.ModOpAddReserves(50.0))
modelProcessor.append(osim.ModOpReplacePathsWithFunctionBasedPaths(
        '../Moco/function_based_paths/@MODEL_NAME@_FunctionBasedPathSet.xml'))
inverse.setModel(modelProcessor)

# Set the initial and final times.
inverse.set_initial_time(@INITIAL_TIME@)
inverse.set_final_time(@FINAL_TIME@)

# Load the kinematics data source.
table_processor = osim.TableProcessor('../IK/@TRIAL@_ik.mot')
table_processor.append(osim.TabOpUseAbsoluteStateNames())
table_processor.append(osim.TabOpAppendCoupledCoordinateValues())
inverse.setKinematics(table_processor)

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
inverse_solution = inverse.solve()
solution = inverse_solution.getMocoSolution()
solution.unseal()
solution.write('@TRIAL@_moco.sto')

# Generate a PDF with plots for the solution trajectory.
model = modelProcessor.process()
report = osim.report.Report(model,
                            '@TRIAL@_moco.sto',
                            output='@TRIAL@_moco.pdf',
                            bilateral=True)
# The PDF is saved to the working directory.
report.generate()
