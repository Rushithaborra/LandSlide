# Feature Suitability Report — Sikkim Road-Corridor Susceptibility Model

Generated 2026-09-01. Audit-only: `scripts/ml/audit_collected_data.py` (read
no resampling/reprojection performed, no `training_dataset.csv` changes).
No model trained. Stopping for review, per instruction.

## Part 1 — Data quality audit (per dataset)

All bounds/CRS/resolution/missing-value numbers below are from actually
running the audit script against the pilot AOI (the real bounding box of
our 777 GSI points: 88.077–88.840°E, 27.083–27.749°N), not assumed.

| Dataset | CRS | Resolution | Covers pilot AOI? | Missing/NoData in pilot window | Notes |
|---|---|---|---|---|---|
| DEM (native) | EPSG:4326 | ~30m (0.000278°) | Yes | 0% | Elevation 211.5–8564.3m, mean 2765m |
| DEM (reprojected) | EPSG:32645 | ~29.2m | Yes | 0% | Consistent with native (2783.8m mean — small diff from bilinear resampling, expected). **Caught a bug writing this audit**: my first version compared this raster's meter-valued bounds directly against the pilot AOI's degree values without reprojecting first, and falsely reported zero coverage — fixed before this table was written. |
| ESA WorldCover | EPSG:4326 | 10m | Yes | 0% | Values 10–100, confirmed categorical class codes (not continuous) |
| SoilGrids clay/sand/silt/soc | EPSG:4326 | ~250m | Yes (clipped exactly at download) | 0% | **Raw values are scaled integers, not physical units** — verified against ISRIC's own conversion table (see Part 2) |
| WorldPop | EPSG:4326 | 1km | Yes | 5.9% (nodata=-99999, plausible masked non-landmass cells) | Whole-India file, not yet clipped to Sikkim boundary |
| Roads / villages / buildings / hospitals-schools / infrastructure (OSM) | EPSG:4326 | Vector | Yes | 0 null geometries | 29–54% of fetched features fall inside the tight pilot bbox — expected, since we deliberately fetched a larger margin |
| GLiM lithology | EPSG:4326 | **0.5° (~56km)** | Technically yes | n/a | Pilot AOI is 0.76° × 0.67° — only **1.53 × 1.33 grid cells** across the entire corridor. See Part 2. |

No dataset had unexpected NaN/Inf values. No unnecessary resampling or
reprojection was performed — the DEM reprojection (EPSG:4326→32645) is the
one required transform, already documented in `README.md` from the original
dataset-construction pass.

## Part 2 — Candidate features

### From the DEM (already implemented, in `training_dataset.csv`)
| Feature | Encoding | Preprocessing |
|---|---|---|
| elevation | continuous, meters | none beyond the DEM reprojection already done |
| slope | continuous, degrees | xarray-spatial (Horn's method) on reprojected DEM |
| aspect | continuous, degrees (0–360) | same |
| curvature | continuous | same |
| distance_to_drainage | continuous, meters | pysheds D8 flow accumulation + distance transform (numpy shim documented) |

### From land cover (NOT yet extracted into the training dataset)
**Design**: sample the ESA WorldCover class at each point's exact lat/lon (10m resolution — finer than the DEM's 30m, simple nearest-pixel lookup, no reprojection needed since points are already in EPSG:4326). One-hot encode the classes actually present in the corridor. From the earlier spot-check: Tree cover (10), Grassland (30), Cropland (40), Built-up (50), Bare/sparse vegetation (60), Water (80) — 6 realistic categories, not all 11 global WorldCover classes.

### From SoilGrids (NOT yet extracted)
**Required preprocessing, verified against ISRIC's own documentation** (not assumed):

| Property | Mapped unit (raw) | Conversion | Conventional unit |
|---|---|---|---|
| clay | g/kg | ÷10 | % |
| sand | g/kg | ÷10 | % |
| silt | g/kg | ÷10 | % |
| soc | dg/kg | ÷10 | **g/kg** (not %, unlike the other three) |

Our raw ranges (clay 0–371, sand 0–662, silt 0–454, soc 0–1252) convert to clay 0–37.1%, sand 0–66.2%, silt 0–45.4%, soc 0–125.2 g/kg — all physically plausible for Himalayan forest soils. This scaling must be applied before these values mean anything; they are currently unscaled integers in the raw files.

### From geology/lithology
**Assessed and rejected on resolution grounds**, per instruction. GLiM's 0.5° grid covers the *entire* pilot corridor with roughly 2 cells — every point in our 777+777 dataset would receive nearly the same one or two lithology values. That's not a predictor, it's a near-constant. Documented as unavailable at usable resolution, not forced in.

## Part 3 — Feature suitability table

