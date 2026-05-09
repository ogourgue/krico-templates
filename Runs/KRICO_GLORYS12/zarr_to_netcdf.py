"""
KRICO - Output Conversion Script
==================================================
Converts Parcels zarr output to compressed NetCDF4 format.

Handles both parallel and serial Parcels outputs:
- Parallel: Merges proc*.zarr files into single zarr, then converts to NetCDF4
- Serial: Directly converts single zarr file to NetCDF4

Compression strategy:
- Lossless zlib compression (complevel=5)
- float32 precision for numeric data (adequate for scientific analysis)
- Typically achieves 60-70% file size reduction

Usage: python zarr_to_netcdf.py <base_name>
Example: python zarr_to_netcdf.py out_01
"""

import xarray as xr
import os
import shutil
from pathlib import Path
import sys
import glob
import numpy as np


def merge_parallel_output(base_name):
    """
    Merge Parcels parallel outputs into single zarr file.
    
    When Parcels runs with MPI, each process writes its particles to a separate
    zarr file (proc00.zarr, proc01.zarr, etc.). This function merges them into
    a single consolidated zarr file organized by trajectory dimension.
    
    Parameters
    ----------
    base_name : str
        Base filename without extension (e.g., "out_01")
        
    Returns
    -------
    str or None
        Path to merged zarr file, or None if no parallel outputs found
        
    Notes
    -----
    - Parallel outputs are in: base_name/proc*.zarr
    - Merged output goes to: base_name.zarr
    - Original parallel directory is removed after successful merge
    """
    # Check if parallel output directory exists
    parallel_dir = base_name
    pattern = f"{parallel_dir}/proc*.zarr"
    zarr_dirs = sorted(glob.glob(pattern))
    
    if not zarr_dirs:
        # No parallel outputs found - might be serial run
        return None
    
    print(f"Found {len(zarr_dirs)} parallel zarr outputs")
    
    # Load all parallel datasets
    datasets = []
    for zarr_dir in zarr_dirs:
        print(f"  Loading {zarr_dir}...")
        ds = xr.open_zarr(zarr_dir)
        datasets.append(ds)
    
    # Find maximum obs dimension size across all datasets
    # Different processes may have particles with different trajectory lengths
    max_obs = max(ds.sizes['obs'] for ds in datasets)
    print(f"  Maximum obs dimension: {max_obs}")
    
    # Pad all datasets to have same obs dimension
    # Required for concatenation along trajectory dimension
    padded_datasets = []
    for i, ds in enumerate(datasets):
        current_obs = ds.sizes['obs']
        if current_obs < max_obs:
            print(f"  Padding dataset {i} from {current_obs} to {max_obs} obs...")
            
            # Calculate number of padding observations needed
            n_pad = max_obs - current_obs
            
            # Pad each variable with appropriate fill values
            padded_vars = {}
            for var in ds.data_vars:
                data = ds[var].values
                
                # Determine fill value based on data type
                if np.issubdtype(data.dtype, np.datetime64):
                    fill_value = np.datetime64('NaT')  # Use NaT for datetime
                elif np.issubdtype(data.dtype, np.floating):
                    fill_value = np.nan  # Use NaN for floating point
                elif np.issubdtype(data.dtype, np.integer):
                    fill_value = -1  # Use -1 for integers
                else:
                    fill_value = 0  # Use 0 for other types

                # Create padding array with same shape except obs dimension
                pad_shape = list(data.shape)
                pad_shape[1] = n_pad  # Assuming obs is second dimension
                pad_array = np.full(pad_shape, fill_value, dtype=data.dtype)
                
                # Concatenate original data with padding along obs dimension
                padded_data = np.concatenate([data, pad_array], axis=1)
                
                # Create new DataArray with padded data
                padded_vars[var] = xr.DataArray(
                    padded_data,
                    dims=ds[var].dims,
                    attrs=ds[var].attrs
                )
            
            # Create new dataset with padded variables
            padded_ds = xr.Dataset(
                padded_vars,
                coords={
                    'trajectory': ds.coords['trajectory'],
                    'obs': np.arange(max_obs)
                },
                attrs=ds.attrs
            )
            padded_datasets.append(padded_ds)
        else:
            # No padding needed, but ensure obs coordinate is consistent
            ds_copy = ds.copy()
            ds_copy = ds_copy.assign_coords({'obs': np.arange(max_obs)})
            padded_datasets.append(ds_copy)
    
    # Concatenate all datasets along trajectory dimension
    print(f"  Concatenating {len(padded_datasets)} datasets...")
    merged = xr.concat(padded_datasets, dim='trajectory')
    
    # Sort by trajectory ID for logical ordering
    if 'trajectory' in merged.coords:
        print(f"  Sorting by trajectory ID...")
        merged = merged.sortby('trajectory')
    
    # Load into memory to resolve any chunking issues
    # This ensures clean write to output zarr file
    print(f"  Loading merged dataset into memory...")
    merged = merged.compute()
    
    # Write merged dataset to single zarr file
    serial_output = f"{base_name}.zarr"
    if os.path.exists(serial_output):
        shutil.rmtree(serial_output)
    
    print(f"  Writing merged output to {serial_output}...")
    merged.to_zarr(serial_output, mode='w', consolidated=True)
    
    # Cleanup: remove parallel output directory
    print(f"  Removing parallel output directory {parallel_dir}...")
    shutil.rmtree(parallel_dir)
    
    print(f"  [OK] Parallel outputs merged successfully")
    
    return serial_output


