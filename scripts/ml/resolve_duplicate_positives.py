"""Investigates and resolves the 3 duplicate-coordinate pairs found in the
777-record GSI Sikkim positive inventory during dataset review.

Findings (full row comparison run 2026-09-02, see run_investigation() output):

1. (27.393056, 88.635278) -- "Kabi Landslide". Same Slide_Name, same
   NH_SH_Location ("State Highway; 4 km before Kabi village"), same
   Material/Movement. History fields are: row A = "Mid-July 2018, 2 August
   2018"; row B = "Mid-July 2018, 2 August 2018, 24 May 2020" -- row B's
   history is a strict superset of row A's. This is GSI re-logging the SAME
   recurring failure site after a 2020 recurrence, filed as a separate
   survey record -- not two independent events. CLEAR duplicate.
   Keep the more complete record, drop the other.

2. (27.426361, 88.583028). Same year (2015), sequential serial numbers
   (.../74 and .../75), identical District/NH_SH_Location/Material/
   Movement, no Slide_Name or History on either row to differentiate them,
   coordinates identical to 6 decimal places. AMBIGUOUS -- could be a
   duplicate data-entry, or two closely-spaced distinct debris slides
   logged against the same rounded field GPS waypoint (common limitation
   of road-corridor survey data). No evidence in the record distinguishes
   them. Treated as a duplicate for training purposes (see rationale
   below) -- flagged as the least-certain of the three.

3. (27.437889, 88.601694) -- "Chawang". Same year (2015), sequential
   serial numbers (.../07 and .../08), identical District/NH_SH_Location/
   Material/Movement. One row has the place name "Chawang", the other
   doesn't. Same ambiguity as #2, same treatment.

Rationale for treating all three as duplicates despite #2/#3's ambiguity:
a supervised model trains on (features, label) pairs at a location. If two
rows share the exact same coordinate, they get IDENTICAL terrain/land-cover
feature values (same DEM pixel, same WorldCover pixel) -- so keeping both
does not add information, it just doubles the weight of that one location
in training. Whether #2/#3 are truly one event or two, deduplicating is the
conservative, defensible choice: it costs nothing (no information lost,
since the duplicate row's features are identical to its pair's) and removes
an unintended sample-weight inflation. This is documented as a judgment
call, not asserted as certain.
"""
import pandas as pd

from scripts.ml.ml_config import DEFAULT_CONFIG, MlConfig

# Resolution rule per duplicate coordinate group: prefer the row with (a)
# a non-null Slide_Name, then (b) the longer/more complete History string,
# then (c) the lower original row index (for reproducibility). Documented,
# not arbitrary "keep first".
def _pick_row_to_keep(group: pd.DataFrame) -> pd.Index:
    def score(row):
        has_name = pd.notna(row["Slide_Name"])
        history_len = len(str(row["History"])) if pd.notna(row["History"]) else 0
        return (has_name, history_len, -row.name)  # -row.name: lower index wins ties

    best_idx = max(group.index, key=lambda i: score(group.loc[i]))
    return best_idx


def run_investigation(config: MlConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    df = pd.read_csv(config.paths.gsi_sikkim_csv)
    dupe_mask = df.duplicated(subset=["Latitude", "Longitude"], keep=False)
    dupes = df[dupe_mask].sort_values(["Latitude", "Longitude"])

    print(f"=== {dupe_mask.sum()} duplicate-coordinate rows found ({dupe_mask.sum() // 2} pairs) ===\n")
    cols = ["Slide_No", "District", "Slide_Name", "NH_SH_Location", "Material_Involved", "Movement_Type", "History"]
    for (lat, lng), group in dupes.groupby(["Latitude", "Longitude"]):
        print(f"--- coordinate ({lat}, {lng}) ---")
        print(group[cols].to_string())
        print()
    return dupes


def deduplicate_positives(df: pd.DataFrame) -> pd.DataFrame:
    """df must have Latitude/Longitude columns (raw GSI schema). Returns df
    with one row per duplicate coordinate group, keeping the most complete
    record per _pick_row_to_keep, and prints exactly what was dropped."""
    dupe_mask = df.duplicated(subset=["Latitude", "Longitude"], keep=False)
    dupes = df[dupe_mask]

    rows_to_drop = []
    for (lat, lng), group in dupes.groupby(["Latitude", "Longitude"]):
        keep_idx = _pick_row_to_keep(group)
        drop_idxs = [i for i in group.index if i != keep_idx]
        rows_to_drop.extend(drop_idxs)
        for i in drop_idxs:
            print(f"DROPPING duplicate: Slide_No={df.loc[i, 'Slide_No']!r} at ({lat}, {lng}) "
                  f"-- kept Slide_No={df.loc[keep_idx, 'Slide_No']!r} instead")

    return df.drop(index=rows_to_drop).reset_index(drop=True)


if __name__ == "__main__":
    run_investigation()
