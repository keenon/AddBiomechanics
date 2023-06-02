#!/bin/bash
#
#SBATCH --job-name=addbiomechanics_mocapserver_dev
#SBATCH --dependency=singleton
#SBATCH --time=00:60:00
#SBATCH --signal=B:SIGUSR1@90
#SBATCH --cpus-per-task=1
#SBATCH --mem=1000M
#SBATCH --partition=bioe

# catch the SIGUSR1 signal
_resubmit() {
    ## Resubmit the job for the next execution
    echo "$(date): job $SLURM_JOBID received SIGUSR1 at $(date), re-submitting"
    sbatch $0
}
trap _resubmit SIGUSR1

ml python/3.9.0
## Run the mocap server, in SLURM mode, in the background so that we don't lose the trap signal
CERT_HOME="/home/users/keenon/certs" python3 ~/AddBiomechanics/server/app/mocap_server.py --bucket biomechanics-uploads161949-dev --deployment DEV --singularity_image_path $GROUP_HOME/keenon/simg/biomechnet_dev_latest.sif &
# Don't exit while the server is running
wait