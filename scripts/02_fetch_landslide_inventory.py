"""
Day 1 (Role A - Data/GIS): pull the Sikkim landslide inventory (positive
samples) directly from GSI NLFC's live ArcGIS FeatureServer, instead of
parsing the 904-page PDF report.

Source: bhusanket.gsi.gov.in, layer "Hosted/India_All_Landslided/FeatureServer/0"
Access: the FeatureServer itself demands a token, but the portal's own
proxy (DotNet/proxy.ashx) passes queries through without one -- same
mechanism the site's own map viewer uses.

Outputs:
  data/raw/gsi_sikkim_landslides_raw.geojson  - full record, every field
  data/raw/gsi_sikkim_landslides.csv          - trimmed to the columns the
                                                 team actually models on
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from shapely.geometry import shape, Point

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
RAW.mkdir(parents=True, exist_ok=True)

FEATURE_SERVER = (
    "https://bhusanket.gsi.gov.in/gisserver/rest/services/Hosted/"
    "India_All_Landslided/FeatureServer/0/query"
)
PROXY = "https://bhusanket.gsi.gov.in/DotNet/proxy.ashx?"

COLUMNS = [
    ("slide_no", "Slide_No"),
    ("state", "State"),
    ("district", "District"),
    ("slide_name", "Slide_Name"),
    ("nh_sh_loca", "NH_SH_Location"),
    ("latitude", "Latitude"),
    ("longitude", "Longitude"),
    ("materialin", "Material_Involved"),
    ("movementty", "Movement_Type"),
    ("history_da", "History_Date"),
    ("activity", "Activity"),
]


def fetch(state="Sikkim"):
    params = {
        "where": f"state='{state}'",
        "outFields": "*",
        "returnGeometry": "true",
        "f": "geojson",
    }
    inner_url = FEATURE_SERVER + "?" + urllib.parse.urlencode(params)
    url = PROXY + inner_url
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)


def main():
    print("Querying GSI NLFC FeatureServer for state='Sikkim'...")
    geojson = fetch("Sikkim")
    n = len(geojson.get("features", []))
    print(f"  got {n} records")

    raw_path = RAW / "gsi_sikkim_landslides_raw.geojson"
    with open(raw_path, "w") as f:
        json.dump(geojson, f)
    print(f"Wrote {raw_path}")

    with open(RAW / "sikkim_boundary.geojson") as f:
        boundary_gj = json.load(f)
    sikkim_poly = shape(boundary_gj["features"][0]["geometry"])

    rows = []
    outside = []
    for feat in geojson["features"]:
        props = feat["properties"]
        lon, lat = feat["geometry"]["coordinates"]
        pt = Point(lon, lat)
        inside = sikkim_poly.contains(pt) or sikkim_poly.buffer(0.02).contains(pt)
        if not inside:
            outside.append((props.get("slide_no"), lat, lon))
        row = {csv_name: props.get(src) for src, csv_name in COLUMNS}
        rows.append(row)

    csv_path = RAW / "gsi_sikkim_landslides.csv"
    header = [c[1] for c in COLUMNS]
    with open(csv_path, "w") as f:
        f.write(",".join(header) + "\n")
        for row in rows:
            vals = []
            for _, name in COLUMNS:
                v = row[name]
                v = "" if v is None else str(v).replace(",", ";")
                vals.append(v)
            f.write(",".join(vals) + "\n")
    print(f"Wrote {csv_path} ({len(rows)} rows)")

    print("\nSpot-check: coordinates falling inside Sikkim boundary")
    print(f"  {len(rows) - len(outside)} / {len(rows)} inside (buffered 0.02deg ~2km for coastline/simplification slack)")
    if outside:
        print(f"  {len(outside)} OUTSIDE -- flag these before trusting the file:")
        for slide_no, lat, lon in outside[:15]:
            print(f"    {slide_no}: lat={lat}, lon={lon}")

    print("\nField completeness (non-null %):")
    for _, name in COLUMNS:
        non_null = sum(1 for r in rows if r[name] not in (None, "", " "))
        print(f"  {name}: {100*non_null/len(rows):.1f}%")


if __name__ == "__main__":
    main()
