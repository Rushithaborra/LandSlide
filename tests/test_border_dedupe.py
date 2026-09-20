"""The loader must not re-create a border stretch a neighbouring state already
owns (scripts/integrate_zone_predictions.py). Pure function, no database."""
from scripts.integrate_zone_predictions import BORDER_TOLERANCE_DEG, is_border_duplicate

OTHER = {"NH2 (111_00_004)": [(25.5000, 94.0000)], "NH29 (222_00_001)": [(25.9, 93.9), (26.5, 94.5)]}


def test_same_name_at_the_same_spot_in_another_state_is_a_duplicate():
    assert is_border_duplicate("NH2 (111_00_004)", 25.5000, 94.0000, OTHER)


def test_it_tolerates_a_few_metres_of_difference():
    assert is_border_duplicate("NH2 (111_00_004)", 25.5000 + BORDER_TOLERANCE_DEG / 2, 94.0000 - BORDER_TOLERANCE_DEG / 2, OTHER)


def test_the_same_name_somewhere_else_is_a_different_stretch_not_a_duplicate():
    # Roads crossing a border share a name across states (105 Assam/Meghalaya
    # names do) but are different places -- both must be kept.
    assert not is_border_duplicate("NH2 (111_00_004)", 25.9, 94.0, OTHER)


def test_a_different_name_is_never_a_duplicate():
    assert not is_border_duplicate("NH2 (999_00_001)", 25.5000, 94.0000, OTHER)


def test_any_of_several_other_copies_can_match():
    assert is_border_duplicate("NH29 (222_00_001)", 26.5, 94.5, OTHER)


def test_no_other_zones_means_no_duplicate():
    assert not is_border_duplicate("NH2 (111_00_004)", 25.5, 94.0, {})
