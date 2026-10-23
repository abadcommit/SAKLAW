# SAKLAW API Guide

This document explains how the frontend can call the SAKLAW backend, what data it can receive, and how to use the response to display possible healthcare facility locations on a map.

## 1. What the API does

The backend runs the SAKLAW model and returns candidate recommendations and accessibility metrics as JSON. The frontend's main responsibility is to display the returned possible locations clearly on an interactive map and let users inspect the supporting information.

**Important:** The recommended coordinates are preliminary candidate locations on the road network. They are not confirmed construction sites. Land availability, zoning, hazard exposure, staffing, facility capacity, and other feasibility factors still require review. The model is a greedy heuristic and does not guarantee a globally optimal network.

## 2. Start the backend

From the repository root, run:

```bash
python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000
```

Useful URLs while the backend is running:

- API documentation / interactive tester: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/api/health`

The API is configured to allow browser requests from `http://localhost:5173`. If the frontend runs on a different origin or port, the backend's CORS configuration may need to be updated.

## 3. Endpoints

### `GET /api/health`

Checks whether the API process is responding.

Example response:

```json
{
  "status": "ok",
  "service": "saklaw-api"
}
```

This endpoint does not run the model or return candidate locations.

### `POST /api/candidates`

Runs the site recommendation model and returns ranked combinations of possible new facility locations.

Full URL for local development:

```text
http://127.0.0.1:8000/api/candidates
```

Send a JSON request body with `Content-Type: application/json`.

## 4. Request body

All fields are optional; the backend uses the defaults shown below.

| Field | Type | Default | Valid values / meaning |
|---|---|---:|---|
| `k` | integer | `5` | Number of sites requested per combination; 1–100 |
| `alternatives` | integer | `5` | Number of alternative combinations requested; 1–20 |
| `alt_separation_km` | number | `5` | Separation distance in kilometres used to make later combinations geographically different; must be ≥ 0 |
| `use_cache` | boolean | `true` | Allows reuse of cached model calculations |
| `use_priority_filter` | boolean | `true` | Enables the model's candidate priority filter |

Example request:

```json
{
  "k": 5,
  "alternatives": 3,
  "alt_separation_km": 5,
  "use_cache": true,
  "use_priority_filter": true
}
```

The `k` value is the number of locations requested **in each combination**, not the total number across all combinations. The model can return fewer than `k` sites if it cannot justify additional candidates. It can also return fewer combinations than requested.

## 5. Example frontend request

Using `fetch` from a frontend running at the allowed local origin:

```javascript
const response = await fetch('http://127.0.0.1:8000/api/candidates', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    k: 5,
    alternatives: 3,
    alt_separation_km: 5,
    use_cache: true,
    use_priority_filter: true,
  }),
});

if (!response.ok) {
  const error = await response.json();
  throw new Error(error.detail ?? 'Failed to generate candidate locations');
}

const data = await response.json();
console.log(data);
```

Model runs can take a while, especially when candidate calculations need to be recomputed. The frontend should show a loading state while awaiting the response and an error state if the request fails. Avoid assuming that the request will finish instantly.

## 6. Response structure

The successful response has this top-level structure:

```json
{
  "status": "completed",
  "combinations_found": 3,
  "requested_sites_per_combination": 5,
  "summary": {},
  "combinations": [
    {
      "rank": 1,
      "sites": [],
      "baseline": {},
      "final": {},
      "network_impact": {},
      "warnings": [],
      "timings": {}
    }
  ]
}
```

The `{}` and `[]` values above are placeholders to illustrate the structure, not literal values returned by the model.

### Top-level fields

| Field | Meaning |
|---|---|
| `status` | Indicates the model completed successfully (`completed`) |
| `combinations_found` | Number of combinations actually returned |
| `requested_sites_per_combination` | Requested number of sites per combination (`k`) |
| `summary` | Overall model summary, including candidate counts, assumptions, version information, warnings, and headline metrics when available |
| `combinations` | Ranked alternative networks; each contains its selected sites and metrics |

### Each combination

| Field | Meaning |
|---|---|
| `rank` | Rank of this network by its overall combined score; rank 1 is the best-scoring returned network |
| `sites` | Selected locations for this combination, in selection order |
| `baseline` | Accessibility metrics before adding the selected sites |
| `final` | Accessibility metrics after adding all selected sites |
| `network_impact` | Aggregate impact of the whole selected network compared with baseline |
| `warnings` | Warnings or limitations associated with this combination |
| `timings` | Model timing information, useful for debugging/performance monitoring |

