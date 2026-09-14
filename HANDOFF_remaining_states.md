# Handoff: finish Assam, Arunachal Pradesh (+ revisit Mizoram/Meghalaya rainfall), optionally Tripura

## Context — read this first

This is the NER (North-East Region) expansion of the Sikkim landslide EWS
data pipeline. The goal: produce `training_dataset_<state>.csv` (same
13-column schema as Sikkim's `data/processed/training_table.csv`) for each
qualifying state, using the same real-data honesty standard as the rest of
this repo — every source is ACCESSIBLE or NOT ACCESSIBLE, nothing is
padded, faked, or silently substituted.

**Work only in this directory** (`sih-landslide-ews-ner`), not the sibling
`sih-landslide-ews` folder. This is a `git worktree` — same repository,
same history, but pinned to `main` and physically separate from that other
folder, which someone else uses for unrelated frontend work and keeps
switching branches on. That collision already overwrote `.gitignore`,
`docs/dataset_inventory.md`, and `data/raw/MANIFEST.csv` twice this
session before the worktree was set up specifically to stop it happening
again. Do not run anything from `../sih-landslide-ews`.

## What's already done (don't redo)

| State | Status | Rows | Rainfall data quality |
|---|---|---|---|
| Manipur | Complete | 2,865 | Good (384/506 grid points fetched, 76%) |
| Nagaland | Complete | 3,128 | Good (348/552 fetched, 63%) |
| Mizoram | Complete but flawed | 3,751 | **Poor — only 24/496 points fetched (4.8%), just 275 unique rainfall values** |
| Meghalaya | Complete but flawed | 1,764 | **Very poor — only 12/540 points fetched (2.2%), just 10 unique rainfall values across the whole state** |
| Sikkim | Pre-existing, untouched | 1,529 | Original, fine |
| Tripura | Inventory only, NOT modeled | 66 landslide records | N/A — see "Tripura" section below |

**Mizoram and Meghalaya need their rainfall step re-run**, not just Assam
and Arunachal Pradesh — their `rainfall_erosivity_r` / `soil_loss_tha_yr`
columns are technically populated but built from so few real points they
don't reflect real spatial variation (Meghalaya's is essentially 10 flat
blocks, not a real field). This wasn't caught until after they were
reported "done" — don't repeat that mistake with Assam/Arunachal Pradesh:
check `Computed R-factor at X/Y points` in the log before calling a state
finished, not just whether the CSV file exists.

Everything else about these two states (terrain, roads, soil, land cover,
negative samples) is fine and does not need rework — only script 21
(rainfall) needs a clean re-run for them.

## What's NOT done

- **Assam**: terrain/DEM/roads/soil/landcover all done and cached
  (`data/processed/*_assam.tif`, `data/raw/assam_*`). Rainfall step
  (script 21) has never successfully completed — every batch attempted so
  far failed and was skipped (0/39 fetched in the last attempt).
- **Arunachal Pradesh**: same situation. Terrain/roads/soil/landcover done.
  Rainfall: 0 successes out of 13 batches attempted before this was
  stopped (100% failure rate).

## The actual blocker: Open-Meteo rate limiting

Both states' rainfall fetches were hitting **100% batch failure** —
every single batch exhausting all 5 retry attempts (15s→45s→90s→180s
backoff chain) and getting logged as skipped, not occasionally rate-limited
like the other 4 states were. This happened after roughly 14+ continuous
hours of this session hitting Open-Meteo's archive API
(`archive-api.open-meteo.com`) across all 6 states. It looks like IP-level
throttling that built up over the session, not a per-request or per-state
limit — stopping Assam did not help Arunachal Pradesh's failure rate at
all, which ruled out "two states competing" as the cause.

**Before retrying, check whether this has cleared**: run one small manual
test batch against the archive API from wherever you're running this (see
"Quick health check" below). If it's still failing 100%, more retries
won't help — either wait longer, try from a different network/IP, or
accept that column stays sparse for now and document it honestly (same as
everything else marked NOT ACCESSIBLE in this repo).

### Quick health check before doing anything else

```bash
cd /Users/rushithaborra/Documents/sih-landslide-ews-ner
curl -s "https://archive-api.open-meteo.com/v1/archive?latitude=26.14&longitude=91.73&start_date=2023-01-01&end_date=2023-01-05&daily=precipitation_sum" | head -c 300
```

If this returns real JSON (starts with `{"latitude":...`), the throttle
has cleared and it's safe to proceed. If it returns nothing, an HTML error
page, or a 429, wait longer before running the full pipeline again —
hammering it in that state just wastes hours for no data, as already
proven tonight.

## How to run each state

The pipeline is a single set of scripts parameterized by
`scripts/ner_config.py`'s `STATE_CONFIGS` dict — never write a
per-state copy of a script. One state at a time:

