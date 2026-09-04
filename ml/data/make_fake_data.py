"""
Generates a FAKE practice dataset that mimics the shape of what Person A
(Data/GIS lead) will eventually hand off: one row per location, with terrain
feature columns + a label (1 = landslide happened here, 0 = it didn't).

Purpose: let the training/validation pipeline (train_model.py) be built and
tested end-to-end BEFORE real Sikkim data exists. When A's real CSV arrives,
swap the file path in train_model.py — nothing else should need to change,
as long as the real CSV uses the same column names defined here.

Run: python make_fake_data.py
Output: fake_landslide_data.csv in this same folder.
"""

import numpy as np
import pandas as pd

RNG = np.random.default_rng(seed=42)
N_LANDSLIDE_POINTS = 150   # pretend GSI inventory size for practice
N_NEGATIVE_POINTS = 150    # matched "safe" points (see negative_sampling.py)

# Sikkim's real bounding box (rough), just so fake lat/lon look plausible
LAT_RANGE = (27.0, 28.2)
LON_RANGE = (88.0, 88.9)

LITHOLOGY_CLASSES = ["gneiss", "phyllite", "schist", "quartzite", "alluvium"]
LANDUSE_CLASSES = ["forest", "agriculture", "built-up", "barren", "scrub"]


def make_landslide_points(n):
    """Positive class: steeper slopes, higher drainage density on average —
    mimics the real-world pattern the model should learn to pick up on."""
    return pd.DataFrame({
        "lat": RNG.uniform(*LAT_RANGE, n),
        "lon": RNG.uniform(*LON_RANGE, n),
        "elevation": RNG.normal(2200, 500, n).clip(200, 5000),
        "slope_deg": RNG.normal(38, 10, n).clip(0, 80),
        "aspect_deg": RNG.uniform(0, 360, n),
        "drainage_density": RNG.normal(0.7, 0.15, n).clip(0, 1),
        "lithology": RNG.choice(LITHOLOGY_CLASSES, n, p=[0.25, 0.3, 0.25, 0.1, 0.1]),
        "landuse": RNG.choice(LANDUSE_CLASSES, n, p=[0.3, 0.25, 0.15, 0.2, 0.1]),
        "mean_annual_rainfall_mm": RNG.normal(3200, 400, n),
        "label": 1,
    })


def make_negative_points(n):
    """Negative class: gentler slopes, lower drainage density on average.
    In the REAL pipeline this comes from negative_sampling.py (random points
    with a buffer around known landslides) — this fake version just draws
    from a different distribution to simulate that contrast."""
    return pd.DataFrame({
        "lat": RNG.uniform(*LAT_RANGE, n),
        "lon": RNG.uniform(*LON_RANGE, n),
        "elevation": RNG.normal(1600, 500, n).clip(200, 5000),
        "slope_deg": RNG.normal(15, 8, n).clip(0, 80),
        "aspect_deg": RNG.uniform(0, 360, n),
        "drainage_density": RNG.normal(0.35, 0.15, n).clip(0, 1),
        "lithology": RNG.choice(LITHOLOGY_CLASSES, n, p=[0.15, 0.15, 0.15, 0.2, 0.35]),
        "landuse": RNG.choice(LANDUSE_CLASSES, n, p=[0.35, 0.3, 0.15, 0.1, 0.1]),
        "mean_annual_rainfall_mm": RNG.normal(2800, 400, n),
        "label": 0,
    })


if __name__ == "__main__":
    df = pd.concat([
        make_landslide_points(N_LANDSLIDE_POINTS),
        make_negative_points(N_NEGATIVE_POINTS),
    ], ignore_index=True)
    df = df.sample(frac=1, random_state=42).reset_index(drop=True)  # shuffle
    df.insert(0, "sample_id", [f"S-{i:04d}" for i in range(len(df))])

    out_path = "fake_landslide_data.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df)} rows to {out_path}")
    print(df.head())
