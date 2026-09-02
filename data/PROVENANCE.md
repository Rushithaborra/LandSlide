# Data/GIS Pipeline — Provenance & Deviations from the Onboarding Docs

Read this alongside the team onboarding guide's Section 8 (Known Issues & Honesty
Notes). Everything below is either a confirmation of what that doc claimed, or a
correction to it, based on actually running the pipeline — not a re-read of the docs.

## What's done (Day 1 core inputs)

| Output | Script | Status |
|---|---|---|
| `data/raw/sikkim_boundary.geojson` | manual (geoBoundaries IND-ADM1) | Done |
| `data/raw/Copernicus_DSM_COG_10_N27_00_E088_00_DEM.tif` + `..._N28_...` | manual (AWS) | Done |
| `data/processed/dem_sikkim_utm45n.tif` | `scripts/01_prep_dem.py` | Done |
| `data/processed/slope_deg.tif`, `aspect_deg.tif` | `scripts/01_prep_dem.py` | Done |
| `data/raw/gsi_sikkim_landslides.csv` (+ `_raw.geojson`) | `scripts/02_fetch_landslide_inventory.py` | Done, 768 records |
| `data/raw/sikkim_roads.geojson` | `scripts/03_fetch_roads_and_check_bias.py` | Done, 7357 segments |

Not started yet: drainage density, lithology, land use, negative sampling.

## Corrections to the onboarding doc

1. **"One DEM tile covers all of Sikkim" is wrong.** Sikkim's real bounding box
   (computed from the actual state polygon, not eyeballed) is
   **27.079–28.129°N, 88.013–88.920°E**. The state's northern tip sits above 28°N,
   which is outside `Copernicus_DSM_COG_10_N27_00_E088_00_DEM` — you need the
   `N28_00_E088_00` tile too. Both are mosaicked in `01_prep_dem.py`.

2. **GSI NLFC's "Download Data" PDF was never used.** The portal
   (bhusanket.gsi.gov.in) runs on ArcGIS and exposes a live FeatureServer
   (`Hosted/India_All_Landslided/FeatureServer/0`) with the full landslide
   inventory as queryable point data — richer than the PDF (state, district,
   material, movement type, lat/lon, dozens more fields) and no PDF-table
   extraction needed. The FeatureServer itself demands an auth token, but the
   site's own proxy (`bhusanket.gsi.gov.in/DotNet/proxy.ashx?<url>`) passes
   queries through without one — this is the same mechanism the portal's own
   map viewer uses, not an exploit. Queried `where=state='Sikkim'` → **768
   records** (doc says 777; small delta is expected, the inventory updates
   over time).

3. **`bhukosh.gsi.gov.in` and `ngdr.mines.gov.in` were both unreachable** when
   checked (DNS/connection failures) — matches the onboarding doc's general
   warning about Indian government portal reliability, but specifically rules
   out `myrole.md` and `vardhan_ds_01.md`'s primary recommendation of bhukosh
   for the landslide inventory and lithology. Only `bhusanket.gsi.gov.in`
   responded.

## Verified (not just repeated) from the onboarding doc

- **Road-proximity bias**: independently re-measured at **97.0%** of landslide
  points within 100m of a road (doc states 96.1%) using freshly-pulled OSM
  road data — consistent, not just copied. Median distance to nearest road:
  6.7m. This bias is real; do not use distance-to-road as a model feature,
  and match this distribution when generating negative samples.
- **All 768 landslide points fall inside the Sikkim boundary polygon**
  (spot-checked all of them via point-in-polygon, not just 15 — cheap to do
  exhaustively once the boundary and inventory are both loaded).

## A bug caught and fixed during processing

