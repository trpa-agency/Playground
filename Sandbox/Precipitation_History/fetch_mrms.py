"""
Pull MRMS gauge-corrected hourly QPE for the Tahoe basin box, June-October.

Sources, in order of preference for a given date:
  * s3://noaa-mrms-pds  (2020-10-14 onward)  - fast, parallel-friendly
  * Iowa State mtarchive (2015 onward)       - university mirror, throttled

Product continuity across the MRMS v11 -> v12 change (Oct 2020):
  <  2020-10-14 : GaugeCorr_QPE_01H
  >= 2020-10-14 : MultiSensor_QPE_01H_Pass2
Both are the gauge-corrected hourly QPE. In the Sierra, where radar beams
are blocked by terrain, the gauge-corrected fields are the only MRMS QPE
worth using -- radar-only QPE is badly biased here.

Each hourly CONUS GRIB2 is 3500x7000 at 0.01 deg; we decode it, keep the
~90x66 Tahoe window, and throw the rest away. Output is one NetCDF per
year-month so the job can resume after an interruption.

Run:  python fetch_mrms.py --years 2021 2022 --workers 8
"""

import argparse
import concurrent.futures as cf
import datetime as dt
import gzip
import io
import os
import sys
import tempfile
import time
import warnings

import numpy as np
import pandas as pd
import requests
import xarray as xr

import config as C

warnings.filterwarnings("ignore")

# MRMS CONUS grid constants (v11 and v12 share this grid).
MRMS_LAT0, MRMS_LON0, MRMS_D = 54.995, -129.995, 0.01
MRMS_NJ, MRMS_NI = 3500, 7000

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "TRPA-precip-analysis/1.0 (contact: TRPA GIS)"


def _window():
    """Row/col slices of the MRMS CONUS grid covering the Tahoe box.

    Latitude runs north -> south, so row 0 is the northernmost.
    """
    j0 = int(np.floor((MRMS_LAT0 - C.LAT_MAX) / MRMS_D))
    j1 = int(np.ceil((MRMS_LAT0 - C.LAT_MIN) / MRMS_D))
    i0 = int(np.floor((C.LON_MIN - MRMS_LON0) / MRMS_D))
    i1 = int(np.ceil((C.LON_MAX - MRMS_LON0) / MRMS_D))
    return j0, j1, i0, i1


J0, J1, I0, I1 = _window()
SUB_LATS = MRMS_LAT0 - np.arange(J0, J1) * MRMS_D
SUB_LONS = MRMS_LON0 + np.arange(I0, I1) * MRMS_D


def product_for(date):
    return C.MRMS_PROD_NEW if date.strftime("%Y%m%d") >= C.MRMS_V12_START \
        else C.MRMS_PROD_OLD


def urls_for(when):
    """Candidate URLs for one hourly file, best source first."""
    ymd = when.strftime("%Y%m%d")
    stamp = when.strftime("%Y%m%d-%H0000")
    prod = product_for(when)
    out = []
    if ymd >= C.MRMS_V12_START:
        out.append(
            f"https://{C.AWS_MRMS_BUCKET}.s3.amazonaws.com/CONUS/{prod}_00.00/"
            f"{ymd}/MRMS_{prod}_00.00_{stamp}.grib2.gz"
        )
    out.append(
        f"{C.MTARCHIVE}/{when:%Y/%m/%d}/mrms/ncep/{prod}/"
        f"{prod}_00.00_{stamp}.grib2.gz"
    )
    return out


def decode_window(raw_gz):
    """Decompress a GRIB2 message and return the Tahoe window in mm."""
    import eccodes

    data = gzip.decompress(raw_gz)
    h = eccodes.codes_new_from_message(data)
    try:
        vals = eccodes.codes_get_values(h)
    finally:
        eccodes.codes_release(h)

    grid = vals.reshape(MRMS_NJ, MRMS_NI)[J0:J1, I0:I1]
    # MRMS flags no-coverage as -3 and missing as -999.
    return np.where(grid < 0, np.nan, grid).astype("float32")


def fetch_hour(when, retries=3):
    for url in urls_for(when):
        for attempt in range(retries):
            try:
                r = SESSION.get(url, timeout=90)
                if r.status_code == 404:
                    break                      # try the next source
                r.raise_for_status()
                return when, decode_window(r.content)
            except Exception:
                if attempt == retries - 1:
                    break
                time.sleep(1.5 * (attempt + 1))
    return when, None


