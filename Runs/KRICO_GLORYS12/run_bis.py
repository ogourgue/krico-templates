"""
KRICO - Parcels Simulation Script
===================================
Antarctic krill larval connectivity Lagrangian particle tracking simulation.

This script releases particles from bathymetrically-defined spawning habitats
(1000-2000m depth) within CCAMLR Statistical Areas and tracks them for 200 days
using GLORYS12 ocean circulation forcing.

Usage: python run.py YEAR MONTH DAY
Example: python run.py 2015 11 15
"""

from datetime import timedelta, datetime
import geopandas as gpd
import numpy as np
import os
import parcels
from shapely.geometry import Point
import xarray as xr
import sys

# ============================================================================
# MPI configuration for parallel execution
# ============================================================================
# Only rank 0 prints to avoid cluttered output in SLURM logs
try:
    from mpi4py import MPI
    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
except ImportError:
    # Not running with MPI
    rank = 0

def print_rank0(message="", end="\n"):
    """Print only from MPI rank 0 to avoid duplicate messages"""
    if rank == 0:
        print(message, end=end)


# ============================================================================
# KEY SIMULATION PARAMETERS
# ============================================================================
# These parameters control model sensitivity and computational cost
# Modify these for sensitivity analysis

# Particle density: number of particles released per km^2 of spawning habitat
# Higher values increase statistical robustness but also computational cost
PARTICLE_DENSITY = 1.0  # particles per km^2

# Timestep for numerical integration
# Smaller timesteps improve accuracy but increase computational cost
# 30 minutes provides numerical stability at GLORYS12 1/12 degree resolution
TIMESTEP = timedelta(minutes=30)

# ============================================================================
# Parse command line arguments
# ============================================================================
if len(sys.argv) != 4:
    print_rank0("ERROR: Incorrect number of arguments")
    print_rank0("Usage: python run.py YEAR MONTH DAY")
    print_rank0("Example: python run.py 2015 11 15")
    sys.exit(1)

# Extract release date from command line
release_year = int(sys.argv[1])
release_month = int(sys.argv[2])
release_day = int(sys.argv[3])

print_rank0("=" * 80)
print_rank0("KRICO SIMULATION")
print_rank0("=" * 80)
print_rank0(f"Release date: {release_year}-{release_month:02d}-{release_day:02d}")
print_rank0(f"Particle density: {PARTICLE_DENSITY} particles/km^2")
print_rank0(f"Timestep: {TIMESTEP}")
print_rank0("=" * 80)
print_rank0()

# Set random seed for reproducibility (unique per release day)
parcels.ParcelsRandom.seed(release_year * 10000 + release_month * 100 + release_day + 100000000)


# ============================================================================
# Configure GLORYS12 field set
# ============================================================================
print_rank0("Configuring GLORYS12 field set...")

# Path to pre-processed Mercator-Ocean GLORYS12 dataset
path_glorys12 = '../../Pre/GLORYS12'

# Calculate simulation period to determine which files to load
# This prevents conflicts when downloading files for other years
print_rank0("  Calculating required file period...")

# Release date
release_date = datetime(release_year, release_month, release_day)

# End date: release + 200 days tracking + 1 month buffer for field interpolation
# Buffer ensures fields are available at end of simulation
end_date = release_date + timedelta(days=200 + 31)

print_rank0(f"  Release date: {release_date.strftime('%Y-%m-%d')}")
print_rank0(f"  End date (with buffer): {end_date.strftime('%Y-%m-%d')}")

# Generate list of (year, month) tuples for all months in the simulation period
months_needed = []
current_date = datetime(release_year, release_month, 1)  # Start at beginning of release month

while current_date <= end_date:
    months_needed.append((current_date.year, current_date.month))
    
    # Advance to next month
    if current_date.month == 12:
        current_date = datetime(current_date.year + 1, 1, 1)
    else:
        current_date = datetime(current_date.year, current_date.month + 1, 1)

print_rank0(f"  Months needed: {len(months_needed)} months from {months_needed[0][0]}-{months_needed[0][1]:02d} to {months_needed[-1][0]}-{months_needed[-1][1]:02d}")