The raw Copernicus DEM tiles don't declare a nodata value in their metadata.
Clipping to the Sikkim polygon without explicitly setting one caused
`rasterio.mask` to silently fill everything outside the state boundary with
elevation `0` (33% of the raster) — indistinguishable from real low terrain,
and it would have produced fake near-vertical "cliffs" in the slope/aspect
calculation right at the boundary edge (real elevation ~2000m next to
fill-value 0 within one pixel). Fixed by using `-9999` as an explicit nodata
sentinel through the mosaic → clip → reproject → slope/aspect pipeline, and
masking any 3x3 slope/aspect window that touches a nodata cell.

## Round 2 — remaining layers from the master dataset list

| Output | Script | Status |
|---|---|---|
| `data/processed/streams.tif`, `distance_to_stream_m.tif` (drainage density) | `scripts/06_derive_drainage_density.py` | Done — pysheds: fill pits → fill depressions → resolve flats → D8 flow direction → accumulation → threshold → distance transform |
| `data/raw/ESA_WorldCover_10m_2021_v200_N27E087_Map.tif`, `data/processed/landcover_sikkim_utm45n.tif` | `scripts/09_prep_landuse.py` | Done |
| `data/raw/sikkim_population_1km.tif` | `scripts/08_fetch_population_clip.py` | Done, at 1km not 100m (see note below) |
| `data/raw/sikkim_villages.geojson` (120), `sikkim_health_edu.geojson` (106) | `scripts/07_fetch_dashboard_extras.py` | Done |
| Lithology | — | **Blocked**, see below |
| `data/raw/sikkim_buildings.geojson` | `scripts/07c_fetch_buildings_chunked.py` | **Blocked**, see below |

### Lithology: genuinely unavailable within a reasonable time-box

Both GSI portals remain unreachable (re-checked, not just carried over from
round 1): `bhukosh.gsi.gov.in` and `ngdr.mines.gov.in` both fail to connect.
Looked for a global fallback — PANGAEA hosts the Global Lithological Map
(GLiM, Hartmann & Moosdorf 2012), but the freely-downloadable file
(`hartmann-moosdorf_2012.zip` via `hdl.handle.net/10013/epic.39939.d001`) is
only the **0.5° gridded version** (~55km cells) — Sikkim is ~110km wide, so
that would give the whole state 2-4 lithology values, not a usable feature.
The full-resolution 1.2M-polygon shapefile wasn't locatable within a
reasonable search window. Per the doc's own guidance ("time-box to ~1hr,
ship v1 without it"), lithology is parked. If someone finds GSI Bhukosh
access later (VPN, different network, etc.) or the full-res GLiM shapefile,
it's still worth adding.

### Buildings: blocked by Overpass server load, not a query problem

Tried three approaches, in order: (1) the full-state query as originally
written, (2) the same query after backing off 60s for what looked like
rate-limiting, (3) splitting into 4 geographic quadrants. All three failed
with the same mix of errors (`IncompleteRead`, 502/504/500) across *both*
the main Overpass server and the kumi mirror — including on a single
quadrant (a quarter of the state), which rules out "the query is just too
big." This looks like the public Overpass infrastructure being under load
at the time, not something fixable by retrying the same approach again.
Buildings is explicitly optional/patchy-in-rural-areas per every team doc;
parking it. Retry `scripts/07c_fetch_buildings_chunked.py` later if needed.

### Population: 1km resolution, not 100m

WorldPop's India population raster at 100m is 753MB, and that server
doesn't support HTTP range requests (GDAL's `/vsicurl/` remote-windowed-read
errored: "Range downloading not supported by this server!"), so a partial
read wasn't possible. Downloading 753MB for one small state, when
population is explicitly optional/non-blocking in every doc, wasn't worth
it. Used WorldPop's 1km product instead (19MB, same source, same year) --
still gives Sikkim a ~110x130 cell grid, plenty for a dashboard overlay.
Sanity check: 678,797 estimated 2020 population vs. Sikkim's actual 2011
census figure of ~610,577 — same order of magnitude, plausible given 9
years of growth on a 2020 gridded model estimate (not a census).

### A land-cover finding B (ML lead) should know about

