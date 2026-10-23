"""Central configuration for SAKLAW: paths, assumptions, thresholds, weights.

Every value that changes a result lives here (or in a params dataclass built
from here) so it can be fingerprinted into cache metadata.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

MODEL_VERSION = "saklaw-2.0"

# ------------------------------------------------------------------ paths
ROOT = Path(os.environ.get("SAKLAW_ROOT", Path(__file__).resolve().parent))
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / "cache"
OUTPUT_DIR = ROOT / "outputs"

GRAPH_FILE = DATA_DIR / "region3_roads.graphml"
HOSPITAL_FILE = DATA_DIR / "hospital_coords.csv"
BARANGAY_FILE = DATA_DIR / "region3_barangay_shape_with_population.geojson"
POPULATION_RASTER = DATA_DIR / "population_calibrated_region3.tif"

OUTPUT_CSV = DATA_DIR / "barangay_accessibility.csv"
OUTPUT_GEOJSON = DATA_DIR / "barangay_accessibility.geojson"
OUTPUT_OVERALL_JSON = DATA_DIR / "accessibility_overall.json"

GRAPH_CACHE = CACHE_DIR / "weighted_road_graph.pkl"
DEMAND_CACHE = CACHE_DIR / "demand_cells.npz"
BASELINE_CACHE = CACHE_DIR / "baseline_travel_times.npz"
CANDIDATE_CACHE_DIR = CACHE_DIR / "candidate_travel_times"

# -------------------------------------------------------------- CRS / area
STUDY_AREA_PCODE = "PH03"
GEOGRAPHIC_CRS = "EPSG:4326"
PROJECTED_CRS = "EPSG:32651"  # UTM 51N: metres, used for all distances

# ------------------------------------------------- baseline model (unchanged)
# Approximate driving speeds by road class. Assumptions, not observed speeds.
SPEED_KMH = {
    "motorway": 80,
    "trunk": 65,
    "primary": 50,
    "secondary": 40,
    "tertiary": 30,
    "residential": 20,
    "unclassified": 20,
    "service": 10,
    "living_street": 10,
}


@dataclass(frozen=True)
class ModelParams:
    """Assumptions that define the baseline AND every candidate scenario.

    Changing any of these invalidates the caches (see fingerprint())."""

    time_limit_minutes: float = 30
    min_barangay_coverage_pct: float = 80
    speed_kmh: dict = field(default_factory=lambda: dict(SPEED_KMH))
    default_speed_kmh: float = 20
    offroad_walking_kmh: float = 5  # raster cell -> nearest road node
    max_hospital_snap_m: float = 3000
    window_size: int = 512

    @property
    def limit_seconds(self) -> float:
        return self.time_limit_minutes * 60

    def speed_fingerprint(self) -> str:
        return digest({"speed": self.speed_kmh, "default": self.default_speed_kmh})


# -------------------------------------------------------- candidate settings
@dataclass(frozen=True)
class CandidateParams:
    grid_spacing_m: float = 1000
    # Grid lines sit at origin + n * spacing in EPSG:32651, independent of the
    # study-area bounding box, so candidate IDs never shift between runs.
    grid_origin_xy: tuple = (0.0, 0.0)
    max_snap_m: float = 500  # grid point -> road node
    min_hospital_separation_m: float = 1000  # new site vs existing hospital
    # Focus the search on underserved areas, with a buffer so that useful sites
    # in better-served neighbouring barangays are still evaluated.
    use_priority_filter: bool = True
    priority_buffer_m: float = 10_000
    priority_min_uncovered_pop: float = 1000  # barangay is 'priority' if it has
    # coverage < target OR at least this many residents outside the threshold


# -------------------------------------------------------- optimizer settings
@dataclass(frozen=True)
class OptimizerParams:
    weights: dict = field(default_factory=lambda: {
        "coverage": 1 / 3, "travel": 1 / 3, "equity": 1 / 3})
    min_site_separation_m: float = 2000  # between recommended sites
    alternative_separation_m: float = 5000
    min_marginal_score: float = 1e-9  # stop when best combined score <= this
    tie_tolerance: float = 1e-12
    # None = exact. A cutoff (seconds) truncates candidate travel-time fields
    # and can omit benefits beyond it; it is reported in the summary.
    candidate_cutoff_seconds: float | None = None
    dijkstra_batch: int = 32

    def normalized_weights(self) -> dict:
        tot = sum(self.weights.values())
        if tot <= 0:
            raise ValueError("Objective weights must sum to a positive value.")
        return {k: v / tot for k, v in self.weights.items()}


# ----------------------------------------------------------------- helpers
def digest(obj) -> str:
    """Stable short hash of a JSON-serialisable object."""
    blob = json.dumps(obj, sort_keys=True, default=str).encode()
    return hashlib.sha256(blob).hexdigest()[:16]


def file_digest(path) -> str:
    """sha256 of a file's bytes (streamed)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def params_dict(p) -> dict:
    return asdict(p)
