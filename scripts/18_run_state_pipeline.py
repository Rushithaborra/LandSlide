"""
Generalized version of scripts/01 (DEM mosaic/clip/reproject/slope/aspect),
06 (drainage density), 09 (land cover), 10 (soil K-factor) and 11 (LS/C
factor) -- parameterized by state via ner_config.STATE_CONFIGS, instead of
copy-pasting each script per state. Sikkim's original numbered scripts are
untouched; this is the same algorithms, generalized.

Usage: python3 scripts/18_run_state_pipeline.py <state_slug>
  e.g. python3 scripts/18_run_state_pipeline.py manipur

Downloads DEM tiles (Copernicus GLO-30) and WorldCover tiles from their
public S3 buckets if not already cached in data/raw/, mosaics/clips/
reprojects to the state's CRS (a standard UTM zone, or a custom transverse
Mercator for states whose bbox spans more than one UTM zone -- see
ner_config.py), derives slope/aspect/drainage/land-cover/soil-K/LS/C, same
methods as the Sikkim scripts including their documented bug fixes
(explicit -9999 nodata through the whole raster chain; resampling every
layer onto the DEM's exact grid before array-level combination).

Outputs (data/processed/, all suffixed by state):
  dem_<state>.tif, slope_deg_<state>.tif, aspect_deg_<state>.tif
  streams_<state>.tif, distance_to_stream_m_<state>.tif
  landcover_<state>.tif
  soil_{clay,sand,silt,soc}_<state>.tif, rusle_k_factor_<state>.tif
  flow_accumulation_<state>.tif, rusle_ls_factor_<state>.tif, rusle_c_factor_<state>.tif
"""
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.merge import merge
from rasterio.warp import calculate_default_transform, reproject, Resampling

np.in1d = np.isin  # pysheds compatibility shim -- np.in1d was removed in numpy 2.x+ (harmless no-op on numpy versions that still have it)
from pysheds.grid import Grid

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ner_config import STATE_CONFIGS

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)
NODATA = -9999.0

DEM_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
WORLDCOVER_BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map"
SOIL_WCS = "https://maps.isric.org/mapserv"

C_FACTOR_BY_CLASS = {
    10: 0.001, 20: 0.014, 30: 0.05, 40: 0.15, 50: 0.01,
    60: 0.45, 70: 0.0, 80: 0.0, 90: 0.01, 95: 0.001, 100: 0.05,
}
MAX_SLOPE_LENGTH_M = 300.0
ACC_THRESHOLD = 500


def download(url, dest, timeout=60, retries=3):
    """urlretrieve has no built-in timeout and can hang indefinitely on a
    stalled connection (caught in practice: a Manipur DEM tile download sat
    with zero network activity for 30+ minutes). Stream via urlopen with an
    explicit socket timeout instead, and retry a bounded number of times.

    Some states' bboxes overlap (e.g. Assam borders nearly every other NER
    state), so two state pipelines run in parallel can both want the same
    DEM/WorldCover tile. The temp filename includes the PID so two
    processes downloading the same tile never write to the same path --
    worst case both fully download it (wasted bandwidth, not corruption),
    and whichever renames-into-place last wins with an equally-valid file.
    """
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    print(f"  downloading {url} ...", flush=True)
    last_err = None
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                expected_len = resp.headers.get("Content-Length")
                expected_len = int(expected_len) if expected_len else None
                tmp_dest = dest.with_suffix(dest.suffix + f".{os.getpid()}.part")
                n_written = 0
                with open(tmp_dest, "wb") as f:
                    while True:
                        chunk = resp.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        n_written += len(chunk)
                if expected_len is not None and n_written != expected_len:
                    tmp_dest.unlink()
                    raise IOError(f"truncated download: got {n_written} bytes, expected {expected_len}")
                tmp_dest.rename(dest)
            return dest
        except Exception as e:
            last_err = e
            print(f"    attempt {attempt+1}/{retries} failed: {e}", flush=True)
    raise RuntimeError(f"download failed after {retries} attempts: {url} ({last_err})")


def fetch_dem_tiles(cfg):
    paths = []
    for tile in cfg["dem_tiles"]:
        dest = RAW / f"{tile}.tif"
        url = f"{DEM_BASE}/{tile}/{tile}.tif"
        try:
            download(url, dest)
            paths.append(dest)
        except Exception as e:
            print(f"  WARNING: tile {tile} failed ({e}) -- skipping; coverage may have a gap")
    return paths


