import numpy as np
import sys
import xarray as xr

# Go there to understand how to use the Mercator OpenDap:
# https://tds.mercator-ocean.fr/userguide/user_guide.html

# Go there to see available variables with Glorys12v1 dataset:
# https://tds.mercator-ocean.fr/thredds/glorys12v1/catalog.html

# Parameters.
NORTH = -40
WEST = -115
EAST = 40

# Open dataset.
ds = xr.open_dataset('http://tds.mercator-ocean.fr/thredds/dodsC/psy4v3r1/global-analysis-forecast-phy-001-024-pgnstatics/PSY4V3R1_mesh_zgr.nc')

# Slice dataset to select the desired latitude and longitude ranges.
geotest = (ds.nav_lon > WEST) & (ds.nav_lon < EAST) & (ds.nav_lat < NORTH)
geoindex = np.argwhere(geotest.values)
xmin = min(geoindex[:, 1])
xmax = max(geoindex[:, 1])
ymin = min(geoindex[:, 0])
ymax = max(geoindex[:, 0])
ds = ds.isel({'x':slice(xmin, xmax), 'y':slice(ymin, ymax)})

# Remove the last y-coordinate to have a consistent C-grid dataset.
ds = ds.isel(y = slice(0, -1))

# Save dataset.
ds.to_netcdf('glorys12_bathymetry.nc')