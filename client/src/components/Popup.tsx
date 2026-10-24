import { useState, type ReactNode } from "react";
import styles from "../stylesheets/Popup.module.css";
import {
  ChevronDown,
  ChevronRight,
  Download,
  Maximize,
  Minimize,
} from "lucide-react";
import { Draggable } from "../hooks/useDraggable";
import type { CandidateRequest, CandidateSite } from "../hooks/useGetCandidates";

interface PopupProps {
  onSuggest: (params: CandidateRequest) => Promise<void>;
  loading: boolean;
  error: string | null;
  ranks: number[];
  rank?: number;
  onRankChange: (rank: number) => void;
  showHospitals: boolean;
  onShowHospitalsChange: (visible: boolean) => void;
  showPopulation: boolean;
  onShowPopulationChange: (visible: boolean) => void;
  sites?: CandidateSite[];
  baseline?: unknown;
  final?: unknown;
  impact?: unknown;
  warnings?: unknown[];
}

function csvValue(value: unknown): string {
  let text: string;

  if (value === null || value === undefined) {
    text = "";
  } else if (typeof value === "object") {
    text = JSON.stringify(value);
  } else {
    text = String(value);
  }

  // Prevent spreadsheet applications from interpreting text as a formula.
  if (typeof value === "string" && /^[=+@\t\r]/.test(text)) {
    text = `'${text}`;
  }

  return `"${text.replace(/"/g, '""')}"`;
}

function exportCandidates(sites: CandidateSite[], rank?: number) {
  if (sites.length === 0) return;

  // Include all fields returned for any candidate, not just coordinates.
  const columns = Array.from(
    new Set(sites.flatMap((site) => Object.keys(site))),
  );
  const rows = [
    columns.map((column) => csvValue(column)).join(","),
    ...sites.map((site) =>
      columns.map((column) => csvValue(site[column])).join(","),
    ),
  ];
  const csv = `\uFEFF${rows.join("\r\n")}`;
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `saklaw-candidates-rank-${rank ?? 1}.csv`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    return undefined;
  }
  return value as Record<string, unknown>;
}

function metric(record: Record<string, unknown> | undefined, key: string) {
  const value = record?.[key];
  return typeof value === "number" && Number.isFinite(value)
    ? value
    : undefined;
}

function formatNumber(value: number | undefined, decimals = 0): string {
  if (value === undefined) return "—";
  return value.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}

function signed(value: number | undefined, decimals = 2): string {
  if (value === undefined) return "—";
  const prefix = value > 0 ? "+" : value < 0 ? "−" : "";
  return `${prefix}${formatNumber(Math.abs(value), decimals)}`;
}

function PopupHeader({ togglePopup }: { togglePopup: () => void }) {
  return (
    <>
      <div className={styles["popup-header-wrapper"]}>
        <h1>SAKLAW</h1>
        <button
          type="button"
          className={styles["icon-button"]}
          onClick={togglePopup}
          aria-label="Minimize popup"
          title="Minimize popup"
        >
          <Minimize size={18} />
        </button>
      </div>
      <h2 id={styles["popup-tagline"]}>Healthcare Accessibility Planning</h2>
    </>
  );
}