# Build file lists for only the required months
# This prevents loading files being downloaded by other jobs
ufiles = []
vfiles = []
wfiles = []
khfiles = []
kzfiles = []
tempfiles = []
icefiles = []

for year, month in months_needed:
    # Format: glorys12_variable_YYYY_MM.nc
    # Construct filenames directly (no glob needed for exact paths)
    ufiles.append(f'{path_glorys12}/glorys12_u_{year}_{month:02d}.nc')
    vfiles.append(f'{path_glorys12}/glorys12_v_{year}_{month:02d}.nc')
    wfiles.append(f'{path_glorys12}/glorys12_w_{year}_{month:02d}.nc')
    khfiles.append(f'{path_glorys12}/glorys12_kh_{year}_{month:02d}.nc')
    kzfiles.append(f'{path_glorys12}/glorys12_kz_{year}_{month:02d}.nc')
    tempfiles.append(f'{path_glorys12}/glorys12_temp_{year}_{month:02d}.nc')
    icefiles.append(f'{path_glorys12}/glorys12_ice_{year}_{month:02d}.nc')

# Verify all required files exist
print_rank0(f"  Files required: {len(ufiles)} months × 7 variables = {len(ufiles) * 7} files")

# Check for missing files
missing_files = []
for filepath in ufiles + vfiles + wfiles + khfiles + kzfiles + tempfiles + icefiles:
    if not os.path.exists(filepath):
        missing_files.append(os.path.basename(filepath))

if missing_files:
    print_rank0("  [ERROR] Missing required forcing files!")
    print_rank0(f"  {len(missing_files)} file(s) not found:")
    for filename in missing_files[:10]:  # Show first 10 missing files
        print_rank0(f"    - {filename}")
    if len(missing_files) > 10:
        print_rank0(f"    ... and {len(missing_files) - 10} more")
    print_rank0()
    print_rank0("  Required period:")
    print_rank0(f"    From: {months_needed[0][0]}-{months_needed[0][1]:02d}")
    print_rank0(f"    To:   {months_needed[-1][0]}-{months_needed[-1][1]:02d}")
    sys.exit(1)

print_rank0(f"  [OK] All required files found")

# Static files (bathymetry and grid coordinates)
bathyfile = f'{path_glorys12}/glorys12_bathymetry.nc'
mask = f'{path_glorys12}/glorys12_coordinates.nc'

# Create filenames dictionary for Parcels FieldSet
# Each variable specifies its coordinate files and data files
filenames = {
    'U': {'lon': mask, 'lat': mask, 'depth': wfiles[0], 'data': ufiles},
    'V': {'lon': mask, 'lat': mask, 'depth': wfiles[0], 'data': vfiles},
    'W': {'lon': mask, 'lat': mask, 'depth': wfiles[0], 'data': wfiles},
    'Kh': {'lon': mask, 'lat': mask, 'depth': wfiles[0], 'data': khfiles},
    'Kz': {'lon': mask, 'lat': mask, 'depth': wfiles[0], 'data': kzfiles},
    'T': {'lon': mask, 'lat': mask, 'depth': wfiles[0], 'data': tempfiles},
    'SIF': {'lon': mask, 'lat': mask, 'data': icefiles},  # 2D field (no depth)
    'H': {'lon': mask, 'lat': mask, 'data': bathyfile}     # 2D field (no depth)
}

# Map Parcels field names to NetCDF variable names
variables = {
    'U': 'vozocrtx',      # NEMO zonal velocity
    'V': 'vomecrty',      # NEMO meridional velocity
    'W': 'vovecrtz',      # NEMO vertical velocity
    'Kh': 'Kh',           # Horizontal diffusivity (pre-computed)
    'Kz': 'votkeavt',     # NEMO vertical mixing coefficient
    'T': 'votemper',      # NEMO temperature
    'SIF': 'ileadfra',    # Sea ice lead fraction
    'H': 'hdept'          # NEMO bathymetry
}

