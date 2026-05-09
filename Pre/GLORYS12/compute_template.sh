#!/bin/sh
#SBATCH --job-name=CMP_1994
#SBATCH --time=2:00:00
#SBATCH --qos=nf
#SBATCH --array=0-11
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=64G

module load python3

# Define the year for January-October.
YEAR=1994

# Define the months to process.
MONTHS=(11 12 1 2 3 4 5 6 7 8 9 10)

# Get the month for this array task.
MONTH=${MONTHS[$SLURM_ARRAY_TASK_ID]}

# Determine the actual year: Nov and Dec are from previous year.
if [ $MONTH -eq 11 ] || [ $MONTH -eq 12 ]; then
    ACTUAL_YEAR=$((YEAR - 1))
else
    ACTUAL_YEAR=$YEAR
fi

# Compute kh (requires u, v, w to be already downloaded).
python3 compute_kh.py ${ACTUAL_YEAR} ${MONTH}
