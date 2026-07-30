"""
Download NOAA MRMS Multi-Sensor QPE (gauge-corrected radar precipitation)
for the Lake Tahoe basin for a given date range, and compute precipitation
totals for that area.

Data source: s3://noaa-mrms-pds (public, no AWS credentials needed)
Product: MultiSensor_QPE_01H_Pass2_00.00  (hourly precip accumulation, mm)
  - "Pass2" = the reprocessed pass that includes more gauge data, best for
    retrospective/historical analysis (vs "Pass1" which is faster/less complete)

Requirements:
    pip install boto3 xarray cfgrib pygrib numpy matplotlib cartopy

Usage:
    python tahoe_precip_mrms.py

Output:
    - Console summary of basin totals per day
    - A PNG map per day showing the spatial precip accumulation pattern
      over the Tahoe basin (mrms_tahoe_data/precip_map_<date>.png)
"""

import os
import gzip
import shutil
import datetime as dt

import boto3
from botocore import UNSIGNED
from botocore.client import Config
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt

try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    HAVE_CARTOPY = True
except ImportError:
    HAVE_CARTOPY = False

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------

# Tahoe basin bounding box (generous, covers the whole lake + surrounding ridgeline)
LAT_MIN, LAT_MAX = 38.80, 39.35
LON_MIN, LON_MAX = -120.25, -119.85   # MRMS longitudes are 0-360, we'll convert

DATES = ["20260712", "20260713"]   # YYYYMMDD, UTC

PRODUCT = "MultiSensor_QPE_01H_Pass2_00.00"
BUCKET = "noaa-mrms-pds"

WORKDIR = "./mrms_tahoe_data"
os.makedirs(WORKDIR, exist_ok=True)

# ------------------------------------------------------------------
# S3 CLIENT (anonymous / no-sign-request, since this bucket is public)
# ------------------------------------------------------------------

s3 = boto3.client("s3", config=Config(signature_version=UNSIGNED))


def list_hourly_files(date_str):
    """List all hourly QPE files for a given date."""
    prefix = f"CONUS/{PRODUCT}/{date_str}/"
    paginator = s3.get_paginator("list_objects_v2")
    keys = []
    for page in paginator.paginate(Bucket=BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            if obj["Key"].endswith(".grib2.gz"):
                keys.append(obj["Key"])
    return sorted(keys)


def download_and_unzip(key):
    """Download a .grib2.gz file and decompress it locally."""
    local_gz = os.path.join(WORKDIR, os.path.basename(key))
    local_grib = local_gz[:-3]  # strip .gz

    if not os.path.exists(local_grib):
        s3.download_file(BUCKET, key, local_gz)
        with gzip.open(local_gz, "rb") as f_in, open(local_grib, "wb") as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.remove(local_gz)

    return local_grib


def subset_tahoe_grid(grib_path):
    """
    Open a MRMS GRIB2 file and return the precip (mm) grid + lat/lon
    coordinate arrays, cropped to the Tahoe basin bounding box.
    """
    ds = xr.open_dataset(grib_path, engine="cfgrib")

    # MRMS grids use 0-360 longitude convention
    lon_min_360 = LON_MIN % 360
    lon_max_360 = LON_MAX % 360

    lat_name = "latitude" if "latitude" in ds.coords else "lat"
    lon_name = "longitude" if "longitude" in ds.coords else "lon"

    subset = ds.sel(
        {lat_name: slice(LAT_MAX, LAT_MIN)},  # MRMS lat usually descends
    ).sel({lon_name: slice(lon_min_360, lon_max_360)})

    varname = list(subset.data_vars)[0]
    data = subset[varname].values

    # MRMS uses a large negative sentinel (e.g. -3 or -999) for missing/no-data
    data = np.where(data < 0, np.nan, data)

    lats = subset[lat_name].values
    lons = subset[lon_name].values
    # convert back to -180/180 for normal plotting
    lons = np.where(lons > 180, lons - 360, lons)

    ds.close()
    return data, lats, lons


def subset_tahoe_mean_and_max(data):
    """Given a precip grid (mm), return basin mean and max."""
    mean_mm = float(np.nanmean(data)) if np.any(~np.isnan(data)) else float("nan")
    max_mm = float(np.nanmax(data)) if np.any(~np.isnan(data)) else float("nan")
    return mean_mm, max_mm


def plot_precip_map(accum_grid, lats, lons, date_str, out_path):
    """Plot a daily accumulated precip map over the Tahoe basin."""
    # convert mm -> inches for the map, since that's the more intuitive
    # unit for a US-based precip total
    accum_in = accum_grid / 25.4

    vmax = np.nanmax(accum_in) if np.any(~np.isnan(accum_in)) else 1.0
    vmax = max(vmax, 0.1)  # avoid a degenerate all-zero color scale

    if HAVE_CARTOPY:
        fig = plt.figure(figsize=(8, 7))
        ax = plt.axes(projection=ccrs.PlateCarree())
        ax.set_extent([LON_MIN, LON_MAX, LAT_MIN, LAT_MAX], crs=ccrs.PlateCarree())

        mesh = ax.pcolormesh(
            lons, lats, accum_in,
            cmap="YlGnBu", vmin=0, vmax=vmax,
            shading="auto", transform=ccrs.PlateCarree(),
        )

        ax.add_feature(cfeature.STATES, linewidth=0.6, edgecolor="gray")
        ax.add_feature(cfeature.LAKES, facecolor="none", edgecolor="black", linewidth=1.0)
        ax.add_feature(cfeature.RIVERS, edgecolor="steelblue", linewidth=0.5)

        gl = ax.gridlines(draw_labels=True, linewidth=0.3, color="gray", alpha=0.5)
        gl.top_labels = False
        gl.right_labels = False

        cbar = plt.colorbar(mesh, ax=ax, orientation="vertical", pad=0.05, shrink=0.8)
        cbar.set_label("Precipitation (in)")

        ax.set_title(f"MRMS 24-hr Precipitation Accumulation — {date_str}\nTahoe Basin")
    else:
        # fallback: plain grid plot, no coastlines/state borders/lake outline
        fig, ax = plt.subplots(figsize=(8, 7))
        mesh = ax.pcolormesh(lons, lats, accum_in, cmap="YlGnBu", vmin=0, vmax=vmax, shading="auto")
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_title(f"MRMS 24-hr Precipitation Accumulation — {date_str}\nTahoe Basin\n"
                     f"(install cartopy for state/lake outlines)")
        cbar = plt.colorbar(mesh, ax=ax)
        cbar.set_label("Precipitation (in)")

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"  Saved map: {out_path}")


