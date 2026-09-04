"""
Negative sampling — generates "safe" (non-landslide) points to train against.

This is explicitly the ML lead's job, not the Data/GIS lead's (see checklist
item #12). A gives you real landslide COORDINATES; you use them to generate
the negative class yourself.

Method (standard approach for this kind of model):
1. Scatter random points across the state's terrain.
2. Drop any random point that falls within BUFFER_METERS of a real landslide
   point — otherwise you might mislabel a landslide-adjacent spot as "safe,"
   which would teach the model the wrong thing.
3. What's left is your negative (label=0) class.

This can't run for real until A hands off actual landslide coordinates —
until then, this file documents + tests the method on a small fake example.
Once real coordinates arrive, call generate_negative_samples() with them. 

Needs: geopandas, shapely (already installed in this project's venv).
"""

import geopandas as gpd
import numpy as np
from shapely.geometry import Point

RNG = np.random.default_rng(seed=42)


def generate_negative_samples(
    landslide_gdf: gpd.GeoDataFrame,
    boundary_gdf: gpd.GeoDataFrame,
    n_samples: int,
    buffer_meters: float = 500,
    crs_metric: str = "EPSG:32645",  # UTM zone 45N — covers Sikkim, gives meters not degrees
) -> gpd.GeoDataFrame:
    """
    landslide_gdf: real landslide points from A (must have a geometry column)
    boundary_gdf: Sikkim state boundary polygon (from GADM/Survey of India)
    n_samples: how many negative points to generate (usually match landslide count)
    buffer_meters: exclusion radius around each landslide point
    crs_metric: a projected CRS so "meters" actually means meters (lat/lon degrees don't)
    """
    # Reproject to a metric CRS so buffering in meters is accurate
    landslide_m = landslide_gdf.to_crs(crs_metric)
    boundary_m = boundary_gdf.to_crs(crs_metric)

    # One combined "forbidden zone" = union of buffers around every landslide point
    exclusion_zone = landslide_m.geometry.buffer(buffer_meters).union_all()

    minx, miny, maxx, maxy = boundary_m.total_bounds
    boundary_shape = boundary_m.geometry.union_all()

    negative_points = []
    attempts = 0
    max_attempts = n_samples * 50  # safety valve so this can't loop forever

    while len(negative_points) < n_samples and attempts < max_attempts:
        attempts += 1
        candidate = Point(RNG.uniform(minx, maxx), RNG.uniform(miny, maxy))
        if not boundary_shape.contains(candidate):
            continue  # outside Sikkim, discard
        if exclusion_zone.contains(candidate):
            continue  # too close to a known landslide, discard
        negative_points.append(candidate)

    if len(negative_points) < n_samples:
        print(
            f"WARNING: only generated {len(negative_points)}/{n_samples} negative "
            f"points after {attempts} attempts — buffer may be too large relative "
            f"to state area, or boundary polygon may be wrong."
        )

    result = gpd.GeoDataFrame(geometry=negative_points, crs=crs_metric)
    result["label"] = 0
    return result.to_crs(landslide_gdf.crs)  # back to original CRS (likely EPSG:4326 lat/lon)


def _demo_with_fake_data():
    """Sanity-check the method on made-up points before real data exists.
    Run this file directly to see it work: python negative_sampling.py"""
    from shapely.geometry import box

    # Fake "Sikkim" bounding box and fake landslide points inside it
    fake_boundary = gpd.GeoDataFrame(
        geometry=[box(88.0, 27.0, 88.9, 28.2)], crs="EPSG:4326"
    )
    fake_landslides = gpd.GeoDataFrame(
        geometry=[Point(88.3 + RNG.uniform(-0.2, 0.2), 27.5 + RNG.uniform(-0.2, 0.2)) for _ in range(20)],
        crs="EPSG:4326",
    )

    negatives = generate_negative_samples(
        fake_landslides, fake_boundary, n_samples=20, buffer_meters=500
    )
    print(f"Generated {len(negatives)} negative sample points (demo/fake data).")
    print(negatives.head())


if __name__ == "__main__":
    _demo_with_fake_data()
