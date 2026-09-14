"""
Generalized version of scripts/03 (OSM roads + road-proximity bias check)
and 04 (bias-matched negative sampling), parameterized by state via
ner_config.STATE_CONFIGS.

Usage: python3 scripts/19_fetch_state_roads_and_negatives.py <state_slug>

Same method as Sikkim's: query Overpass for drivable road classes only
(motorway..service, excluding footpaths/tracks -- an unfiltered highway=*
query is what caused repeated IncompleteRead/502/504 failures in Sikkim's
own mountainous, trail-dense terrain), independently measure this state's
own road-proximity bias (don't assume Sikkim's 97% figure transfers), then
generate negatives that match THIS state's own measured distribution.

Outputs:
  data/raw/<state>_roads.geojson
  data/raw/<state>_negative_samples.csv
  prints this state's own road-proximity bias measurement
"""
import json
import random
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import shape, Point, LineString, Polygon
from shapely.strtree import STRtree

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ner_config import STATE_CONFIGS

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
ROAD_CLASSES = "motorway|trunk|primary|secondary|tertiary|unclassified|residential|service"
EXCLUSION_BUFFER_M = 100
MAX_ATTEMPTS_PER_SAMPLE = 60

random.seed(42)
np.random.seed(42)


def _query_bbox(south, west, north, east):
    query = f"""
    [out:json][timeout:180];
    way["highway"~"^({ROAD_CLASSES})$"]({south},{west},{north},{east});
    out geom;
    """
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err = None
    for url in OVERPASS_URLS:
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, data=data, headers={"User-Agent": "sih-landslide-ews-data-pipeline/1.0"})
                with urllib.request.urlopen(req, timeout=240) as resp:
                    return json.load(resp)
            except Exception as e:
                print(f"  {url} attempt {attempt+1} failed: {e}")
                last_err = e
    raise last_err


def fetch_roads(bbox, margin=0.05):
    minx, miny, maxx, maxy = bbox
    south, west, north, east = miny - margin, minx - margin, maxy + margin, maxx + margin
    try:
        return _query_bbox(south, west, north, east)
    except Exception as e:
        # A large state's full-bbox query can produce a response big enough
        # that Overpass's own server times out generating it (504) --
        # retrying the identical query just hits the same server-side limit
        # again (observed on Assam: 4 straight failures across both
        # mirrors). Split into a 2x2 grid of sub-queries and merge instead
        # -- each quadrant is a quarter the data, so if the whole-state
        # query is the problem, this gets past it.
        print(f"  whole-bbox query failed ({e}) -- falling back to 2x2 quadrant split")
        mid_lat, mid_lon = (south + north) / 2, (west + east) / 2
        quadrants = [
            (south, west, mid_lat, mid_lon), (south, mid_lon, mid_lat, east),
            (mid_lat, west, north, mid_lon), (mid_lat, mid_lon, north, east),
        ]
        merged_elements = {}
        for i, (s, w, n, e2) in enumerate(quadrants):
            print(f"  quadrant {i+1}/4: ({s:.2f},{w:.2f})-({n:.2f},{e2:.2f})")
            result = _query_bbox(s, w, n, e2)
            for el in result.get("elements", []):
                merged_elements[el["id"]] = el  # dedup ways spanning quadrant boundaries
        return {"elements": list(merged_elements.values())}


def osm_to_geojson(osm):
    features = []
    for el in osm.get("elements", []):
        if el["type"] != "way" or "geometry" not in el:
            continue
        coords = [[pt["lon"], pt["lat"]] for pt in el["geometry"]]
        if len(coords) < 2:
            continue
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
                          "properties": {"osm_id": el["id"], "highway": el.get("tags", {}).get("highway")}})
    return {"type": "FeatureCollection", "features": features}


def polygon_rings(geom):
    if geom.geom_type == "Polygon":
        return [list(geom.exterior.coords)] + [list(r.coords) for r in geom.interiors]
    largest = max(geom.geoms, key=lambda g: g.area)
    return [list(largest.exterior.coords)] + [list(r.coords) for r in largest.interiors]


def sample_point_near_road(road_lines, road_weights, road_tree, target_dist, refine_iters=4):
    line = random.choices(road_lines, weights=road_weights, k=1)[0]
    anchor = line.interpolate(random.random(), normalized=True)
    angle = random.uniform(0, 2 * np.pi)
    point = Point(anchor.x + target_dist * np.cos(angle), anchor.y + target_dist * np.sin(angle))
    for _ in range(refine_iters):
        nearest_idx = road_tree.nearest(point)
        nearest_line = road_lines[nearest_idx]
        nearest_pt = nearest_line.interpolate(nearest_line.project(point))
        dx, dy = point.x - nearest_pt.x, point.y - nearest_pt.y
        dist = (dx ** 2 + dy ** 2) ** 0.5
        if dist < 1e-6:
            angle = random.uniform(0, 2 * np.pi)
            dx, dy = np.cos(angle), np.sin(angle)
            dist = 1.0
        scale = target_dist / dist
        point = Point(nearest_pt.x + dx * scale, nearest_pt.y + dy * scale)
    return point


