"""Rainfall threshold configuration: units must be days and mm/day, and Assam's
Guwahati equation must be the paper's hourly fit converted correctly.

Source: Bhusan et al. (2014), ISPRS Archives XL-8, doi:10.5194/isprsarchives-XL-8-15-2014.
Figure 7 plots mean rainfall intensity in mm/h against duration in hours; the fit is
I = 5.9 * D^-0.479. The engine works in mm/day and days, so the configured
coefficient is 5.9 * 24^0.521 = 30.9. Configuring the raw 5.9 made Assam's thresholds
5.2x too low (a normal monsoon day counted as dangerous)."""
import pytest
from pydantic import ValidationError

from app.config import RainfallThresholdConfig
from app.services.alert_engine import intensity_duration_threshold

PAPER_COEFFICIENT_PER_HOUR = 5.9
EXPONENT = -0.479
ASSAM = RainfallThresholdConfig(
    region="Assam (Guwahati)", coefficient=30.9, exponent=EXPONENT,
    source="Bhusan et al. (2014), converted from mm/h and hours", verified_against_primary_text=True,
)


def paper_threshold_mm_per_day(duration_days: float) -> float:
    """The paper's hourly equation, evaluated directly and expressed as the mean
    mm/day over a window of `duration_days` days."""
    duration_hours = 24 * duration_days
    return 24 * PAPER_COEFFICIENT_PER_HOUR * duration_hours**EXPONENT


@pytest.mark.parametrize("days", [1, 3, 5, 7, 10, 15, 20])
def test_the_configured_threshold_equals_the_papers_hourly_equation_converted(days):
    assert intensity_duration_threshold(days, ASSAM, "moderate") == pytest.approx(paper_threshold_mm_per_day(days), rel=5e-3)


def test_the_one_day_threshold_is_about_31_mm_not_6():
    assert intensity_duration_threshold(1, ASSAM, "moderate") == pytest.approx(30.9, abs=0.05)


def test_the_conversion_factor_is_24_to_the_power_of_one_minus_the_exponent():
    assert PAPER_COEFFICIENT_PER_HOUR * 24 ** (1 + EXPONENT) == pytest.approx(30.9, abs=0.05)


def test_the_raw_hourly_coefficient_would_be_5_point_2_times_too_sensitive():
    raw = RainfallThresholdConfig(region="wrong", coefficient=5.9, exponent=EXPONENT, source="unconverted")
    assert intensity_duration_threshold(1, ASSAM, "moderate") / intensity_duration_threshold(1, raw, "moderate") == pytest.approx(5.24, abs=0.02)


@pytest.mark.parametrize("field,value", [("intensity_unit", "mm/h"), ("duration_unit", "hours"), ("intensity_unit", "mm/hour")])
def test_a_threshold_declared_in_other_units_is_rejected_at_startup(field, value):
    with pytest.raises(ValidationError, match="convert the coefficient first"):
        RainfallThresholdConfig(region="x", coefficient=5.9, exponent=EXPONENT, source="paper", **{field: value})


def test_days_and_mm_per_day_are_accepted():
    RainfallThresholdConfig(region="x", coefficient=30.9, exponent=EXPONENT, source="paper", duration_unit="days", intensity_unit="mm/day")
