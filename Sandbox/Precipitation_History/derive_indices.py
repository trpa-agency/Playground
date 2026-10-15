"""
Apply the derived storm-character indices to an already-computed extremes
NetCDF, so the expensive per-year pass does not have to be repeated.

Run:  python derive_indices.py --dataset aorc
"""

import argparse
import os

import xarray as xr

import config as C
import tahoe_precip as T

ap = argparse.ArgumentParser()
ap.add_argument("--dataset", default="aorc")
prefix = ap.parse_args().dataset

path = os.path.join(C.OUT, f"{prefix}_tahoe_extremes.nc")
with xr.open_dataset(path) as ds:
    out = T.add_derived_indices(ds.load())

# Write beside the original and swap it in. netCDF4 keeps a Windows file
# lock, so rewriting the path in place fails if any other process has the
# dataset open.
tmp = path + ".tmp"
out.to_netcdf(tmp)
out.close()
os.replace(tmp, path)
print(f"added derived indices to {path}")
print("  ", [v for v in out.data_vars
             if v.startswith(("flash", "norm_intensity"))])
