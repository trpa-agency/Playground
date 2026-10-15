"""
Put AORC, MRMS and NOAA Atlas 14 on one grid and ask which of them can be
trusted for which duration.

Atlas 14 is treated as the reference, because it is the published design
standard for the region and is built from long station records rather than
from a gridded reanalysis or a radar mosaic.

Two separate questions are reported:

  level    median ratio of our return level to Atlas 14. Our statistics
           cover Jun-Oct only, so a ratio below 1 is expected; how far
           below is the diagnostic.
  pattern  spatial correlation across in-basin cells. This is the one that
           matters for "where is it worst", and a weak correlation is a
           warning that the hot-spot map is not reliable.

MRMS sits on a 0.01 deg grid and is matched to the AORC/Atlas 14 grid by
nearest neighbour; at ~1 km both ways this shifts a cell by at most ~400 m.

Run:  python compare_datasets.py
"""

import os

import numpy as np
import pandas as pd
import xarray as xr

import config as C

RPS = (2, 10, 25, 100)


def load(prefix):
    p = os.path.join(C.OUT, f"{prefix}_tahoe_extremes.nc")
    return xr.open_dataset(p) if os.path.exists(p) else None


def main():
    a14 = xr.open_dataset(os.path.join(C.OUT, "atlas14_tahoe_ams.nc"))
    aorc = load("aorc")
    mrms = load("mrms")

    # Every dataset here is compared by coordinate, never by array position.
    # The Atlas 14 ASCII grids arrive latitude-descending while AORC and MRMS
    # are ascending, and comparing raw .values would silently flip north for
    # south.
    a14 = a14.sortby("latitude").sortby("longitude")
    aorc = aorc.sortby("latitude").sortby("longitude")
    a14 = a14.interp(latitude=aorc.latitude, longitude=aorc.longitude,
                     method="nearest")

    mask = aorc["in_basin"].values
    rows = []

    for name, ds in (("AORC", aorc), ("MRMS", mrms)):
        if ds is None:
            print(f"{name}: no extremes file yet, skipping", flush=True)
            continue

        # Match MRMS's 0.01-deg grid onto the AORC / Atlas 14 grid.
        ds = ds.sortby("latitude").sortby("longitude")
        if not np.array_equal(ds.latitude.values, aorc.latitude.values):
            ds = ds.interp(latitude=aorc.latitude, longitude=aorc.longitude,
                           method="nearest")

        for dur in ("1h", "24h"):
            for T in RPS:
                ours = np.where(mask, ds[f"rl_{dur}_{T}yr"].values, np.nan)
                ref = np.where(mask, a14[f"a14_{dur}_{T}yr"].values, np.nan)
                ok = np.isfinite(ours) & np.isfinite(ref) & (ref > 0)
                if ok.sum() < 20:
                    continue
                rows.append({
                    "dataset": name, "duration": dur, "return_yr": T,
                    "median_ratio": float(np.median(ours[ok] / ref[ok])),
                    "spatial_r": float(np.corrcoef(ours[ok], ref[ok])[0, 1]),
                    "our_median_in": float(np.median(ours[ok])),
                    "a14_median_in": float(np.median(ref[ok])),
                    "n_cells": int(ok.sum()),
                })

    df = pd.DataFrame(rows)
    out = os.path.join(C.OUT, "dataset_comparison.csv")
    df.to_csv(out, index=False, float_format="%.4f")

    print(f"\nAgainst NOAA Atlas 14 (AMS), in-basin cells only\n")
    print(f"{'dataset':<7} {'dur':<5} {'T':>5} {'ours':>7} {'A14':>7} "
          f"{'ratio':>7} {'spatial r':>10}")
    for r in df.itertuples():
        print(f"{r.dataset:<7} {r.duration:<5} {r.return_yr:>4}y "
              f"{r.our_median_in:>7.2f} {r.a14_median_in:>7.2f} "
              f"{r.median_ratio:>7.2f} {r.spatial_r:>10.3f}")

    # AORC vs MRMS directly, where both exist.
    if aorc is not None and mrms is not None:
        m = mrms.sortby("latitude").sortby("longitude").interp(
            latitude=aorc.latitude, longitude=aorc.longitude,
            method="nearest")
        print(f"\nAORC vs MRMS directly\n")
        print(f"{'dur':<5} {'T':>5} {'MRMS/AORC':>10} {'spatial r':>10}")
        for dur in ("1h", "24h"):
            for T in RPS:
                a = np.where(mask, aorc[f"rl_{dur}_{T}yr"].values, np.nan)
                b = np.where(mask, m[f"rl_{dur}_{T}yr"].values, np.nan)
                ok = np.isfinite(a) & np.isfinite(b) & (a > 0)
                if ok.sum() < 20:
                    continue
                print(f"{dur:<5} {T:>4}y {np.median(b[ok]/a[ok]):>10.2f} "
                      f"{np.corrcoef(a[ok], b[ok])[0,1]:>10.3f}")

    print(f"\nwrote {out}", flush=True)


if __name__ == "__main__":
    main()
