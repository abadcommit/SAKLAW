"""Greedy iterative selection of k new hospital sites, with alternatives.

Each round scores every remaining candidate by its MARGINAL improvement over the
current scenario (baseline + sites already chosen), picks the best, updates the
scenario, and repeats. This is a heuristic: it does not guarantee the globally
optimal set of k sites.

Alternatives: combination 1 is the plain greedy result. Each further combination
is the greedy result with every candidate within `alternative_separation_m` of
any site in an EARLIER combination removed, so combinations are genuinely
different networks (for k=1: spread-out alternative single sites). Combinations
are ranked by the combined score of the whole network.

Re-scoring is incremental but exact: a candidate's marginal score can only
change if the newly selected site changed the travel time of a road node the
candidate improves, or the coverage total of a barangay the candidate touches.
Only those candidates are re-evaluated (`incremental=False` re-scores all).
The initial all-candidate evaluation is done once and shared by all combinations.
"""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import backend.model.config as cfg
from backend.model.candidate_evaluation import (CandidateFieldStore, CellIndex, Impact, ObjectiveReference,
                                  ScenarioState, build_time_matrix, score_impact)
from backend.model.candidate_generation import generate_candidates, write_candidate_geojson
from backend.model.config import CandidateParams, OptimizerParams


@dataclass
class OptimizationResult:
    requested: int
    selected: list  # one dict per site, in selection order
    baseline: dict
    final: dict
    stop_reason: str
    candidate_scores: pd.DataFrame
    reference: ObjectiveReference
    state: ScenarioState
    warnings: list = field(default_factory=list)
    timings: dict = field(default_factory=dict)
    consistency: dict = field(default_factory=dict)
    network_impact: Impact = field(default_factory=Impact)  # whole set vs baseline
    combination: int = 1  # rank after sorting by network score
    generation_order: int = 1  # order in which it was generated


