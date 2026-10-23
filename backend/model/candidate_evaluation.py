"""Evaluate hypothetical hospitals against the baseline accessibility model.

Key ideas
---------
* Candidate travel-time field: ONE single-source Dijkstra on the reversed road
  graph (scipy's C implementation) gives, for every road node n, the time D[n]
  from n TO the candidate in the original, possibly one-way, graph.
* Cell time to the candidate = connector[cell] + D[nearest_node[cell]], i.e.
  exactly the baseline's definition (connector counted once).
* Only nodes where D[n] < baseline_node_time[n] are stored. This is EXACT, not
  an approximation: scenario times only ever decrease from baseline, so a node
  that does not beat the baseline can never beat any later scenario either.
* Scenario updates are vectorised and incremental: only cells attached to the
  candidate's improving nodes are touched.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

import backend.model.config as cfg
from backend.model.config import ModelParams, OptimizerParams


# ------------------------------------------------------------ road matrix
def build_time_matrix(G, node_index) -> csr_matrix:
    """Sparse N x N matrix, M[u, v] = fastest single-edge time u -> v (seconds).

    Parallel edges are reduced to their minimum. Undirected graphs are
    symmetrised. Weights are floored at 1e-9 so scipy never sees an
    'absent' zero-weight edge."""
    idx = node_index.id_to_index
    us, vs, ts = [], [], []
    for u, v, d in G.edges(data=True):
        t = max(float(d["travel_time"]), 1e-9)
        us.append(idx[u]); vs.append(idx[v]); ts.append(t)
        if not G.is_directed():
            us.append(idx[v]); vs.append(idx[u]); ts.append(t)
    df = pd.DataFrame({"u": us, "v": vs, "t": ts}).groupby(["u", "v"], as_index=False)["t"].min()
    n = len(node_index.node_ids)
    return csr_matrix((df["t"].to_numpy(), (df["u"].to_numpy(), df["v"].to_numpy())), shape=(n, n))


# ------------------------------------------------------------ candidate fields
@dataclass
class CandidateField:
    node_idx: np.ndarray  # road nodes that this candidate would IMPROVE
    seconds: np.ndarray  # time from each of those nodes to the candidate


class CandidateFieldStore:
    """Computes and caches candidate travel-time fields.

    The cache file name and its embedded metadata include the baseline
    fingerprint (graph file, speeds, hospital file, ...) and the cutoff, so an
    incompatible field is never reused after any assumption changes."""

    def __init__(self, time_matrix, baseline_node_seconds, fingerprint: dict,
                 cache_dir=cfg.CANDIDATE_CACHE_DIR, cutoff_seconds=None, batch=32):
        self.MT = time_matrix.T.tocsr()  # reversed graph
        self.base = np.asarray(baseline_node_seconds)
        self.cutoff = cutoff_seconds
        self.batch = batch
        self.meta = {"baseline": fingerprint, "cutoff_seconds": cutoff_seconds,
                     "n_nodes": int(len(self.base))}
        self.key = cfg.digest(self.meta)
        self.path = None if cache_dir is None else Path(cache_dir) / f"fields_{self.key}.npz"
        self.fields: dict[int, CandidateField] = {}
        self.n_computed = 0
        self._load()

    def _load(self):
        if self.path is None or not self.path.exists():
            return
        with np.load(self.path, allow_pickle=False) as z:
            if json.loads(str(z["meta"])) != json.loads(json.dumps(self.meta, sort_keys=True,
                                                                   default=str)):
                return  # incompatible: ignore silently-safe, recompute
            nodes, ptr, ni, sec = z["cand_nodes"], z["ptr"], z["node_idx"], z["seconds"]
        for k, c in enumerate(nodes):
            self.fields[int(c)] = CandidateField(ni[ptr[k]:ptr[k + 1]], sec[ptr[k]:ptr[k + 1]])

    def save(self):
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        nodes = np.array(sorted(self.fields), dtype=np.int64)
        lens = np.array([len(self.fields[int(c)].node_idx) for c in nodes], dtype=np.int64)
        ptr = np.concatenate([[0], np.cumsum(lens)])
        ni = (np.concatenate([self.fields[int(c)].node_idx for c in nodes])
              if len(nodes) else np.zeros(0, np.int32))
        sec = (np.concatenate([self.fields[int(c)].seconds for c in nodes])
               if len(nodes) else np.zeros(0))
        np.savez(self.path, cand_nodes=nodes, ptr=ptr, node_idx=ni, seconds=sec,
                 meta=json.dumps(self.meta, sort_keys=True, default=str))

    def ensure(self, node_indices) -> int:
        """Compute any missing fields; returns how many were computed."""
        missing = [int(c) for c in dict.fromkeys(node_indices) if int(c) not in self.fields]
        limit = np.inf if self.cutoff is None else float(self.cutoff)
        for i in range(0, len(missing), self.batch):
            chunk = missing[i:i + self.batch]
            D = dijkstra(self.MT, directed=True, indices=chunk, limit=limit)
            for r, c in enumerate(chunk):
                row = D[r]
                sel = np.flatnonzero(row < self.base)
                self.fields[c] = CandidateField(sel.astype(np.int32), row[sel])
        if missing:
            self.n_computed += len(missing)
            self.save()
        return len(missing)

    def get(self, node_index: int) -> CandidateField:
        if int(node_index) not in self.fields:
            self.ensure([node_index])
        return self.fields[int(node_index)]


# ------------------------------------------------------------ cell index
@dataclass
class CellIndex:
    """node -> cells lookup (CSR). Built once, shared by all scenarios."""
    order: np.ndarray
    ptr: np.ndarray

    @classmethod
    def build(cls, cells, n_nodes):
        order = np.argsort(cells.nearest_node_index, kind="stable")
        counts = np.bincount(cells.nearest_node_index, minlength=n_nodes)
        return cls(order, np.concatenate([[0], np.cumsum(counts)]))


# ------------------------------------------------------------ objective scores
@dataclass
class ObjectiveReference:
    """Fixed baseline reference values used to normalise each objective, so
    scores stay comparable across selection rounds."""
    coverage_ref_pop: float
    travel_ref_seconds: float
    equity_ref: float
    warnings: list = field(default_factory=list)

    @classmethod
    def from_state(cls, st: "ScenarioState"):
        w = []
        cov = st.total_pop - st.covered_total
        trav = st.weighted_mean_seconds()
        eq = st.mean_shortfall()
        for name, v in (("population outside threshold", cov),
                        ("baseline weighted mean travel time", trav),
                        ("baseline mean barangay shortfall", eq)):
            if not (v and v > 0):
                w.append(f"{name} is zero/undefined: that objective contributes 0.")
        return cls(float(cov), float(trav or 0), float(eq), w)


@dataclass
class Impact:
    added_population: float = 0.0
    coverage_gain_pp: float = 0.0
    weighted_time_reduction_min: float = 0.0
    equity_shortfall_reduction: float = 0.0  # mean-shortfall units (fraction of 1)
    barangays_meeting_target_gain: int = 0
    improved_cells: int = 0
    coverage_score: float = 0.0
    travel_score: float = 0.0
    equity_score: float = 0.0
    combined_score: float = 0.0


def _clamp01(x):
    return float(min(1.0, max(0.0, x)))


def score_impact(imp: Impact, ref: ObjectiveReference, weights: dict) -> Impact:
    imp.coverage_score = (_clamp01(imp.added_population / ref.coverage_ref_pop)
                          if ref.coverage_ref_pop > 0 else 0.0)
    imp.travel_score = (_clamp01(imp.weighted_time_reduction_min * 60 / ref.travel_ref_seconds)
                        if ref.travel_ref_seconds > 0 else 0.0)
    imp.equity_score = (_clamp01(imp.equity_shortfall_reduction / ref.equity_ref)
                        if ref.equity_ref > 0 else 0.0)
    imp.combined_score = (weights["coverage"] * imp.coverage_score
                          + weights["travel"] * imp.travel_score
                          + weights["equity"] * imp.equity_score)
    return imp


@dataclass
class ChangeSummary:
    """What a committed selection changed (drives incremental re-scoring)."""
    changed_nodes: np.ndarray
    zones_coverage_changed: np.ndarray
    improved_cells: int


class _Change:
    __slots__ = ("cells", "new", "cur", "pop", "zu", "delta", "wsec", "impact", "touched")


# ------------------------------------------------------------ scenario state
class ScenarioState:
    """Current per-cell travel times plus running aggregates.

    Weighted mean travel time is computed over the population that is
    reachable in the BASELINE (fixed denominator, so scenarios are comparable);
    residents unreachable in the baseline are excluded from that mean and are
    covered by the coverage objective instead."""

    def __init__(self, cells, baseline_seconds, params: ModelParams, cell_index: CellIndex):
        self.cells, self.params, self.ci = cells, params, cell_index
        self.baseline = np.asarray(baseline_seconds)
        self.current = self.baseline.copy()  # never overwrite self.baseline
        self.limit = params.limit_seconds
        self.target = params.min_barangay_coverage_pct
        z, p, n = cells.zone_index, cells.population, cells.n_zones
        self.zone_total = np.bincount(z, weights=p, minlength=n)
        cov = self.current <= self.limit
        self.zone_covered = np.bincount(z[cov], weights=p[cov], minlength=n)
        self.ref_mask = np.isfinite(self.baseline)
        self.ref_pop = float(p[self.ref_mask].sum())
        self.weighted_time_sum = float((p[self.ref_mask] * self.current[self.ref_mask]).sum())
        self.valid_zone = self.zone_total > 0
        self.n_valid = int(self.valid_zone.sum())
        self.total_pop = float(self.zone_total.sum())
        self.covered_total = float(self.zone_covered.sum())

    # ---- aggregates
    def zone_pct(self):
        return np.divide(self.zone_covered, self.zone_total, out=np.full(len(self.zone_total), np.nan),
                         where=self.valid_zone) * 100

    def mean_shortfall(self):
        pct = self.zone_pct()[self.valid_zone]
        return float(np.maximum(0.0, self.target - pct).sum() / 100 / self.n_valid)

    def barangays_meeting_target(self):
        pct = self.zone_pct()
        return int(np.sum(self.valid_zone & (pct >= self.target)))

    def weighted_mean_seconds(self):
        return self.weighted_time_sum / self.ref_pop if self.ref_pop > 0 else None

    def snapshot(self) -> dict:
        wm = self.weighted_mean_seconds()
        return {
            "population_within_threshold": self.covered_total,
            "population_coverage_pct": 100 * self.covered_total / self.total_pop,
            "weighted_mean_travel_time_min": None if wm is None else wm / 60,
            "barangays_meeting_target": self.barangays_meeting_target(),
            "mean_barangay_shortfall": self.mean_shortfall(),
        }

    # ---- candidate application
    def _gather(self, field: CandidateField):
        ci, cells = self.ci, self.cells
        nodes = field.node_idx
        counts = ci.ptr[nodes + 1] - ci.ptr[nodes]
        total = int(counts.sum())
        if total == 0:
            return None, None
        rep = np.repeat(np.arange(len(nodes)), counts)
        within = np.arange(total) - np.repeat(np.cumsum(counts) - counts, counts)
        idx = ci.order[ci.ptr[nodes][rep] + within]
        new = cells.connector_seconds[idx] + field.seconds[rep]
        return idx, new

    def _compute(self, field: CandidateField, want_touched: bool = False) -> _Change:
        ch = _Change()
        ch.impact = Impact()
        idx, new = self._gather(field)
        ch.touched = (np.zeros(0, np.int64) if idx is None else
                      np.unique(self.cells.zone_index[idx])) if want_touched else None
        empty = idx is None
        if not empty:
            cur = self.current[idx]
            imp = new < cur
            idx, new, cur = idx[imp], new[imp], cur[imp]
            empty = len(idx) == 0
        if empty:
            ch.cells = ch.new = ch.cur = ch.pop = np.zeros(0)
            ch.zu = ch.delta = np.zeros(0)
            ch.wsec = 0.0
            return ch
        p = self.cells.population[idx]
        zc = self.cells.zone_index[idx]
        newly = (new <= self.limit) & (cur > self.limit)
        added = float(p[newly].sum())
        rm = self.ref_mask[idx]
        wsec = float((p[rm] * (cur[rm] - new[rm])).sum())
        zu, inv = np.unique(zc[newly], return_inverse=True)
        delta = np.bincount(inv, weights=p[newly], minlength=len(zu))
        gain_meet, eq_red = 0, 0.0
        if len(zu):
            tot = self.zone_total[zu]
            old_cov = self.zone_covered[zu]
            old_pct = old_cov / tot * 100
            new_pct = (old_cov + delta) / tot * 100
            eq_red = float((np.maximum(0, self.target - old_pct).sum()
                            - np.maximum(0, self.target - new_pct).sum()) / 100 / self.n_valid)
            gain_meet = int(np.sum((old_pct < self.target) & (new_pct >= self.target)))
        i = ch.impact
        i.added_population = added
        i.coverage_gain_pp = 100 * added / self.total_pop
        i.weighted_time_reduction_min = (wsec / self.ref_pop / 60) if self.ref_pop > 0 else 0.0
        i.equity_shortfall_reduction = eq_red
        i.barangays_meeting_target_gain = gain_meet
        i.improved_cells = int(len(idx))
        ch.cells, ch.new, ch.cur, ch.pop, ch.zu, ch.delta, ch.wsec = idx, new, cur, p, zu, delta, wsec
        return ch

    def evaluate(self, field: CandidateField, ref: ObjectiveReference, weights: dict) -> Impact:
        """Marginal impact of adding this candidate to the CURRENT scenario."""
        return score_impact(self._compute(field).impact, ref, weights)

    def evaluate_with_touched(self, field: CandidateField, ref: ObjectiveReference, weights: dict):
        """Like evaluate(), also returning barangays containing any cell the
        candidate could affect (used to decide when to re-score it)."""
        ch = self._compute(field, want_touched=True)
        return score_impact(ch.impact, ref, weights), ch.touched

    def touched_zones(self, field: CandidateField) -> np.ndarray:
        """Barangays containing any cell the candidate could affect."""
        idx, _ = self._gather(field)
        return np.zeros(0, np.int64) if idx is None else np.unique(self.cells.zone_index[idx])

    def apply(self, field: CandidateField) -> ChangeSummary:
        """Commit a candidate: T_new = min(T_current, T_candidate)."""
        ch = self._compute(field)
        if len(ch.cells):
            self.current[ch.cells] = ch.new
            self.zone_covered[ch.zu] += ch.delta
            self.covered_total += ch.impact.added_population
            self.weighted_time_sum -= ch.wsec
        return ChangeSummary(
            np.unique(self.cells.nearest_node_index[ch.cells]) if len(ch.cells) else np.zeros(0, np.int64),
            ch.zu, ch.impact.improved_cells)
