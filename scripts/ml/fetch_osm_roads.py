"""Download OpenStreetMap road geometry for the pilot corridor via the
Overpass API -- public, no key, no login.

Note: the Overpass server returns 406 Not Acceptable without an explicit
User-Agent/Accept header on some client configurations (verified during the
data audit) -- this is why the headers below aren't optional decoration.

I/O note: geopandas' file read/write (`to_file`/`read_file`) needs pyogrio
or fiona, both GDAL-backed -- pyogrio's compiled extension is blocked by an
Application Control policy in this environment (verified: persistent, not a
one-off). So GeoJSON is read/written directly via the stdlib `json` module
plus shapely's `mapping`/`shape`, and only assembled into a GeoDataFrame
in-memory (which needs no GDAL backend, verified separately)."""
import json
import pathlib

import geopandas as gpd
import httpx
from shapely.geometry import LineString, mapping, shape

from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig


def fetch_roads_geojson(config: MlConfig = DEFAULT_CONFIG) -> pathlib.Path:
    if config.paths.roads_geojson.exists():
        return config.paths.roads_geojson

    south, west, north, east = config.roads.bbox
    query = f'[out:json][timeout:90];(way["highway"]({south},{west},{north},{east}););out geom;'
    headers = {"User-Agent": "sih-landslide-prototype/1.0", "Accept": "application/json"}
    response = httpx.get(config.roads.overpass_url, params={"data": query}, headers=headers, timeout=120.0)
    response.raise_for_status()
    data = response.json()

    lines = [
        LineString([(pt["lon"], pt["lat"]) for pt in el["geometry"]])
        for el in data["elements"]
        if el["type"] == "way" and "geometry" in el and len(el["geometry"]) >= 2
    ]
    feature_collection = {
        "type": "FeatureCollection",
        "features": [{"type": "Feature", "properties": {}, "geometry": mapping(line)} for line in lines],
    }

    config.paths.roads_geojson.parent.mkdir(parents=True, exist_ok=True)
    with open(config.paths.roads_geojson, "w") as f:
        json.dump(feature_collection, f)
    return config.paths.roads_geojson


def load_roads(config: MlConfig = DEFAULT_CONFIG) -> gpd.GeoDataFrame:
    path = fetch_roads_geojson(config)
    with open(path) as f:
        feature_collection = json.load(f)
    lines = [shape(feat["geometry"]) for feat in feature_collection["features"]]
    return gpd.GeoDataFrame(geometry=lines, crs="EPSG:4326")


def main(config: MlConfig = DEFAULT_CONFIG) -> None:
    gdf = load_roads(config)
    print(f"road segments: {len(gdf)}")
    print(f"saved to: {config.paths.roads_geojson}")


if __name__ == "__main__":
    main()