class GreedySelector:
    """Holds the candidate table, fields and the shared first-round evaluation."""

    def __init__(self, store: CandidateFieldStore, candidates: pd.DataFrame,
                 oparams: OptimizerParams = OptimizerParams()):
        self.store, self.oparams = store, oparams
        self.weights = oparams.normalized_weights()
        self.cand = candidates[candidates["eligible"]].reset_index(drop=True)
        self.n = len(self.cand)
        cols = ["candidate_id", "grid_id", "node_id", "node_index", "longitude", "latitude",
                "snap_distance_m", "x_m", "y_m"]
        self.scores = self.cand[cols].copy()
        for c in ("coverage_score", "travel_score", "equity_score", "combined_score",
                  "added_population"):
            self.scores["initial_" + c] = np.nan
        self.xy = self.cand[["x_m", "y_m"]].to_numpy()
        self.ids = self.cand["candidate_id"].to_numpy()
        self.timings = {}

    # ---- one evaluation of every candidate against the baseline (shared)
    def prepare(self, baseline_state: ScenarioState, verbose=True):
        self.ref = ObjectiveReference.from_state(baseline_state)
        self.base_impacts = [None] * self.n
        self.base_score = np.full(self.n, -np.inf)
        self.touched = [None] * self.n
        self.fields = []
        if self.n == 0:
            return
        ts = time.time()
        self.store.ensure(self.cand["node_index"].to_numpy())
        self.timings["candidate_fields_s"] = time.time() - ts
        self.fields = [self.store.fields[int(v)] for v in self.cand["node_index"]]
        ts = time.time()
        for i in range(self.n):
            imp, self.touched[i] = baseline_state.evaluate_with_touched(
                self.fields[i], self.ref, self.weights)
            self.base_impacts[i] = imp
            self.base_score[i] = imp.combined_score
            for c in ("coverage_score", "travel_score", "equity_score", "combined_score"):
                self.scores.at[i, "initial_" + c] = getattr(imp, c)
            self.scores.at[i, "initial_added_population"] = imp.added_population
        self.timings["initial_evaluation_s"] = time.time() - ts

    # ---- one greedy run on a FRESH state
    def run(self, k: int, state: ScenarioState, banned: np.ndarray | None = None,
            incremental: bool = True, verbose: bool = True) -> OptimizationResult:
        if not isinstance(k, (int, np.integer)) or k < 0:
            raise ValueError("k must be a non-negative integer.")
        op, n = self.oparams, self.n
        t0 = time.time()
        baseline = state.snapshot()
        warnings = list(self.ref.warnings)
        scores = self.scores.copy()
        scores["selection_order"] = 0
        scores["not_selected_reason"] = ""
        active = np.ones(n, bool)
        if banned is not None:
            active &= ~banned
            scores.loc[banned, "not_selected_reason"] = "near_site_in_earlier_combination"
        impacts = list(self.base_impacts) if n else []
        score = self.base_score.copy()
        dirty = np.ones(n, bool) if not incremental else np.zeros(n, bool)
        selected, stop, n_eval = [], "requested_count_reached", 0

        if k == 0:
            stop = "k_is_zero"
        elif not active.any():
            stop = "no_eligible_candidates"
            warnings.append("No eligible candidates.")
        else:
            for rnd in range(1, k + 1):
                ts = time.time()
                todo = np.flatnonzero(active & dirty)
                n_active = int(active.sum())
                for i in todo:
                    impacts[i] = state.evaluate(self.fields[i], self.ref, self.weights)
                    score[i] = impacts[i].combined_score
                dirty[todo] = False
                n_eval += len(todo)
                if not active.any():
                    stop = "no_eligible_candidates_remaining"
                    break
                best = score[active].max()
                if best <= op.min_marginal_score:
                    stop = "no_remaining_candidate_improves_the_objectives"
                    break
                ties = np.flatnonzero(active & (score >= best - op.tie_tolerance))
                b = min(ties, key=lambda i: (-impacts[i].added_population, str(self.ids[i])))
                imp = impacts[b]
                summ = state.apply(self.fields[b])
                selected.append({
                    "candidate_id": self.ids[b], "selection_order": rnd, "index": int(b),
                    "impact": imp, "after": state.snapshot(),
                    "evaluated_this_round": int(len(todo)), "round_s": time.time() - ts})
                scores.at[b, "selection_order"] = rnd
                active[b] = False
                d = np.hypot(self.xy[:, 0] - self.xy[b, 0], self.xy[:, 1] - self.xy[b, 1])
                sep = active & (d < op.min_site_separation_m)
                scores.loc[sep, "not_selected_reason"] = f"within_separation_of_site_{rnd}"
                active[sep] = False
                if incremental:
                    nm = np.zeros(self.store.base.shape[0], bool)
                    nm[summ.changed_nodes] = True
                    zm = np.zeros(state.cells.n_zones, bool)
                    zm[summ.zones_coverage_changed] = True
                    for i in np.flatnonzero(active & ~dirty):
                        if nm[self.fields[i].node_idx].any() or zm[self.touched[i]].any():
                            dirty[i] = True
                else:
                    dirty[:] = True
                if verbose:
                    print(f"  round {rnd}: {self.ids[b]}  +{imp.added_population:,.0f} people "
                          f"(score {imp.combined_score:.5f}; re-scored {len(todo)} of {n_active})")

        if len(selected) < k:
            warnings.append(
                f"Only {len(selected)} of {k} requested sites could be justified: {stop}. "
                "No additional locations were invented to reach the requested count.")
        if op.candidate_cutoff_seconds is not None:
            warnings.append(
                f"Candidate travel times were truncated at {op.candidate_cutoff_seconds/60:.0f} "
                "min; benefits beyond the cutoff are not counted.")
        scores.loc[(scores["selection_order"] == 0) & (scores["not_selected_reason"] == ""),
                   "not_selected_reason"] = "lower_marginal_score"
        final = state.snapshot()
        net = Impact(
            added_population=final["population_within_threshold"] - baseline["population_within_threshold"],
            coverage_gain_pp=final["population_coverage_pct"] - baseline["population_coverage_pct"],
            weighted_time_reduction_min=((baseline["weighted_mean_travel_time_min"]
                                          - final["weighted_mean_travel_time_min"])
                                         if baseline["weighted_mean_travel_time_min"] is not None else 0.0),
            equity_shortfall_reduction=baseline["mean_barangay_shortfall"] - final["mean_barangay_shortfall"],
            barangays_meeting_target_gain=final["barangays_meeting_target"] - baseline["barangays_meeting_target"])
        score_impact(net, self.ref, self.weights)
        timings = {**self.timings, "run_s": time.time() - t0, "evaluations": n_eval}
        return OptimizationResult(k, selected, baseline, final, stop, scores, self.ref, state,
                                  warnings, timings, _full_recompute(state), net)


