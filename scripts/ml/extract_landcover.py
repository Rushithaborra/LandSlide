"""Land-cover feature extraction from ESA WorldCover 10m 2021.

Verified during the feature-suitability audit: WorldCover's native CRS is
EPSG:4326, same as our point coordinates (lat/lon) -- so sampling is a
direct nearest-pixel lookup, no reprojection needed (unlike the DEM, which
does need one for slope/aspect/curvature). This module asserts that CRS
match rather than assuming it, since silently sampling misaligned rasters
is exactly the kind of mistake the earlier SoilGrids Homolosine mixup was.
"""
import numpy as np
import pandas as pd
import rasterio

from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig

# Official ESA WorldCover v200 (2021) class legend. Only classes actually
# observed in our sample points get turned into one-hot columns -- see
# one_hot_encode() -- so this dict is documentation of all possible codes,
# not an assumption about what's present in Sikkim.
WORLDCOVER_CLASSES = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse_vegetation",
    70: "snow_ice",
    80: "water",
    90: "herbaceous_wetland",
    95: "mangroves",
    100: "moss_lichen",
}


def sample_land_cover(lons: np.ndarray, lats: np.ndarray, config: MlConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    """Returns a DataFrame with land_cover_code, land_cover_class (readable
    name), and land_cover_nodata (bool) for each (lon, lat) point."""
    with rasterio.open(config.paths.landcover_tif) as src:
        assert str(src.crs) == "EPSG:4326", (
            f"WorldCover CRS is {src.crs}, expected EPSG:4326 to match point coordinates "
            "directly -- do not sample without reprojecting if this ever changes"
        )
        nodata = src.nodata

        codes = []
        for lon, lat in zip(lons, lats):
            row, col = src.index(lon, lat)
            if 0 <= row < src.height and 0 <= col < src.width:
                window = rasterio.windows.Window(col, row, 1, 1)
                value = src.read(1, window=window)[0, 0]
            else:
                value = nodata if nodata is not None else 0
            codes.append(int(value))

    codes = np.array(codes)
    is_nodata = (codes == nodata) if nodata is not None else np.zeros_like(codes, dtype=bool)
    is_unknown = ~np.isin(codes, list(WORLDCOVER_CLASSES.keys())) & ~is_nodata
    if is_unknown.any():
        unknown_codes = sorted(set(codes[is_unknown].tolist()))
        raise ValueError(f"unrecognized WorldCover class code(s) found: {unknown_codes}")

    names = [WORLDCOVER_CLASSES.get(c, "nodata") for c in codes]
    return pd.DataFrame({"land_cover_code": codes, "land_cover_class": names, "land_cover_nodata": is_nodata})


def one_hot_encode(land_cover_class: pd.Series) -> pd.DataFrame:
    """One-hot encodes only the classes actually present -- not all 11
    possible global WorldCover classes, per the feature-suitability design."""
    dummies = pd.get_dummies(land_cover_class, prefix="landcover")
    return dummies.astype(int)


if __name__ == "__main__":
    df = pd.read_csv(DEFAULT_CONFIG.paths.gsi_sikkim_csv)
    result = sample_land_cover(df["Longitude"].values, df["Latitude"].values)
    print(result["land_cover_class"].value_counts())
    print(f"nodata samples: {result['land_cover_nodata'].sum()}")
