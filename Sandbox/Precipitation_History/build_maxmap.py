"""
Build the self-contained record-rainfall web map from mrms_maxima_tahoe.nc,
and export the same layers as GeoTIFFs.

Reads:   data/processed/mrms_maxima_tahoe.nc
Writes:  tahoe_mrms_maxmap.html          one file, no server, no build step
         data/processed/mrms_maxima_gis/ one GeoTIFF per layer

The page embeds every layer as JSON, so it works offline apart from the
basemap tiles. Depths are carried as tenths of a millimetre: MRMS reports
QPE to 0.1 mm, so integers are lossless here and roughly halve the payload
against floats.

Run:  python build_maxmap.py
"""

import datetime as dt
import json
import os
import re

import numpy as np
import xarray as xr

import config as C

HERE = os.path.dirname(os.path.abspath(__file__))
VENDOR = os.path.join(HERE, "vendor")
OUT_HTML = os.path.join(HERE, "tahoe_mrms_maxmap.html")
GIS = os.path.join(C.OUT, "mrms_maxima_gis")

SCALE = 10          # tenths of a mm
NODATA = -1
CELL_DEG = 0.01     # MRMS CONUS grid spacing

PERIODS = [("all", "Jun–Oct", "Jun–Oct"), ("6", "June", "Jun"),
           ("7", "July", "Jul"), ("8", "August", "Aug"),
           ("9", "September", "Sep"), ("10", "October", "Oct")]

# Class edges in inches, fixed per duration so all six periods share one
# scale -- letting each month rescale would make them all look alike.
#
# The edges are spaced on the pooled distribution rather than on round
# numbers, because both fields are strongly skewed and an even ramp
# saturates. The 24-hour field is close to bimodal: the summer months sit
# between 0.4 and 2 in, while October and the season maximum sit between
# 2.5 and 7.8 in, so the upper classes are stretched to keep both readable.
BREAKS_IN = {"1h":  [0.2, 0.3, 0.4, 0.6, 1.0, 1.5],
             "24h": [0.75, 1.0, 1.5, 2.5, 4.0, 6.0]}


# --------------------------------------------------------------- boundary
def rdp(points, eps):
    """Ramer-Douglas-Peucker simplification, to keep the embedded outline small."""
    if len(points) < 3:
        return points
    a, b = points[0], points[-1]
    dx, dy = b[0] - a[0], b[1] - a[1]
    den = (dx * dx + dy * dy) ** 0.5
    if den == 0:
        d = [((p[0] - a[0]) ** 2 + (p[1] - a[1]) ** 2) ** 0.5 for p in points]
    else:
        d = [abs(dy * (p[0] - a[0]) - dx * (p[1] - a[1])) / den for p in points]
    k = int(np.argmax(d))
    if d[k] <= eps:
        return [a, b]
    return rdp(points[:k + 1], eps)[:-1] + rdp(points[k:], eps)


def boundary_rings(eps=0.0004):
    with open(C.BOUNDARY) as fh:
        gj = json.load(fh)
    rings = []
    for feat in gj["features"]:
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" \
            else geom["coordinates"]
        for poly in polys:
            pts = [[round(float(x), 5), round(float(y), 5)]
                   for x, y in (p[:2] for p in poly[0])]
            rings.append(rdp(pts, eps))
    return rings


# ------------------------------------------------------------------- GIS
def export_tifs(ds, lats_north_first):
    import export_gis as EG

    os.makedirs(GIS, exist_ok=True)
    n = 0
    for dur in ("1h", "24h"):
        for key, label, _ in PERIODS:
            name = f"max_{dur}_{key}"
            EG.write_tif(os.path.join(GIS, f"{name}.tif"),
                         ds[name].values, ds.latitude.values,
                         ds.longitude.values, units="inches",
                         desc=f"MRMS record {dur} rainfall, {label}")
            EG.write_tif(os.path.join(GIS, f"{name}_basinclip.tif"),
                         np.where(ds["in_basin"].values, ds[name].values, np.nan),
                         ds.latitude.values, ds.longitude.values, units="inches",
                         desc=f"MRMS record {dur} rainfall, {label} "
                              f"(clipped to TRPA boundary)")
            n += 2
    rows = ["raster,units,meaning"]
    for dur in ("1h", "24h"):
        for key, label, _ in PERIODS:
            rows.append(f"max_{dur}_{key}.tif,inches,"
                        f"Largest {dur} rainfall observed in any {label} "
                        f"of {ds.attrs['seasons']}")
    with open(os.path.join(GIS, "DATA_DICTIONARY.csv"), "w") as fh:
        fh.write("\n".join(rows) + "\n")
    print(f"wrote {n} GeoTIFFs to {GIS}", flush=True)