def fetch_worldcover_tiles(cfg):
    paths = []
    for tile in cfg["worldcover_tiles"]:
        dest = RAW / f"{tile}.tif"
        url = f"{WORLDCOVER_BASE}/{tile}.tif"
        try:
            download(url, dest)
            paths.append(dest)
        except Exception as e:
            print(f"  WARNING: WorldCover tile {tile} not available ({e}) -- likely open ocean/out of coverage, skipping")
    return paths


def boundary_geoms(slug):
    with open(RAW / f"{slug}_boundary.geojson") as f:
        gj = json.load(f)
    return [feat["geometry"] for feat in gj["features"]]


def mosaic_clip_reproject_dem(dem_paths, geoms, dst_crs):
    srcs = [rasterio.open(p) for p in dem_paths]
    mosaic_arr, mosaic_transform = merge(srcs, nodata=NODATA)
    meta = srcs[0].meta.copy()
    meta.update(driver="GTiff", height=mosaic_arr.shape[1], width=mosaic_arr.shape[2],
                transform=mosaic_transform, nodata=NODATA)
    for s in srcs:
        s.close()

    tmp_path = PROCESSED / f"_mosaic_tmp_{os.getpid()}.tif"
    with rasterio.open(tmp_path, "w", **meta) as tmp:
        tmp.write(mosaic_arr)
    with rasterio.open(tmp_path) as src:
        out_arr, out_transform = mask(src, geoms, crop=True, nodata=NODATA)
        out_meta = src.meta.copy()
    out_meta.update(height=out_arr.shape[1], width=out_arr.shape[2], transform=out_transform, nodata=NODATA)
    tmp_path.unlink()

    src_crs = out_meta["crs"]
    transform, width, height = calculate_default_transform(
        src_crs, dst_crs, out_meta["width"], out_meta["height"],
        *rasterio.transform.array_bounds(out_meta["height"], out_meta["width"], out_meta["transform"]),
    )
    dst_meta = out_meta.copy()
    dst_meta.update(crs=dst_crs, transform=transform, width=width, height=height, nodata=NODATA)
    dst_arr = np.full((out_arr.shape[0], height, width), NODATA, dtype=out_arr.dtype)
    for i in range(out_arr.shape[0]):
        reproject(source=out_arr[i], destination=dst_arr[i],
                  src_transform=out_meta["transform"], src_crs=src_crs, src_nodata=NODATA,
                  dst_transform=transform, dst_crs=dst_crs, dst_nodata=NODATA,
                  resampling=Resampling.bilinear)
    return dst_arr, dst_meta


def slope_aspect(elev, pixel_size, nodata=NODATA):
    z = elev.astype(np.float64)
    valid = elev != nodata
    px = pixel_size
    zp = np.pad(z, 1, mode="edge")
    validp = np.pad(valid, 1, mode="edge")
    a = zp[:-2, :-2]; b = zp[:-2, 1:-1]; c = zp[:-2, 2:]
    d = zp[1:-1, :-2];                    f = zp[1:-1, 2:]
    g = zp[2:, :-2];  h = zp[2:, 1:-1];   i = zp[2:, 2:]
    window_valid = np.all(
        [validp[:-2, :-2], validp[:-2, 1:-1], validp[:-2, 2:],
         validp[1:-1, :-2], validp[1:-1, 1:-1], validp[1:-1, 2:],
         validp[2:, :-2], validp[2:, 1:-1], validp[2:, 2:]], axis=0)
    dzdx = ((c + 2 * f + i) - (a + 2 * d + g)) / (8 * px)
    dzdy = ((g + 2 * h + i) - (a + 2 * b + c)) / (8 * px)
    slope_rad = np.arctan(np.sqrt(dzdx ** 2 + dzdy ** 2))
    slope_deg = np.degrees(slope_rad)
    aspect_rad = np.arctan2(dzdy, -dzdx)
    aspect_deg = np.degrees(aspect_rad)
    aspect_deg = np.mod(90.0 - aspect_deg, 360.0)
    slope_deg = np.where(window_valid, slope_deg, nodata).astype(np.float32)
    aspect_deg = np.where(window_valid, aspect_deg, nodata).astype(np.float32)
    return slope_deg, aspect_deg


def resample_to_grid(path, dem_meta, resampling):
    with rasterio.open(path) as src:
        src_nodata = src.nodata
        out = np.full((dem_meta["height"], dem_meta["width"]), src_nodata, dtype=src.dtypes[0])
        reproject(source=rasterio.band(src, 1), destination=out,
                  src_transform=src.transform, src_crs=src.crs, src_nodata=src_nodata,
                  dst_transform=dem_meta["transform"], dst_crs=dem_meta["crs"], dst_nodata=src_nodata,
                  resampling=resampling)
    return out, src_nodata


