"""Read-only test of the IMD API from this machine (the key only works from its registered IP).

    python scripts/imd_probe.py districtwarning [--id 164]
    python scripts/imd_probe.py districtrainfall
    python scripts/imd_probe.py aws_data --param sid=18

Needs IMD_API_KEY, IMD_EMAIL and IMD_PASSWORD in .env. Prints the response's shape and a short
sample, and saves the full response to data/interim/imd_<endpoint>.json (gitignored) so it can be
studied without calling IMD again. Never prints the key, the password or the token.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services import imd


def describe(data, depth: int = 0) -> str:
    if isinstance(data, list):
        first = describe(data[0], depth + 1) if data else "empty"
        return f"list of {len(data)} -> {first}"
    if isinstance(data, dict):
        return "object with keys " + ", ".join(list(data)[:15]) + (" ..." if len(data) > 15 else "")
    return type(data).__name__


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("endpoint", help="e.g. districtwarning (see https://api.imd.gov.in/public/api_reference.html)")
    parser.add_argument("--id")
    parser.add_argument("--param", action="append", default=[], help="extra query parameter, key=value (repeatable)")
    args = parser.parse_args()

    params = dict(p.split("=", 1) for p in args.param)
    if args.id:
        params["id"] = args.id
    try:
        data = imd.call(args.endpoint, params)
    except imd.ImdNotConfigured as e:
        print(f"not configured: {e}")
        return 2
    except imd.ImdError as e:
        print(f"IMD error: {e}")
        return 1

    out = Path("data/interim") / f"imd_{args.endpoint}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{args.endpoint}: {describe(data)}")
    sample = data[0] if isinstance(data, list) and data else data
    print(json.dumps(sample, ensure_ascii=False)[:600])
    print(f"full response saved to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
