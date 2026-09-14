"""
Shared per-state configuration for the NER expansion (Assam, Arunachal
Pradesh, Manipur, Meghalaya, Mizoram, Nagaland -- the 6 states that cleared
the >=~500-landslide-record modeling threshold; Tripura, at 66 records, did
not and is intentionally excluded from this registry).

One config dict, imported by every generalized pipeline script
(18_run_state_pipeline.py, 19_fetch_state_roads_and_negatives.py,
20_build_state_training_dataset.py) -- not a copy of scripts 01/06/09/10/11
per state. This is the "STATE_CONFIGS" the task brief expected to already
exist as scripts/ml/ml_config.py; it doesn't, so this is a fresh one,
scoped to what this expansion actually needs.

Boundary source: geoBoundaries.org IND-ADM1 (same source Sikkim's own
boundary came from, per data/PROVENANCE.md and README.md -- not GADM,
which the original task brief assumed without that being what this repo
actually used).

UTM: computed from each state's own real bbox (zone = floor((lon+180)/6)+1),
not copied from Sikkim's 45N. Assam, Arunachal Pradesh and Meghalaya each
span more than one standard 6-deg UTM zone -- rather than picking one zone
and absorbing the distortion, those three use a custom Transverse Mercator
centered on the state's own mean longitude (a standard technique for
regional analysis that doesn't fit a single UTM zone), flagged explicitly
below via `custom_proj`.
"""
import math

# state slug -> (boundary geojson properties.shapeName in the geoBoundaries
# IND-ADM1 file, which uses diacritics for some names)
GEOBOUNDARIES_NAME = {
    "assam": "Assam",
    "arunachal_pradesh": "Arunāchal Pradesh",
    "manipur": "Manipur",
    "meghalaya": "Meghālaya",
    "mizoram": "Mizoram",
    "nagaland": "Nāgāland",
}

# bbox = (minx/west, miny/south, maxx/east, maxy/north), computed from the
# real geoBoundaries polygon on 2026-09-13 -- see data/raw/<state>_boundary.geojson
STATE_CONFIGS = {
    "assam": {
        "display_name": "Assam",
        "bbox": (89.699, 24.136, 96.018, 27.972),
        "utm_epsg": None,  # spans zones 45N-47N -- see custom_proj
        "custom_proj": "+proj=tmerc +lat_0=0 +lon_0=92.86 +k=0.9996 +x_0=500000 +y_0=0 +datum=WGS84 +units=m +no_defs",
        "utm_zone_note": "bbox spans UTM zones 45N-47N (89.7-96.0E) -- custom transverse "
                          "Mercator centered on the state's own mean longitude (92.86E) used "
                          "instead of forcing one standard zone",
        "dem_tiles": None,  # computed at runtime from bbox
        "worldcover_tiles": None,
    },
    "arunachal_pradesh": {
        "display_name": "Arunachal Pradesh",
        "bbox": (91.546, 26.651, 97.411, 29.462),
        "utm_epsg": None,  # spans zones 46N-47N (and touches 48N at the very NE tip)
        "custom_proj": "+proj=tmerc +lat_0=0 +lon_0=94.48 +k=0.9996 +x_0=500000 +y_0=0 +datum=WGS84 +units=m +no_defs",
        "utm_zone_note": "bbox spans 91.5-97.4E, crossing UTM zones 46N/47N (and the very "
                          "NE tip approaches 48N) -- exactly the multi-zone case flagged in "
                          "the task brief. Custom transverse Mercator centered on 94.48E used.",
        "dem_tiles": None,
        "worldcover_tiles": None,
    },
    "manipur": {
        "display_name": "Manipur",
        "bbox": (92.971, 23.833, 94.745, 25.692),
        "utm_epsg": 32646,
        "custom_proj": None,
        "utm_zone_note": "single zone (46N), like Sikkim's single-zone case",
        "dem_tiles": None,
        "worldcover_tiles": None,
    },
    "meghalaya": {
        "display_name": "Meghalaya",
        "bbox": (89.814, 25.029, 92.803, 26.120),
        "utm_epsg": None,  # spans 45N-46N
        "custom_proj": "+proj=tmerc +lat_0=0 +lon_0=91.31 +k=0.9996 +x_0=500000 +y_0=0 +datum=WGS84 +units=m +no_defs",
        "utm_zone_note": "bbox spans UTM zones 45N-46N (89.8-92.8E) -- custom transverse "
                          "Mercator centered on 91.31E used instead of one standard zone",
        "dem_tiles": None,
        "worldcover_tiles": None,
    },
    "mizoram": {
        "display_name": "Mizoram",
        "bbox": (92.257, 21.941, 93.436, 24.521),
        "utm_epsg": 32646,
        "custom_proj": None,
        "utm_zone_note": "single zone (46N)",
        "dem_tiles": None,
        "worldcover_tiles": None,
    },
    "nagaland": {
        "display_name": "Nagaland",
        "bbox": (93.327, 25.199, 95.242, 27.036),
        "utm_epsg": 32646,
        "custom_proj": None,
        "utm_zone_note": "single zone (46N)",
        "dem_tiles": None,
        "worldcover_tiles": None,
    },
}


def dem_tile_list(bbox, margin_deg=0.0):
    """Copernicus GLO-30 tiles are 1x1 degree, named by their SW corner."""
    minx, miny, maxx, maxy = bbox
    lat0, lat1 = int(math.floor(miny - margin_deg)), int(math.floor(maxy + margin_deg))
    lon0, lon1 = int(math.floor(minx - margin_deg)), int(math.floor(maxx + margin_deg))
    tiles = []
    for lat in range(lat0, lat1 + 1):
        for lon in range(lon0, lon1 + 1):
            ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
            ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
            tiles.append(f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM")
    return tiles


def worldcover_tile_list(bbox, margin_deg=0.0):
    """ESA WorldCover 2021 v200 tiles are 3x3 degree, named by their SW
    corner rounded down to a multiple of 3."""
    minx, miny, maxx, maxy = bbox
    lat0 = int(math.floor((miny - margin_deg) / 3) * 3)
    lat1 = int(math.floor((maxy + margin_deg) / 3) * 3)
    lon0 = int(math.floor((minx - margin_deg) / 3) * 3)
    lon1 = int(math.floor((maxx + margin_deg) / 3) * 3)
    tiles = []
    for lat in range(lat0, lat1 + 1, 3):
        for lon in range(lon0, lon1 + 1, 3):
            ns = f"N{lat:02d}" if lat >= 0 else f"S{-lat:02d}"
            ew = f"E{lon:03d}" if lon >= 0 else f"W{-lon:03d}"
            tiles.append(f"ESA_WorldCover_10m_2021_v200_{ns}{ew}_Map")
    return tiles


for _slug, _cfg in STATE_CONFIGS.items():
    _cfg["dem_tiles"] = dem_tile_list(_cfg["bbox"])
    _cfg["worldcover_tiles"] = worldcover_tile_list(_cfg["bbox"])
    _cfg["dst_crs"] = f"EPSG:{_cfg['utm_epsg']}" if _cfg["utm_epsg"] else _cfg["custom_proj"]


if __name__ == "__main__":
    for slug, cfg in STATE_CONFIGS.items():
        print(f"{cfg['display_name']:<20} dem_tiles={len(cfg['dem_tiles']):3d}  "
              f"worldcover_tiles={len(cfg['worldcover_tiles']):2d}  crs={cfg['dst_crs'][:50]}")
