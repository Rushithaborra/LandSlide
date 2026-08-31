"""Seed one pilot zone from a GeoJSON Polygon file — for handing the frontend
and ML leads something real to point at once the pilot area is finalized.

Deliberately does NOT hardcode any coordinates: the roadmap doc recommends
Sikkim or Mizoram but the team hasn't picked the exact pilot zone boundary
yet (that's Data/GIS lead's call, from real GSI/QGIS work). Point this at
that real boundary once it exists — see config/pilot_zone.example.geojson
for the expected shape (a placeholder square in the Gulf of Guinea, at
0,0 — obviously not a real place, just showing the file format).

Usage:
    python scripts/seed_zone.py <path-to-geojson> "<zone name>"
"""
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from geoalchemy2.shape import from_shape
from shapely.geometry import shape

from app.database import SessionLocal
from app.models import Zone


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        print("Error: expected exactly 2 arguments (geojson path, zone name).")
        sys.exit(1)

    geojson_path, zone_name = pathlib.Path(sys.argv[1]), sys.argv[2]
    if not geojson_path.exists():
        print(f"Error: {geojson_path} not found. This script will not invent a geometry for you —")
        print("supply a real Polygon GeoJSON file once the pilot zone boundary is finalized.")
        sys.exit(1)

    geojson = json.loads(geojson_path.read_text())
    if geojson.get("type") != "Polygon":
        print(f"Error: expected a GeoJSON Polygon, got {geojson.get('type')!r}.")
        sys.exit(1)

    polygon = shape(geojson)
    db = SessionLocal()
    try:
        zone = Zone(name=zone_name, geometry=from_shape(polygon, srid=4326))
        db.add(zone)
        db.commit()
        db.refresh(zone)
        print(f"Seeded zone {zone.id} ({zone_name!r}) from {geojson_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
