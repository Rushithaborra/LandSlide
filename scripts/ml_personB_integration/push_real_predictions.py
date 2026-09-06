"""Connects Person B's real, separately-trained susceptibility model to our
backend for real: fetches every zone currently in production (already has a
centroid_lat/centroid_lng, computed server-side), runs each centroid through
B's actual model (real DEM/GSI/RUSLE pipeline, not our own placeholder one),
and pushes the result through our existing, unmodified
PUT /zones/{id}/susceptibility endpoint -- the exact same contract B's own
README describes.

This REPLACES the placeholder susceptibility scores our own groundwork
model previously wrote for these zones, with B's real model's real output.
model_version is set to a name that clearly attributes it to B's model, not
ours, so it's honest which model actually produced any given score if asked.

Points outside B's raster coverage (OutOfCoverageError) are skipped and
reported, not silently defaulted.
"""
import asyncio
import json
import sys
from pathlib import Path

import httpx
import joblib
import pandas as pd

from features import OutOfCoverageError, get_features_at_point

BACKEND_BASE_URL = "https://landslide-ews-backend.onrender.com"
MODEL_DIR = Path(__file__).resolve().parent / "model"

_pipeline = joblib.load(MODEL_DIR / "susceptibility_model.joblib")
_metadata = json.loads((MODEL_DIR / "model_metadata.json").read_text())
FEATURE_COLUMNS = _metadata["numeric_features"] + _metadata["categorical_features"]
MODEL_VERSION = "personB-random_forest-v1-20260902"


def risk_class(score: float) -> str:
    if score < 0.35:
        return "low"
    elif score < 0.65:
        return "moderate"  # B's API calls this "medium"; our schema's vocabulary is "moderate"
    return "high"


def predict(lat: float, lon: float) -> tuple[float, str] | None:
    try:
        features = get_features_at_point(lat, lon)
    except OutOfCoverageError:
        return None
    X = pd.DataFrame([{col: features[col] for col in FEATURE_COLUMNS}])
    score = float(_pipeline.predict_proba(X)[0, 1])
    return score, risk_class(score)


async def push_all(zones: list[dict], concurrency: int = 15) -> dict:
    ok, skipped_out_of_coverage, failed = 0, [], []
    sem = asyncio.Semaphore(concurrency)

    async def one(client, zone):
        nonlocal ok
        result = predict(zone["centroid_lat"], zone["centroid_lng"])
        if result is None:
            skipped_out_of_coverage.append(zone["name"])
            return
        score, tier = result
        async with sem:
            try:
                resp = await client.put(
                    f"{BACKEND_BASE_URL}/zones/{zone['id']}/susceptibility",
                    json={"susceptibility_score": round(score, 4), "risk_tier": tier, "model_version": MODEL_VERSION},
                )
                if resp.status_code == 200:
                    ok += 1
                else:
                    failed.append((zone["id"], resp.status_code, resp.text[:200]))
            except Exception as e:
                failed.append((zone["id"], "exception", str(e)[:200]))

    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [one(client, z) for z in zones]
        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 300 == 0:
                print(f"  processed {done}/{len(zones)}")

    return {"ok": ok, "skipped_out_of_coverage": skipped_out_of_coverage, "failed": failed}


async def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(f"{BACKEND_BASE_URL}/zones")
        resp.raise_for_status()
        zones = resp.json()
    print(f"fetched {len(zones)} zones from production")
    if limit:
        zones = zones[:limit]
        print(f"limiting to first {limit}")

    result = await push_all(zones)
    print(f"\nDone: {result['ok']} updated with B's real model, "
          f"{len(result['skipped_out_of_coverage'])} outside B's raster coverage, "
          f"{len(result['failed'])} failed")
    if result["skipped_out_of_coverage"]:
        print("out of coverage (first 10):", result["skipped_out_of_coverage"][:10])
    if result["failed"]:
        print("failures (first 5):", result["failed"][:5])


if __name__ == "__main__":
    asyncio.run(main())
