"""Scientifically defensible negative (non-landslide) sampling for the
road-corridor susceptibility model.

Why a road corridor, not random points across Sikkim (see ml_config.py for
the full rationale): the GSI inventory is 96.1% within 100m of a mapped
road -- a field-survey artifact, not evidence that susceptibility itself is
road-proximate. Sampling negatives uniformly across the state would let a
model "win" by learning distance-to-road instead of real terrain signal.
Constraining both positives and negatives to the same road corridor keeps
the comparison honest, and matches this project's own road-connectivity
framing intentionally, not as a workaround.

Method:
1. Buffer the road network by `corridor_buffer_m` -> the full sampling corridor.
2. Remove a `exclusion_buffer_m` disc around every positive point (all of
   them, not just the current district's) -- avoids sampling the same
   failure zone as a documented event.
3. For each district, further restrict to that district's own positive
   points buffered by `district_hull_buffer_m`, intersected with the
   corridor -- this is how per-district proportions are preserved without
   needing external administrative boundary polygons.
4. Rejection-sample points uniformly within each district's region, seeded
   for reproducibility.

Known limitation: negatives mean "not yet documented in this inventory," not
"proven non-susceptible." This is presence-only data; false negatives
(undocumented slides) are expected, especially near the corridor edges.
"""
import numpy as np
import pandas as pd
import pyproj
from shapely.geometry import Point
from shapely.ops import unary_union

from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig
from scripts.ml.fetch_osm_roads import load_roads

WGS84 = "EPSG:4326"


def to_utm_points(lons, lats, target_crs: str) -> list[Point]:
    transformer = pyproj.Transformer.from_crs(WGS84, target_crs, always_xy=True)
    xs, ys = transformer.transform(lons, lats)
    return [Point(x, y) for x, y in zip(xs, ys)]


def to_wgs84_lonlat(points: list[Point], source_crs: str) -> tuple[list[float], list[float]]:
    transformer = pyproj.Transformer.from_crs(source_crs, WGS84, always_xy=True)
    lons, lats = [], []
    for p in points:
        lon, lat = transformer.transform(p.x, p.y)
        lons.append(lon)
        lats.append(lat)
    return lons, lats


def build_road_corridor(roads_utm_geoms, buffer_m: float):
    """roads_utm_geoms: iterable of shapely LineStrings already in a metric CRS."""
    return unary_union([line.buffer(buffer_m) for line in roads_utm_geoms])


def build_exclusion_zone(positive_points_utm: list[Point], exclusion_m: float):
    return unary_union([p.buffer(exclusion_m) for p in positive_points_utm])


def build_sampling_region(full_corridor, exclusion_zone):
    """Corridor with a disc removed around every known positive."""
    return full_corridor.difference(exclusion_zone)


def build_district_region(sampling_region, district_positive_points_utm: list[Point], hull_buffer_m: float):
    """Restricts the (already exclusion-cleared) corridor to the area near
    this specific district's positives, so negatives stay geographically
    matched to where that district was actually surveyed."""
    if not district_positive_points_utm:
        return sampling_region.buffer(0).intersection(Point(0, 0).buffer(0))  # empty geometry
    district_hull = unary_union([p.buffer(hull_buffer_m) for p in district_positive_points_utm])
    return sampling_region.intersection(district_hull)


def rejection_sample_points(polygon, n: int, rng: np.random.Generator, max_attempts: int = 20000) -> list[Point]:
    """Uniform rejection sampling within an arbitrary polygon's bounding box.
    Returns fewer than n (with the shortfall left to the caller to report)
    rather than looping forever if the polygon is too small/thin for the
    requested count."""
    if polygon.is_empty or n <= 0:
        return []

    minx, miny, maxx, maxy = polygon.bounds
    points: list[Point] = []
    attempts = 0
    while len(points) < n and attempts < max_attempts:
        batch = min(max(n - len(points), 1) * 4, 2000)
        xs = rng.uniform(minx, maxx, batch)
        ys = rng.uniform(miny, maxy, batch)
        attempts += batch
        for x, y in zip(xs, ys):
            if len(points) >= n:
                break
            candidate = Point(x, y)
            if polygon.contains(candidate):
                points.append(candidate)
    return points


def build_negative_samples(
    positives_df: pd.DataFrame, config: MlConfig = DEFAULT_CONFIG, roads_gdf=None
) -> pd.DataFrame:
    """positives_df must have columns: Latitude, Longitude, District.
    Returns a DataFrame with columns: latitude, longitude, district, label=0.
    """
    target_crs = config.dem.target_crs
    rng = np.random.default_rng(config.sampling.random_seed)

    if roads_gdf is None:
        roads_gdf = load_roads(config)
    roads_utm = roads_gdf.to_crs(target_crs).geometry.tolist()

    all_positive_points_utm = to_utm_points(positives_df["Longitude"], positives_df["Latitude"], target_crs)

    full_corridor = build_road_corridor(roads_utm, config.sampling.corridor_buffer_m)
    exclusion_zone = build_exclusion_zone(all_positive_points_utm, config.sampling.exclusion_buffer_m)
    sampling_region = build_sampling_region(full_corridor, exclusion_zone)

    positives_df = positives_df.copy()
    positives_df["_utm_point"] = all_positive_points_utm

    rows = []
    for district, group in positives_df.groupby("District"):
        n_target = round(len(group) * config.sampling.ratio)
        district_region = build_district_region(
            sampling_region, group["_utm_point"].tolist(), config.sampling.district_hull_buffer_m
        )
        sampled = rejection_sample_points(district_region, n_target, rng)
        if len(sampled) < n_target:
            print(
                f"WARNING: district {district!r} wanted {n_target} negatives, "
                f"only found room for {len(sampled)} within the corridor."
            )
        lons, lats = to_wgs84_lonlat(sampled, target_crs)
        for lon, lat in zip(lons, lats):
            rows.append({"latitude": lat, "longitude": lon, "district": district, "label": 0})

    return pd.DataFrame(rows)


def main(config: MlConfig = DEFAULT_CONFIG) -> None:
    positives = pd.read_csv(config.paths.gsi_sikkim_csv)
    negatives = build_negative_samples(positives, config)
    config.paths.negatives_csv.parent.mkdir(parents=True, exist_ok=True)
    negatives.to_csv(config.paths.negatives_csv, index=False)
    print(f"generated {len(negatives)} negatives -> {config.paths.negatives_csv}")
    print(negatives["district"].value_counts())


if __name__ == "__main__":
    main()
