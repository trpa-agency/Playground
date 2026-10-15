"""
Rank every Jun-Oct day in the AORC record by how wet it was over the basin.

This exists to make the MRMS pull tractable. Decoding one hourly MRMS CONUS
GRIB2 costs several seconds on this machine, and a full 12-season Jun-Oct
pull is ~44,000 files. Almost all of those hours are bone dry and contribute
nothing to an extreme-value analysis.

AORC is already cached locally and is free to scan, so it is used to flag
candidate storm days. MRMS is then pulled only for those days (plus a pad),
which preserves every event that matters for 1-hour and 24-hour extremes.

Run:  python screen_days.py
"""

import os

import numpy as np
import pandas as pd

import config as C
import tahoe_precip as T


def main():
    files = T.year_files("aorc")
    rows = []
    for y in sorted(files):
        cube = T.load_year(files[y])
        r24 = T.rolling_24h(cube)
        m = T.season_mask(cube)
        li = T.local_index(cube)[m]
        p1 = cube.isel(time=m)
        p24 = r24.isel(time=m)

        bmax1 = np.nanmax(p1.values, axis=(1, 2))
        bmax24 = np.nanmax(p24.values, axis=(1, 2))
        df = pd.DataFrame({"local": li, "max1h": bmax1, "max24h": bmax24})
        df["date"] = df["local"].dt.date
        g = df.groupby("date").agg(max1h_mm=("max1h", "max"),
                                   max24h_mm=("max24h", "max")).reset_index()
        g["year"] = y
        rows.append(g)
        print(f"  {y}: {len(g)} days", flush=True)
        del cube, r24, p1, p24

    day = pd.concat(rows, ignore_index=True)
    day["max1h_in"] = day.max1h_mm / C.MM_PER_IN
    day["max24h_in"] = day.max24h_mm / C.MM_PER_IN
    out = os.path.join(C.OUT, "aorc_daily_basin_max.csv")
    day.to_csv(out, index=False, float_format="%.4f")
    print("wrote", out, flush=True)

    n = len(day)
    print(f"\n{n} Jun-Oct days, {day.year.min()}-{day.year.max()}")
    print(f"{'thresh (in/24h)':>16} {'days':>7} {'% of days':>10} "
          f"{'MRMS hrs w/ +-1d pad':>22}")
    for t in [0.05, 0.10, 0.25, 0.50, 1.00]:
        sel = day.max24h_in >= t
        # A +-1 day pad guarantees the full 24-hour window around each event.
        padded = sel | sel.shift(1, fill_value=False) | sel.shift(-1, fill_value=False)
        print(f"{t:>16.2f} {sel.sum():>7} {100*sel.mean():>9.1f}% "
              f"{padded.sum()*24:>22,}")


if __name__ == "__main__":
    main()
