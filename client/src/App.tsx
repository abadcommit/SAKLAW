import { useState } from 'react'
import styles from './App.module.css'
import Map from './components/Map.tsx'
import Popup from './components/Popup.tsx'
import { useGetCandidates } from './hooks/useGetCandidates'

function App() {
  const { data, loading, error, getCandidates } = useGetCandidates()
  const [rank, setRank] = useState(1)

  const combinations = data?.combinations ?? []
  const combination = combinations.find((c) => c.rank === rank) ?? combinations[0]
  const sites = combination?.sites ?? []

  return (
    <div className={styles['app-wrapper']}>
      <Popup
        onSuggest={() => getCandidates()}
        loading={loading}
        error={error}
        ranks={combinations.map((c) => c.rank)}
        rank={combination?.rank}
        onRankChange={setRank}
      />
      <Map sites={sites} />
    </div>
  )
}

export default App