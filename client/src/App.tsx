import styles from './App.module.css'
import Sidebar from './components/Sidebar.tsx'
import Map from './components/Map.tsx'
import Popup from './components/Popup.tsx'

function App() {
  return (
    <div className={styles['app-wrapper']}>
      <Popup />
      <Map />
    </div>
  )
}

export default App