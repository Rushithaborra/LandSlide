"""
Day 2 (Role A - Data/GIS): generate negative (non-landslide) samples.

Critical constraint from the onboarding doc (Section 8): negative samples
must match the positive samples' road-proximity distribution, or the model
just learns "near a road = risky" (the survey artifact), not real terrain
risk.

Method: bootstrap-resample the *actual* empirical distance-to-road values
measured from the 768 positive points (scripts/03), then for each drawn
target distance, place a candidate point near a randomly-chosen road
segment (weighted by segment length, so busier road corridors get sampled
proportionally) at approximately that distance, in a random direction.
Reject candidates that fall outside Sikkim, too close to a known landslide
(label leakage), or too far off the target distance after the nearest-road
recheck.

Output: data/raw/sikkim_negative_samples.csv (lon, lat, distance_to_road_m)
"""
import json
import random
from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import shape, Point, LineString
from shapely.strtree import STRtree

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

N_NEGATIVE = 768  # match positive count, 1:1 balanced classes
EXCLUSION_BUFFER_M = 100  # keep negatives at least this far from any real landslide
MAX_ATTEMPTS_PER_SAMPLE = 60

random.seed(42)
np.random.seed(42)


def load_utm_geoms():
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)
    to_wgs = Transformer.from_crs("EPSG:32645", "EPSG:4326", always_xy=True)

    with open(RAW / "sikkim_boundary.geojson") as f:
        boundary_gj = json.load(f)
    boundary_wgs = shape(boundary_gj["features"][0]["geometry"])
    boundary_utm_coords = [
        [to_utm.transform(x, y) for x, y in ring]
        for ring in _polygon_rings(boundary_wgs)
    ]
    from shapely.geometry import Polygon
    boundary_utm = Polygon(boundary_utm_coords[0], boundary_utm_coords[1:])

    with open(RAW / "sikkim_roads.geojson") as f:
        roads_gj = json.load(f)
    road_lines = []
    for feat in roads_gj["features"]:
        coords = [to_utm.transform(lon, lat) for lon, lat in feat["geometry"]["coordinates"]]
        if len(coords) >= 2:
            road_lines.append(LineString(coords))

    with open(RAW / "gsi_sikkim_landslides_raw.geojson") as f:
        landslides_gj = json.load(f)
    positive_pts_utm = []
    for feat in landslides_gj["features"]:
        lon, lat = feat["geometry"]["coordinates"]
        positive_pts_utm.append(Point(to_utm.transform(lon, lat)))

    return to_utm, to_wgs, boundary_utm, road_lines, positive_pts_utm


def _polygon_rings(geom):
    if geom.geom_type == "Polygon":
        return [list(geom.exterior.coords)] + [list(r.coords) for r in geom.interiors]
    # MultiPolygon: use the largest ring set (Sikkim is a single polygon, but be safe)
    largest = max(geom.geoms, key=lambda g: g.area)
    return [list(largest.exterior.coords)] + [list(r.coords) for r in largest.interiors]


def empirical_positive_distances(positive_pts_utm, road_tree, road_lines):
    dists = []
    for pt in positive_pts_utm:
        idx = road_tree.nearest(pt)
        dists.append(pt.distance(road_lines[idx]))
    return np.array(dists)


def sample_point_near_road(road_lines, road_weights, road_tree, target_dist, refine_iters=4):
    """Place a point at ~target_dist from its TRUE nearest road.

    A naive version anchors to one randomly-chosen road segment and offsets
    by target_dist in a random direction -- but in a dense network the
    candidate's actual nearest road is often a *different*, closer segment,
    which systematically biases measured distances well below target (this
    was caught empirically: negatives came out at roughly half the positives'
    distance at every percentile). Iterating against the real nearest-road
    lookup each step converges on the intended distance instead.
    """
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


def main():
    print("Loading boundary, roads, positive points (UTM)...")
    to_utm, to_wgs, boundary_utm, road_lines, positive_pts_utm = load_utm_geoms()
    print(f"  {len(road_lines)} road segments, {len(positive_pts_utm)} positive points")

    road_tree = STRtree(road_lines)
    road_weights = [line.length for line in road_lines]

    print("Computing empirical road-distance distribution for positives...")
    pos_dists = empirical_positive_distances(positive_pts_utm, road_tree, road_lines)
    print(f"  median {np.median(pos_dists):.1f}m, 90th pct {np.percentile(pos_dists, 90):.1f}m")

    positive_tree = STRtree(positive_pts_utm)

    print(f"Generating {N_NEGATIVE} negative samples...")
    negatives = []
    rejects = {"outside_boundary": 0, "too_near_positive": 0, "distance_mismatch": 0}

    while len(negatives) < N_NEGATIVE:
        target_dist = float(np.random.choice(pos_dists)) * np.random.uniform(0.85, 1.15)
        target_dist = max(target_dist, 0.5)

        accepted = False
        for _ in range(MAX_ATTEMPTS_PER_SAMPLE):
            candidate = sample_point_near_road(road_lines, road_weights, road_tree, target_dist)

            if not boundary_utm.contains(candidate):
                rejects["outside_boundary"] += 1
                continue

            nearest_pos_idx = positive_tree.nearest(candidate)
            if candidate.distance(positive_pts_utm[nearest_pos_idx]) < EXCLUSION_BUFFER_M:
                rejects["too_near_positive"] += 1
                continue

            nearest_road_idx = road_tree.nearest(candidate)
            actual_dist = candidate.distance(road_lines[nearest_road_idx])
            if abs(actual_dist - target_dist) > max(5, target_dist * 0.15):
                rejects["distance_mismatch"] += 1
                continue

            lon, lat = to_wgs.transform(candidate.x, candidate.y)
            negatives.append({"lon": lon, "lat": lat, "distance_to_road_m": actual_dist})
            accepted = True
            break

        if not accepted:
            continue  # retry with a freshly drawn target_dist

    out_path = RAW / "sikkim_negative_samples.csv"
    with open(out_path, "w") as f:
        f.write("Longitude,Latitude,Distance_To_Road_M\n")
        for n in negatives:
            f.write(f"{n['lon']:.6f},{n['lat']:.6f},{n['distance_to_road_m']:.1f}\n")
    print(f"Wrote {out_path} ({len(negatives)} rows)")
    print(f"  rejections during search: {rejects}")

    neg_dists = np.array([n["distance_to_road_m"] for n in negatives])
    print("\nDistribution match check (negative vs. positive road-distance):")
    for p in [10, 25, 50, 75, 90]:
        print(f"  p{p}: negative={np.percentile(neg_dists, p):.1f}m  positive={np.percentile(pos_dists, p):.1f}m")
    within_100_neg = 100 * np.sum(neg_dists <= 100) / len(neg_dists)
    print(f"  % within 100m: negative={within_100_neg:.1f}%  positive={100*np.sum(pos_dists<=100)/len(pos_dists):.1f}%")


if __name__ == "__main__":
    main()
