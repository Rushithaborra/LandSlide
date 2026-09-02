"""Loads generated corridor predictions (scripts/generate_zone_predictions.py's
output) and pushes them into the backend: creates a Zone row per corridor
(direct DB insert, same pattern as scripts/seed_zone.py -- there is no
POST /zones endpoint, zone creation has never gone through the HTTP API in
this project) then updates its susceptibility via the EXISTING, unmodified
PUT /zones/{id}/susceptibility endpoint over real HTTP, and verifies the
round-trip via GET.

Does not create a new backend architecture, does not touch the alert engine
or dashboard.
"""
import json
import pathlib
import sys
import time

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from geoalchemy2.shape import from_shape
from shapely.geometry import shape

from app.database import SessionLocal
from app.models import Zone

GEOJSON_PATH = pathlib.Path(__file__).resolve().parent.parent / "outputs" / "gis" / "sikkim_road_susceptibility.geojson"
BACKEND_BASE_URL = "http://localhost:8000"


def zone_name_for(props: dict) -> str:
    """Human-readable label, but MUST be unique per segment -- Zone.name is
    the only field this direct-DB-insert path can match existing rows on
    (no segment_id column on Zone; not adding one is a deliberate "don't
    modify the backend" call for this task). Using `ref` alone (e.g.
    'NH10') is NOT enough: a single highway ref covers dozens of distinct
    500m segments, so a first version of this function collided them --
    verified for real: 3921 segments produced only 1899 distinct zones,
    each repeatedly overwritten by whichever same-named segment was
    processed last. Embedding segment_id guarantees uniqueness while
    keeping the road identifier for readability."""
    label = props.get("ref") or props.get("name") or "road"
    return f"{label} ({props['segment_id']})"


def create_or_get_zones(features: list[dict], limit: int | None = None) -> list[tuple[str, str]]:
    """Creates a Zone row for each corridor not already present (matched by
    name, since segment_id isn't stored on Zone -- the schema wasn't
    changed for this task). Returns [(segment_id, zone_id), ...]."""
    db = SessionLocal()
    mapping = []
    try:
        existing_names = {z.name for z in db.query(Zone.name).all()}
        for feat in features[:limit] if limit else features:
            props = feat["properties"]
            name = zone_name_for(props)
            polygon = shape(feat["geometry"])

            zone = db.query(Zone).filter(Zone.name == name).first()
            if zone is None:
                zone = Zone(name=name, geometry=from_shape(polygon, srid=4326))
                db.add(zone)
                db.commit()
                db.refresh(zone)
            mapping.append((props["segment_id"], str(zone.id), props["susceptibility_score"],
                             props["risk_tier"], props["model_version"]))
    finally:
        db.close()
    return mapping


def push_susceptibility(mapping: list[tuple], base_url: str = BACKEND_BASE_URL) -> dict:
    ok, failed = 0, []
    with httpx.Client(timeout=10.0) as client:
        for segment_id, zone_id, score, tier, version in mapping:
            resp = client.put(
                f"{base_url}/zones/{zone_id}/susceptibility",
                json={"susceptibility_score": score, "risk_tier": tier, "model_version": version},
            )
            if resp.status_code == 200:
                ok += 1
            else:
                failed.append((segment_id, zone_id, resp.status_code, resp.text[:200]))
    return {"ok": ok, "failed": failed}


def verify_readback(zone_id: str, base_url: str = BACKEND_BASE_URL) -> dict:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{base_url}/zones/{zone_id}")
    return {"status_code": resp.status_code, "body": resp.json() if resp.status_code == 200 else resp.text}


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None

    with open(GEOJSON_PATH) as f:
        geojson = json.load(f)
    features = geojson["features"]
    print(f"loaded {len(features)} corridor predictions from {GEOJSON_PATH}")
    if limit:
        print(f"limiting to first {limit} for this run")

    t0 = time.time()
    mapping = create_or_get_zones(features, limit=limit)
    print(f"zones created/matched: {len(mapping)} in {time.time()-t0:.1f}s")

    t0 = time.time()
    result = push_susceptibility(mapping)
    print(f"PUT /zones/{{id}}/susceptibility: {result['ok']} succeeded, {len(result['failed'])} failed, "
          f"in {time.time()-t0:.1f}s")
    if result["failed"]:
        print("failures (first 5):", result["failed"][:5])

    if mapping:
        sample_zone_id = mapping[0][1]
        readback = verify_readback(sample_zone_id)
        print(f"\nGET readback verification for zone {sample_zone_id}: HTTP {readback['status_code']}")
        print(readback["body"])
