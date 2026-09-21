"""Pull villages and emergency services out of an OpenStreetMap regional extract.

A faster, more reliable replacement for the tile-by-tile Overpass download in
`scripts/fetch_osm_places.py`: the public Overpass servers time out constantly, while
Geofabrik publishes the whole north-east as one file.

    # 1. download once (about 105 MB, updated daily):
    #    https://download.geofabrik.de/asia/india/north-eastern-zone-latest.osm.pbf
    python scripts/extract_osm_places.py data/interim/north-eastern-zone-latest.osm.pbf
    # 2. put the result in the database (same snapshot format as the Overpass script):
    python scripts/load_osm_places.py

Uses the same rules as the Overpass script (`place_row`): villages/hamlets, towns and cities
that have a name, and hospitals, clinics, police and fire stations (a service may be
unnamed). A way (a building outline) becomes the mean of its corner points. Relations
(rare multi-part buildings) are skipped. OpenStreetMap is mapped by volunteers, so
coverage is uneven; the dashboard says so.
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import osmium
from osmium.filter import KeyFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_osm_places import EAST, NORTH, SOUTH, WEST, place_row  # noqa: E402  (same extent and row rules)


def elements(pbf: Path):
    """Tagged nodes and ways as Overpass-style dicts, so `place_row` applies unchanged."""
    processor = osmium.FileProcessor(str(pbf)).with_locations().with_filter(KeyFilter("place", "amenity"))
    for obj in processor:
        tags = {t.k: t.v for t in obj.tags}
        if obj.is_node():
            yield {"type": "node", "id": obj.id, "tags": tags, "lat": obj.location.lat, "lon": obj.location.lon}
        elif obj.is_way():
            points = [n.location for n in obj.nodes if n.location.valid()]
            if points:
                yield {
                    "type": "way", "id": obj.id, "tags": tags,
                    "center": {"lat": sum(p.lat for p in points) / len(points), "lon": sum(p.lon for p in points) / len(points)},
                }


def data_date(pbf: Path) -> datetime:
    """When the extract's data is from (its replication timestamp), else the file's own time."""
    header = osmium.FileProcessor(str(pbf)).header
    stamp = header.get("osmosis_replication_timestamp")
    if stamp:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    return datetime.fromtimestamp(pbf.stat().st_mtime, tz=timezone.utc)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pbf", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/interim/osm_places.json"))
    args = parser.parse_args()

    rows: dict[str, dict] = {}
    seen = 0
    for element in elements(args.pbf):
        seen += 1
        row = place_row(element)
        if not row or not row["kind"]:
            continue
        if row["kind"] in ("village", "town", "city") and not row["name"]:
            continue  # an unnamed settlement cannot be shown to a resident
        if not (SOUTH <= row["lat"] <= NORTH and WEST <= row["lng"] <= EAST):
            continue  # outside the eight states' extent
        rows[row["osm_id"]] = row

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fetched_at = data_date(args.pbf)
    args.out.write_text(
        json.dumps({"fetched_at": fetched_at.isoformat(), "source": f"OpenStreetMap, Geofabrik extract {args.pbf.name}", "done_tiles": [], "places": list(rows.values())}, ensure_ascii=False),
        encoding="utf-8",
    )
    kinds: dict[str, int] = {}
    for r in rows.values():
        kinds[r["kind"]] = kinds.get(r["kind"], 0) + 1
    print(f"{seen} tagged objects read -> {len(rows)} places written to {args.out} (data from {fetched_at:%Y-%m-%d}): {kinds}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
