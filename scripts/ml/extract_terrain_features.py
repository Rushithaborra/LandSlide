"""Terrain feature extraction from a (metric-CRS) DEM: elevation, slope,
aspect, curvature, and distance-to-drainage.

Library-first: slope/aspect/curvature use xarray-spatial's Horn's-method
implementation (the standard algorithm GIS software uses), not a hand-rolled
gradient. Distance-to-drainage uses pysheds' D8 flow-accumulation (the
standard hydrological algorithm), not a custom watershed implementation.

Known environment issue: pysheds targets pre-2.0 numpy and calls the removed
`numpy.in1d` (renamed to `numpy.isin`). We apply a one-line alias as a
compatibility shim -- this is not a custom algorithm, just un-renaming a
numpy function -- and verified the full D8 pipeline runs correctly with it.
"""
import numpy as np
import pandas as pd
import pyproj
import rasterio
import xarray as xr
from scipy import ndimage
from xrspatial import aspect as xrs_aspect
from xrspatial import curvature as xrs_curvature
from xrspatial import slope as xrs_slope

from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig

if not hasattr(np, "in1d"):
    np.in1d = np.isin  # pysheds compatibility shim -- see module docstring


def compute_slope_aspect_curvature(elevation: np.ndarray, pixel_size_m: float) -> dict[str, np.ndarray]:
    """elevation must already be in a metric CRS (constant pixel_size_m in
    both x and y) -- degree-based pixels give meaningless slope (verified)."""
    da = xr.DataArray(elevation.astype(np.float64), dims=["y", "x"], attrs={"res": (pixel_size_m, pixel_size_m)})
    return {
        "slope": xrs_slope(da).values,
        "aspect": xrs_aspect(da).values,
        "curvature": xrs_curvature(da).values,
    }


def compute_distance_to_drainage(dem_utm_path, stream_threshold: int = 500) -> tuple[np.ndarray, float]:
    """D8 flow accumulation -> cells above stream_threshold contributing
    cells are treated as drainage channels -> Euclidean distance transform.
    stream_threshold is a coarse, documented choice (not calibrated against
    mapped streams) -- fine for a susceptibility *feature*, not for claiming
    an accurate stream network."""
    from pysheds.grid import Grid

    grid = Grid.from_raster(str(dem_utm_path))
    dem = grid.read_raster(str(dem_utm_path))
    pit_filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)
    fdir = grid.flowdir(inflated)
    acc = grid.accumulation(fdir)

    stream_mask = np.asarray(acc) > stream_threshold
    pixel_size_m = grid.affine.a
    dist_px = ndimage.distance_transform_edt(~stream_mask)
    return dist_px * pixel_size_m, pixel_size_m


def build_feature_stack(dem_utm_path, config: MlConfig = DEFAULT_CONFIG) -> dict:
    """Computes all terrain features for the pilot DEM and returns them
    alongside the raster's affine transform + CRS, for point sampling."""
    with rasterio.open(dem_utm_path) as src:
        elevation = src.read(1).astype(np.float64)
        transform = src.transform
        crs = src.crs
        pixel_size_m = transform.a

    sac = compute_slope_aspect_curvature(elevation, pixel_size_m)
    dist_drainage, _ = compute_distance_to_drainage(dem_utm_path)

    return {
        "elevation": elevation,
        "slope": sac["slope"],
        "aspect": sac["aspect"],
        "curvature": sac["curvature"],
        "distance_to_drainage": dist_drainage,
        "transform": transform,
        "crs": crs,
    }


def sample_at_points(
    feature_stack: dict, lons: np.ndarray, lats: np.ndarray, points_crs: str = "EPSG:4326"
) -> pd.DataFrame:
    """Looks up each terrain feature at the given (lon, lat) points via
    nearest-pixel indexing into the precomputed feature rasters."""
    transformer = pyproj.Transformer.from_crs(points_crs, feature_stack["crs"], always_xy=True)
    xs, ys = transformer.transform(lons, lats)
    transform = feature_stack["transform"]
    inv = ~transform

    rows, cols = [], []
    for x, y in zip(xs, ys):
        col, row = inv * (x, y)
        rows.append(int(row))
        cols.append(int(col))
    rows, cols = np.array(rows), np.array(cols)

    n_rows, n_cols = feature_stack["elevation"].shape
    in_bounds = (rows >= 0) & (rows < n_rows) & (cols >= 0) & (cols < n_cols)

    out = {"in_bounds": in_bounds}
    for feature in ["elevation", "slope", "aspect", "curvature", "distance_to_drainage"]:
        values = np.full(len(lons), np.nan)
        values[in_bounds] = feature_stack[feature][rows[in_bounds], cols[in_bounds]]
        out[feature] = values
    return pd.DataFrame(out)


def main(config: MlConfig = DEFAULT_CONFIG) -> None:
    stack = build_feature_stack(config.paths.dem_utm_path, config)
    for name in ["elevation", "slope", "aspect", "curvature", "distance_to_drainage"]:
        arr = stack[name]
        print(f"{name:22s} min={np.nanmin(arr):.2f} mean={np.nanmean(arr):.2f} max={np.nanmax(arr):.2f}")


if __name__ == "__main__":
    main()
