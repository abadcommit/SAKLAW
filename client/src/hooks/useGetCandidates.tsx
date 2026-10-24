import { useRef, useState, useCallback } from "react";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8000";
const STORAGE_KEY = "saklaw:candidates:v1";

export type CandidateRequest = {
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

function loadSavedCandidates(): CandidateResponse | null {
	try {
		if (typeof window === "undefined") {
			return null;
		}

		const saved = window.localStorage.getItem(STORAGE_KEY);

		if (!saved) {
			return null;
		}

		const parsed: unknown = JSON.parse(saved);

		if (
			typeof parsed === "object" &&
			parsed !== null &&
			"combinations" in parsed &&
			Array.isArray(parsed.combinations)
		) {
			return parsed as CandidateResponse;
		}
	} catch {
		// Ignore invalid or unavailable saved data.
	}

	return null;
}

export function useGetCandidates() {
	const [data, setData] = useState<CandidateResponse | null>(
		() => loadSavedCandidates(),
	);
	const [loading, setLoading] = useState(false);
	const [error, setError] = useState<string | null>(null);

	// Prevent duplicate requests before React updates loading state.
	const requestInProgress = useRef(false);

	const getCandidates = useCallback(async (params: CandidateRequest = {}) => {
		if (requestInProgress.current) {
			return null;
		}

		requestInProgress.current = true;
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
					use_priority_filter: true,
					...params,
					use_cache: true,
				}),
			});

			if (!response.ok) {
				const details = await response.text();
				throw new Error(
					details || `Request failed (${response.status})`,
				);
			}

			const result: CandidateResponse = await response.json();

			if (!Array.isArray(result.combinations)) {
				throw new Error("Invalid API response: missing combinations.");
			}

			setData(result);

			// Persist the latest successful result across page reloads.
			try {
				window.localStorage.setItem(
					STORAGE_KEY,
					JSON.stringify(result),
				);
			} catch {
				// The current session still works if storage is unavailable.
				console.warn("Could not save candidates to localStorage.");
			}

			return result;
		} catch (err) {
			const message =
				err instanceof Error
					? err.message
					: "Something went wrong while fetching candidates.";

			setError(message);
			return null;
		} finally {
			requestInProgress.current = false;
			setLoading(false);
		}
	}, []);

	return { data, loading, error, getCandidates };
}