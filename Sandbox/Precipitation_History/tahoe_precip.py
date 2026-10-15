"""
Loading and extreme-value helpers for the Tahoe basin heavy-rainfall analysis.

The per-year cubes are ~90 MB each, so 20 years does not fit comfortably in
memory at once. Everything here is therefore written to be driven one season
at a time, with only the reduced statistics kept across years.
"""

import glob
import json
import os
import re

import numpy as np
import pandas as pd
import xarray as xr

import config as C


# ---------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------

def year_files(prefix):
    """Map year -> sorted list of cache files for that year."""
    out = {}
    for f in sorted(glob.glob(os.path.join(C.INTERIM, f"{prefix}_tahoe_*.nc"))):
        m = re.search(r"_(\d{4})(\d{2})?\.nc$", os.path.basename(f))
        if m:
            out.setdefault(int(m.group(1)), []).append(f)
    return out


def load_year(files):
    """Load one season into memory as a contiguous hourly DataArray."""
    parts = []
    for f in files:
        # AORC caches hold a bare DataArray; MRMS caches hold a Dataset with
        # precip_mm plus the per-hour fetch/screen status flag.
        with xr.open_dataset(f) as d:
            da = d["precip_mm"] if "precip_mm" in d.data_vars                 else d[list(d.data_vars)[0]]
            parts.append(da.load())
    cube = parts[0] if len(parts) == 1 else xr.concat(parts, dim="time")
    cube = cube.sortby("time")
    _, first = np.unique(cube.time.values, return_index=True)
    cube = cube.isel(time=np.sort(first))

    # Reindex onto a gap-free hourly axis so the 24-hour rolling window
    # cannot silently span a data outage.
    full = pd.date_range(cube.time.values[0], cube.time.values[-1], freq="h")
    cube = cube.reindex(time=full)

    # MRMS grids run north to south while AORC runs south to north. Normalise
    # to ascending here so every downstream product -- NetCDF, CSV, GeoTIFF,
    # cross-dataset comparison -- shares one orientation.
    return cube.sortby("latitude").sortby("longitude")


def local_index(cube):
    return cube.time.to_index().tz_localize("UTC").tz_convert(C.LOCAL_TZ)


def season_mask(cube):
    return np.isin(local_index(cube).month, C.SEASON_MONTHS)


# ---------------------------------------------------------------------
# Accumulation
# ---------------------------------------------------------------------

def _rolling_sum(arr, w):
    """Trailing sum over `w` steps along axis 0, via cumulative sums.

    xarray's own rolling falls back to a Python loop without bottleneck
    installed, which is far too slow for 22 million points per season.
    A cumsum differences in one pass instead.
    """
    cs = np.cumsum(arr, axis=0, dtype="float64")
    out = np.empty_like(cs)
    out[:w] = cs[:w]
    out[w:] = cs[w:] - cs[:-w]
    return out


def rolling_24h(cube, min_valid=20):
    """Running 24-hour accumulation, labelled at the end of the window.

    A rolling window is used instead of calendar-day totals because storms
    do not respect midnight; calendar days can understate the true worst
    24-hour depth at a site by up to about 40%.

    Windows missing more than (24 - min_valid) hours are set to NaN so that
    data outages are not read as dry periods.
    """
    vals = cube.values
    good = np.isfinite(vals)
    acc = _rolling_sum(np.where(good, vals, 0.0), 24)
    nval = _rolling_sum(good.astype("float32"), 24)
    acc = np.where(nval >= min_valid, acc, np.nan).astype("float32")
    return xr.DataArray(acc, dims=cube.dims, coords=cube.coords,
                        name="precip24_mm")


# ---------------------------------------------------------------------
# Domain mask
# ---------------------------------------------------------------------

