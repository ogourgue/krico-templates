#!/bin/sh
#SBATCH --job-name=GLO_STAT
#SBATCH --time=1:00:00
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --hint=nomultithread
#SBATCH --qos=np

module load python3
python3 download_bathymetry.py 
python3 download_coordinates.py
