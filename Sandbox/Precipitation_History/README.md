

## Grid registration (read before doing raster math)

The three sources do **not** share a grid, even though two of them have the
same cell size:

| Source | Cell size | Registration |
|---|---|---|
| AORC | 1/120 deg | reference grid used for all combined products |
| Atlas 14 | 1/120 deg | offset ~0.9 cells (**~840 m**) in latitude from AORC |
| MRMS | 0.01 deg | different grid entirely (76x56 over this box) |

Overlaying the *native* rasters and differencing them in ArcGIS would be
quietly wrong. `build_combined.py` snaps Atlas 14 and MRMS onto the AORC grid
by nearest neighbour and writes `tahoe_combined_extremes.nc`,
`tahoe_combined_cells.csv`, and matching GeoTIFFs -- use those for any
cross-source comparison. The per-source folders keep each product on its
native grid for reference.

Latitude order is another trap: AORC ascends south to north, while both the
Atlas 14 ASCII grids and MRMS run north to south. Everything written by this
pipeline is normalised to ascending latitude; raw interim MRMS files are not.

## Findings

### Which dataset to use for which duration

Measured against NOAA Atlas 14 (annual-maximum series) across the 2,004
in-basin cells. "Level" is the median ratio of our return level to Atlas 14;
"pattern" is the spatial correlation, which is what matters for a hot-spot map.

| Source | Duration | Level | Pattern |
|---|---|---|---|
| AORC | 24-hour | 0.70-0.80 (10-100 yr) | **0.84** |
| MRMS | 24-hour | 0.61-0.69 | 0.61 |
| AORC | 1-hour | **0.38-0.43** | 0.66-0.87 |
| MRMS | 1-hour | **0.83-0.89** | **0.23 -> 0.06 -> -0.03** |

Read the 1-hour rows together: the two datasets fail in opposite directions.

* **AORC damps short-duration intensity.** Its 1-hour depths are ~40% of
  Atlas 14 at *every* return period. A seasonal restriction would bite hardest
  at short return periods and ease off at long ones -- which is exactly what
  the 24-hour row does (0.43 -> 0.80). The flat 1-hour ratio is the signature
  of temporal disaggregation smoothing sub-daily peaks, not of season sampling.
* **MRMS gets the magnitude right and the map wrong.** Its peak-hour depths
  land at 83-89% of Atlas 14 -- essentially correct for a Jun-Oct-only sample
  -- because radar genuinely resolves convective bursts. But its spatial
  correlation with Atlas 14 decays to zero as return period rises.

### The 1-hour pattern is storm luck, not terrain

Split-half test: fit each half of the record independently and ask whether the
two halves agree on which cells are wet. Controlled for record length by
restricting AORC to MRMS's exact 11 seasons and the same 5v6 split.

| Dataset | Split | 1-hour | 24-hour |
|---|---|---|---|
| AORC (2015-2025) | 5v6 | 0.848 | 0.875 |
| MRMS (2015-2025) | 5v6 | **0.217** | 0.471 |
| AORC (2006-2025) | 10v10 | 0.731 | 0.891 |

MRMS's 1-hour pattern does not reproduce, and the sample-size control rules out
record length as the explanation. Eleven seasons of convective extremes record
*where individual thunderstorms happened to land*. Atlas 14 uses regional
frequency analysis -- pooling across many stations -- precisely to suppress that
noise.

AORC's high 1-hour reproducibility is not evidence that it is right: a smooth
climatology-derived field reproduces whether or not its magnitudes are correct,
and we know its magnitudes are 40% low.

**Practical recommendation**

| Question | Use |
|---|---|
| Where are 24-hour extremes worst? | **AORC** (`aorc_gis/rl_24h_*.tif`) |
| What 1-hour depth to design to? | **Atlas 14** (`atlas14_pds_gis/a14_1h_*.tif`) |
| Do intense 1-hour bursts occur here? | **MRMS** (magnitudes, storm catalogue) |
| Where are 1-hour bursts worst? | **No gridded product supports this** |

### Where heavy rain concentrates (24-hour, AORC, 20 seasons)

* Absolute depth peaks on the Sierra crest near Desolation Wilderness / Echo
  Summit (about 38.91-38.98 N, -120.13 to -120.16), roughly 2.4x the basin
  median, driven by October atmospheric rivers -- Oct 2021, Oct 2010, Oct 2016.
* Depth alone is largely climatology: return levels correlate 0.95-0.97 with
  mean seasonal precipitation, so a map of them mostly restates the orographic
  pattern.
* **Flashiness** (1-hour divided by 24-hour depth) is the independent signal --
  weakly *anti*-correlated with wetness (r = -0.20). It peaks on the **east
  shore and Carson Range** (Stateline, Zephyr Cove, Incline) at ~0.16 versus
  ~0.098 on the west crest: drier places whose design event is proportionally a
  short burst, and which is where the basin's impervious surface sits.

### MRMS caveats

* Record is 2015-2025 and spans the v11 to v12 product change (Oct 2020),
  `GaugeCorr_QPE_01H` before, `MultiSensor_QPE_01H_Pass2` after.
* Fetched on storm days only (17,192 of 17,215 wanted hours, 99.87% success);
  non-storm hours are stored as zero. Extremes and threshold exceedances are
  unaffected, but **seasonal totals and wet-hour counts are biased low** and
  are flagged as such in the NetCDF attributes.