# Define dimension mappings for NEMO C-grid
# 3D fields with time dimension
c_grid_dimensions = {
    'lon': 'glamf',
    'lat': 'gphif',
    'depth': 'depthw',
    'time': 'time_counter'
}

# 2D fields with time dimension (surface variables)
c_grid_dimensions_2d_t = {
    'lon': 'glamf',
    'lat': 'gphif',
    'time': 'time_counter'
}

# 2D fields without time dimension (static fields like bathymetry)
c_grid_dimensions_2d = {
    'lon': 'glamf',
    'lat': 'gphif'
}

# Assign dimension mappings to each variable
dimensions = {
    'U': c_grid_dimensions,
    'V': c_grid_dimensions,
    'W': c_grid_dimensions,
    'Kh': c_grid_dimensions,
    'Kz': c_grid_dimensions,
    'T': c_grid_dimensions,
    'SIF': c_grid_dimensions_2d_t,
    'H': c_grid_dimensions_2d
}

# Create Parcels FieldSet from NEMO output
print_rank0("  Loading NEMO fields with automatic chunking...")
fieldset = parcels.FieldSet.from_nemo(filenames, variables, dimensions, chunksize='auto')
print_rank0("  [OK] Field set configured")
print_rank0()


# ============================================================================
# Load CCAMLR Statistical Areas
# ============================================================================
print_rank0("Loading CCAMLR Statistical Areas...")

# Path to CCAMLR shapefile dataset
path_ccamlr = '../../Pre/ccamlr-data/geographical_data/asd'

# Load shapefile and filter to areas of interest
# These are the primary krill fishing grounds and spawning regions
ccamlr = gpd.read_file(f'{path_ccamlr}/CCAMLR_ASD_EPSG4326.shp')
areas = ['48.1', '48.2', '48.3', '48.4', '48.5', '48.6', '88.3']
ccamlr = ccamlr[ccamlr['GAR_Long_L'].isin(areas)]

# Combine all areas into a single geometry for efficient spatial queries
# This allows checking if a point is within ANY CCAMLR area in a single operation
ccamlr_combined = ccamlr.union_all()

print_rank0(f"  Loaded {len(areas)} CCAMLR areas: {', '.join(areas)}")
print_rank0("  [OK] CCAMLR regions configured")
print_rank0()


# ============================================================================
# Define particle release strategy
# ============================================================================
print_rank0("Configuring particle release strategy...")

# Single release time for this day at noon UTC
release_time = datetime(release_year, release_month, release_day, 12)
print_rank0(f"  Release time: {release_time}")

# Load bathymetry dataset to identify spawning habitats
print_rank0("  Loading bathymetry data...")
bathy_ds = xr.open_dataset(f'{path_glorys12}/glorys12_bathymetry.nc')

# Extract bathymetry grid and coordinates
hdept = bathy_ds['hdept'].isel(t=0).values  # Bathymetry (remove time dimension)
nav_lon = bathy_ds['nav_lon'].values        # Longitude grid
nav_lat = bathy_ds['nav_lat'].values        # Latitude grid

# Initialize lists for particle release positions
lon = []
lat = []

# Use the global particle density parameter (defined at top of script)
# This ensures spatially uniform sampling across spawning habitat
print_rank0(f"  Particle density: {PARTICLE_DENSITY} particles/km^2")
print_rank0()


# ============================================================================
# Identify valid release locations
# ============================================================================
print_rank0("Identifying valid release locations...")
print_rank0("  Scanning grid for bathymetry 1000-2000m within CCAMLR areas...")

# Store valid location information before generating particles
# This separates spatial identification from particle generation
valid_locations = []

