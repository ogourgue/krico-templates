#!/bin/sh
#SBATCH --job-name=DWL_1994
#SBATCH --time=2:00:00
#SBATCH --qos=nf
#SBATCH --array=0-71
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1

module load python3

# Define the year for January-October.
YEAR=1994

# Define the months to process.
MONTHS=(11 12 1 2 3 4 5 6 7 8 9 10)

# Define the download scripts (6 scripts, not including compute_kh).
SCRIPTS=(
    "download_u.py"
    "download_v.py"
    "download_w.py"
    "download_kz.py"
    "download_temp.py"
    "download_ice.py"
)

# Calculate which month and which script to run.
# 12 months x 6 scripts = 72 tasks total.
MONTH_IDX=$((SLURM_ARRAY_TASK_ID / 6))
SCRIPT_IDX=$((SLURM_ARRAY_TASK_ID % 6))

# Get the month and script name.
MONTH=${MONTHS[$MONTH_IDX]}
SCRIPT=${SCRIPTS[$SCRIPT_IDX]}

# Determine the actual year: Nov and Dec are from previous year.
if [ $MONTH -eq 11 ] || [ $MONTH -eq 12 ]; then
    ACTUAL_YEAR=$((YEAR - 1))
else
    ACTUAL_YEAR=$YEAR
fi

# Execute the script
python3 ${SCRIPT} ${ACTUAL_YEAR} ${MONTH}
