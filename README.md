# KRICO: Templates

Reusable simulation templates for Lagrangian particle tracking of Antarctic krill larval dispersal using Parcels and GLORYS12v1 ocean reanalysis. Complete workflow for 3D advection-diffusion simulations across CCAMLR Areas 48 and 88 (1994–2025).

Author: Olivier Gourgue (RBINS)

Related repositories:

* __[krico-post-production](https://github.com/ogourgue/krico-post-production)__ — Post-processing and recruitment classification pipeline
* __[krico-paper1](https://github.com/ogourgue/krico-paper1)__ — Paper 1 figure reproduction

## Repository Structure

```
krico-templates/
├── Pre/
│   └── GLORYS12/
│       └── [Data preprocessing scripts for GLORYS12v1 reanalysis]
│
└── Runs/
    └── KRICO_GLORYS12/
        └── [Parcels simulation scripts for larval tracking]
```

## Workflow Overview

The simulation pipeline consists of two stages:

### Stage 1: **Pre/GLORYS12/** — Data Preprocessing

Download and preprocess GLORYS12v1 ocean reanalysis fields for your simulation period:

- **Static files** (one-time): bathymetry, grid coordinates
- **Monthly data** (per year): velocity (u, v, w), temperature, vertical mixing coefficient, sea ice concentration
- **Computed fields** (post-processing): horizontal diffusivity (Smagorinsky formulation)

Output: Monthly NetCDF4 files ready for Parcels forcing

**→ See [Pre/GLORYS12/README.md](Pre/GLORYS12/README.md) for detailed instructions**

### Stage 2: **Runs/KRICO_GLORYS12/** — Lagrangian Simulations

Release particles from Antarctic spawning habitats (1000–2000 m bathymetry) and track them for 200 days post-release using GLORYS12v1 forcing:

- **Particle release**: ~500,000 particles/day from slope zone within CCAMLR Statistical Areas
- **Release depth**: 50–200 m (uniform distribution)
- **Tracking period**: 200 days with daily output
- **Physics**: 3D RK4 advection, stochastic horizontal/vertical diffusion, boundary conditions
- **Variables tracked**: position, depth, temperature, bathymetry, sea ice concentration

Output: Daily position data for all particles in compressed NetCDF4 format (~1.6–1.7 GB per release day)

**→ See [Runs/KRICO_GLORYS12/README.md](Runs/KRICO_GLORYS12/README.md) for detailed instructions**

## Quick Start

1. **Prepare forcing data**:
   ```bash
   cd Pre/GLORYS12/
   sbatch download_static.sh                 # One-time static files
   cp download_template.sh download_1994.sh
   # Edit download_1994.sh with your year
   sbatch download_1994.sh                   # Monthly data for 1994
   cp compute_template.sh compute_1994.sh
   # Edit compute_1994.sh with your year
   sbatch compute_1994.sh                    # Compute horizontal diffusivity
   ```

2. **Run simulations**:
   ```bash
   cd ../../Runs/KRICO_GLORYS12/
   # Edit job.sh with your release year/month
   sbatch job.sh                             # Run simulations for one month
   ```

3. **Convert output**:
   - Conversion happens automatically in `job.sh`
   - Manual conversion: `python zarr_to_netcdf.py YYYY_MM_DD`

## Key Features

- **Reusable templates**: Adapt for different forcing datasets, domains, or release strategies
- **Production-ready**: Validated against observations; used for 30-year hindcast (1993–2023)
- **Robust error handling**: Three simulation versions (run.py, run_bis.py, run_ter.py) for problematic dates
- **Efficient I/O**: Parallel MPI execution, automatic zarr→NetCDF4 conversion with lossless compression
- **Fully documented**: Extensive inline comments explaining physics and numerical methods

## Requirements

- **HPC environment**: SLURM cluster with MPI support. **Note**: All SLURM scripts (`job.sh`, `*_template.sh`) are written specifically for ECMWF HPC2020. On other clusters, use these as templates/inspiration; structural differences in module systems, queue names, and resource limits will require adaptation.
- **Software**: Parcels v3.x, Python 3.8+, xarray, geopandas, numpy, mpi4py
- **Data access**: Internet or institutional access to Mercator Ocean OpenDAP servers (for downloading GLORYS12v1)
- **Storage**: ~5–10 TB for full 30-year dataset (compressed NetCDF4)

## Customization

Both stages include template files for easy adaptation:

- **Pre/GLORYS12/**:
  - `download_template.sh` → `download_YYYY.sh` for your year
  - `compute_template.sh` → `compute_YYYY.sh` for your year

- **Runs/KRICO_GLORYS12/**:
  - `job.sh`: Edit `YEAR` and `MONTH` for your release period
  - `run.py` / `run_bis.py` / `run_ter.py`: Modify particle density, timestep, domain

## References

- **Parcels documentation**: https://parcels.readthedocs.io/
- **GLORYS12v1 data**: https://tds.mercator-ocean.fr/thredds/glorys12v1/
- **CCAMLR Statistical Areas**: https://www.ccamlr.org/
- **KRICO methodology**: See krico-paper1 repository for publication details

## License

GNU General Public License v3.0 — See LICENSE file

---

**Maintainer**: Olivier Gourgue (ECOMOD, RBINS)
**Last updated**: May 2026