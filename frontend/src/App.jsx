import { useEffect, useRef, useState } from 'react'
import { control } from './api.js'
import { useWorld } from './useWorld.js'
import { METRICS } from './colors.js'
import MapView from './components/MapView.jsx'
import GodModePanel from './components/GodModePanel.jsx'
import CitizenInspector from './components/CitizenInspector.jsx'
import Feed from './components/Feed.jsx'
import CityPanel from './components/CityPanel.jsx'

const TABS = ['God Mode', 'Citizen', 'Feed', 'City']

export default function App() {
  const world = useWorld()
  const [tab, setTab] = useState('God Mode')
  const [metric, setMetric] = useState('mood')
  const [selected, setSelected] = useState(null)
  const [playing, setPlaying] = useState(false)
  const [speed, setSpeed] = useState(1)
  useEffect(() => setPlaying(world.playing), [world.playing])
  const startWards = useRef([])
  if (!startWards.current.length && world.wards.length) startWards.current = world.wards

  const select = (id) => {
    setSelected(id)
    setTab('Citizen')
  }
  const run = async (action, s = speed) => {
    const res = await control(action, s)
    setPlaying(res.playing)
  }

  return (
    <div className="app">
      <header>
        <div className="brand">Namma <span>Matrix</span></div>
        <div className="clock">
          Day {world.tick} · {world.simDate}
          <span className={`status ${world.connected ? 'on' : 'off'}`}>{world.connected ? 'live' : 'offline'}</span>
          {world.provider && <span className="badge">LLM: {world.provider}</span>}
        </div>
        <div className="controls">
          {playing ? <button onClick={() => run('pause')}>Pause</button> : <button className="primary" onClick={() => run('play')}>Play</button>}
          <button onClick={() => run('step')} disabled={playing}>Step</button>
          <select value={speed} onChange={(e) => { const s = Number(e.target.value); setSpeed(s); if (playing) run('play', s) }}>
            {[0.5, 1, 2, 4].map((s) => <option key={s} value={s}>{s}×</option>)}
          </select>
        </div>
      </header>
      <main>
        <section className="map-wrap">
          <MapView wards={world.wards} citizens={world.citizens} bubbles={world.bubbles} tick={world.tick} metric={metric} selectedId={selected} onSelect={select} />
          <div className="metric-picker">
            {Object.entries(METRICS).map(([k, m]) => (
              <button key={k} className={metric === k ? 'active' : ''} onClick={() => setMetric(k)}>{m.label}</button>
            ))}
          </div>
        </section>
        <aside>
          <nav>
            {TABS.map((t) => <button key={t} className={tab === t ? 'active' : ''} onClick={() => setTab(t)}>{t}</button>)}
          </nav>
          {tab === 'God Mode' && <GodModePanel wards={world.wards} />}
          {tab === 'Citizen' && <CitizenInspector id={selected} tick={world.tick} wards={world.wards} citizens={world.citizens} onSelect={select} />}
          {tab === 'Feed' && <Feed feed={world.feed} events={world.events} wards={world.wards} />}
          {tab === 'City' && <CityPanel wards={world.wards} startWards={startWards.current} city={world.city} opinions={world.opinions} lastTick={world.lastTick} />}
        </aside>
      </main>
    </div>
  )
}