def select_sites(state: ScenarioState, store: CandidateFieldStore, candidates: pd.DataFrame,
                 k: int, oparams: OptimizerParams = OptimizerParams(),
                 incremental: bool = True, verbose: bool = True) -> OptimizationResult:
    """Single greedy selection (combination 1). `state` must be a fresh baseline state;
    it is advanced to the final scenario."""
    sel = GreedySelector(store, candidates, oparams)
    sel.prepare(state, verbose)
    return sel.run(k, state, incremental=incremental, verbose=verbose)


def find_alternatives(make_state, store: CandidateFieldStore, candidates: pd.DataFrame, k: int,
                      n_alternatives: int, oparams: OptimizerParams = OptimizerParams(),
                      verbose: bool = True):
    """Return (results ranked by network score, warnings). Each combination avoids the
    neighbourhood (`alternative_separation_m`) of every site in earlier combinations."""
    sel = GreedySelector(store, candidates, oparams)
    sel.prepare(make_state(), verbose)
    banned = np.zeros(sel.n, bool)
    results, warns = [], []
    for g in range(1, max(1, n_alternatives) + 1):
        if verbose and n_alternatives > 1:
            print(f"Combination {g}/{n_alternatives}")
        res = sel.run(k, make_state(), banned=banned, verbose=verbose)
        res.generation_order = g
        if len(res.selected) == 0 and k > 0:
            warns.append(f"Stopped after {g - 1} combinations: no further sites available "
                         f"outside {oparams.alternative_separation_m/1000:.1f} km of earlier ones.")
            break
        if len(res.selected) < k:
            res.warnings.append(f"Combination {g} is INCOMPLETE ({len(res.selected)} of {k} sites).")
        results.append(res)
        for s in res.selected:
            i = s["index"]
            banned |= np.hypot(sel.xy[:, 0] - sel.xy[i, 0],
                               sel.xy[:, 1] - sel.xy[i, 1]) < oparams.alternative_separation_m
        if k == 0:
            break
    if len(results) < n_alternatives and not warns and k > 0:
        warns.append(f"Only {len(results)} of {n_alternatives} combinations could be produced.")
    results.sort(key=lambda r: (-r.network_impact.combined_score, r.generation_order))
    for rank, r in enumerate(results, 1):
        r.combination = rank
    return results, warns


def _full_recompute(state: ScenarioState) -> dict:
    """Independent recomputation of final metrics from the per-cell times, to
    cross-check the incremental aggregates."""
    from backend.model.analyze_barangay import calculate_metrics
    m = calculate_metrics(state.cells, state.current, state.params)
    covered = float(m["covered_population"].sum())
    ref = np.isfinite(state.baseline)
    wm = float((state.cells.population[ref] * state.current[ref]).sum()
               / state.cells.population[ref].sum() / 60)
    return {"population_within_threshold": covered, "weighted_mean_travel_time_min": wm,
            "max_abs_diff_vs_incremental": max(
                abs(covered - state.covered_total),
                abs(wm - state.weighted_mean_seconds() / 60))}


# ------------------------------------------------------------------ outputs
def _site_rows(result: OptimizationResult, cand, base):
    rows = []
    for s in result.selected:
        i, a = s["impact"], s["after"]
        c = cand.loc[s["candidate_id"]]
        rows.append({
            "combination": result.combination, "candidate_id": s["candidate_id"],
            "selection_order": s["selection_order"],
            "longitude": float(c.longitude), "latitude": float(c.latitude),
            "combined_score": i.combined_score,
            "additional_population_covered": i.added_population,
            "coverage_gain_percentage_points": i.coverage_gain_pp,
            "weighted_travel_time_reduction_min": i.weighted_time_reduction_min,
            "barangays_meeting_target_gain": i.barangays_meeting_target_gain,
            "equity_score": i.equity_score, "coverage_score": i.coverage_score,
            "travel_score": i.travel_score, "snap_distance_m": float(c.snap_distance_m),
            "grid_id": c.grid_id, "node_id": c.node_id,
            "cumulative_additional_population": a["population_within_threshold"]
            - base["population_within_threshold"],
            "cumulative_coverage_pct": a["population_coverage_pct"],
            "cumulative_weighted_mean_travel_time_min": a["weighted_mean_travel_time_min"],
        })
    return rows


