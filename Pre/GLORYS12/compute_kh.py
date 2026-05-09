import xarray as xr
import numpy as np
import sys

YEAR = int(sys.argv[1])
MONTH = int(sys.argv[2])

# Smagorinsky coefficient.
CS = 0.1

# Open the NetCDF files.
dsu = xr.open_dataset(f'glorys12_u_{YEAR}_{MONTH:02d}.nc')
dsv = xr.open_dataset(f'glorys12_v_{YEAR}_{MONTH:02d}.nc')
dsw = xr.open_dataset(f'glorys12_w_{YEAR}_{MONTH:02d}.nc')


###############################
# Resample u and v on w-grid. #
###############################

# Vertical interpolation from T-levels to W-levels.
dsu_vert = dsu.interp(deptht = dsw.depthw.values, method = 'linear', kwargs = {'fill_value': 'extrapolate'})
dsv_vert = dsv.interp(deptht = dsw.depthw.values, method = 'linear', kwargs = {'fill_value': 'extrapolate'})
dsu_vert = dsu_vert.rename({'deptht': 'depthw'})
dsv_vert = dsv_vert.rename({'deptht': 'depthw'})

# Horizontal interpolation.
# U-grid is shifted by 0.5 in x-direction relative to T/W-grid.
# V-grid is shifted by 0.5 in y-direction relative to T/W-grid.
# Simple averaging between neighboring U/V-points.
dsu_on_w_grid = 0.5 * (dsu_vert + dsu_vert.roll(x = 1, roll_coords = False))
dsv_on_w_grid = 0.5 * (dsv_vert + dsv_vert.roll(y = 1, roll_coords = False))

# Step 3: Assign the exact coordinates from W-grid.
dsu_on_w_grid = dsu_on_w_grid.assign_coords({
    'nav_lat': dsw.nav_lat,
    'nav_lon': dsw.nav_lon,
    'depthw': dsw.depthw
})
dsv_on_w_grid = dsv_on_w_grid.assign_coords({
    'nav_lat': dsw.nav_lat,
    'nav_lon': dsw.nav_lon,
    'depthw': dsw.depthw
})


##############################
# Compute cell surface area. #
##############################

# Earth radius in meters.
R_earth = 6371000.0

# Get 2D lat/lon arrays.
nav_lat = dsw.nav_lat.values  # shape: (y, x)
nav_lon = dsw.nav_lon.values  # shape: (y, x)

# Convert to radians.
lat_rad = np.deg2rad(nav_lat)
lon_rad = np.deg2rad(nav_lon)

# Compute local grid spacings using finite differences.
# dx: distance between points in x-direction (meters).
# dy: distance between points in y-direction (meters).

# Initialize dx and dy arrays.
dx = np.full_like(nav_lat, np.nan)
dy = np.full_like(nav_lat, np.nan)

# Interior points using centered differences.
dx[:, 1:-1] = R_earth * np.abs(np.deg2rad(nav_lon[:, 2:] - nav_lon[:, :-2]) / 2) * np.cos(lat_rad[:, 1:-1])
dy[1:-1, :] = R_earth * np.abs(np.deg2rad(nav_lat[2:, :] - nav_lat[:-2, :]) / 2)

# Boundary points using forward/backward differences.
dx[:, 0] = R_earth * np.abs(np.deg2rad(nav_lon[:, 1] - nav_lon[:, 0])) * np.cos(lat_rad[:, 0])
dy[0, :] = R_earth * np.abs(np.deg2rad(nav_lat[1, :] - nav_lat[0, :]))
dx[:, -1] = R_earth * np.abs(np.deg2rad(nav_lon[:, -1] - nav_lon[:, -2])) * np.cos(lat_rad[:, -1])
dy[-1, :] = R_earth * np.abs(np.deg2rad(nav_lat[-1, :] - nav_lat[-2, :]))

# Compute cell area using assuming cells are approximately rectangular.
cell_area = dx * dy  # shape: (y, x)


###############################################
# Compute the norm of the strain rate tensor. #
###############################################

# Extract velocity components (now all on W-grid).
u = dsu_on_w_grid['vozocrtx']  # eastward velocity
v = dsv_on_w_grid['vomecrty']  # northward velocity

# Get the data as numpy arrays (shape: time, depth, y, x).
u_data = u.values
v_data = v.values

# Initialize gradient arrays (shape: time, depth, y, x).
du_dx = np.full_like(u_data, np.nan)
dv_dy = np.full_like(v_data, np.nan)
du_dy = np.full_like(u_data, np.nan)
dv_dx = np.full_like(v_data, np.nan)

# Broadcast dx and dy to include time and depth dimensions.
dx_4d = dx[np.newaxis, np.newaxis, :, :]  # shape: (1, 1, y, x)
dy_4d = dy[np.newaxis, np.newaxis, :, :]  # shape: (1, 1, y, x)

# Compute centered differences for interior points.
du_dx[:, :, :, 1:-1] = (u_data[:, :, :, 2:] - u_data[:, :, :, :-2]) / (2 * dx_4d[:, :, :, 1:-1])
dv_dx[:, :, :, 1:-1] = (v_data[:, :, :, 2:] - v_data[:, :, :, :-2]) / (2 * dx_4d[:, :, :, 1:-1])
du_dy[:, :, 1:-1, :] = (u_data[:, :, 2:, :] - u_data[:, :, :-2, :]) / (2 * dy_4d[:, :, 1:-1, :])
dv_dy[:, :, 1:-1, :] = (v_data[:, :, 2:, :] - v_data[:, :, :-2, :]) / (2 * dy_4d[:, :, 1:-1, :])


###################################
# Compute horizontal diffusivity. #
###################################

# Broadcast cell_area to include time and depth dimensions.
cell_area_4d = cell_area[np.newaxis, np.newaxis, :, :]  # shape: (1, 1, y, x)

# Smagorinsky.
Kh = CS * cell_area_4d * np.sqrt(du_dx ** 2 + dv_dy ** 2 + 0.5 * (du_dy + dv_dx) ** 2)

# Replace NaN values by zero if they are not NaN values in w.
Kh[np.isnan(Kh)] = 0.0
Kh[np.isnan(dsw['vovecrtz'].values)] = np.nan


########################
# Save to NetCDF file. #
########################

# Add Kh to the dataset as a new variable.
dsw['Kh'] = (('time_counter', 'depthw', 'y', 'x'), Kh)

# Add attributes to Kh variable.
dsw['Kh'].attrs['long_name'] = 'Horizontal diffusivity (Smagorinsky)'
dsw['Kh'].attrs['units'] = 'm2/s'
dsw['Kh'].attrs['description'] = f'Computed using Smagorinsky formulation with CS = {CS}'
dsw['Kh'].attrs['coordinates'] = 'nav_lon nav_lat'

# Create a new dataset with only Kh and coordinates.
ds_out = dsw[['Kh']].copy()

# Construct output filename.
output_filename = f'glorys12_kh_{YEAR}_{MONTH:02d}.nc'

# Save to NetCDF.
ds_out.to_netcdf(output_filename, format = 'NETCDF4')

# Close datasets.
dsu.close()
dsv.close()
dsw.close()
ds_out.close()