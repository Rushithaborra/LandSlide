"""
Turns a (lat, lon) into the same feature dict the model was trained on, by
sampling the raster layers at that point -- the same rasters and method used
in data/build_negative_features.py and scripts/15_build_handoff_csv.py, so a
live prediction is measured identically to the training data. If this used a
different sampling method, any accuracy difference between training and live
predictions could just be a measurement mismatch, not a real model problem.

The dashboard/backend only has coordinates -- it doesn't know Sikkim's slope
or rainfall at an arbitrary point. This module is the bridge: point in,
terrain features out. app.py then hands those features to the trained model.
"""

from pathlib import Path

import rasterio
from pyproj import Transformer

REPO_ROOT = Path(__file__).resolve().parents[2]
RASTER_DIR = REPO_ROOT / "data" / "processed"
NODATA = -9999.0

LANDUSE_NAMES = {
    10: "forest", 20: "shrubland", 30: "grassland", 40: "cropland",
    50: "built-up", 60: "bare/sparse vegetation", 70: "snow/ice",
    80: "water", 90: "wetland", 95: "mangroves", 100: "moss/lichen",
}

RASTERS = {
    "elevation": (RASTER_DIR / "dem_sikkim_utm45n.tif", NODATA),
    "slope_deg": (RASTER_DIR / "slope_deg.tif", NODATA),
    "aspect_deg": (RASTER_DIR / "aspect_deg.tif", NODATA),
    "drainage_density": (RASTER_DIR / "drainage_density.tif", NODATA),
    "landuse_code": (RASTER_DIR / "landcover_sikkim_utm45n.tif", 255),
    "mean_annual_rainfall_mm": (RASTER_DIR / "mean_annual_rainfall_mm.tif", NODATA),
    "distance_to_drainage": (RASTER_DIR / "distance_to_stream_m.tif", NODATA),
    "curvature": (RASTER_DIR / "curvature.tif", NODATA),
    "terrain_ruggedness": (RASTER_DIR / "terrain_ruggedness.tif", NODATA),
}

_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:32645", always_xy=True)


class OutOfCoverageError(Exception):
    """Raised when a point falls outside Sikkim / outside all rasters' data area."""


def get_features_at_point(lat: float, lon: float) -> dict:
    x, y = _to_utm.transform(lon, lat)

    raw = {}
    for col, (path, nodata_val) in RASTERS.items():
        with rasterio.open(path) as src:
            val = float(next(src.sample([(x, y)]))[0])
            raw[col] = None if val == nodata_val else val

    required = ["elevation", "slope_deg", "aspect_deg", "drainage_density",
                "landuse_code", "mean_annual_rainfall_mm"]
    missing = [c for c in required if raw[c] is None]
    if missing:
        raise OutOfCoverageError(
            f"({lat}, {lon}) is outside Sikkim's data coverage -- missing: {missing}"
        )

    return {
        "elevation": raw["elevation"],
        "slope_deg": raw["slope_deg"],
        "aspect_deg": raw["aspect_deg"],
        "drainage_density": raw["drainage_density"],
        "mean_annual_rainfall_mm": raw["mean_annual_rainfall_mm"],
        "curvature": raw["curvature"] if raw["curvature"] is not None else 0.0,
        "distance_to_drainage": raw["distance_to_drainage"] if raw["distance_to_drainage"] is not None else 0.0,
        "terrain_ruggedness": raw["terrain_ruggedness"] if raw["terrain_ruggedness"] is not None else 0.0,
        "landuse": LANDUSE_NAMES.get(int(raw["landuse_code"]), "unknown"),
    }


if __name__ == "__main__":
    # Quick manual check: Gangtok (should be inside Sikkim's coverage)
    feats = get_features_at_point(lat=27.3389, lon=88.6065)
    print("Features at Gangtok (27.3389, 88.6065):")
    for k, v in feats.items():
        print(f"  {k}: {v}")
