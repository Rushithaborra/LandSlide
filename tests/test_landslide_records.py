"""GSI landslide records: the cleaning rules (real data, so they only tidy, never
invent), the API around them, and the cleaned-up highway corridors."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.database import get_db
from app.main import app
from app.routers import corridors
from app.services.landslide_records import clean_activity, clean_all, clean_district, clean_record, clean_text


def row(**over):
    base = {"Slide_No": "AS/DIM/1", "State": "Assam", "District": "Dima Hasao", "Slide_Name": "Digar nala", "NH_SH_Location": "NH 54",
            "Latitude": "25.41", "Longitude": "93.28", "Material_Involved": "", "Movement_Type": "", "History_Date": "", "Activity": "Active"}
    base.update(over)
    return base


# --- cleaning --------------------------------------------------------------------


def test_text_is_trimmed_single_spaced_and_empty_becomes_none():
    assert clean_text("  Raja   Bazaar\n road ") == "Raja Bazaar road"
    assert clean_text("   ") is None and clean_text(None) is None and clean_text("") is None


def test_garbled_dashes_from_the_assam_file_are_repaired():
    assert clean_text("Raja Bazaar ΓÇôBara Arkap road.") == "Raja Bazaar –Bara Arkap road."


def test_free_text_is_capped_not_dropped():
    assert len(clean_text("x" * 900, limit=500)) == 500


@pytest.mark.parametrize("raw,expected", [(" East Sikkim", "East Sikkim"), ("Gyalshing District, Sikkim", "Gyalshing"), ("Dima Hasao", "Dima Hasao"), ("  ", None), (None, None)])
def test_district_names_are_tidied_but_otherwise_kept(raw, expected):
    assert clean_district(raw, "Sikkim") == expected


@pytest.mark.parametrize("raw,expected", [("active", "Active"), ("  Dormant ", "Dormant"), ("", "Unknown"), (" ", "Unknown"), (None, "Unknown"), ("Active and suspended", "Active and suspended")])
def test_activity_is_capitalised_and_blank_is_unknown_not_guessed(raw, expected):
    assert clean_activity(raw) == expected


def test_a_record_keeps_only_what_the_inventory_says():
    r = clean_record(row(Material_Involved="Debris", History_Date=""), "Assam")
    assert r["material"] == "Debris" and r["movement"] is None and r["history_note"] is None
    assert (r["lat"], r["lng"]) == (25.41, 93.28) and r["state"] == "Assam"
    assert "date" not in r and "severity" not in r  # the inventories have neither, so none is shown


@pytest.mark.parametrize("bad", [{"Latitude": ""}, {"Longitude": "abc"}, {"Latitude": "51.0"}, {"Longitude": "10.0"}])
def test_rows_without_usable_coordinates_are_dropped(bad):
    assert clean_record(row(**bad), "Assam") is None


def test_exact_duplicates_are_dropped_but_a_shared_slide_number_is_not_a_duplicate():
    rows = [row(), row(), row(Slide_Name="Other slide", Latitude="25.5"), row(Slide_No="", Slide_Name="No number", Latitude="25.6")]
    records, dropped = clean_all(rows, "Assam")
    assert len(records) == 3 and dropped == {"no_coordinates": 0, "duplicate": 1}
    assert [r["slide_no"] for r in records].count("AS/DIM/1") == 2  # same GSI number, different places: both kept


# --- the API -----------------------------------------------------------------------


@pytest.fixture
def client():
    db = MagicMock()
    app.dependency_overrides[get_db] = lambda: db
    yield TestClient(app), db
    app.dependency_overrides.pop(get_db, None)


def sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True}))


def record_obj(**over):
    base = dict(id=uuid.uuid4(), slide_no="1", state="Assam", district="Cachar", slide_name="S", location="L", lat=24.9, lng=93.1,
                activity="Active", material=None, movement=None, history_note=None, source="GSI")
    base.update(over)
    return SimpleNamespace(**base)


def test_the_list_returns_the_total_and_the_page(client):
    c, db = client
    db.scalar.return_value = 587
    db.execute.return_value.scalars.return_value.all.return_value = [record_obj(), record_obj(slide_name="T")]
    body = c.get("/landslide-records", params={"state": "Assam", "limit": 2}).json()
    assert body["total"] == 587 and [i["slide_name"] for i in body["items"]] == ["S", "T"]


def test_filters_combine_and_a_search_term_is_matched_literally(client):
    c, db = client
    db.scalar.return_value = 0
    db.execute.return_value.scalars.return_value.all.return_value = []
    c.get("/landslide-records", params={"state": "Assam", "district": "Cachar", "activity": "Active", "q": "100%_x"})
    query = sql(db.execute.call_args.args[0])
    assert "state = 'Assam'" in query and "district = 'Cachar'" in query and "activity = 'Active'" in query
    assert "100\\%\\_x" in query  # % and _ typed by the user are escaped, not wildcards


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 500}, {"offset": -1}, {"q": "x" * 101}])
def test_paging_and_search_limits_are_enforced(client, params):
    c, _ = client
    assert c.get("/landslide-records", params=params).status_code == 422


def test_the_summary_reports_what_is_loaded(client):
    c, db = client
    db.scalar.return_value = 0  # a state whose records are not loaded
    db.execute.return_value.all.return_value = []
    body = c.get("/landslide-records/summary", params={"state": "Manipur"}).json()
    assert body == {"total": 0, "districts": [], "activities": []}


# --- corridors: cleaned up ------------------------------------------------------------


def test_two_refs_for_one_road_read_as_one_label():
    assert corridors.display_code("SH37;SH022") == "SH37 / SH022"
    assert corridors.display_code("NH27") == "NH27"


def test_each_corridor_says_what_kind_it_is(client):
    c, db = client
    rows = [
        SimpleNamespace(code="NH27", kind="highway", zone_count=2760, active_alert_count=0, risk_tier="high", name="NH27 (1_00_001)", susceptibility_score=0.9),
        SimpleNamespace(code="Ambari Makri Road", kind="named", zone_count=17, active_alert_count=0, risk_tier="high", name="Ambari Makri Road (2_00_001)", susceptibility_score=0.8),
        SimpleNamespace(code="road", kind="unnamed", zone_count=27718, active_alert_count=0, risk_tier="high", name="road (3_00_001)", susceptibility_score=0.7),
    ]
    db.execute.return_value.all.return_value = rows
    body = c.get("/corridors", params={"state": "Assam"}).json()
    assert [(x["code"], x["kind"]) for x in body] == [("NH27", "highway"), ("Ambari Makri Road", "named"), ("road", "unnamed")]
