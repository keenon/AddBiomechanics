#!/bin/bash
#
#SBATCH --job-name=addbiomechanics_mocapserver_prod
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
python3 /app/mocap_server.py --bucket biomechanics-uploads83039-prod --deployment PROD --singularity_image_path $GROUP_HOME/keenon/biomechnet_prod.spk &