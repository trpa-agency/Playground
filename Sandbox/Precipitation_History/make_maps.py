"""
Render the heavy-rainfall grids as map figures.

Produces, per dataset:
  <ds>_return_levels.png   1-hour and 24-hour depths at 2/10/25/100 years
  <ds>_exceedance.png      how often each intensity threshold is crossed
  <ds>_proneness.png       relative proneness plus the record-max fields

Run:  python make_maps.py --dataset aorc
"""

import argparse
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.colors import LinearSegmentedColormap

import config as C

# A sequential ramp that stays legible in print and for the common forms of
# colour-vision deficiency; avoids the rainbow banding that makes precip
# maps easy to misread.
PRECIP_CMAP = LinearSegmentedColormap.from_list(
    "precip", ["#f7fbff", "#c6dbef", "#6baed6", "#2171b5",
               "#08519c", "#54278f", "#3f007d"])
DIVERGE_CMAP = LinearSegmentedColormap.from_list(
    "prone", ["#4575b4", "#e0f3f8", "#fee090", "#f46d43", "#a50026"])


def boundary_rings():
    with open(C.BOUNDARY) as fh:
        gj = json.load(fh)
    rings = []
    for feat in gj["features"]:
        geom = feat["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" \
            else geom["coordinates"]
        for poly in polys:
            rings.append(np.asarray(poly[0], dtype=float)[:, :2])
    return rings


def draw(ax, ds, field, title, cmap=PRECIP_CMAP, vmin=None, vmax=None,
         units="in", rings=None):
    da = ds[field]
    vals = np.where(ds["in_basin"].values, da.values, np.nan)

    m = ax.pcolormesh(ds.longitude, ds.latitude, vals, cmap=cmap,
                      vmin=vmin, vmax=vmax, shading="nearest")
    for r in (rings or []):
        ax.plot(r[:, 0], r[:, 1], color="0.15", lw=0.9)

    ax.set_title(title, fontsize=9, pad=4)
    ax.set_aspect(1.0 / np.cos(np.deg2rad(39.1)))
    ax.set_xticks([]); ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)

    cb = plt.colorbar(m, ax=ax, fraction=0.046, pad=0.02)
    cb.ax.tick_params(labelsize=7)
    cb.set_label(units, fontsize=7)

    # Mark the wettest in-basin cell -- that is the point the reader is
    # looking for on a "where is it worst" map.
    if np.isfinite(vals).any():
        jy, jx = np.unravel_index(np.nanargmax(vals), vals.shape)
        ax.plot(ds.longitude[jx], ds.latitude[jy], marker="*", ms=9,
                mfc="#ffd400", mec="k", mew=0.6, zorder=5)
    return m


def figure(ds, fields, titles, out, suptitle, cmap=PRECIP_CMAP,
           share_scale=True, units="in", ncols=4):
    rings = boundary_rings()
    n = len(fields)
    nrows = int(np.ceil(n / ncols))
    fig, axes = plt.subplots(nrows, ncols,
                             figsize=(3.5 * ncols, 3.8 * nrows))
    axes = np.atleast_1d(axes).ravel()

    vmin = vmax = None
    if share_scale:
        stack = [np.where(ds["in_basin"].values, ds[f].values, np.nan)
                 for f in fields]
        vmin = float(np.nanmin(stack))
        vmax = float(np.nanmax(stack))

    for ax, f, t in zip(axes, fields, titles):
        draw(ax, ds, f, t, cmap=cmap, vmin=vmin, vmax=vmax, units=units,
             rings=rings)
    for ax in axes[n:]:
        ax.axis("off")

    fig.suptitle(suptitle, fontsize=12, y=0.995)
    fig.tight_layout(rect=[0, 0.01, 1, 0.97])
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print("wrote", out, flush=True)


def main(prefix):
    nc = os.path.join(C.OUT, f"{prefix}_tahoe_extremes.nc")
    ds = xr.open_dataset(nc)
    seasons = ds.attrs.get("seasons", "")
    n = ds.attrs.get("n_seasons", "")
    tag = f"{ds.attrs.get('dataset', prefix.upper())}  {seasons}  " \
          f"({n} Jun-Oct seasons)"

    for dur, lbl in (("1h", "1-hour"), ("24h", "24-hour")):
        figure(
            ds,
            [f"rl_{dur}_{T}yr" for T in (2, 10, 25, 100)],
            [f"{T}-year" for T in (2, 10, 25, 100)],
            os.path.join(C.OUT, f"{prefix}_return_levels_{dur}.png"),
            f"Tahoe Basin — {lbl} rainfall depth by return period\n{tag}",
        )

    th1 = C.THRESH_01H_IN
    figure(ds,
           [f"exc_1h_{t:g}in_per_season" for t in th1],
           [f"\u2265 {t:g} in/hr" for t in th1],
           os.path.join(C.OUT, f"{prefix}_exceedance_1h.png"),
           f"Tahoe Basin — hours per season exceeding a 1-hour intensity\n{tag}",
           cmap=PRECIP_CMAP, share_scale=False, units="hours/season", ncols=5)

    th24 = C.THRESH_24H_IN
    figure(ds,
           [f"exc_24h_{t:g}in_per_season" for t in th24],
           [f"\u2265 {t:g} in/24h" for t in th24],
           os.path.join(C.OUT, f"{prefix}_exceedance_24h.png"),
           f"Tahoe Basin — 24-hour windows per season exceeding a depth\n{tag}",
           cmap=PRECIP_CMAP, share_scale=False, units="windows/season", ncols=5)

    rings = boundary_rings()
    fig, axes = plt.subplots(1, 4, figsize=(14, 3.9))
    draw(axes[0], ds, "prone_index_1h",
         "Proneness index, 1-hour\n(10-yr depth / basin median)",
         cmap=DIVERGE_CMAP, units="\u00d7 median", rings=rings)
    draw(axes[1], ds, "prone_index_24h",
         "Proneness index, 24-hour\n(10-yr depth / basin median)",
         cmap=DIVERGE_CMAP, units="\u00d7 median", rings=rings)
    draw(axes[2], ds, "record_max_1h", "Record 1-hour depth", rings=rings)
    draw(axes[3], ds, "record_max_24h", "Record 24-hour depth", rings=rings)
    fig.suptitle(f"Tahoe Basin — where heavy rainfall concentrates\n{tag}",
                 fontsize=12, y=0.99)
    fig.tight_layout(rect=[0, 0.01, 1, 0.9])
    out = os.path.join(C.OUT, f"{prefix}_proneness.png")
    fig.savefig(out, dpi=160)
    plt.close(fig)
    print("wrote", out, flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default="aorc")
    main(ap.parse_args().dataset)
