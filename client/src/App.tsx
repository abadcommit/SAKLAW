import { useState } from "react";
import styles from "./App.module.css";
import Map from "./components/Map.tsx";
import Popup from "./components/Popup.tsx";
import {
  useGetCandidates,
  type CandidateRequest,
} from "./hooks/useGetCandidates";

export default function App() {
  const { data, loading, error, getCandidates } = useGetCandidates();
  const [rank, setRank] = useState(1);

  // Map layer visibility settings
  const [showHospitals, setShowHospitals] = useState(true);
  const [showPopulation, setShowPopulation] = useState(true);

  const combinations = data?.combinations ?? [];
  const selectedCombination =
    combinations.find((combination) => combination.rank === rank) ??
    combinations[0];

  const sites = selectedCombination?.sites ?? [];

  async function handleSuggest(params: CandidateRequest): Promise<void> {
    const result = await getCandidates(params);
    if (!result) return;

    const defaultRank = result.combinations.some(
      (combination) => combination.rank === 1
    )
      ? 1
      : result.combinations[0]?.rank ?? 1;

    setRank(defaultRank);

    console.log(
      result.combinations.map((combination) => ({
        rank: combination.rank,
        coordinates: combination.sites.map(({ latitude, longitude }) => ({
          latitude,
          longitude,
        })),
      }))
    );
  }

  return (
    <div className={styles["app-wrapper"]}>
      <Popup
        onSuggest={handleSuggest}
        loading={loading}
        error={error}
        ranks={combinations.map((combination) => combination.rank)}
        rank={selectedCombination?.rank ?? rank}
        onRankChange={setRank}
        showHospitals={showHospitals}
        onShowHospitalsChange={setShowHospitals}
        showPopulation={showPopulation}
        onShowPopulationChange={setShowPopulation}
        sites={sites}
        baseline={selectedCombination?.baseline}
        final={selectedCombination?.final}
        impact={selectedCombination?.network_impact}
        warnings={selectedCombination?.warnings}
      />

      <Map
        sites={sites}
        showHospitals={showHospitals}
        showPopulation={showPopulation}
      />
    </div>
  );
}
