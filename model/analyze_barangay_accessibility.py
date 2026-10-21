"""SAKLAW baseline accessibility model (refactored for reuse).

The calculations are those of the original single-script model; they are only
split into functions with explicit inputs/outputs, and the intermediate arrays
(road-node index, per-cell demand table, baseline times) are exposed and cached
so candidate-site analysis does not repeat them.

Run `python model.py` to reproduce the original three outputs.
"""
from __future__ import annotations

import ast
import json
import pickle
import time
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import networkx as nx
import numpy as np
import pandas as pd
import rasterio
from pyproj import Transformer
from rasterio.features import rasterize
from rasterio.windows import Window
from scipy.spatial import cKDTree
from shapely.geometry import mapping

import config as cfg
from config import ModelParams


# ============================================================ helpers
def parse_list(value):
    """Convert GraphML list-like strings into Python lists."""
    if isinstance(value, list):
        return value
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = ast.literal_eval(value)
            if isinstance(parsed, list):
                return parsed
        except (ValueError, SyntaxError):
            pass
        return [value]
    return [value]


def get_highway(value):
    values = parse_list(value)
    return str(values[0]) if values else "unclassified"


def require_file(path):
    if not Path(path).exists():
        raise FileNotFoundError(f"Missing input file: {path}")


# ============================================================ data classes
@dataclass
class NodeIndex:
    """Stable ordering of road nodes + projected coordinates + KD-tree."""

    node_ids: list
    id_to_index: dict
    lonlat: np.ndarray  # (N,2) lon/lat
    xy: np.ndarray  # (N,2) EPSG:32651 metres
    tree: cKDTree


@dataclass
class HospitalSet:
    node_indices: np.ndarray  # unique snapped road-node indices
    table: pd.DataFrame  # valid hospitals with snap info


@dataclass
class DemandCells:
    """Aligned per-cell arrays. NEVER filter/reorder one without the others."""

    population: np.ndarray  # float64
    zone_index: np.ndarray  # int32, 0-based row in `barangays` (zone_id - 1)
    nearest_node_index: np.ndarray  # int32, index into NodeIndex ordering
    connector_seconds: np.ndarray  # float64, off-road walk to nearest node
    n_zones: int

    def __len__(self):
        return len(self.population)


@dataclass
class BaselineModel:
    params: ModelParams
    barangays: gpd.GeoDataFrame
    graph: nx.Graph
    node_index: NodeIndex
    hospitals: HospitalSet
    node_seconds: np.ndarray  # baseline time node -> nearest hospital (inf = none)
    cells: DemandCells
    baseline_seconds: np.ndarray  # per cell
    metrics: dict
    fingerprints: dict


# ============================================================ 1. barangays
def load_barangays(path=cfg.BARANGAY_FILE) -> gpd.GeoDataFrame:
    barangays = gpd.read_file(path)
    if barangays.crs is None:
        raise ValueError("Barangay CRS is missing. Verify its source CRS first.")
    if "ADM1_PCODE" in barangays.columns:
        barangays = barangays[
            barangays["ADM1_PCODE"].astype(str) == cfg.STUDY_AREA_PCODE
        ].copy()
    barangays = barangays.reset_index(drop=True)
    if barangays.empty:
        raise ValueError("No Region III barangays were found.")
    if "ADM4_EN" not in barangays.columns:
        raise ValueError("Expected barangay name column ADM4_EN.")
    if "population" not in barangays.columns:
        raise ValueError("Expected census population column 'population'.")
    # Stable integer ID used only for rasterization (1..n).
    barangays["zone_id"] = np.arange(1, len(barangays) + 1)
    return barangays


