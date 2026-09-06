"""Fetches live rainfall (real Open-Meteo data) for the highest-susceptibility
zones -- a defensible, real prioritization: focus live monitoring on the
most dangerous corridors first, not an arbitrary sample. Also gives the
dashboard's "pick a zone for the rainfall card/chart" logic real data to
find regardless of which zone happens to be first in the list.
"""
import asyncio
import sys

import httpx

BACKEND_BASE_URL = "https://landslide-ews-backend.onrender.com"


async def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.get(f"{BACKEND_BASE_URL}/zones")
        resp.raise_for_status()
        zones = resp.json()

    zones = [z for z in zones if z["risk_tier"] == "high"]
    zones.sort(key=lambda z: -(z["susceptibility_score"] or 0))
    zones = zones[:limit]
    print(f"fetching live rainfall for the top {len(zones)} highest-susceptibility zones")

    ok, failed = 0, []
    sem = asyncio.Semaphore(10)

    async def one(client, zone):
        nonlocal ok
        async with sem:
            try:
                resp = await client.post(f"{BACKEND_BASE_URL}/rainfall/{zone['id']}/fetch")
                if resp.status_code == 200:
                    ok += 1
                else:
                    failed.append((zone["name"], resp.status_code, resp.text[:150]))
            except Exception as e:
                failed.append((zone["name"], "exception", str(e)[:150]))

    async with httpx.AsyncClient(timeout=60.0) as client:
        tasks = [one(client, z) for z in zones]
        done = 0
        for coro in asyncio.as_completed(tasks):
            await coro
            done += 1
            if done % 10 == 0:
                print(f"  {done}/{len(zones)}")

    print(f"\nDone: {ok} succeeded, {len(failed)} failed")
    if failed:
        print("failures:", failed[:5])


if __name__ == "__main__":
    asyncio.run(main())
