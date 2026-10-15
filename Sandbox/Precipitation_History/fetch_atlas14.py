"""
Download NOAA Atlas 14 Volume 6 precipitation-frequency grids for the
durations this study cares about, and clip them to the Tahoe box.

Atlas 14 is the published design standard for this region. It is used here
two ways: as an independent check on the AORC- and MRMS-derived return
levels, and as a deliverable in its own right, since it is what a TRPA
drainage review would actually cite.

The regional ASCII grids cover the whole Southwest, so each is streamed,
unzipped, and cropped before anything is written.

Run:  python fetch_atlas14.py
"""

import io
import os
import zipfile

import numpy as np
import requests
import xarray as xr

import config as C

BASE = "https://hdsc.nws.noaa.gov/pub/hdsc/data/sw"

# (duration code in the filename, label used in our outputs)
DURATIONS = [("60m", "1h"), ("24h", "24h")]
RETURNS = [2, 5, 10, 25, 50, 100]


def read_asc(text):
    """Parse an ESRI ASCII grid into (array, lons, lats)."""
    head = {}
    lines = text.splitlines()
    n = 0
    for line in lines:
        parts = line.split()
        if len(parts) == 2 and not parts[0].lstrip("-").replace(".", "").isdigit():
            head[parts[0].lower()] = float(parts[1])
            n += 1
        else:
            break

    ncols, nrows = int(head["ncols"]), int(head["nrows"])
    xll, yll, cell = head["xllcorner"], head["yllcorner"], head["cellsize"]
    nodata = head.get("nodata_value", -9999)

    arr = np.fromstring(" ".join(lines[n:]), sep=" ", dtype="float64")
    arr = arr.reshape(nrows, ncols)
    arr = np.where(arr == nodata, np.nan, arr)

    # ASCII grids are written north row first.
    lons = xll + cell * (np.arange(ncols) + 0.5)
    lats = yll + cell * (np.arange(nrows)[::-1] + 0.5)
    return arr, lons, lats


def fetch_one(ari, dur_code, series="pds"):
    # The plain grids are partial-duration series (what design guidance
    # normally cites); the _ams grids are annual-maximum series, which is
    # what our own Gumbel fits produce and therefore the fair comparison.
    suffix = "a_ams" if series == "ams" else "a"
    url = f"{BASE}/sw{ari}yr{dur_code}{suffix}.zip"
    r = requests.get(url, timeout=300)
    r.raise_for_status()
    zf = zipfile.ZipFile(io.BytesIO(r.content))
    name = [n for n in zf.namelist() if n.lower().endswith(".asc")][0]
    return read_asc(zf.read(name).decode("latin-1"))


def main(series="pds"):
    out = {}
    coords = None
    for dur_code, dur_lbl in DURATIONS:
        for ari in RETURNS:
            arr, lons, lats = fetch_one(ari, dur_code, series)

            # Atlas 14 depths are published in thousandths of an inch.
            arr = arr / 1000.0

            jx = np.where((lons >= C.LON_MIN) & (lons <= C.LON_MAX))[0]
            jy = np.where((lats >= C.LAT_MIN) & (lats <= C.LAT_MAX))[0]
            sub = arr[np.ix_(jy, jx)]
            sl, sla = lons[jx], lats[jy]

            if coords is None:
                coords = {"latitude": sla, "longitude": sl}
            out[f"a14_{dur_lbl}_{ari}yr"] = (("latitude", "longitude"), sub)
            print(f"  {dur_lbl} {ari:>3}yr  {sub.shape}  "
                  f"{np.nanmin(sub):.2f}-{np.nanmax(sub):.2f} in", flush=True)

    ds = xr.Dataset(out, coords=coords)
    # ESRI ASCII grids are written north row first, so latitude comes out
    # descending. AORC and MRMS both use ascending latitude; match them so
    # the three datasets align by coordinate without any flipping.
    ds = ds.sortby("latitude")
    for v in ds.data_vars:
        ds[v].attrs = {"units": "in", "source": "NOAA Atlas 14 Vol 6 v2",
                       "series": "annual maximum" if series == "ams"
                       else "partial duration"}
    ds.attrs["source"] = "NOAA Atlas 14 Volume 6 (Southwest), version 2"
    ds.attrs["series"] = series

    path = os.path.join(C.OUT, f"atlas14_tahoe_{series}.nc")
    ds.to_netcdf(path)
    print("wrote", path, flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", choices=["pds", "ams"], default="pds")
    main(ap.parse_args().series)
