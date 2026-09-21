"""Cleaning for the Geological Survey of India landslide inventories (one CSV per
state, from the NER data pipeline) before they are stored as `landslide_records`.

These are real historical records, so the rules only tidy presentation -- stray
whitespace, garbled dash characters, inconsistent capitalisation, a state name stuck
onto a district -- and drop what cannot be shown (no usable coordinates, or an exact
duplicate). Nothing is invented: a field that is empty stays empty, and an empty
activity is shown as "Unknown", not guessed."""
import re

# Bounding box around all eight north-east states; a record outside it is a data error.
LAT_RANGE = (21.0, 30.5)
LNG_RANGE = (87.5, 98.0)

# Mojibake seen in the Assam file: a UTF-8 en dash / apostrophe decoded as cp437.
_MOJIBAKE = {"ΓÇô": "–", "ΓÇö": "—", "ΓÇÖ": "’", "ΓÇ£": "“", "ΓÇ¥": "”", "â€“": "–", "â€™": "’"}


def clean_text(value: str | None, limit: int | None = None) -> str | None:
    """Trimmed, single-spaced text (newlines included), garbled dashes fixed; None if empty."""
    if value is None:
        return None
    for bad, good in _MOJIBAKE.items():
        value = value.replace(bad, good)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return None
    return value[:limit] if limit else value


def clean_district(value: str | None, state: str) -> str | None:
    """'Gyalshing District, Sikkim' -> 'Gyalshing'; ' East Sikkim' -> 'East Sikkim'. The
    inventory's own district names are otherwise kept as they are."""
    district = clean_text(value)
    if district is None:
        return None
    district = re.sub(rf",\s*{re.escape(state)}\s*$", "", district, flags=re.I)
    district = re.sub(r"\s+District\s*$", "", district, flags=re.I)
    return district.strip() or None


def clean_activity(value: str | None) -> str:
    """The recorded activity, capitalised ('active' -> 'Active'); 'Unknown' when blank."""
    activity = clean_text(value)
    if activity is None:
        return "Unknown"
    return activity[0].upper() + activity[1:]


def clean_record(row: dict, state: str) -> dict | None:
    """One inventory CSV row -> a record dict, or None if it has no usable coordinates."""
    try:
        lat, lng = float(row["Latitude"]), float(row["Longitude"])
    except (KeyError, TypeError, ValueError):
        return None
    if not (LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LNG_RANGE[0] <= lng <= LNG_RANGE[1]):
        return None
    return {
        "slide_no": clean_text(row.get("Slide_No")),
        "state": state,
        "district": clean_district(row.get("District"), state),
        "slide_name": clean_text(row.get("Slide_Name")),
        "location": clean_text(row.get("NH_SH_Location")),
        "lat": lat,
        "lng": lng,
        "activity": clean_activity(row.get("Activity")),
        "material": clean_text(row.get("Material_Involved")),
        "movement": clean_text(row.get("Movement_Type")),
        "history_note": clean_text(row.get("History_Date"), limit=500),
    }


def clean_all(rows: list[dict], state: str) -> tuple[list[dict], dict]:
    """Clean every row; drop rows without usable coordinates and exact duplicates
    (same name at the same place). Returns (records, counts of what was dropped)."""
    records, seen = [], set()
    dropped = {"no_coordinates": 0, "duplicate": 0}
    for row in rows:
        record = clean_record(row, state)
        if record is None:
            dropped["no_coordinates"] += 1
            continue
        key = (record["slide_name"], round(record["lat"], 5), round(record["lng"], 5))
        if key in seen:
            dropped["duplicate"] += 1
            continue
        seen.add(key)
        records.append(record)
    return records, dropped
