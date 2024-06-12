#!/bin/bash
#
#SBATCH --job-name=publish_dataset
#SBATCH --time=48:00:00
#SBATCH --signal=B:SIGUSR1@90
#SBATCH --cpus-per-task=1
#SBATCH --mem=4000M
#SBATCH --partition=bioe

ml python/3.9.0
python3 ~/AddBiomechanics/server/app/data_publisher.py --standard-model rajagopal_with_arms --target-gdrive-folder May15_2024_Rajagopal_With_Arms