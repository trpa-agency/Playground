# -*- coding: utf-8 -*-
"""
BikePedUpdate.pyt
ArcGIS Pro Python Toolbox — Bike & Pedestrian Counter Data Update

Designed for publishing as an ArcGIS Portal Geoprocessing Service so the
dashboard "Run Update" button can trigger an ETL run remotely.

ETL flow:
  1. Read Trafx daily CSV (wide: columns = counter names, rows = dates)
  2. Read Ecovision daily CSV (same wide format)
  3. Melt both to long format, normalize counter names, derive fields
  4. Load counter_id lookup from the Points feature layer (MapServer/5)
  5. Truncate the Counts feature layer table (MapServer/1 edit endpoint)
     and append all rows via the ArcGIS API for Python FeatureLayer.edit_features

Compatible with ArcGIS Pro 3.4 + arcpy + arcgis (ArcGIS API for Python 2.x).
"""

import arcpy
import os
import json
import traceback

# ---------------------------------------------------------------------------
# Station name normalisation — keep in sync with BikePedUpdate.py
# ---------------------------------------------------------------------------
STATION_LOOKUP = {
    # Trafx names → canonical counter names
    "SR 28 NB": "SR 28 NB",
    "SR 28 SB": "SR 28 SB",
    "Tunnel Creek Road": "Tunnel Creek Road",
    "Flume Trail": "Flume Trail",
    "Cave Rock": "Cave Rock",
    "Round Hill Pines": "Round Hill Pines",
    "Spooner Junction": "Spooner Junction",
    "Kingsbury North": "Kingsbury North",
    "Kingsbury South": "Kingsbury South",
    "Echo Lakes": "Echo Lakes",
    "Emerald Bay": "Emerald Bay",
    "Tahoe City": "Tahoe City",
    "Brockway Summit": "Brockway Summit",
    # Ecovision names → canonical counter names (add as needed)
    "TC_SB": "Tahoe City SB",
    "TC_NB": "Tahoe City NB",
}

SEASON_MAP = {
    1: "Winter",  2: "Winter",  3: "Off-Season",
    4: "Off-Season", 5: "Off-Season", 6: "Summer",
    7: "Summer",  8: "Summer",  9: "Summer",
    10: "Off-Season", 11: "Off-Season", 12: "Winter",
}


# ===========================================================================
class Toolbox:
    def __init__(self):
        self.label = "Bike Ped Counter Tools"
        self.alias = "BikePedTools"
        self.tools = [BikePedUpdate]