# ============================================================ 2. graph
def load_and_prepare_graph(graph_file=cfg.GRAPH_FILE,
                           params: ModelParams = ModelParams()) -> nx.Graph:
    """Read GraphML, make attributes numeric, assign travel_time (seconds)."""
    G = nx.read_graphml(graph_file)
    if not G.is_directed():
        print("WARNING: graph is undirected. One-way restrictions "
              "cannot be represented in routing results.")
    for node, attrs in G.nodes(data=True):
        if "x" not in attrs or "y" not in attrs:
            raise ValueError(f"Node {node} lacks x/y coordinates.")
        attrs["x"] = float(attrs["x"])
        attrs["y"] = float(attrs["y"])
    edge_iter = (G.edges(keys=True, data=True) if G.is_multigraph()
                 else ((u, v, None, d) for u, v, d in G.edges(data=True)))
    for u, v, key, attrs in edge_iter:
        if "length" not in attrs:
            raise ValueError("Graph edges lack a length attribute. "
                             "Rebuild or repair the graph before routing.")
        length_m = float(attrs["length"])
        highway = get_highway(attrs.get("highway"))
        speed_kmh = params.speed_kmh.get(highway, params.default_speed_kmh)
        attrs["travel_time"] = length_m / (speed_kmh * 1000 / 3600)
    return G


def build_node_index(G: nx.Graph) -> NodeIndex:
    node_ids = list(G.nodes())
    lonlat = np.array([[G.nodes[n]["x"], G.nodes[n]["y"]] for n in node_ids])
    to_utm = Transformer.from_crs(cfg.GEOGRAPHIC_CRS, cfg.PROJECTED_CRS, always_xy=True)
    x, y = to_utm.transform(lonlat[:, 0], lonlat[:, 1])
    xy = np.column_stack([x, y])
    return NodeIndex(node_ids, {n: i for i, n in enumerate(node_ids)},
                     lonlat, xy, cKDTree(xy))


# ============================================================ 3. hospitals
def load_hospitals_and_snap(hospital_file, node_index: NodeIndex,
                            params: ModelParams = ModelParams()) -> HospitalSet:
    hospitals = pd.read_csv(hospital_file)
    for col in ["longitude", "latitude"]:
        if col not in hospitals.columns:
            raise ValueError(f"Hospital CSV must contain '{col}'.")
        hospitals[col] = pd.to_numeric(hospitals[col], errors="coerce")
    hospitals = hospitals.dropna(subset=["longitude", "latitude"]).copy()
    if hospitals.empty:
        raise ValueError("No valid hospital coordinates found.")
    to_utm = Transformer.from_crs(cfg.GEOGRAPHIC_CRS, cfg.PROJECTED_CRS, always_xy=True)
    hx, hy = to_utm.transform(hospitals["longitude"].to_numpy(),
                              hospitals["latitude"].to_numpy())
    dist, idx = node_index.tree.query(np.column_stack([hx, hy]), k=1)
    valid = dist <= params.max_hospital_snap_m
    if not valid.all():
        print(f"WARNING: Excluding {int((~valid).sum())} hospitals more than "
              f"{params.max_hospital_snap_m} m from the road graph.")
    hospitals = hospitals[valid].copy()
    hospitals["snap_distance_m"] = dist[valid]
    hospitals["node_index"] = idx[valid]
    if len(hospitals) == 0:
        raise ValueError("No hospitals could be matched to the road graph. "
                         "Check coordinate systems and graph coverage.")
    return HospitalSet(np.unique(idx[valid]).astype(np.int64), hospitals)


# ============================================================ 4. baseline node times
def calculate_baseline_node_times(G: nx.Graph, node_index: NodeIndex,
                                  hospital_node_indices) -> np.ndarray:
    """Seconds from every road node TO its nearest hospital (inf if none).

    The graph is reversed (when directed) so one multi-source Dijkstra gives
    time *to* the hospital in the original graph."""
    routing_graph = G.reverse(copy=False) if G.is_directed() else G
    sources = {node_index.node_ids[i] for i in hospital_node_indices}
    times = nx.multi_source_dijkstra_path_length(
        routing_graph, sources=sources, weight="travel_time")
    out = np.full(len(node_index.node_ids), np.inf)
    for node, t in times.items():
        out[node_index.id_to_index[node]] = t
    return out


