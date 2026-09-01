# Datasets used in this project

All sources below are public and free — no account or API key needed for
any of them. Team members can either (a) pull the small derived files
already committed in `data/` after cloning this repo, or (b) hit the same
links directly and regenerate everything from scratch via the scripts
listed. No shared git remote is set up yet (`git remote -v` is empty) — if
you want everyone on the exact same repo, someone needs to push this to a
GitHub org/repo and share that URL; until then, this doc + direct links are
the way to stay in sync.

## 1. Landslide inventory (positive samples)

**GSI National Landslide Forecasting Centre (NLFC) — "Landslide Inventory (Field Validated)"**
- Portal: https://bhusanket.gsi.gov.in/
- Direct file (what we actually parsed): https://bhusanket.gsi.gov.in/pics/landslide_report.pdf
- Format: **904-page PDF, tabular** (not a CSV/shapefile — the portal's "Download Data" button just opens this PDF). We extracted it with `pdfplumber` into a real table.
- Content: 36,072 records nationwide (Sl.No, Slide_No, State, District, Slide_Name, NH_SH_Location, Latitude, Longitude, Material_Involved, Movement_Type, History/date)
- **Already extracted for you**: [`data/raw/gsi_sikkim_landslides.csv`](../data/raw/gsi_sikkim_landslides.csv) — the 777-record Sikkim subset, committed in this repo. No need to re-parse the 904-page PDF yourself.
- License/access: public government portal, no login, no stated usage restriction found on the site.
- **Known limitation**: 96.1% of Sikkim records are within 100m of a mapped road — a field-survey artifact (see `README.md` "ML data pipeline" section). Scope your claims accordingly.

## 2. Elevation / terrain (DEM)

**Copernicus GLO-30 Digital Elevation Model**
- Registry page: https://registry.opendata.aws/copernicus-dem/
- Public S3 bucket (no key, plain HTTPS): `https://copernicus-dem-30m.s3.amazonaws.com/`
- Tile used for the Sikkim pilot: `Copernicus_DSM_COG_10_N27_00_E088_00_DEM` — direct download:
  https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N27_00_E088_00_DEM/Copernicus_DSM_COG_10_N27_00_E088_00_DEM.tif
- Format: Cloud-Optimized GeoTIFF, ~30m resolution, native CRS EPSG:4326 (must reproject to EPSG:32645/UTM 45N before computing slope/aspect — see `scripts/ml/fetch_dem.py`)
- Coverage: this single tile (27–28°N, 88–89°E) covers all 777 Sikkim inventory points — no mosaicking needed for this pilot
- License: Copernicus DEM is free and open (see registry page for full terms)
- **Regenerate**: `python -m scripts.ml.fetch_dem` (downloads + reprojects automatically)

*(Evaluated but not used: OpenTopography's Global DEM API — requires a free account/API key, which nobody on the team has created yet. Copernicus-on-AWS needed no such step.)*

## 3. Road network

**OpenStreetMap, via the Overpass API**
- Query endpoint: https://overpass-api.de/api/interpreter
- Interactive query builder (useful for exploring by hand): https://overpass-turbo.eu/
- Raw map browser: https://www.openstreetmap.org/
- Format: JSON (`out geom` Overpass query), converted to GeoJSON in our pipeline
- Bounding box used: 26.9–28.2°N, 87.9–89.0°E (Sikkim + small margin)
- License: **ODbL (OpenStreetMap's Open Database License)** — attribution required if this ends up in any public-facing map/dashboard
- **Regenerate**: `python -m scripts.ml.fetch_osm_roads`
- Note: the public Overpass server occasionally times out under load (hit this once this session) — just retry, or use a mirror like https://overpass.kumi.systems/api/interpreter

## 4. Rainfall

**Open-Meteo** — https://open-meteo.com/ (docs: https://open-meteo.com/en/docs)
- Forecast + recent-past endpoint (used by the backend's live alert pipeline): https://api.open-meteo.com/v1/forecast
- Historical archive endpoint (used for the rainfall case study, back to 2011+ confirmed, ERA5-based reanalysis, ~10km grid): https://archive-api.open-meteo.com/v1/archive
- No key, no login, generous free-tier rate limits
- License: CC BY 4.0 (attribution required)
- **Honesty note for the team/judges**: this is our fallback, not the deck's stated primary source. We checked 6 official Government-of-Sikkim/IMD rainfall sources this session — all either unreachable (IMD Sikkim, ENVIS Sikkim — DNS failures) or had no public rainfall dataset (SSDMA, Sikkim Open Government Data portal). Don't imply IMD data is live; it isn't.

## 5. Rainfall intensity-duration threshold (not a dataset — a literature value)

- Harilal, G.T., Madhu, D., Ramesh, M.V. & Pullarkatt, D. (2019). "Towards establishing rainfall thresholds for a real-time landslide early warning system in Sikkim, India." *Landslides*, 16(12), 2395–2408.
- DOI: https://doi.org/10.1007/s10346-019-01244-1
- Configured in `.env` / `app/config.py` (`RainfallThresholdConfig`) — **flagged `verified_against_primary_text: false`**, since the paper is paywalled and we only confirmed the coefficients via secondary summaries + Semantic Scholar metadata (https://api.semanticscholar.org/graph/v1/paper/DOI:10.1007/s10346-019-01244-1). If anyone on the team has journal access, verifying this directly against the primary text would be worth doing before quoting it to judges.

## Checked, evaluated, and explicitly NOT used

For the record, so nobody re-spends time on these:

| Source | Why not used |
|---|---|
| `Itanagar Yupia Road Susceptibility Map.pdf` (local file) | Arunachal Pradesh, not Sikkim; a rendered susceptibility map (raster), not extractable point/event data |
| `Sikkim_Landslide_2016.pdf` (NRSC "So Bhir"/Mantam report, local file) | Real event report, but the exact same event is already in the GSI inventory (cross-validated coordinates match) — adds no new data point |
| IMD Sikkim (`imdsikkim.gov.in`) | Domain unreachable (DNS failure) |
| ENVIS Sikkim (`sikenvis.nic.in`) | Domain unreachable (DNS failure) |
| Sikkim SDMA (`ssdma.nic.in`) | Reachable, but no public data portal — awareness/emergency-contacts site only |
| Sikkim Open Government Data (`sikkim.data.gov.in`) | Reachable, 355 catalogs, none are rainfall/meteorology |
| OpenTopography Global DEM API | Requires an API key/account we haven't created |

## Regenerating everything from scratch

```bash
pip install -r requirements.txt
python -m scripts.ml.fetch_dem            # DEM tile -> data/raw/dem/, data/processed/
python -m scripts.ml.fetch_osm_roads      # roads -> data/raw/sikkim_roads.geojson
python -m scripts.ml.build_negative_samples
python -m scripts.ml.build_training_dataset
python -m scripts.ml.rainfall_threshold_case_study
```

`data/raw/gsi_sikkim_landslides.csv` is already committed — there's no script to regenerate it from the 904-page PDF (that extraction takes ~5 minutes and isn't automated yet); if you need to redo it, ask and I'll add `scripts/ml/fetch_gsi_inventory.py`.
