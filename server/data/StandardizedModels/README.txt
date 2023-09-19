Please cite: 
Uhlrich, S.D., Jackson, R.W., Seth, A. Kolesar, J.A., Delp, S.L. Muscle coordination retraining inspired by 
musculoskeletal simulations reduces knee contact force. Sci Rep 12, 9842 (2022). https://doi.org/10.1038/s41598-022-13386-9

FullBodyModel_passiveCal_hipAbdMoved_noArms.osim is identical to FullBodyModel_passiveCal_hipAbdMoved.osim,
but the arms and associated coordinate actuators have been removed. The mass from the arms has been added to
the torso to preserve mass distribution, but the torso center of mass has not been altered. If not tracking 
arms, it may be better to simply lock the arm coordinates or replace the joints with weld joints
for a better estimate of the upper body center of mass location.

By default, the OpenSim GUI will use the model geometry in the install directory (C:\OpenSim4.1\Geometry). If you
are primarily using this model, you can replace that geometry folder with the provided geometry folder. Otherwise, you can
ensure that this geometry folder is in the same folder as the model, or add the path to the new geometry folder in
the OpenSim GUI Edit->Preferences->Paths:Geometry search paths. OpenSim will default to the first path in that list,
so prepend this to the paths in the list. 