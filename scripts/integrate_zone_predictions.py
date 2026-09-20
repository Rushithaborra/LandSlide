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
        # Keyed by (name, state), not name alone: a road crossing a state border
        # yields the same zone name in both states (57 Nagaland names collided
        # with live Manipur zones), and a name-only match would have skipped
        # creating the Nagaland zone and then overwritten the Manipur zone's
        # score with Nagaland's.
        existing = {(name, st): str(zid) for name, st, zid in db.query(Zone.name, Zone.state, Zone.id).all()}
        selected = features[:limit] if limit else features

        to_insert = []
        for feat in selected:
            props = feat["properties"]
            name = zone_name_for(props)
            if (name, state) not in existing:
                new_id = str(uuid.uuid4())
                polygon = shape(feat["geometry"])
                centroid = polygon.centroid
                to_insert.append({
                    "id": new_id, "name": name, "state": state,
                    "geometry": from_shape(polygon, srid=4326),
                    "centroid_lat": centroid.y, "centroid_lng": centroid.x,
                })
                existing[(name, state)] = new_id

        for i in range(0, len(to_insert), chunk_size):
            chunk = to_insert[i:i + chunk_size]
            db.execute(Zone.__table__.insert(), chunk)
            db.commit()
            print(f"  inserted zones {i + len(chunk)}/{len(to_insert)}")

        for feat in selected:
            props = feat["properties"]
            name = zone_name_for(props)
            mapping.append((props["segment_id"], existing[(name, state)], props["susceptibility_score"],
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


def push_susceptibility_bulk(mapping: list[tuple], chunk_size: int = 2000) -> int:
    """Writes score/tier/model_version for every mapped zone with a few
    set-based UPDATE ... FROM (VALUES ...) statements (same three fields the
    PUT endpoint writes; the table's CHECK constraints still apply). Default
    path because the HTTP route needs a local API on BACKEND_BASE_URL -- with
    none running, every PUT failed ("All connection attempts failed") and the
    freshly inserted zones sat unscored in production. This is also ~50x
    faster (8,458 zones in ~26s vs ~22 min of PUTs)."""
    from psycopg2.extras import execute_values
    from app.database import engine

    rows = [(zid, score, tier, version) for _, zid, score, tier, version in mapping]
    conn = engine.raw_connection()
    try:
        cur = conn.cursor()
        for i in range(0, len(rows), chunk_size):
            execute_values(
                cur,
                "UPDATE zones z SET susceptibility_score = v.s::float8, risk_tier = v.t, model_version = v.m, "
                "last_updated = now() FROM (VALUES %s) AS v(id, s, t, m) WHERE z.id = v.id::uuid",
                rows[i:i + chunk_size], page_size=chunk_size,
            )
            conn.commit()
        return len(rows)
    finally:
        conn.close()


def vacuum_zones() -> None:
    """VACUUM ANALYZE after a bulk load. The map/stats/corridor endpoints are
    answered from covering indexes (migrations/011_zone_map_indexes.sql), which
    only skip the 220 MB of polygons once the freshly inserted rows are marked
    visible -- until autovacuum gets around to it, every query quietly falls
    back to reading the table (counts went from 0.2 s to 6+ s)."""
    import psycopg2
    from app.config import settings

    conn = psycopg2.connect(settings.database_url)
    conn.autocommit = True  # VACUUM cannot run inside a transaction
    try:
        conn.cursor().execute("VACUUM (ANALYZE) zones")
    finally:
        conn.close()


def verify_readback(zone_id: str, base_url: str = BACKEND_BASE_URL) -> dict:
    with httpx.Client(timeout=10.0) as client:
        resp = client.get(f"{base_url}/zones/{zone_id}")
    return {"status_code": resp.status_code, "body": resp.json() if resp.status_code == 200 else resp.text}


if __name__ == "__main__":
    # e.g. `python scripts/integrate_zone_predictions.py assam` or with a
    # row limit for a smoke test: `... assam 5`. Defaults to Sikkim so a
    # bare invocation is unchanged from before this script was generalized.
    # `--http` sends scores through PUT /zones/{id}/susceptibility instead of
    # the direct bulk write (needs an API running at BACKEND_BASE_URL).
    use_http = "--http" in sys.argv
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    state_arg = args[0] if args else "sikkim"
    limit = int(args[1]) if len(args) > 1 else None
    # "arunachal_pradesh" -> "Arunachal Pradesh": plain .capitalize() gave
    # "Arunachal_pradesh", which zones.state's CHECK constraint rejects.
    state = state_arg.replace("_", " ").title()

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
    if use_http:
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
    else:
        n = push_susceptibility_bulk(mapping)
        print(f"bulk score write: {n} zones in {time.time()-t0:.1f}s")
        db = SessionLocal()
        try:
            total = db.query(Zone).filter(Zone.state == state).count()
            unscored = db.query(Zone).filter(Zone.state == state, Zone.risk_tier.is_(None)).count()
        finally:
            db.close()
        print(f"{state} in database: {total} zones, {unscored} unscored")

    t0 = time.time()
    vacuum_zones()
    print(f"vacuum/analyze zones: {time.time()-t0:.1f}s")
