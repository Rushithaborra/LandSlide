# NER Expansion — Dataset Inventory

Extends the Sikkim-only pipeline (`README.md`, `data/PROVENANCE.md`) to
the 7 remaining North-East states. Same honesty standard as the rest of
this repo: every source is marked ACCESSIBLE or NOT ACCESSIBLE based on
what was actually reached, not what should theoretically work. Nothing
here is fabricated or silently substituted — where data is thin or
unreliable, it's flagged, not hidden. See also
`data/processed/README.md` for a reader-facing summary of per-state data
quality, and `HANDOFF_remaining_states.md` for what's still in progress.

## Status as of 2026-09-14

| State | Landslide records (deduped) | Modeled? | Rainfall data quality |
|---|---:|---|---|
| Mizoram | 1,881 | Yes | **Poor — 24/496 rainfall points fetched (4.8%)** |
| Nagaland | 1,571 | Yes | Good — 348/552 fetched (63%) |
| Manipur | 1,437 | Yes | Good — 384/506 fetched (76%) |
| Arunachal Pradesh | 1,038 | Not yet | N/A — pipeline paused, see below |
| Meghalaya | 892 | Yes | **Very poor — 12/540 fetched (2.2%), 10 unique values total** |
| Assam | 590 | Not yet | N/A — pipeline paused, see below |
| **Tripura** | **66** | **No — below modeling threshold** | N/A |
| (Sikkim, reference) | 768 | Yes (pre-existing) | Good |

## Modeling threshold

Sikkim's model was trained on 768 records. The team set the bar for the
NER states at matching that scale (~500+ records), decided explicitly
rather than picked silently. Six of seven states clear it; Tripura (66
records, ~12x smaller than Sikkim) does not and is **not modeled** — its
inventory CSV (`data/raw/gsi_tripura_landslides.csv`) is still produced
and logged, per the instruction not to pad or silently drop a thin state.

## 1. Landslide inventory (positive samples)

**Source**: GSI NLFC's live ArcGIS FeatureServer, via the same public
proxy method already used for Sikkim (`scripts/16_fetch_ner_landslide_inventories.py`,
generalizing `scripts/02`) — not the national PDF report, which this
repo's own `data/PROVENANCE.md` already documented as abandoned for
Sikkim in favor of the FeatureServer.

Status: **ACCESSIBLE** for all 7 states.

Two real bugs caught and fixed during this step:
- The FeatureServer's `maxRecordCount` is 2000 — a single-page query
  silently truncated Mizoram (2046 true records) to exactly 2000. Fixed
  with pagination + a `returnCountOnly` cross-check.
- The original CSV writer corrupted rows whenever a field (e.g.
  `NH_SH_Location`) contained an embedded newline, splitting one logical
  row into two physical lines. Affected 5 of 6 new states and, discovered
  later, the pre-existing Sikkim CSV too (6 rows). Fixed by switching to
  Python's `csv.writer`, which properly quotes such fields.

Dedup: exact-coordinate duplicates dropped (same physical report entered
twice), applied uniformly to every state.

## 2. Boundary + geography

**Source**: geoBoundaries.org `IND-ADM1` (same source as Sikkim's own
boundary, not GADM — the original task brief assumed GADM without that
matching what this repo actually uses).

Real bbox and UTM zone(s) computed per state, not copied from Sikkim's
45N:

| State | UTM handling |
|---|---|
| Assam | Spans 3 zones (45N-47N) — custom transverse Mercator centered on 92.86°E |
| Arunachal Pradesh | Spans 2-3 zones (46N-47N, tip nears 48N) — custom TM centered on 94.48°E |
| Meghalaya | Spans 2 zones (45N-46N) — custom TM centered on 91.31°E |
| Manipur, Mizoram, Nagaland | Single zone (46N) — standard EPSG:32646 |

Full config: `scripts/ner_config.py`.

## 3. DEM, terrain, roads, land cover, soil

