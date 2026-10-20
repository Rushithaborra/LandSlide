# IMD station rainfall logger

Logs IMD's real rain-gauge readings for the north-east next to Open-Meteo's estimate at the
same coordinates, so "how far off is Open-Meteo here" can be answered with real gauges.
Local research artifact only: nothing here touches the production database or dashboard.

- Script: `scripts/imd_station_logger.py` (one run = one poll; one IMD call plus a few Open-Meteo calls)
- Output: `data/interim/imd_station_log.db` (SQLite, gitignored), table `polls`, one row per station per run
- Scheduler: Windows Task Scheduler task **IMD Station Rainfall Logger**, every 6 hours, running
  `scripts/run_imd_station_logger.ps1` (it sets the working directory so `.env` is found, appends each
  run to `data/interim/imd_station_logger.log`, and passes the logger's exit code on). "Run task as soon
  as possible after a scheduled start is missed" is on, so a run missed while the laptop was off happens at the next wake.
- Needs `IMD_API_KEY`, `IMD_EMAIL`, `IMD_PASSWORD` in `.env`. IMD's key only works from the one public IP
  it was registered for, so this can only run from that machine (not GitHub Actions or Render).

## How to tell whether it is working

Task Scheduler "Last Run Result" is `0x0` only when the poll really succeeded; any failure is `0x1`.
(Before 2026-10-20 the wrapper always reported success, and the logger recorded nothing from 26 Sep to 20 Oct
without anything looking wrong.) The authoritative check is the data:

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; print(sqlite3.connect('data/interim/imd_station_log.db').execute('select count(*), max(polled_at_utc) from polls').fetchone())"
```

The newest `polled_at_utc` should be within about 6 hours (longer only if the laptop was off). The log
(`data/interim/imd_station_logger.log`) shows each run and, on failure, a `=== FAILED (exit code N) ===` line.

## HTTP 403 from IMD = the public IP changed

This has happened repeatedly (home ISP addresses rotate). To fix it:

1. Find this machine's current public IP (IMD's own check: `https://api.imd.gov.in/public/ip.php`).
2. In the IMD API portal, create or update a DEV key for that IP (the portal allows two DEV keys, so delete a dead one first).
3. Put the new key in `.env` as `IMD_API_KEY` (never paste it into chat, a commit or a screenshot).
4. Run `.\.venv\Scripts\python.exe scripts\imd_station_logger.py` once; it should print a station count, not an error.

The same key serves `scripts/push_imd_warnings.py`, so the dashboard's IMD warnings snapshot cannot be refreshed
either while it is rejected. A fixed public IP for this machine (or running both from a host that has one) would end this.