# ============================================================ 5. demand cells
def prepare_population_cells(raster_file, barangays: gpd.GeoDataFrame,
                             node_index: NodeIndex,
                             params: ModelParams = ModelParams()) -> DemandCells:
    """Collect every valid populated raster cell with its barangay, nearest
    road node and off-road connector time (same rules as the original)."""
    walking_mps = params.offroad_walking_kmh * 1000 / 3600
    pops_l, zone_l, node_l, conn_l = [], [], [], []
    with rasterio.open(raster_file) as src:
        raster_crs = src.crs
        if raster_crs is None:
            raise ValueError("Population raster CRS is missing.")
        b_r = barangays.to_crs(raster_crs)
        shapes = [(mapping(g), int(z)) for g, z in zip(b_r.geometry, b_r["zone_id"])
                  if g is not None and not g.is_empty]
        raster_to_utm = Transformer.from_crs(raster_crs, cfg.PROJECTED_CRS, always_xy=True)
        W = params.window_size
        for row_off in range(0, src.height, W):
            for col_off in range(0, src.width, W):
                h = min(W, src.height - row_off)
                w = min(W, src.width - col_off)
                window = Window(col_off, row_off, w, h)
                population = src.read(1, window=window, masked=True)
                transform = src.window_transform(window)
                zone_ids = rasterize(shapes, out_shape=(h, w), transform=transform,
                                     fill=0, dtype="int32", all_touched=False)
                pop_values = np.asarray(population.filled(0), dtype=np.float64)
                valid = ((~np.ma.getmaskarray(population)) & np.isfinite(pop_values)
                         & (pop_values > 0) & (zone_ids > 0))
                if not valid.any():
                    continue
                rows, cols = np.where(valid)
                xs, ys = rasterio.transform.xy(transform, rows, cols, offset="center")
                px, py = raster_to_utm.transform(np.asarray(xs), np.asarray(ys))
                dist, nearest = node_index.tree.query(np.column_stack([px, py]), k=1)
                pops_l.append(pop_values[rows, cols])
                zone_l.append((zone_ids[rows, cols] - 1).astype(np.int32))
                node_l.append(nearest.astype(np.int32))
                conn_l.append(dist / walking_mps)
            print(f"Processed raster rows {row_off + h:,}/{src.height:,}")
    return DemandCells(np.concatenate(pops_l), np.concatenate(zone_l),
                       np.concatenate(node_l), np.concatenate(conn_l), len(barangays))


def cell_seconds_from_node_seconds(cells: DemandCells, node_seconds) -> np.ndarray:
    """Cell time = off-road connector + road time from its nearest node."""
    return cells.connector_seconds + node_seconds[cells.nearest_node_index]


# ============================================================ 6. metrics
def calculate_metrics(cells: DemandCells, seconds: np.ndarray,
                      params: ModelParams = ModelParams()) -> dict:
    """Per-barangay accumulators for ANY per-cell time array (baseline or
    scenario) using exactly the baseline definitions. Arrays are length n_zones."""
    n = cells.n_zones
    z, p = cells.zone_index, cells.population
    covered = seconds <= params.limit_seconds
    reachable = np.isfinite(seconds)
    unreachable = ~reachable

    def bc(mask, weights=None):
        zz = z[mask]
        w = None if weights is None else weights[mask]
        return np.bincount(zz, weights=w, minlength=n)

    ones = None
    return {
        "total_population": bc(np.ones_like(covered), p),
        "total_cells": bc(np.ones_like(covered)).astype(np.int64),
        "covered_population": bc(covered, p),
        "covered_cells": bc(covered).astype(np.int64),
        "travel_time_sum": bc(reachable, seconds),
        "reachable_cells": bc(reachable).astype(np.int64),
        "population_time_sum": bc(reachable, p * np.where(reachable, seconds, 0.0)),
        "covered_time_sum": bc(covered, seconds),
        "unreachable_population": bc(unreachable, p),
        "unreachable_cells": bc(unreachable).astype(np.int64),
    }


