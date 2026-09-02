"""
Standalone retry for the buildings query from scripts/07 -- it got
rate-limited (429) after several other Overpass queries ran back-to-back.
Waits out the rate-limit window before trying, with longer backoff between
attempts than the original script used.
"""
import time
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "extras", Path(__file__).resolve().parent / "07_fetch_dashboard_extras.py"
)
extras = importlib.util.module_from_spec(spec)
spec.loader.exec_module(extras)

if __name__ == "__main__":
    print("Waiting 60s to clear any Overpass rate-limit window...")
    time.sleep(60)
    extras.fetch_buildings()
