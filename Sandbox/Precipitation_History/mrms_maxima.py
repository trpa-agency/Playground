"""
Per-cell record maxima from the MRMS hourly QPE cubes: 1-hour and 24-hour,
for the whole Jun-Oct season and for each calendar month separately.

For every cell this records both the depth and *when* it happened, because
"the wettest hour here was 1.8 in on 5 Aug 2022" is far more useful to a
planner than the number alone -- and, given how scattered convective maxima
turn out to be, the dates are what make the scatter visible.

Months are local (Pacific). The 24-hour value is a rolling window labelled
at its end hour, so a storm spanning midnight is not split; the window's end
hour decides which month it counts toward.

Outputs
    data/processed/mrms_maxima_tahoe.nc     all layers + occurrence times
    data/processed/mrms_maxima_gis/*.tif    one GeoTIFF per layer
    data/processed/mrms_maxima_payload.json compact payload for the web map

Run:  python mrms_maxima.py
"""

import json
import os

import numpy as np
import pandas as pd
import xarray as xr

import config as C
import tahoe_precip as T

MONTHS = [(6, "June"), (7, "July"), (8, "August"), (9, "September"),
          (10, "October")]
DURATIONS = ("1h", "24h")


def accumulate(prefix="mrms"):
    """Running per-cell maxima and their timestamps, over all seasons."""
    files = T.year_files(prefix)
    if not files:
        raise SystemExit(f"no cached {prefix} cubes in {C.INTERIM}")
    years = sorted(files)

    best = {}          # (dur, period) -> (max array, timestamp array)
    series = {}        # (dur, year, month) -> basin-level stats
    lat = lon = None
    basin = None

    for y in years:
        cube = T.load_year(files[y])
        if lat is None:
            lat, lon = cube.latitude.values, cube.longitude.values
            basin = T.basin_mask(lat, lon)

        fields = {"1h": cube.values,
                  "24h": T.rolling_24h(cube).values}
        li = T.local_index(cube)
        month = li.month.values
        stamps = li.strftime("%Y-%m-%d %H:00").to_numpy()

        for dur in DURATIONS:
            arr = fields[dur]
            for key, sel in [("all", np.isin(month, C.SEASON_MONTHS))] + \
                            [(str(m), month == m) for m, _ in MONTHS]:
                if not sel.any():
                    continue
                sub = arr[sel]
                # nanargmax needs at least one finite value per column; cells
                # that are all-NaN are carried through as NaN.
                allnan = np.all(~np.isfinite(sub), axis=0)
                filled = np.where(np.isfinite(sub), sub, -np.inf)
                k = np.argmax(filled, axis=0)
                vmax = np.take_along_axis(filled, k[None], axis=0)[0]
                vmax = np.where(allnan, np.nan, vmax)
                when = stamps[sel][k]

                # Basin-level series for the charts tab: one number per
                # duration, year and calendar month. Taken over in-basin
                # cells only, so the wetter out-of-basin crest does not
                # stand in for the basin's own record.
                # A month the storm-day screen skipped outright contains
                # fetcher-written zeros, not observations. Recording it as
                # 0.00 would plot as a measured dry month, so leave it out
                # of the series entirely.
                if key != "all" and not sel.any():
                    pass
                elif key != "all":
                    cells = vmax[basin]
                    finite = cells[np.isfinite(cells)]
                    if finite.size:
                        j = int(np.nanargmax(np.where(basin, vmax, np.nan)))
                        jy, jx = np.unravel_index(j, vmax.shape)
                        series[(dur, y, int(key))] = {
                            "max": float(np.max(finite)),
                            "med": float(np.median(finite)),
                            "when": str(when[jy, jx]),
                            "lat": float(lat[jy]), "lon": float(lon[jx]),
                        }

                slot = best.get((dur, key))
                if slot is None:
                    best[(dur, key)] = [vmax.copy(), when.astype("U16")]
                else:
                    prev_v, prev_w = slot
                    newer = np.isfinite(vmax) & (~np.isfinite(prev_v)
                                                 | (vmax > prev_v))
                    prev_v[newer] = vmax[newer]
                    prev_w[newer] = when[newer]

        print(f"  {y}: max1h {np.nanmax(fields['1h'])/C.MM_PER_IN:5.2f} in  "
              f"max24h {np.nanmax(fields['24h'])/C.MM_PER_IN:5.2f} in",
              flush=True)
        del cube, fields

    return best, series, lat, lon, years