def build_result_table(barangays, m: dict, params: ModelParams = ModelParams()) -> pd.DataFrame:
    n = len(barangays)
    total_pop = m["total_population"]
    covered_pop = m["covered_population"]
    reachable_cells = m["reachable_cells"]
    covered_n = m["covered_cells"]
    unreachable_pop = m["unreachable_population"]

    avg_time = np.divide(m["travel_time_sum"], reachable_cells,
                         out=np.full(n, np.nan), where=reachable_cells > 0) / 60
    weighted_avg_time = np.divide(
        m["population_time_sum"], total_pop - unreachable_pop,
        out=np.full(n, np.nan), where=(total_pop - unreachable_pop) > 0) / 60
    avg_covered_time = np.divide(m["covered_time_sum"], covered_n,
                                 out=np.full(n, np.nan), where=covered_n > 0) / 60
    coverage_pct = np.divide(covered_pop, total_pop, out=np.full(n, np.nan),
                             where=total_pop > 0) * 100

    result = pd.DataFrame({
        "ADM4_PCODE": barangays["ADM4_PCODE"].astype(str),
        "total_population": total_pop,
        "population_within_threshold": covered_pop,
        "population_coverage_pct": coverage_pct,
        "avg_travel_time_min": avg_time,
        "population_weighted_avg_travel_time_min": weighted_avg_time,
        "avg_covered_travel_time_min": avg_covered_time,
        "max_travel_time_min": np.nan,
        "raster_cell_count": m["total_cells"],
        "reachable_cell_count": reachable_cells,
        "covered_cell_count": covered_n,
        "unreachable_cell_count": m["unreachable_cells"],
        "unreachable_population": unreachable_pop,
        "time_limit_minutes": params.time_limit_minutes,
    })
    result["meets_coverage_threshold"] = (
        (result["population_coverage_pct"] >= params.min_barangay_coverage_pct)
        & result["population_coverage_pct"].notna()).astype("int8")
    return result


def build_overall(m: dict, result: pd.DataFrame, params: ModelParams = ModelParams()) -> dict:
    all_pop = float(np.sum(m["total_population"]))
    all_cov = float(np.sum(m["covered_population"]))
    all_unr = float(np.sum(m["unreachable_population"]))
    all_reach_cells = int(np.sum(m["reachable_cells"]))
    all_cov_cells = int(np.sum(m["covered_cells"]))
    reachable_pop = all_pop - all_unr
    return {
        "time_limit_minutes": params.time_limit_minutes,
        "required_barangay_coverage_pct": params.min_barangay_coverage_pct,
        "total_population": all_pop,
        "population_within_threshold": all_cov,
        "population_outside_threshold": all_pop - all_cov,
        "population_coverage_pct": 100 * all_cov / all_pop if all_pop > 0 else None,
        "unreachable_population": all_unr,
        "reachable_population": reachable_pop,
        "avg_travel_time_min": (float(np.sum(m["travel_time_sum"]) / all_reach_cells / 60)
                                if all_reach_cells else None),
        "population_weighted_avg_travel_time_min": (
            float(np.sum(m["population_time_sum"]) / reachable_pop / 60)
            if reachable_pop > 0 else None),
        "avg_covered_travel_time_min": (float(np.sum(m["covered_time_sum"]) / all_cov_cells / 60)
                                        if all_cov_cells else None),
        "raster_cell_count": int(np.sum(m["total_cells"])),
        "reachable_cell_count": all_reach_cells,
        "covered_cell_count": all_cov_cells,
        "unreachable_cell_count": int(np.sum(m["unreachable_cells"])),
        "barangay_count": len(result),
        "barangays_meeting_coverage_target": int(result["meets_coverage_threshold"].sum()),
        "road_speed_assumptions_kmh": params.speed_kmh,
        "default_road_speed_kmh": params.default_speed_kmh,
        "offroad_walking_speed_kmh": params.offroad_walking_kmh,
    }


