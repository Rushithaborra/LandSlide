"""exit_code_for decides whether the GitHub Actions run shows green or red.
A run must not show green unless the backend actually recorded a refresh --
see the real 2026-09-26 incident this guards against: the run finished, took
its full ~4.5 minutes, hit no error, and still silently stored nothing."""
import importlib.util
from pathlib import Path

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
