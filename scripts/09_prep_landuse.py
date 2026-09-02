"""
Day 3 (Role A - Data/GIS): clip + reproject ESA WorldCover to Sikkim,
matching the same pipeline used for the DEM (clip to boundary, reproject
to EPSG:32645).

ESA WorldCover 2021 classes (10m):
  10 Tree cover      20 Shrubland     30 Grassland     40 Cropland
  50 Built-up        60 Bare/sparse   70 Snow/ice      80 Water
  90 Wetland         95 Mangroves     100 Moss/lichen

Output: data/processed/landcover_sikkim_utm45n.tif
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

SRC = RAW / "ESA_WorldCover_10m_2021_v200_N27E087_Map.tif"
BOUNDARY = RAW / "sikkim_boundary.geojson"
DST_CRS = "EPSG:32645"
NODATA = 255  # ESA WorldCover's own nodata/fill value for uint8 classes

CLASS_NAMES = {
    10: "Tree cover", 20: "Shrubland", 30: "Grassland", 40: "Cropland",
    50: "Built-up", 60: "Bare/sparse vegetation", 70: "Snow/ice",
    80: "Water bodies", 90: "Wetland", 95: "Mangroves", 100: "Moss/lichen",
}


def main():
    with open(BOUNDARY) as f:
        gj = json.load(f)
    geoms = [feat["geometry"] for feat in gj["features"]]

    print("Clipping WorldCover to Sikkim boundary...")
    with rasterio.open(SRC) as src:
        out_arr, out_transform = mask(src, geoms, crop=True, nodata=NODATA)
        out_meta = src.meta.copy()
    out_meta.update(height=out_arr.shape[1], width=out_arr.shape[2], transform=out_transform, nodata=NODATA)
    print(f"  clipped shape: {out_arr.shape}")

    print(f"Reprojecting to {DST_CRS}...")
    src_crs = out_meta["crs"]
    transform, width, height = calculate_default_transform(
        src_crs, DST_CRS, out_meta["width"], out_meta["height"],
        *rasterio.transform.array_bounds(out_meta["height"], out_meta["width"], out_meta["transform"]),
    )
    dst_arr = np.full((height, width), NODATA, dtype=np.uint8)
    reproject(
        source=out_arr[0], destination=dst_arr,
        src_transform=out_meta["transform"], src_crs=src_crs, src_nodata=NODATA,
        dst_transform=transform, dst_crs=DST_CRS, dst_nodata=NODATA,
        resampling=Resampling.nearest,  # categorical data -- never interpolate classes
    )
    print(f"  reprojected shape: {dst_arr.shape}, pixel size: {transform[0]:.2f} m")

    out_path = PROCESSED / "landcover_sikkim_utm45n.tif"
    dst_meta = out_meta.copy()
    dst_meta.update(crs=DST_CRS, transform=transform, width=width, height=height, compress="deflate")
    with rasterio.open(out_path, "w", **dst_meta) as dst:
        dst.write(dst_arr, 1)
    print(f"Wrote {out_path}")

    print("\nClass distribution (% of valid Sikkim area):")
    valid = dst_arr[dst_arr != NODATA]
    total = valid.size
    for code in sorted(np.unique(valid)):
        pct = 100 * np.sum(valid == code) / total
        name = CLASS_NAMES.get(int(code), f"class {code}")
        print(f"  {code:>3} {name:<25} {pct:5.1f}%")


if __name__ == "__main__":
    main()
