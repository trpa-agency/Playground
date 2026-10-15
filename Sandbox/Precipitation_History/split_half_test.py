"""
Is the 1-hour hot-spot pattern real, or is it sampling noise?

A short record of convective extremes can produce a map that looks
structured but only records where individual thunderstorms happened to
land. The test: split the record in half, fit each half independently, and
see whether the two halves agree about which cells are the wet ones.

A pattern driven by terrain reproduces. A pattern driven by storm luck does
not. The 24-hour duration acts as the control -- orographic, so it should
reproduce well in both datasets.

Run:  python split_half_test.py
"""

import os

import numpy as np
import xarray as xr

import config as C
import tahoe_precip as T


def halves_corr(ams, mask):
    """Correlate per-cell means of the first and second half of the record."""
    n = ams.sizes["year"]
    a = ams.isel(year=slice(0, n // 2)).mean("year").values
    b = ams.isel(year=slice(n // 2, n)).mean("year").values
    ok = mask & np.isfinite(a) & np.isfinite(b)
    return float(np.corrcoef(a[ok], b[ok])[0, 1]), n // 2, n - n // 2


def main():
    print(f"{'dataset':<7} {'duration':<9} {'split':<11} "
          f"{'r between halves':>17}")
    for prefix in ("aorc", "mrms"):
        p = os.path.join(C.OUT, f"{prefix}_tahoe_extremes.nc")
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            print(f"{prefix}: no usable extremes file")
            continue
        ds = xr.open_dataset(p)
        mask = ds["in_basin"].values.astype(bool)
        for dur in ("1h", "24h"):
            r, n1, n2 = halves_corr(ds[f"ams_{dur}"], mask)
            print(f"{prefix.upper():<7} {dur:<9} {f'{n1}v{n2} yrs':<11} "
                  f"{r:>17.3f}")
        ds.close()

    print("\nA terrain-driven pattern reproduces between halves; a pattern "
          "made of storm luck does not.")


if __name__ == "__main__":
    main()
