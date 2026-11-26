"""exit_code_for decides whether the GitHub Actions run shows green or red.
A run must not show green unless the backend actually recorded a refresh --
see the real 2026-09-26 incident this guards against: the run finished, took
its full ~4.5 minutes, hit no error, and still silently stored nothing."""
import importlib.util
import io
import sys
import urllib.error
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "refresh_rainfall_from_runner", Path(__file__).resolve().parent.parent / "scripts" / "refresh_rainfall_from_runner.py"
)
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def result(zones_refreshed, **over):
    base = {"zones_selected": 227, "zones_refreshed": zones_refreshed, "zones_failed": 0}
    base.update(over)
    return base


def test_a_real_refresh_with_no_chunk_failures_is_green():
    assert runner.exit_code_for(result(227), failures=[]) == 0


def test_a_partial_chunk_failure_still_shows_red_even_if_something_was_refreshed():
    assert runner.exit_code_for(result(200), failures=["timeout on chunk 3"]) == 1


def test_zero_refreshed_is_red_even_with_no_reported_failures():
    """The exact incident: Open-Meteo fetches all succeeded (failures=[]), the backend
    call itself didn't error, but zones_refreshed came back 0 -- nothing was stored."""
    assert runner.exit_code_for(result(0), failures=[]) == 1


def test_a_missing_zones_refreshed_key_is_treated_as_zero_not_trusted():
    assert runner.exit_code_for({"zones_selected": 227}, failures=[]) == 1


# --- Open-Meteo's hourly limit (the real 2026-11-15 failures: 5 chunks x ~90 s of useless retries) ---


def http_429(reason):
    body = io.BytesIO(('{"error":true,"reason":"%s"}' % reason).encode())
    return urllib.error.HTTPError("https://api.open-meteo.com/v1/forecast", 429, "Too Many Requests", {}, body)


def test_an_hourly_limit_is_not_retried_or_slept_on(monkeypatch):
    attempts, sleeps = [], []
    monkeypatch.setattr(runner.time, "sleep", sleeps.append)

    def refuse(req, timeout):
        attempts.append(1)
        raise http_429("Hourly API request limit exceeded. Please try again in the next hour.")

    monkeypatch.setattr(runner.urllib.request, "urlopen", refuse)
    with pytest.raises(runner.RateLimited):
        runner.call("https://api.open-meteo.com/v1/forecast?x=1")
    assert len(attempts) == 1 and sleeps == []


def test_a_per_minute_limit_is_still_retried(monkeypatch):
    attempts = []
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)

    class Ok:
        def __enter__(self):
            return io.BytesIO(b'{"ok": true}')

        def __exit__(self, *a):
            return False

    def flaky(req, timeout):
        attempts.append(1)
        if len(attempts) == 1:
            raise http_429("Minutely API request limit exceeded. Please try again in one minute.")
        return Ok()

    monkeypatch.setattr(runner.urllib.request, "urlopen", flaky)
    assert runner.call("https://api.open-meteo.com/v1/forecast?x=1") == {"ok": True}
    assert len(attempts) == 2


def test_the_starting_point_moves_each_hour_and_no_zone_is_lost_or_duplicated():
    targets = [{"id": i} for i in range(800)]
    first, second = runner.rotate_for_fairness(targets, 100), runner.rotate_for_fairness(targets, 101)
    assert first[0] != second[0]
    assert sorted(t["id"] for t in first) == list(range(800))
    assert runner.rotate_for_fairness([], 5) == []


def test_a_run_stops_at_the_limit_but_still_sends_what_it_already_fetched(monkeypatch, capsys):
    # distinct points (0.1 degree apart) so de-duplication doesn't merge them
    targets = [{"id": f"z{i}", "lat": 27.0 + i * 0.1, "lng": 88.0} for i in range(runner.CHUNK_SIZE * 4)]
    posted = {}
    fetch_calls = []

    def fake_call(url, **kw):
        if "/rainfall/status" in url:
            return {"age_minutes": None}
        if "/rainfall/targets" in url:
            return targets
        if "/rainfall/ingest" in url:
            posted.update(kw["data"])
            return {"zones_refreshed": len(kw["data"]["readings"])}
        fetch_calls.append(url)
        if len(fetch_calls) == 3:  # the third chunk hits the hourly limit
            raise runner.RateLimited("HTTP 429 from api.open-meteo.com: Hourly API request limit exceeded.")
        n = url.split("latitude=")[1].split("&")[0].count("%2C") + 1  # one latitude per zone in the chunk
        return [{"daily": {"time": ["2026-11-15"], "precipitation_sum": [1.0]}}] * n

    monkeypatch.setattr(runner, "call", fake_call)
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.setenv("BACKEND_URL", "https://backend.example")
    monkeypatch.setenv("OFFICER_KEY", "test-key")
    monkeypatch.setattr(sys, "argv", ["runner"])
    code = runner.main()
    assert len(fetch_calls) == 3  # the 4th chunk was never attempted
    assert len(posted["readings"]) == runner.CHUNK_SIZE * 2  # the two good chunks were still sent
    assert code == 0  # cut short only by the quota, data stored: green with a warning
    assert "::warning::Open-Meteo's limit is used up" in capsys.readouterr().err


