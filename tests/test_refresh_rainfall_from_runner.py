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
    targets = [{"id": f"z{i}", "lat": 27.0, "lng": 88.0} for i in range(runner.CHUNK_SIZE * 4)]
    posted = {}
    fetch_calls = []

    def fake_call(url, **kw):
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
    assert code == 1  # a partial run still shows red
    assert "limit is used up" in capsys.readouterr().err