# Loop over every grid point in the bathymetry dataset
for j in range(hdept.shape[0]):  # Latitude dimension
    for i in range(hdept.shape[1]):  # Longitude dimension

        # Get coordinates for this grid cell
        grid_lon = nav_lon[j, i]
        grid_lat = nav_lat[j, i]

        # Check if bathymetry is in spawning habitat range (1000-2000m)
        # This represents shelf-slope interfaces identified in literature
        if 1000 <= hdept[j, i] <= 2000:

            # Create point geometry for spatial query
            point = Point(grid_lon, grid_lat)

            # Check if point falls within any CCAMLR area of interest
            if ccamlr_combined.contains(point):

                # Estimate grid cell size from neighboring points
                # This accounts for variable cell size at different latitudes
                if i < hdept.shape[1] - 1:
                    dlon = abs(nav_lon[j, i + 1] - grid_lon)
                elif i > 0:
                    dlon = abs(grid_lon - nav_lon[j, i - 1])
                else:
                    dlon = 1.0 / 12.0  # Fallback to nominal GLORYS12 resolution
                
                if j < hdept.shape[0] - 1:
                    dlat = abs(nav_lat[j + 1, i] - grid_lat)
                elif j > 0:
                    dlat = abs(grid_lat - nav_lat[j - 1, i])
                else:
                    dlat = 1.0 / 12.0  # Fallback to nominal GLORYS12 resolution

                # Calculate cell area in km²
                # Convert degrees to kilometers, accounting for latitude compression
                lat_rad = np.radians(grid_lat)
                dist_lon_km = dlon * 111.32 * np.cos(lat_rad)  # Longitude distance in km
                dist_lat_km = dlat * 111.32                     # Latitude distance in km
                cell_area_km2 = dist_lon_km * dist_lat_km

                # Calculate number of particles for this cell based on density
                # Ensures spatially uniform sampling proportional to cell area
                n_points_per_cell = int(np.round(PARTICLE_DENSITY * cell_area_km2))

                # Ensure at least 1 particle per valid cell
                n_points_per_cell = max(1, n_points_per_cell)

                # Store location information for particle generation
                valid_locations.append({
                    'grid_lon': grid_lon,
                    'grid_lat': grid_lat,
                    'dlon': dlon,
                    'dlat': dlat,
                    'n_particles': n_points_per_cell
                })

print_rank0(f"  [OK] Found {len(valid_locations)} valid spatial locations")
print_rank0()


# ============================================================================
# Generate particle positions
# ============================================================================
print_rank0("Generating particle positions...")

# Generate particles for all identified valid locations
for loc in valid_locations:
    # Release multiple particles per grid cell based on calculated density
    for _ in range(loc['n_particles']):
        # Add random offset within grid cell to avoid all particles
        # starting at cell centers (improves sampling of sub-grid variability)
        offset_lon = np.random.uniform(-0.5 * loc['dlon'], 0.5 * loc['dlon'])
        offset_lat = np.random.uniform(-0.5 * loc['dlat'], 0.5 * loc['dlat'])
        
        # Add particle position to release arrays
        lon.append(loc['grid_lon'] + offset_lon)
        lat.append(loc['grid_lat'] + offset_lat)

# Generate uniform random depths for all particles (50-200m)
# This represents the upper water column where early larval stages develop
# Uniform distribution samples vertical shear in horizontal currents
depth = np.random.uniform(50, 200, size=len(lon)).tolist()

print_rank0(f"  [OK] Generated {len(lon)} particles for release")

# Filter out particles too close to domain boundaries
# This prevents FieldOutOfBoundError at initialization
# Use same boundaries as DeleteParticle kernel
lon_filtered = []
lat_filtered = []
depth_filtered = []

for i in range(len(lon)):
    if -76 <= lat[i] <= -41 and -114 <= lon[i] <= 39:
        lon_filtered.append(lon[i])
        lat_filtered.append(lat[i])
        depth_filtered.append(depth[i])

n_filtered = len(lon) - len(lon_filtered)
if n_filtered > 0:
    print_rank0(f"  Filtered {n_filtered} particles too close to boundaries")

lon = lon_filtered
lat = lat_filtered
depth = depth_filtered

print_rank0(f"  [OK] Final particle count: {len(lon)}")
print_rank0()


# ============================================================================
# Create particle set
# ============================================================================
print_rank0("Creating particle set...")

# Define custom particle class that samples additional fields
# This allows tracking temperature and sea ice conditions along trajectories
SampleParticle = parcels.JITParticle.add_variables([
    'temperature', 'sea_ice_area_fraction', 'bathymetry'
])

