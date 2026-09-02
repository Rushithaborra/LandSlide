"""
Day 3-4 (Role A/D support): non-blocking dashboard context layers --
villages, buildings, hospitals/schools -- all via OSM Overpass.

Learned from scripts/03 (roads): keep queries scoped to Sikkim's actual
bbox + small margin, not the wider one the docs suggested, or responses
get large enough to fail mid-download.

Outputs:
  data/raw/sikkim_villages.geojson
  data/raw/sikkim_buildings.geojson   (may be large/patchy in rural areas -- known limitation)
  data/raw/sikkim_health_edu.geojson  (hospitals + schools)
"""
import json
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
BBOX = "27.03,87.96,28.18,88.97"


def run_query(query, label):
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err = None
    for url in OVERPASS_URLS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(
                    url, data=data, headers={"User-Agent": "sih-landslide-ews-data-pipeline/1.0"}
                )
                with urllib.request.urlopen(req, timeout=180) as resp:
                    return json.load(resp)
            except Exception as e:
                print(f"  [{label}] {url} attempt {attempt+1} failed: {e}")
                last_err = e
    raise last_err


def to_geojson(osm, geom_types=("node", "way")):
    features = []
    for el in osm.get("elements", []):
        tags = el.get("tags", {})
        if el["type"] == "node":
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        elif el["type"] == "way" and "geometry" in el:
            coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
            if len(coords) < 2:
                continue
            geom = {"type": "LineString", "coordinates": coords}
        elif el["type"] == "way" and "center" in el:
            geom = {"type": "Point", "coordinates": [el["center"]["lon"], el["center"]["lat"]]}
        else:
            continue
        features.append({"type": "Feature", "geometry": geom, "properties": {"osm_id": el["id"], **tags}})
    return {"type": "FeatureCollection", "features": features}


def fetch_villages():
    query = f"""
    [out:json][timeout:120];
    node["place"="village"]({BBOX});
    out body;
    """
    osm = run_query(query, "villages")
    gj = to_geojson(osm)
    path = RAW / "sikkim_villages.geojson"
    with open(path, "w") as f:
        json.dump(gj, f)
    print(f"Wrote {path} ({len(gj['features'])} villages)")


def fetch_buildings():
    query = f"""
    [out:json][timeout:180];
    way["building"]({BBOX});
    out center;
    """
    osm = run_query(query, "buildings")
    gj = to_geojson(osm)
    path = RAW / "sikkim_buildings.geojson"
    with open(path, "w") as f:
        json.dump(gj, f)
    print(f"Wrote {path} ({len(gj['features'])} buildings)")


def fetch_health_edu():
    query = f"""
    [out:json][timeout:120];
    (
      node["amenity"="hospital"]({BBOX});
      node["amenity"="clinic"]({BBOX});
      node["amenity"="school"]({BBOX});
      way["amenity"="hospital"]({BBOX});
      way["amenity"="school"]({BBOX});
    );
    out center;
    """
    osm = run_query(query, "health_edu")
    gj = to_geojson(osm)
    path = RAW / "sikkim_health_edu.geojson"
    with open(path, "w") as f:
        json.dump(gj, f)
    print(f"Wrote {path} ({len(gj['features'])} hospitals/clinics/schools)")


if __name__ == "__main__":
    print("Fetching villages...")
    fetch_villages()
    print("Fetching hospitals/schools...")
    fetch_health_edu()
    print("Fetching buildings (largest query, expect it to take longest)...")
    fetch_buildings()
