"""
Fields Role B's handoff spec asks for that weren't derived yet:
  - drainage_density: a real hydrological metric (stream length per unit
    area in a local window), normalized 0-1 -- NOT the same thing as
    distance_to_stream_m (which is distance to nearest stream, already in
    the training table as `distance_to_drainage`-equivalent). B's "nice to
    have" list actually asks for both as separate columns.
  - curvature, terrain_ruggedness: explicitly listed as optional-tier, but
    cheap to derive from the DEM already on disk -- no reason to skip them.

Outputs:
  data/processed/drainage_density.tif   (0-1, moving-window stream fraction)
  data/processed/curvature.tif          (Laplacian of elevation, 1/m)
  data/processed/terrain_ruggedness.tif (TRI, Riley et al. 1999, meters)
"""
from pathlib import Path

import numpy as np
import rasterio
from scipy.ndimage import uniform_filter

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
DEM_PATH = PROCESSED / "dem_sikkim_utm45n.tif"
STREAMS_PATH = PROCESSED / "streams.tif"
NODATA = -9999.0

DRAINAGE_WINDOW_M = 500  # local neighborhood radius for density -- matches typical
                          # 1st/2nd-order catchment scale at this DEM's ~29m resolution


def compute_drainage_density():
    with rasterio.open(STREAMS_PATH) as src:
        streams = src.read(1)
        stream_nodata = src.nodata
        meta = src.meta.copy()
        pixel_size = src.transform[0]

    stream_binary = (streams == 1).astype(np.float32)
    window_px = max(3, int(round(DRAINAGE_WINDOW_M / pixel_size)))
    if window_px % 2 == 0:
        window_px += 1  # odd window for a centered kernel

    density = uniform_filter(stream_binary, size=window_px, mode="nearest")

    with rasterio.open(DEM_PATH) as src:
        dem_arr = src.read(1)
    valid = dem_arr != NODATA

    d_valid = density[valid]
    lo, hi = d_valid.min(), d_valid.max()
    density_norm = (density - lo) / (hi - lo) if hi > lo else density * 0
    density_out = np.where(valid, density_norm, NODATA).astype(np.float32)

    out_path = PROCESSED / "drainage_density.tif"
    out_meta = meta.copy()
    out_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(density_out, 1)
    print(f"Wrote {out_path} (window {window_px}px ~= {window_px*pixel_size:.0f}m)")
    vals = density_out[valid]
    print(f"  range: {vals.min():.3f} - {vals.max():.3f}, median {np.median(vals):.3f}")
    return out_path


def compute_curvature():
    with rasterio.open(DEM_PATH) as src:
        elev = src.read(1)
        meta = src.meta.copy()
        pixel_size = src.transform[0]
    valid = elev != NODATA

    z = elev.astype(np.float64)
    zp = np.pad(z, 1, mode="edge")
    validp = np.pad(valid, 1, mode="edge")
    window_valid = (
        validp[:-2, 1:-1] & validp[2:, 1:-1] & validp[1:-1, :-2] & validp[1:-1, 2:] & validp[1:-1, 1:-1]
    )

    # Laplacian curvature: positive = convex (ridge), negative = concave (valley/channel)
    laplacian = (
        zp[:-2, 1:-1] + zp[2:, 1:-1] + zp[1:-1, :-2] + zp[1:-1, 2:] - 4 * zp[1:-1, 1:-1]
    ) / (pixel_size ** 2)

    curv_out = np.where(window_valid, laplacian, NODATA).astype(np.float32)
    out_path = PROCESSED / "curvature.tif"
    out_meta = meta.copy()
    out_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(curv_out, 1)
    print(f"Wrote {out_path}")
    vals = curv_out[window_valid]
    print(f"  range: {vals.min():.5f} - {vals.max():.5f}, median {np.median(vals):.5f}")
    return out_path


def compute_terrain_ruggedness():
    """TRI (Riley et al. 1999): sqrt of sum of squared elevation differences
    to the 8 neighbors -- standard ruggedness index, meters."""
    with rasterio.open(DEM_PATH) as src:
        elev = src.read(1)
        meta = src.meta.copy()
    valid = elev != NODATA

    z = elev.astype(np.float64)
    zp = np.pad(z, 1, mode="edge")
    validp = np.pad(valid, 1, mode="edge")

    offsets = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    sq_diff_sum = np.zeros_like(z)
    window_valid = validp[1:-1, 1:-1].copy()
    for dr, dc in offsets:
        neighbor = zp[1 + dr:1 + dr + z.shape[0], 1 + dc:1 + dc + z.shape[1]]
        neighbor_valid = validp[1 + dr:1 + dr + z.shape[0], 1 + dc:1 + dc + z.shape[1]]
        sq_diff_sum += np.where(neighbor_valid, (z - neighbor) ** 2, 0)
        window_valid &= neighbor_valid

    tri = np.sqrt(sq_diff_sum)
    tri_out = np.where(window_valid, tri, NODATA).astype(np.float32)

    out_path = PROCESSED / "terrain_ruggedness.tif"
    out_meta = meta.copy()
    out_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    with rasterio.open(out_path, "w", **out_meta) as dst:
        dst.write(tri_out, 1)
    print(f"Wrote {out_path}")
    vals = tri_out[window_valid]
    print(f"  range: {vals.min():.2f} - {vals.max():.2f} m, median {np.median(vals):.2f} m")
    print("  (Riley et al. 1999 classes: <80 gentle, 80-116 moderate, 116-239 rugged, >239 extreme)")
    return out_path


if __name__ == "__main__":
    print("Computing drainage density (moving-window stream fraction, normalized 0-1)...")
    compute_drainage_density()
    print("\nComputing curvature (Laplacian of elevation)...")
    compute_curvature()
    print("\nComputing terrain ruggedness index (Riley et al. 1999)...")
    compute_terrain_ruggedness()
