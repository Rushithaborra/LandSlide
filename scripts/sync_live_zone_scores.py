"""
Fixes a real staleness bug found while verifying the 3D terrain feature
against the task spec's own acceptance criteria ("verify by comparing a
known high-susceptibility zone's on-screen color/position against its real
susceptibility_score and risk_tier from the API"): doing that check for a
real zone (segment_id 44848721_00_001) showed risk_tier=high in the live
production API (Person B's real model, connected 2026-09-06) but
risk_tier=moderate in outputs/gis/sikkim_road_susceptibility.geojson -- the
static file both generate_hillshade_overlay.py (Phase 1) and
generate_terrain_rgb.py's texture (Phase 2) are built from.

The geojson was generated 2026-09-02, before Person B's model was connected
and overwrote scores for 3,411 of 3,921 zones. Checked here: literally
every one of the 3,921 features in that geojson is still on
random_forest-extended-v1-20260902 -- none reflect the live update.

The live GET /zones endpoint only returns centroids, not polygon geometry
(confirmed against its OpenAPI spec), so it can't replace the geojson as
the geometry source -- the real corridor shapes only exist in that file.
Fix: pull real live scores from the API and merge them onto the geojson's
real geometries, joined on segment_id (the same safe key
integrate_zone_predictions.py already uses, after that script's own
history of a name-collision bug -- see README/CLAUDE.md). The live zone
`name` field is literally f"{ref} ({segment_id})", so segment_id is
recovered with a regexp rather than needing a new API field.

Output: outputs/gis/sikkim_road_susceptibility_live.geojson -- a separate
file, not an overwrite of the original, so the original stays available as
a record of the pre-Person-B baseline. generate_hillshade_overlay.py and
generate_terrain_rgb.py's texture step should point at the _live file.
"""
import json
import re
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
GEOJSON_PATH = ROOT / "outputs" / "gis" / "sikkim_road_susceptibility.geojson"
OUT_PATH = ROOT / "outputs" / "gis" / "sikkim_road_susceptibility_live.geojson"
API_BASE = "https://landslide-ews-backend.onrender.com"

SEGMENT_ID_RE = re.compile(r"\(([^)]+)\)\s*$")


def fetch_all_live_zones(state: str) -> dict[str, dict]:
    """Returns {segment_id: {susceptibility_score, risk_tier, model_version}}."""
    by_segment = {}
    offset = 0
    limit = 5000
    with httpx.Client(timeout=60) as client:
        while True:
            resp = client.get(f"{API_BASE}/zones", params={"state": state, "limit": limit, "offset": offset})
            resp.raise_for_status()
            batch = resp.json()
            if not batch:
                break
            for z in batch:
                m = SEGMENT_ID_RE.search(z.get("name") or "")
                if not m:
                    continue
                by_segment[m.group(1)] = {
                    "susceptibility_score": z.get("susceptibility_score"),
                    "risk_tier": z.get("risk_tier"),
                    "model_version": z.get("model_version"),
                }
            if len(batch) < limit:
                break
            offset += limit
    return by_segment


def main():
    with open(GEOJSON_PATH) as f:
        gj = json.load(f)

    print(f"Fetching real live zone scores for Sikkim from {API_BASE} ...")
    live_by_segment = fetch_all_live_zones("Sikkim")
    print(f"  {len(live_by_segment)} live zones indexed by segment_id")

    matched = changed = unmatched = 0
    for feat in gj["features"]:
        seg_id = feat["properties"].get("segment_id")
        live = live_by_segment.get(seg_id)
        if live is None:
            unmatched += 1
            continue
        matched += 1
        old_tier = feat["properties"].get("risk_tier")
        feat["properties"]["susceptibility_score"] = live["susceptibility_score"]
        feat["properties"]["risk_tier"] = live["risk_tier"]
        feat["properties"]["model_version"] = live["model_version"]
        if live["risk_tier"] != old_tier:
            changed += 1

    print(f"Matched {matched}/{len(gj['features'])} zones by segment_id "
          f"({unmatched} unmatched -- kept their old static score).")
    print(f"{changed} zones changed risk_tier after syncing to live production data "
          f"(these were rendering a stale tier before this fix).")

    with open(OUT_PATH, "w") as f:
        json.dump(gj, f)
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