# ===========================================================================
class BikePedUpdate:
    """Update the Bike & Pedestrian counter database from Trafx/Ecovision CSVs."""

    def __init__(self):
        self.label = "Update Bike Ped Counts"
        self.description = (
            "Reads Trafx and Ecovision daily CSV exports, normalises and merges "
            "the data, then replaces all rows in the ArcGIS Online / Portal "
            "Counts feature layer table."
        )
        self.canRunInBackground = True

    # ------------------------------------------------------------------
    def getParameterInfo(self):
        params = []

        # 0 — Trafx CSV (file path OR URL)
        p0 = arcpy.Parameter(
            displayName="Trafx Daily CSV (file path or URL)",
            name="trafx_csv",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        p0.value = ""
        params.append(p0)

        # 1 — Ecovision CSV (file path OR URL)
        p1 = arcpy.Parameter(
            displayName="Ecovision Daily CSV (file path or URL)",
            name="ecovision_csv",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        p1.value = ""
        params.append(p1)

        # 2 — Points feature layer URL (for counter_id lookup)
        p2 = arcpy.Parameter(
            displayName="Points Feature Layer URL",
            name="points_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        p2.value = (
            "https://maps.trpa.org/server/rest/services/"
            "LTInfo_Monitoring/MapServer/5"
        )
        params.append(p2)

        # 3 — Counts feature layer URL (edit endpoint)
        p3 = arcpy.Parameter(
            displayName="Counts Feature Layer URL (edit endpoint)",
            name="counts_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        p3.value = (
            "https://maps.trpa.org/server/rest/services/"
            "LTInfo_Monitoring/MapServer/1"
        )
        params.append(p3)

        # 4 — Portal / AGOL URL
        p4 = arcpy.Parameter(
            displayName="Portal URL",
            name="portal_url",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        p4.value = arcpy.GetActivePortalURL() or "https://www.arcgis.com"
        params.append(p4)

        # 5 — Authentication mode
        p5 = arcpy.Parameter(
            displayName="Authentication Mode",
            name="auth_mode",
            datatype="GPString",
            parameterType="Required",
            direction="Input",
        )
        p5.filter.type = "ValueList"
        p5.filter.list = ["Pro (signed-in user)", "Token", "Username / Password"]
        p5.value = "Pro (signed-in user)"
        params.append(p5)

        # 6 — Token (optional, shown when auth_mode = Token)
        p6 = arcpy.Parameter(
            displayName="Token",
            name="token",
            datatype="GPStringHidden",
            parameterType="Optional",
            direction="Input",
        )
        params.append(p6)

        # 7 — Username (optional)
        p7 = arcpy.Parameter(
            displayName="Username",
            name="username",
            datatype="GPString",
            parameterType="Optional",
            direction="Input",
        )
        params.append(p7)

        # 8 — Password (optional)
        p8 = arcpy.Parameter(
            displayName="Password",
            name="password",
            datatype="GPStringHidden",
            parameterType="Optional",
            direction="Input",
        )
        params.append(p8)

        # 9 — Dry run (preview only, no writes)
        p9 = arcpy.Parameter(
            displayName="Dry Run (preview only — no data will be written)",
            name="dry_run",
            datatype="GPBoolean",
            parameterType="Optional",
            direction="Input",
        )
        p9.value = False
        params.append(p9)

        # 10 — Output summary (derived)
        p10 = arcpy.Parameter(
            displayName="Summary",
            name="summary",
            datatype="GPString",
            parameterType="Derived",
            direction="Output",
        )
        params.append(p10)

        return params

    # ------------------------------------------------------------------
    def isLicensed(self):
        return True

    # ------------------------------------------------------------------
    def updateParameters(self, parameters):
        auth_mode = parameters[5].valueAsText or ""
        parameters[6].enabled = auth_mode == "Token"
        parameters[7].enabled = auth_mode == "Username / Password"
        parameters[8].enabled = auth_mode == "Username / Password"

    # ------------------------------------------------------------------
    def updateMessages(self, parameters):
        auth_mode = parameters[5].valueAsText or ""
        if auth_mode == "Token" and not (parameters[6].valueAsText or "").strip():
            parameters[6].setWarningMessage("Token is required for Token auth mode.")
        if auth_mode == "Username / Password":
            if not (parameters[7].valueAsText or "").strip():
                parameters[7].setWarningMessage("Username is required.")
            if not (parameters[8].valueAsText or "").strip():
                parameters[8].setWarningMessage("Password is required.")

    # ------------------------------------------------------------------
    def execute(self, parameters, messages):
        try:
            import pandas as pd
        except ImportError:
            arcpy.AddError(
                "pandas is required. Install it in your ArcGIS Pro conda environment:\n"
                "  conda install pandas"
            )
            return

        try:
            from arcgis.gis import GIS
            from arcgis.features import FeatureLayer
        except ImportError:
            arcpy.AddError(
                "arcgis (ArcGIS API for Python) is required. Install via:\n"
                "  conda install arcgis"
            )
            return

        # ---- unpack parameters ----------------------------------------
        trafx_src    = parameters[0].valueAsText.strip()
        ecovision_src = parameters[1].valueAsText.strip()
        points_url   = parameters[2].valueAsText.strip()
        counts_url   = parameters[3].valueAsText.strip()
        portal_url   = parameters[4].valueAsText.strip()
        auth_mode    = parameters[5].valueAsText
        token        = (parameters[6].valueAsText or "").strip()
        username     = (parameters[7].valueAsText or "").strip()
        password     = (parameters[8].valueAsText or "").strip()
        dry_run      = bool(parameters[9].value)

        arcpy.SetProgressor("default", "Connecting to portal…")

        # ---- connect to GIS -------------------------------------------
        gis = _connect_gis(portal_url, auth_mode, token, username, password, messages)
        if gis is None:
            return

        arcpy.AddMessage(f"Connected as: {gis.properties.user.username if hasattr(gis, 'properties') else 'anonymous'}")

        # ---- read CSVs ------------------------------------------------
        arcpy.SetProgressor("default", "Reading Trafx CSV…")
        df_trafx = _read_csv(trafx_src, "trafx", messages)
        if df_trafx is None:
            return

        arcpy.SetProgressor("default", "Reading Ecovision CSV…")
        df_eco = _read_csv(ecovision_src, "ecovision", messages)
        if df_eco is None:
            return

        # ---- melt & normalise -----------------------------------------
        arcpy.SetProgressor("default", "Processing data…")
        df = pd.concat([df_trafx, df_eco], ignore_index=True)
        arcpy.AddMessage(f"Total rows after merge: {len(df):,}")

        # ---- load counter_id lookup from points layer -----------------
        arcpy.SetProgressor("default", "Loading counter ID lookup from points layer…")
        id_map = _load_counter_ids(points_url, gis, messages)
        if id_map is None:
            arcpy.AddWarning("Could not load counter IDs — counter_id will be NULL.")
            id_map = {}

        df["counter_id"] = df["counter_name"].map(id_map)
        arcpy.AddMessage(
            f"Matched {df['counter_id'].notna().sum():,} / {len(df):,} rows to a counter_id."
        )

        # ---- cross-reference validation --------------------------------
        # Names in CSV data but missing from points layer → no counter_id,
        # so counts will be orphaned with no spatial feature to join to.
        csv_names    = set(df["counter_name"].dropna().unique())
        points_names = set(id_map.keys())

        in_csv_not_points = sorted(csv_names - points_names)
        in_points_not_csv = sorted(points_names - csv_names)

        if in_csv_not_points:
            arcpy.AddWarning(
                f"\n⚠  {len(in_csv_not_points)} counter name(s) found in the CSV data "
                f"but NOT in the points layer — these rows will have no counter_id "
                f"and will be orphaned:\n"
                + "\n".join(f"    • {n}" for n in in_csv_not_points)
            )

        if in_points_not_csv:
            arcpy.AddWarning(
                f"\n⚠  {len(in_points_not_csv)} counter name(s) exist in the points layer "
                f"but have NO data in the CSVs — no counts will be loaded for them:\n"
                + "\n".join(f"    • {n}" for n in in_points_not_csv)
            )

        if not in_csv_not_points and not in_points_not_csv:
            arcpy.AddMessage("✓  All counter names match between CSVs and points layer.")

        # Hard-stop if every CSV row is unmatched (likely a name format problem)
        if df["counter_id"].isna().all() and id_map:
            arcpy.AddError(
                "No counter names from the CSV matched the points layer at all. "
                "Check that STATION_LOOKUP covers the column headers in your CSV files "
                "and that the points layer name field was detected correctly."
            )
            return

        # ---- preview --------------------------------------------------
        arcpy.AddMessage(f"\nSample rows:\n{df.head(10).to_string(index=False)}\n")
        arcpy.AddMessage(
            f"Date range: {df['count_date'].min()} → {df['count_date'].max()}"
        )
        arcpy.AddMessage(f"Unique counters: {df['counter_name'].nunique()}")
        arcpy.AddMessage(f"Total rows: {len(df):,}")

        if dry_run:
            arcpy.AddMessage("\nDRY RUN — no data written.")
            parameters[10].value = f"Dry run complete. {len(df):,} rows ready to write."
            return

        # ---- write to feature layer -----------------------------------
        arcpy.SetProgressor("default", "Updating counts feature layer…")
        _write_to_feature_layer(counts_url, df, gis, messages)

        summary = f"Update complete. {len(df):,} rows written to {counts_url}"
        arcpy.AddMessage(summary)
        parameters[10].value = summary

    # ------------------------------------------------------------------
    def postExecute(self, parameters):
        pass


# ===========================================================================
# Helpers
# ===========================================================================

def _connect_gis(portal_url, auth_mode, token, username, password, messages):
    """Return an authenticated GIS object or None on failure."""
    from arcgis.gis import GIS
    try:
        if auth_mode == "Pro (signed-in user)":
            return GIS("pro")
        elif auth_mode == "Token":
            return GIS(portal_url, token=token)
        else:
            return GIS(portal_url, username=username, password=password)
    except Exception as exc:
        arcpy.AddError(f"Portal connection failed: {exc}")
        return None


def _read_csv(src, category, messages):
    """
    Read a wide-format daily CSV from a file path or URL.

    Expected format:
      - First column: date (YYYY-MM-DD or M/D/YYYY)
      - Remaining columns: one per counter station, values = daily counts

    Returns a long-format DataFrame with columns:
      count_date, counter_name, count_of_bike_ped,
      month_of_year, season_of_year, counter_category
    """
    import pandas as pd

    try:
        if src.startswith("http://") or src.startswith("https://"):
            df_wide = pd.read_csv(src)
        elif os.path.isfile(src):
            df_wide = pd.read_csv(src)
        else:
            arcpy.AddError(f"Cannot read {category} CSV — not a valid path or URL: {src}")
            return None
    except Exception as exc:
        arcpy.AddError(f"Error reading {category} CSV: {exc}")
        return None

    arcpy.AddMessage(
        f"{category}: {len(df_wide):,} rows × {len(df_wide.columns)} columns read."
    )

    # Detect date column (first column)
    date_col = df_wide.columns[0]
    counter_cols = [c for c in df_wide.columns if c != date_col]

    # Melt wide → long
    df_long = df_wide.melt(
        id_vars=[date_col],
        value_vars=counter_cols,
        var_name="raw_name",
        value_name="count_of_bike_ped",
    )

    # Parse dates
    df_long["count_date"] = pd.to_datetime(df_long[date_col], errors="coerce")
    df_long = df_long.dropna(subset=["count_date"])

    # Drop rows with no count value
    df_long = df_long.dropna(subset=["count_of_bike_ped"])
    df_long["count_of_bike_ped"] = pd.to_numeric(
        df_long["count_of_bike_ped"], errors="coerce"
    )
    df_long = df_long.dropna(subset=["count_of_bike_ped"])
    df_long["count_of_bike_ped"] = df_long["count_of_bike_ped"].astype(int)

    # Normalise counter name
    df_long["counter_name"] = df_long["raw_name"].apply(
        lambda n: STATION_LOOKUP.get(n, n)
    )

    # Derived fields
    df_long["month_of_year"] = df_long["count_date"].dt.month
    df_long["season_of_year"] = df_long["month_of_year"].map(SEASON_MAP)
    df_long["counter_category"] = category

    return df_long[[
        "count_date", "counter_name", "count_of_bike_ped",
        "month_of_year", "season_of_year", "counter_category",
    ]]


def _load_counter_ids(points_url, gis, messages):
    """
    Query the points feature layer and return {counter_name: counter_id}.
    Tries several candidate field names for both the name and ID columns.
    """
    try:
        from arcgis.features import FeatureLayer
        lyr = FeatureLayer(points_url, gis=gis)
        fset = lyr.query(where="1=1", out_fields="*", return_geometry=False)
        if not fset.features:
            arcpy.AddWarning("Points layer returned no features.")
            return {}

        fields = [f["name"].lower() for f in fset.fields]

        name_candidates = ["counter_name", "name", "station_name", "site_name", "label"]
        id_candidates = ["counter_id", "monitoring_site_id", "site_id", "objectid", "fid"]

        name_field = next((c for c in name_candidates if c in fields), None)
        id_field   = next((c for c in id_candidates   if c in fields), None)

        if not name_field or not id_field:
            arcpy.AddWarning(
                f"Could not find name/id fields in points layer. Fields: {fields}"
            )
            return {}

        # Use original-case field names
        orig_fields = {f["name"].lower(): f["name"] for f in fset.fields}
        name_f = orig_fields[name_field]
        id_f   = orig_fields[id_field]

        id_map = {}
        for feat in fset.features:
            n = feat.attributes.get(name_f)
            i = feat.attributes.get(id_f)
            if n and i is not None:
                id_map[n] = i
                id_map[STATION_LOOKUP.get(n, n)] = i

        arcpy.AddMessage(f"Loaded {len(id_map)} counter ID mappings from points layer.")
        return id_map

    except Exception as exc:
        arcpy.AddWarning(f"Could not load counter IDs: {exc}")
        return None


def _write_to_feature_layer(counts_url, df, gis, messages):
    """
    Replace all rows in the counts feature layer table.

    Strategy:
      1. Delete all existing features (delete_features where=1=1)
      2. Chunk-add all new features (add_features in batches of 1000)

    The feature layer must be editable (published as Feature Service, not
    a read-only MapServer layer — update the URL to the FeatureServer
    endpoint before publishing as a web tool).
    """
    from arcgis.features import FeatureLayer, Feature
    import math

    # Swap MapServer → FeatureServer if needed (common mistake)
    edit_url = counts_url.replace("/MapServer/", "/FeatureServer/")
    if edit_url != counts_url:
        arcpy.AddMessage(
            f"Note: Switched URL to FeatureServer endpoint for editing:\n  {edit_url}"
        )

    try:
        lyr = FeatureLayer(edit_url, gis=gis)
    except Exception as exc:
        arcpy.AddError(f"Could not connect to counts feature layer: {exc}")
        return

    # Delete all existing rows
    arcpy.AddMessage("Deleting existing rows…")
    try:
        result = lyr.delete_features(where="1=1")
        arcpy.AddMessage(f"Delete result: {result}")
    except Exception as exc:
        arcpy.AddError(f"Failed to delete existing rows: {exc}\n{traceback.format_exc()}")
        return

    # Build feature list
    features = []
    for _, row in df.iterrows():
        attrs = {
            "count_date": int(row["count_date"].timestamp() * 1000),  # epoch ms
            "counter_name": row["counter_name"],
            "count_of_bike_ped": int(row["count_of_bike_ped"]),
            "month_of_year": int(row["month_of_year"]),
            "season_of_year": row["season_of_year"],
            "counter_category": row["counter_category"],
        }
        if "counter_id" in df.columns and row.get("counter_id") is not None:
            attrs["counter_id"] = int(row["counter_id"])
        features.append(Feature(attributes=attrs))

    # Add in batches
    batch_size = 1000
    n_batches = math.ceil(len(features) / batch_size)
    arcpy.SetProgressor("step", "Writing rows…", 0, n_batches, 1)

    total_added = 0
    for i in range(n_batches):
        chunk = features[i * batch_size : (i + 1) * batch_size]
        try:
            result = lyr.edit_features(adds=chunk)
            added = sum(1 for r in result.get("addResults", []) if r.get("success"))
            total_added += added
            arcpy.AddMessage(
                f"Batch {i + 1}/{n_batches}: {added}/{len(chunk)} rows added."
            )
        except Exception as exc:
            arcpy.AddError(
                f"Error writing batch {i + 1}: {exc}\n{traceback.format_exc()}"
            )
        arcpy.SetProgressorPosition()

    arcpy.AddMessage(f"\nTotal rows written: {total_added:,}")
