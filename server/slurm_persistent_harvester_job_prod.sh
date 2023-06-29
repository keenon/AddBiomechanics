#!/bin/bash
#
#SBATCH --job-name=addbiomechanics_mocapserver_dev
#SBATCH --dependency=singleton
#SBATCH --time=00:60:00
#SBATCH --signal=B:SIGUSR1@90
#SBATCH --cpus-per-task=4
#SBATCH --mem=4000M
#SBATCH --partition=bioe

# catch the SIGUSR1 signal
_resubmit() {
    ## Resubmit the job for the next execution
    echo "$(date): job $SLURM_JOBID received SIGUSR1 at $(date), re-submitting"
    sbatch $0
}
trap _resubmit SIGUSR1

ml python/3.9.0
## Run the data harvester, in the background so that we don't lose the trap signal
CERT_HOME="/home/users/keenon/certs" python3 ~/AddBiomechanics/server/app/data_harvester.py --bucket biomechanics-uploads83039-prod --deployment PROD &
# Don't exit while the harvester is running
wait