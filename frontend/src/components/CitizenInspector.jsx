import { useEffect, useState } from 'react'
import { getCitizen } from '../api.js'
import { moodColor } from '../colors.js'
import { TOPICS, stanceWord } from '../opinions.js'

export default function CitizenInspector({ id, tick, wards, citizens, onSelect }) {
  const [view, setView] = useState(null)

  useEffect(() => {
    if (!id) return
    let live = true
    getCitizen(id).then((v) => live && setView(v))
    return () => { live = false }
  }, [id, tick])

  if (!id) return <div className="panel"><p className="hint">Click any citizen on the map to read their mind.</p></div>
  if (!view || view.persona.id !== id) return <div className="panel"><p className="hint">Loading…</p></div>

  const { persona: p, state: s, memories, friends } = view
  const ward = wards.find((w) => w.id === s.ward_id)
  return (
    <div className="panel inspector">
      <div className="who">
        <span className="dot" style={{ background: moodColor(s.mood) }} />
        <div>
          <h2>{p.name}</h2>
          <div className="muted">{p.age} · {p.job} · {ward?.name}</div>
        </div>
      </div>
      <div className="thought">“{s.last_thought || 'Nothing on their mind yet.'}”</div>
      <div className="facts">
        <span>Mood <b style={{ color: moodColor(s.mood) }}>{s.mood >= 0 ? '+' : ''}{s.mood.toFixed(2)}</b></span>
        <span>Doing <b>{s.last_action.replace('_', ' ')}</b></span>
        <span>Income <b>{p.income_band}</b></span>
        <span>Speaks <b>{p.language}</b></span>
      </div>
      <p className="muted">{p.family}. Values {p.values.join(' and ')}; {p.traits.join(', ')}.{p.commutes_by_metro ? ' Takes the metro.' : ''}</p>
      {Object.keys(s.opinions || {}).length > 0 && (
        <>
          <h3>Opinions</h3>
          <ul className="opinions">
            {Object.entries(TOPICS).map(([k, t]) => {
              const o = s.opinions[k]
              if (!o) return null
              const width = `${Math.abs(o.stance) * 50}%`
              return (
                <li key={k} title={t.statement}>
                  <div className="opinion-head">
                    <span>{t.label}</span>
                    <span className="bar"><span style={{ width, background: moodColor(o.stance), [o.stance < 0 ? 'right' : 'left']: '50%' }} /></span>
                    <b>{stanceWord(o.stance)}</b>
                  </div>
                  <div className="muted why">“{o.why}”</div>
                </li>
              )
            })}
          </ul>
        </>
      )}
      {s.beliefs.length > 0 && (
        <>
          <h3>Beliefs</h3>
          <ul>{s.beliefs.slice(-3).map((b, i) => <li key={i}>{b}</li>)}</ul>
        </>
      )}
      <h3>Memory stream</h3>
      <ul className="memories">
        {memories.slice().reverse().map((m, i) => (
          <li key={i}><span className={`tag ${m.kind}`}>{m.kind}</span> <span className="muted">day {m.tick}</span> {m.text}</li>
        ))}
      </ul>
      <h3>Friends</h3>
      <div className="examples">{friends.map((f) => <button key={f} className="chip" onClick={() => onSelect(f)}>{citizens[f]?.name ?? f}</button>)}</div>
    </div>
  )
}
