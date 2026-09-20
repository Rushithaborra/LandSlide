"""Download villages and emergency services for the north-east from OpenStreetMap.

Run once (and occasionally to refresh); `scripts/load_osm_places.py` puts the result
in the database. The public Overpass servers time out on big queries, so the region
is cut into 1-degree tiles, each fetched separately with retries and a polite pause.
The output is a dated snapshot -- OpenStreetMap is mapped by volunteers, so it is
incomplete and can be out of date in places; the dashboard says so.

    python scripts/fetch_osm_places.py [--out data/interim/osm_places.json] [--only 27,88]

By default only tiles that contain at least one zone of ours are fetched (the rest
of the box is sea, Bhutan, Bangladesh, Myanmar and China), and the output file is
saved after every tile, so an interrupted run resumes where it stopped.
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

# Lon/lat extent of all eight north-east states (Sikkim reaches furthest west).
WEST, SOUTH, EAST, NORTH = 88.0, 21.9, 97.5, 29.6
SERVERS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter", "https://overpass.private.coffee/api/interpreter"]
HEADERS = {"User-Agent": "landslide-ews-research/1.0 (SIH prototype; contact via GitHub Rushithaborra/LandSlide)", "Accept": "application/json"}
PAUSE_SECONDS = 2.0
FIRST_TILES = {(27, 88), (28, 88)}  # Sikkim

# What counts as a "village" for the dashboard, and which services matter for a rescue.
VILLAGE_QUERY = 'node["place"~"^(village|hamlet|town|city)$"]["name"]({bbox});'
SERVICE_QUERY = 'nwr["amenity"~"^(hospital|clinic|police|fire_station)$"]({bbox});'


def tiles_with_zones() -> list[tuple[int, int]]:
    """1-degree tiles (by south-west corner) that contain at least one of our zones."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from sqlalchemy import func, select

    from app.database import SessionLocal
    from app.models import Zone

    with SessionLocal() as db:
        rows = db.execute(select(func.floor(Zone.centroid_lat), func.floor(Zone.centroid_lng)).distinct()).all()
    return sorted((int(lat), int(lng)) for lat, lng in rows)


def query(client: httpx.Client, body: str, attempts: int = 6) -> list[dict]:
    payload = f"[out:json][timeout:60];({body});out tags center;"
    for attempt in range(1, attempts + 1):
        server = SERVERS[(attempt - 1) % len(SERVERS)]
        try:
            resp = client.post(server, data={"data": payload}, timeout=90)
            if resp.status_code == 200:
                return resp.json()["elements"]
            print(f"    {server.split('/')[2]} -> HTTP {resp.status_code} (attempt {attempt})", file=sys.stderr)
        except (httpx.HTTPError, ValueError) as e:
            print(f"    {server.split('/')[2]} -> {type(e).__name__} (attempt {attempt})", file=sys.stderr)
        time.sleep(min(60, 5 * attempt))
    raise RuntimeError("all Overpass attempts failed for this tile")


def place_row(e: dict) -> dict | None:
    tags = e.get("tags", {})
    lat = e.get("lat") if "lat" in e else (e.get("center") or {}).get("lat")
    lng = e.get("lon") if "lon" in e else (e.get("center") or {}).get("lon")
    if lat is None or lng is None:
        return None
    if "place" in tags:
        kind = "village" if tags["place"] in ("village", "hamlet") else tags["place"]  # village | town | city
    else:
        kind = tags.get("amenity")  # hospital | clinic | police | fire_station
    return {
        "osm_id": f"{e['type'][0]}{e['id']}",  # n123 / w123 / r123
        "kind": kind,
        "name": tags.get("name") or tags.get("name:en"),
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "phone": tags.get("phone") or tags.get("contact:phone"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", default="data/interim/osm_places.json")
    parser.add_argument("--only", help="fetch just one tile, e.g. 27,88 (south-west corner), to test")
    args = parser.parse_args()

    out = Path(args.out)
    todo = [tuple(int(v) for v in args.only.split(","))] if args.only else tiles_with_zones()
    todo.sort(key=lambda tile: (tile not in FIRST_TILES, tile))  # Sikkim (the only state with rain alerts) first
    rows: dict[str, dict] = {}
    done: set[tuple[int, int]] = set()
    if out.exists():  # resume
        saved = json.loads(out.read_text(encoding="utf-8"))
        rows = {r["osm_id"]: r for r in saved["places"]}
        done = {tuple(t) for t in saved.get("done_tiles", [])}
        print(f"resuming: {len(rows)} places and {len(done)} tiles already saved")
    failed = []

    def save():
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(
            json.dumps({"fetched_at": datetime.now(timezone.utc).isoformat(), "source": "OpenStreetMap via Overpass API",
                        "done_tiles": sorted(done), "places": list(rows.values())}, ensure_ascii=False),
            encoding="utf-8",
        )

    with httpx.Client(headers=HEADERS) as client:
        for i, (lat, lng) in enumerate(todo, 1):
            if (lat, lng) in done:
                continue
            bbox = f"{lat},{lng},{lat + 1},{lng + 1}"  # south,west,north,east
            try:
                found = query(client, VILLAGE_QUERY.format(bbox=bbox)) + query(client, SERVICE_QUERY.format(bbox=bbox))
            except RuntimeError as e:
                failed.append((lat, lng))
                print(f"[{i}/{len(todo)}] tile {lat},{lng}: FAILED ({e})")
                continue
            for e in found:
                row = place_row(e)
                if row and row["kind"]:
                    rows[row["osm_id"]] = row
            done.add((lat, lng))
            save()
            print(f"[{i}/{len(todo)}] tile {lat},{lng}: {len(found)} elements (total {len(rows)})", flush=True)
            time.sleep(PAUSE_SECONDS)

    save()
    kinds = {}
    for r in rows.values():
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"wrote {len(rows)} places to {out}: {kinds}")
    if failed:
        print(f"{len(failed)} tiles failed and are missing: {failed} -- re-run to fill them in", file=sys.stderr)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
