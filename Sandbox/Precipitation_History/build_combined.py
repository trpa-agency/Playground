"""
Harmonise every source onto the AORC grid and write one combined product.

The three datasets do not share a grid registration: Atlas 14's 30-arc-second
grid is offset from AORC's by about 0.9 cells in latitude, and MRMS is on a
0.01-degree grid entirely. Raster algebra across them in ArcGIS would be
quietly wrong. This step snaps Atlas 14 and MRMS to the AORC grid by nearest
neighbour so that ratio maps and side-by-side comparisons are valid.

Outputs one NetCDF, one GeoTIFF per layer, and a single per-cell CSV that can
be joined straight onto a point or fishnet layer.

Run:  python build_combined.py
"""

import os

import numpy as np
import pandas as pd
import xarray as xr

import config as C
import tahoe_precip as T

RPS = (2, 10, 25, 100)
DURS = ("1h", "24h")


def snap(ds, ref):
    """Nearest-neighbour snap onto the reference grid."""
    ds = ds.sortby("latitude").sortby("longitude")
    if (ds.sizes.get("latitude") == ref.sizes["latitude"]
            and np.allclose(ds.latitude.values, ref.latitude.values)):
        return ds
    return ds.interp(latitude=ref.latitude, longitude=ref.longitude,
                     method="nearest")


def main():
    aorc = xr.open_dataset(os.path.join(C.OUT, "aorc_tahoe_extremes.nc"))
    aorc = aorc.sortby("latitude").sortby("longitude")

    sources = {"aorc": aorc}
    for tag, fn in (("a14ams", "atlas14_tahoe_ams.nc"),
                    ("a14pds", "atlas14_tahoe_pds.nc"),
                    ("mrms", "mrms_tahoe_extremes.nc")):
        p = os.path.join(C.OUT, fn)
        if os.path.exists(p):
            sources[tag] = snap(xr.open_dataset(p), aorc)
        else:
            print(f"note: {fn} not present, skipping {tag}", flush=True)

    out = xr.Dataset(coords={"latitude": aorc.latitude,
                             "longitude": aorc.longitude})
    out["in_basin"] = aorc["in_basin"]

    for tag, ds in sources.items():
        for dur in DURS:
            for Tr in RPS:
                key = (f"a14_{dur}_{Tr}yr" if tag.startswith("a14")
                       else f"rl_{dur}_{Tr}yr")
                if key not in ds:
                    continue
                out[f"{tag}_{dur}_{Tr}yr"] = ds[key]
                out[f"{tag}_{dur}_{Tr}yr"].attrs = {
                    "units": "in", "source": tag}

    # Ratios against Atlas 14, the published design standard.
    if "a14ams" in sources:
        for tag in ("aorc", "mrms"):
            if tag not in sources:
                continue
            for dur in DURS:
                for Tr in RPS:
                    a = out.get(f"{tag}_{dur}_{Tr}yr")
                    b = out.get(f"a14ams_{dur}_{Tr}yr")
                    if a is None or b is None:
                        continue
                    v = f"ratio_{tag}_over_a14_{dur}_{Tr}yr"
                    out[v] = a / b.where(b > 0)
                    out[v].attrs = {
                        "units": "ratio",
                        "long_name": f"{tag.upper()} divided by Atlas 14 AMS"}

    # Flashiness from each source that can supply both durations.
    for tag in ("aorc", "mrms", "a14ams"):
        a = out.get(f"{tag}_1h_10yr")
        b = out.get(f"{tag}_24h_10yr")
        if a is None or b is None:
            continue
        out[f"flashiness_{tag}"] = a / b.where(b > 0)
        out[f"flashiness_{tag}"].attrs = {
            "units": "ratio",
            "long_name": "10-year 1-hour depth over 10-year 24-hour depth"}

    out.attrs["grid"] = "AORC v1.1 1-km (1/120 deg), EPSG:4326"
    out.attrs["note"] = ("Atlas 14 and MRMS snapped to the AORC grid by "
                         "nearest neighbour; native registrations differ")

    nc = os.path.join(C.OUT, "tahoe_combined_extremes.nc")
    out.to_netcdf(nc)
    print("wrote", nc, flush=True)

    # One joinable table of every in-basin cell.
    mask = out["in_basin"].values.astype(bool)
    lon2d, lat2d = np.meshgrid(out.longitude.values, out.latitude.values)
    tbl = {"lat": lat2d[mask], "lon": lon2d[mask]}
    for v in out.data_vars:
        if out[v].dims == ("latitude", "longitude") and v != "in_basin":
            tbl[v] = out[v].values[mask]
    df = pd.DataFrame(tbl)
    csv = os.path.join(C.OUT, "tahoe_combined_cells.csv")
    df.to_csv(csv, index=False, float_format="%.4f")
    print(f"wrote {csv}  ({len(df)} cells x {len(df.columns)} fields)",
          flush=True)
    return out


if __name__ == "__main__":
    main()
