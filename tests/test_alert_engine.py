"""Unit tests for the pure decision core in app.services.alert_engine.
No DB needed — intensity_duration_threshold() and evaluate_daily_rainfall()
take an explicit config, independent of whatever's in .env. check_and_trigger()
(the DB-touching wrapper) still needs a live Postgres to integration-test."""
from datetime import date

import pytest

from app.config import RainfallThresholdConfig
from app.services.alert_engine import evaluate_daily_rainfall, intensity_duration_threshold

# Deterministic test config: threshold(D) = 40 * D^-1 = 40/D mm/day.
# D=1 -> 40, D=3 -> 13.33, D=5 -> 8, D=7 -> 5.71 mm/day (moderate tier).
TEST_CONFIG = RainfallThresholdConfig(
    region="test-fixture",
    coefficient=40.0,
    exponent=-1.0,
    source="synthetic, for unit tests only",
)


def d(day: int) -> date:
    return date(2026, 8, day)


# --- susceptibility scaling ---------------------------------------------


def test_threshold_scales_with_susceptibility_tier():
    high = intensity_duration_threshold(1, risk_tier="high", config=TEST_CONFIG)
    moderate = intensity_duration_threshold(1, risk_tier="moderate", config=TEST_CONFIG)
    low = intensity_duration_threshold(1, risk_tier="low", config=TEST_CONFIG)

    assert high == pytest.approx(32.0)  # 40 * 0.8
    assert moderate == pytest.approx(40.0)  # 40 * 1.0
    assert low == pytest.approx(50.0)  # 40 * 1.25
    assert high < moderate < low


def test_same_rainfall_breaches_high_and_moderate_but_not_low():
    """45mm in a day: crosses the high and moderate bar, not the low one —
    this is the whole point of combining the two risk layers."""
    daily = {d(1): 45.0}

    high = evaluate_daily_rainfall(daily, risk_tier="high", durations_days=[1], config=TEST_CONFIG)
    moderate = evaluate_daily_rainfall(daily, risk_tier="moderate", durations_days=[1], config=TEST_CONFIG)
    low = evaluate_daily_rainfall(daily, risk_tier="low", durations_days=[1], config=TEST_CONFIG)

    assert high is not None and high.duration_days == 1
    assert moderate is not None and moderate.duration_days == 1
    assert low is None


# --- breach / no-breach across durations --------------------------------


def test_no_breach_when_rainfall_is_low():
    daily = {d(i): 2.0 for i in range(1, 8)}  # 2mm/day for 7 days, well under every threshold
    result = evaluate_daily_rainfall(daily, risk_tier="high", config=TEST_CONFIG)
    assert result is None


def test_breach_detected_at_sustained_longer_duration():
    """6mm/day sustained for 7 days doesn't cross the 1/3/5-day bars but
    does cross the 7-day one (6.0 >= 5.71) — the case a same-day cutoff
    would miss entirely."""
    daily = {d(i): 6.0 for i in range(1, 8)}
    result = evaluate_daily_rainfall(daily, risk_tier="moderate", durations_days=[1, 3, 5, 7], config=TEST_CONFIG)

    assert result is not None
    assert result.duration_days == 7
    assert result.observed_mean_intensity_mm_per_day == pytest.approx(6.0)


def test_empty_rainfall_returns_no_crossing():
    assert evaluate_daily_rainfall({}, config=TEST_CONFIG) is None


def test_incomplete_window_is_skipped_not_falsely_triggered():
    """Only 2 days of data but duration 5 is requested — too little data to
    judge that window, so it's skipped rather than treated as a breach."""
    daily = {d(1): 100.0, d(2): 100.0}
    result = evaluate_daily_rainfall(daily, durations_days=[5], config=TEST_CONFIG)
    assert result is None


# --- invalid rainfall input ----------------------------------------------


def test_negative_rainfall_raises():
    with pytest.raises(ValueError):
        evaluate_daily_rainfall({d(1): -5.0}, config=TEST_CONFIG)


def test_nan_rainfall_raises():
    with pytest.raises(ValueError):
        evaluate_daily_rainfall({d(1): float("nan")}, config=TEST_CONFIG)


def test_none_rainfall_raises():
    with pytest.raises(ValueError):
        evaluate_daily_rainfall({d(1): None}, config=TEST_CONFIG)


def test_infinite_rainfall_raises():
    with pytest.raises(ValueError):
        evaluate_daily_rainfall({d(1): float("inf")}, config=TEST_CONFIG)


# --- invalid threshold parameters -----------------------------------------


def test_zero_or_negative_duration_raises():
    with pytest.raises(ValueError):
        intensity_duration_threshold(0, config=TEST_CONFIG)
    with pytest.raises(ValueError):
        intensity_duration_threshold(-3, config=TEST_CONFIG)


def test_unknown_risk_tier_raises():
    with pytest.raises(ValueError):
        intensity_duration_threshold(1, risk_tier="extreme", config=TEST_CONFIG)
