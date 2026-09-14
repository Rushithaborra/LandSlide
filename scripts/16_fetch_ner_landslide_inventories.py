"""
NER expansion, step 1: pull the landslide inventory for the 7 remaining
North-East states (Sikkim's neighbours) from the same live GSI NLFC
FeatureServer used in scripts/02_fetch_landslide_inventory.py -- no PDF
parsing. The state's own PROVENANCE.md already established the PDF
report was never used for Sikkim; the FeatureServer is the proven source
and its `fetch()` already takes a `state` argument, so this script reuses
it rather than re-deriving a second inventory method.

One script, one config list -- not a copy of scripts/02 per state.

Source: bhusanket.gsi.gov.in, layer "Hosted/India_All_Landslided/FeatureServer/0"
Access: same undocumented-but-public proxy mechanism as scripts/02
(bhusanket.gsi.gov.in/DotNet/proxy.ashx) -- the site's own map viewer uses
this to bypass the FeatureServer's token requirement.

Outputs (per state):
  data/raw/gsi_<state>_landslides_raw.geojson  - full record, every field
  data/raw/gsi_<state>_landslides.csv          - trimmed, deduped columns

State name strings verified against the FeatureServer's own distinct
`state` values on 2026-09-13 (queried with returnDistinctValues) -- all 7
below match exactly, no spelling variants (unlike e.g. "Jammu & Kashmir",
which has 4 different spellings in the source data and isn't relevant here).
"""
import csv
import json
import urllib.parse
import urllib.request
from pathlib import Path

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

NER_STATES = [
    "Assam",
    "Arunachal Pradesh",
    "Manipur",
    "Meghalaya",
    "Mizoram",
    "Nagaland",
    "Tripura",
]


def true_count(state):
    """The layer's own maxRecordCount is 2000 -- a single query silently
    truncates any state with more records than that (caught on Mizoram:
    a single-query fetch returned exactly 2000 features, but the server's
    own returnCountOnly reports 2046 true records). Always check this
    before trusting a single-page fetch."""
    params = {"where": f"state='{state}'", "returnCountOnly": "true", "f": "json"}
    url = PROXY + FEATURE_SERVER + "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=60) as resp:
        return json.load(resp)["count"]


def fetch(state):
    """Paginate with resultOffset/resultRecordCount past the server's
    2000-record page cap, then verify the total against true_count()."""
    expected = true_count(state)
    all_features = []
    offset = 0
    page_size = 2000
    while True:
        params = {
            "where": f"state='{state}'",
            "outFields": "*",
            "returnGeometry": "true",
            "resultOffset": offset,
            "resultRecordCount": page_size,
            "f": "geojson",
        }
        inner_url = FEATURE_SERVER + "?" + urllib.parse.urlencode(params)
        url = PROXY + inner_url
        with urllib.request.urlopen(url, timeout=90) as resp:
            page = json.load(resp)
        feats = page.get("features", [])
        all_features.extend(feats)
        if len(feats) < page_size:
            break
        offset += page_size

    if len(all_features) != expected:
        print(f"  WARNING: fetched {len(all_features)} features but server "
              f"reports {expected} true records for {state} -- pagination "
              f"may be incomplete, do not trust this count silently")

    return {"type": "FeatureCollection", "features": all_features}, expected


def slug(state):
    return state.lower().replace(" ", "_")


def dedup_exact_coordinates(rows):
    """Drop exact-duplicate (lat, lon) pairs, keeping the first occurrence.
    Same method as the exact-coordinate dedup already applied to Sikkim's
    inventory checks -- coordinates that match to full float precision are
    the same physical report entered twice (e.g. re-surveyed / re-submitted
    slide records), not two independent slides that happen to coincide.
    """
    seen = set()
    deduped = []
    dupes = 0
    for row in rows:
        key = (row["Latitude"], row["Longitude"])
        if key in seen:
            dupes += 1
            continue
        seen.add(key)
        deduped.append(row)
    return deduped, dupes


def main():
    summary = []
    for state in NER_STATES:
        print(f"\nQuerying GSI NLFC FeatureServer for state='{state}'...")
        geojson, expected = fetch(state)
        n_raw = len(geojson.get("features", []))
        print(f"  got {n_raw} records (server reports {expected} true records)")

        raw_path = RAW / f"gsi_{slug(state)}_landslides_raw.geojson"
        with open(raw_path, "w") as f:
            json.dump(geojson, f)
        print(f"  wrote {raw_path}")

        rows = []
        for feat in geojson["features"]:
            props = feat["properties"]
            row = {name: props.get(src) for src, name in COLUMNS}
            rows.append(row)

        deduped, n_dupes = dedup_exact_coordinates(rows)

        # Plain string-joining broke on any field containing an embedded
        # newline (e.g. NH_SH_Location values like "Chattrick\nKamjong
        # road") -- it split one logical row into two physical CSV lines,
        # silently misaligning every column after it. Caught this on 5 of
        # 6 new states (Manipur worst, 76 corrupted rows) AND retroactively
        # on the pre-existing Sikkim CSV (6 rows) -- csv.writer with
        # default quoting handles embedded commas/newlines/quotes correctly.
        csv_path = RAW / f"gsi_{slug(state)}_landslides.csv"
        header = [c[1] for c in COLUMNS]
        with open(csv_path, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(header)
            for row in deduped:
                vals = []
                for _, name in COLUMNS:
                    v = row[name]
                    vals.append("" if v is None else str(v))
                writer.writerow(vals)
        print(f"  wrote {csv_path} ({len(deduped)} rows, {n_dupes} exact-coordinate duplicates dropped)")

        summary.append((state, n_raw, n_dupes, len(deduped)))

    print("\n" + "=" * 60)
    print(f"{'State':<20}{'raw':>8}{'dupes':>8}{'final':>8}")
    for state, n_raw, n_dupes, n_final in summary:
        print(f"{state:<20}{n_raw:>8}{n_dupes:>8}{n_final:>8}")


if __name__ == "__main__":
    main()
