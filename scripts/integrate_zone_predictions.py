"""Loads generated corridor predictions (scripts/generate_zone_predictions.py's
output) and pushes them into the backend: creates a Zone row per corridor
(direct DB insert, same pattern as scripts/seed_zone.py -- there is no
POST /zones endpoint, zone creation has never gone through the HTTP API in
this project) then updates its susceptibility via the EXISTING, unmodified
PUT /zones/{id}/susceptibility endpoint over real HTTP, and verifies the
round-trip via GET.

Does not create a new backend architecture, does not touch the alert engine
or dashboard.

Performance note (added when scaling to the full 3921-segment run): the
original version did one commit per zone and one sequential HTTP PUT per
zone -- fine for a 5-row smoke test, but each round trip to the remote
Supabase database/backend costs ~0.5-2.5s, so 3921 of them serially would
take hours. Zone creation now bulk-inserts in chunks (UUIDs generated
client-side so we know each zone's id without a round trip back); the PUT
phase now fires requests concurrently (bounded by a semaphore) instead of
one at a time. Same operations, same endpoint, just not one-at-a-time.
"""
import asyncio
import json
import pathlib
import sys
import time
import uuid

import httpx

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from geoalchemy2.shape import from_shape
from shapely.geometry import shape

from app.database import SessionLocal
from app.models import Zone

OUTPUT_DIR = pathlib.Path(__file__).resolve().parent.parent / "outputs" / "gis"
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


def create_or_get_zones(features: list[dict], state: str = "Sikkim", limit: int | None = None,
                         chunk_size: int = 300) -> list[tuple]:
    """Creates a Zone row for each corridor not already present (matched by
    name, since segment_id isn't stored on Zone -- the schema wasn't
    changed for this task). Returns [(segment_id, zone_id, score, tier, version), ...].

    New zones are bulk-inserted in chunks (id generated client-side, so no
    round trip is needed to learn each new row's id) instead of one INSERT
    + commit per zone -- the only thing that changed is how many network
    round trips this takes, not what ends up in the database.

    `state` MUST be passed explicitly for any non-Sikkim run: Zone.state
    defaults to "Sikkim" at the ORM level, and this bulk Core-level insert
    respects that Python-side default for any column left out of the values
    dict -- so a first version of this script that ran for Assam without
    setting `state` here would have silently mislabeled every real Assam
    zone as Sikkim. Caught and fixed before this ever ran against Assam.
    """
    db = SessionLocal()
    mapping = []
    try:
        existing = {name: str(zid) for name, zid in db.query(Zone.name, Zone.id).all()}
        selected = features[:limit] if limit else features

        to_insert = []
        for feat in selected:
            props = feat["properties"]
            name = zone_name_for(props)
            if name not in existing:
                new_id = str(uuid.uuid4())
                polygon = shape(feat["geometry"])
                centroid = polygon.centroid
                to_insert.append({
                    "id": new_id, "name": name, "state": state,
                    "geometry": from_shape(polygon, srid=4326),
                    "centroid_lat": centroid.y, "centroid_lng": centroid.x,
                })
                existing[name] = new_id

        for i in range(0, len(to_insert), chunk_size):
            chunk = to_insert[i:i + chunk_size]
            db.execute(Zone.__table__.insert(), chunk)
            db.commit()
            print(f"  inserted zones {i + len(chunk)}/{len(to_insert)}")

        for feat in selected:
            props = feat["properties"]
            name = zone_name_for(props)
            mapping.append((props["segment_id"], existing[name], props["susceptibility_score"],
                             props["risk_tier"], props["model_version"]))
    finally:
        db.close()
    return mapping


async def push_susceptibility_async(mapping: list[tuple], base_url: str = BACKEND_BASE_URL, concurrency: int = 15) -> dict:
    ok, failed = 0, []
    sem = asyncio.Semaphore(concurrency)

    async def one(client, segment_id, zone_id, score, tier, version):
        nonlocal ok
        async with sem:
            try:
                resp = await client.put(
                    f"{base_url}/zones/{zone_id}/susceptibility",
                    json={"susceptibility_score": score, "risk_tier": tier, "model_version": version},
                )
                if resp.status_code == 200:
                    ok += 1
                else:
                    failed.append((segment_id, zone_id, resp.status_code, resp.text[:200]))
            except Exception as e:
                failed.append((segment_id, zone_id, "exception", str(e)[:200]))

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [one(client, *m) for m in mapping]
        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 200 == 0:
                print(f"  susceptibility PUT: {done}/{len(mapping)}")
    return {"ok": ok, "failed": failed}


def push_susceptibility(mapping: list[tuple], base_url: str = BACKEND_BASE_URL) -> dict:
    return asyncio.run(push_susceptibility_async(mapping, base_url))


def verify_readback(zone_id: str, base_url: str = BACKEND_BASE_URL) -> dict:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{base_url}/zones/{zone_id}")
    return {"status_code": resp.status_code, "body": resp.json() if resp.status_code == 200 else resp.text}


if __name__ == "__main__":
    # e.g. `python scripts/integrate_zone_predictions.py assam` or with a
    # row limit for a smoke test: `... assam 5`. Defaults to Sikkim so a
    # bare invocation is unchanged from before this script was generalized.
    state_arg = sys.argv[1] if len(sys.argv) > 1 else "sikkim"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else None
    state = state_arg.capitalize()

    geojson_path = OUTPUT_DIR / f"{state_arg.lower()}_road_susceptibility.geojson"
    with open(geojson_path) as f:
        geojson = json.load(f)
    features = geojson["features"]
    print(f"loaded {len(features)} corridor predictions from {geojson_path} (state={state})")
    if limit:
        print(f"limiting to first {limit} for this run")

    t0 = time.time()
    mapping = create_or_get_zones(features, state=state, limit=limit)
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