* The basin is radar-poor -- KRGX, KDAX and KBBX are all blocked or overshooting
  over the Sierra crest. MRMS 24-hour depths run ~11% below AORC and correlate
  only 0.61 with Atlas 14, consistent with beam blockage suppressing orographic
  totals.


## Record-rainfall explorer (`tahoe_mrms_maxmap.html`)

A single self-contained page — open it directly, no server. MRMS only, so the
whole thing is one consistent product across all twelve layers.

**Layers** — record 1-hour and 24-hour rainfall per cell, for the whole
Jun–Oct season and for each calendar month: 2 durations x 6 periods.
Each cell also carries **when** its record happened, which is what makes the
scatter of convective maxima visible rather than just asserted.

**Controls** — duration, period, units (in/mm), basemap, colour scale, clip to
the TRPA boundary, light/dark theme. Hovering reads out the depth and its date;
clicking pins a cell and draws its month-by-month profile. Every layer can be
exported as CSV grid, GeoJSON points, or one long CSV. Zoom sits bottom-left so
it does not cover the hover readout.

**Charts tab** — six graphs of basin-wide records (the wettest in-basin cell
for each period), in whichever unit the toolbar is set to:

| Chart | Shows |
|---|---|
| Record by calendar month, 1-hour and 24-hour | the record across all seasons beside the median year, so a one-off event is distinguishable from a typical one |
| Month x year heatmap, 1-hour and 24-hour | every month of every season; hover a cell for the exact date |
| Season maximum by year, 1-hour and 24-hour | the largest single hour / rolling day of each Jun-Oct season |

**Each side-by-side pair shares one y axis** (0-8 in over this record). The
1-hour bars are therefore short — that is the point. The two durations differ
by roughly a factor of three, and scaling each panel to its own maximum would
make a 0.50 in hour in October look as impressive as a 6.76 in day. Every bar
is labelled with its value, so nothing is lost to the short bars.

The two heatmaps are the exception: their y axis is the year, already shared,
so **colour** is scaled within each heatmap. Sharing colour across them would
flatten the entire 1-hour panel into the palest class.

Three year-months are blank rather than zero — **2018-09, 2020-10, 2024-06**.
The storm-day screen found no qualifying day in them, so no MRMS hours were
fetched; the fetcher wrote zeros that were never observed. Plotting those as a
measured 0.00 would be wrong, so they are carried as missing. The map layers
are unaffected, since each pools ten or eleven other seasons.

**Two colour-scale modes, and the choice matters.** *Shared* puts every period
on one ramp per duration, so the months are directly comparable — this is the
default and the reason the monthly maps exist. But October's 24-hour field
(2.5–7.8 in) barely overlaps the summer months' (0.4–2 in), so on a shared
ramp October reads as one flat dark block. *Relative* re-classes each map on
its own quantiles to expose internal structure. Neither is "right"; they answer
different questions.

Rebuild with `python mrms_maxima.py && python build_maxmap.py`.

### What the monthly maps show

The seasonal split is sharp, and it runs in opposite directions for the two
durations (in-basin values):

| Period | 1-hour max | 24-hour max |
|---|---|---|
| June | 1.91 in | 2.79 in |
| July | **2.06 in** | 2.47 in |
| August | 1.83 in | 2.51 in |
| September | 1.18 in | 2.18 in |
| October | **0.50 in** | **6.76 in** |

July's worst hour is **four times** October's, while October's worst day is
**2.7 times** July's. These are two unrelated hazards sharing one season:
summer convective bursts, and autumn atmospheric rivers.

The year-by-year view shows how lumpy this is. October 2021 alone reaches
**6.76 in** over 24 hours — more than double any other October in the record,
and more than any month of any season. Strip that one atmospheric river out and
October looks like an unremarkable month. Eleven seasons is a short record to
hang a design number on.

### The lake suppresses summer convection

Median record depth over the lake surface versus in-basin land:

| Duration / month | Lake | Land | Land ÷ lake |
|---|---|---|---|
| 1-hour, June | 0.21 in | 0.30 in | **1.43x** |
| 1-hour, July | 0.45 in | 0.60 in | **1.33x** |
| 1-hour, August | 0.48 in | 0.67 in | **1.40x** |
| 1-hour, September | 0.80 in | 0.85 in | 1.06x |
| 1-hour, October | 0.30 in | 0.30 in | **0.97x** |

Land out-rains the lake by a third to a half during the convective months, and
the gap closes completely in October. October is the useful control here: it is
frontal rather than convective, and a radar-geometry artifact would not
politely disappear in one month. The signal is consistent with cold water
stabilising the boundary layer and suppressing convection over the lake.

For planning this means the summer 1-hour hazard is a **shoreline-and-uphill**
problem, not a lake-centred one — and the wettest single hour in the record
(3.26 in, 4 Aug 2022) sits on the north-east side, outside the TRPA line.

Note the earlier caveat still applies: MRMS 1-hour **magnitudes** are sound,
but with only 11 seasons the cell-by-cell *pattern* of convective maxima is
largely storm luck. Read these maps as "this much rain has fallen here", not
as "this is where it will fall next".
