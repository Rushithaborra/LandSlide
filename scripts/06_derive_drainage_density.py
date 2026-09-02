"""
Day 2 (Role A - Data/GIS): drainage density, derived from the DEM already
on disk -- no new download (per the doc: "Fill Sinks -> Flow Accumulation
-> Stream extraction" using QGIS hydrology tools; this is the scripted
equivalent using pysheds).

Pipeline:
  1. Fill pits / depressions, resolve flats (so flow has somewhere to go)
  2. D8 flow direction
  3. Flow accumulation
  4. Threshold accumulation to extract a stream network
  5. Euclidean distance transform -> distance-to-stream raster (the actual
     "drainage density" feature: how close is each point to a drainage line)

Output:
  data/processed/streams.tif             - binary stream mask
  data/processed/distance_to_stream_m.tif - distance to nearest stream, meters
"""
from pathlib import Path

import numpy as np
import rasterio
from pysheds.grid import Grid
from scipy.ndimage import distance_transform_edt

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
DEM_PATH = PROCESSED / "dem_sikkim_utm45n.tif"
NODATA = -9999.0

# Flow-accumulation threshold (in cells) above which a cell is called a
# stream. At ~30m pixels, 500 cells ~= 0.45 sq km contributing area, a
# common rule-of-thumb starting threshold for stream extraction at this
# resolution; tune if the resulting network looks too sparse/dense next to
# known rivers.
ACC_THRESHOLD = 500


def main():
    print(f"Loading DEM: {DEM_PATH}")
    grid = Grid.from_raster(str(DEM_PATH))
    dem = grid.read_raster(str(DEM_PATH))

    print("Filling pits...")
    pit_filled = grid.fill_pits(dem)
    print("Filling depressions...")
    flooded = grid.fill_depressions(pit_filled)
    print("Resolving flats...")
    inflated = grid.resolve_flats(flooded)

    print("Computing D8 flow direction...")
    fdir = grid.flowdir(inflated)

    print("Computing flow accumulation...")
    acc = grid.accumulation(fdir)

    print(f"Extracting stream network (accumulation > {ACC_THRESHOLD} cells)...")
    streams = (np.asarray(acc) > ACC_THRESHOLD).astype(np.uint8)
    n_stream_px = int(streams.sum())
    print(f"  {n_stream_px} stream pixels ({100*n_stream_px/streams.size:.2f}% of valid area)")

    with rasterio.open(DEM_PATH) as src:
        meta = src.meta.copy()
        pixel_size = src.transform[0]
        dem_arr = src.read(1)

    valid_mask = dem_arr != NODATA

    streams_path = PROCESSED / "streams.tif"
    stream_meta = meta.copy()
    stream_meta.update(dtype="uint8", nodata=255, compress="deflate")
    streams_out = np.where(valid_mask, streams, 255).astype(np.uint8)
    with rasterio.open(streams_path, "w", **stream_meta) as dst:
        dst.write(streams_out, 1)
    print(f"Wrote {streams_path}")

    print("Computing Euclidean distance to nearest stream...")
    if n_stream_px == 0:
        raise RuntimeError("No stream pixels extracted -- lower ACC_THRESHOLD and retry")
    dist_px = distance_transform_edt(streams == 0)
    dist_m = (dist_px * pixel_size).astype(np.float32)
    dist_m = np.where(valid_mask, dist_m, NODATA).astype(np.float32)

    dist_path = PROCESSED / "distance_to_stream_m.tif"
    dist_meta = meta.copy()
    dist_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    with rasterio.open(dist_path, "w", **dist_meta) as dst:
        dst.write(dist_m, 1)
    print(f"Wrote {dist_path}")

    valid_dist = dist_m[valid_mask]
    print("\nSanity check:")
    print(f"  distance-to-stream range: {valid_dist.min():.1f} - {valid_dist.max():.1f} m")
    print(f"  median: {np.median(valid_dist):.1f} m")


if __name__ == "__main__":
    main()
