"""Download Copernicus GLO-30 DEM tile(s) for the pilot corridor and
reproject to a metric CRS.

Source: the public AWS Open Data bucket (s3://copernicus-dem-30m) -- no
account, no API key, plain HTTPS. Verified during the data audit: a real
tile downloads and reads correctly (elevation range 183m-8564m, the max
matching Kangchenjunga's real elevation at this tile's edge).

Reprojection to EPSG:32645 (UTM 45N) is not optional: slope/aspect/curvature
computed directly on the native EPSG:4326 (degree-pixel) tile come out
wrong (~90 degrees everywhere, verified) because linear terrain algorithms
assume metric pixel spacing.
"""
import pathlib

import httpx
import rasterio
from rasterio.warp import Resampling, calculate_default_transform, reproject

from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig


def download_tile(tile_id: str, config: MlConfig = DEFAULT_CONFIG) -> pathlib.Path:
    config.paths.dem_raw_dir.mkdir(parents=True, exist_ok=True)
    out_path = config.paths.dem_raw_dir / f"{tile_id}.tif"
    if out_path.exists():
        return out_path

    dem_dir = f"Copernicus_DSM_COG_10_{tile_id}_DEM"
    url = f"{config.dem.bucket_url}/{dem_dir}/{dem_dir}.tif"
    with httpx.stream("GET", url, timeout=120.0, follow_redirects=True) as response:
        response.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in response.iter_bytes(chunk_size=1 << 20):
                f.write(chunk)
    return out_path


def reproject_to_utm(tile_paths: list, config: MlConfig = DEFAULT_CONFIG) -> pathlib.Path:
    """Merges (if multiple tiles) and reprojects to config.dem.target_crs.
    For this pilot there's exactly one tile, so this is a straight reproject."""
    if len(tile_paths) != 1:
        raise NotImplementedError(
            "Multiple DEM tiles would need a mosaic step (rasterio.merge) before "
            "reprojecting -- not needed for this pilot (single tile covers all "
            "777 Sikkim points), so it's intentionally not implemented yet."
        )

    config.paths.dem_utm_path.parent.mkdir(parents=True, exist_ok=True)
    src_path = tile_paths[0]
    with rasterio.open(src_path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, config.dem.target_crs, src.width, src.height, *src.bounds
        )
        kwargs = src.meta.copy()
        kwargs.update({"crs": config.dem.target_crs, "transform": transform, "width": width, "height": height})
        with rasterio.open(config.paths.dem_utm_path, "w", **kwargs) as dst:
            reproject(
                source=rasterio.band(src, 1),
                destination=rasterio.band(dst, 1),
                src_transform=src.transform,
                src_crs=src.crs,
                dst_transform=transform,
                dst_crs=config.dem.target_crs,
                resampling=Resampling.bilinear,
            )
    return config.paths.dem_utm_path


def main(config: MlConfig = DEFAULT_CONFIG) -> None:
    tile_paths = [download_tile(tile_id, config) for tile_id in config.dem.tile_ids]
    for p in tile_paths:
        print(f"DEM tile ready: {p}")
    utm_path = reproject_to_utm(tile_paths, config)
    print(f"Reprojected DEM ({config.dem.target_crs}): {utm_path}")

    with rasterio.open(utm_path) as d:
        print(f"  shape={d.shape} res={d.res} bounds={d.bounds}")


if __name__ == "__main__":
    main()
