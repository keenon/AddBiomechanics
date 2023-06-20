import opensim as osim

# Construct the MocoInverse tool.
inverse = osim.MocoInverse()

# Construct a ModelProcessor and set it on the tool. The default
# muscles in the model are replaced with optimization-friendly
# DeGrooteFregly2016Muscles, and adjustments are made to the default muscle
# parameters.
modelProcessor = osim.ModelProcessor(@MODEL@)
modelProcessor.append(osim.ModOpAddExternalLoads(@EXTERNAL_LOADS@))
modelProcessor.append(osim.ModOpIgnoreTendonCompliance())
modelProcessor.append(osim.ModOpReplaceMusclesWithDeGrooteFregly2016())
modelProcessor.append(osim.ModOpIgnorePassiveFiberForcesDGF())
modelProcessor.append(osim.ModOpAddReserves(25.0))
inverse.setModel(modelProcessor)

# Construct a TableProcessor of the coordinate data and pass it to the
# inverse tool. TableProcessors can be used in the same way as
# ModelProcessors by appending TableOperators to modify the base table.
# A TableProcessor with no operators, as we have here, simply returns the
# base table.
inverse.setKinematics(osim.TableProcessor(@KINEMATICS@))

# Initial time, final time, and mesh interval.
inverse.set_initial_time(@INITIAL_TIME@)
inverse.set_final_time(@FINAL_TIME@)
inverse.set_mesh_interval(0.02)

# By default, Moco gives an error if the kinematics contains extra columns.
# Here, we tell Moco to allow (and ignore) those extra columns.
inverse.set_kinematics_allow_extra_columns(True)

# Solve the problem and write the solution to a Storage file.
solution_fname = '@TRIAL_NAME@_MocoInverse_solution.sto'
solution = inverse.solve()
solution.getMocoSolution().write('example3DWalking_MocoInverse_solution.sto')

# Generate a PDF with plots for the solution trajectory.
model = modelProcessor.process()
report = osim.report.Report(model,
                            'example3DWalking_MocoInverse_solution.sto',
                            bilateral=True)
# The PDF is saved to the working directory.
report.generate()