Same methods as Sikkim (Copernicus GLO-30, ESA WorldCover, ISRIC
SoilGrids, OSM/Overpass), generalized into `scripts/18-20` and
parameterized by `scripts/ner_config.py` — one pipeline, not a per-state
copy. Bias percentages (road-proximity, land-cover skew) are recomputed
per state, never assumed to match Sikkim's figures — e.g. Manipur's
road-proximity bias measured at 64.3%, dramatically different from
Sikkim's 97.0%.

Assam's Overpass road query is large enough to hit server-side 504
timeouts on the whole-bbox query; `scripts/19` automatically falls back
to a 2x2 quadrant split and merges results when this happens.

## 4. Rainfall (historical erosivity + live monitoring)

**Historical (RUSLE R-factor)**: Open-Meteo archive API,
`scripts/21_compute_state_rainfall_erosivity.py`. **This is the one part
of the pipeline that did not go cleanly** — see the per-state fetch
rates in the table above. Manipur and Nagaland are fine; Mizoram and
Meghalaya are not (see `data/processed/README.md` for the full
explanation); Assam and Arunachal Pradesh's rainfall step has not
completed at all, blocked by what looks like session-wide IP throttling
from Open-Meteo after many hours of sustained use (confirmed: stopping
one state running alongside another did not improve the other's success
rate, ruling out simple per-state contention).

Assam and Arunachal Pradesh also use a coarser rainfall sample grid
(0.25° vs. the default 0.09°) — their areas would otherwise need
~270 and ~193 API batches respectively (vs. ~40-50 for the smaller
states), a disclosed resolution tradeoff, not a silent shortcut.

**Live (current + 7-day forecast)**: Open-Meteo Forecast API
(`scripts/17_fetch_live_rainfall.py`), confirmed working for all 8 states
independent of the historical-archive throttling issue above (different
endpoint). This is a snapshot-on-demand, not a historical record.

**Published rainfall ID threshold**: only Assam has one — a real, citable
equation for Guwahati (`Intensity = 5.9 × Duration^-0.479`, ISPRS
Archives XL-8/15, 2014). No equivalent published threshold was found for
the other 6 states in a bounded search; their live rainfall is reported
without a pass/fail judgment rather than borrowing Assam's number.

## 5. Soil composition (static)

**Source**: ISRIC SoilGrids 2.0 via WCS, same as Sikkim. Status:
**ACCESSIBLE**, no account needed, generalized in `scripts/18`.

## 6. Soil moisture (live) — SMAP

**NOT ACCESSIBLE in this session.** NASA Earthdata's login service itself
responds (HTTP 200), but registering a new account requires an
interactive human signup (real name, email verification, EULA acceptance)
that isn't appropriate to automate on the user's behalf. Recommendation:
register manually at `urs.earthdata.nasa.gov/users/new`, then a follow-up
session can pull SMAP L3/L4 for all 8 states.

## 7. Lithology

**NOT ACCESSIBLE, retried and confirmed still down.** `bhukosh.gsi.gov.in`:
connection timeout (same as before). `ngdr.mines.gov.in`: DNS resolution
now fails outright (worse than before — the domain may have changed).
GLiM is deliberately not used as a fallback — its 0.5° resolution was
already documented as impractically coarse. Logged NOT ACCESSIBLE for all
8 states.

## 8. Inclinometer data

**NOT ACCESSIBLE — no public bulk dataset exists.** Confirmed via a
bounded search, not assumed: GSI/NDMA inclinometers are physical
instruments at specific monitored slopes, not published as open data.
Say this plainly to judges — it isn't part of this system.

## What's still in progress

See `HANDOFF_remaining_states.md` for full detail:
- Assam and Arunachal Pradesh: terrain/roads/soil done, rainfall step
  blocked on Open-Meteo throttling.
- Mizoram and Meghalaya: need their rainfall step re-run once Open-Meteo
  recovers — everything else about them is fine.
- Tripura: has an inventory but was never run through the full pipeline
  (below the modeling threshold); can be done on request, flagged as
  low-confidence given its small sample size.