def run(slug):
    cfg = STATE_CONFIGS[slug]
    print(f"=== {cfg['display_name']} roads + negative sampling ===")

    roads_path = RAW / f"{slug}_roads.geojson"
    negatives_path = RAW / f"{slug}_negative_samples.csv"
    if roads_path.exists() and negatives_path.exists():
        # Overpass is the flakiest source in this whole pipeline (documented
        # repeatedly for Sikkim too) -- re-querying it on every retry of a
        # later-failing step is wasteful and, worse, adds load to an already
        # struggling public server. If a prior run already produced both
        # outputs, trust them and skip straight to reporting the bias
        # numbers from what's on disk, exactly like the DEM/WorldCover
        # tile caching in scripts/18.
        print(f"  {roads_path} and {negatives_path} already exist -- skipping Overpass fetch and re-sampling")
        with open(roads_path) as f:
            roads_gj = json.load(f)
        print(f"  loaded {len(roads_gj['features'])} cached road segments")
    else:
        print("Querying Overpass API for roads (drivable classes only)...")
        osm = fetch_roads(cfg["bbox"])
        roads_gj = osm_to_geojson(osm)
        print(f"  got {len(roads_gj['features'])} road segments")
        with open(roads_path, "w") as f:
            json.dump(roads_gj, f)
        print(f"  wrote {roads_path}")

    # UTM for metric distance work: use the state's real single zone if it
    # has one, otherwise its custom transverse Mercator (ner_config.py) --
    # never Sikkim's 45N.
    to_utm = Transformer.from_crs("EPSG:4326", cfg["dst_crs"], always_xy=True)
    to_wgs = Transformer.from_crs(cfg["dst_crs"], "EPSG:4326", always_xy=True)

    road_lines_utm = []
    for feat in roads_gj["features"]:
        coords = [to_utm.transform(lon, lat) for lon, lat in feat["geometry"]["coordinates"]]
        road_lines_utm.append(LineString(coords))
    if not road_lines_utm:
        raise RuntimeError(f"No road geometries returned for {slug} -- cannot do bias-matched negative sampling")
    road_tree = STRtree(road_lines_utm)
    road_weights = [line.length for line in road_lines_utm]

    with open(RAW / f"gsi_{slug}_landslides.csv") as f:
        import csv
        positives = list(csv.DictReader(f))
    positive_pts_utm = [Point(to_utm.transform(float(p["Longitude"]), float(p["Latitude"]))) for p in positives]

    print(f"\nMeasuring {cfg['display_name']}'s OWN road-proximity bias (not assuming Sikkim's 97% transfers)...")
    distances = []
    for pt in positive_pts_utm:
        idx = road_tree.nearest(pt)
        distances.append(pt.distance(road_lines_utm[idx]))
    distances = np.array(distances)
    within_100m = int(np.sum(distances <= 100))
    pct = 100 * within_100m / len(distances)
    print(f"  {within_100m}/{len(distances)} landslide points within 100m of a road = {pct:.1f}%")
    print(f"  median distance: {np.median(distances):.1f} m, 90th pct: {np.percentile(distances, 90):.1f} m")

    print(f"\nLoading {cfg['display_name']} boundary for negative-sample containment check...")
    with open(RAW / f"{slug}_boundary.geojson") as f:
        boundary_gj = json.load(f)
    boundary_wgs = shape(boundary_gj["features"][0]["geometry"])
    rings = polygon_rings(boundary_wgs)
    boundary_utm = Polygon([to_utm.transform(x, y) for x, y in rings[0]],
                            [[to_utm.transform(x, y) for x, y in r] for r in rings[1:]])

    positive_tree = STRtree(positive_pts_utm)
    n_negative = len(positive_pts_utm)  # 1:1 balanced classes, same as Sikkim

    print(f"\nGenerating {n_negative} negative samples matching {cfg['display_name']}'s own road-distance distribution...")
    negatives = []
    rejects = {"outside_boundary": 0, "too_near_positive": 0, "distance_mismatch": 0}
    guard = 0
    while len(negatives) < n_negative and guard < n_negative * 200:
        guard += 1
        target_dist = float(np.random.choice(distances)) * np.random.uniform(0.85, 1.15)
        target_dist = max(target_dist, 0.5)
        for _ in range(MAX_ATTEMPTS_PER_SAMPLE):
            candidate = sample_point_near_road(road_lines_utm, road_weights, road_tree, target_dist)
            if not boundary_utm.contains(candidate):
                rejects["outside_boundary"] += 1
                continue
            nearest_pos_idx = positive_tree.nearest(candidate)
            if candidate.distance(positive_pts_utm[nearest_pos_idx]) < EXCLUSION_BUFFER_M:
                rejects["too_near_positive"] += 1
                continue
            nearest_road_idx = road_tree.nearest(candidate)
            actual_dist = candidate.distance(road_lines_utm[nearest_road_idx])
            if abs(actual_dist - target_dist) > max(5, target_dist * 0.15):
                rejects["distance_mismatch"] += 1
                continue
            lon, lat = to_wgs.transform(candidate.x, candidate.y)
            negatives.append({"lon": lon, "lat": lat, "distance_to_road_m": actual_dist})
            break

    if len(negatives) < n_negative:
        print(f"  WARNING: only generated {len(negatives)}/{n_negative} negatives after {guard} attempts "
              f"-- state's road network may be too sparse for full 1:1 balance; using what was generated, not padding")

    out_path = RAW / f"{slug}_negative_samples.csv"
    with open(out_path, "w") as f:
        f.write("Longitude,Latitude,Distance_To_Road_M\n")
        for n in negatives:
            f.write(f"{n['lon']:.6f},{n['lat']:.6f},{n['distance_to_road_m']:.1f}\n")
    print(f"Wrote {out_path} ({len(negatives)} rows)")
    print(f"  rejections: {rejects}")

    neg_dists = np.array([n["distance_to_road_m"] for n in negatives])
    print("\nDistribution match check (negative vs. positive road-distance, this state's own numbers):")
    for p in [10, 25, 50, 75, 90]:
        print(f"  p{p}: negative={np.percentile(neg_dists, p):.1f}m  positive={np.percentile(distances, p):.1f}m")


if __name__ == "__main__":
    run(sys.argv[1])
