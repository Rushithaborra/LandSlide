"""Rain-worsened updates: an alert that is already active is updated (and the
zone's subscribers re-texted) when its rain gets clearly worse.

Synthetic config: threshold(D) = 40 / D mm/day, so ANY window's cumulative rain
divided by 40 is the same ratio -- 60 mm in a window is 1.5x the danger level."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.config import RainfallThresholdConfig
from app.services import alert_engine as ae
from tests.test_alert_auto_resolve import CONFIG, TODAY, series

NOW = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)


# --- strongest_ratio / has_worsened (pure) ----------------------------------


def test_ratio_is_one_exactly_at_the_danger_level():
    assert ae.strongest_ratio(series({0: 40.0}), CONFIG) == pytest.approx(1.0)


def test_ratio_scales_with_the_rain():
    assert ae.strongest_ratio(series({0: 60.0}), CONFIG) == pytest.approx(1.5)
    assert ae.strongest_ratio(series({0: 100.0}), CONFIG) == pytest.approx(2.5)


def test_it_takes_the_strongest_window_not_the_shortest_crossing():
    # Here the 4-day window is relatively MORE sensitive than the 1-day one, so the
    # strongest ratio comes from the longer window (evaluate_daily_rainfall would
    # have reported the shortest crossing instead).
    cfg = RainfallThresholdConfig(region="t", coefficient=40.0, exponent=-0.5, source="synthetic", durations_days=[1, 4])
    data = {TODAY - timedelta(days=d): 30.0 for d in range(0, 5)}  # 30 mm every day
    one_day = 30.0 / 40.0
    four_day = 30.0 / (40.0 * 4**-0.5)  # threshold 20 mm/day -> 1.5
    assert ae.strongest_ratio(data, cfg) == pytest.approx(max(one_day, four_day))
    assert four_day > one_day


def test_long_windows_are_left_out_of_the_worsening_measure():
    # 20 mm on each of 12 days: the 10-day window is far over its level (mean 20 vs
    # 40/sqrt(10) = 12.6) but the 1-day window is not (20 vs 40). Only short windows
    # count, so this old, spread-out rain is not seen as "worse".
    cfg = RainfallThresholdConfig(region="t", coefficient=40.0, exponent=-0.5, source="synthetic", durations_days=[1, 10])
    data = {TODAY - timedelta(days=d): 20.0 for d in range(0, 12)}
    assert ae.strongest_ratio(data, cfg) == pytest.approx(20.0 / 40.0)  # 1-day only
    assert ae.strongest_ratio(data, cfg, max_duration_days=20) > 1.5  # the long window would have dominated


def test_no_complete_window_means_no_ratio():
    cfg = RainfallThresholdConfig(region="t", coefficient=40.0, exponent=-1.0, source="s", durations_days=[3, 5])
    assert ae.strongest_ratio({TODAY: 10.0}, cfg) is None
    assert ae.strongest_ratio({}, CONFIG) is None


def test_bad_rainfall_data_is_an_error_not_silent():
    with pytest.raises(ValueError):
        ae.strongest_ratio({TODAY: -1.0}, CONFIG)


@pytest.mark.parametrize("baseline,current,expected", [(1.0, 1.49, False), (1.0, 1.5, True), (1.2, 2.5, True), (2.0, 1.0, False)])
def test_worsened_needs_a_full_step_above_the_baseline(baseline, current, expected):
    assert ae.has_worsened(baseline, current, step=0.5) is expected


# --- escalate_if_worsened ---------------------------------------------------


@pytest.fixture
def sms(monkeypatch):
    calls = []

    def fake(db, zone_id, zone_name, severity, message=None, bypass_cooldown=False):
        calls.append({"zone": zone_name, "severity": severity, "message": message})
        return {"skipped": False, "sent": 2}

    monkeypatch.setattr("app.services.sms_alerts.trigger_zone_alert", fake)
    monkeypatch.setattr(ae.settings, "rainfall_escalation_step", 0.5)
    monkeypatch.setattr(ae.settings, "rainfall_escalation_min_hours", 6)
    return calls


def _alert(peak=1.2, worsened_at=None, count=0, delivery="log_only"):
    return SimpleNamespace(peak_ratio=peak, worsened_at=worsened_at, worsened_count=count, delivery_method=delivery)


ZONE = SimpleNamespace(id="z1", name="NH10 (1_00_001)")


def run(alert, data, now=NOW):
    return ae.escalate_if_worsened(MagicMock(), alert, ZONE, data, CONFIG, "moderate", now=now)


def test_clearly_worse_rain_updates_the_alert_and_texts_people(sms):
    a = _alert(peak=1.2)
    assert run(a, series({0: 100.0})) is True  # 2.5x now
    assert a.peak_ratio == pytest.approx(2.5) and a.worsened_at == NOW and a.worsened_count == 1
    assert len(sms) == 1 and "rain has got worse near NH10" in sms[0]["message"] and sms[0]["severity"] == "moderate"
    assert a.delivery_method == "sms_twilio"


def test_a_small_increase_does_nothing(sms):
    a = _alert(peak=1.2)
    assert run(a, series({0: 56.0})) is False  # 1.4x: only +0.2
    assert a.worsened_at is None and a.peak_ratio == 1.2 and sms == []


def test_an_alert_without_a_baseline_is_only_measured_never_texted(sms):
    a = _alert(peak=None)
    assert run(a, series({0: 200.0})) is False  # even 5x: nothing to compare with yet
    assert a.peak_ratio == pytest.approx(5.0) and a.worsened_count == 0 and sms == []


def test_no_second_update_inside_the_minimum_gap_and_the_baseline_does_not_move(sms):
    a = _alert(peak=2.0, worsened_at=NOW - timedelta(hours=2), count=1)
    assert run(a, series({0: 160.0})) is False  # 4x, but updated 2 hours ago
    assert a.peak_ratio == 2.0 and a.worsened_count == 1 and sms == []
    # once the gap has passed, the same worsening is caught
    assert run(a, series({0: 160.0}), now=NOW + timedelta(hours=5)) is True
    assert a.worsened_count == 2


def test_a_forecast_day_can_never_cause_an_update(sms):
    a = _alert(peak=1.2)
    data = series({0: 30.0})
    data[TODAY + timedelta(days=2)] = 500.0  # a PREDICTED downpour in two days
    assert run(a, data) is False and sms == []


def test_an_sms_failure_still_records_the_update(monkeypatch, sms):
    def boom(*args, **kwargs):
        raise RuntimeError("twilio down")

    monkeypatch.setattr("app.services.sms_alerts.trigger_zone_alert", boom)
    a = _alert(peak=1.2)
    assert run(a, series({0: 100.0})) is True and a.worsened_count == 1


def test_a_skipped_sms_leaves_the_delivery_method_alone(monkeypatch, sms):
    monkeypatch.setattr("app.services.sms_alerts.trigger_zone_alert", lambda *a, **k: {"skipped": True, "reason": "cooldown"})
    a = _alert(peak=1.2)
    assert run(a, series({0: 100.0})) is True and a.delivery_method == "log_only"
