"""
Day 3-4 (Role A/D support, optional): population, for impact/prioritization
framing.

WorldPop's India raster at 100m is 753MB and, on checking, that server
doesn't support HTTP range requests (GDAL's /vsicurl/ windowed-read trick
errors out: "Range downloading not supported by this server!"), so a
partial remote read isn't possible there. Downloading the whole 753MB file
just for one small state -- when population is an explicitly optional,
non-blocking layer in every team doc -- isn't worth it. Using WorldPop's
1km "Global_2000_2020_1km" product instead: same real source, same year,
19MB, fully downloadable. Coarser (1km vs 100m) but for Sikkim's ~7000 km2
that's still a ~70x100 cell grid, plenty for a dashboard impact overlay.

Output: data/raw/sikkim_population_1km.tif
"""
import json
import urllib.request
from pathlib import Path

import rasterio
from rasterio.mask import mask

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
INTERIM.mkdir(parents=True, exist_ok=True)

SRC_URL = "https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/IND/ind_ppp_2020_1km_Aggregated.tif"
COUNTRY_TIF = INTERIM / "ind_ppp_2020_1km_Aggregated.tif"  # whole-India intermediate, not the Sikkim deliverable


def main():
    if not COUNTRY_TIF.exists() or COUNTRY_TIF.stat().st_size < 15_000_000:
        print(f"Downloading {SRC_URL} ...")
        urllib.request.urlretrieve(SRC_URL, COUNTRY_TIF)
    size = COUNTRY_TIF.stat().st_size
    print(f"  {COUNTRY_TIF.name}: {size:,} bytes")
    if size < 15_000_000:
        raise RuntimeError(f"Download looks truncated ({size} bytes, expected ~19MB) -- retry")

    with open(RAW / "sikkim_boundary.geojson") as f:
        boundary_gj = json.load(f)
    geoms = [boundary_gj["features"][0]["geometry"]]

    with rasterio.open(COUNTRY_TIF) as src:
        print(f"  source crs: {src.crs}, shape: {src.shape}, dtype: {src.dtypes[0]}")
        data, out_transform = mask(src, geoms, crop=True)
        meta = src.meta.copy()
        meta.update(
            height=data.shape[1],
            width=data.shape[2],
            transform=out_transform,
            compress="deflate",
        )

    out_path = RAW / "sikkim_population_1km.tif"
    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(data)
    print(f"Wrote {out_path} ({data.shape[2]}x{data.shape[1]} px)")

    nodata = meta.get("nodata")
    band = data[0]
    valid = band[band != nodata] if nodata is not None else band[band > 0]
    if valid.size:
        print(f"\nSanity check: total estimated population in Sikkim: {valid.sum():,.0f}")
        print(f"  (Sikkim's actual 2011 census population is ~610,577 -- expect same order of magnitude,")
        print(f"   not exact -- this is a 2020 gridded model estimate, not a census)")


if __name__ == "__main__":
    main()
