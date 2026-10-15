"""
Turn the cached hourly precipitation cubes into heavy-rainfall statistics
for the Tahoe basin, on 1-hour and 24-hour durations.

For each grid cell and each duration this produces:
  * the annual maximum series over the Jun-Oct season
  * Gumbel return levels (2, 5, 10, 25, 50, 100 year)
  * how often each intensity threshold is crossed per season
  * seasonal totals and wet-hour counts

and, for the basin as a whole, a declustered catalogue of the largest
storms in the record.

Run:  python analyze.py --dataset aorc
      python analyze.py --dataset mrms
"""

import argparse
import os

import numpy as np
import pandas as pd
import xarray as xr

import config as C
import tahoe_precip as T

RPS = (2, 5, 10, 25, 50, 100)


def analyze(prefix, label):
    files_by_year = T.year_files(prefix)
    if not files_by_year:
        raise SystemExit(f"no cached {prefix} files in {C.INTERIM}")

    years = sorted(files_by_year)
    print(f"[{label}] {len(years)} seasons: {years[0]}-{years[-1]}", flush=True)

    ams1, ams24, totals, wet, cov = [], [], [], [], []
    exc1 = {t: [] for t in C.THRESH_01H_IN}
    exc24 = {t: [] for t in C.THRESH_24H_IN}
    events = []
    kept_years = []

    for y in years:
        cube = T.load_year(files_by_year[y])
        r24 = T.rolling_24h(cube)

        m = T.season_mask(cube)
        p1 = cube.isel(time=m)
        p24 = r24.isel(time=m)
        li = T.local_index(cube)[m]

        # Fraction of season hours actually present -- a season that is
        # badly incomplete must not contribute an annual maximum.
        coverage = float(p1.notnull().mean())
        cov.append(coverage)
        if coverage < 0.80:
            print(f"  {y}: coverage {coverage:.0%} -- excluded from AMS",
                  flush=True)
            continue
        kept_years.append(y)

        ams1.append(p1.max("time"))
        ams24.append(p24.max("time"))
        totals.append(p1.sum("time"))
        wet.append((p1 >= 0.254).sum("time").astype("float32"))

        for t in C.THRESH_01H_IN:
            exc1[t].append((p1 >= t * C.MM_PER_IN).sum("time").astype("float32"))
        for t in C.THRESH_24H_IN:
            exc24[t].append((p24 >= t * C.MM_PER_IN).sum("time").astype("float32"))

        # Storm catalogue: rank by the wettest cell in the basin, which is
        # what a localised cloudburst actually looks like here.
        basin_max_24 = p24.max(["latitude", "longitude"]).values
        for when, depth in T.decluster_peaks(basin_max_24, li, n=12):
            k = int(np.argmin(np.abs(li - when)))
            fld = p24.isel(time=k).values
            if np.all(np.isnan(fld)):
                continue
            jy, jx = np.unravel_index(np.nanargmax(fld), fld.shape)
            lo = max(0, k - 23)
            events.append({
                "end_local": when.strftime("%Y-%m-%d %H:%M"),
                "year": y,
                "max24_in": depth / C.MM_PER_IN,
                "basin_mean24_in": float(np.nanmean(fld)) / C.MM_PER_IN,
                "max1h_in": float(np.nanmax(p1.isel(time=slice(lo, k + 1)).values))
                / C.MM_PER_IN,
                "lat": float(p24.latitude[jy]),
                "lon": float(p24.longitude[jx]),
            })

        print(f"  {y}: cov {coverage:.0%}  max1h "
              f"{float(ams1[-1].max())/C.MM_PER_IN:5.2f} in  max24h "
              f"{float(ams24[-1].max())/C.MM_PER_IN:5.2f} in", flush=True)
        del cube, r24, p1, p24

    yc = xr.DataArray(kept_years, dims="year", name="year")
    A1 = xr.concat(ams1, dim=yc)
    A24 = xr.concat(ams24, dim=yc)

    ds = xr.Dataset({
        "ams_1h": A1, "ams_24h": A24,
        "season_total": xr.concat(totals, dim=yc),
        "wet_hours": xr.concat(wet, dim=yc),
    })
    ds["mean_season_total"] = ds.season_total.mean("year")
    ds["mean_wet_hours"] = ds.wet_hours.mean("year")
    ds["mean_ams_1h"] = A1.mean("year")
    ds["mean_ams_24h"] = A24.mean("year")
    ds["record_max_1h"] = A1.max("year")
    ds["record_max_24h"] = A24.max("year")

    for dur, ams in (("1h", A1), ("24h", A24)):
        rl = T.gumbel_return_levels(ams, RPS)
        for T_ in RPS:
            ds[f"rl_{dur}_{T_}yr"] = rl[f"rl_{T_}yr"]

    n = len(kept_years)
    for t, v in exc1.items():
        ds[f"exc_1h_{t:g}in_per_season"] = xr.concat(v, dim=yc).sum("year") / n
    for t, v in exc24.items():
        ds[f"exc_24h_{t:g}in_per_season"] = xr.concat(v, dim=yc).sum("year") / n

    # Convert every depth field to inches for downstream use.
    for v in list(ds.data_vars):
        if v.startswith(("ams_", "rl_", "mean_ams", "record_max",
                         "season_total", "mean_season_total")):
            ds[v] = ds[v] / C.MM_PER_IN
            ds[v].attrs["units"] = "in"

    mask = T.basin_mask(ds.latitude.values, ds.longitude.values)
    ds["in_basin"] = (("latitude", "longitude"), mask)

    # "Proneness": how a cell's 10-year 24-hour depth compares with the
    # basin median, so the map reads as relative risk rather than absolute
    # depth (which is dominated by elevation).
    for dur in ("1h", "24h"):
        base = np.nanmedian(np.where(mask, ds[f"rl_{dur}_10yr"].values, np.nan))
        ds[f"prone_index_{dur}"] = ds[f"rl_{dur}_10yr"] / base

    ds = T.add_derived_indices(ds)

    # If the cubes came from a storm-day-screened fetch, hours on non-storm
    # days were stored as zero rather than fetched. Extremes and threshold
    # exceedances are unaffected -- those days had no rain to contribute --
    # but seasonal totals and wet-hour counts are biased low and must not be
    # read as climatology.
    import glob as _glob
    screened = False
    for _f in _glob.glob(os.path.join(C.INTERIM, f"{prefix}_tahoe_*.nc")):
        with xr.open_dataset(_f) as _d:
            if _d.attrs.get("screened") == "yes":
                screened = True
        break
    if screened:
        for _v in ("season_total", "mean_season_total", "wet_hours",
                   "mean_wet_hours"):
            if _v in ds:
                ds[_v].attrs["warning"] = (
                    "BIASED LOW: source fetch covered storm days only; "
                    "use for relative comparison, not as a climatological "
                    "total")
        print(f"[{label}] note: storm-day-screened input -- seasonal totals "
              f"and wet-hour counts are biased low", flush=True)
    ds.attrs["storm_day_screened"] = "yes" if screened else "no"

    ds.attrs.update(dataset=label, seasons=f"{kept_years[0]}-{kept_years[-1]}",
                    n_seasons=n, months="Jun-Oct (local)",
                    boundary="TRPA regulatory boundary")

    # Write to a sibling file and swap it in. netCDF4 holds the handle open
    # in xarray's file cache, and writing straight to the final path has
    # twice left a zero-byte file behind when anything else touched it.
    out_nc = os.path.join(C.OUT, f"{prefix}_tahoe_extremes.nc")
    tmp_nc = out_nc + ".tmp"
    ds.to_netcdf(tmp_nc)
    ds.close()
    os.replace(tmp_nc, out_nc)
    size = os.path.getsize(out_nc)
    if size == 0:
        raise RuntimeError(f"{out_nc} came out empty")
    print(f"[{label}] wrote {out_nc} ({size/1e6:.1f} MB)", flush=True)

    # Re-open for the summaries below, so the writer handle is not reused.
    ds = xr.open_dataset(out_nc).load()

    ev = pd.DataFrame(events).sort_values("max24_in", ascending=False)
    ev = ev.drop_duplicates("end_local").head(60)
    ev.to_csv(os.path.join(C.OUT, f"{prefix}_top_storms.csv"), index=False,
              float_format="%.3f")

    # Per-cell table for GIS: one row per in-basin cell.
    flat = {"lat": None, "lon": None}
    lon2d, lat2d = np.meshgrid(ds.longitude.values, ds.latitude.values)
    keep = mask.ravel()
    tbl = {"lat": lat2d.ravel()[keep], "lon": lon2d.ravel()[keep]}
    for v in ds.data_vars:
        if ds[v].dims == ("latitude", "longitude") and v != "in_basin":
            tbl[v] = ds[v].values.ravel()[keep]
    pd.DataFrame(tbl).to_csv(
        os.path.join(C.OUT, f"{prefix}_cell_stats.csv"),
        index=False, float_format="%.4f")

    # Per-season basin summary.
    summ = pd.DataFrame({
        "year": kept_years,
        "coverage": [c for c, y in zip(cov, years) if y in kept_years],
        "basin_mean_total_in": ds.season_total.where(ds.in_basin)
                                 .mean(["latitude", "longitude"]).values,
        "basin_max_1h_in": ds.ams_1h.where(ds.in_basin)
                             .max(["latitude", "longitude"]).values,
        "basin_max_24h_in": ds.ams_24h.where(ds.in_basin)
                              .max(["latitude", "longitude"]).values,
    })
    summ.to_csv(os.path.join(C.OUT, f"{prefix}_season_summary.csv"),
                index=False, float_format="%.3f")

    print(summ.to_string(index=False, float_format=lambda x: f"{x:.2f}"),
          flush=True)
    return ds


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=["aorc", "mrms"], default="aorc")
    a = ap.parse_args()
    analyze(a.dataset, a.dataset.upper())
