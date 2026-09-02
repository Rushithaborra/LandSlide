# Sikkim Landslide EWS — Data/GIS Pipeline

Data pipeline for the **AI-Based Landslide Early Warning System** — SIH 2026, Problem Statement 26001 (Ministry of Development of North Eastern Region). Pilot state: **Sikkim**.

This repo covers the **Data/GIS side** of Feature 1 (susceptibility model + GIS heatmap) end to end — terrain processing, the landslide inventory, bias-controlled negative sampling, and a full training table — plus a complete **RUSLE soil-erosion model** built on top of it. It does not cover Feature 2 (rainfall alerts + citizen reporting), model training itself, or the dashboard frontend — those are other roles' work, described in the team onboarding guide.

## Quick facts

| | |
|---|---|
| Landslide inventory | 768 records, pulled live from GSI's ArcGIS FeatureServer (not the PDF report) |
| Training table | 1529 points × 13 columns, handed off for susceptibility modeling |
| Erosion model | Full RUSLE (K × LS × C × P × R) — soil loss estimate, t/ha/yr |
| Dashboard exports | 7 raster layers as PNG + Leaflet-ready manifest, 5 vector layers as GeoJSON |
| Blocked | Lithology (GSI portals down), building footprints (Overpass overload) |

Full methodology, every bug caught and fixed, and every literature caveat is in **[`data/PROVENANCE.md`](data/PROVENANCE.md)** — read that before trusting or presenting any number from this pipeline. A presentation-ready summary is in **[`Sikkim_Data_Dossier.pdf`](Sikkim_Data_Dossier.pdf)**.

---

## Repository structure

```
sih-landslide-ews/
├── scripts/              15 pipeline scripts, run in numeric order (see below)
├── data/
│   ├── raw/               Downloaded, unmodified source data
│   ├── processed/         Derived rasters/tables (clipped, reprojected, computed)
│   ├── dashboard/         Web-ready PNG exports + manifest.json for Leaflet
│   ├── interim/           Scratch/cache (Open-Meteo response cache, temp files)
│   └── PROVENANCE.md      Full methodology, bugs found & fixed, literature caveats
├── requirements.txt
└── Sikkim_Data_Dossier.pdf   Presentation-format summary of the whole pipeline
```

## Setup