# --------------------------------------------------------------- payload
def build_payload(ds):
    # xarray holds latitude ascending; the page indexes rows from the north
    # edge downward, matching the sibling hourly map, so flip here once.
    flip = ds.latitude.values[0] < ds.latitude.values[-1]
    lats = ds.latitude.values[::-1] if flip else ds.latitude.values
    lons = ds.longitude.values
    ny, nx = len(lats), len(lons)

    def oriented(name):
        a = ds[name].values
        return a[::-1] if flip else a

    basin2d = oriented("in_basin").astype(bool)

    layers = {}
    for dur in ("1h", "24h"):
        for key, _, _s in PERIODS:
            depth_in = oriented(f"max_{dur}_{key}").astype("float64")
            when = oriented(f"when_{dur}_{key}").astype("U16")

            mm = depth_in * C.MM_PER_IN
            q = np.where(np.isfinite(mm), np.rint(mm * SCALE), NODATA)
            q = q.astype("int32").ravel()

            # Occurrence stamps repeat heavily -- one storm sets the record
            # over many cells at once -- so intern them and store indices.
            flat = when.ravel()
            uniq, inv = np.unique(flat, return_inverse=True)
            table = [str(u) for u in uniq]
            inv = inv.astype("int32")
            blank = {i for i, u in enumerate(table) if not u.strip()}
            widx = np.where(q == NODATA, -1, inv)
            if blank:
                widx = np.where(np.isin(inv, list(blank)), -1, widx)

            # Per-layer quantile edges, for the "Relative" scale mode.
            # October's 24-hour range (2.5-7.8 in) barely overlaps the summer
            # months' (0.4-2 in), so one shared 7-class ramp cannot resolve
            # both; equal-count classes within a layer expose the structure
            # inside whichever month is being looked at.
            vals = mm[np.isfinite(mm) & (mm > 0) & basin2d]
            if vals.size > 40:
                edges = [float(np.quantile(vals, p))
                         for p in (1/7, 2/7, 3/7, 4/7, 5/7, 6/7)]
                # Collapse duplicate edges so a flat layer cannot produce
                # zero-width classes.
                ded = []
                for e in edges:
                    if not ded or e > ded[-1] + 1e-6:
                        ded.append(round(e, 3))
                edges = ded if len(ded) == 6 else None
            else:
                edges = None

            layers[f"{dur}|{key}"] = {
                "g": q.tolist(),
                "w": widx.astype("int32").tolist(),
                "wl": table,
                "b": edges,
            }

    in_basin = oriented("in_basin").astype("int8").ravel().tolist()

    # Basin-level series for the charts tab: one value per duration, year and
    # calendar month. Carried in the same tenths-of-a-mm units as the grids so
    # the page's unit conversion applies unchanged.
    series = None
    if "series_max_1h" in ds:
        def q2(name):
            a = ds[name].values * C.MM_PER_IN * SCALE
            return [[int(round(v)) if np.isfinite(v) else NODATA for v in row]
                    for row in a]
        series = {
            "years": [int(v) for v in ds.year.values],
            "months": [int(v) for v in ds.month.values],
            "max": {d: q2(f"series_max_{d}") for d in ("1h", "24h")},
            "med": {d: q2(f"series_med_{d}") for d in ("1h", "24h")},
            "when": {d: [[str(v) for v in row]
                         for row in ds[f"series_when_{d}"].values]
                     for d in ("1h", "24h")},
        }

    return {
        "product": "MRMS gauge-corrected hourly QPE",
        "source": ds.attrs.get("source", "NOAA MRMS"),
        "note": ds.attrs.get("note", ""),
        "seasons": ds.attrs.get("seasons", ""),
        "nSeasons": int(ds.attrs.get("n_seasons", 0)),
        "generated": dt.datetime.now(dt.timezone.utc)
                       .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "units": "mm", "scale": SCALE, "nodata": NODATA, "cellDeg": CELL_DEG,
        "nx": nx, "ny": ny,
        "bounds": {
            "north": float(lats[0] + CELL_DEG / 2),
            "south": float(lats[-1] - CELL_DEG / 2),
            "west": float(lons[0] - CELL_DEG / 2),
            "east": float(lons[-1] + CELL_DEG / 2),
        },
        "lats": [round(float(v), 4) for v in lats],
        "lons": [round(float(v), 4) for v in lons],
        "periods": [{"key": k, "label": l, "short": s} for k, l, s in PERIODS],
        # JSON has no Infinity; the page reads null as an open top class.
        "breaks": {d: [round(v * C.MM_PER_IN, 3) for v in BREAKS_IN[d]] + [None]
                   for d in BREAKS_IN},
        "layers": layers,
        "series": series,
        "inBasin": in_basin,
        "boundary": boundary_rings(),
    }


# -------------------------------------------------------------- assemble
def read_vendor(name):
    with open(os.path.join(VENDOR, name), encoding="utf-8") as f:
        return f.read()


def main():
    ds = xr.open_dataset(os.path.join(C.OUT, "mrms_maxima_tahoe.nc"))

    export_tifs(ds, None)

    payload = build_payload(ds)
    print(f"payload: {payload['ny']}x{payload['nx']} cells, "
          f"{len(payload['periods'])} periods x 2 durations", flush=True)

    css = read_vendor("leaflet.css")
    js = read_vendor("leaflet.js")
    # Leaflet's CSS references marker sprites we do not ship; the page uses
    # none, so strip the rules rather than leave dead requests behind.
    css = re.sub(r"url\((images/[^)]+)\)", "none", css)

    with open(os.path.join(HERE, "maxmap_template.html"), encoding="utf-8") as f:
        html = f.read()

    html = (html
            .replace("/*__LEAFLET_CSS__*/", css)
            .replace("/*__LEAFLET_JS__*/", js)
            .replace('"__DATA__"', json.dumps(payload, separators=(",", ":"))))

    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"wrote {OUT_HTML} ({os.path.getsize(OUT_HTML)/1e6:.2f} MB)",
          flush=True)


if __name__ == "__main__":
    main()
