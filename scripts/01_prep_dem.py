"""
Day 1/2 (Role A - Data/GIS): mosaic DEM tiles, clip to Sikkim boundary,
reproject to UTM 45N (EPSG:32645), derive slope + aspect.

Inputs:
  data/raw/Copernicus_DSM_COG_10_N27_00_E088_00_DEM.tif
  data/raw/Copernicus_DSM_COG_10_N28_00_E088_00_DEM.tif
  data/raw/sikkim_boundary.geojson

Outputs (data/processed/):
  dem_sikkim_utm45n.tif   - clipped, reprojected elevation
  slope_deg.tif           - slope in degrees
  aspect_deg.tif          - aspect in degrees (0-360, 0/360=N, clockwise)
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.merge import merge
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
PROCESSED.mkdir(parents=True, exist_ok=True)

TILES = [
    RAW / "Copernicus_DSM_COG_10_N27_00_E088_00_DEM.tif",
    RAW / "Copernicus_DSM_COG_10_N28_00_E088_00_DEM.tif",
]
BOUNDARY = RAW / "sikkim_boundary.geojson"
DST_CRS = "EPSG:32645"
NODATA = -9999.0


def mosaic_tiles():
    srcs = [rasterio.open(t) for t in TILES]
    mosaic_arr, mosaic_transform = merge(srcs, nodata=NODATA)
    meta = srcs[0].meta.copy()
    meta.update(
        driver="GTiff",
        height=mosaic_arr.shape[1],
        width=mosaic_arr.shape[2],
        transform=mosaic_transform,
        nodata=NODATA,
    )
    for s in srcs:
        s.close()
    return mosaic_arr, meta


def clip_to_boundary(arr, meta):
    with open(BOUNDARY) as f:
        gj = json.load(f)
    geoms = [feat["geometry"] for feat in gj["features"]]

    mem_path = PROCESSED / "_mosaic_tmp.tif"
    with rasterio.open(mem_path, "w", **meta) as tmp:
        tmp.write(arr)

    with rasterio.open(mem_path) as src:
        out_arr, out_transform = mask(src, geoms, crop=True, nodata=NODATA)
        out_meta = src.meta.copy()
    out_meta.update(
        height=out_arr.shape[1], width=out_arr.shape[2], transform=out_transform,
        nodata=NODATA,
    )
    mem_path.unlink()
    return out_arr, out_meta


def reproject_to_utm(arr, meta):
    src_crs = meta["crs"]
    transform, width, height = calculate_default_transform(
        src_crs, DST_CRS, meta["width"], meta["height"], *rasterio.transform.array_bounds(
            meta["height"], meta["width"], meta["transform"]
        )
    )
    dst_meta = meta.copy()
    dst_meta.update(crs=DST_CRS, transform=transform, width=width, height=height, nodata=NODATA)

    dst_arr = np.full((arr.shape[0], height, width), NODATA, dtype=arr.dtype)
    for i in range(arr.shape[0]):
        reproject(
            source=arr[i],
            destination=dst_arr[i],
            src_transform=meta["transform"],
            src_crs=src_crs,
            src_nodata=NODATA,
            dst_transform=transform,
            dst_crs=DST_CRS,
            dst_nodata=NODATA,
            resampling=Resampling.bilinear,
        )
    return dst_arr, dst_meta


def slope_aspect(elev, pixel_size, nodata=NODATA):
    """Horn's method (same algorithm gdaldem slope/aspect uses).

    Any 3x3 window touching a nodata cell produces nodata in the output,
    so the Sikkim-boundary clip edge doesn't get read as a fake cliff.
    """
    z = elev.astype(np.float64)
    valid = elev != nodata
    px = pixel_size
    # pad edges by replication
    zp = np.pad(z, 1, mode="edge")
    validp = np.pad(valid, 1, mode="edge")

    a = zp[:-2, :-2]; b = zp[:-2, 1:-1]; c = zp[:-2, 2:]
    d = zp[1:-1, :-2];                    f = zp[1:-1, 2:]
    g = zp[2:, :-2];  h = zp[2:, 1:-1];   i = zp[2:, 2:]

    window_valid = np.all(
        [validp[:-2, :-2], validp[:-2, 1:-1], validp[:-2, 2:],
         validp[1:-1, :-2], validp[1:-1, 1:-1], validp[1:-1, 2:],
         validp[2:, :-2], validp[2:, 1:-1], validp[2:, 2:]],
        axis=0,
    )

    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * px)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * px)

    slope_rad = np.arctan(np.sqrt(dzdx ** 2 + dzdy ** 2))
    slope_deg = np.degrees(slope_rad)

    aspect_rad = np.arctan2(dzdy, -dzdx)
    aspect_deg = np.degrees(aspect_rad)
    aspect_deg = np.where(aspect_deg < 0, 90.0 - aspect_deg, 90.0 - aspect_deg)
    aspect_deg = np.mod(aspect_deg, 360.0)

    slope_deg = np.where(window_valid, slope_deg, nodata).astype(np.float32)
    aspect_deg = np.where(window_valid, aspect_deg, nodata).astype(np.float32)

    return slope_deg, aspect_deg


def main():
    print("Mosaicking DEM tiles...")
    arr, meta = mosaic_tiles()
    print(f"  mosaic shape: {arr.shape}, crs: {meta['crs']}")

    print("Clipping to Sikkim boundary...")
    arr, meta = clip_to_boundary(arr, meta)
    print(f"  clipped shape: {arr.shape}")

    print(f"Reprojecting to {DST_CRS}...")
    arr, meta = reproject_to_utm(arr, meta)
    print(f"  reprojected shape: {arr.shape}, pixel size: {meta['transform'][0]:.2f} m")

    dem_path = PROCESSED / "dem_sikkim_utm45n.tif"
    out_meta = meta.copy()
    out_meta.update(driver="GTiff", count=1, compress="deflate", dtype="float32", nodata=NODATA)
    with rasterio.open(dem_path, "w", **out_meta) as dst:
        dst.write(arr[0].astype(np.float32), 1)
    print(f"Wrote {dem_path}")

    print("Computing slope + aspect (Horn's method)...")
    pixel_size = meta["transform"][0]
    slope_deg, aspect_deg = slope_aspect(arr[0], pixel_size)

    slope_path = PROCESSED / "slope_deg.tif"
    aspect_path = PROCESSED / "aspect_deg.tif"
    single_meta = out_meta.copy()
    with rasterio.open(slope_path, "w", **single_meta) as dst:
        dst.write(slope_deg, 1)
    with rasterio.open(aspect_path, "w", **single_meta) as dst:
        dst.write(aspect_deg, 1)
    print(f"Wrote {slope_path}")
    print(f"Wrote {aspect_path}")

    elev_valid = arr[0][arr[0] != NODATA]
    slope_valid = slope_deg[slope_deg != NODATA]
    aspect_valid = aspect_deg[aspect_deg != NODATA]
    print("\nSanity check (nodata excluded):")
    print(f"  valid pixels: {elev_valid.size} / {arr[0].size} ({100*elev_valid.size/arr[0].size:.1f}%)")
    print(f"  elevation range: {elev_valid.min():.1f} - {elev_valid.max():.1f} m")
    print(f"  slope range: {slope_valid.min():.1f} - {slope_valid.max():.1f} deg")
    print(f"  aspect range: {aspect_valid.min():.1f} - {aspect_valid.max():.1f} deg")


if __name__ == "__main__":
    main()
