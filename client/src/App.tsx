import styles from './App.module.css'
import Sidebar from './components/Sidebar.tsx'
import Map from './components/Map.tsx'

function App() {
  return (
    <div className={styles['app-wrapper']}>
      <Sidebar />
      <Map />
    </div>
  )
}

export default App