def main():
    grand_total_mean = 0.0
    grand_total_max = 0.0

    for date_str in DATES:
        print(f"\n=== {date_str} ===")
        keys = list_hourly_files(date_str)
        if not keys:
            print("  No files found for this date (check date/product name).")
            continue

        daily_mean_sum = 0.0
        daily_max_sum = 0.0
        accum_grid = None
        grid_lats = grid_lons = None

        for key in keys:
            grib_path = download_and_unzip(key)
            data, lats, lons = subset_tahoe_grid(grib_path)
            mean_mm, max_mm = subset_tahoe_mean_and_max(data)
            hour_label = os.path.basename(key).split("_")[-1].replace(".grib2", "")
            print(f"  {hour_label}: basin-mean={mean_mm:.2f} mm, basin-max={max_mm:.2f} mm")
            daily_mean_sum += 0 if np.isnan(mean_mm) else mean_mm
            daily_max_sum += 0 if np.isnan(max_mm) else max_mm

            # build up the running spatial total for this day (treat NaN as 0
            # for the accumulation itself so gaps don't wipe out the whole sum)
            hourly_filled = np.nan_to_num(data, nan=0.0)
            if accum_grid is None:
                accum_grid = hourly_filled.copy()
                grid_lats, grid_lons = lats, lons
            else:
                accum_grid += hourly_filled

        print(f"  --> Daily total (basin-avg): {daily_mean_sum:.2f} mm "
              f"({daily_mean_sum/25.4:.2f} in)")
        print(f"  --> Daily total (basin-max cell): {daily_max_sum:.2f} mm "
              f"({daily_max_sum/25.4:.2f} in)")

        if accum_grid is not None:
            map_path = os.path.join(WORKDIR, f"precip_map_{date_str}.png")
            plot_precip_map(accum_grid, grid_lats, grid_lons, date_str, map_path)

        grand_total_mean += daily_mean_sum
        grand_total_max += daily_max_sum

    print("\n=== TOTAL over both days ===")
    print(f"Basin-average total: {grand_total_mean:.2f} mm ({grand_total_mean/25.4:.2f} in)")
    print(f"Basin-max cell total: {grand_total_max:.2f} mm ({grand_total_max/25.4:.2f} in)")


if __name__ == "__main__":
    main()
