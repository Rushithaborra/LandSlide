"""
Dashboard export (Role A -> Role D handoff). Everything in data/processed/
is analysis-grade GeoTIFF -- not something a React+Leaflet dashboard can
render directly. This reprojects the dashboard-relevant rasters to
EPSG:4326, colorizes them, and exports PNG + lat/lon bounds so Role D can
drop each one straight into Leaflet with L.imageOverlay(url, bounds).

Vector layers (roads, villages, health/edu, landslide points, boundary) are
NOT touched here -- they're already GeoJSON in data/raw/ and work directly
with L.geoJSON(), no conversion needed.

Skipped on purpose: flow_accumulation.tif and streams.tif are intermediate/
technical outputs (used to build distance_to_stream_m and the LS-factor),
not something a dashboard viewer would want as its own layer. The 4 raw
soil property layers are likewise inputs to the K-factor, not end products
-- K-factor itself is exported instead.

Output: data/dashboard/*.png + data/dashboard/manifest.json
"""
import json
from pathlib import Path

import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
from matplotlib import cm
from matplotlib.colors import Normalize, ListedColormap, BoundaryNorm
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "dashboard"
OUT.mkdir(parents=True, exist_ok=True)
DST_CRS = "EPSG:4326"

# Official ESA WorldCover legend colors -- matches the published reference,
# not an arbitrary palette.
LAYER_CAVEATS = {
    "erosion_soil_loss": (
        "RUSLE was built for rainfall-driven erosion on soil-covered slopes, not "
        "the periglacial/bare-rock terrain above ~4000m (44% of Sikkim). Values in "
        "that zone run implausibly high (max 10,339 t/ha/yr at one pixel) and "
        "aren't physically meaningful -- caption this or mask above the snowline "
        "rather than presenting the raw map as-is. See data/PROVENANCE.md, Round 4."
    ),
}

WORLDCOVER_COLORS = {
    10: ("#006400", "Tree cover"),
    20: ("#FFBB22", "Shrubland"),
    30: ("#FFFF4C", "Grassland"),
    40: ("#F096FF", "Cropland"),
    50: ("#FA0000", "Built-up"),
    60: ("#B4B4B4", "Bare/sparse vegetation"),
    70: ("#F0F0F0", "Snow/ice"),
    80: ("#0064C8", "Water bodies"),
    90: ("#0096A0", "Wetland"),
    95: ("#00CF75", "Mangroves"),
    100: ("#FAE6A0", "Moss/lichen"),
}

# (source path, output id, title, colormap, unit, categorical?)
LAYERS = [
    (PROCESSED / "dem_sikkim_utm45n.tif", "elevation", "Elevation", "terrain", "m", False),
    (PROCESSED / "slope_deg.tif", "slope", "Slope", "YlOrRd", "deg", False),
    (PROCESSED / "distance_to_stream_m.tif", "distance_to_stream", "Distance to Stream", "Blues_r", "m", False),
    (PROCESSED / "landcover_sikkim_utm45n.tif", "landcover", "Land Cover", None, "class", True),
    (PROCESSED / "rusle_k_factor.tif", "erosion_k_factor", "Soil Erodibility (K-factor)", "OrRd", "unitless", False),
    (PROCESSED / "rusle_soil_loss_annual.tif", "erosion_soil_loss", "Annual Soil Loss Estimate (RUSLE)", "OrRd", "t/ha/yr", False),
    (RAW / "sikkim_population_1km.tif", "population", "Population (2020 est., 1km)", "viridis", "people/km²", False),
]


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def reproject_to_wgs84(path):
    with rasterio.open(path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, DST_CRS, src.width, src.height, *src.bounds
        )
        dst_nodata = src.nodata if src.nodata is not None else -9999.0
        dst = np.full((height, width), dst_nodata, dtype=np.float32)
        reproject(
            source=rasterio.band(src, 1),
            destination=dst,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src.nodata,
            dst_transform=transform,
            dst_crs=DST_CRS,
            dst_nodata=dst_nodata,
            resampling=Resampling.nearest if src.dtypes[0].startswith("uint") else Resampling.bilinear,
        )
        bounds = rasterio.transform.array_bounds(height, width, transform)  # (left, bottom, right, top)
        return dst, dst_nodata, bounds


def render_continuous(arr, nodata, cmap_name):
    valid = arr != nodata
    if not valid.any():
        raise RuntimeError("no valid pixels")
    lo, hi = np.percentile(arr[valid], [2, 98])
    if lo == hi:
        hi = lo + 1
    norm = Normalize(vmin=lo, vmax=hi, clip=True)
    cmap = cm.get_cmap(cmap_name)
    rgba = cmap(norm(arr))
    rgba[..., 3] = np.where(valid, 1.0, 0.0)  # transparent nodata
    img = (rgba * 255).astype(np.uint8)
    return img, float(lo), float(hi)


def render_landcover(arr, nodata):
    rgba = np.zeros((*arr.shape, 4), dtype=np.uint8)
    for code, (hexcolor, _name) in WORLDCOVER_COLORS.items():
        mask = arr == code
        r, g, b = hex_to_rgb(hexcolor)
        rgba[mask] = (r, g, b, 255)
    rgba[arr == nodata] = (0, 0, 0, 0)
    return rgba


def main():
    manifest = {"crs": DST_CRS, "layers": []}

    for path, layer_id, title, cmap_name, unit, categorical in LAYERS:
        if not path.exists():
            print(f"SKIP {layer_id}: {path} not found")
            continue
        print(f"Rendering {layer_id} ({title})...")
        arr, nodata, bounds = reproject_to_wgs84(path)
        left, bottom, right, top = bounds

        if categorical:
            img = render_landcover(arr, nodata)
            legend = [{"code": c, "color": h, "label": n} for c, (h, n) in WORLDCOVER_COLORS.items()]
            value_range = None
        else:
            img, lo, hi = render_continuous(arr, nodata, cmap_name)
            legend = {"colormap": cmap_name, "min": round(lo, 3), "max": round(hi, 3)}
            value_range = [round(lo, 3), round(hi, 3)]

        png_path = OUT / f"{layer_id}.png"
        Image.fromarray(img, mode="RGBA").save(png_path)

        entry = {
            "id": layer_id,
            "title": title,
            "file": png_path.name,
            "unit": unit,
            "bounds_leaflet": [[bottom, left], [top, right]],  # L.imageOverlay(url, bounds) format
            "legend": legend,
            "value_range": value_range,
        }
        if layer_id in LAYER_CAVEATS:
            entry["caveat"] = LAYER_CAVEATS[layer_id]
        manifest["layers"].append(entry)
        print(f"  wrote {png_path.name}, bounds {[[round(bottom,4), round(left,4)], [round(top,4), round(right,4)]]}")

    manifest["vector_layers"] = [
        {"id": "boundary", "file": "../raw/sikkim_boundary.geojson", "type": "polygon"},
        {"id": "roads", "file": "../raw/sikkim_roads.geojson", "type": "line"},
        {"id": "villages", "file": "../raw/sikkim_villages.geojson", "type": "point"},
        {"id": "health_edu", "file": "../raw/sikkim_health_edu.geojson", "type": "point"},
        {"id": "landslide_points", "file": "../raw/gsi_sikkim_landslides_raw.geojson", "type": "point"},
    ]

    manifest_path = OUT / "manifest.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"\nWrote {manifest_path}")
    print(f"{len(manifest['layers'])} raster layers exported to {OUT}/")


if __name__ == "__main__":
    main()