def hours_in_month(year, month):
    start = dt.datetime(year, month, 1)
    end = (start + dt.timedelta(days=32)).replace(day=1)
    now = dt.datetime.utcnow() - dt.timedelta(days=1)
    end = min(end, now)
    n = int((end - start).total_seconds() // 3600)
    return [start + dt.timedelta(hours=k) for k in range(max(n, 0))]


def storm_days(csv_path, threshold_in, pad_days=1):
    """Set of local dates worth pulling MRMS for.

    Days are flagged from the AORC record, which is already cached locally,
    because decoding an MRMS CONUS GRIB2 costs seconds and the overwhelming
    majority of Jun-Oct hours here are dry. The threshold is deliberately
    low and each flagged day is padded, so the screen keeps every event that
    could matter to a 1-hour or 24-hour maximum.
    """
    day = pd.read_csv(csv_path, parse_dates=["date"])
    hit = day.loc[day.max24h_in >= threshold_in, "date"]
    keep = set()
    for d in hit:
        for k in range(-pad_days, pad_days + 1):
            keep.add((d + pd.Timedelta(days=k)).date())
    return keep


def fetch_month(year, month, workers=8, overwrite=False, keep_days=None):
    """Fetch one month. Hours on days the screen ruled out are stored as 0.

    The month file always carries a gap-free hourly axis plus an
    `hour_status` flag (0 fetched, 1 screened dry, 2 fetch failed) so that
    a deliberately skipped hour is never confused with a data outage.
    """
    out = os.path.join(C.INTERIM, f"mrms_tahoe_{year}{month:02d}.nc")
    if os.path.exists(out) and not overwrite:
        return out, "cached", 0

    hours = hours_in_month(year, month)
    if not hours:
        return None, "no hours (future)", 0

    if hours[0].strftime("%Y%m%d") < C.MRMS_V12_START:
        # mtarchive is a university mirror; stay polite on the pre-2020 years
        # that can only come from there.
        workers = min(workers, 6)

    if keep_days is None:
        wanted = hours
    else:
        # Screening is done on local dates, so shift the UTC stamp before
        # testing membership.
        wanted = [h for h in hours
                  if (pd.Timestamp(h, tz="UTC").tz_convert(C.LOCAL_TZ).date())
                  in keep_days]

    grids, failed = {}, set()
    t0 = time.time()
    if wanted:
        with cf.ThreadPoolExecutor(max_workers=workers) as ex:
            for when, g in ex.map(fetch_hour, wanted):
                if g is None:
                    failed.add(when)
                else:
                    grids[when] = g

    if wanted and not grids:
        return None, "NO DATA", len(wanted)

    ny, nx = (J1 - J0), (I1 - I0)
    stack = np.zeros((len(hours), ny, nx), dtype="float32")
    status = np.ones(len(hours), dtype="int8")          # default: screened dry
    for k, h in enumerate(hours):
        if h in grids:
            stack[k] = grids[h]
            status[k] = 0
        elif h in failed:
            stack[k] = np.nan
            status[k] = 2

    ds = xr.Dataset(
        {"precip_mm": (("time", "latitude", "longitude"), stack),
         "hour_status": ("time", status)},
        coords={"time": pd.DatetimeIndex(hours),
                "latitude": SUB_LATS, "longitude": SUB_LONS},
    )
    ds["precip_mm"].attrs = {
        "units": "mm", "long_name": "Hourly total precipitation",
        "source": f"NOAA MRMS {product_for(hours[0])}",
        "accumulation": "1 hour, ending at the timestamp", "time_zone": "UTC"}
    ds["hour_status"].attrs = {
        "flag_values": "0,1,2",
        "flag_meanings": "fetched screened_dry fetch_failed"}
    ds.attrs["screened"] = "yes" if keep_days is not None else "no"

    ds.to_netcdf(out, encoding={
        "precip_mm": {"zlib": True, "complevel": 4, "dtype": "float32"}})
    return out, (f"{len(grids)}/{len(wanted)} fetched, "
                 f"{len(hours)-len(wanted)} screened dry, "
                 f"{time.time()-t0:.0f}s"), len(failed)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--years", type=int, nargs="*", default=C.MRMS_YEARS)
    ap.add_argument("--months", type=int, nargs="*", default=list(C.SEASON_MONTHS))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--storm-days", default=os.path.join(
        C.OUT, "aorc_daily_basin_max.csv"),
        help="AORC daily screen CSV; pass 'none' to fetch every hour")
    ap.add_argument("--threshold", type=float, default=0.05,
                    help="basin-max 24-hour depth (in) that flags a storm day")
    args = ap.parse_args()

    keep = None
    if args.storm_days.lower() != "none":
        keep = storm_days(args.storm_days, args.threshold)
        print(f"screen: {len(keep)} storm days at >= {args.threshold} in/24h",
              flush=True)

    print(f"MRMS window rows {J0}:{J1} cols {I0}:{I1} "
          f"-> {J1-J0} x {I1-I0} cells", flush=True)

    total_failed = 0
    for y in args.years:
        for m in args.months:
            try:
                path, note, nfail = fetch_month(y, m, workers=args.workers,
                                                overwrite=args.overwrite,
                                                keep_days=keep)
                total_failed += nfail
                print(f"{y}-{m:02d}  {note}", flush=True)
            except Exception as e:
                print(f"{y}-{m:02d}  FAILED {type(e).__name__}: {e}", flush=True)
    print(f"done; {total_failed} hours failed to fetch", flush=True)


if __name__ == "__main__":
    main()
