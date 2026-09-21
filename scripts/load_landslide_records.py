"""Load a state's GSI landslide inventory into `landslide_records`.

    python scripts/load_landslide_records.py assam [sikkim ...] [--dir PATH]

Reads `<dir>/gsi_<state>_landslides.csv` (default dir: the NER pipeline repo's data/raw,
C:/Users/kilar/LandSlide-ner/data/raw), cleans it with app.services.landslide_records
and REPLACES that state's existing records in one transaction, so re-running with a
corrected file never leaves stale or doubled rows. Prints what was dropped and why.
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import delete

from app.database import SessionLocal
from app.models import LandslideRecord
from app.services.landslide_records import clean_all

DEFAULT_DIR = Path("C:/Users/kilar/LandSlide-ner/data/raw")
STATE_NAMES = {
    "sikkim": "Sikkim", "assam": "Assam", "arunachal_pradesh": "Arunachal Pradesh", "manipur": "Manipur",
    "meghalaya": "Meghalaya", "mizoram": "Mizoram", "nagaland": "Nagaland", "tripura": "Tripura",
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("states", nargs="+", choices=sorted(STATE_NAMES), help="state slug(s), e.g. assam")
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args()

    for slug in args.states:
        state = STATE_NAMES[slug]
        path = args.dir / f"gsi_{slug}_landslides.csv"
        with path.open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        records, dropped = clean_all(rows, state)
        with SessionLocal() as db:
            db.execute(delete(LandslideRecord).where(LandslideRecord.state == state))
            db.add_all(LandslideRecord(**r) for r in records)
            db.commit()
        print(f"{state}: {len(rows)} rows read -> {len(records)} loaded; dropped {dropped['no_coordinates']} without usable coordinates, {dropped['duplicate']} exact duplicates")
    return 0


if __name__ == "__main__":
    sys.exit(main())
