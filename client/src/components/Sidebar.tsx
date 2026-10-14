import { PanelLeft } from "lucide-react"
import styles from '../stylesheets/Sidebar.module.css'


export default function Sidebar() {

  return (
    <div className={styles.sidebar}>
      <div className={styles['head-wrapper']}>
        <h1>Saklaw</h1> {/* Saklaw Logo Here */}
        <PanelLeft strokeWidth={3}/>
      </div>
    </div>
  )
}