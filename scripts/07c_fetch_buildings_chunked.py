"""
Buildings kept failing as one query (rate-limited, then repeated 502/504/500
across both Overpass mirrors even after backing off) -- Sikkim's OSM
building count is dense enough, combined with public-server load, that a
single request for the whole state doesn't reliably finish. Splitting into
4 quadrants, each a much smaller ask, with a real pause between requests to
stay well under rate limits.
"""
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

S, W, N, E = 27.03, 87.96, 28.18, 88.97
MID_LAT = (S + N) / 2
MID_LON = (W + E) / 2
QUADRANTS = [
    (S, W, MID_LAT, MID_LON),
    (S, MID_LON, MID_LAT, E),
    (MID_LAT, W, N, MID_LON),
    (MID_LAT, MID_LON, N, E),
]


def run_query(query, label):
    data = urllib.parse.urlencode({"data": query}).encode()
    last_err = None
    for url in OVERPASS_URLS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    url, data=data, headers={"User-Agent": "sih-landslide-ews-data-pipeline/1.0"}
                )
                with urllib.request.urlopen(req, timeout=120) as resp:
                    return json.load(resp)
            except Exception as e:
                print(f"  [{label}] {url} attempt {attempt+1} failed: {e}")
                last_err = e
                time.sleep(15)
    raise last_err


def to_geojson(osm):
    features = []
    for el in osm.get("elements", []):
        tags = el.get("tags", {})
        if el["type"] == "way" and "center" in el:
            geom = {"type": "Point", "coordinates": [el["center"]["lon"], el["center"]["lat"]]}
        elif el["type"] == "node":
            geom = {"type": "Point", "coordinates": [el["lon"], el["lat"]]}
        else:
            continue
        features.append({"type": "Feature", "geometry": geom, "properties": {"osm_id": el["id"], **tags}})
    return features


def main():
    all_features = []
    for i, (s, w, n, e) in enumerate(QUADRANTS):
        bbox = f"{s},{w},{n},{e}"
        query = f"""
        [out:json][timeout:90];
        way["building"]({bbox});
        out center;
        """
        print(f"Quadrant {i+1}/4 ({bbox})...")
        osm = run_query(query, f"buildings-q{i+1}")
        feats = to_geojson(osm)
        print(f"  {len(feats)} buildings")
        all_features.extend(feats)
        if i < len(QUADRANTS) - 1:
            time.sleep(20)  # stay well clear of rate limits between quadrants

    gj = {"type": "FeatureCollection", "features": all_features}
    path = RAW / "sikkim_buildings.geojson"
    with open(path, "w") as f:
        json.dump(gj, f)
    print(f"\nWrote {path} ({len(all_features)} buildings total)")


if __name__ == "__main__":
    main()
