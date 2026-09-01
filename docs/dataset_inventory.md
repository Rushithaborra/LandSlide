# Dataset Collection Inventory — Sikkim Landslide EWS

Generated 2026-09-01, against `Data_Sources_Checklist.md` (the team's master
list). This is a **collection and documentation pass only** — nothing here
has been used to train a model or select features. Full field-by-field
provenance is in [`data/raw/MANIFEST.csv`](../data/raw/MANIFEST.csv)
(source URL, license, account requirement, limitations, leakage concerns per
dataset); this doc is the readable summary.

## A. Complete dataset inventory

| # | Dataset | Source | Status | Downloaded? | Format | Resolution | Coverage | Notes |
|---|---|---|---|---|---|---|---|---|
| 1/10 | GSI landslide inventory (Sikkim) | bhusanket.gsi.gov.in | ACCESSIBLE | Yes | CSV (extracted from PDF) | Point | Sikkim, 777 records | 96.1% within 100m of a road (verified) |
| 2 | Sikkim admin boundary | GADM v4.1 | ACCESSIBLE | Yes | GeoJSON | State-level vector | Sikkim | License restricts commercial redistribution |
| 2 (alt) | Survey of India boundary | soi.gov.in | **NOT ACCESSIBLE** | No | — | — | — | Domain unreachable |
| 3 | DEM | Copernicus GLO-30 (AWS) | ACCESSIBLE | Yes | COG GeoTIFF | ~30m | Single tile, all of Sikkim | Needs UTM reprojection (verified) |
| 3 (alt) | DEM | OpenTopography | Needs account | No | — | — | — | 401 without API key |
| 4/5/13 | Slope, aspect, curvature | Derived from #3 | Pipeline built | n/a (derived) | numpy/GeoTIFF | ~30m | Same as DEM | See E below |
| 6/14 | Drainage density, distance-to-drainage | Derived from #3 | Pipeline built | n/a (derived) | numpy/GeoTIFF | ~30m | Same as DEM | Density itself not yet computed (have distance-to-drainage) |
| 7 | Lithology/geology | GSI Bhukosh | **NOT ACCESSIBLE** | No | — | — | — | Domain unreachable; NGDR alternate also unreachable |
| 7 (alt) | GLiM lithology | PANGAEA | ACCESSIBLE | Yes | ASCII grid | **0.5° (~55km) — too coarse to use** | Global | Kept for documentation only |
| 8 | Land cover | ESA WorldCover | ACCESSIBLE | Yes | COG GeoTIFF | 10m | 3×3° tile, all of Sikkim | 2021 snapshot |
| 8 (alt) | Land cover | Bhuvan | Reachable, no bulk-download found | No | — | — | — | Interactive viewer, not pursued further |
| 9 | Rainfall | Open-Meteo | ACCESSIBLE (live API) | n/a (API) | JSON | Hourly/daily, ~10km | Any point | Not the deck's stated primary (IMD); IMD confirmed unreachable |
| 12 | Negative samples | Generated, not downloaded | n/a | n/a | — | — | — | Already built separately, untouched this pass |
| 15-18 | SoilGrids (clay/sand/silt/SOC) | ISRIC | ACCESSIBLE | Yes | GeoTIFF | 250m | Exact Sikkim bbox | Anonymous WCS access, no login |
| 19 | SMAP soil moisture | NASA Earthdata | **NOT ACCESSIBLE** | No | — | — | — | Requires account; no-login alternate also login-gated |
| 20 | Sentinel-1 | Planetary Computer (not Copernicus Data Space) | ACCESSIBLE, verified | No (query only) | COG (per-scene) | ~10-20m | Queryable | Real scene found; full download is follow-up work |
| 21 | Sentinel-2 | Planetary Computer | ACCESSIBLE, verified | No (query only) | COG (per-scene) | 10-20m | Queryable | Same as above |
| 22 | Roads | OpenStreetMap/Overpass | ACCESSIBLE | Yes | GeoJSON | Vector | Sikkim + margin | Already had this |
| 23 | Villages/hamlets | OpenStreetMap/Overpass | ACCESSIBLE | Yes | GeoJSON | Point | Sikkim + margin | 341 points |
| 23 (alt) | Census village boundaries | censusindia.gov.in | Reachable, not pursued | No | — | — | — | OSM points sufficient for now |
| 24 | Buildings | OpenStreetMap/Overpass | ACCESSIBLE | Yes | GeoJSON | Point (centroid) | Sikkim + margin | 289,607 — centroids only, not footprints |
| 25 | Population | WorldPop India 2020 | ACCESSIBLE | Yes | GeoTIFF | 1km | All India | Not yet clipped to Sikkim |
| 26 | Hospitals/schools | OpenStreetMap/Overpass | ACCESSIBLE | Yes | GeoJSON | Point | Sikkim + margin | 138 points |
| 27 | Critical infrastructure | OpenStreetMap/Overpass | ACCESSIBLE | Yes | GeoJSON | Point | Sikkim + margin | 2,353 points (power/telecom tags only) |