def williams_k_factor(sand_pct, silt_pct, clay_pct, oc_pct):
    sn1 = 1 - sand_pct / 100
    f_csand = 0.2 + 0.3 * np.exp(-0.256 * sand_pct * (1 - silt_pct / 100))
    f_clsi = (silt_pct / (clay_pct + silt_pct + 1e-9)) ** 0.3
    f_orgc = 1 - (0.25 * oc_pct) / (oc_pct + np.exp(3.72 - 2.95 * oc_pct))
    f_hisand = 1 - (0.7 * sn1) / (sn1 + np.exp(-5.51 + 22.9 * sn1))
    return f_csand * f_clsi * f_orgc * f_hisand


def run(slug):
    import requests
    cfg = STATE_CONFIGS[slug]
    dst_crs = cfg["dst_crs"]
    print(f"=== {cfg['display_name']} ({slug}) ===")
    print(f"  bbox: {cfg['bbox']}  |  {cfg['utm_zone_note']}")

    print(f"\n[1/6] Fetching {len(cfg['dem_tiles'])} DEM tiles...")
    dem_paths = fetch_dem_tiles(cfg)
    print(f"  {len(dem_paths)}/{len(cfg['dem_tiles'])} tiles available")

    geoms = boundary_geoms(slug)

    print(f"\n[2/6] Mosaicking, clipping to {cfg['display_name']} boundary, reprojecting to {dst_crs[:40]}...")
    dem_arr, dem_meta = mosaic_clip_reproject_dem(dem_paths, geoms, dst_crs)
    pixel_size = dem_meta["transform"][0]
    print(f"  shape: {dem_arr.shape}, pixel size: {pixel_size:.2f} m")

    dem_path = PROCESSED / f"dem_{slug}.tif"
    out_meta = dem_meta.copy()
    out_meta.update(driver="GTiff", count=1, compress="deflate", dtype="float32", nodata=NODATA)
    with rasterio.open(dem_path, "w", **out_meta) as dst:
        dst.write(dem_arr[0].astype(np.float32), 1)
    print(f"  wrote {dem_path}")

    elev_valid = dem_arr[0][dem_arr[0] != NODATA]
    print(f"  elevation range: {elev_valid.min():.1f} - {elev_valid.max():.1f} m "
          f"({100*elev_valid.size/dem_arr[0].size:.1f}% valid pixels)")

    print("\n  Computing slope + aspect (Horn's method)...")
    slope_deg, aspect_deg = slope_aspect(dem_arr[0], pixel_size)
    with rasterio.open(PROCESSED / f"slope_deg_{slug}.tif", "w", **out_meta) as dst:
        dst.write(slope_deg, 1)
    with rasterio.open(PROCESSED / f"aspect_deg_{slug}.tif", "w", **out_meta) as dst:
        dst.write(aspect_deg, 1)
    print(f"  slope range: {slope_deg[slope_deg!=NODATA].min():.1f} - {slope_deg[slope_deg!=NODATA].max():.1f} deg")

    print(f"\n[3/6] Drainage density (pysheds: fill -> flow dir -> accumulation -> threshold -> distance)...")
    grid = Grid.from_raster(str(dem_path))
    dem_r = grid.read_raster(str(dem_path))
    pit_filled = grid.fill_pits(dem_r)
    flooded = grid.fill_depressions(pit_filled)
    inflated = grid.resolve_flats(flooded)
    fdir = grid.flowdir(inflated)
    acc = grid.accumulation(fdir)
    acc_arr = np.asarray(acc)
    streams = (acc_arr > ACC_THRESHOLD).astype(np.uint8)
    valid_mask = dem_arr[0] != NODATA
    n_stream_px = int(streams.sum())
    print(f"  {n_stream_px} stream pixels ({100*n_stream_px/streams.size:.2f}%)")
    if n_stream_px == 0:
        print("  WARNING: no stream pixels extracted at this threshold -- distance-to-stream will be meaningless")
    from scipy.ndimage import distance_transform_edt
    dist_px = distance_transform_edt(streams == 0) if n_stream_px > 0 else np.full(streams.shape, NODATA)
    dist_m = (dist_px * pixel_size).astype(np.float32)
    dist_m = np.where(valid_mask, dist_m, NODATA).astype(np.float32)
    with rasterio.open(PROCESSED / f"distance_to_stream_m_{slug}.tif", "w", **out_meta) as dst:
        dst.write(dist_m, 1)

    acc_out = np.where(valid_mask, acc_arr, NODATA).astype(np.float32)
    with rasterio.open(PROCESSED / f"flow_accumulation_{slug}.tif", "w", **out_meta) as dst:
        dst.write(acc_out, 1)
    print(f"  wrote distance_to_stream_m_{slug}.tif, flow_accumulation_{slug}.tif")

    print(f"\n[4/6] Fetching {len(cfg['worldcover_tiles'])} ESA WorldCover tile(s)...")
    wc_paths = fetch_worldcover_tiles(cfg)
    if not wc_paths:
        raise RuntimeError(f"No WorldCover tiles available for {slug} -- cannot proceed without land cover")

    print(f"  Mosaicking, clipping, reprojecting land cover...")
    wc_srcs = [rasterio.open(p) for p in wc_paths]
    wc_nodata = 255
    wc_mosaic, wc_transform = merge(wc_srcs, nodata=wc_nodata)
    wc_meta = wc_srcs[0].meta.copy()
    wc_meta.update(height=wc_mosaic.shape[1], width=wc_mosaic.shape[2], transform=wc_transform, nodata=wc_nodata)
    for s in wc_srcs:
        s.close()
    tmp_path = PROCESSED / f"_wc_mosaic_tmp_{os.getpid()}.tif"
    with rasterio.open(tmp_path, "w", **wc_meta) as tmp:
        tmp.write(wc_mosaic)
    with rasterio.open(tmp_path) as src:
        wc_clip, wc_clip_transform = mask(src, geoms, crop=True, nodata=wc_nodata)
        wc_clip_meta = src.meta.copy()
    wc_clip_meta.update(height=wc_clip.shape[1], width=wc_clip.shape[2], transform=wc_clip_transform, nodata=wc_nodata)
    tmp_path.unlink()

    lc_transform, lc_w, lc_h = calculate_default_transform(
        wc_clip_meta["crs"], dst_crs, wc_clip_meta["width"], wc_clip_meta["height"],
        *rasterio.transform.array_bounds(wc_clip_meta["height"], wc_clip_meta["width"], wc_clip_meta["transform"]))
    lc_arr = np.full((lc_h, lc_w), wc_nodata, dtype=np.uint8)
    reproject(source=wc_clip[0], destination=lc_arr,
              src_transform=wc_clip_meta["transform"], src_crs=wc_clip_meta["crs"], src_nodata=wc_nodata,
              dst_transform=lc_transform, dst_crs=dst_crs, dst_nodata=wc_nodata, resampling=Resampling.nearest)
    lc_path = PROCESSED / f"landcover_{slug}.tif"
    lc_meta = wc_clip_meta.copy()
    lc_meta.update(crs=dst_crs, transform=lc_transform, width=lc_w, height=lc_h, compress="deflate")
    with rasterio.open(lc_path, "w", **lc_meta) as dst:
        dst.write(lc_arr, 1)
    print(f"  wrote {lc_path}")

    print(f"\n[5/6] Fetching ISRIC SoilGrids (clay/sand/silt/soc, 0-5cm) for bbox {cfg['bbox']}...")
    minx, miny, maxx, maxy = cfg["bbox"]
    soil_bbox = (minx - 0.1, miny - 0.1, maxx + 0.1, maxy + 0.1)
    processed_soil = {}
    for prop in ["clay", "sand", "silt", "soc"]:
        raw_path = RAW / f"soil_{prop}_{slug}_0-5cm.tif"
        if not raw_path.exists():
            params = {
                "map": f"/map/{prop}.map", "SERVICE": "WCS", "VERSION": "2.0.1",
                "REQUEST": "GetCoverage", "COVERAGEID": f"{prop}_0-5cm_mean",
                "FORMAT": "GEOTIFF_INT16",
                "SUBSET": [f"X({soil_bbox[0]},{soil_bbox[2]})", f"Y({soil_bbox[1]},{soil_bbox[3]})"],
                "SUBSETTINGCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
                "OUTPUTCRS": "http://www.opengis.net/def/crs/EPSG/0/4326",
            }
            # Unprotected single-shot request here is what killed the first
            # Nagaland run (ConnectionResetError mid-handshake) -- add the
            # same retry treatment as every other network call in this file.
            last_err = None
            for attempt in range(3):
                try:
                    resp = requests.get(SOIL_WCS, params=params, timeout=120)
                    resp.raise_for_status()
                    with open(raw_path, "wb") as f:
                        f.write(resp.content)
                    break
                except Exception as e:
                    last_err = e
                    print(f"  {prop} fetch attempt {attempt+1}/3 failed: {e}")
                    if attempt < 2:
                        time.sleep(10 * (attempt + 1))
            else:
                raise RuntimeError(f"SoilGrids fetch for {prop} failed after 3 attempts: {last_err}")
            print(f"  fetched {prop} ({raw_path.stat().st_size:,} bytes)")

        soil_nodata = -9999
        with rasterio.open(raw_path) as src:
            s_arr, s_transform = mask(src, geoms, crop=True, nodata=soil_nodata)
            s_meta = src.meta.copy()
            s_meta.update(height=s_arr.shape[1], width=s_arr.shape[2], transform=s_transform, nodata=soil_nodata)
        s_dst_transform, s_w, s_h = calculate_default_transform(
            s_meta["crs"], dst_crs, s_meta["width"], s_meta["height"],
            *rasterio.transform.array_bounds(s_meta["height"], s_meta["width"], s_meta["transform"]))
        s_out = np.full((s_h, s_w), soil_nodata, dtype=s_arr.dtype)
        reproject(source=s_arr[0], destination=s_out,
                  src_transform=s_meta["transform"], src_crs=s_meta["crs"], src_nodata=soil_nodata,
                  dst_transform=s_dst_transform, dst_crs=dst_crs, dst_nodata=soil_nodata, resampling=Resampling.bilinear)
        out_path = PROCESSED / f"soil_{prop}_{slug}.tif"
        s_out_meta = s_meta.copy()
        s_out_meta.update(crs=dst_crs, transform=s_dst_transform, width=s_w, height=s_h, compress="deflate")
        with rasterio.open(out_path, "w", **s_out_meta) as dst:
            dst.write(s_out, 1)
        processed_soil[prop] = (s_out, s_out_meta)

    clay_arr, k_meta = processed_soil["clay"]
    sand_arr = processed_soil["sand"][0]
    silt_arr = processed_soil["silt"][0]
    soc_arr = processed_soil["soc"][0]
    k_nodata = k_meta["nodata"]
    k_valid_mask = (clay_arr != k_nodata) & (sand_arr != k_nodata) & (silt_arr != k_nodata) & (soc_arr != k_nodata)
    clay_pct, sand_pct, silt_pct = clay_arr / 10, sand_arr / 10, silt_arr / 10
    oc_pct = np.clip(soc_arr / 10, 0.01, None)
    k_vals = williams_k_factor(sand_pct, silt_pct, clay_pct, oc_pct)
    k_out = np.where(k_valid_mask, k_vals, k_nodata).astype(np.float32)
    k_path = PROCESSED / f"rusle_k_factor_{slug}.tif"
    k_out_meta = k_meta.copy()
    k_out_meta.update(dtype="float32", nodata=float(k_nodata))
    with rasterio.open(k_path, "w", **k_out_meta) as dst:
        dst.write(k_out, 1)
    print(f"  wrote {k_path}")

    print(f"\n[6/6] LS-factor (Moore & Burch 1986) + C-factor (land cover reclass)...")
    slope_rad = np.radians(np.clip(slope_deg, 0, 89.9))
    acc_safe = np.clip(acc_arr, 0, None)
    upslope_length = np.clip(acc_safe * pixel_size, None, MAX_SLOPE_LENGTH_M)
    ls_valid = valid_mask & (slope_deg != NODATA) & (acc_arr >= 0)
    ls = (upslope_length / 22.13) ** 0.4 * (np.sin(slope_rad) / 0.0896) ** 1.3
    ls_out = np.where(ls_valid, ls, NODATA).astype(np.float32)
    with rasterio.open(PROCESSED / f"rusle_ls_factor_{slug}.tif", "w", **out_meta) as dst:
        dst.write(ls_out, 1)

    lc_regrid, lc_regrid_nodata = resample_to_grid(lc_path, dem_meta, Resampling.nearest)
    c_out = np.full(lc_regrid.shape, NODATA, dtype=np.float32)
    lc_valid = lc_regrid != lc_regrid_nodata
    for code, c_val in C_FACTOR_BY_CLASS.items():
        c_out[lc_valid & (lc_regrid == code)] = c_val
    with rasterio.open(PROCESSED / f"rusle_c_factor_{slug}.tif", "w", **out_meta) as dst:
        dst.write(c_out, 1)
    print(f"  wrote rusle_ls_factor_{slug}.tif, rusle_c_factor_{slug}.tif")

    print(f"\n=== {cfg['display_name']} terrain/soil/landcover pipeline complete ===")


if __name__ == "__main__":
    slug = sys.argv[1]
    run(slug)
