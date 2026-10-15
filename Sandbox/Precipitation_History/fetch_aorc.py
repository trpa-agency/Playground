"""
Pull 20 years (2006-2025) of AORC v1.1 1-km hourly precipitation for the
Tahoe basin box, June-October, and cache one NetCDF per year.

AORC is stored on S3 as one Zarr store per year, chunked (144, 128, 256)
in (time, lat, lon). The Tahoe box lands inside a single longitude chunk
and two latitude chunks, so a season costs ~50 chunk reads -- cheap.

Run:  python fetch_aorc.py [--years 2006 2007 ...] [--workers 4]
"""

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd
import s3fs
import xarray as xr

import config as C


def season_slice(year):
    """UTC time bounds that fully contain the local Jun 1 - Oct 31 season.

    A 3-day pad on each end guarantees that any 24-hour accumulation window
    overlapping the season is complete, and absorbs the UTC/Pacific offset.
    """
    return slice(f"{year}-05-29", f"{year}-11-03")


def fetch_year(year, fs=None, overwrite=False):
    out = os.path.join(C.INTERIM, f"aorc_tahoe_{year}.nc")
    if os.path.exists(out) and not overwrite:
        return out, "cached"

    fs = fs or s3fs.S3FileSystem(anon=True)
    store = s3fs.S3Map(root=f"{C.AORC_BUCKET}/{year}.zarr", s3=fs, check=False)
    ds = xr.open_dataset(store, engine="zarr", consolidated=True,
                         chunks={"time": 144})

    sub = ds["APCP_surface"].sel(
        time=season_slice(year),
        latitude=slice(C.LAT_MIN, C.LAT_MAX),
        longitude=slice(C.LON_MIN, C.LON_MAX),
    )

    t0 = time.time()
    arr = sub.load()
    elapsed = time.time() - t0

    # AORC stores int16 * 0.1 with -32767 as fill; xarray has already applied
    # scale_factor and turned fill into NaN. Precip cannot be negative --
    # clip the tiny negatives that round-tripping the scale factor can leave.
    arr = arr.where(np.isnan(arr) | (arr >= 0), 0.0)
    arr.name = "precip_mm"
    arr.attrs = {
        "units": "mm",
        "long_name": "Hourly total precipitation",
        "source": "NOAA AORC v1.1 1-km",
        "accumulation": "1 hour, ending at the timestamp",
        "time_zone": "UTC",
    }

    enc = {"precip_mm": {"zlib": True, "complevel": 4, "dtype": "float32"}}
    arr.to_netcdf(out, encoding=enc)
    ds.close()
    return out, f"{arr.sizes['time']}h in {elapsed:.0f}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="*", default=C.AORC_YEARS)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args()

    fs = s3fs.S3FileSystem(anon=True)
    for y in args.years:
        try:
            path, note = fetch_year(y, fs=fs, overwrite=args.overwrite)
            size = os.path.getsize(path) / 1e6
            print(f"{y}  {note:<24} {size:6.1f} MB  {os.path.basename(path)}",
                  flush=True)
        except Exception as e:
            print(f"{y}  FAILED: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