def write_outputs(model, results, candidates: pd.DataFrame, cparams: CandidateParams,
                  oparams: OptimizerParams, outdir=cfg.OUTPUT_DIR, extra: dict | None = None,
                  requested_alternatives: int = 1, alt_warnings=None):
    """`results`: ranked list of OptimizationResult (rank 1 first), or one result."""
    import geopandas as gpd
    from backend.model.analyze_barangay import (build_overall, build_result_table, calculate_metrics,
                       write_accessibility_outputs)
    results = [results] if isinstance(results, OptimizationResult) else list(results)
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    best = results[0]
    base = best.baseline
    cand = candidates.set_index("candidate_id")

    rows = [r for res in results for r in _site_rows(res, cand, base)]
    sites = pd.DataFrame(rows)
    sites_gdf = gpd.GeoDataFrame(
        sites, geometry=gpd.points_from_xy(sites.longitude, sites.latitude) if len(sites) else [],
        crs=cfg.GEOGRAPHIC_CRS)
    if len(sites):  # which barangay each site falls in (for readability)
        j = gpd.sjoin(sites_gdf, model.barangays[["ADM4_EN", "ADM3_EN", "ADM2_EN", "geometry"]],
                      how="left", predicate="within")
        j = j[~j.index.duplicated()]
        for col in ("ADM4_EN", "ADM3_EN", "ADM2_EN"):
            sites_gdf[col] = j[col].to_numpy()
    sites_gdf.to_file(outdir / "recommended_sites.geojson", driver="GeoJSON")
    write_candidate_geojson(candidates, outdir / "candidate_sites.geojson")
    best.candidate_scores.drop(columns=["x_m", "y_m"]).to_csv(outdir / "candidate_scores.csv", index=False)

    # ---- barangay layer after, per combination (rank 1 keeps the plain name)
    for res in results:
        m = calculate_metrics(model.cells, res.state.current, model.params)
        ra = build_result_table(model.barangays, m, model.params)
        oa = build_overall(m, ra, model.params)
        suffix = "" if res.combination == 1 else f"_combo{res.combination}"
        write_accessibility_outputs(model.barangays, ra, oa,
                                    outdir / f"barangay_accessibility_after{suffix}.csv",
                                    outdir / f"barangay_accessibility_after{suffix}.geojson", None)

    # ---- summary
    def pair(res, key):
        return {"baseline": res.baseline[key], "final": res.final[key]}

    def combo_summary(res):
        wb, wf = res.baseline["weighted_mean_travel_time_min"], res.final["weighted_mean_travel_time_min"]
        n = res.network_impact
        return {
            "combination": res.combination, "generation_order": res.generation_order,
            "complete": len(res.selected) == res.requested,
            "candidate_ids": [s["candidate_id"] for s in res.selected],
            "network_score": n.combined_score,
            "network_coverage_score": n.coverage_score, "network_travel_score": n.travel_score,
            "network_equity_score": n.equity_score,
            "population_within_threshold": pair(res, "population_within_threshold"),
            "population_coverage_pct": pair(res, "population_coverage_pct"),
            "additional_population_covered": n.added_population,
            "weighted_mean_travel_time_min": pair(res, "weighted_mean_travel_time_min"),
            "weighted_mean_travel_time_reduction_min": None if wb is None else wb - wf,
            "barangays_meeting_target": pair(res, "barangays_meeting_target"),
            "mean_barangay_coverage_shortfall": pair(res, "mean_barangay_shortfall"),
            "stop_reason": res.stop_reason, "warnings": res.warnings,
        }

    summary = {
        "requested_hospitals": best.requested,
        "selected_hospitals": len(best.selected),
        "stop_reason": best.stop_reason,
        "alternatives_requested": requested_alternatives,
        "alternatives_returned": len(results),
        "alternative_separation_m": oparams.alternative_separation_m,
        "combinations": [combo_summary(r) for r in results],
        "combination_warnings": list(alt_warnings or []),
        # headline metrics below describe combination 1 (best network score)
        "population_within_threshold": pair(best, "population_within_threshold"),
        "population_coverage_pct": pair(best, "population_coverage_pct"),
        "additional_population_covered": best.network_impact.added_population,
        "weighted_mean_travel_time_min": pair(best, "weighted_mean_travel_time_min"),
        "weighted_mean_travel_time_reduction_min": combo_summary(best)["weighted_mean_travel_time_reduction_min"],
        "barangays_meeting_target": pair(best, "barangays_meeting_target"),
        "mean_barangay_coverage_shortfall": pair(best, "mean_barangay_shortfall"),
        "notes": {
            "combinations": "Combination 1 is the best-scoring network. Each later combination "
            "excludes candidates within alternative_separation_m of every site in earlier "
            "combinations, so combinations are different networks. Ranking uses the combined "
            "score of the whole network vs the baseline.",
            "cumulative_values": "Before/after values come from the final selected set, "
            "not from summing per-site gains. Per-site gains are marginal (scored "
            "after earlier selections in the same combination).",
            "weighted_mean_denominator": "Population reachable in the baseline (fixed "
            "across scenarios). Baseline-unreachable residents are counted by the "
            "coverage objective only.",
            "interpretation": "Preliminary potential locations on road nodes, not confirmed "
            "construction sites. Land availability, zoning, hazard exposure, capacity, "
            "staffing and feasibility must be reviewed. Greedy heuristic: no guarantee of "
            "a globally optimal set. Hospital capacity is not modelled.",
        },
        "assumptions": {
            "time_limit_minutes": model.params.time_limit_minutes,
            "barangay_coverage_target_pct": model.params.min_barangay_coverage_pct,
            "road_speed_kmh": model.params.speed_kmh,
            "default_road_speed_kmh": model.params.default_speed_kmh,
            "offroad_walking_speed_kmh": model.params.offroad_walking_kmh,
            "candidate_grid_spacing_m": cparams.grid_spacing_m,
            "candidate_grid_origin_xy_epsg32651": list(cparams.grid_origin_xy),
            "max_snap_distance_m": cparams.max_snap_m,
            "min_distance_to_existing_hospital_m": cparams.min_hospital_separation_m,
            "min_separation_between_new_sites_m": oparams.min_site_separation_m,
            "priority_filter": cparams.use_priority_filter,
            "priority_buffer_m": cparams.priority_buffer_m,
            "objective_weights": oparams.normalized_weights(),
            "normalisation_reference": {
                "coverage_ref_population_outside_threshold": best.reference.coverage_ref_pop,
                "travel_ref_weighted_mean_seconds": best.reference.travel_ref_seconds,
                "equity_ref_mean_shortfall": best.reference.equity_ref},
            "candidate_cutoff_seconds": oparams.candidate_cutoff_seconds,
        },
        "candidates": {
            "generated": int(len(candidates)),
            "eligible": int(candidates["eligible"].sum()),
            "excluded_by_reason": candidates.loc[~candidates["eligible"], "exclusion_reason"]
            .value_counts().to_dict(),
        },
        "versions": {"model": cfg.MODEL_VERSION, "fingerprints": {
            k: v for k, v in model.fingerprints.items() if not k.endswith("_key")}},
        "warnings": best.warnings,
        "consistency_check": best.consistency,
        "timings_s": best.timings,
    }
    if extra:
        summary.update(extra)
    with open(outdir / "scenario_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=_json_default, allow_nan=False)
    return summary


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    raise TypeError(type(o))


# ------------------------------------------------------------------ pipeline
def recommend_sites(k: int, n_alternatives: int = 1, params=cfg.ModelParams(),
                    cparams: CandidateParams = CandidateParams(),
                    oparams: OptimizerParams = OptimizerParams(), outdir=cfg.OUTPUT_DIR,
                    use_cache=True, verbose=True, write=True, model=None):
    """End-to-end: baseline -> candidates -> greedy selection (+alternatives) -> outputs.
    Returns (ranked results, candidates, summary)."""
    from backend.model.analyze_barangay import build_baseline_model
    t0 = time.time()
    model = model or build_baseline_model(params, use_cache=use_cache)
    t_model = time.time() - t0

    t0 = time.time()
    candidates = generate_candidates(model, cparams)
    t_gen = time.time() - t0
    n_ok = int(candidates["eligible"].sum())
    if verbose:
        print(f"Candidates: {len(candidates):,} grid points -> {n_ok:,} eligible "
              f"({t_gen:.1f}s). Excluded: "
              f"{candidates.loc[~candidates.eligible, 'exclusion_reason'].value_counts().to_dict()}")

    M = build_time_matrix(model.graph, model.node_index)
    store = CandidateFieldStore(
        M, model.node_seconds, model.fingerprints["baseline_digest"],
        cache_dir=cfg.CANDIDATE_CACHE_DIR if use_cache else None,
        cutoff_seconds=oparams.candidate_cutoff_seconds, batch=oparams.dijkstra_batch)
    cell_index = CellIndex.build(model.cells, len(model.node_index.node_ids))

    def make_state():
        return ScenarioState(model.cells, model.baseline_seconds, model.params, cell_index)

    results, alt_warns = find_alternatives(make_state, store, candidates, k, n_alternatives,
                                           oparams, verbose=verbose)
    for r in results:
        r.timings.update({"baseline_model_s": t_model, "candidate_generation_s": t_gen,
                          "fields_computed_this_run": store.n_computed})
    summary = None
    if write and results:
        summary = write_outputs(model, results, candidates, cparams, oparams, outdir,
                                requested_alternatives=n_alternatives, alt_warnings=alt_warns)
    return results, candidates, summary


def main():
    ap = argparse.ArgumentParser(description="Recommend k new hospital sites for Region III.")
    ap.add_argument("--k", type=int, required=True, help="number of new hospitals per combination")
    ap.add_argument("--alternatives", type=int, default=5,
                    help="number of different combinations (sets of k sites) to return")
    ap.add_argument("--alt-separation-km", type=float, default=5,
                    help="later combinations avoid sites within this distance of earlier ones "
                         "(default 5 km)")
    ap.add_argument("--outdir", default=str(cfg.OUTPUT_DIR))
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--no-priority-filter", action="store_true")
    ap.add_argument("--cutoff-min", type=float, default=None,
                    help="optional travel-time cutoff for candidate fields (approximation)")
    a = ap.parse_args()
    cp = CandidateParams(use_priority_filter=not a.no_priority_filter)
    kw = {} if a.alt_separation_km is None else {"alternative_separation_m": a.alt_separation_km * 1000}    
    op = OptimizerParams(candidate_cutoff_seconds=None if a.cutoff_min is None else a.cutoff_min * 60, **kw)
    results, _, summary = recommend_sites(a.k, a.alternatives, cparams=cp, oparams=op,
                                          outdir=a.outdir, use_cache=not a.no_cache)
    print(f"\n{len(results)} combination(s) of {a.k} hospital(s), ranked by network score:")
    for r in results:
        b, f = r.baseline, r.final
        print(f" #{r.combination}: {[s['candidate_id'] for s in r.selected]}  "
              f"coverage {b['population_coverage_pct']:.2f}% -> {f['population_coverage_pct']:.2f}%, "
              f"mean time {b['weighted_mean_travel_time_min']:.2f} -> {f['weighted_mean_travel_time_min']:.2f} min, "
              f"barangays at target {b['barangays_meeting_target']} -> {f['barangays_meeting_target']} "
              f"(score {r.network_impact.combined_score:.4f})")
        for w in r.warnings:
            print("   WARNING:", w)
    for w in (summary or {}).get("combination_warnings", []):
        print("WARNING:", w)
    print(f"Outputs in {a.outdir}")


if __name__ == "__main__":
    main()

#call site_optimizer by python3 site_optimizer.py --k num_of_hospitals