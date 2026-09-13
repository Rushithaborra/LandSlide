"""Investigates and resolves data-quality issues found in the 635-record GSI
Assam positive inventory during initial dataset review (2026-09-13).

Findings differ in kind from Sikkim's (see resolve_duplicate_positives.py):
Sikkim had 3 pairs of rows sharing an identical 6-decimal-place coordinate --
strong evidence of the same physical site logged twice. Assam's raw export
has ~30 groups of rows sharing a coordinate rounded to only 2 decimal places
(~1km precision) -- e.g. six separate Slide_No entries all logged at exactly
(26.56, 94.36) along "Mariani-Chanki Rd", Jorhat. These almost certainly are
distinct slides along the same road/nala recorded with coarse field GPS, not
duplicate entries of one event -- unlike Sikkim's case, there is no evidence
(matching Slide_Name, matching History, sequential-looking metadata) that
they are the same record. Treating "same rounded coordinate" as duplication
here would discard ~10% of a hard-sourced real dataset on weak grounds, so
this script does NOT dedupe on coordinate alone the way Sikkim's script did.

Two narrower, well-evidenced issues are handled instead:

1. Literal duplicate entry: Sl_No 28 and 190 share the same Slide_No
   ("AS/NC/83G04/2009/B-5"), same Slide_Name ("Phaiding Landslide"), same
   District, same coordinates -- the identical Slide_No is the giveaway this
   is one survey record entered into the export twice, not two events.

2. Geolocation outliers: rows whose district label is inconsistent with
   where every other same-district point actually falls. Every other "Dima
   Hasao" point clusters at ~24.9-25.8N, ~92.7-93.5E; three rows fall far
   outside that box under the same district label:
   - Sl_No 28/190 (26.20261, 91.14528) -- ~180km from the Dima Hasao cluster,
     actually sitting in the Kamrup/Nagaon longitude band. Also the literal
     duplicate from #1.
   - Sl_No 449 "Dautohaja Tunnel No. 3 slide" (26.098167, 91.881278) -- same
     issue, lands in the Kamrup Metro area, not Dima Hasao.
   - Sl_No 481 "Bandarkhal landslide" (26.11, 94.76) -- Bandarkhal is a real,
     repeatedly-surveyed site elsewhere in this same dataset (Sl_No 108, 182,
     286, 381, 425, 442, 489, 511, 525, 610, all at ~25.04-25.06N/92.79-92.81E)
     -- this row's coordinate is off by whole degrees, almost certainly a
     transcription error, not a second Bandarkhal.
   - Sl_No 561 "Jatinga Lampur landslide" (25.146306, 93.942167) -- Jatinga
     Lampur is also independently surveyed elsewhere (Sl_No 594, "Jatinga
     Lampur railway slide", at 25.11286, 92.87756, describing the same two
     railway stations) -- again off by roughly a degree of longitude.

Rationale for dropping rather than correcting: the project's standing rule
(see CLAUDE.md, GSI Bhukosh/lithology precedent) is to not invent or guess
values GSI itself didn't provide. A plausible corrected coordinate exists for
481 and 561 (their same-named counterpart elsewhere in the dataset), but
substituting it would mean asserting these are the same physical slide
without GSI having said so -- so all 5 flagged rows are dropped rather than
silently "fixed" to a guessed location.

Net effect: 635 raw rows -> 630 kept for training.
"""
import pandas as pd

from scripts.ml.ml_config import STATE_CONFIGS

DROP_SL_NO = {28, 190, 449, 481, 561}


def run_investigation(csv_path=None) -> pd.DataFrame:
    csv_path = csv_path or STATE_CONFIGS["assam"].paths.gsi_assam_csv
    df = pd.read_csv(csv_path)
    flagged = df[df["Sl_No"].isin(DROP_SL_NO)]
    cols = ["Sl_No", "Slide_No", "District", "Slide_Name", "NH_SH_Location", "Latitude", "Longitude"]
    print(f"=== {len(flagged)} flagged rows ===\n")
    print(flagged[cols].to_string())
    return flagged


def clean_positives(df: pd.DataFrame) -> pd.DataFrame:
    """df must have the raw GSI Assam schema (Sl_No, Latitude, Longitude, ...).
    Drops the 5 rows identified above and prints exactly what was dropped."""
    drop_mask = df["Sl_No"].isin(DROP_SL_NO)
    for _, row in df[drop_mask].iterrows():
        print(f"DROPPING Sl_No={row['Sl_No']} Slide_No={row['Slide_No']!r} "
              f"({row['Latitude']}, {row['Longitude']}) -- geolocation inconsistent with its District")
    return df[~drop_mask].reset_index(drop=True)


if __name__ == "__main__":
    run_investigation()
