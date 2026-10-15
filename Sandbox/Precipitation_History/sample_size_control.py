"""
Sample-size control for the split-half test.

MRMS has 11 seasons where AORC has 20, and a shorter record is noisier for
free. Restricting AORC to exactly the same 11 seasons makes the two
directly comparable, so any remaining gap in split-half reproducibility is
a property of the data rather than of the record length.

Run:  python sample_size_control.py
"""

import os

import numpy as np
import xarray as xr

import config as C
from split_half_test import halves_corr


def main():
    a = xr.open_dataset(os.path.join(C.OUT, "aorc_tahoe_extremes.nc"))
    m = xr.open_dataset(os.path.join(C.OUT, "mrms_tahoe_extremes.nc"))

    shared = sorted(set(int(y) for y in m.year.values)
                    & set(int(y) for y in a.year.values))
    a11 = a.sel(year=shared)
    m11 = m.sel(year=shared)

    print(f"matched on {len(shared)} shared seasons: "
          f"{shared[0]}-{shared[-1]}\n")
    print(f"{'dataset':<10} {'duration':<9} {'split':<11} "
          f"{'r between halves':>17}")

    for tag, ds in ((f"AORC-{len(shared)}", a11), ("MRMS", m11)):
        mask = ds["in_basin"].values.astype(bool)
        for dur in ("1h", "24h"):
            r, n1, n2 = halves_corr(ds[f"ams_{dur}"], mask)
            print(f"{tag:<10} {dur:<9} {f'{n1}v{n2} yrs':<11} {r:>17.3f}")

    # For reference, the full 20-season AORC result.
    mask = a["in_basin"].values.astype(bool)
    print()
    for dur in ("1h", "24h"):
        r, n1, n2 = halves_corr(a[f"ams_{dur}"], mask)
        print(f"{'AORC-20':<10} {dur:<9} {f'{n1}v{n2} yrs':<11} {r:>17.3f}")


if __name__ == "__main__":
    main()
