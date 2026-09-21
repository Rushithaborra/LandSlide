"""Fetch IMD's district warnings from this machine and push them to the backend as a snapshot.

    python scripts/push_imd_warnings.py            # dry run: fetch and summarise, send nothing
    python scripts/push_imd_warnings.py --push     # replace the backend's IMD snapshot

The IMD key only works from its registered IP (this laptop), so the live server cannot fetch IMD
itself; run this before a demo and the dashboard shows the snapshot with its age. Needs IMD_API_KEY,
IMD_EMAIL, IMD_PASSWORD in .env, and API_KEY too when the backend enforces the officer key.

Two IMD endpoints are joined on IMD's own district id (Obj_id, the same in every endpoint):
`state_district_rainfall_forecast` says which state each district is in, `districtwarning` has the
5-day warning codes (2 heavy rain, 16 very heavy, 17 extremely heavy, see the IMD API reference) and
colours (1 red, 2 orange, 3 yellow, 4 green). Day 1 is taken to be the issue date, as IMD's bulletins
do; only the issue DATE is used, because the feed's own timestamp has no stated time zone.
"""
import argparse
import os
import sys
from collections import Counter
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.security import auth_headers
from app.services import imd

NER = {"ARUNACHAL PRADESH": "Arunachal Pradesh", "ASSAM": "Assam", "MANIPUR": "Manipur", "MEGHALAYA": "Meghalaya",
       "MIZORAM": "Mizoram", "NAGALAND": "Nagaland", "SIKKIM": "Sikkim", "TRIPURA": "Tripura"}
DEFAULT_BACKEND = "https://landslide-ews-backend.onrender.com"


def parse_codes(value) -> list[int]:
    return [int(part) for part in str(value or "").replace(" ", "").split(",") if part.isdigit()]


def build_rows(warnings: list[dict], districts: list[dict]) -> tuple[list[dict], dict]:
    """Rows for the backend plus a report of which north-east districts IMD's warnings feed lacks."""
    by_id = {w["Obj_id"]: w for w in warnings}
    rows, missing = [], Counter()
    for d in districts:
        state = NER.get(d["State"].strip().upper())
        if state is None:
            continue
        w = by_id.get(d["Obj_id"])
        if w is None:
            missing[state] += 1
            continue
        issued = date.fromisoformat(w["Date"])
        for day in range(1, 6):
            codes = parse_codes(w.get(f"Day_{day}"))
            if not codes or not str(w.get(f"Day{day}_Color", "")).isdigit():
                continue  # nothing usable for this day; a gap is better than a guess
            rows.append({
                "state": state, "district": w["District"].title(), "obj_id": d["Obj_id"], "day": day,
                "valid_date": (issued + timedelta(days=day - 1)).isoformat(), "codes": codes, "color": int(w[f"Day{day}_Color"]),
            })
    return rows, dict(missing)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--push", action="store_true", help="actually replace the backend's snapshot (default: dry run)")
    parser.add_argument("--backend", default=os.environ.get("BACKEND_URL", DEFAULT_BACKEND))
    args = parser.parse_args()

    try:
        warnings = imd.call("districtwarning")
        districts = imd.call("state_district_rainfall_forecast")
    except (imd.ImdNotConfigured, imd.ImdError) as e:
        print(f"IMD: {e}")
        return 1

    rows, missing = build_rows(warnings, districts)
    issued = date.fromisoformat(warnings[0]["Date"])
    rain = Counter(r["state"] for r in rows if {2, 16, 17} & set(r["codes"]))
    print(f"IMD issue date {issued}; {len(rows)} district-days for {len({r['obj_id'] for r in rows})} north-east districts")
    print("districts IMD's warnings feed does not list:", missing or "none")
    print("district-days with a rain warning, by state:", dict(rain) or "none")
    if not args.push:
        print("dry run: nothing sent (add --push)")
        return 0

    payload = {"issued_at": datetime.combine(issued, time.min, tzinfo=timezone.utc).isoformat(), "rows": rows}
    response = httpx.post(f"{args.backend}/imd/warnings", json=payload, headers=auth_headers(), timeout=90)
    print(f"backend: HTTP {response.status_code} {response.text[:200]}")
    return 0 if response.status_code == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
