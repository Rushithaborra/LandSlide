"""Generates data/raw/MANIFEST.csv -- the provenance record for every
dataset in the Data Source Checklist audit (2026-09-01). Static facts
gathered through direct verification (curl/browser checks, real downloads)
during that audit -- this script just assembles them into one structured
file rather than re-deriving them, since re-verifying ~20 external sources
programmatically each run would need bespoke login/redirect handling per
source that isn't worth building for a one-off provenance record."""
import csv
import pathlib

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "data" / "raw" / "MANIFEST.csv"

DOWNLOAD_DATE = "2026-09-01"

FIELDS = [
    "dataset_name", "checklist_item", "source_url", "download_date", "file_format",
    "spatial_coverage", "temporal_coverage", "resolution", "license",
    "account_required", "access_status", "local_path", "intended_possible_use",
    "known_limitations", "leakage_concerns",
]

ROWS = [
    dict(
        dataset_name="GSI NLFC Landslide Inventory (Field Validated) -- Sikkim subset",
        checklist_item="1, 10",
        source_url="https://bhusanket.gsi.gov.in/pics/landslide_report.pdf",
        download_date="2026-08-31 (prior session)", file_format="PDF table, extracted to CSV",
        spatial_coverage="Sikkim state (777 records; national file has 36,072)",
        temporal_coverage="Event dates where recorded: 2009-2025, 15.6% of records have any date",
        resolution="Point (lat/lon), 6 decimal places where precise",
        license="Public GSI government portal, no stated restriction",
        account_required="No", access_status="ACCESSIBLE, DOWNLOADED",
        local_path="data/raw/gsi_sikkim_landslides.csv",
        intended_possible_use="Positive samples for susceptibility model",
        known_limitations="96.1% within 100m of a mapped road (survey bias, verified); "
                           "71.4% missing Slide_Name; only 8.8% have a single clean date",
        leakage_concerns="Material_Involved/Movement_Type/Slide_Name/NH_SH_Location are "
                          "POST-EVENT descriptive fields -- already excluded from training_dataset.csv",
    ),
    dict(
        dataset_name="Sikkim administrative boundary (via GADM India states)",
        checklist_item="2",
        source_url="https://geodata.ucdavis.edu/gadm/gadm4.1/json/gadm41_IND_1.json.zip",
        download_date=DOWNLOAD_DATE, file_format="GeoJSON (MultiPolygon)",
        spatial_coverage="All India states; Sikkim extracted separately",
        temporal_coverage="Static (administrative boundary, GADM v4.1)",
        resolution="Vector polygon, state-level detail",
        license="GADM: free for non-commercial/academic use, redistribution restricted -- see gadm.org/license.html",
        account_required="No", access_status="ACCESSIBLE, DOWNLOADED",
        local_path="data/raw/boundary/gadm41_IND_1.json.zip; "
                    "data/raw/boundary/sikkim_boundary.geojson (Sikkim-only extract)",
        intended_possible_use="Clipping/context for maps, dashboards, defining full-state extent",
        known_limitations="Not the official Survey of India boundary (SoI site unreachable from this "
                           "environment); GADM's own license restricts commercial redistribution",
        leakage_concerns="None",
    ),
    dict(
        dataset_name="Survey of India official boundary",
        checklist_item="2 (alternate)",
        source_url="https://soi.gov.in", download_date="", file_format="", spatial_coverage="",
        temporal_coverage="", resolution="", license="",
        account_required="Unknown", access_status="NOT ACCESSIBLE -- domain unreachable from this "
                                                    "environment (curl and browser both failed)",
        local_path="", intended_possible_use="More authoritative boundary than GADM",
        known_limitations="Could not verify login requirement since site is unreachable",
        leakage_concerns="",
    ),
    dict(
        dataset_name="Copernicus GLO-30 DEM -- Sikkim tile",
        checklist_item="3",
        source_url="https://copernicus-dem-30m.s3.amazonaws.com/Copernicus_DSM_COG_10_N27_00_E088_00_DEM/"
                    "Copernicus_DSM_COG_10_N27_00_E088_00_DEM.tif",
        download_date="2026-08-31 (prior session)", file_format="Cloud-Optimized GeoTIFF",
        spatial_coverage="27-28N, 88-89E (single tile, covers all 777 Sikkim points)",
        temporal_coverage="Static (2011-2015 radar acquisition composite)",
        resolution="~30m (10 arc-sec)", license="Copernicus DEM: free and open, see registry.opendata.aws/copernicus-dem",
        account_required="No", access_status="ACCESSIBLE, DOWNLOADED",
        local_path="data/raw/dem/N27_00_E088_00.tif",
        intended_possible_use="Elevation + source for all derived terrain layers",
        known_limitations="Native CRS EPSG:4326 -- must reproject to UTM 45N before deriving slope/aspect "
                           "(verified: unreprojected slope is wrong, ~90deg everywhere)",
        leakage_concerns="None -- static terrain, unrelated to event timing",
    ),
    dict(
        dataset_name="OpenTopography Global DEM API (alternate DEM source)",
        checklist_item="3 (alternate)",
        source_url="https://portal.opentopography.org/API/globaldem", download_date="", file_format="",
        spatial_coverage="", temporal_coverage="", resolution="", license="",
        account_required="Yes (verified: 401 without a key)",
        access_status="NOT ACCESSIBLE without an API key/account -- not pursued, Copernicus-on-AWS covers this need",
        local_path="", intended_possible_use="Would have been redundant with the AWS source already downloaded",
        known_limitations="", leakage_concerns="",
    ),
    dict(
        dataset_name="Slope / Aspect / Curvature / Drainage density / Distance-to-drainage",
        checklist_item="4, 5, 6, 13, 14",
        source_url="DERIVED from Copernicus GLO-30 DEM (row above) -- not an independent external dataset",
        download_date="n/a (derived)", file_format="In-memory numpy arrays via scripts/ml/extract_terrain_features.py",
        spatial_coverage="Same as source DEM", temporal_coverage="Same as source DEM",
        resolution="~30m (same as source DEM)", license="Inherits source DEM license",
        account_required="No", access_status="DERIVATION PIPELINE BUILT AND VERIFIED",
        local_path="scripts/ml/extract_terrain_features.py computes these on demand from "
                    "data/processed/dem_sikkim_utm45n.tif",
        intended_possible_use="Core terrain features for the susceptibility model",
        known_limitations="Slope/aspect/curvature via xarray-spatial (Horn's method); "
                           "distance-to-drainage via pysheds D8 flow accumulation with a documented "
                           "numpy.in1d->numpy.isin compatibility shim; drainage DENSITY specifically "
                           "(distinct from distance-to-drainage) not yet computed, same pipeline could add it",
        leakage_concerns="None -- static terrain",
    ),
    dict(
        dataset_name="Lithology/geology -- GSI Bhukosh",
        checklist_item="7",
        source_url="https://bhukosh.gsi.gov.in", download_date="", file_format="", spatial_coverage="",
        temporal_coverage="", resolution="", license="",
        account_required="Yes, per checklist (free registration)",
        access_status="NOT ACCESSIBLE -- domain unreachable from this environment (curl and browser "
                       "both failed; could not even reach the login page to confirm the registration claim)",
        local_path="", intended_possible_use="Lithology/rock-type feature for susceptibility model",
        known_limitations="Also tried NGDR (ngdr.mines.gov.in) as the checklist's suggested alternate -- "
                           "also unreachable from this environment",
        leakage_concerns="",
    ),
    dict(
        dataset_name="Global Lithological Map Database (GLiM) v1.0 -- gridded",
        checklist_item="7 (alternate found)",
        source_url="https://doi.pangaea.de/10.1594/PANGAEA.788537 "
                    "(file: https://hdl.handle.net/10013/epic.39939.d001)",
        download_date=DOWNLOAD_DATE, file_format="ASCII grid (.asc) + class legend (.txt)",
        spatial_coverage="Global", temporal_coverage="Static (published 2012)",
        resolution="0.5 degree (~55km) -- MUCH coarser than project needs",
        license="CC-BY 3.0", account_required="No", access_status="ACCESSIBLE, DOWNLOADED",
        local_path="data/raw/lithology/GLiM_0.5deg_gridded.zip",
        intended_possible_use="NOT practically usable for point/road-corridor-level susceptibility -- "
                               "Sikkim (~1.2deg x 0.7deg) would be covered by only 1-2 grid cells. "
                               "Kept only for completeness/documentation.",
        known_limitations="Underlying GLiM vector dataset has 1,235,400 polygons at much finer "
                           "resolution but is hosted separately (CCGM.org per literature) -- not "
                           "located/verified in this pass; would need a follow-up if lithology is "
                           "judged worth pursuing despite GSI Bhukosh being unreachable",
        leakage_concerns="None",
    ),
    dict(
        dataset_name="Land cover -- ESA WorldCover 10m 2021",
        checklist_item="8",
        source_url="https://esa-worldcover.s3.amazonaws.com/v200/2021/map/"
                    "ESA_WorldCover_10m_2021_v200_N27E087_Map.tif",
        download_date=DOWNLOAD_DATE, file_format="Cloud-Optimized GeoTIFF",
        spatial_coverage="27-30N, 87-90E (3x3 deg tile, covers all of Sikkim)",
        temporal_coverage="2021 snapshot", resolution="10m",
        license="CC-BY 4.0, cite Zanaga et al. 2021 (DOI 10.5281/zenodo.5571936)",
        account_required="No", access_status="ACCESSIBLE, DOWNLOADED",
        local_path="data/raw/landcover/ESA_WorldCover_10m_2021_v200_N27E087_Map.tif",
        intended_possible_use="Land-use/land-cover feature (forest/cropland/built-up/water classes)",
        known_limitations="2021 snapshot only -- not real-time; verified real class distribution over "
                           "Sikkim sub-window (predominantly tree cover, plausible for the terrain)",
        leakage_concerns="None -- static, pre-dates all training events",
    ),
    dict(
        dataset_name="Bhuvan LULC (alternate land-cover source)",
        checklist_item="8 (alternate)",
        source_url="https://bhuvan.nrsc.gov.in", download_date="", file_format="", spatial_coverage="",
        temporal_coverage="", resolution="", license="",
        account_required="Unclear -- portal is an interactive map viewer, not a bulk-download page",
        access_status="PORTAL REACHABLE, but no direct bulk-download endpoint found in this pass -- "
                       "not pursued further since ESA WorldCover already provides a working substitute",
        local_path="", intended_possible_use="India-specific, GSI-methodology-aligned LULC",
        known_limitations="Would need further UI navigation (possibly account-gated for thematic layers) "
                           "to locate a direct download",
        leakage_concerns="",
    ),
    dict(
        dataset_name="Rainfall -- Open-Meteo (forecast + historical archive)",
        checklist_item="9",
        source_url="https://api.open-meteo.com/v1/forecast ; https://archive-api.open-meteo.com/v1/archive",
        download_date="verified across prior sessions, live API (not a static file)",
        file_format="JSON API", spatial_coverage="Point query by lat/lon, any location",
        temporal_coverage="Historical archive confirmed back to at least 2011 (ERA5-based, extends to 1940)",
        resolution="Hourly/daily, ~9-11km grid (ERA5 reanalysis)",
        license="CC-BY 4.0", account_required="No", access_status="ACCESSIBLE, LIVE (not a downloaded file)",
        local_path="Used live by app/services/open_meteo.py and scripts/ml/rainfall_threshold_case_study.py",
        intended_possible_use="Dynamic rainfall-threshold alert layer; rainfall case study for the 68 dated events",
        known_limitations="NOT the deck's stated primary source (IMD) -- IMD Sikkim and ENVIS Sikkim "
                           "both confirmed unreachable (DNS failure) in a prior session's audit",
        leakage_concerns="Kept entirely separate from the static susceptibility training_dataset.csv, "
                          "per project's two-layer architecture rule",
    ),
    dict(
        dataset_name="Negative/non-landslide samples",
        checklist_item="12",
        source_url="Not a downloadable dataset -- generated, per checklist's own note",
        download_date="", file_format="", spatial_coverage="", temporal_coverage="", resolution="",
        license="", account_required="No",
        access_status="TO BE GENERATED -- already built (scripts/ml/build_negative_samples.py), "
                       "not re-touched in this collection pass per instruction",
        local_path="data/processed/negative_samples.csv",
        intended_possible_use="Negative class for susceptibility model",
        known_limitations="Road-corridor sampling method, documented separately",
        leakage_concerns="None by construction (excluded from positive buffer)",
    ),
    dict(
        dataset_name="SoilGrids -- clay, sand, silt, soil organic carbon (0-5cm)",
        checklist_item="15-18",
        source_url="https://maps.isric.org/mapserv (WCS 2.0.1, COVERAGEID=<property>_0-5cm_mean)",
        download_date=DOWNLOAD_DATE, file_format="GeoTIFF (WCS GetCoverage response)",
        spatial_coverage="27-28.2N, 88-88.9E (clipped exactly to Sikkim pilot bbox)",
        temporal_coverage="Static (SoilGrids 2.0, released 2020)",
        resolution="250m", license="CC-BY 4.0",
        account_required="No (anonymous WebDAV/WCS access, verified)",
        access_status="ACCESSIBLE, DOWNLOADED (all 4 properties)",
        local_path="data/raw/soilgrids/{clay,sand,silt,soc}_0-5cm_mean_sikkim.tif",
        intended_possible_use="Soil composition features -- possible susceptibility predictors",
        known_limitations="First download attempt used an incorrectly-guessed Homolosine coordinate "
                           "subset and silently returned data for the WRONG region (~95-97E, not "
                           "Sikkim) -- caught by verifying bounds before accepting the file, discarded, "
                           "redone correctly with a Lat/Long subset instead",
        leakage_concerns="None -- static soil property",
    ),
    dict(
        dataset_name="SMAP soil moisture",
        checklist_item="19",
        source_url="https://earthdata.nasa.gov", download_date="", file_format="", spatial_coverage="",
        temporal_coverage="", resolution="", license="",
        account_required="Yes -- NASA Earthdata login required",
        access_status="NOT ACCESSIBLE -- requires an account, which cannot be created on the team's "
                       "behalf. Checked for a no-login alternate (ESA CCI Soil Moisture via CEDA) -- "
                       "also appears to require registration.",
        local_path="", intended_possible_use="Soil moisture proxy (checklist's own note: first item to cut if time-constrained)",
        known_limitations="", leakage_concerns="",
    ),
    dict(
        dataset_name="Sentinel-1 (radar)",
        checklist_item="20",
        source_url="Verified accessible WITHOUT an account via Microsoft Planetary Computer STAC API: "
                    "https://planetarycomputer.microsoft.com/api/stac/v1/search "
                    "(collection: sentinel-1-rtc) -- real scene found covering Sikkim "
                    "(S1D_IW_GRDH_1SDV_20260830T120500...). Copernicus Data Space (the checklist's "
                    "suggested source) does require registration and was not used.",
        download_date=DOWNLOAD_DATE + " (verified access only)", file_format="Cloud-Optimized GeoTIFF (per-scene)",
        spatial_coverage="Per-scene, global catalog, queryable by Sikkim bbox",
        temporal_coverage="Ongoing (Sentinel-1 mission)", resolution="~10-20m",
        license="Copernicus Sentinel data (free, open) + Microsoft's Planetary Computer terms",
        account_required="No (via Planetary Computer)",
        access_status="ACCESSIBLE (verified query success), NOT YET DOWNLOADED",
        local_path="", intended_possible_use="Soil moisture proxy / recent-disturbance detection",
        known_limitations="A full scene/mosaic download and cloud/processing pipeline is a larger task "
                           "than this collection pass covered -- flagged as follow-up work, not done",
        leakage_concerns="Would need care: only use scenes dated BEFORE each event if ever used as a "
                          "per-event feature",
    ),
    dict(
        dataset_name="Sentinel-2 (optical)",
        checklist_item="21",
        source_url="Verified accessible WITHOUT an account via Microsoft Planetary Computer STAC API "
                    "(collection: sentinel-2-l2a) -- real scene found covering Sikkim "
                    "(S2B_MSIL2A_20241229T044119...)",
        download_date=DOWNLOAD_DATE + " (verified access only)", file_format="Cloud-Optimized GeoTIFF (per-scene, per-band)",
        spatial_coverage="Per-scene, global catalog, queryable by Sikkim bbox",
        temporal_coverage="Ongoing (Sentinel-2 mission)", resolution="10-20m depending on band",
        license="Copernicus Sentinel data (free, open) + Microsoft's Planetary Computer terms",
        account_required="No (via Planetary Computer)",
        access_status="ACCESSIBLE (verified query success), NOT YET DOWNLOADED",
        local_path="", intended_possible_use="LULC substitute/supplement to ESA WorldCover, vegetation index features",
        known_limitations="Same as Sentinel-1 -- full download/mosaic not yet done, flagged as follow-up",
        leakage_concerns="Same caution as Sentinel-1 if ever used per-event",
    ),
    dict(
        dataset_name="Roads -- OpenStreetMap",
        checklist_item="22",
        source_url="https://overpass-api.de/api/interpreter (way[highway], bbox 26.9,87.9,28.2,89.0)",
        download_date="2026-08-31 (prior session)", file_format="GeoJSON",
        spatial_coverage="Sikkim + margin bbox", temporal_coverage="OSM snapshot, live-queried",
        resolution="Vector line geometry", license="ODbL -- attribution required if published",
        account_required="No", access_status="ACCESSIBLE, DOWNLOADED",
        local_path="data/raw/sikkim_roads.geojson",
        intended_possible_use="Road-corridor sampling for both the susceptibility dataset and "
                               "road-connectivity risk framing",
        known_limitations="Used the query API directly rather than the HOT Export Tool the checklist "
                           "suggested -- same underlying OSM data, equivalent result",
        leakage_concerns="None",
    ),
    dict(
        dataset_name="Villages/hamlets -- OpenStreetMap",
        checklist_item="23",
        source_url="https://overpass-api.de/api/interpreter (node[place=village|hamlet])",
        download_date=DOWNLOAD_DATE, file_format="GeoJSON (points)",
        spatial_coverage="Sikkim + margin bbox", temporal_coverage="OSM snapshot, live-queried",
        resolution="Point", license="ODbL", account_required="No",
        access_status="ACCESSIBLE, DOWNLOADED (341 points)",
        local_path="data/raw/osm_extras/villages_hamlets.geojson",
        intended_possible_use="Impact/exposure analysis -- which villages are near high-risk zones",
        known_limitations="OSM village/hamlet tagging coverage in rural Sikkim is not guaranteed complete",
        leakage_concerns="None",
    ),
    dict(
        dataset_name="Buildings -- OpenStreetMap (centroids)",
        checklist_item="24",
        source_url="https://overpass-api.de/api/interpreter (way/node[building])",
        download_date=DOWNLOAD_DATE, file_format="GeoJSON (points -- centroids, not footprint polygons)",
        spatial_coverage="Sikkim + margin bbox", temporal_coverage="OSM snapshot, live-queried",
        resolution="Point (building centroid)", license="ODbL", account_required="No",
        access_status="ACCESSIBLE, DOWNLOADED (289,607 centroids)",
        local_path="data/raw/osm_extras/buildings_centroids.geojson",
        intended_possible_use="Impact/exposure density near risk zones",
        known_limitations="Centroids only, not full footprint polygons -- kept the payload proportionate "
                           "given 289,607 features; full polygons could be re-fetched later if needed. "
                           "Rural OSM building coverage in NER is a known, honest limitation "
                           "(per the checklist's own note) -- flag this if judges ask.",
        leakage_concerns="None",
    ),
    dict(
        dataset_name="Hospitals/schools -- OpenStreetMap",
        checklist_item="26",
        source_url="https://overpass-api.de/api/interpreter (amenity=hospital|school)",
        download_date=DOWNLOAD_DATE, file_format="GeoJSON (points)",
        spatial_coverage="Sikkim + margin bbox", temporal_coverage="OSM snapshot, live-queried",
        resolution="Point", license="ODbL", account_required="No",
        access_status="ACCESSIBLE, DOWNLOADED (138 points)",
        local_path="data/raw/osm_extras/hospitals_schools.geojson",
        intended_possible_use="Impact/response-prioritization analysis",
        known_limitations="OSM completeness not verified against an official facility registry",
        leakage_concerns="None",
    ),
    dict(
        dataset_name="Critical infrastructure (power/telecom) -- OpenStreetMap",
        checklist_item="27",
        source_url="https://overpass-api.de/api/interpreter (power=*, telecom=*)",
        download_date=DOWNLOAD_DATE, file_format="GeoJSON (points)",
        spatial_coverage="Sikkim + margin bbox", temporal_coverage="OSM snapshot, live-queried",
        resolution="Point", license="ODbL", account_required="No",
        access_status="ACCESSIBLE, DOWNLOADED (2,353 points)",
        local_path="data/raw/osm_extras/infrastructure.geojson",
        intended_possible_use="Impact/response-prioritization analysis",
        known_limitations="Per the checklist's own honest note: coverage beyond what OSM has mapped "
                           "is not realistically gettable in this timeframe -- say so if asked, don't "
                           "imply comprehensive coverage",
        leakage_concerns="None",
    ),
    dict(
        dataset_name="Population -- WorldPop India 2020",
        checklist_item="25",
        source_url="https://data.worldpop.org/GIS/Population/Global_2000_2020_1km/2020/IND/"
                    "ind_ppp_2020_1km_Aggregated.tif",
        download_date=DOWNLOAD_DATE, file_format="GeoTIFF",
        spatial_coverage="All India (Sikkim sub-window verified, sum ~1.6M people in the bbox -- "
                          "bbox is larger than the state polygon, not yet clipped)",
        temporal_coverage="2020 estimate", resolution="1km (checklist mentioned 100m; used the 1km "
                                                        "aggregated product -- smaller, faster, still a "
                                                        "real WorldPop product; 100m version available "
                                                        "as a follow-up if finer resolution is needed)",
        license="CC-BY 4.0 (WorldPop)", account_required="No",
        access_status="ACCESSIBLE, DOWNLOADED (first attempt was interrupted mid-transfer, retried "
                       "successfully -- file size verified to match exactly)",
        local_path="data/raw/population/ind_ppp_2020_1km_Aggregated.tif",
        intended_possible_use="Impact/exposure analysis -- population near risk zones",
        known_limitations="Not yet clipped to the Sikkim state boundary (whole-India file)",
        leakage_concerns="None",
    ),
    dict(
        dataset_name="Census of India village boundaries",
        checklist_item="23 (alternate)",
        source_url="https://censusindia.gov.in", download_date="", file_format="", spatial_coverage="",
        temporal_coverage="", resolution="", license="",
        account_required="Unclear", access_status="Portal reachable (redirect observed) but not "
                                                     "pursued -- OSM village points already obtained "
                                                     "as a working substitute, and checklist itself "
                                                     "flags Census data as \"heavier format to work "
                                                     "with under time pressure\"",
        local_path="", intended_possible_use="Official village boundaries (vs. OSM points)",
        known_limitations="", leakage_concerns="",
    ),
    dict(
        dataset_name="HOT Export Tool (alternate roads/buildings source)",
        checklist_item="22-24 (alternate)",
        source_url="https://export.hotosm.org", download_date="", file_format="", spatial_coverage="",
        temporal_coverage="", resolution="", license="",
        account_required="Unclear (redirect observed, not investigated)",
        access_status="NOT PURSUED -- direct Overpass API queries already obtained equivalent OSM data "
                       "for roads/villages/buildings/hospitals-schools/infrastructure",
        local_path="", intended_possible_use="", known_limitations="", leakage_concerns="",
    ),
]


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for row in ROWS:
            writer.writerow(row)
    print(f"wrote {len(ROWS)} rows -> {OUT_PATH}")


if __name__ == "__main__":
    main()
