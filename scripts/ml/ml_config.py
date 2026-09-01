"""Shared, explicit configuration for the ML data pipeline. All tunable
parameters live here so a script never hides a magic number inline.

Scope note: this pipeline builds a ROAD-CORRIDOR susceptibility dataset, not
a full-state one. The GSI Sikkim inventory is 96.1%-within-100m-of-a-road
(measured against real OpenStreetMap road geometry, see docs/ audit) — an
artifact of how GSI's field validation actually happens (along NH/SH road
corridors), not evidence that susceptibility itself is road-proximate. We
lean into this as an intentional scope choice: it matches the project's own
road-connectivity objective (flagging at-risk road segments before they
fail), not a limitation we're hiding.
"""
import pathlib
from dataclasses import dataclass, field

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
DATA_PROCESSED = REPO_ROOT / "data" / "processed"
DATA_CASE_STUDY = REPO_ROOT / "data" / "case_study"


@dataclass(frozen=True)
class DemConfig:
    # Copernicus GLO-30 tile(s) covering the pilot corridor. All 777 GSI
    # Sikkim points fall inside this single tile (27-28N, 88-89E) -- verified
    # during the data audit, no mosaicking needed for this pilot.
    tile_ids: tuple[str, ...] = ("N27_00_E088_00",)
    bucket_url: str = "https://copernicus-dem-30m.s3.amazonaws.com"
    source_crs: str = "EPSG:4326"
    # UTM zone 45N -- correct metric CRS for Sikkim (~88E). Slope/aspect/
    # curvature are meaningless in degree-based EPSG:4326 pixels (verified:
    # produced ~90 degrees everywhere before reprojection).
    target_crs: str = "EPSG:32645"


@dataclass(frozen=True)
class RoadsConfig:
    # Bounding box slightly larger than Sikkim state to avoid edge effects
    # at the border. (south, west, north, east)
    bbox: tuple[float, float, float, float] = (26.9, 87.9, 28.2, 89.0)
    overpass_url: str = "https://overpass-api.de/api/interpreter"


@dataclass(frozen=True)
class NegativeSamplingConfig:
    # Corridor half-width around road centerlines, in meters. Chosen because
    # it captures 99.4% of positives' measured distance to nearest road
    # (verified during audit: p99 = 315m).
    corridor_buffer_m: float = 500.0
    # Radius excluded around each positive point, in meters. Documented
    # judgment call: Himalayan slide widths run to hundreds of meters (the
    # 2016 Mantam/So Bhir slide was 530m wide), so this avoids sampling the
    # same failure zone as an already-recorded event.
    exclusion_buffer_m: float = 200.0
    # Buffer used to build each district's own sub-corridor (union of
    # buffers around that district's positive points, intersected with the
    # full road corridor) -- this is how district-level proportions are
    # preserved without needing external administrative boundary data.
    district_hull_buffer_m: float = 3000.0
    # negatives per positive
    ratio: float = 1.0
    random_seed: int = 42


@dataclass(frozen=True)
class PathsConfig:
    gsi_sikkim_csv: pathlib.Path = DATA_RAW / "gsi_sikkim_landslides.csv"
    dem_raw_dir: pathlib.Path = DATA_RAW / "dem"
    dem_utm_path: pathlib.Path = DATA_PROCESSED / "dem_sikkim_utm45n.tif"
    roads_geojson: pathlib.Path = DATA_RAW / "sikkim_roads.geojson"
    landcover_tif: pathlib.Path = DATA_RAW / "landcover" / "ESA_WorldCover_10m_2021_v200_N27E087_Map.tif"
    negatives_csv: pathlib.Path = DATA_PROCESSED / "negative_samples.csv"
    training_dataset_csv: pathlib.Path = DATA_PROCESSED / "training_dataset.csv"
    sampling_plot: pathlib.Path = DATA_PROCESSED / "sampling_map.png"
    case_study_csv: pathlib.Path = DATA_CASE_STUDY / "rainfall_threshold_case_study.csv"


@dataclass(frozen=True)
class MlConfig:
    dem: DemConfig = field(default_factory=DemConfig)
    roads: RoadsConfig = field(default_factory=RoadsConfig)
    sampling: NegativeSamplingConfig = field(default_factory=NegativeSamplingConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)


DEFAULT_CONFIG = MlConfig()
