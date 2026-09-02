"""
Soil erosion model inputs (Role A support): the docs' GSI lithology sources
are down, and the global fallbacks tried (GLiM, Macrostrat) are too coarse
to vary at all within Sikkim -- useless as a landslide feature. But for
*soil erosion* specifically, bedrock lithology isn't actually the right
input anyway: standard erosion modeling (RUSLE) uses soil texture + organic
carbon to compute soil erodibility (the K-factor), which is what actually
predicts how easily surface soil detaches and washes away.

Source: ISRIC SoilGrids 2.0 via WCS (maps.isric.org), 250m, no login --
already on the team's own "optional/stretch" list, just not fetched yet.
Confirmed it has real spatial variance across Sikkim (std dev 89 on a
0-1000 g/kg scale for clay), unlike the lithology fallbacks.

Fetches clay/sand/silt/soc (organic carbon) at 0-5cm (surface, the relevant
depth for erosion), clips/reprojects to match the rest of the pipeline
(EPSG:32645), then computes the RUSLE K-factor using the Williams (1995)
EPIC formula -- the standard approach when you have texture + organic
carbon but not a direct erodibility nomograph value.

Outputs:
  data/raw/soil_{property}_0-5cm.tif       (clay, sand, silt, soc; WGS84)
  data/processed/soil_{property}_sikkim_utm45n.tif
  data/processed/rusle_k_factor.tif        (soil erodibility, unitless)
"""
import json
from pathlib import Path

import numpy as np
import rasterio
import requests
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
BOUNDARY = RAW / "sikkim_boundary.geojson"
DST_CRS = "EPSG:32645"

WCS_BASE = "https://maps.isric.org/mapserv"
# Sikkim bbox + margin, lon/lat (X, Y)
BBOX = (87.9, 26.9, 89.0, 28.3)

PROPERTIES = ["clay", "sand", "silt", "soc"]  # all at 0-5cm mean


def fetch_property(prop):
    coverage_id = f"{prop}_0-5cm_mean"
    params = {
        "map": f"/map/{prop}.map",
        "SERVICE": "WCS",
        "VERSION": "2.0.1",
        "REQUEST": "GetCoverage",
        "COVERAGEID": coverage_id,
        "FORMAT": "GEOTIFF_INT16",
        "SUBSET": [f"X({BBOX[0]},{BBOX[2]})", f"Y({BBOX[1]},{BBOX[3]})"],
        "SUBSETTINGCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
        "OUTPUTCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
    }
    resp = requests.get(WCS_BASE, params=params, timeout=60)
    resp.raise_for_status()
    out_path = RAW / f"soil_{prop}_0-5cm.tif"
    with open(out_path, "wb") as f:
        f.write(resp.content)
    return out_path


SOIL_NODATA = -9999  # ISRIC's raw WCS GEOTIFF_INT16 output doesn't declare its own nodata value


def clip_reproject(src_path, out_path, nodata=None):
    with open(BOUNDARY) as f:
        gj = json.load(f)
    geoms = [feat["geometry"] for feat in gj["features"]]

    with rasterio.open(src_path) as src:
        src_nodata = nodata if nodata is not None else (src.nodata if src.nodata is not None else SOIL_NODATA)
        arr, transform = mask(src, geoms, crop=True, nodata=src_nodata)
        meta = src.meta.copy()
        meta.update(height=arr.shape[1], width=arr.shape[2], transform=transform, nodata=src_nodata)

    src_crs = meta["crs"]
    dst_transform, width, height = calculate_default_transform(
        src_crs, DST_CRS, meta["width"], meta["height"],
        *rasterio.transform.array_bounds(meta["height"], meta["width"], meta["transform"]),
    )
    dst_arr = np.full((height, width), src_nodata if src_nodata is not None else -9999, dtype=arr.dtype)
    reproject(
        source=arr[0], destination=dst_arr,
        src_transform=meta["transform"], src_crs=src_crs, src_nodata=src_nodata,
        dst_transform=dst_transform, dst_crs=DST_CRS, dst_nodata=src_nodata,
        resampling=Resampling.bilinear,
    )
    dst_meta = meta.copy()
    dst_meta.update(crs=DST_CRS, transform=dst_transform, width=width, height=height, compress="deflate")
    with rasterio.open(out_path, "w", **dst_meta) as dst:
        dst.write(dst_arr, 1)
    return dst_arr, dst_meta


def williams_k_factor(sand_pct, silt_pct, clay_pct, oc_pct):
    """RUSLE/EPIC soil erodibility K-factor (Williams, 1995).
    Inputs as percent (0-100). Returns unitless K (US customary units,
    the form most RUSLE literature reports)."""
    sn1 = 1 - sand_pct / 100
    f_csand = 0.2 + 0.3 * np.exp(-0.256 * sand_pct * (1 - silt_pct / 100))
    f_clsi = (silt_pct / (clay_pct + silt_pct + 1e-9)) ** 0.3
    f_orgc = 1 - (0.25 * oc_pct) / (oc_pct + np.exp(3.72 - 2.95 * oc_pct))
    f_hisand = 1 - (0.7 * sn1) / (sn1 + np.exp(-5.51 + 22.9 * sn1))
    return f_csand * f_clsi * f_orgc * f_hisand


def main():
    processed = {}
    for prop in PROPERTIES:
        print(f"Fetching {prop} (0-5cm mean) from ISRIC SoilGrids WCS...")
        raw_path = fetch_property(prop)
        print(f"  wrote {raw_path} ({raw_path.stat().st_size:,} bytes)")

        print(f"  clipping + reprojecting to {DST_CRS}...")
        out_path = PROCESSED / f"soil_{prop}_sikkim_utm45n.tif"
        arr, meta = clip_reproject(raw_path, out_path)
        processed[prop] = (arr, meta)
        print(f"  wrote {out_path}")

    print("\nComputing RUSLE K-factor (Williams 1995 EPIC formula)...")
    clay_arr, meta = processed["clay"]
    sand_arr, _ = processed["sand"]
    silt_arr, _ = processed["silt"]
    soc_arr, _ = processed["soc"]
    nodata = meta["nodata"]

    valid = (clay_arr != nodata) & (sand_arr != nodata) & (silt_arr != nodata) & (soc_arr != nodata)

    # SoilGrids reports texture in g/kg (per mille of a kg, i.e. parts per
    # thousand) and organic carbon in dg/kg -- both /10 to get %.
    clay_pct = clay_arr.astype(np.float64) / 10
    sand_pct = sand_arr.astype(np.float64) / 10
    silt_pct = silt_arr.astype(np.float64) / 10
    oc_pct = soc_arr.astype(np.float64) / 10
    oc_pct = np.clip(oc_pct, 0.01, None)  # avoid div-by-zero in f_orgc at oc=0

    k = williams_k_factor(sand_pct, silt_pct, clay_pct, oc_pct)
    k_out = np.where(valid, k, nodata).astype(np.float32)

    out_path = PROCESSED / "rusle_k_factor.tif"
    k_meta = meta.copy()
    k_meta.update(dtype="float32", nodata=float(nodata))
    with rasterio.open(out_path, "w", **k_meta) as dst:
        dst.write(k_out, 1)
    print(f"Wrote {out_path}")

    k_valid = k[valid[0] if valid.ndim == 3 else valid]
    print("\nSanity check:")
    print(f"  K-factor range: {k_valid.min():.3f} - {k_valid.max():.3f}")
    print(f"  median: {np.median(k_valid):.3f}")
    print("  (higher K = more erodible soil; typical RUSLE K values run ~0.02-0.65)")


if __name__ == "__main__":
    main()