function CollapsibleSection({
  title,
  summary,
  defaultOpen = false,
  children,
}: {
  title: string;
  summary?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const contentId = `section-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-")}`;

  return (
    <section className={styles["collapsible-section"]}>
      <button
        type="button"
        className={styles["section-toggle"]}
        aria-expanded={isOpen}
        aria-controls={contentId}
        onClick={() => setIsOpen((open) => !open)}
      >
        <span className={styles["section-heading-content"]}>
          <strong>{title}</strong>
          {!isOpen && summary && (
            <span className={styles["section-summary"]}>{summary}</span>
          )}
        </span>
        {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
      </button>
      {isOpen && (
        <div id={contentId} className={styles["section-content"]}>
          {children}
        </div>
      )}
    </section>
  );
}

function SliderParameter({
  id,
  label,
  value,
  min,
  max,
  step = 1,
  suffix = "",
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  suffix?: string;
  onChange: (value: number) => void;
}) {
  return (
    <div className={styles["slider-parameter"]}>
      <div className={styles["slider-label-row"]}>
        <label htmlFor={id}>{label}</label>
        <output htmlFor={id} className={styles["slider-value"]}>
          {value}{suffix}
        </output>
      </div>
      <input
        id={id}
        className={styles["parameter-slider"]}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      <div className={styles["slider-range"]}>
        <span>{min}{suffix}</span>
        <span>{max}{suffix}</span>
      </div>
    </div>
  );
}

function AccessibilityImpact({
  baseline,
  final,
  impact,
  warnings,
}: {
  baseline?: unknown;
  final?: unknown;
  impact?: unknown;
  warnings?: unknown[];
}) {
  const before = asRecord(baseline);
  const after = asRecord(final);
  const networkImpact = asRecord(impact);

  const beforeCoverage = metric(before, "population_coverage_pct");
  const afterCoverage = metric(after, "population_coverage_pct");
  const beforePopulation = metric(before, "population_within_threshold");
  const afterPopulation = metric(after, "population_within_threshold");
  const beforeTravel = metric(before, "weighted_mean_travel_time_min");
  const afterTravel = metric(after, "weighted_mean_travel_time_min");
  const beforeBarangays = metric(before, "barangays_meeting_target");
  const afterBarangays = metric(after, "barangays_meeting_target");
  const beforeShortfall = metric(before, "mean_barangay_shortfall");
  const afterShortfall = metric(after, "mean_barangay_shortfall");

  const coverageGain =
    metric(networkImpact, "coverage_gain_pp") ??
    (beforeCoverage !== undefined && afterCoverage !== undefined
      ? afterCoverage - beforeCoverage
      : undefined);
  const populationGain =
    metric(networkImpact, "added_population") ??
    (beforePopulation !== undefined && afterPopulation !== undefined
      ? afterPopulation - beforePopulation
      : undefined);
  const travelReduction =
    metric(networkImpact, "weighted_time_reduction_min") ??
    (beforeTravel !== undefined && afterTravel !== undefined
      ? beforeTravel - afterTravel
      : undefined);
  const barangayGain =
    metric(networkImpact, "barangays_meeting_target_gain") ??
    (beforeBarangays !== undefined && afterBarangays !== undefined
      ? afterBarangays - beforeBarangays
      : undefined);
  const shortfallReduction =
    metric(networkImpact, "equity_shortfall_reduction") ??
    (beforeShortfall !== undefined && afterShortfall !== undefined
      ? beforeShortfall - afterShortfall
      : undefined);

  const hasData = Boolean(before || after || networkImpact);

  if (!hasData) {
    return (
      <p className={styles["impact-empty"]}>
        Generate candidate sites to view the estimated accessibility changes for
        the selected solution.
      </p>
    );
  }

  return (
    <div className={styles["accessibility-content"]}>
      <div className={styles["impact-highlight"]}>
        <span>Population coverage within 30 minutes</span>
        <strong>{coverageGain === undefined ? "—" : `${signed(coverageGain)} pp`}</strong>
        <small>
          {beforeCoverage === undefined ? "—" : `${formatNumber(beforeCoverage, 2)}%`}
          {" → "}
          {afterCoverage === undefined ? "—" : `${formatNumber(afterCoverage, 2)}%`}
        </small>
      </div>

      <div className={styles["impact-grid"]}>
        <div className={styles["impact-card"]}>
          <span>Additional population covered</span>
          <strong>
            {populationGain === undefined ? "—" : `+${formatNumber(populationGain)}`}
          </strong>
        </div>
        <div className={styles["impact-card"]}>
          <span>Mean travel time</span>
          <strong>
            {travelReduction === undefined
              ? "—"
              : `${formatNumber(travelReduction, 2)} min lower`}
          </strong>
          <small>
            {formatNumber(beforeTravel, 2)} → {formatNumber(afterTravel, 2)} min
          </small>
        </div>
        <div className={styles["impact-card"]}>
          <span>Barangays meeting target</span>
          <strong>{barangayGain === undefined ? "—" : signed(barangayGain, 0)}</strong>
          <small>
            {formatNumber(beforeBarangays)} → {formatNumber(afterBarangays)}
          </small>
        </div>
        <div className={styles["impact-card"]}>
          <span>Mean coverage shortfall</span>
          <strong>
            {shortfallReduction === undefined
              ? "—"
              : `${formatNumber(shortfallReduction * 100, 2)} pp lower`}
          </strong>
          <small>
            {beforeShortfall === undefined
              ? "—"
              : `${formatNumber(beforeShortfall * 100, 2)}%`}
            {" → "}
            {afterShortfall === undefined
              ? "—"
              : `${formatNumber(afterShortfall * 100, 2)}%`}
          </small>
        </div>
      </div>

      <div className={styles["metric-table-wrapper"]}>
        <h3>Before vs. after</h3>
        <div className={styles["metric-table"]}>
          <div className={styles["metric-table-header"]}>
            <span>Metric</span>
            <span>Existing</span>
            <span>With sites</span>
          </div>
          <div className={styles["metric-table-row"]}>
            <span>Population within 30 min</span>
            <span>{formatNumber(beforePopulation)}</span>
            <span>{formatNumber(afterPopulation)}</span>
          </div>
          <div className={styles["metric-table-row"]}>
            <span>Population coverage</span>
            <span>{beforeCoverage === undefined ? "—" : `${formatNumber(beforeCoverage, 2)}%`}</span>
            <span>{afterCoverage === undefined ? "—" : `${formatNumber(afterCoverage, 2)}%`}</span>
          </div>
          <div className={styles["metric-table-row"]}>
            <span>Weighted mean travel time</span>
            <span>{beforeTravel === undefined ? "—" : `${formatNumber(beforeTravel, 2)} min`}</span>
            <span>{afterTravel === undefined ? "—" : `${formatNumber(afterTravel, 2)} min`}</span>
          </div>
          <div className={styles["metric-table-row"]}>
            <span>Barangays meeting target</span>
            <span>{formatNumber(beforeBarangays)}</span>
            <span>{formatNumber(afterBarangays)}</span>
          </div>
        </div>
      </div>

      {warnings && warnings.length > 0 && (
        <div className={styles["impact-warnings"]}>
          <strong>Model warnings</strong>
          {warnings.map((warning, index) => (
            <p key={`${index}-${String(warning)}`}>{String(warning)}</p>
          ))}
        </div>
      )}

      <p className={styles["impact-note"]}>
        These are model estimates comparing the existing healthcare network with
        the selected set of candidate sites, not guarantees of real-world
        outcomes. Candidate locations are preliminary and are not confirmed
        construction sites.
      </p>
    </div>
  );
}

export default function Popup({
  onSuggest,
  loading,
  error,
  ranks,
  rank,
  onRankChange,
  showHospitals,
  onShowHospitalsChange,
  showPopulation,
  onShowPopulationChange,
  sites = [],
  baseline,
  final,
  impact,
  warnings,
}: PopupProps) {
  const [isOpen, setIsOpen] = useState(true);
  const [k, setK] = useState(5);
  const [alternatives, setAlternatives] = useState(5);
  const [separation, setSeparation] = useState(5);
  const [usePriorityFilter, setUsePriorityFilter] = useState(true);

  function togglePopup() {
    setIsOpen((open) => !open);
  }

  if (!isOpen) {
    return (
      <button
        type="button"
        className={styles["popup-wrapper-closed"]}
        onClick={togglePopup}
        aria-label="Expand Saklaw popup"
        title="Expand popup"
      >
        <Maximize size={18} />
      </button>
    );
  }

  return (
    <Draggable>
      <div className={styles["popup-wrapper-open"]}>
        <PopupHeader togglePopup={togglePopup} />

        <CollapsibleSection title="Parameters" summary={`${k} sites · ${alternatives} alternatives`}>
          <div className={styles["param-select-wrapper"]}>
            <SliderParameter
              id="sites-per-combination"
              label="Sites per combination"
              value={k}
              min={1}
              max={100}
              onChange={setK}
            />

            <div className={styles["parameter-divider"]} />

            <div className={styles["parameter-group-heading"]}>
              <h2>Alternative solutions</h2>
              <p>Explore different site combinations.</p>
            </div>

            <SliderParameter
              id="alternatives"
              label="Number of alternatives"
              value={alternatives}
              min={1}
              max={20}
              onChange={setAlternatives}
            />

            <SliderParameter
              id="separation"
              label="Minimum separation"
              value={separation}
              min={0}
              max={50}
              suffix=" km"
              onChange={setSeparation}
            />

            <div className={styles["priority-toggle"]}>
              <div>
                <span>Priority areas only</span>
                <p>Apply the model's priority-area filter.</p>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={usePriorityFilter}
                aria-label="Restrict candidates to priority areas"
                className={`${styles["toggle-switch"]} ${
                  usePriorityFilter ? styles["toggle-switch-active"] : ""
                }`}
                onClick={() => setUsePriorityFilter((enabled) => !enabled)}
              >
                <span />
              </button>
            </div>

            <p className={styles["cache-note"]}>
              <span className={styles["cache-dot"]} />
              Cache enabled
            </p>
          </div>
        </CollapsibleSection>

        <CollapsibleSection
          title="Map layers"
          summary={`${showHospitals ? "Hospitals on" : "Hospitals off"} · ${showPopulation ? "Population on" : "Population off"}`}
        >
          <div className={styles["map-layers-section"]}>
            <label className={styles["layer-toggle"]}>
              <span className={styles["layer-label"]}>
                <span className={styles["legend-dot"]} />
                Existing hospitals
              </span>
              <input
                type="checkbox"
                checked={showHospitals}
                onChange={(event) => onShowHospitalsChange(event.target.checked)}
              />
            </label>

            <label className={styles["layer-toggle"]}>
              <span className={styles["layer-label"]}>
                <span className={styles["legend-heat"]} />
                Population density
              </span>
              <input
                type="checkbox"
                checked={showPopulation}
                onChange={(event) => onShowPopulationChange(event.target.checked)}
              />
            </label>
          </div>
        </CollapsibleSection>

        <CollapsibleSection
          title="Suggested solutions"
          summary={ranks.length > 0 ? `${ranks.length} available` : "Not generated"}
        >
          {ranks.length > 0 && (
            <div className={styles["rank-section"]}>
              <label htmlFor="candidate-rank">Select a network</label>
              <select
                id="candidate-rank"
                value={rank ?? ranks[0]}
                onChange={(event) => onRankChange(Number(event.target.value))}
              >
                {ranks.map((availableRank) => (
                  <option key={availableRank} value={availableRank}>
                    Rank {availableRank}{availableRank === 1 ? " (Recommended)" : ""}
                  </option>
                ))}
              </select>
            </div>
          )}

          <button
            type="button"
            className={styles["candidate-button"]}
            onClick={() =>
              void onSuggest({
                k,
                alternatives,
                alt_separation_km: separation,
                use_priority_filter: usePriorityFilter,
              })
            }
            disabled={loading}
          >
            {loading ? "Finding candidates..." : "Get Candidates"}
          </button>
          {error && <p role="alert">{error}</p>}

          {sites.length > 0 ? (
            <div className={styles["candidate-results"]}>
              <div className={styles["candidate-results-header"]}>
                <p>
                  {sites.length} candidate {sites.length === 1 ? "site" : "sites"}
                  {rank !== undefined ? ` · Rank ${rank}` : ""}
                </p>
                <button
                  type="button"
                  className={styles["export-button"]}
                  onClick={() => exportCandidates(sites, rank)}
                  title="Download the selected solution as a CSV file"
                >
                  <Download size={15} />
                  Export CSV
                </button>
              </div>

              <ol className={styles["candidate-list"]}>
                {sites.map((site, index) => (
                  <li
                    key={`${String(site.candidate_id)}-${index}`}
                    className={styles["candidate-item"]}
                  >
                    <strong>
                      Site {site.selection_order ?? index + 1}
                      {site.candidate_id !== undefined
                        ? ` · ID ${site.candidate_id}`
                        : ""}
                    </strong>
                    <span>Latitude: {site.latitude}</span>
                    <span>Longitude: {site.longitude}</span>
                  </li>
                ))}
              </ol>
              <p className={styles["candidate-list-note"]}>
                The CSV contains the fields returned for each site in the selected solution.
              </p>
            </div>
          ) : (
            <p className={styles["candidate-list-empty"]}>
              {ranks.length > 0
                ? "No candidate sites are available for this solution."
                : "Generate candidates to see the proposed sites here."}
            </p>
          )}
        </CollapsibleSection>

        <CollapsibleSection
          title="Accessibility impact"
          summary={
            metric(asRecord(impact), "coverage_gain_pp") === undefined
              ? "Before vs. after"
              : `${signed(metric(asRecord(impact), "coverage_gain_pp"))} pp coverage`
          }
          defaultOpen
        >
          <AccessibilityImpact
            baseline={baseline}
            final={final}
            impact={impact}
            warnings={warnings}
          />
        </CollapsibleSection>
      </div>
    </Draggable>
  );
}