Each site's object contains the selected-site fields produced by the optimizer, plus `longitude` and `latitude` from the candidate table. The site fields include `candidate_id`, `selection_order`, and `impact` and `after` metric objects. The exact metric fields inside those objects are model-defined; use the response from the running backend or `/docs` to inspect the current full schema.

## 7. Displaying locations on the map

For the frontend's main map, use the `sites` array from the selected combination. Each site provides numeric `longitude` and `latitude` fields.

Example:

```javascript
const bestCombination = data.combinations.find(
  (combination) => combination.rank === 1
);

const mapLocations = (bestCombination?.sites ?? []).map((site) => ({
  id: site.candidate_id,
  longitude: site.longitude,
  latitude: site.latitude,
  selectionOrder: site.selection_order,
  impact: site.impact,
  after: site.after,
}));
```

Use `longitude` as the map's x-coordinate and `latitude` as its y-coordinate. Confirm your map library's expected coordinate order; GeoJSON coordinate arrays conventionally use `[longitude, latitude]`.

Suggested map behaviour:

1. Place a marker for each returned site in the chosen combination.
2. Let users select a marker to inspect its candidate ID, selection order, and available impact metrics.
3. Allow users to switch between combinations using `combinations`.
4. Display baseline-versus-final metrics from `baseline` and `final` to explain the expected network-level change.
5. Show warnings and explain that these are preliminary candidate locations, not confirmed construction sites.

The API response provides recommended point coordinates. It does not, by itself, provide a ready-made frontend map, map tiles, or a rendered map layer. The backend also writes GeoJSON/CSV/JSON output files to its configured output directory, but the POST response itself is JSON; the frontend should use the response body unless a separate file-serving endpoint is added.

## 8. Understanding alternatives and scores

- **Combination 1 / rank 1:** The best-scoring returned network according to the model's combined network score.
- **Later combinations:** Each combination excludes candidates within `alt_separation_km` of sites selected in earlier generated combinations. This is intended to produce geographically different networks.
- **Site order:** `selection_order` indicates the order in which a site was selected by the greedy algorithm.
- **Site impact vs network impact:** A site's `impact` is marginal—measured after earlier selections in the same combination. `network_impact` compares the complete selected set against the baseline. Do not sum individual site gains to estimate the network's final gain.
- **Fewer results than requested:** A combination may contain fewer than `k` sites if no remaining candidate sufficiently improves the model objectives. The API can also return fewer alternatives than requested.

Useful metric names may include `population_coverage_pct`, `weighted_mean_travel_time_min`, `additional_population_covered`, `barangays_meeting_target`, and `coverage_gain_pp`. Check whether a metric is a baseline/final pair, a per-site marginal value, or a network-level total before presenting it.

## 9. Errors and validation

### `422 Unprocessable Entity`

Returned when the request body is invalid, such as `k` outside 1–100, `alternatives` outside 1–20, a negative `alt_separation_km`, or values with the wrong type.

### `500 Internal Server Error`

If the model fails, the API returns a detail message similar to:

```json
{
  "detail": "SAKLAW model failed. Check the backend terminal."
}
```

Check the backend terminal for the traceback and underlying cause.

## 10. Frontend integration checklist

- [ ] Call `GET /api/health` to check that the backend is available.
- [ ] Send a JSON body to `POST /api/candidates`.
- [ ] Show a loading indicator while the model runs.
- [ ] Handle non-2xx responses and display a useful error.
- [ ] Read the selected combination's `sites` array.
- [ ] Plot each site's `longitude` and `latitude` on the map.
- [ ] Allow switching between returned combinations.
- [ ] Show baseline/final accessibility metrics and relevant warnings.
- [ ] Do not label candidate locations as approved or confirmed hospitals.

## 11. Scope and limitations

SAKLAW is a decision-support tool for preliminary healthcare facility site identification. The model's locations are road-network candidate points and require further local validation. The greedy selection method is a heuristic, not a proof of a globally optimal solution. Hospital capacity is not modelled. Treat model metrics as estimates based on the input data and configured assumptions, not guarantees of real-world outcomes.
