"""build_rows joins IMD's district list (state) to its warnings (codes) on IMD's own district id."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("push_imd_warnings", Path(__file__).resolve().parent.parent / "scripts" / "push_imd_warnings.py")
push = importlib.util.module_from_spec(spec)
spec.loader.exec_module(push)


def warning(obj_id, name, codes=("1", "1", "1", "1", "1"), colors=("4", "4", "4", "4", "4"), day="2026-09-21"):
    w = {"Obj_id": obj_id, "District": name, "Date": day}
    for i in range(5):
        w[f"Day_{i + 1}"], w[f"Day{i + 1}_Color"] = codes[i], colors[i]
    return w


DISTRICTS = [
    {"Obj_id": "10", "District": "KAMRUP METRO", "State": "ASSAM"},        # named differently in the warnings feed
    {"Obj_id": "313", "District": "AIZAWL", "State": "MIZORAM"},          # missing from the warnings feed
    {"Obj_id": "99", "District": "PATNA", "State": "BIHAR"},              # not a north-east state
]


def test_districts_are_joined_on_id_not_name_and_days_get_dates():
    rows, missing = push.build_rows([warning("10", "KAMRUP", codes=("4", "4,2", "2", "1", "1"), colors=("3", "3", "3", "4", "4")), warning("99", "PATNA")], DISTRICTS)
    assert missing == {"Mizoram": 1}
    assert {r["state"] for r in rows} == {"Assam"} and len(rows) == 5
    day2 = next(r for r in rows if r["day"] == 2)
    assert day2 == {"state": "Assam", "district": "Kamrup", "obj_id": "10", "day": 2, "valid_date": "2026-09-22", "codes": [4, 2], "color": 3}


def test_a_day_with_unusable_values_is_left_out_not_guessed():
    rows, _ = push.build_rows([warning("10", "KAMRUP", codes=("2", "", "n/a", "1", "1"), colors=("3", "3", "3", "x", "4"))], DISTRICTS)
    assert sorted(r["day"] for r in rows) == [1, 5]  # day 2 empty, day 3 not numeric, day 4 has a bad colour
