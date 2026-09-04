# Data handoff format — send this to Person A (Data/GIS lead)

To avoid a Day-2 scramble merging four separate raster files by hand, please
hand off ONE CSV with these exact columns, one row per point:

## Required (blocks training — priority)

| Column | Type | Example | Notes |
|---|---|---|---|
| `sample_id` | string/int | "LS-014" | unique id per row |
| `lat` | float | 27.5412 | WGS84 (EPSG:4326) |
| `lon` | float | 88.5122 | WGS84 (EPSG:4326) |
| `elevation` | float | 1820.0 | raw DEM elevation (meters), not just slope/aspect |
| `slope_deg` | float | 34.2 | degrees, from DEM |
| `aspect_deg` | float | 187.5 | degrees (0-360), from DEM |
| `drainage_density` | float | 0.68 | normalized 0-1 if possible |
| `lithology` | string | "gneiss" | category name, not a code number |
| `landuse` | string | "forest" | category name, not a code number |
| `mean_annual_rainfall_mm` | float | 3150.0 | from Open-Meteo historical, per-point or nearest station — the training pipeline requires this column, it's not optional |
| `label` | int | 1 | **1 = landslide occurred here (from GSI inventory) ONLY.** Do NOT generate 0-rows — negative sampling is my job, not yours (see negative_sampling.py + checklist item #12). Sending only label=1 rows is correct. |

## Nice to have — don't block on these if time is short

| Column | Notes |
|---|---|
| `district` | for sanity-checking + pitch deck data quality slide |
| `date` | landslide event date, if GSI inventory has it |
| `landslide_type` | e.g. debris flow, rockfall, if available |
| `area_m2` | if available |
| `curvature`, `distance_to_drainage`, `terrain_ruggedness` | optional-tier factors from the data checklist |
| source / CRS / resolution / processing notes per layer | useful documentation, not required to train |

## Also send separately (not part of the CSV)

The Sikkim boundary polygon (GADM or Survey of India) as a shapefile/GeoJSON
— needed to generate negative samples inside the correct area (see
negative_sampling.py).

## Explicitly NOT your job

Generating negative (label=0) samples. That requires buffering around known
landslide points, which only makes sense once I have both your landslide
coordinates and the boundary polygon — I'll do that myself once both arrive.
If you see this requested elsewhere (e.g. a generic checklist), it doesn't
apply here — send label=1 rows only.

Practice file already built at `data/fake_landslide_data.csv` using exactly
this schema — if your real export matches these column names, I can swap
it into `train_model.py` in under a minute.