# Create particle set with single release time
# All particles are released simultaneously at the specified date/time
pset = parcels.ParticleSet(
    fieldset=fieldset,
    pclass=SampleParticle,
    lon=lon,
    lat=lat,
    depth=depth,
    time=release_time
)

print_rank0(f"  [OK] Particle set created with {pset.size} particles")
print_rank0()


# ============================================================================
# Define kernels (particle behavior)
# ============================================================================

def Sample(particle, fieldset, time):
    """
    Sample environmental variables at particle position.
    
    Records temperature, sea ice fraction, and bathymetry along trajectories.
    These variables are used for post-processing analysis of larval habitat.
    """
    particle.temperature = fieldset.T[time, particle.depth, particle.lat, particle.lon]
    particle.sea_ice_area_fraction = fieldset.SIF[time, particle.depth, particle.lat, particle.lon]
    particle.bathymetry = fieldset.H[time, particle.depth, particle.lat, particle.lon]


def HDiffusionM1(particle, fieldset, time):
    """
    Horizontal diffusion using Milstein first-order scheme (M1).
    
    Implements stochastic displacement representing sub-gridscale mixing.
    Includes both random displacement (Wiener process) and gradient-dependent
    drift from spatially variable diffusivity.
    
    Uses Smagorinsky-computed Kh from GLORYS12 pre-processing.
    """
    # Resolution for central difference gradient approximation
    # Should be of the order of the local grid size
    dres = 0.0833

    # Generate Wiener increments (random walk component)
    # These have zero mean and standard deviation = sqrt(dt)
    dWx = parcels.rng.normalvariate(0, math.sqrt(math.fabs(particle.dt)))
    dWy = parcels.rng.normalvariate(0, math.sqrt(math.fabs(particle.dt)))

    # Convert diffusivity from m²/s to deg²/s
    # Required because particle positions are in degrees
    R_earth = 6371000.0  # Earth radius in meters
    deg_to_m_lat = math.pi * R_earth / 180.0
    lat_rad = particle.lat * math.pi / 180.0
    deg_to_m_lon = deg_to_m_lat * math.cos(lat_rad)  # Longitude spacing varies with latitude

    # Compute diffusivity gradients using central differences
    # These represent spatial variation in mixing intensity
    Kxp1 = fieldset.Kh[time, particle.depth, particle.lat, particle.lon + dres] / (deg_to_m_lon ** 2)
    Kxm1 = fieldset.Kh[time, particle.depth, particle.lat, particle.lon - dres] / (deg_to_m_lon ** 2)
    Kyp1 = fieldset.Kh[time, particle.depth, particle.lat + dres, particle.lon] / (deg_to_m_lat ** 2)
    Kym1 = fieldset.Kh[time, particle.depth, particle.lat - dres, particle.lon] / (deg_to_m_lat ** 2)
    dKdx = (Kxp1 - Kxm1) / (2 * dres)
    dKdy = (Kyp1 - Kym1) / (2 * dres)

    # Convert Kh from m²/s to deg²/s at particle location
    Kh_m2s = fieldset.Kh[time, particle.depth, particle.lat, particle.lon]
    Kh_deg2s_x = Kh_m2s / (deg_to_m_lon ** 2)
    Kh_deg2s_y = Kh_m2s / (deg_to_m_lat ** 2)

    # Amplitude of stochastic displacement: sqrt(2*Kh)
    bx = math.sqrt(2 * Kh_deg2s_x)
    by = math.sqrt(2 * Kh_deg2s_y)

    # Milstein scheme: includes both Wiener process and gradient correction
    # Particle positions updated after all terms evaluated (prevents order-dependence)
    particle_dlon += 0.5 * dKdx * (dWx ** 2 + particle.dt) + bx * dWx
    particle_dlat += 0.5 * dKdy * (dWy ** 2 + particle.dt) + by * dWy