| feature | source | resolution | preprocessing | candidate role | leakage risk | recommendation |
|---|---|---|---|---|---|---|
| elevation | Copernicus GLO-30 | ~30m | none (done) | susceptibility predictor | none | **USE** |
| slope | Copernicus GLO-30 | ~30m | none (done) | susceptibility predictor | none | **USE** — strongest verified signal (33.2° vs 28.4° mean, pos vs neg) |
| curvature | Copernicus GLO-30 | ~30m | none (done) | susceptibility predictor | none | **USE** — mechanistically grounded (water convergence), real observed shift |
| distance_to_drainage | Copernicus GLO-30 (derived) | ~30m | none (done) | susceptibility predictor | none | **USE** — standard GSI factor, though marginal signal was weak in the earlier review (319.7 vs 328.3m) — kept for multivariate value and established methodology |
| aspect | Copernicus GLO-30 | ~30m | none (done) | susceptibility predictor | none | **OPTIONAL** — real but weakest observed signal (179.7° vs 176.1°, heavy overlap); scientifically defensible but not essential for a first minimal model |
| land_cover_class | ESA WorldCover | 10m | one-hot encode 6 classes; extraction not yet built | susceptibility predictor | none (2021 snapshot, static, pre-dates all training events) | **USE** — cheap, well-justified (vegetation/root reinforcement affects stability), extraction is a small addition to the existing point-sampling pipeline |
| clay / sand / silt | ISRIC SoilGrids | 250m | ÷10 to %; extraction not yet built | susceptibility predictor | none | **OPTIONAL** — real relevance (soil texture affects permeability/cohesion) but the three are highly collinear by construction (sum to ~100%); adds 3 correlated dimensions for a first model |
| soil_organic_carbon | ISRIC SoilGrids | 250m | ÷10 to g/kg; extraction not yet built | susceptibility predictor | none | **OPTIONAL** — plausible secondary factor, not core |
| lithology | GLiM | 0.5° (~56km) | n/a | — | — | **REJECT** — resolution unusable at pilot scale (quantified: ~2 grid cells cover the whole corridor) |
| roads | OpenStreetMap | vector | none | impact/prioritization | **HIGH if used as a predictor** — distance-to-road tracks the GSI survey bias we measured (96.1% within 100m), not real susceptibility | **GIS-ONLY** — explicitly excluded as a predictor per your instruction |
| villages | OpenStreetMap | vector, 341 points | none | exposure/impact | low as a GIS layer; would be reverse-causality risk if used as a susceptibility predictor (settlements may avoid known-unsafe slopes) | **GIS-ONLY** |
| buildings | OpenStreetMap | vector, 289,607 centroids | none | exposure density | same reverse-causality concern as villages | **GIS-ONLY** |
| hospitals/schools | OpenStreetMap | vector, 138 points | none | response prioritization | n/a, not a terrain factor | **GIS-ONLY** |
| population | WorldPop | 1km | needs clipping to Sikkim boundary | exposure weighting | reverse-causality risk (population avoids unsafe terrain historically) — no strong scientific case to use as a susceptibility driver | **GIS-ONLY** |
| latitude/longitude | — | — | — | — | direct memorization risk with only 1554 rows | **REJECT** (hard exclusion, unchanged from dataset-construction phase) |
| distance_to_road | OSM (derived) | — | — | — | encodes the survey-bias artifact directly | **REJECT** (hard exclusion) |
| Material_Involved, Movement_Type, Slide_Name, NH_SH_Location, History | GSI inventory | — | — | — | **post-event outcome fields** | **REJECT** (hard exclusion) |
| rainfall (any) | Open-Meteo | — | — | — | breaks the two-layer architecture | **REJECT** for this model — stays in the separate dynamic rule layer and the 68-event case study |
| existing susceptibility map | (not collected as event data) | — | — | — | circular — using a susceptibility output as a susceptibility label | **REJECT** — never used, confirmed again |

## Part 4 — Proposed minimal feature set for the first model

**elevation, slope, curvature, distance_to_drainage, land_cover_class** — 5 features (4 already in `training_dataset.csv`; land_cover_class needs one small extraction addition before training).

Why each earns its place:
- **slope** — the literature's strongest predictor, and the one feature with a clear, already-verified signal in our own data (33.2° vs 28.4°)
- **curvature** — mechanistically distinct from slope (captures water convergence, not steepness), real observed shift, standard GSI factor
- **elevation** — base terrain context, standard GSI factor, cheap
- **distance_to_drainage** — standard GSI factor (undercutting/saturation proxy); kept despite weak marginal signal because it's mechanistically independent of the other three and may contribute in combination even where it doesn't separate classes alone
- **land_cover_class** — the one non-DEM addition that clears the bar: real scientific justification (vegetation/root reinforcement), fine resolution (10m, finer than everything else), zero leakage risk, and cheap to extract with the pipeline we already have

**Deliberately left out of the minimal set** (kept as OPTIONAL for a later, expanded model): aspect (weakest observed signal), and the four SoilGrids properties (real relevance, but correlated with each other and not yet extracted — better suited to a v2 model than the leanest defensible first pass).

Lithology, roads, villages, buildings, hospitals/schools, and population are excluded from the susceptibility model entirely, per your instruction — they remain candidates for the separate GIS impact/prioritization layer.

---
**Stopping here, as instructed.** No training, no changes to `training_dataset.csv`. If you approve this minimal set, the next step would be building the land-cover extraction (small addition to the existing point-sampling code) and re-running `build_training_dataset.py` before any model touches the data.
