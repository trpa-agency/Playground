"""
Export the heavy-rainfall grids as GeoTIFFs for ArcGIS, plus a storm
catalogue as GeoJSON.

Everything is written on the native ~1-km lat/lon grid in EPSG:4326, north-up.
Depth rasters are in inches; exceedance rasters are counts per season.

Run:  python export_gis.py --dataset aorc
"""

import argparse
import json
import os

# A PostgreSQL/PostGIS install on this machine exports a PROJ_LIB pointing at
# a proj.db too old for the PROJ that rasterio ships, which makes even
# EPSG:4326 fail to resolve. Clear the inherited vars before rasterio loads so
# its own bundled database wins.
for _v in ("PROJ_LIB", "PROJ_DATA", "GDAL_DATA"):
    os.environ.pop(_v, None)

import numpy as np
import pandas as pd
import rasterio
import xarray as xr
from rasterio.transform import from_origin

_bundled = os.path.join(os.path.dirname(rasterio.__file__), "proj_data")
if os.path.isdir(_bundled):
    os.environ["PROJ_LIB"] = os.environ["PROJ_DATA"] = _bundled

import config as C

DEPTH_UNITS = "inches"


# Field-by-field units and plain-English meaning. Guessing these from the
# variable name got mean_wet_hours labelled "inches", so they are explicit.
FIXED = {
    "mean_season_total": ("inches", "Mean Jun-Oct precipitation total"),
    "mean_wet_hours": ("hours per season",
                       "Mean count of hours with at least 0.01 in"),
    "mean_ams_1h": ("inches", "Mean annual maximum 1-hour depth"),
    "mean_ams_24h": ("inches", "Mean annual maximum 24-hour depth"),
    "record_max_1h": ("inches", "Largest 1-hour depth in the record"),
    "record_max_24h": ("inches",
                       "Largest rolling 24-hour depth in the record"),
    "prone_index_1h": ("ratio",
                       "10-year 1-hour depth divided by the basin median"),
    "prone_index_24h": ("ratio",
                        "10-year 24-hour depth divided by the basin median"),
    "flashiness": ("ratio",
                   "10-year 1-hour depth divided by 10-year 24-hour depth; "
                   "high means the design event is a short burst"),
    "norm_intensity_1h": ("in per in",
                          "10-year 1-hour depth per inch of mean Jun-Oct "
                          "total"),
    "norm_intensity_24h": ("in per in",
                           "10-year 24-hour depth per inch of mean Jun-Oct "
                           "total"),
}


def units_for(name):
    if name in FIXED:
        return FIXED[name][0]
    if name.startswith("exc_"):
        return "count per season"
    return DEPTH_UNITS


def meaning_for(name):
    if name in FIXED:
        return FIXED[name][1]
    if name.startswith("rl_"):
        _, dur, T = name.split("_")
        return (f"{dur} rainfall depth with a {T.replace('yr','')}-year "
                f"return period (Gumbel, L-moments)")
    if name.startswith("a14_"):
        _, dur, T = name.split("_")
        return (f"NOAA Atlas 14 {dur} depth, {T.replace('yr','')}-year "
                f"return period")
    if name.startswith("exc_"):
        parts = name.split("_")
        return (f"{parts[1]} windows per Jun-Oct season reaching "
                f"{parts[2].replace('in', ' in')}")
    return name


def write_tif(path, arr, lats, lons, nodata=-9999.0, units=DEPTH_UNITS,
              desc=""):
    """Write one north-up EPSG:4326 GeoTIFF."""
    # xarray keeps latitude ascending; GeoTIFF rows run north to south.
    if lats[0] < lats[-1]:
        arr = arr[::-1]
        lats = lats[::-1]

    dy = abs(float(lats[0] - lats[1]))
    dx = abs(float(lons[1] - lons[0]))
    transform = from_origin(float(lons[0]) - dx / 2,
                            float(lats[0]) + dy / 2, dx, dy)

    data = np.where(np.isfinite(arr), arr, nodata).astype("float32")
    with rasterio.open(
        path, "w", driver="GTiff", height=data.shape[0], width=data.shape[1],
        count=1, dtype="float32", crs="EPSG:4326", transform=transform,
        nodata=nodata, compress="deflate", tiled=True,
    ) as dst:
        dst.write(data, 1)
        dst.update_tags(1, UNITS=units, DESCRIPTION=desc)
    return path


def _open(prefix):
    """The extremes files are named per dataset; Atlas 14 is named per series."""
    for cand in (f"{prefix}_tahoe_extremes.nc", f"{prefix}_extremes.nc",
                 f"{prefix}_tahoe.nc",
                 f"atlas14_tahoe_{prefix.replace('atlas14_', '')}.nc"):
        p = os.path.join(C.OUT, cand)
        if os.path.exists(p):
            return xr.open_dataset(p)
    raise SystemExit(f"no NetCDF found for '{prefix}' in {C.OUT}")


def main(prefix):
    ds = _open(prefix)
    gis = os.path.join(C.OUT, f"{prefix}_gis")
    os.makedirs(gis, exist_ok=True)

    lats = ds.latitude.values
    lons = ds.longitude.values

    if "in_basin" in ds:
        mask = ds["in_basin"].values
    else:
        # Atlas 14 grids carry no basin mask of their own; they share the
        # AORC grid exactly, so the mask can be borrowed.
        import tahoe_precip as T
        mask = T.basin_mask(lats, lons)

    written = []
    for name in ds.data_vars:
        da = ds[name]
        if da.dims != ("latitude", "longitude") or name == "in_basin":
            continue

        units = units_for(name)

        # Two versions: full analysis box, and clipped to the TRPA line.
        vals = da.values.astype("float32")
        written.append(write_tif(os.path.join(gis, f"{name}.tif"),
                                 vals, lats, lons, units=units,
                                 desc=meaning_for(name)))
        written.append(write_tif(
            os.path.join(gis, f"{name}_basinclip.tif"),
            np.where(mask, vals, np.nan), lats, lons, units=units,
            desc=meaning_for(name) + " (clipped to TRPA boundary)"))

    # Storm catalogue as points (our datasets only; Atlas 14 has none).
    storms_csv = os.path.join(C.OUT, f"{prefix}_top_storms.csv")
    if not os.path.exists(storms_csv):
        print(f"wrote {len(written)} GeoTIFFs to {gis}", flush=True)
        return
    storms = pd.read_csv(storms_csv)
    feats = [{
        "type": "Feature",
        "geometry": {"type": "Point", "coordinates": [r.lon, r.lat]},
        "properties": {k: (None if pd.isna(v) else v)
                       for k, v in r._asdict().items() if k != "Index"},
    } for r in storms.itertuples()]
    gj = os.path.join(gis, f"{prefix}_top_storms.geojson")
    with open(gj, "w") as fh:
        json.dump({"type": "FeatureCollection", "features": feats}, fh, indent=1)

    # A short data dictionary so the rasters are self-explanatory in ArcGIS.
    rows = []
    for name in ds.data_vars:
        if ds[name].dims != ("latitude", "longitude") or name == "in_basin":
            continue
        rows.append({"raster": f"{name}.tif",
                     "units": units_for(name),
                     "meaning": meaning_for(name)})
    pd.DataFrame(rows).to_csv(os.path.join(gis, "DATA_DICTIONARY.csv"),
                              index=False)

    print(f"wrote {len(written)} GeoTIFFs + {os.path.basename(gj)} to {gis}",
          flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="aorc")
    main(ap.parse_args().dataset)