```bash
cd sih-landslide-ews
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

No API keys or accounts needed anywhere in this pipeline — every source is either keyless-public or reached through a documented public endpoint.

## Reproducing the pipeline

Every output in `data/` was produced by one of these scripts. They're numbered in dependency order — run them in sequence for a from-scratch rebuild (roughly 20–30 min, mostly spent waiting on Open-Meteo's rate limits):

| # | Script | Produces |
|---|---|---|
| 01 | `01_prep_dem.py` | Mosaics 2 Copernicus DEM tiles, clips to Sikkim, reprojects to EPSG:32645, derives slope + aspect |
| 02 | `02_fetch_landslide_inventory.py` | Pulls the 768-record landslide inventory live from GSI's FeatureServer |
| 03 | `03_fetch_roads_and_check_bias.py` | Fetches OSM roads, independently verifies the inventory's road-proximity reporting bias |
| 04 | `04_generate_negative_samples.py` | Generates non-landslide points matching the positives' road-proximity distribution |
| 05 | `05_build_training_table.py` | Joins every terrain/erosion raster against the positive+negative points → `training_table.csv` |
| 06 | `06_derive_drainage_density.py` | Fill→flow-direction→accumulation→threshold→distance-to-stream, via pysheds |
| 07 / 07b / 07c | `07_fetch_dashboard_extras.py` (+retries) | Villages, hospitals/schools, buildings from OSM |
| 08 | `08_fetch_population_clip.py` | WorldPop population, clipped to Sikkim |
| 09 | `09_prep_landuse.py` | Clips/reprojects ESA WorldCover land cover |
| 10 | `10_fetch_soil_and_erodibility.py` | Soil clay/sand/silt/organic-carbon from ISRIC SoilGrids; computes RUSLE K-factor |
| 11 | `11_rusle_ls_c_factor.py` | LS-factor (flow accumulation + slope) and C-factor (land cover); combines K×LS×C×P |
| 12 | `12_export_dashboard_layers.py` | Reprojects + colorizes rasters to PNG for Leaflet, writes `manifest.json` |
| 13 | `13_compute_rainfall_erosivity.py` | R-factor from 10 years of Open-Meteo rainfall (Modified Fournier Index); **completes RUSLE** |
| 14 | `14_compute_additional_terrain_metrics.py` | Drainage density, curvature, terrain ruggedness index |
| 15 | `15_build_handoff_csv.py` | Builds the ML-lead-format handoff CSV (positive samples only, per their spec) |

Re-run any individual script any time an upstream source changes — everything downstream re-joins on `lon`/`lat`, nothing needs a full rebuild.

---

## Datasets

### Downloaded (live external sources)

| Dataset | Source | Used for |
|---|---|---|
| Sikkim boundary | [geoBoundaries.org](https://www.geoboundaries.org/api/current/gbOpen/IND/ADM1/) (IND ADM1) | Clip extent for every layer |
| DEM (2 tiles) | [Copernicus GLO-30, AWS Open Data](https://copernicus-dem-30m.s3.amazonaws.com/) | Elevation, slope, aspect, drainage |
| Landslide inventory | [GSI NLFC FeatureServer](https://bhusanket.gsi.gov.in/gisserver/rest/services/Hosted/India_All_Landslided/FeatureServer/0) | Positive samples (768 records) |
| Roads | [OpenStreetMap / Overpass API](https://overpass-api.de/api/interpreter) | Dashboard layer + bias verification + negative-sample anchoring |
| Land cover | [ESA WorldCover 2021 v200](https://esa-worldcover.org) | Vegetated/bare feature, RUSLE C-factor |
| Population | [WorldPop, Global_2000_2020_1km](https://www.worldpop.org) | Dashboard impact layer |
| Villages, hospitals/schools | OpenStreetMap / Overpass API | Dashboard context |
| Soil clay/sand/silt/organic carbon | [ISRIC SoilGrids 2.0 (WCS)](https://www.isric.org/explore/soilgrids) | RUSLE K-factor |
| Rainfall (10yr daily) | [Open-Meteo historical archive](https://archive-api.open-meteo.com/v1/archive) | RUSLE R-factor, mean annual rainfall |

### Derived (computed from the above)

Slope, aspect, drainage density/streams, flow accumulation, curvature, terrain ruggedness, land cover (clipped/reprojected), RUSLE K/LS/C/R factors and the combined soil-loss estimate.

### Generated (not from any single source)

Negative (non-landslide) samples — algorithmically placed to match the positive samples' measured road-proximity distribution, not downloaded or naively randomized.

### Blocked

- **Lithology** — both GSI portals (NGDR, BHUKOSH) unreachable; global fallbacks (GLiM, Macrostrat) too coarse to vary within Sikkim. See `PROVENANCE.md` for everything tried.
- **Building footprints** — Overpass public infrastructure overload across 3 different query strategies, not a query problem. Retry `07c_fetch_buildings_chunked.py` later.

---

## Key deliverables

- **`data/processed/training_table.csv`** — 1529 rows × 13 columns (`lon, lat, elevation_m, slope_deg, aspect_deg, distance_to_stream_m, landcover_class, soil_erodibility_k, rusle_ls_factor, rusle_c_factor, rainfall_erosivity_r, soil_loss_tha_yr, label`). Includes both positive (landslide) and bias-matched negative samples — ready to train a susceptibility classifier.
- **`data/processed/handoff_for_B.csv`** — 765 rows × 18 columns, matching the ML lead's exact requested schema. **Positive samples only**, per their explicit spec (negative sampling is their own pipeline's job).
- **`data/processed/rusle_soil_loss_annual.tif`** — full RUSLE annual soil-loss estimate (t/ha/yr). Read the caveat in `PROVENANCE.md` before presenting this above ~4000m elevation — RUSLE wasn't built for periglacial terrain.
- **`data/dashboard/`** — 7 PNG raster layers (elevation, slope, distance-to-stream, land cover, K-factor, soil loss, population) + `manifest.json` with Leaflet-ready bounds, plus pointers to the 5 GeoJSON vector layers in `data/raw/`. Drop straight into `L.imageOverlay()` / `L.geoJSON()`.

## Model input feature reference

| Column | Meaning |
|---|---|
| `elevation_m` | DEM elevation |
| `slope_deg` | Slope steepness, 0–90° |
| `aspect_deg` | Compass direction the slope faces, 0–360° |
| `distance_to_stream_m` | Distance to nearest derived drainage line |
| `drainage_density` | Local stream-length density in a 500m window, normalized 0–1 |
| `landcover_class` / `landuse` | ESA WorldCover class (code or name) |
| `soil_erodibility_k` | RUSLE K-factor (Williams 1995 EPIC formula) |
| `rusle_ls_factor` | RUSLE LS-factor (Moore & Burch 1986, capped at 300m equivalent slope length) |
| `rusle_c_factor` | RUSLE C-factor (literature values by land cover class) |
| `rainfall_erosivity_r` | RUSLE R-factor (Arnoldus 1980, from 10yr Open-Meteo rainfall) |
| `soil_loss_tha_yr` | Full RUSLE annual soil loss estimate |
| `curvature` | Laplacian of elevation — positive = ridge, negative = valley |
| `terrain_ruggedness` | TRI (Riley et al. 1999), meters |

---

## Notes for anyone continuing this work

- **Nothing here is fabricated.** Every download hit a live source; every derived value traces to a documented script; every literature-sourced coefficient (RUSLE C-values, the Arnoldus R-factor formula) is flagged as needing primary-source verification before quoting to judges, same standard the team already applies to the rainfall threshold.
- **Two real bugs were caught and fixed** in the raster pipeline (a silent nodata-fill bug, and a grid-misalignment bug when combining rasters built at different native resolutions) — see `PROVENANCE.md` for what they were and how they were caught, in case the same class of bug shows up in new layers.
- **Re-run scripts, don't hand-edit outputs.** Every processed file is reproducible from `data/raw/` — if something looks wrong, fix the script and re-run rather than patching the CSV/GeoTIFF directly.
- **Open-Meteo rate-limits hard on sustained batch traffic.** `13_compute_rainfall_erosivity.py` caches every API response to `data/interim/rainfall_cache/` specifically so this doesn't need re-fetching; don't delete that folder unless you intend to re-hit the API from scratch.