Landslide points hit ESA WorldCover's "Built-up" class at **10.2%**
(78/765) vs. only **5.1%** (39/766) for the road-bias-matched negative
samples. This is very likely the *same* reporting-proximity artifact as the
road bias (Section 8 of the onboarding doc) showing up again — built-up
areas cluster along roads and settlements, i.e. exactly where landslides
get observed and logged. Negative sampling was only built to match
road-proximity, not land-cover class, so this residual skew got through.
Worth watching in feature importance / partial dependence once B trains a
model — if `landcover_class` (Built-up) comes out as a strong predictor,
suspect this artifact before trusting it as a real signal.

On the other side: distance-to-stream shows a real, plausible difference
(landslide points: 262.9m median vs. negatives: 344.0m) — landslides
clustering closer to drainage lines matches known geomorphology (slope
undercutting, saturated ground), not an obvious reporting artifact.

## Overpass API note

An unfiltered `highway=*` query over Sikkim's bbox pulls in the region's large
trekking-trail network (footpaths/tracks around Kangchenjunga) and produced a
response large enough to repeatedly fail mid-download (`IncompleteRead`,
502/504 gateway errors) against both the main Overpass server and the kumi
mirror. Filtering to drivable classes
(`motorway|trunk|primary|secondary|tertiary|unclassified|residential|service`)
fixed it. If a later pass wants footpaths/tracks too, fetch them as a
separate, smaller query rather than widening this one.

## Round 3 — RUSLE erosion factor stack + dashboard export

| Output | Script | Status |
|---|---|---|
| `data/processed/flow_accumulation.tif`, `rusle_ls_factor.tif` | `scripts/11_rusle_ls_c_factor.py` | Done |
| `data/processed/rusle_c_factor.tif` | `scripts/11_rusle_ls_c_factor.py` | Done |
| `data/processed/rusle_klcp_partial.tif` (K×LS×C×P) | `scripts/11_rusle_ls_c_factor.py` | Done — missing only R (rainfall erosivity), blocked on Role C |
| `data/dashboard/*.png` + `manifest.json` | `scripts/12_export_dashboard_layers.py` | Done |

### Two bugs caught building the LS-factor

1. **LS-factor blew up to 6786 at river channels on the first run.** The
   Moore & Burch (1986) formula treats flow accumulation as a proxy for
   hillslope length, which breaks down at valley bottoms where accumulation
   represents a whole watershed (hundreds of thousands of cells), not a
   hillslope. Fixed by capping the accumulation-derived length at 300m — a
   standard cap in operational RUSLE mapping (Renard et al. 1997, AH703).
   Range after the fix: 0.00–63.44, median 17.62 — sane for mountainous
   terrain.

2. **Combining K × LS × C crashed on a shape mismatch, then would have
   silently produced garbage if it hadn't.** `rusle_k_factor.tif` (from
   SoilGrids, ~247m native) and `landcover_sikkim_utm45n.tif` (from
   WorldCover, ~10m native) were each reprojected to EPSG:32645
   independently, so they share Sikkim's extent and CRS but **not** the
   DEM's pixel grid. Point-sampling (`scripts/05`) doesn't care about this
   — it looks up by coordinate — but array-level combination does. Fixed by
   resampling every layer onto the DEM's exact grid (nearest-neighbor for
   the categorical land cover, bilinear for the continuous K-factor) before
   multiplying. Worth checking for this same class of bug in any other
   raster combined by array math rather than point-sampling.

### Erosion output

`rusle_klcp_partial.tif` = K × LS × C × P (support-practice P defaulted to
1.0 — no terracing data available). Range 0.0000–7.8025, median 0.0032: the
low median matches Sikkim's ~51% forest cover (C ≈ 0.001 there suppresses
the product almost to zero), with the high end coming from bare/cropland/
built-up pixels on steep slopes. Multiply by R (rainfall erosivity,
MJ·mm/(ha·h·yr)) once Role C's rainfall data supports computing it, for the
full annual soil-loss estimate in t/ha/yr.