## B. Downloaded raw data

All in `data/raw/`:
```
data/raw/
  gsi_sikkim_landslides.csv          777 landslide records (already had)
  sikkim_roads.geojson               22,414 road segments (already had)
  boundary/
    gadm41_IND_1.json.zip            all India states
    sikkim_boundary.geojson          Sikkim extracted
  dem/
    N27_00_E088_00.tif                Copernicus GLO-30 (already had)
  landcover/
    ESA_WorldCover_10m_2021_v200_N27E087_Map.tif
  lithology/
    GLiM_0.5deg_gridded.zip           coarse, documented as impractical
  soilgrids/
    clay_0-5cm_mean_sikkim.tif
    sand_0-5cm_mean_sikkim.tif
    silt_0-5cm_mean_sikkim.tif
    soc_0-5cm_mean_sikkim.tif
  population/
    ind_ppp_2020_1km_Aggregated.tif
  osm_extras/
    villages_hamlets.geojson
    buildings_centroids.geojson
    hospitals_schools.geojson
    infrastructure.geojson
```
No raw file was overwritten during this pass — everything above is untouched
original source data. (`sikkim_roads.geojson` and the DEM tile are gitignored
as large/regeneratable, per the existing project convention — see `.gitignore`.)

## C. Provenance manifest

[`data/raw/MANIFEST.csv`](../data/raw/MANIFEST.csv) — 24 rows, one per
dataset/source investigated (including the ones that failed), with all
required fields: source URL, download date, format, spatial/temporal
coverage, resolution, license, account requirement, access status, local
path, intended use, known limitations, leakage concerns.

## D. Not accessible — and exactly why

| Source | Why |
|---|---|
| GSI Bhukosh (`bhukosh.gsi.gov.in`) | Domain unreachable from this environment (both direct requests and browser navigation failed — not a login wall, the site itself didn't respond) |
| NGDR (`ngdr.mines.gov.in`) | Same — unreachable |
| Survey of India (`soi.gov.in`) | Same — unreachable |
| SMAP soil moisture (NASA Earthdata) | Requires an account — cannot be created on the team's behalf. A no-login alternate (ESA CCI Soil Moisture via CEDA) also appears to require registration |

None of these were silently substituted — each is recorded as not accessed, per instruction. If anyone on the team already has GSI Bhukosh/NGDR credentials or can reach those domains from a different network, the lithology gap could close quickly.

## E. Derived layers still needed

- **Drainage density** specifically (as distinct from distance-to-drainage, which we do have) — same D8 flow-accumulation pipeline (`scripts/ml/extract_terrain_features.py`) could produce it with a small addition (kernel density of stream cells) if wanted
- Everything else in the "derived" category (slope, aspect, curvature, distance-to-drainage) already has a working, tested extraction pipeline from the collected DEM — no new source data needed, just re-running the existing scripts

## F. Datasets requiring preprocessing before use

- **WorldPop population** — whole-India raster, needs clipping to the Sikkim boundary (`data/raw/boundary/sikkim_boundary.geojson`, now available)
- **ESA WorldCover** — full 3×3° tile, could be clipped tighter to the road corridor if file size becomes a concern
- **SoilGrids** rasters — already clipped to the Sikkim bbox at download time, no further clipping needed, but not yet aligned/resampled to the DEM's 30m grid for feature-stacking
- **OSM buildings** — centroids only; if footprint area/density (not just point density) is ever wanted, needs re-fetching as polygons
- **GLiM lithology** — impractically coarse (0.5°) as-is; would need the finer-resolution vector version (not located in this pass) to be usable at all
- **Sentinel-1/2** — access verified, but no actual scene has been downloaded/mosaicked/cloud-filtered yet — this is real follow-up work, not a quick preprocessing step

---
**Stopping here, as instructed.** No ML training, no feature selection, no changes to the backend or the existing susceptibility dataset. This pass only collected and documented.
