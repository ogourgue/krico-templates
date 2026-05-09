# Parcels Simulations: KRICO GLORYS12v1

This folder contains Parcels simulation scripts for KRICO Lagrangian particle tracking on GLORYS12v1 ocean reanalysis.

## Overview

The simulation pipeline:

1. **Setup**: Prepare forcing data from Pre/GLORYS12/ (download completed first)
2. **Run**: Execute Parcels particle tracking simulations via `job.sh` (MPI parallelized)
3. **Convert**: Convert zarr outputs to compressed NetCDF4 via `zarr_to_netcdf.py`

## File Structure

```
Runs/KRICO_GLORYS12/
├── README.md (this file)
├── job_template.sh              # SLURM job script template
├── run.py                        # Parcels simulation script (primary version)
├── run_bis.py                    # Alternative version (for problematic dates)
├── run_ter.py                    # Final version (for remaining problematic dates)
└── zarr_to_netcdf.py            # Output conversion script
```

## Simulation Setup

### Release Strategy

- **Domain**: Slope zone (1000–2000 m bathymetry)
- **Density**: ~1.0 particle/km²
- **Release depth**: 50–200 m (uniform)
- **Release period**: 15th of month to 14th of next month (31 days × ~500k particles/day)
- **Tracking duration**: 200 days post-release
- **Advection**: 3D RK4, 30-minute timestep, Milstein stochastic diffusion
- **Behavior**: Passive tracers (no DVM, no mortality)

### Variables Tracked

Particles record daily:
- Longitude, latitude, depth
- Temperature (at particle location)
- Bathymetry (nearest grid point)
- Sea ice concentration

Output dimensions:
- ~500,000 particles per release day
- 200 daily observations per particle
- ~1.6–1.7 GB per cohort (compressed NetCDF4)

## Workflow

### Step 1: Download Forcing Data

Complete **Pre/GLORYS12/** preprocessing first:
1. Download static files (`download_static.sh`)
2. Download monthly data for your years (`download_YYYY.sh`)
3. Compute horizontal diffusivity (`compute_YYYY.sh`)

All files should be in place before starting simulations.

### Step 2: Run Simulations

For each release month, edit `job.sh` and submit:

```bash
# Edit job.sh: change YEAR and MONTH to your target month
# Example: YEAR=1993 MONTH=11 runs release dates 15 Nov 1993 to 14 Dec 1993
vi job.sh
sbatch job.sh
```

**Release period**: Each job runs one calendar month worth of release dates (15th to 14th of next month), not a full year.

**Spawning season**: Nov–Feb requires 4 separate job submissions:
- Nov: YEAR=1993 MONTH=11 (15 Nov 1993 – 14 Dec 1993)
- Dec: YEAR=1993 MONTH=12 (15 Dec 1993 – 14 Jan 1994)
- Jan: YEAR=1994 MONTH=1 (15 Jan 1994 – 14 Feb 1994)
- Feb: YEAR=1994 MONTH=2 (15 Feb 1994 – 14 Mar 1994)

**Job resources:**
- Job name: `KRICO_0001` (rename to match your cohort)
- Time: 12 hours (per job array)
- Array: 31 tasks (one per release day)
- MPI tasks: 8 per node
- CPUs per task: 1
- Memory: 16 GB per CPU
- Total per day: ~128 GB (8 tasks × 16 GB)

**What the job does:**
1. Validates each date (skips non-existent dates like Feb 30)
2. Runs Parcels simulation in MPI mode
3. On success: converts zarr → NetCDF4 (automatically)
4. On failure: exits with error code

### Step 3: Troubleshooting with Alternative Versions

If certain release dates crash, **only re-run those dates** with an alternative version:

**Version priority** (in order of attempted use):
1. **`run.py`** — Primary version (used first)
2. **`run_bis.py`** — Alternative 1 (for dates that crashed with run.py)
3. **`run_ter.py`** — Alternative 2 (for dates that crashed with both run.py and run_bis.py)

**Real-world experience**: Some release dates cause crashes when particles evaluate velocity fields below the ocean bottom (depth interpolation error). This typically occurs with extreme forcing conditions. Solutions:

- **`run_bis.py`**: Uses a different random seed for stochastic diffusion. Altered particle trajectories avoid problematic depth evaluations. Solves most crashes.
- **`run_ter.py`**: Implements a depth threshold (5000 m) that removes particles exceeding this depth. These deep particles are scientifically unlikely to reach shelf zones and contribute to recruitment anyway, so removal is acceptable.

**Important**: Only re-submit the specific failing dates, not the entire month. Modify `job.sh`:

```bash
# Edit job.sh to re-run only failed dates:
# Change #SBATCH --array=1-31 to #SBATCH --array=5,8,12,25 (only failed dates)
# Change python run.py to python run_bis.py
vi job.sh
sbatch job.sh
```

This keeps simulation costs manageable and avoids re-computing successful dates.

## Output Conversion

Conversion happens **automatically** in `job.sh` after each successful simulation.

To manually convert (if needed):

```bash
python zarr_to_netcdf.py 1994_11_15
```

**Conversion details:**
- Input: zarr directory (parallel or serial)
- Output: single compressed NetCDF4 file
- Compression: zlib level 5 (lossless)
- Precision: float32 for particle positions/properties
- Size reduction: typically 60–70%
- Parallel zarr files are merged, then converted

**Handles both:**
- Parallel runs: Merges `proc*.zarr` → single zarr → NetCDF4
- Serial runs: Single zarr → NetCDF4

## Customization

Edit `run.py` (or `run_bis.py`, `run_ter.py`):
- Release depth: `release_depth = [50, 200]`
- Tracking duration: `duration = 200` (days)
- Time-stepping: `dt = 1800` (30 minutes)
- Particle density: `n_particles_per_cell = 1.0`

## Notes

- **Date handling**: Job script automatically skips non-existent dates (Feb 30, Nov 31, etc.)
- **Year transitions**: November and December are part of the *following* spawning year's cohort (e.g., Nov/Dec 1993 → 1994 spawning year)
- **Dependencies**: All GLORYS12 forcing files must be downloaded and preprocessed before running simulations
- **MPI environment**: Script loads Intel MPI and Conda environment with Parcels + mpi4py
- **Parallel zarr**: Each MPI rank writes its particles to `proc*.zarr`; `zarr_to_netcdf.py` automatically merges before NetCDF4 conversion

## References

- Parcels documentation: https://parcels.readthedocs.io/
- Parcels GitHub: https://github.com/OceanParcels/parcels
- KRICO methodology: See krico-paper1 for publication details
