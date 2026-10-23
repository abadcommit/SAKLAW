"""Generate the 1 km candidate grid and snap it to the road network.

Candidates are POTENTIAL locations on road nodes that the network model can
evaluate. They are not verified buildable parcels: land use, zoning, hazards
and ownership must be checked separately.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from scipy.spatial import cKDTree
from scipy.sparse.csgraph import connected_components

import backend.model.config as cfg
from backend.model.candidate_evaluation import build_time_matrix
from backend.model.config import CandidateParams

REASONS = ("snap_distance_exceeded", "duplicate_node", "disconnected_node",
           "existing_hospital_node", "too_close_to_hospital", "outside_priority_area")


def study_area_utm(barangays):
    """Union of barangay geometries in EPSG:32651 + the per-barangay geoms."""
    geoms = shapely.make_valid(barangays.to_crs(cfg.PROJECTED_CRS).geometry.values)
    return shapely.union_all(geoms), geoms


def make_grid(area, spacing, origin_xy):
    """Cell centres on a lattice anchored at `origin_xy` (NOT at the bbox),
    so IDs are stable. Returns ix, iy, x, y for centres inside the area."""
    minx, miny, maxx, maxy = area.bounds
    ox, oy = origin_xy
    ix = np.arange(int(np.floor((minx - ox) / spacing)), int(np.floor((maxx - ox) / spacing)) + 1)
    iy = np.arange(int(np.floor((miny - oy) / spacing)), int(np.floor((maxy - oy) / spacing)) + 1)
    IX, IY = np.meshgrid(ix, iy, indexing="ij")
    IX, IY = IX.ravel(), IY.ravel()
    X = ox + (IX + 0.5) * spacing
    Y = oy + (IY + 0.5) * spacing
    inside = shapely.contains_xy(area, X, Y)
    return IX[inside], IY[inside], X[inside], Y[inside]


def priority_barangay_mask(model, cparams: CandidateParams = CandidateParams()):
    """Barangays below the coverage target or with many uncovered residents."""
    m, p = model.metrics, model.params
    tot, cov = m["total_population"], m["covered_population"]
    pct = np.divide(cov, tot, out=np.full(len(tot), np.nan), where=tot > 0) * 100
    return ((pct < p.min_barangay_coverage_pct)
            | ((tot - cov) >= cparams.priority_min_uncovered_pop))


def generate_candidates(model, cparams: CandidateParams = CandidateParams()) -> pd.DataFrame:
    """Return ALL grid candidates (eligible or not) with exclusion reasons."""
    ni = model.node_index
    area, geoms = study_area_utm(model.barangays)
    ix, iy, gx, gy = make_grid(area, cparams.grid_spacing_m, cparams.grid_origin_xy)

    dist, node_idx = ni.tree.query(np.column_stack([gx, gy]), k=1)
    df = pd.DataFrame({
        "candidate_id": [f"C{a}_{b}" for a, b in zip(ix, iy)],
        "grid_id": [f"G{a}_{b}" for a, b in zip(ix, iy)],
        "grid_x_m": gx, "grid_y_m": gy,
        "node_index": node_idx.astype(np.int64),
        "node_id": [str(ni.node_ids[i]) for i in node_idx],
        # coordinates are the SNAPPED ROAD NODE, not the grid centre
        "longitude": ni.lonlat[node_idx, 0], "latitude": ni.lonlat[node_idx, 1],
        "x_m": ni.xy[node_idx, 0], "y_m": ni.xy[node_idx, 1],
        "snap_distance_m": dist,
    })
    reason = np.full(len(df), "", dtype=object)

    def mark(mask, why):
        mask = mask & (reason == "")
        reason[mask] = why

    # 1. too far from any road node
    mark(dist > cparams.max_snap_m, "snap_distance_exceeded")

    # 2. several grid points on one node: keep the closest (tie: smaller id)
    ok = reason == ""
    order = df[ok].sort_values(["node_index", "snap_distance_m", "grid_id"]).index
    first = ~df.loc[order, "node_index"].duplicated()
    dup_idx = order[~first.to_numpy()]
    reason[df.index.get_indexer(dup_idx)] = "duplicate_node"

    # 3. nodes outside the largest strongly connected component
    M = build_time_matrix(model.graph, ni)
    _, labels = connected_components(M, directed=True, connection="strong")
    biggest = np.bincount(labels).argmax()
    mark(labels[node_idx] != biggest, "disconnected_node")

    # 4. existing hospitals: same node, or closer than the separation rule
    hosp = model.hospitals.table
    hosp_node = np.isin(node_idx, model.hospitals.node_indices)
    mark(hosp_node, "existing_hospital_node")
    to_utm = Transformer.from_crs(cfg.GEOGRAPHIC_CRS, cfg.PROJECTED_CRS, always_xy=True)
    hx, hy = to_utm.transform(hosp["longitude"].to_numpy(), hosp["latitude"].to_numpy())
    d_h, _ = cKDTree(np.column_stack([hx, hy])).query(ni.xy[node_idx], k=1)
    df["nearest_hospital_m"] = d_h
    mark(d_h < cparams.min_hospital_separation_m, "too_close_to_hospital")

    # 5. focus on underserved areas, with a buffer
    df["in_priority_area"] = True
    if cparams.use_priority_filter:
        prio = priority_barangay_mask(model, cparams)
        if prio.any():
            zone = shapely.union_all(shapely.buffer(
                shapely.simplify(geoms[prio], 100), cparams.priority_buffer_m, quad_segs=4))
            inside = shapely.contains_xy(zone, df["x_m"].to_numpy(), df["y_m"].to_numpy())
            df["in_priority_area"] = inside
            mark(~inside, "outside_priority_area")
        else:
            print("WARNING: no priority barangays; priority filter skipped.")

    df["eligible"] = reason == ""
    df["exclusion_reason"] = reason
    return df.reset_index(drop=True)


def write_candidate_geojson(df: pd.DataFrame, path):
    import geopandas as gpd
    cols = ["candidate_id", "grid_id", "node_id", "longitude", "latitude",
            "snap_distance_m", "nearest_hospital_m", "eligible", "exclusion_reason"]
    g = gpd.GeoDataFrame(df[cols].copy(),
                         geometry=gpd.points_from_xy(df["longitude"], df["latitude"]),
                         crs=cfg.GEOGRAPHIC_CRS)
    g.to_file(path, driver="GeoJSON")
