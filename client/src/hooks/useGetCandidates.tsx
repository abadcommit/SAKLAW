import { useState } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

type CandidateRequest = {
  k?: number;
  alternatives?: number;
  alt_separation_km?: number;
  use_cache?: boolean;
  use_priority_filter?: boolean;
};

export type CandidateSite = {
  candidate_id: string | number;
  selection_order?: number;
  longitude: number;
  latitude: number;
  [key: string]: unknown;
};

export type CandidateCombination = {
  rank: number;
  sites: CandidateSite[];
  baseline: unknown;
  final: unknown;
  network_impact: Record<string, unknown>;
  warnings: unknown[];
  timings: Record<string, unknown>;
};

export type CandidateResponse = {
  status: string;
  combinations_found: number;
  requested_sites_per_combination: number;
  summary: unknown;
  combinations: CandidateCombination[];
};

export function useGetCandidates() {
  const [data, setData] = useState<CandidateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function getCandidates(params: CandidateRequest = {}) {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_URL}/api/candidates`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          k: 5,
          alternatives: 5,
          alt_separation_km: 5,
          use_cache: true,
          use_priority_filter: true,
          ...params,
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed (${response.status})`);
      }

      const result: CandidateResponse = await response.json();
      setData(result);
      return result;
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong";

      setError(message);
      return null;
    } finally {
      setLoading(false);
    }
  }

  return { data, loading, error, getCandidates };
}