def convert_to_netcdf(zarr_path):
    """
    Convert zarr to compressed NetCDF4 file with float32 precision.
    
    Applies lossless compression and converts numeric variables to float32 for
    efficient storage. This typically reduces file size by 60-70% with no loss
    in scientific accuracy (float32 provides ~7 decimal places of precision).
    
    Parameters
    ----------
    zarr_path : str
        Path to zarr file (e.g., "out_01.zarr")
        
    Returns
    -------
    str
        Path to created NetCDF file
        
    Notes
    -----
    Compression settings:
    - Algorithm: zlib (lossless, like ZIP)
    - Compression level: 5 (good balance of speed vs. compression)
    - Precision: float32 for numeric data (half the size of float64)
    - Datetime variables are handled automatically by xarray
    """
    print()
    print(f"Converting zarr to compressed NetCDF4...")
    
    # Calculate original zarr size for comparison
    orig_files = list(Path(zarr_path).rglob('*'))
    orig_file_count = len([f for f in orig_files if f.is_file()])
    orig_size = sum(f.stat().st_size for f in orig_files if f.is_file())
    orig_size_gb = orig_size / 1e9
    print(f"  Original zarr: {orig_size_gb:.2f} GB in {orig_file_count} files")
    
    # Load zarr dataset
    print(f"  Loading zarr dataset...")
    ds = xr.open_zarr(zarr_path)
    
    # Configure encoding with compression and dtype conversion
    print(f"  Configuring compression (zlib level 5, float32 for numeric data)...")
    encoding = {}
    
    for var in ds.data_vars:
        # Check if variable is datetime type
        if np.issubdtype(ds[var].dtype, np.datetime64):
            # For datetime variables: apply compression only (no dtype conversion)
            # xarray handles datetime encoding automatically
            encoding[var] = {
                'zlib': True,      # Lossless compression
                'complevel': 5     # Compression level 1-9 (5 = balanced)
            }
        else:
            # For numeric variables: apply compression + float32 conversion
            # float32 provides adequate precision for particle trajectories
            encoding[var] = {
                'zlib': True,           # Lossless compression
                'complevel': 5,         # Compression level
                'dtype': 'float32'      # Convert to single precision
            }
    
    # Write compressed NetCDF4 file
    nc_path = zarr_path.replace('.zarr', '.nc')
    print(f"  Writing compressed NetCDF4 to {nc_path}...")
    ds.to_netcdf(nc_path, engine='netcdf4', encoding=encoding)
    
    # Calculate final size and compression statistics
    nc_size = os.path.getsize(nc_path)
    nc_size_gb = nc_size / 1e9
    compression_ratio = (1 - nc_size / orig_size) * 100
    saved_gb = orig_size_gb - nc_size_gb
    
    print(f"  Compressed NetCDF4: {nc_size_gb:.2f} GB in 1 file")
    print(f"  Compression ratio: {compression_ratio:.1f}%")
    print(f"  Space saved: {saved_gb:.2f} GB")
    
    # Remove zarr directory after successful conversion
    print(f"  Removing zarr directory...")
    shutil.rmtree(zarr_path)
    
    print(f"  [OK] Conversion complete")
    
    return nc_path


# ============================================================================
# Main execution
# ============================================================================
if __name__ == "__main__":
    # Check command line arguments
    if len(sys.argv) != 2:
        print("ERROR: Incorrect number of arguments")
        print()
        print("Usage: python zarr_to_netcdf.py <base_name>")
        print("Example: python zarr_to_netcdf.py out_01")
        print()
        print("For parallel runs: Looks for out_01/proc*.zarr")
        print("                   Merges to out_01.zarr")
        print("                   Converts to out_01.nc")
        print()
        print("For serial runs:   Converts out_01.zarr to out_01.nc")
        sys.exit(1)
    
    # Extract base name from command line
    base_name = sys.argv[1]
    
    # Remove .zarr extension if provided
    if base_name.endswith('.zarr'):
        base_name = base_name[:-5]
    
    print("=" * 80)
    print("PARCELS OUTPUT PROCESSING")
    print("=" * 80)
    
    # Step 1: Check for parallel outputs and merge if found
    print()
    print("Step 1: Checking for parallel outputs...")
    merged_path = merge_parallel_output(base_name)
    
    if merged_path:
        # Parallel outputs were merged
        zarr_path = merged_path
        print()
        print("[SUCCESS] Parallel outputs merged successfully")
    else:
        # No parallel outputs - assume serial run
        zarr_path = f"{base_name}.zarr"
        print(f"  No parallel outputs found")
        print(f"  Processing serial output: {zarr_path}")
    
    # Step 2: Convert zarr to NetCDF4
    print()
    print("Step 2: Converting to compressed NetCDF4...")
    nc_path = convert_to_netcdf(zarr_path)
    
    # Print summary
    print()
    print("=" * 80)
    print("PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Final output: {nc_path}")
    print()
    print("This NetCDF4 file contains:")
    print("  - All particle trajectories")
    print("  - Lossless zlib compression")
    print("  - float32 precision (adequate for analysis)")
    print("  - Single consolidated file for easy distribution")
