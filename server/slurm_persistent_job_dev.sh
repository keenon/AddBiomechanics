#!/bin/bash
#
#SBATCH --job-name=dev_addb_mocapserver
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

# This is a dead man's switch, and has a timeout of 2 hours on the server. We requeue this job every 60 minutes, so hitting this once per job should keep things running.
curl -fsS -m 10 --retry 5 -o /dev/null https://hc-ping.com/29f8f84e-3b4e-4978-a045-96ff71ed6fb3

## Run the mocap server, in SLURM mode, in the background so that we don't lose the trap signal
export PYTHONUNBUFFERED=1
CERT_HOME="/home/users/keenon/certs" python3 ~/AddBiomechanics/server/app/mocap_server.py --bucket biomechanics-uploads161949-dev --deployment DEV --singularity_image_path $GROUP_HOME/keenon/simg/biomechnet_dev_latest.sif || true &
# Loop forever, printing the time
while true; do
    echo "$(date): normal execution"
    sleep 60 &
    wait $!
done