"""The national baseline rule: IMD's 'heavy rain' level (64.5 mm in 24 h) for any state that
has no landslide threshold of its own. Pure functions, no DB."""
from datetime import date, timedelta

import pytest

from app import config
from app.config import IMD_HEAVY_RAIN, RainfallThresholdConfig, get_rainfall_threshold
from app.services.alert_engine import evaluate_daily_rainfall, intensity_duration_threshold

TODAY = date(2026, 9, 21)


def days(*mm):
    """Daily totals ending on TODAY, oldest first."""
    return {TODAY - timedelta(days=len(mm) - 1 - i): v for i, v in enumerate(mm)}


def test_a_state_with_no_threshold_of_its_own_gets_the_imd_baseline_never_another_states(monkeypatch):
    monkeypatch.setattr(config.settings, "rainfall_thresholds", {})
    for state in ("Assam", "Meghalaya", "Mizoram"):
        assert get_rainfall_threshold(state) is IMD_HEAVY_RAIN


def test_a_states_own_configured_threshold_wins_over_the_baseline(monkeypatch):
    own = RainfallThresholdConfig(region="Assam (own)", coefficient=30.9, exponent=-0.479, source="test")
    monkeypatch.setattr(config.settings, "rainfall_thresholds", {"assam": own})
    assert get_rainfall_threshold("Assam") is own
    assert get_rainfall_threshold("Meghalaya") is IMD_HEAVY_RAIN


def test_sikkim_keeps_its_original_setting(monkeypatch):
    sikkim = RainfallThresholdConfig(region="Sikkim", coefficient=43.26, exponent=-0.78, source="test")
    monkeypatch.setattr(config.settings, "rainfall_thresholds", {})
    monkeypatch.setattr(config.settings, "rainfall_threshold", sikkim)
    assert get_rainfall_threshold("Sikkim") is sikkim


def test_the_baseline_is_a_single_24_hour_line_scaled_by_the_susceptibility_tier():
    assert IMD_HEAVY_RAIN.durations_days == [1]
    assert intensity_duration_threshold(1, IMD_HEAVY_RAIN, "moderate") == pytest.approx(64.5)
    assert intensity_duration_threshold(1, IMD_HEAVY_RAIN, "high") == pytest.approx(64.5 * 0.8)
    assert intensity_duration_threshold(1, IMD_HEAVY_RAIN, "low") == pytest.approx(64.5 * 1.25)
    assert "not a landslide-specific threshold" in IMD_HEAVY_RAIN.source  # said on the page, not hidden


def test_an_ordinary_wet_monsoon_does_not_alert_but_a_heavy_day_does():
    wet_month = days(*([12.0] * 20))  # 12 mm every day for 20 days: normal monsoon, the case the Guwahati curve flagged
    assert evaluate_daily_rainfall(wet_month, IMD_HEAVY_RAIN, "high") is None

    heavy_day = days(*([5.0] * 19 + [70.0]))
    crossing = evaluate_daily_rainfall(heavy_day, IMD_HEAVY_RAIN, "high")
    assert crossing is not None and crossing.duration_days == 1
    assert crossing.threshold_mm_per_day == pytest.approx(51.6)


def test_the_guwahati_curve_would_have_flagged_that_ordinary_month():
    """The reason Assam is not switched on with its own equation (see .env.example)."""
    guwahati = RainfallThresholdConfig(region="Assam (Guwahati)", coefficient=30.9, exponent=-0.479, source="Bhusan 2014")
    assert evaluate_daily_rainfall(days(*([12.0] * 20)), guwahati, "high") is not None
