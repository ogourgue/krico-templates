# GLORYS12v1 Data Preprocessing

This folder contains scripts to download and preprocess GLORYS12v1 ocean reanalysis data for the KRICO project.

## Overview

The preprocessing pipeline has three stages:

1. **Static files** (one-time): bathymetry, coordinates
2. **Download** (monthly data): ocean velocity (u, v, w), temperature, vertical diffusivity coefficient (kz), sea ice concentration
3. **Compute** (post-processing): horizontal diffusivity (kh) via Smagorinsky formulation

## Variables

| Variable | Script | Description |
|----------|--------|-------------|
| Bathymetry | `download_bathymetry.py` | Ocean depth (one-time) |
| Coordinates | `download_coordinates.py` | Grid coordinates (one-time) |
| u | `download_u.py` | Zonal velocity (m/s) |
| v | `download_v.py` | Meridional velocity (m/s) |
| w | `download_w.py` | Vertical velocity (m/s) |
| T | `download_temp.py` | Temperature (°C) |
| kz | `download_kz.py` | Vertical diffusivity coefficient (m²/s) |
| ice | `download_ice.py` | Sea ice concentration (0–1) |
| kh | `compute_kh.py` | Horizontal diffusivity (m²/s, computed from u, v, w) |

## File Outputs

All outputs are saved as monthly NetCDF4 files with naming convention:
```
glorys12_VARIABLE_YYYY_MM.nc
```

Example: `glorys12_u_1994_11.nc` contains zonal velocity for November 1994.

## Domain

- **Latitude**: 78°S to 40°S
- **Longitude**: 115°W to 40°E
- **Grid**: 1/12° resolution from Mercator Ocean (GLORYS12v1)

## Workflow & Dependencies

### Step 1: Download Static Files (one-time)

Run once at the beginning:

```bash
sbatch download_static.sh
```

This downloads bathymetry and coordinates. No time dependency; can run anytime.

### Step 2: Download Monthly Data

For each year, adapt the example template:

```bash
cp download_template.sh download_1994.sh
# Edit download_1994.sh and change YEAR=1994
sbatch download_1994.sh
```

**Resources** (from template):
- Job name: `DWL_1994`
- Time: 2 hours
- Array: 72 tasks (12 months × 6 variables)
- CPUs: 1 per task
- Memory: default

This job downloads u, v, w, kz, temp, ice for all 12 months in parallel.

### Step 3: Compute Horizontal Diffusivity

**Dependency**: u, v, w must be downloaded first.

Once downloads are complete, run:

```bash
cp compute_template.sh compute_1994.sh
# Edit compute_1994.sh and change YEAR=1994
sbatch compute_1994.sh
```

**Resources** (from template):
- Job name: `CMP_1994`
- Time: 2 hours
- Array: 12 tasks (one per month)
- CPUs: 1 per task
- Memory: 64 GB per task

This computes kh using the Smagorinsky formulation from downloaded u, v, w files.

## Data Access

All scripts fetch data from Mercator Ocean OpenDAP servers:
- Static: `http://tds.mercator-ocean.fr/thredds/dodsC/psy4v3r1/global-analysis-forecast-phy-001-024-pgn*`
- Daily: `http://tds.mercator-ocean.fr/thredds/dodsC/glorys12v1-daily-*`

Requires internet access or ECMWF HPC network access.

## Notes

- **Nov/Dec handling**: November and December are assigned to the *previous* spawning year (e.g., Nov/Dec 1993 → spawning year 1994). The scripts handle this automatically.
- **Smagorinsky coefficient**: `compute_kh.py` uses CS = 0.1 (hardcoded). Edit the script if you need a different value.
- **Temporary files**: Daily download scripts create temporary day files, then concatenate into monthly files, then delete temporaries. Final output is one file per month.

## References

- Mercator Ocean documentation: https://tds.mercator-ocean.fr/userguide/user_guide.html
- GLORYS12v1 variables: https://tds.mercator-ocean.fr/thredds/glorys12v1/catalog.html
