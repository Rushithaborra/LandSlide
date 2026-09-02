"""
Completes the RUSLE erosion factor stack. K-factor (soil erodibility) is
already done (scripts/10). This builds:

  LS-factor (slope length-steepness): Moore & Burch (1986) unit stream
  power formulation, the standard raster-GIS approach when you have a DEM
  but not surveyed slope-length transects:
      LS = (flow_accum * cell_size / 22.13)^0.4 * (sin(slope) / 0.0896)^1.3
  Flow accumulation is recomputed here with pysheds (same pipeline as
  scripts/06's drainage density, which didn't persist the accumulation
  raster itself).

  C-factor (cover management): reclassifies the ESA WorldCover layer using
  standard RUSLE literature C-values per land cover type (Wischmeier &
  Smith 1978; Morgan 2005; Panagos et al. 2015 for the cover-management
  factor specifically). These are literature-typical values, not measured
  for Sikkim -- same caveat as the team's rainfall threshold coefficients:
  fine for a first working model, but cite the actual source before
  quoting exact numbers to judges.

  P-factor (support practice): defaulted to 1.0 (no conservation terracing
  data available) -- the standard assumption when none exists.

Combines K x LS x C x P into a partial soil-loss-per-unit-erosivity raster.
Multiply by R (rainfall erosivity, Role C's rainfall data) to get the full
RUSLE annual soil loss estimate once that's available.

Outputs:
  data/processed/flow_accumulation.tif
  data/processed/rusle_ls_factor.tif
  data/processed/rusle_c_factor.tif
  data/processed/rusle_klcp_partial.tif   (K x LS x C x P, missing only R)
"""
from pathlib import Path

import numpy as np
import rasterio
from pysheds.grid import Grid
from rasterio.warp import reproject, Resampling

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
DEM_PATH = PROCESSED / "dem_sikkim_utm45n.tif"
LANDCOVER_PATH = PROCESSED / "landcover_sikkim_utm45n.tif"
K_FACTOR_PATH = PROCESSED / "rusle_k_factor.tif"
NODATA = -9999.0

# RUSLE C-factor by ESA WorldCover class -- literature-typical values
# (Wischmeier & Smith 1978; Morgan 2005; Panagos et al. 2015). Verify
# against a primary source before quoting exact numbers to judges, same
# caveat as the Harilal et al. rainfall threshold coefficients.
C_FACTOR_BY_CLASS = {
    10: 0.001,   # Tree cover -- dense canopy, near-total protection
    20: 0.014,   # Shrubland
    30: 0.05,    # Grassland
    40: 0.15,    # Cropland -- tilled, seasonal bare-soil exposure
    50: 0.01,    # Built-up -- mostly impervious; nominal value for disturbed/bare edges
    60: 0.45,    # Bare/sparse vegetation -- minimal cover, high erosion
    70: 0.0,     # Snow/ice -- not a soil erosion process
    80: 0.0,     # Water bodies -- not applicable
    90: 0.01,    # Wetland -- saturated, low RUSLE-type erosion
    95: 0.001,   # Mangroves -- dense vegetation
    100: 0.05,   # Moss/lichen -- sparse alpine cover
}
P_FACTOR = 1.0  # no terracing/conservation-practice data available

# The Moore & Burch formula treats flow accumulation as a proxy for
# hillslope length, which breaks down badly at river channels -- a cell at
# a major valley bottom can have accumulation in the hundreds of thousands,
# giving nonsensical LS values in the thousands. Standard practice in
# operational RUSLE mapping caps the contributing length at a maximum
# representative hillslope length (commonly 100-300m; Renard et al. 1997,
# AH703) so channel cells don't blow up the formula.
MAX_SLOPE_LENGTH_M = 300.0


def compute_flow_accumulation():
    print(f"Loading DEM: {DEM_PATH}")
    grid = Grid.from_raster(str(DEM_PATH))
    dem = grid.read_raster(str(DEM_PATH))

    print("Filling pits, depressions, resolving flats...")
    pit_filled = grid.fill_pits(dem)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)

    print("Computing D8 flow direction + accumulation...")
    fdir = grid.flowdir(inflated)
    acc = grid.accumulation(fdir)
    return np.asarray(acc)


def resample_to_grid(path, dem_meta, resampling):
    """Resample a raster onto the DEM's exact grid. Every layer in this
    pipeline shares Sikkim's extent and EPSG:32645 but was built at its
    source's native resolution (DEM ~29m, WorldCover ~10m, SoilGrids-derived
    K-factor ~247m) -- fine for point-sampling (scripts/05), but array-level
    combination needs one common grid."""
    with rasterio.open(path) as src:
        src_nodata = src.nodata
        out = np.full((dem_meta["height"], dem_meta["width"]), src_nodata, dtype=src.dtypes[0])
        reproject(
            source=rasterio.band(src, 1),
            destination=out,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=src_nodata,
            dst_transform=dem_meta["transform"],
            dst_crs=dem_meta["crs"],
            dst_nodata=src_nodata,
            resampling=resampling,
        )
    return out, src_nodata


