"""
Shared configuration for the Tahoe Basin heavy-rainfall analysis.

Two gridded precipitation datasets are used, for different reasons:

  AORC  - NOAA Analysis of Record for Calibration, v1.1, 1-km hourly.
          1979-2025. This is the only 1-km hourly product that actually
          spans 20 years, so it carries the long-record return-period work.

  MRMS  - Multi-Radar Multi-Sensor gauge-corrected QPE, 1-km hourly.
          2015-present only (MRMS did not exist before ~2014). Used for
          the modern radar-era record, at the user's request.

Both are on ~1-km lat/lon grids, so the two can be compared cell to cell
after a nearest-neighbour regrid.
"""

import os

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
RAW = os.path.join(DATA, "raw")
INTERIM = os.path.join(DATA, "interim")
OUT = os.path.join(DATA, "processed")
BOUNDARY = os.path.join(DATA, "boundary", "trpa_boundary.geojson")

for _d in (DATA, RAW, INTERIM, OUT):
    os.makedirs(_d, exist_ok=True)

# ---------------------------------------------------------------------
# Analysis domain
# ---------------------------------------------------------------------
# The TRPA regulatory boundary spans lon -120.252..-119.877, lat 38.704..39.325.
# We pull a slightly larger box so the surrounding ridgelines (where the
# orographic maxima actually sit) are included and so edge cells are not
# clipped by the boundary itself.
LON_MIN, LON_MAX = -120.35, -119.80
LAT_MIN, LAT_MAX = 38.65, 39.40

# ---------------------------------------------------------------------
# Season
# ---------------------------------------------------------------------
# "June through October", evaluated in local (Pacific) time. Data are
# fetched with a buffer on each end so that 24-hour accumulation windows
# straddling the season boundary are complete before trimming.
SEASON_MONTHS = (6, 7, 8, 9, 10)
LOCAL_TZ = "America/Los_Angeles"

# ---------------------------------------------------------------------
# Record lengths
# ---------------------------------------------------------------------
AORC_YEARS = list(range(2006, 2026))   # 20 complete Jun-Oct seasons
MRMS_YEARS = list(range(2015, 2027))   # full MRMS era; 2026 partial

# ---------------------------------------------------------------------
# MRMS product names change at the v11 -> v12 transition (Oct 2020).
# GaugeCorr_QPE_01H is the pre-v12 analogue of MultiSensor_QPE_01H_Pass2:
# both are the gauge-corrected hourly QPE, which is what we want in a
# region where radar-only QPE is unreliable.
# ---------------------------------------------------------------------
MRMS_V12_START = "20201014"            # first date present in noaa-mrms-pds
MRMS_PROD_NEW = "MultiSensor_QPE_01H_Pass2"
MRMS_PROD_OLD = "GaugeCorr_QPE_01H"

AWS_MRMS_BUCKET = "noaa-mrms-pds"
MTARCHIVE = "https://mtarchive.geol.iastate.edu"
AORC_BUCKET = "noaa-nws-aorc-v1-1-1km"

# Thresholds used for exceedance-frequency mapping (inches).
# 1-hour thresholds bracket the NOAA Atlas 14 2-yr..100-yr range for the
# Tahoe area; 24-hour likewise.
THRESH_01H_IN = [0.10, 0.25, 0.50, 0.75, 1.00]
THRESH_24H_IN = [0.50, 1.00, 1.50, 2.00, 3.00]

MM_PER_IN = 25.4