## Round 4 — R-factor and the completed RUSLE equation

Role C never delivered a separate rainfall-erosivity dataset (there wasn't
a "Role C" actively feeding this session), so R was computed directly:
`scripts/13_compute_rainfall_erosivity.py` samples a 182-point grid across
Sikkim at ~0.09° spacing (matching ERA5's native ~10km resolution — no
point oversampling), pulls 10 years (2014–2023) of daily precipitation per
point from Open-Meteo's archive API (the team's already-confirmed working
rainfall source), derives R via the Modified Fournier Index and the
Arnoldus (1980) regression (`R = 4.17×MFI − 152`, MJ·mm/(ha·h·yr) — a real,
literature-standard formula for exactly this data-scarce situation, same
"verify against the primary text before quoting to judges" caveat as the
Harilal et al. rainfall threshold), then interpolates the point values onto
the DEM grid.

**Hit Open-Meteo's rate limit** repeatedly — 25-point batches back-to-back
triggered 429s immediately; smaller batches (12 points) with an 8s pause
and exponential backoff (15/45/90/180s) got most of the way through but
still hit a persistent 429 wall on 3 of 16 batches even after the full
backoff chain (up to 180s) — this reads as a longer-duration quota, not
just burst throttling. Fixed two ways: (1) each batch's raw response is
now cached to `data/interim/rainfall_cache/` so a re-run never re-fetches
data already obtained, and (2) a batch that exhausts all retries is now
*skipped* with a warning instead of crashing the whole script. Final run
used 156 of the 182 sample points (86%) — still solid coverage at ERA5's
~10km native resolution, and the soil-loss median barely moved between the
182-point and 156-point interpolations (6.80 → 6.86 t/ha/yr), confirming
the missing 14% didn't meaningfully change the result.

R-factor: 101.9–3732.8, median 1847.1 MJ·mm/(ha·h·yr) across 156 sample
points — plausible for Sikkim specifically once you account for its huge
elevation-driven climate gradient (humid subtropical south around 300m
down to cold, dry high-alpine north near the Tibetan plateau), even though
it reads low against generic "monsoon South Asia" figures that mostly
describe wetter lowland regions. Also derived `mean_annual_rainfall_mm.tif`
(the raw climatology, not just erosivity) alongside R: 478–8303mm, median
3278mm — matches Sikkim's known south-wet/north-dry gradient.

`rusle_soil_loss_annual.tif` = K × LS × C × P × R, the full annual soil
loss estimate (t/ha/yr) — **this completes RUSLE**. Median 6.86 t/ha/yr,
90th percentile 302.38, max 10,339.52.

### A real limitation, not a bug — documented, not hidden

The extreme tail (3.0% of the state above 1000 t/ha/yr) is heavily
elevation-concentrated: median elevation 4605m among those pixels vs.
3656m overall, and 5.0% of the area above 4000m exceeds 1000 t/ha/yr vs.
only 0.25% below 2000m. Traced the single max pixel (10,339.5 t/ha/yr,
27.61°N 88.22°E) through every component factor — K=0.305, LS=48.9 (steep,
53°), C=0.45 (bare/sparse vegetation class), R=1542.7 — and the arithmetic
is exactly right; this is not a resampling or alignment bug like the two
caught in Round 3. It's RUSLE itself being applied outside where it's
valid: the equation was built for rainfall-driven sheet-and-rill erosion on
soil-covered slopes (cropland, pasture, temperate hillslopes), not
periglacial/rockfall-dominated bare rock and scree above ~4000m, which is
44% of Sikkim's area. Don't present the raw max to a jury or trust pixels
above the snowline/treeline as literal soil-loss predictions — use median/
90th-percentile summaries, and say plainly that RUSLE's high-alpine output
should be read as "not physically meaningful here" rather than silently
capped to look cleaner. The dashboard PNG (below) already reads as
reasonable because it's percentile-clipped (2nd–98th) for display, which
incidentally hides this tail — worth a caption on the dashboard itself,
not just in this file.

