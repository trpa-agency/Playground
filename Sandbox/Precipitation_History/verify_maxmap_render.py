"""
Render the twelve map layers straight out of the web page's embedded payload.

This is a check on the payload, not on the styling: it walks the same row/col
indexing the browser uses, so a north-south flip or a bad bounds calculation
shows up immediately as an upside-down or displaced basin. Numeric tests
cannot catch that; a picture can.

Writes: data/processed/mrms_maxmap_verify.png

Run:  python verify_maxmap_render.py
"""

import io
import json
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import ListedColormap, BoundaryNorm

import config as C

HTML = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "tahoe_mrms_maxmap.html")
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
        "#256abf", "#184f95", "#0d366b"]


def payload():
    h = io.open(HTML, encoding="utf-8").read()
    return json.loads(re.search(r"const DATA = (\{.*?\});\n", h, re.S).group(1))


def main():
    d = payload()
    nx, ny, S, ND = d["nx"], d["ny"], d["scale"], d["nodata"]
    B = d["bounds"]
    # Row 0 is the north edge, exactly as the page's cellAt() assumes.
    extent = [B["west"], B["east"], B["south"], B["north"]]

    fig, axes = plt.subplots(2, 6, figsize=(21, 8))
    for r, dur in enumerate(("1h", "24h")):
        edges = [0] + [v for v in d["breaks"][dur] if v is not None]
        edges = edges + [max(edges) * 3]
        cmap = ListedColormap(RAMP)
        norm = BoundaryNorm(edges, cmap.N)

        for c, p in enumerate(d["periods"]):
            L = d["layers"][f"{dur}|{p['key']}"]
            g = np.array(L["g"], dtype="float64").reshape(ny, nx)
            g = np.where(g == ND, np.nan, g / S)          # mm

            ax = axes[r, c]
            im = ax.imshow(g, extent=extent, origin="upper", cmap=cmap,
                           norm=norm, interpolation="nearest")
            for ring in d["boundary"]:
                a = np.asarray(ring)
                ax.plot(a[:, 0], a[:, 1], color="k", lw=0.8)

            ax.set_title(f"{'1-hour' if dur == '1h' else '24-hour'} · "
                         f"{p['label']}\nmax {np.nanmax(g)/C.MM_PER_IN:.2f} in",
                         fontsize=9)
            ax.set_xticks([]); ax.set_yticks([])
            ax.set_aspect(1.0 / np.cos(np.deg2rad(39.1)))

    fig.suptitle(f"Payload render check — MRMS record rainfall, "
                 f"{d['seasons']} (row 0 = north edge)", fontsize=13)
    fig.tight_layout(rect=[0, 0, 1, 0.95])
    out = os.path.join(C.OUT, "mrms_maxmap_verify.png")
    fig.savefig(out, dpi=110)
    print("wrote", out, flush=True)


if __name__ == "__main__":
    main()
