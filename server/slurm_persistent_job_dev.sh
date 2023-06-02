#!/bin/bash
#
#SBATCH --job-name=addbiomechanics_mocapserver_dev
#SBATCH --dependency=singleton
#SBATCH --time=00:60:00
#SBATCH --signal=B:SIGUSR1@90
#SBATCH --cpus-per-task=1
#SBATCH --mem=1000M

# catch the SIGUSR1 signal
_resubmit() {
    ## Resubmit the job for the next execution
    echo "$(date): job $SLURM_JOBID received SIGUSR1 at $(date), re-submitting"
    sbatch $0
}
trap _resubmit SIGUSR1

## Run the mocap server, in SLURM mode, in the background so that we don't lose the trap signal
python3 /app/mocap_server.py --bucket biomechanics-uploads161949-dev --deployment DEV --singularity_image_path $GROUP_HOME/keenon/simg/biomechnet_dev_latest.spk &