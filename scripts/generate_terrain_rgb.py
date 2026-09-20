"""
Phase 2 of the 3D terrain visualization: encodes the same real Sikkim DEM
already used in Phase 1 (data/processed/dem_sikkim_utm45n.tif) into a
Mapbox Terrain-RGB image, so deck.gl's TerrainLayer can build a real 3D
mesh from it (actual elevation geometry, not a flat image like Phase 1's
static hillshade).

Mapbox Terrain-RGB encoding (the standard deck.gl TerrainLayer expects,
via its elevationDecoder): elevation = -10000 + (R*65536 + G*256 + B) * 0.1
https://docs.mapbox.com/data/tilesets/reference/mapbox-terrain-rgb-v1/

Real Sikkim elevation range in this DEM: 0m - 8560m (matches Kanchenjunga's
real ~8586m summit) -- comfortably inside the format's encodable range, no
clipping needed.

Reuses Phase 1's real bounds (sikkim_hillshade_bounds.json, computed from
this same raster's own transform) rather than recomputing them, since it's
the same DEM file -- and reuses Phase 1's hillshade+risk-tier PNG as the
texture draped over this mesh, so Phase 2 adds real 3D geometry without
inventing any new imagery.
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DEM_PATH = ROOT / "data" / "processed" / "dem_sikkim_utm45n.tif"
BOUNDS_PATH = ROOT / "dashboard-app" / "public" / "sikkim_hillshade_bounds.json"
OUT_PATH = ROOT / "dashboard-app" / "public" / "sikkim_terrain_rgb.png"

ELEVATION_OFFSET = -10000.0
ELEVATION_SCALE = 0.1


def encode_terrain_rgb(elevation: np.ndarray) -> np.ndarray:
    value = np.round((elevation - ELEVATION_OFFSET) / ELEVATION_SCALE).astype(np.uint32)
    r = (value // 65536) % 256
    g = (value // 256) % 256
    b = value % 256
    rgb = np.stack([r, g, b], axis=-1).astype(np.uint8)
    return rgb


def main():
    with rasterio.open(DEM_PATH) as src:
        elevation = src.read(1)
        nodata = src.nodata

    if nodata is not None:
        elevation = np.where(elevation == nodata, 0.0, elevation)

    print(f"Real elevation range: {elevation.min():.1f}m - {elevation.max():.1f}m")

    rgb = encode_terrain_rgb(elevation)
    Image.fromarray(rgb, mode="RGB").save(OUT_PATH)
    print(f"Wrote {OUT_PATH} ({rgb.shape[1]}x{rgb.shape[0]})")

    if not BOUNDS_PATH.exists():
        raise SystemExit(
            f"{BOUNDS_PATH} not found -- run scripts/generate_hillshade_overlay.py "
            "first (Phase 1), this script reuses its real computed bounds."
        )
    print(f"Reusing real bounds from {BOUNDS_PATH} (same DEM, same transform).")


if __name__ == "__main__":
    main()