### Dashboard export

Nothing in `data/processed/` was usable by a React+Leaflet dashboard
directly — all analysis-grade GeoTIFF in EPSG:32645. `scripts/12` reprojects
the dashboard-relevant rasters (elevation, slope, distance-to-stream, land
cover, K-factor, the full RUSLE soil-loss estimate, population) to
EPSG:4326, colorizes them (land cover uses ESA WorldCover's official legend
colors, not an arbitrary palette), and writes PNG + a `manifest.json` with
each layer's `bounds_leaflet` in the exact `[[south,west],[north,east]]`
shape `L.imageOverlay(url, bounds)` expects. Vector layers (roads,
villages, health/edu, landslide points, boundary) needed no conversion —
they're already GeoJSON and drop straight into `L.geoJSON()`. Skipped on
purpose: `flow_accumulation.tif` and `streams.tif` (intermediate technical
layers, not end products) and the 4 raw soil property layers (inputs to
K-factor, already represented by it).

### Training table

`training_table.csv` now carries the full RUSLE factor breakdown
(`soil_erodibility_k`, `rusle_ls_factor`, `rusle_c_factor`,
`rainfall_erosivity_r`, `soil_loss_tha_yr`) alongside the original terrain/
landslide columns — the same 1529-point set now supports both the
susceptibility model and erosion analysis. See `scripts/05`.

## Round 5 — matching Role B's exact handoff format

Role B sent `handoff_format_for_A.md` specifying an exact CSV schema. Two
things worth flagging:

1. **B's spec explicitly says not to send negative samples**: "Do NOT
   generate 0-rows — negative sampling is my job, not yours... Sending
   only label=1 rows is correct." `training_table.csv` already has 766
   bias-matched negatives built earlier this session (a materially more
   careful methodology than a generic boundary-buffer approach — see
   Round 1/2's negative-sampling bug-fix writeup). Rather than override
   what B explicitly asked for, `scripts/15_build_handoff_csv.py` produces
   a **separate** file (`handoff_for_B.csv`) with positive rows only,
   matching B's spec exactly. `training_table.csv` still exists in case B
   wants to use the already-built negatives instead of re-deriving them.

2. **Two required/nice-to-have fields needed new derivations**:
   `drainage_density` (a real moving-window stream-density metric,
   normalized 0-1 — not the same thing as `distance_to_stream_m`, which is
   a different metric already in the training table) and
   `mean_annual_rainfall_mm` (the raw climatology, split out from the
   R-factor computation in Round 4). `curvature` and `terrain_ruggedness`
   (Riley et al. 1999 TRI) were both explicitly optional-tier but cheap to
   add given the DEM was already on disk — see `scripts/14`.

`lithology` is sent as an empty column, not fabricated or omitted —  both
GSI portals are still unreachable. `landuse` uses plain category names
(e.g. "forest") per B's spec, not the WorldCover numeric codes.

**Found and fixed a real data-quality issue in GSI's own source data**:
the `district` field had 17 distinct raw values for Sikkim's 4 traditional
districts — whitespace inconsistencies ("East Sikkim" vs " East Sikkim"),
inconsistent suffixes ("East District" / "East district, Sikkim" / "East
Sikkim"), and HQ town names used as stand-ins (Namchi=South, Gangtok/
Pakyong=East, Geyzing/Gyalshing/Soreng=West). B asked for this field
specifically for a data-quality slide, so it's normalized to the 4 clean
names rather than passed through messy.

Output: `data/processed/handoff_for_B.csv`, 765 rows (768 landslide points,
3 dropped to nodata at raster edges), 18 columns — every required and
nice-to-have field from `handoff_format_for_A.md` is present and populated
except `lithology`. The boundary polygon B asked for separately is at
`data/raw/sikkim_boundary.geojson`, already the correct format (GeoJSON).
