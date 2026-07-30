"""
Build a self-contained, interactive single-page HTML web map from the MRMS
hourly QPE GRIB2 files already downloaded by the Tahoe precip notebook.

Reads:   ./mrms_tahoe_data/*.grib2   (MultiSensor_QPE_01H_Pass2, mm/hr)
Writes:  ./tahoe_precip_map.html     (one file, no build step, no server)

The HTML embeds the full hourly grid as JSON, so the page works offline
except for the basemap tiles.

Usage:
    python build_precip_webmap.py
"""

import base64
import glob
import json
import os
import re
import datetime as dt

import numpy as np
import xarray as xr

# ------------------------------------------------------------------ config
HERE = os.path.dirname(os.path.abspath(__file__))
WORKDIR = os.path.join(HERE, "mrms_tahoe_data")
OUT_HTML = os.path.join(HERE, "tahoe_precip_map.html")

# Where the inlined Leaflet build lives. Downloaded once; see README note at
# the bottom of this file if you need to refresh it.
VENDOR = os.path.join(HERE, "vendor")

LAT_MIN, LAT_MAX = 38.80, 39.35
LON_MIN, LON_MAX = -120.25, -119.85

PRODUCT = "MRMS MultiSensor QPE 01H Pass2"
CELL_DEG = 0.01  # MRMS CONUS grid spacing

# MRMS QPE is reported to 0.1 mm, so tenths-of-a-mm integers are lossless
# and roughly halve the size of the embedded JSON vs. floats.
SCALE = 10
NODATA = -1


# ------------------------------------------------------------------ extract
def read_hour(path):
    """Return (valid_time, lats, lons, grid_mm) for one MRMS GRIB2 file."""
    ds = xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""})
    sub = ds.sel(latitude=slice(LAT_MAX, LAT_MIN)).sel(
        longitude=slice(LON_MIN % 360, LON_MAX % 360)
    )
    var = list(sub.data_vars)[0]
    grid = np.asarray(sub[var].values, dtype="float64")

    # MRMS flags missing / no-coverage with large negatives (-3, -999)
    grid = np.where(grid < 0, np.nan, grid)

    lats = sub.latitude.values.astype("float64")
    lons = sub.longitude.values.astype("float64")
    lons = np.where(lons > 180, lons - 360, lons)

    valid = ds.valid_time.values
    ds.close()
    return np.datetime64(valid, "s").astype("datetime64[s]").item(), lats, lons, grid


def build_payload():
    files = sorted(glob.glob(os.path.join(WORKDIR, "*.grib2")))
    if not files:
        raise SystemExit(f"No .grib2 files in {WORKDIR} — run the notebook first.")

    times, frames = [], []
    lats = lons = None

    for path in files:
        valid, la, lo, grid = read_hour(path)
        if lats is None:
            lats, lons = la, lo
        times.append(valid.replace(tzinfo=dt.timezone.utc))

        # tenths of a mm as ints; NODATA sentinel survives the round trip
        q = np.where(np.isnan(grid), NODATA, np.rint(grid * SCALE)).astype("int32")
        frames.append(q.ravel(order="C").tolist())
        print(f"  {valid:%Y-%m-%d %HZ}  mean={np.nanmean(grid):5.2f} mm  "
              f"max={np.nanmax(grid):5.2f} mm")

    ny, nx = len(lats), len(lons)

    # Cell-edge bounds: coordinates are cell centers, so pad by half a cell.
    # Latitude descends, so row 0 is the *north* edge.
    bounds = {
        "north": float(lats[0] + CELL_DEG / 2),
        "south": float(lats[-1] - CELL_DEG / 2),
        "west": float(lons[0] - CELL_DEG / 2),
        "east": float(lons[-1] + CELL_DEG / 2),
    }

    return {
        "product": PRODUCT,
        "source": "s3://noaa-mrms-pds  (NOAA MRMS, public)",
        "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "units": "mm",
        "scale": SCALE,
        "nodata": NODATA,
        "cellDeg": CELL_DEG,
        "nx": nx,
        "ny": ny,
        "bounds": bounds,
        "lats": [round(float(v), 4) for v in lats],
        "lons": [round(float(v), 4) for v in lons],
        "times": [t.strftime("%Y-%m-%dT%H:%M:%SZ") for t in times],
        "frames": frames,
    }


# ------------------------------------------------------------------ assemble
def read_vendor(name):
    path = os.path.join(VENDOR, name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def main():
    print("Reading GRIB2 hours…")
    payload = build_payload()
    print(f"\n{payload['ny']} x {payload['nx']} cells x {len(payload['times'])} hours")

    leaflet_css = read_vendor("leaflet.css")
    leaflet_js = read_vendor("leaflet.js")

    # Leaflet's CSS points at marker sprites we don't ship; we use no markers,
    # so drop those rules rather than leave dead requests in the page.
    leaflet_css = re.sub(r"url\((images/[^)]+)\)", "none", leaflet_css)

    with open(os.path.join(HERE, "webmap_template.html"), encoding="utf-8") as f:
        template = f.read()

    html = (
        template
        .replace("/*__LEAFLET_CSS__*/", leaflet_css)
        .replace("/*__LEAFLET_JS__*/", leaflet_js)
        .replace('"__DATA__"', json.dumps(payload, separators=(",", ":")))
    )

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nWrote {OUT_HTML}  ({os.path.getsize(OUT_HTML)/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
