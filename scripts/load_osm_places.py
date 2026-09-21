"""Load the OpenStreetMap snapshot from scripts/fetch_osm_places.py into the `places` table.

    python scripts/load_osm_places.py [data/interim/osm_places.json]

An upsert by OpenStreetMap id, so it can be re-run with a newer or partial snapshot
(nothing is deleted: a place missing from a later, partial download is kept).
"""
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.database import SessionLocal
from app.models import Place

CHUNK = 2000
ALLOWED_KINDS = {"village", "town", "city", "hospital", "clinic", "police", "fire_station"}  # the table's CHECK


def main() -> int:
    path = Path(sys.argv[1] if len(sys.argv) > 1 else "data/interim/osm_places.json")
    snapshot = json.loads(path.read_text(encoding="utf-8"))
    fetched_at = datetime.fromisoformat(snapshot["fetched_at"])
    rows = [
        {"osm_id": p["osm_id"], "kind": p["kind"], "name": p["name"], "lat": p["lat"], "lng": p["lng"], "phone": p.get("phone"), "fetched_at": fetched_at}
        for p in snapshot["places"]
        if p["kind"] in ALLOWED_KINDS  # an older download may hold other place=* kinds (e.g. city_block)
    ]
    skipped = len(snapshot["places"]) - len(rows)
    if skipped:
        print(f"skipping {skipped} records whose kind is not one the table accepts")
    with SessionLocal() as db:
        for i in range(0, len(rows), CHUNK):
            chunk = rows[i : i + CHUNK]
            stmt = pg_insert(Place).values(chunk)
            db.execute(stmt.on_conflict_do_update(
                index_elements=[Place.osm_id],
                set_={c: stmt.excluded[c] for c in ("kind", "name", "lat", "lng", "phone", "fetched_at")},
            ))
        db.commit()
        total = db.query(Place).count()
    print(f"loaded {len(rows)} places from {path} (snapshot {fetched_at:%Y-%m-%d}); table now holds {total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