def basin_mask(lats, lons, geojson_path=None):
    """Boolean (lat, lon) mask of cells whose centre lies inside the TRPA line."""
    from matplotlib.path import Path

    path_file = geojson_path or C.BOUNDARY
    with open(path_file) as fh:
        gj = json.load(fh)

    rings = []
    for feat in gj["features"]:
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" \
            else geom["coordinates"]
        for poly in polys:
            rings.append(np.asarray(poly[0], dtype=float)[:, :2])

    lon2d, lat2d = np.meshgrid(lons, lats)
    pts = np.column_stack([lon2d.ravel(), lat2d.ravel()])
    inside = np.zeros(len(pts), dtype=bool)
    for ring in rings:
        inside |= Path(ring).contains_points(pts)
    return inside.reshape(lat2d.shape)


# ---------------------------------------------------------------------
# Extreme value fitting
# ---------------------------------------------------------------------

def gumbel_return_levels(ams, return_periods=(2, 5, 10, 25, 50, 100)):
    """Per-cell Gumbel (EV1) return levels fitted by L-moments.

    L-moments rather than moments or MLE: with only ~20 annual maxima per
    cell they are much less biased and far more stable, which matters when
    the fit is repeated independently at every grid cell.

    `ams` must be (year, lat, lon).
    """
    x = np.sort(np.asarray(ams.values, dtype=float), axis=0)
    n = x.shape[0]
    i = np.arange(1, n + 1)[:, None, None]

    l1 = x.mean(axis=0)
    b1 = (((i - 1) / (n - 1)) * x).sum(axis=0) / n
    l2 = 2 * b1 - l1

    alpha = np.where(l2 > 0, l2 / np.log(2.0), np.nan)
    xi = l1 - alpha * np.euler_gamma

    dims = ams.dims[1:]
    coords = {d: ams.coords[d] for d in dims}
    data = {}
    for T in return_periods:
        y = -np.log(-np.log(1.0 - 1.0 / T))
        data[f"rl_{T}yr"] = (dims, xi + alpha * y)
    data["gumbel_loc"] = (dims, xi)
    data["gumbel_scale"] = (dims, alpha)
    return xr.Dataset(data, coords=coords)


def decluster_peaks(series, times, n=25, sep_hours=48):
    """Top-n peaks separated by at least `sep_hours`, largest first.

    Without declustering a single multi-day storm would occupy most of the
    top of the list; the separation makes the catalogue read as distinct
    events.
    """
    s = np.asarray(series, dtype=float).copy()
    s[np.isnan(s)] = -np.inf
    picks = []
    for _ in range(n):
        k = int(np.argmax(s))
        if not np.isfinite(s[k]) or s[k] <= 0:
            break
        picks.append((times[k], float(s[k])))
        lo = max(0, k - sep_hours)
        hi = min(len(s), k + sep_hours + 1)
        s[lo:hi] = -np.inf
    return picks


# ---------------------------------------------------------------------
# Derived indices
# ---------------------------------------------------------------------

def add_derived_indices(ds):
    """Add indices that describe storm *character*, not just storm size.

    Absolute return levels in this basin correlate ~0.95 with mean seasonal
    precipitation, so a map of them is largely a map of the orographic
    climatology. These ratios divide that background out, leaving the part
    that says something about how rain arrives at a place:

      flashiness       1-hour depth as a share of the 24-hour depth. High
                       values mark cells where the design event is a short
                       burst -- the regime that overwhelms small culverts,
                       inlets, and steep urban catchments.
      norm_intensity_* return level per inch of mean seasonal precipitation,
                       i.e. how extreme a wet place is *for how wet it is*.
    """
    ds = ds.copy()
    ds["flashiness"] = ds["rl_1h_10yr"] / ds["rl_24h_10yr"]
    ds["flashiness"].attrs = {
        "units": "ratio",
        "long_name": "10-year 1-hour depth divided by 10-year 24-hour depth"}

    for dur in ("1h", "24h"):
        v = f"norm_intensity_{dur}"
        ds[v] = ds[f"rl_{dur}_10yr"] / ds["mean_season_total"]
        ds[v].attrs = {
            "units": "in per in",
            "long_name": f"10-year {dur} depth per inch of mean Jun-Oct total"}
    return ds