```bash
cd /Users/rushithaborra/Documents/sih-landslide-ews-ner
.venv/bin/python3 scripts/18_run_state_pipeline.py <state_slug>      # terrain/DEM/soil/landcover -- SKIP if already cached (see table above)
.venv/bin/python3 scripts/19_fetch_state_roads_and_negatives.py <state_slug>  # roads/negatives -- SKIP if already cached
.venv/bin/python3 scripts/21_compute_state_rainfall_erosivity.py <state_slug> # rainfall -- THIS is what needs (re-)running
.venv/bin/python3 scripts/20_build_state_training_dataset.py <state_slug>    # final assembly + bias audit
```

`<state_slug>` is one of: `assam`, `arunachal_pradesh`, `mizoram`,
`meghalaya` (for the rainfall-only redo), `tripura` (see below).

Or use the orchestrator, which retries a state up to 2x and skips
steps whose outputs already exist on disk:

```bash
./scripts/run_all_ner_states.sh assam arunachal_pradesh
```

**Do not run more than 2 states' rainfall step at once.** Running 2+
concurrently was already shown to multiply 429 failures without any
wall-clock benefit once Open-Meteo's limit is the bottleneck (confirmed
empirically this session, not a guess) — worse, it burns through more of
whatever throttling budget resets over time. Run them sequentially, or at
most 2 in parallel if you've confirmed via the health check that the API
is currently healthy.

### Grid resolution note

Assam and Arunachal Pradesh use a coarser rainfall sample grid (0.25° vs
the default 0.09°) than the other states — see `COARSE_GRID_STATES` in
`scripts/21_compute_state_rainfall_erosivity.py`. This was a deliberate,
disclosed tradeoff: at the default resolution they'd need ~270 and ~193
API batches respectively (vs. ~40-50 for the smaller states), which is
what caused the original multi-hour estimate before rate limiting even
became the dominant problem. Don't revert this without a good reason — it
was necessary just to get the batch count into a survivable range.

## Known bugs already found and fixed (don't rediscover these)

- `scripts/16`'s original CSV writer corrupted rows whenever a field (e.g.
  `NH_SH_Location`) contained an embedded newline — fixed by switching to
  Python's `csv.writer`. If you ever regenerate a `gsi_<state>_landslides.csv`
  by hand, use `csv.writer`/`csv.DictWriter`, never manual
  `",".join(...)`.
- The FeatureServer's `maxRecordCount` is 2000 — a naive single-page query
  silently truncates any state with more records (caught on Mizoram, which
  has 2046). Always paginate with `resultOffset`/`resultRecordCount` and
  verify against `returnCountOnly=true`.
- `urllib.request.urlretrieve` has no timeout and can hang forever on a
  stalled connection — `scripts/18`'s `download()` now streams via
  `urlopen(..., timeout=...)` with retries and a Content-Length check
  instead.
- Any temp file used during mosaicking must include `os.getpid()` in its
  name if two states might ever run `scripts/18` concurrently — a shared
  fixed name (`_mosaic_tmp.tif`) caused a real crash when Assam and
  Arunachal Pradesh briefly overlapped.
- A state whose bbox spans more than one UTM zone (Assam: 3 zones,
  Arunachal Pradesh: 2-3, Meghalaya: 2) uses a custom transverse Mercator
  centered on its own mean longitude (`ner_config.py`'s `custom_proj`),
  not a forced single UTM zone.
- Assam's Overpass road query is large enough to hit server-side 504s on
  the whole-bbox query; `scripts/19`'s `fetch_roads()` automatically falls
  back to a 2x2 quadrant split and merges results if the full query fails.

## Tripura

Tripura has only 66 landslide records after dedup — well below the
~500-record bar the team set (matching Sikkim's scale) for the other 6
states. It was **not** run through the full pipeline for that reason, only
through the landslide-inventory step (`data/raw/gsi_tripura_landslides.csv`,
`data/raw/tripura_boundary.geojson` already exist).

If you're asked to model it anyway: it's cheap to run (only 6 DEM tiles,
small area, few rainfall batches needed) — just run it through the same 4
scripts. But **flag it explicitly as below the team's own modeling
threshold** in whatever output/report this feeds — 66 points is thin for
a spatial susceptibility model, and the point of the threshold discussion
earlier in this project was specifically to not quietly ship an
under-powered dataset as if it were equivalent to the others.

## When you're done

Update `docs/dataset_inventory.md` and `data/raw/MANIFEST.csv` (create
them fresh in this worktree if they don't exist — they were repeatedly
overwritten by branch collisions in the other directory before this
worktree existed, so don't assume old content is still accurate) with:
per-state landslide counts, rainfall grid-point fetch rates (be honest
about sparse ones, per the Mizoram/Meghalaya table above), and the same
ACCESSIBLE/NOT ACCESSIBLE format already used for lithology/SMAP/
inclinometer elsewhere in this project.

Do not commit or push — leave changes as uncommitted working-tree files
for review, same rule as the rest of this session.