def calculate_baseline_metrics(cells, baseline_seconds, barangays, params=ModelParams()):
    m = calculate_metrics(cells, baseline_seconds, params)
    result = build_result_table(barangays, m, params)
    return m, result, build_overall(m, result, params)


# ============================================================ 7. outputs
def write_accessibility_outputs(barangays, result, overall, csv_path, geojson_path, json_path):
    Path(csv_path).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(csv_path, index=False)
    geo = barangays[["ADM4_PCODE", "geometry"]].copy()
    for col in result.columns:
        if col != "ADM4_PCODE":
            geo[col] = result[col].to_numpy()
    geo.to_crs(cfg.GEOGRAPHIC_CRS).to_file(geojson_path, driver="GeoJSON")
    if json_path is not None:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(overall, f, indent=2, allow_nan=False)


def save_baseline_outputs(model: BaselineModel, csv_path=cfg.OUTPUT_CSV,
                          geojson_path=cfg.OUTPUT_GEOJSON, json_path=cfg.OUTPUT_OVERALL_JSON):
    result = build_result_table(model.barangays, model.metrics, model.params)
    overall = build_overall(model.metrics, result, model.params)
    write_accessibility_outputs(model.barangays, result, overall,
                                csv_path, geojson_path, json_path)
    return result, overall


# ============================================================ 8. caching
def _meta_equal(saved: dict, wanted: dict) -> bool:
    return json.loads(json.dumps(saved, sort_keys=True)) == json.loads(
        json.dumps(wanted, sort_keys=True))


def compute_fingerprints(params, graph_file, hospital_file, raster_file, barangay_file) -> dict:
    """Metadata that decides which caches are still valid. A change to the
    requested number of hospitals is NOT part of it."""
    fp = {
        "model_version": cfg.MODEL_VERSION,
        "graph_file": cfg.file_digest(graph_file),
        "hospital_file": cfg.file_digest(hospital_file),
        "raster_file": cfg.file_digest(raster_file),
        "barangay_file": cfg.file_digest(barangay_file),
        "speeds": params.speed_fingerprint(),
        "offroad_walking_kmh": params.offroad_walking_kmh,
        "max_hospital_snap_m": params.max_hospital_snap_m,
        "crs": [cfg.GEOGRAPHIC_CRS, cfg.PROJECTED_CRS],
    }
    graph_key = {k: fp[k] for k in ("model_version", "graph_file", "speeds", "crs")}
    cells_key = {**{k: fp[k] for k in ("model_version", "graph_file", "raster_file",
                                       "barangay_file", "offroad_walking_kmh", "crs")}}
    baseline_key = {"graph": graph_key, "cells": cells_key,
                    "hospital_file": fp["hospital_file"],
                    "max_hospital_snap_m": fp["max_hospital_snap_m"]}
    fp["graph_key"], fp["cells_key"], fp["baseline_key"] = graph_key, cells_key, baseline_key
    fp["baseline_digest"] = cfg.digest(baseline_key)
    return fp


def _timed(label, fn, *a, **k):
    t0 = time.time()
    out = fn(*a, **k)
    print(f"[{label}] {time.time() - t0:.1f}s")
    return out


