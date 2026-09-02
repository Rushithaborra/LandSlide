"""
Day 1 (Role A): pull Sikkim roads from OpenStreetMap (Overpass API) for the
dashboard's context layer, and independently verify the road-proximity bias
claim in the onboarding doc (96.1% of landslide points within 100m of a road).

Outputs:
  data/raw/sikkim_roads.geojson
  prints the measured road-proximity percentage for comparison against the doc
"""
import json
import urllib.request
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import shape, LineString
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
# Sikkim's actual bbox (27.079-28.129N, 88.013-88.920E) + ~0.05deg (~5km) margin.
# The originally-tried 26.9-28.2N,87.9-89.0E margin pulled in far more of
# West Bengal/Bhutan than needed and made the response too large to
# reliably finish downloading.
BBOX = "27.03,87.96,28.18,88.97"  # south,west,north,east

# Restrict to drivable road classes. An unfiltered highway=* query in Sikkim
# pulls in the region's huge network of trekking footpaths/tracks around
# Kangchenjunga, which bloated the response past what the connection could
# reliably finish downloading (repeated IncompleteRead/502/504 on the full
# highway=* query).
ROAD_CLASSES = (
    "motorway|trunk|primary|secondary|tertiary|unclassified|residential|service"
)
QUERY = f"""
[out:json][timeout:120];
way["highway"~"^({ROAD_CLASSES})$"]({BBOX});
out geom;
"""


def fetch_roads():
    data = urllib.parse.urlencode({"data": QUERY}).encode()
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
                print(f"  {url} attempt {attempt+1} failed: {e}")
                last_err = e
    raise last_err


def osm_to_geojson(osm):
    features = []
    for el in osm.get("elements", []):
        if el["type"] != "way" or "geometry" not in el:
            continue
        coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
        if len(coords) < 2:
            continue
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {"osm_id": el["id"], "highway": el.get("tags", {}).get("highway")},
            }
        )
    return {"type": "FeatureCollection", "features": features}


def main():
    print("Querying Overpass API for Sikkim roads...")
    osm = fetch_roads()
    roads_gj = osm_to_geojson(osm)
    print(f"  got {len(roads_gj['features'])} road segments")

    roads_path = RAW / "sikkim_roads.geojson"
    with open(roads_path, "w") as f:
        json.dump(roads_gj, f)
    print(f"Wrote {roads_path}")

    print("\nChecking road-proximity bias claim (doc says 96.1% within 100m)...")
    with open(RAW / "gsi_sikkim_landslides_raw.geojson") as f:
        landslides = json.load(f)

    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)

    road_lines_utm = []
    for feat in roads_gj["features"]:
        coords = [to_utm.transform(lon, lat) for lon, lat in feat["geometry"]["coordinates"]]
        road_lines_utm.append(LineString(coords))

    if not road_lines_utm:
        print("  No road geometries returned -- cannot verify.")
        return

    tree = STRtree(road_lines_utm)

    within_100m = 0
    total = 0
    distances = []
    for feat in landslides["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        x, y = to_utm.transform(lon, lat)
        from shapely.geometry import Point
        pt = Point(x, y)
        nearest_idx = tree.nearest(pt)
        nearest_line = road_lines_utm[nearest_idx]
        dist = pt.distance(nearest_line)
        distances.append(dist)
        total += 1
        if dist <= 100:
            within_100m += 1

    pct = 100 * within_100m / total
    distances = np.array(distances)
    print(f"  {within_100m} / {total} landslide points within 100m of a road = {pct:.1f}%")
    print(f"  (doc claims 96.1% -- {'CONSISTENT' if abs(pct - 96.1) < 5 else 'DIVERGES, investigate'})")
    print(f"  median distance to nearest road: {np.median(distances):.1f} m")
    print(f"  90th percentile distance: {np.percentile(distances, 90):.1f} m")


if __name__ == "__main__":
    import urllib.parse
    main()
