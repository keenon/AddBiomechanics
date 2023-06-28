import org.opensim.modeling.*;

% Update the model.
% -----------------
% Replace locked coordinates with weld joints.
model = Model('../Models/final.osim');
model.initSystem();
coordinates = model.getCoordinateSet();
locked_joints = StdVectorString();
locked_coordinates = {};
for icoord = 0:coordinates.getSize()-1
    coord = coordinates.get(icoord);
    if coord.get_locked()
        locked_coordinates{end+1} = char(coord.getName());
        locked_joints.add(coord.getJoint().getName());
    end
end

% Remove actuators associated with locked coordinates.
for i = 1:length(locked_coordinates)
    coordinate = locked_coordinates{i};
    forceSet = model.updForceSet();
    for iforce = 0:forceSet.getSize()-1
        force = forceSet.get(iforce);
        actu = CoordinateActuator.safeDownCast(force);
        if ~isempty(actu) 
            if strcmp(actu.get_coordinate(), coordinate)
                forceSet.remove(iforce);
                break;
            end
        end
    end
end

model.finalizeConnections();
model.initSystem();

% Construct a ModelProcessor.
modelProcessor = ModelProcessor(model);
modelProcessor.append(ModOpReplaceJointsWithWelds(locked_joints));
modelProcessor.append(ModOpAddExternalLoads('../ID/@TRIAL@_external_forces.xml'));
modelProcessor.append(ModOpIgnoreTendonCompliance());
modelProcessor.append(ModOpReplaceMusclesWithDeGrooteFregly2016());
modelProcessor.append(ModOpIgnorePassiveFiberForcesDGF());
modelProcessor.append(ModOpAddReserves(50.0));

% Construct the MocoInverse tool.
inverse = MocoInverse();

% Set the model processor and time bounds.
inverse.setModel(modelProcessor);
inverse.set_initial_time(@INITIAL_TIME@);
inverse.set_final_time(@FINAL_TIME@);

% Load the kinematics data source.
table = TimeSeriesTable('../IK/@TRIAL@_ik.mot');
labels = table.getColumnLabels();
for i = 0:labels.size()-1
    if strcmp(char(labels.get(i)), 'knee_angle_r')
        table.appendColumn('knee_angle_r_beta', ...
            table.getDependentColumn('knee_angle_r'));
    end
    if strcmp(char(labels.get(i)), 'knee_angle_l')
        table.appendColumn('knee_angle_l_beta', ...
            table.getDependentColumn('knee_angle_l'));
    end
end

% Construct a TableProcessor to update the kinematics table labels.
tableProcessor = TableProcessor(table);
tableProcessor.append(TabOpUseAbsoluteStateNames());
inverse.setKinematics(tableProcessor);

% Configure additional settings for the MocoInverse problem.
inverse.set_mesh_interval(0.02);
inverse.set_convergence_tolerance(1e-5);
inverse.set_constraint_tolerance(1e-5);
inverse.set_max_iterations(2000);
inverse.set_kinematics_allow_extra_columns(true);

% Solve the problem.
% ------------------
% Solve the problem and write the solution to a Storage file.
solution = inverse.solve();
solution.getMocoSolution().write('@TRIAL@_moco.sto');