import { useState } from 'react'
import styles from '../stylesheets/Popup.module.css'
import { Minimize, Maximize } from 'lucide-react'
import { Draggable } from '../hooks/useDraggable';
import { useGetCandidates } from '../hooks/useGetCandidates';

interface Param {
  name: string;
  desc: string;
}

function PopupHeader({ togglePopup }: { togglePopup: () => void }) {
  return (<>
    <div className={styles['popup-header-wrapper']}>
      <h1>Saklaw</h1>
      <Minimize onClick={togglePopup} />
    </div>
    <h2 id={styles['popup-tagline']}>Tagline here</h2>
  </>)
}

function Parameter({ name, desc }: { name: string, desc: string }) {
  return (<div className={styles['parameter-wrapper']}>
    <label>
      <input type='checkbox' />
      {name}
    </label>
    {/* <h3>{desc}</h3> */}
  </div>)
}

function ParamSelect({ params }: { params: Param[] }) {
  const paramItems = params.map((p) => <Parameter name={p.name} desc={p.desc} />)

  return (<div className={styles['param-select-wrapper']}>
    <h1>Parameters</h1>
    {paramItems}
  </div>)
}

export default function Popup() {

  const [isOpen, setIsOpen] = useState(true)
  let params = [
    {
      name: 'Parameter 1',
      desc: 'I do a thing',
    },
    {
      name: 'Parameter 2',
      desc: 'I do a thing',
    },
    {
      name: 'Parameter 3',
      desc: 'I do a thing',
    }
  ]

  function togglePopup() {
    setIsOpen((open) => (!open))
  }

  if (isOpen) {
    return (<Draggable><div className={styles['popup-wrapper-open']}>
      <PopupHeader togglePopup={togglePopup} />
      <ParamSelect params={params} />
      <button className={styles['candidate-button']}>Get Candidates</button>
    </div></Draggable>)
  }

  return (<div className={styles['popup-wrapper-closed']}
    onClick={togglePopup}>
      <Maximize />
  </div>)
}