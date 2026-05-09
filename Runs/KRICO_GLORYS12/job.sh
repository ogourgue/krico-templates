#!/bin/bash
#SBATCH --job-name=KRICO_0001
#SBATCH --time=12:00:00
#SBATCH --qos=nf
#SBATCH --array=1-31
#SBATCH --ntasks=8
#SBATCH --cpus-per-task=1
#SBATCH --mem-per-cpu=16G

# ============================================================================
# KRICO - SLURM Job Script
# ============================================================================
# This script runs Parcels simulations in parallel for multiple release days.
# Job array spans from 15th of MONTH to 14th of MONTH+1 (31 tasks total).
# Tasks 1-17: Days 15-31 of MONTH
# Tasks 18-31: Days 1-14 of MONTH+1
# Non-existent dates (e.g., Feb 30, Nov 31) are skipped gracefully.
# After simulation completes, zarr output is converted to compressed NetCDF4.
# ============================================================================

# ----------------------------------------------------------------------------
# Load modules and environment
# ----------------------------------------------------------------------------
# Intel MPI setup (required for MPI environment variables)
module load intel-mpi/2025.0.1

# Conda environment containing Parcels and mpi4py
module load conda
conda activate parcels

# Configure Intel MPI for SLURM
export I_MPI_PMI_LIBRARY=/usr/lib64/libpmi2.so
export I_MPI_FABRICS=shm:ofi
export SLURM_MPI_TYPE=pmi2

# ----------------------------------------------------------------------------
# Define simulation parameters
# ----------------------------------------------------------------------------
# Base year and month for the simulation period
# Job array runs from 15th of MONTH to 14th of MONTH+1
YEAR=1993
MONTH=11

# Calculate actual day and month from array task ID
# Tasks 1-17: Days 15-31 of the specified MONTH
# Tasks 18-31: Days 1-14 of MONTH+1
if [ ${SLURM_ARRAY_TASK_ID} -le 17 ]; then
    # Tasks 1-17: Days 15-31 of current month
    DAY=$((14 + ${SLURM_ARRAY_TASK_ID}))
    ACTUAL_MONTH=$MONTH
    ACTUAL_YEAR=$YEAR
else
    # Tasks 18-31: Days 1-14 of next month
    DAY=$((${SLURM_ARRAY_TASK_ID} - 17))
    ACTUAL_MONTH=$((MONTH + 1))
    ACTUAL_YEAR=$YEAR

    # Handle year rollover (December -> January)
    if [ $ACTUAL_MONTH -gt 12 ]; then
        ACTUAL_MONTH=1
        ACTUAL_YEAR=$((YEAR + 1))
    fi
fi

# Validate that this date exists (handles Feb 29-31, Apr 31, etc.)
if ! date -d "${ACTUAL_YEAR}-${ACTUAL_MONTH}-${DAY}" &>/dev/null; then
    echo "=========================================="
    echo "KRICO Simulation"
    echo "=========================================="
    echo "Array task ID: ${SLURM_ARRAY_TASK_ID}"
    echo "Calculated date: ${ACTUAL_YEAR}-${ACTUAL_MONTH}-${DAY}"
    echo ""
    echo "[SKIP] Date does not exist - ending job without error"
    echo "=========================================="
    exit 0
fi

# Use validated date for simulation
YEAR=$ACTUAL_YEAR
MONTH=$ACTUAL_MONTH

# ----------------------------------------------------------------------------
# Print job information
# ----------------------------------------------------------------------------
echo "=========================================="
echo "KRICO Simulation"
echo "=========================================="
echo "Release date: ${YEAR}-${MONTH}-${DAY}"
echo "Array task ID: ${SLURM_ARRAY_TASK_ID}"
echo "Running on node: $(hostname)"
echo "Job ID: ${SLURM_JOB_ID}"
echo "MPI tasks: ${SLURM_NTASKS}"
echo "=========================================="
echo ""

# ----------------------------------------------------------------------------
# Run Parcels simulation with MPI
# ----------------------------------------------------------------------------
echo "Starting Parcels simulation..."
srun python run.py $YEAR $MONTH $DAY

# ----------------------------------------------------------------------------
# Check simulation status and convert output
# ----------------------------------------------------------------------------
if [ $? -eq 0 ]; then
    echo ""
    echo "[SUCCESS] Simulation completed successfully for day ${DAY}"
    echo ""

    # Format filename: YYYY_MM_DD
    MONTH_PADDED=$(printf "%02d" ${MONTH})
    DAY_PADDED=$(printf "%02d" ${DAY})

    # Convert zarr output to compressed NetCDF4
    echo "Converting zarr output to NetCDF4..."
    python zarr_to_netcdf.py ${YEAR}_${MONTH_PADDED}_${DAY_PADDED}

    if [ $? -eq 0 ]; then
        echo ""
        echo "[SUCCESS] Conversion completed successfully for day ${DAY}"
        echo "=========================================="
        echo "Job complete for release day ${DAY}!"
        echo "=========================================="
    else
        echo ""
        echo "[ERROR] Output conversion failed for day ${DAY}"
        exit 1
    fi
else
    echo ""
    echo "[ERROR] Simulation failed for day ${DAY}"
    exit 1
fi
