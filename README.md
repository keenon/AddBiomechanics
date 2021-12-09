### BiomechanicsNet

This is an open effort to assemble a large dataset of human motion, recorded from several modalities (kinematics, GRF, EMG, and IMU). We compose this dataset out of dozens of heterogeneous motion capture datasets published in both biomechanics and computer graphics. While there are dozens of these datasets, few contain everything we’d like. For example, [Mahmood et. al](https://amass.is.tue.mpg.de/) is very large and covers many motion types, but contains only skeleton kinematics (no GRF, EMG, or accelerometers). [Carmago et. al](http://www.epic.gatech.edu/opensource-biomechanics-camargo-et-al/) contains EMG, motion capture, and GRF data for motions on uneven surfaces, but only for the lower-half of the body. [Lencioni et. al](https://springernature.figshare.com/collections/Human_kinematic_kinetic_and_EMG_data_during_level_walking_toe_heel-walking_stairs_ascending_descending/4494755) contains EMG, motion capture, and GRF data for the whole body, but only for walking up and down stairs. There are dozens more datasets, each with its own idiosyncrasies.

Our goal in this project is to provide a standard format for modality-sparse human motion data, and loaders for as many datasets as we can. We standardize on the [Rajagopal Human Body Model](https://simtk.org/projects/full_body), as implemented in the [Nimble Physics Engine](https://nimblephysics.org).

Licenses-permitting, we plan to make pre-translated aggregate datasets available for public download.

## Getting Set Up

1. Download (credentials)[https://drive.google.com/file/d/1okCCdvqaZh20gc4TG152o7yJV9_vnBtf/view?usp=sharing] into `.devcontainer/.aws/credentials` and `server/.aws/credentials`.
2. Download (server_credentials.csv)[https://drive.google.com/file/d/1e1GrwpOm0viZhNGkw_lDNPa_cfYhJ3r3/view?usp=sharing] into `.devcontainer/server_credentials.csv` and `server/server_credentials.csv`.
3. Open this project in VSCode, and then use Ctrl+Shift+P and get to the command "Remote-Containers: Open Folder in Container...". Re-open this folder in a Docker container.
4. Using a VSCode Terminal, navigate to `frontend` and execute `yarn start` to begin serving a live frontend