def VDiffusionM1(particle, fieldset, time):
    """
    Vertical diffusion using Milstein first-order scheme (M1).
    
    Implements vertical mixing using NEMO's vertical mixing coefficients (Kz).
    Includes gradient correction for spatially variable vertical diffusivity.
    
    Ensures particles remain below surface and above bottom.
    """
    # Vertical limit: minimum depth below surface (meters)
    # Prevents particles from rising above the surface
    vertical_limit = 1.0
    
    # Resolution for central difference gradient approximation (meters)
    dz = 1

    # Calculate depths for gradient computation
    depth_above = particle.depth - dz
    depth_below = particle.depth + dz

    # Ensure particle stays below surface (minimum depth = vertical_limit)
    if depth_above < vertical_limit:
        depth_above = vertical_limit

    # Ensure particle stays above bottom (check if Kz = 0 indicates seafloor)
    if fieldset.Kz[time, depth_below, particle.lat, particle.lon] == 0.0:
        depth_below = particle.depth

    # Get vertical mixing coefficients above and below particle
    Kz_above = fieldset.Kz[time, depth_above, particle.lat, particle.lon]
    Kz_below = fieldset.Kz[time, depth_below, particle.lat, particle.lon]

    # Compute vertical gradient of Kz using central differences
    if depth_below - depth_above > 0.0:
        dKdz = (Kz_below - Kz_above) / (depth_below - depth_above)
    else:
        dKdz = 0.0

    # Limit gradient magnitude to prevent numerical instabilities
    if dKdz < -1e-5:
        dKdz = -1e-5
    elif dKdz > 1e-5:
        dKdz = 1e-5

    # Generate Wiener increment (random walk component)
    dW = parcels.rng.normalvariate(0, math.sqrt(math.fabs(particle.dt)))

    # Amplitude of stochastic displacement: sqrt(2*Kz)
    b = math.sqrt(2 * fieldset.Kz[time, particle.depth, particle.lat, particle.lon])

    # Milstein scheme for vertical diffusion
    # Particle depth updated after all terms evaluated
    particle_ddepth += 0.5 * dKdz * (dW ** 2 + particle.dt) + b * dW


def DeleteParticle(particle, fieldset, time):
    """
    Delete particles that leave the model domain.
    
    Prevents error accumulation from particles advected beyond field boundaries.
    These represent larvae exported from the Southern Ocean circulation.
    
    Includes proactive deletion for particles approaching domain boundaries
    to avoid FieldOutOfBoundError during field sampling.
    
    Domain boundaries (with buffer):
    - Latitude: -76 to -41 (full domain: -78 to -40)
    - Longitude: -114 to 39 (full domain: -115 to 40)
    """
    # Delete particles that have already triggered out-of-bounds error
    if particle.state == parcels.StatusCode.ErrorOutOfBounds:
        particle.delete()
    
    # Proactively delete particles approaching domain boundaries
    # Buffer prevents FieldOutOfBoundError during field sampling
    if particle.lat < -76 or particle.lat > -41 or particle.lon < -114 or particle.lon > 39:
        particle.state = parcels.StatusCode.ErrorOutOfBounds
        particle.delete()