def test_a_rate_limit_alone_is_green_but_any_other_failure_is_red():
    limited = runner.RATE_LIMITED_PREFIX + "HTTP 429 ... Daily API request limit exceeded"
    assert runner.exit_code_for(result(600), failures=[limited]) == 0
    assert runner.exit_code_for(result(600), failures=[limited, "chunk 3 timed out"]) == 1
    assert runner.exit_code_for(result(0), failures=[limited]) == 1  # nothing stored is always red


def test_zones_in_the_same_1km_cell_share_one_point_and_all_get_readings(monkeypatch):
    targets = [
        {"id": "a", "lat": 27.3301, "lng": 88.6101},
        {"id": "b", "lat": 27.3302, "lng": 88.6102},  # same ~1 km cell as a
        {"id": "c", "lat": 27.5, "lng": 88.9},
    ]
    points = runner.dedupe_points(targets)
    assert [p["zone_ids"] for p in points] == [["a", "b"], ["c"]]

    urls = []

    def fake_call(url, **kw):
        urls.append(url)
        return [{"daily": {"time": ["2026-11-26"], "precipitation_sum": [4.0]}}] * 2

    monkeypatch.setattr(runner, "call", fake_call)
    readings = runner.fetch_chunk(points, past_days=runner.SHORT_PAST_DAYS)
    assert sorted(r["zone_id"] for r in readings) == ["a", "b", "c"]
    assert all(r["days"] == [{"day": "2026-11-26", "mm": 4.0}] for r in readings)
    assert "past_days=2" in urls[0]


def _run_main(monkeypatch, argv, age_minutes=None, utc_hour=9):
    urls = []

    def fake_call(url, **kw):
        if "/rainfall/status" in url:
            return {"age_minutes": age_minutes}
        if "/rainfall/targets" in url:
            return [{"id": "z1", "lat": 27.3, "lng": 88.6}]
        if "/rainfall/ingest" in url:
            return {"zones_refreshed": 1}
        urls.append(url)
        return {"daily": {"time": ["2026-11-26"], "precipitation_sum": [1.0]}}

    monkeypatch.setattr(runner, "call", fake_call)
    monkeypatch.setattr(runner.time, "sleep", lambda s: None)
    monkeypatch.setenv("BACKEND_URL", "https://backend.example")
    monkeypatch.setenv("OFFICER_KEY", "test-key")
    monkeypatch.setattr(runner.time, "gmtime", lambda *a: type("T", (), {"tm_hour": utc_hour})())
    monkeypatch.setattr(sys, "argv", ["runner", *argv])
    assert runner.main() == 0
    return urls[0] if urls else None


def test_most_runs_fetch_the_short_window(monkeypatch):
    assert f"past_days={runner.SHORT_PAST_DAYS}&" in _run_main(monkeypatch, [])


def test_the_first_fetch_of_the_utc_day_and_the_full_flag_fetch_the_whole_window(monkeypatch):
    assert f"past_days={runner.FULL_PAST_DAYS}&" in _run_main(monkeypatch, [], utc_hour=1)
    assert f"past_days={runner.FULL_PAST_DAYS}&" in _run_main(monkeypatch, ["--full"])


def test_fresh_data_means_no_open_meteo_calls_and_a_green_run(monkeypatch):
    assert _run_main(monkeypatch, [], age_minutes=runner.MIN_AGE_MINUTES - 1) is None


def test_old_enough_data_or_force_fetches(monkeypatch):
    assert _run_main(monkeypatch, [], age_minutes=runner.MIN_AGE_MINUTES) is not None
    assert _run_main(monkeypatch, ["--force"], age_minutes=5) is not None
