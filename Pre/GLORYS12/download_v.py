import calendar
import numpy as np
import os
import sys
import xarray as xr

# Go there to understand how to use the Mercator OpenDap:
# https://tds.mercator-ocean.fr/userguide/user_guide.html

# Go there to see available variables with Glorys12v1 dataset:
# https://tds.mercator-ocean.fr/thredds/glorys12v1/catalog.html

# The script:
# - download individual temporary daily files,
# - concatenate daily files into a monthly file,
# - delete temporary daily files.

# Parameters.
YEAR = int(sys.argv[1])  # e.g., 2019
MONTH = int(sys.argv[2])  # e.g., 1
NORTH = -40
WEST = -115
EAST = 40

# Open dataset.
url = 'http://tds.mercator-ocean.fr/thredds/dodsC/glorys12v1-daily-gridV'
ds = xr.open_dataset(url)

# Only keep relevant variable.
ds = ds[['vomecrty']]

# Loop over days.
for i in range(calendar.monthrange(YEAR, MONTH)[1]):

    # Slice dataset to select the desired single day.
    date_str = f'{YEAR}-{MONTH:02d}-{i+1:02d}'
    dsi = ds.sel(time_counter = date_str)

    # Slice dataset to select the desired latitude and longitude ranges.
    geotest = (dsi.nav_lon > WEST) & (dsi.nav_lon < EAST) & (dsi.nav_lat < NORTH)
    geoindex = np.argwhere(geotest.values)
    xmin = min(geoindex[:, 1])
    xmax = max(geoindex[:, 1])
    ymin = min(geoindex[:, 0])
    ymax = max(geoindex[:, 0])
    dsi = dsi.isel({'x':slice(xmin, xmax), 'y':slice(ymin, ymax)})

    # Save dataset.
    dsi.to_netcdf(f'glorys12_v_{YEAR}_{MONTH:02d}_{i+1:02d}.nc', format='NETCDF4')

# Concatenate daily files.
ds = xr.open_mfdataset(f'glorys12_v_{YEAR}_{MONTH:02d}_*.nc')
ds.to_netcdf(f'glorys12_v_{YEAR}_{MONTH:02d}.nc', format = 'NETCDF4')

# Delete daily files.
for i in range(calendar.monthrange(YEAR, MONTH)[1]):
    os.remove(f'glorys12_v_{YEAR}_{MONTH:02d}_{i+1:02d}.nc')