def main():
    with rasterio.open(DEM_PATH) as src:
        dem_meta = src.meta.copy()
        dem_arr = src.read(1)
        pixel_size = src.transform[0]
    valid = dem_arr != NODATA

    acc = compute_flow_accumulation()
    acc_path = PROCESSED / "flow_accumulation.tif"
    acc_meta = dem_meta.copy()
    acc_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    acc_out = np.where(valid, acc, NODATA).astype(np.float32)
    with rasterio.open(acc_path, "w", **acc_meta) as dst:
        dst.write(acc_out, 1)
    print(f"Wrote {acc_path}")

    print("\nComputing LS-factor (Moore & Burch, 1986)...")
    with rasterio.open(PROCESSED / "slope_deg.tif") as src:
        slope_deg = src.read(1)
        slope_nodata = src.nodata

    ls_valid = valid & (slope_deg != slope_nodata) & (acc >= 0)
    slope_rad = np.radians(np.clip(slope_deg, 0, 89.9))
    acc_safe = np.clip(acc, 0, None)

    upslope_length = np.clip(acc_safe * pixel_size, None, MAX_SLOPE_LENGTH_M)
    ls = (upslope_length / 22.13) ** 0.4 * (np.sin(slope_rad) / 0.0896) ** 1.3
    ls_out = np.where(ls_valid, ls, NODATA).astype(np.float32)

    ls_path = PROCESSED / "rusle_ls_factor.tif"
    ls_meta = dem_meta.copy()
    ls_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    with rasterio.open(ls_path, "w", **ls_meta) as dst:
        dst.write(ls_out, 1)
    print(f"Wrote {ls_path}")
    ls_stats = ls_out[ls_valid]
    print(f"  LS range: {ls_stats.min():.2f} - {ls_stats.max():.2f}, median {np.median(ls_stats):.2f}")

    print("\nResampling land cover onto the DEM's exact grid...")
    # landcover_sikkim_utm45n.tif and rusle_k_factor.tif each share the
    # DEM's CRS but not its grid -- each was reprojected independently at
    # its source's native resolution (WorldCover ~10m, SoilGrids-derived
    # K-factor ~247m) vs. the DEM's ~29m. Point-sampling (scripts/05)
    # doesn't care about this since it looks up by coordinate, but
    # combining rasters cell-by-cell here does -- caught this from a
    # shape-mismatch crash on the first run.
    lc, lc_nodata = resample_to_grid(LANDCOVER_PATH, dem_meta, Resampling.nearest)  # categorical -- never interpolate

    print("Computing C-factor from land cover classes...")
    c_out = np.full(lc.shape, NODATA, dtype=np.float32)
    lc_valid = lc != lc_nodata
    for code, c_val in C_FACTOR_BY_CLASS.items():
        c_out[lc_valid & (lc == code)] = c_val
    unmapped = lc_valid & (c_out == NODATA)
    if unmapped.any():
        print(f"  WARNING: {unmapped.sum()} pixels have an unmapped land cover code -- check C_FACTOR_BY_CLASS")

    c_path = PROCESSED / "rusle_c_factor.tif"
    c_meta = dem_meta.copy()
    c_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    with rasterio.open(c_path, "w", **c_meta) as dst:
        dst.write(c_out, 1)
    print(f"Wrote {c_path}")

    print("\nResampling K-factor onto the DEM's exact grid...")
    k, k_nodata = resample_to_grid(K_FACTOR_PATH, dem_meta, Resampling.bilinear)  # continuous value

    print("Combining K x LS x C x P (partial -- missing only R, rainfall erosivity)...")
    combined_valid = ls_valid & lc_valid & (k != k_nodata) & (c_out != NODATA)
    klcp = k * ls_out * c_out * P_FACTOR
    klcp_out = np.where(combined_valid, klcp, NODATA).astype(np.float32)

    klcp_path = PROCESSED / "rusle_klcp_partial.tif"
    klcp_meta = dem_meta.copy()
    klcp_meta.update(dtype="float32", nodata=NODATA, compress="deflate")
    with rasterio.open(klcp_path, "w", **klcp_meta) as dst:
        dst.write(klcp_out, 1)
    print(f"Wrote {klcp_path}")

    klcp_stats = klcp_out[combined_valid]
    print("\nSanity check (K x LS x C x P, unitless until multiplied by R):")
    print(f"  valid pixels: {combined_valid.sum():,} / {dem_arr.size:,}")
    print(f"  range: {klcp_stats.min():.4f} - {klcp_stats.max():.4f}")
    print(f"  median: {np.median(klcp_stats):.4f}")
    print("  Next step: multiply by R (rainfall erosivity, MJ*mm/(ha*h*yr)) once Role C's rainfall")
    print("  data supports computing it, to get the full annual soil-loss estimate (t/ha/yr).")


if __name__ == "__main__":
    main()