def KeepInOcean(particle, fieldset, time):
    """
    Ensure particles remain in valid ocean regions.
    
    Prevents particles from:
    - Rising above the surface (depth < vertical_limit)
    - Sinking below the seafloor (velocity = 0)
    - Getting stuck on land (velocity = 0)
    
    Particles stuck on bottom are moved vertically upward.
    Particles stuck on land receive random horizontal displacement.
    """
    # Vertical limit: minimum depth below surface (meters)
    # Prevents particles from rising above the surface
    # vertical_limit = 1.0  # Defined in VDiffusionM1 (Parcels stacks all kernels)
    
    # Keep particle below surface (minimum depth = vertical_limit)
    if particle.depth + particle_ddepth < vertical_limit:
        particle_ddepth = vertical_limit - particle.depth

    # Calculate new particle position after all kernel updates
    depth_new = particle.depth + particle_ddepth
    lat_new = particle.lat + particle_dlat
    lon_new = particle.lon + particle_dlon

    # Check velocity at new position to detect stuck particles
    u_new, v_new = fieldset.UV[time, depth_new, lat_new, lon_new]

    # Check surface velocity to distinguish bottom vs. land
    us_new, vs_new = fieldset.UV[time, vertical_limit, lat_new, lon_new]

    # Particle stuck (velocity = 0)
    if u_new == 0.0 and v_new == 0.0:

        # Case 1: Particle stuck on bottom (surface has velocity)
        # Solution: Move particle upward incrementally until back in water column
        if math.fabs(us_new) > 0.0 or math.fabs(vs_new) > 0.0:

            # Initialize depth correction
            ddepth = 0

            # Move up incrementally by 1m until velocity is non-zero
            while u_new == 0.0 and v_new == 0.0:

                # Update depth correction (negative = moving up)
                ddepth -= 1
                if depth_new + ddepth < vertical_limit:
                    ddepth = vertical_limit - depth_new

                # Check velocity at adjusted depth
                u_new, v_new = fieldset.UV[time, depth_new + ddepth, lat_new, lon_new]

            # Apply depth correction to particle
            particle_ddepth += ddepth

        # Case 2: Particle stuck on land (no surface velocity)
        # Solution: Apply random horizontal displacement to move back into ocean
        else:

            # Initial search radius (degrees)
            r = 1.0 / 1024.0

            # Number of random attempts per radius before increasing radius
            n = 100
            counter = n

            # Repeatedly try random displacements until particle is back in ocean
            while u_new == 0.0 and v_new == 0.0:

                # Decrement counter
                counter -= 1

                # If all attempts at this radius failed, double the radius
                if counter == 0:
                    counter = n
                    r *= 2.0

                # Generate random displacement at current radius
                angle = parcels.ParcelsRandom.uniform(0.0, 2.0 * math.pi)
                dlon = r * math.cos(angle)
                dlat = r * math.sin(angle)

                # Check velocity at displaced position
                u_new, v_new = fieldset.UV[time, depth_new, lat_new + dlat, lon_new + dlon]

            # Apply horizontal displacement to particle
            particle_dlon += dlon
            particle_dlat += dlat


# ============================================================================
# Combine kernels
# ============================================================================
print_rank0("Configuring kernels...")

# Create kernel sequence
# Order matters: advection -> diffusion -> boundaries -> sampling
kernels = pset.Kernel([
    parcels.AdvectionRK4_3D,  # 4th-order Runge-Kutta advection
    HDiffusionM1,              # Horizontal diffusion (Milstein scheme)
    VDiffusionM1,              # Vertical diffusion (Milstein scheme)
    DeleteParticle,            # Remove particles leaving domain
    KeepInOcean,               # Boundary conditions (surface, bottom, land)
    Sample                     # Sample environmental variables
])

print_rank0("  [OK] Kernels configured")
print_rank0()


# ============================================================================
# Execute simulation
# ============================================================================
print_rank0("Executing simulation...")

# Configure output file
# Filename: YYYY_MM_DD format
output_filename = f'{release_year}_{release_month:02d}_{release_day:02d}'
output_file = pset.ParticleFile(output_filename, outputdt=timedelta(days=1))

# Simulation duration: track larvae for 200 days post-release
# This captures full connectivity timescale (120-160 days to major recruitment areas)
runtime_days = 200

print_rank0(f"  Runtime: {runtime_days} days")
print_rank0(f"  Output frequency: daily")
print_rank0(f"  Output file: {output_filename}.zarr")
print_rank0(f"  Timestep: {TIMESTEP}")
print_rank0()
print_rank0("  Starting execution (this will take several hours)...")
print_rank0()

# Execute simulation
# Timestep from global variable TIMESTEP defined at top of script
pset.execute(
    kernels,
    runtime=timedelta(days=runtime_days),
    dt=TIMESTEP,
    output_file=output_file
)

# ============================================================================
# Simulation complete
# ============================================================================
print_rank0()
print_rank0("=" * 80)
print_rank0(f"[SUCCESS] Simulation complete for release day {release_day:02d}")
print_rank0("=" * 80)
print_rank0()
print_rank0("Output saved to zarr format - will be converted to NetCDF4 by job script")
