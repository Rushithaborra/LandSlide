# Why the dashboard's rainfall went stale, and how it stays current now

Written 2026-09-20 for the team. Plain language; the technical detail is in
`README.md` ("Scheduled rainfall refresh").

## What people saw
- The Alerts section looked current, but the rainfall section showed data about
  6 days old.
- Sikkim's big rainfall figures were not showing up as new alerts.

## Why it happened (four separate causes)
1. **Nothing was refreshing rainfall.** Rainfall only updates when something asks
   the weather service (Open-Meteo) for it. The hourly/3-hourly GitHub timer we
   set up ran once and did nothing: the `OFFICER_API_KEY` secret was not visible to
   the repo, so it skipped, and the green tick hid that.
2. **The old "refresh when someone opens the page" path was broken by security.**
   When we added the officer key, that refresh started being rejected (401) and the
   error was silently swallowed, so the chart froze on whatever was last stored.
3. **The "Rainfall (24h)" card was misleading.** It took the newest reading in the
   table, which can be a *forecast* day, and in the All States view it picked an
   Assam zone.
4. **Alerts are snapshots.** An alert's text is written when it is raised and never
   changes. Most Sikkim alerts were raised on Sep 6, so they looked "current" while
   the rainfall underneath had not moved.

A fifth thing we found while fixing it: **Open-Meteo refuses (HTTP 429) requests
from Render's shared IP address**, so the backend could not fetch rainfall itself
even when asked.

The "114 mm" mentioned for Sikkim was most likely a multi-day total, not one day
(largest single day in our data was 87.2 mm; largest 3-day zone total 122.1 mm).
Alerts are judged on multi-day totals against the rainfall threshold.

## How it works now
- **Every hour**, a GitHub Actions job fetches rainfall from Open-Meteo itself and
  sends it to the backend, which stores it and fires or clears alerts. (GitHub's
  servers are not blocked the way Render's is.)
- **Opening the dashboard** also nudges the backend to refresh if the data is over
  150 minutes old. This is a backstop for a missed hourly run.
- The dashboard shows **"Rainfall updated X min ago"**, so anyone can see how fresh
  the data is.
- **"Rainfall (24h)"** now uses only real, observed days (never a forecast) and
  says which day the number is for.
- Each alert shows **"Rain now: X mm (day)"** next to its original text.
- **Assam** is refreshed but does not raise alerts (its rainfall threshold comes
  from a Guwahati urban study and would flag every monsoon day). The dashboard
  now says "Alerting not enabled for Assam" instead of a misleading 0.
- **"Affected Villages" was renamed "Zones Under Alert"**: we have no village
  data; the card counts zones with an active alert.

## Before a demo or judging
1. Open Actions -> **Refresh rainfall** -> **Run workflow** once, to wake the
   Render server and make the data fresh. GitHub can delay scheduled runs.
2. Check the dashboard says "Rainfall updated ... min ago" with a small number.
3. If the run goes red, the log shows the exact error. `GET /rainfall/status` on
   the backend shows when data was last refreshed.

## If a judge asks
- *"Is the rainfall live?"* Yes: fetched hourly from Open-Meteo (a real weather
  model service, not an IMD gauge feed) and refreshed when the dashboard opens.
  The 3 days shown as forecast are labelled as forecast and never trigger alerts.
- *"Why does Assam show no alerts?"* Alerting is deliberately off for Assam until
  its threshold is properly validated; the dashboard says so.
