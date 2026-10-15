"""
Check the AORC-derived return levels against NOAA Atlas 14, the published
precipitation-frequency standard for this region.

Two things are being tested, and they are different questions:

  1. Level  - our Jun-Oct return levels should sit *below* Atlas 14's
              all-season values, because the basin's largest storms are
              usually winter events that our season excludes.
  2. Pattern - the spatial arrangement of wet and dry cells should agree.
              This is the test that matters for "where is it worst", and it
              is independent of any level bias.

Atlas 14 Volume 6 (Southwest), annual-maximum series, is queried point by
point from the HDSC service. Requests are spaced out to stay polite.

Run:  python compare_atlas14.py --stride 4
"""

import argparse
import ast
import os
import re
import time

import numpy as np
import pandas as pd
import requests
import xarray as xr

import config as C

HDSC = "https://hdsc.nws.noaa.gov/cgi-bin/hdsc/new/cgi_readH5.py"

# Row order of the Atlas 14 quantile table.
DURATIONS = ["5min", "10min", "15min", "30min", "60min", "2h", "3h", "6h",
             "12h", "24h", "2day", "3day", "4day", "7day", "10day", "20day",
             "30day", "45day", "60day"]
ARI = [1, 2, 5, 10, 25, 50, 100, 200, 500]

SESSION = requests.Session()


def atlas14_point(lat, lon, retries=3):
    """Return {duration: {ARI: depth_in}} for one point."""
    params = {"lat": f"{lat:.4f}", "lon": f"{lon:.4f}", "type": "pf",
              "data": "depth", "units": "english", "series": "ams"}
    for k in range(retries):
        try:
            txt = SESSION.get(HDSC, params=params, timeout=60).text
            m = re.search(r"quantiles\s*=\s*(\[\[.*?\]\])\s*;", txt, re.S)
            if not m:
                return None
            q = ast.literal_eval(m.group(1))
            return {DURATIONS[i]: {ARI[j]: float(q[i][j])
                                   for j in range(len(ARI))}
                    for i in range(len(DURATIONS))}
        except Exception:
            if k == retries - 1:
                return None
            time.sleep(2 * (k + 1))
    return None


def main(prefix, stride, pause):
    ds = xr.open_dataset(os.path.join(C.OUT, f"{prefix}_tahoe_extremes.nc"))
    mask = ds["in_basin"].values
    lats, lons = ds.latitude.values, ds.longitude.values

    pts = [(i, j) for i in range(0, len(lats), stride)
           for j in range(0, len(lons), stride) if mask[i, j]]
    print(f"sampling {len(pts)} in-basin points at stride {stride}", flush=True)

    rows = []
    for n, (i, j) in enumerate(pts, 1):
        a = atlas14_point(float(lats[i]), float(lons[j]))
        if a is None:
            continue
        rows.append({
            "lat": float(lats[i]), "lon": float(lons[j]),
            "a14_1h_10yr": a["60min"][10], "a14_1h_100yr": a["60min"][100],
            "a14_24h_10yr": a["24h"][10], "a14_24h_100yr": a["24h"][100],
            "aorc_1h_10yr": float(ds.rl_1h_10yr[i, j]),
            "aorc_1h_100yr": float(ds.rl_1h_100yr[i, j]),
            "aorc_24h_10yr": float(ds.rl_24h_10yr[i, j]),
            "aorc_24h_100yr": float(ds.rl_24h_100yr[i, j]),
        })
        if n % 20 == 0:
            print(f"  {n}/{len(pts)}", flush=True)
        time.sleep(pause)

    df = pd.DataFrame(rows)
    out = os.path.join(C.OUT, f"{prefix}_vs_atlas14.csv")
    df.to_csv(out, index=False, float_format="%.3f")
    print(f"wrote {out}  ({len(df)} points)\n", flush=True)

    print(f"{'metric':<16} {'ratio Jun-Oct/A14':>19} {'spatial r':>11}")
    for dur in ("1h", "24h"):
        for T in (10, 100):
            a = df[f"aorc_{dur}_{T}yr"]
            b = df[f"a14_{dur}_{T}yr"]
            print(f"{dur+' '+str(T)+'yr':<16} {np.median(a/b):>19.2f} "
                  f"{a.corr(b):>11.3f}")
    return df


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="aorc")
    ap.add_argument("--stride", type=int, default=4)
    ap.add_argument("--pause", type=float, default=0.35)
    a = ap.parse_args()
    main(a.dataset, a.stride, a.pause)