def main():
    best, series, lat, lon, years = accumulate()

    periods = [("all", "Jun-Oct")] + [(str(m), n) for m, n in MONTHS]
    ds = xr.Dataset(coords={"latitude": lat, "longitude": lon})

    for dur in DURATIONS:
        for key, label in periods:
            v, w = best[(dur, key)]
            name = f"max_{dur}_{key}"
            ds[name] = (("latitude", "longitude"), v / C.MM_PER_IN)
            ds[name].attrs = {"units": "in", "duration": dur, "period": label,
                              "long_name": f"Record {dur} rainfall, {label}"}
            ds[f"when_{dur}_{key}"] = (("latitude", "longitude"),
                                       w.astype("U16"))
            ds[f"when_{dur}_{key}"].attrs = {
                "long_name": f"Local time of the {dur} maximum, {label}"}

    ds["in_basin"] = (("latitude", "longitude"),
                      T.basin_mask(lat, lon))

    # Basin series as (duration, year, month) arrays.
    mon = [m for m, _ in MONTHS]
    for dur in DURATIONS:
        for field in ("max", "med"):
            arr = np.full((len(years), len(mon)), np.nan)
            for iy, y in enumerate(years):
                for im, m in enumerate(mon):
                    rec = series.get((dur, y, m))
                    if rec:
                        arr[iy, im] = rec[field] / C.MM_PER_IN
            ds[f"series_{field}_{dur}"] = (("year", "month"), arr)
            ds[f"series_{field}_{dur}"].attrs = {"units": "in"}
        wh = np.full((len(years), len(mon)), "", dtype="U16")
        for iy, y in enumerate(years):
            for im, m in enumerate(mon):
                rec = series.get((dur, y, m))
                if rec:
                    wh[iy, im] = rec["when"]
        ds[f"series_when_{dur}"] = (("year", "month"), wh)
    ds = ds.assign_coords(year=years, month=mon)
    ds.attrs.update(
        dataset="MRMS", seasons=f"{years[0]}-{years[-1]}",
        n_seasons=len(years), months="Jun-Oct (local)",
        source="NOAA MRMS gauge-corrected hourly QPE",
        note=("GaugeCorr_QPE_01H before 2020-10-14, "
              "MultiSensor_QPE_01H_Pass2 after; storm-day-screened fetch, "
              "which does not affect maxima"))

    out = os.path.join(C.OUT, "mrms_maxima_tahoe.nc")
    tmp = out + ".tmp"
    ds.to_netcdf(tmp)
    ds.close()
    os.replace(tmp, out)
    print(f"wrote {out} ({os.path.getsize(out)/1e6:.1f} MB)", flush=True)

    summarise(xr.open_dataset(out), periods)


def summarise(ds, periods):
    mask = ds["in_basin"].values.astype(bool)
    print(f"\n{'period':<10} {'1-hour max':>12} {'24-hour max':>13} "
          f"{'1h basin median':>17}")
    for key, label in periods:
        a = np.where(mask, ds[f"max_1h_{key}"].values, np.nan)
        b = np.where(mask, ds[f"max_24h_{key}"].values, np.nan)
        print(f"{label:<10} {np.nanmax(a):>10.2f} in {np.nanmax(b):>11.2f} in "
              f"{np.nanmedian(a):>15.2f} in")


if __name__ == "__main__":
    main()