def build_baseline_model(params: ModelParams = ModelParams(),
                         graph_file=cfg.GRAPH_FILE, hospital_file=cfg.HOSPITAL_FILE,
                         raster_file=cfg.POPULATION_RASTER, barangay_file=cfg.BARANGAY_FILE,
                         cache_dir=cfg.CACHE_DIR, use_cache=True) -> BaselineModel:
    """Build (or load from valid caches) the reusable baseline state."""
    for p in (graph_file, hospital_file, raster_file, barangay_file):
        require_file(p)
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    graph_cache = cache_dir / "weighted_road_graph.pkl"
    demand_cache = cache_dir / "demand_cells.npz"
    baseline_cache = cache_dir / "baseline_travel_times.npz"

    fp = compute_fingerprints(params, graph_file, hospital_file, raster_file, barangay_file)
    barangays = _timed("barangays", load_barangays, barangay_file)

    # ---- weighted graph
    G = None
    if use_cache and graph_cache.exists():
        with open(graph_cache, "rb") as f:  # trusted local cache
            saved = pickle.load(f)
        if _meta_equal(saved["meta"], fp["graph_key"]):
            G = saved["graph"]
            print("Loaded weighted road graph from cache.")
    if G is None:
        G = _timed("graph", load_and_prepare_graph, graph_file, params)
        with open(graph_cache, "wb") as f:
            pickle.dump({"meta": fp["graph_key"], "graph": G}, f, protocol=pickle.HIGHEST_PROTOCOL)
    node_index = _timed("node index", build_node_index, G)

    # ---- hospitals + baseline node times (+ demand cells)
    hospitals = load_hospitals_and_snap(hospital_file, node_index, params)

    cells = None
    if use_cache and demand_cache.exists():
        with np.load(demand_cache, allow_pickle=False) as z:
            if _meta_equal(json.loads(str(z["meta"])), fp["cells_key"]) and \
                    int(z["n_zones"]) == len(barangays):
                cells = DemandCells(z["population"], z["zone_index"],
                                    z["nearest_node_index"], z["connector_seconds"],
                                    int(z["n_zones"]))
                print("Loaded demand cells from cache.")
    if cells is None:
        cells = _timed("demand cells", prepare_population_cells,
                       raster_file, barangays, node_index, params)
        np.savez(demand_cache, population=cells.population, zone_index=cells.zone_index,
                 nearest_node_index=cells.nearest_node_index,
                 connector_seconds=cells.connector_seconds, n_zones=cells.n_zones,
                 meta=json.dumps(fp["cells_key"], sort_keys=True))

    node_seconds = baseline_seconds = None
    if use_cache and baseline_cache.exists():
        with np.load(baseline_cache, allow_pickle=False) as z:
            if _meta_equal(json.loads(str(z["meta"])), fp["baseline_key"]) and \
                    len(z["baseline_seconds"]) == len(cells):
                node_seconds, baseline_seconds = z["node_seconds"], z["baseline_seconds"]
                hospitals = HospitalSet(z["hospital_node_indices"], hospitals.table)
                print("Loaded baseline travel times from cache.")
    if node_seconds is None:
        node_seconds = _timed("baseline dijkstra", calculate_baseline_node_times,
                              G, node_index, hospitals.node_indices)
        baseline_seconds = cell_seconds_from_node_seconds(cells, node_seconds)
        np.savez(baseline_cache, node_seconds=node_seconds, baseline_seconds=baseline_seconds,
                 hospital_node_indices=hospitals.node_indices,
                 meta=json.dumps(fp["baseline_key"], sort_keys=True))

    metrics = calculate_metrics(cells, baseline_seconds, params)
    return BaselineModel(params, barangays, G, node_index, hospitals, node_seconds,
                         cells, baseline_seconds, metrics, fp)


# ============================================================ CLI
def main():
    model = build_baseline_model(use_cache=True)
    result, overall = save_baseline_outputs(model)
    print("Finished.")
    print(f"Barangay CSV: {cfg.OUTPUT_CSV}")
    print(f"Barangay GeoJSON: {cfg.OUTPUT_GEOJSON}")
    print(f"Overall JSON: {cfg.OUTPUT_OVERALL_JSON}")
    pct = overall["population_coverage_pct"]
    print(f"Overall population coverage: {pct:.2f}%" if pct is not None
          else "Overall population coverage: undefined")


if __name__ == "__main__":
    main()