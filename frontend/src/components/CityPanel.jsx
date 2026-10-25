import { moodColor } from '../colors.js'

export default function CityPanel({ wards, startWards, city, lastTick }) {
  const start = Object.fromEntries(startWards.map((w) => [w.id, w]))
  const pct = (now, then) => (then ? ((now / then - 1) * 100).toFixed(1) : '0.0')
  return (
    <div className="panel">
      <table className="wards">
        <thead><tr><th>Ward</th><th>Rent ₹</th><th>Δ</th><th>People</th><th>Mood</th></tr></thead>
        <tbody>
          {wards.map((w) => (
            <tr key={w.id}>
              <td>{w.name}</td>
              <td>{Math.round(w.rent).toLocaleString('en-IN')}</td>
              <td>{pct(w.rent, start[w.id]?.rent)}%</td>
              <td>{w.population.toLocaleString('en-IN')}</td>
              <td><span className="dot small" style={{ background: moodColor(w.mood) }} /> {w.mood.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h3>City levers</h3>
      <div className="facts">
        <span>Corporate tax <b>{city.corporate_tax}%</b></span>
        <span>Metro fare <b>₹{city.metro_fare?.toFixed(0)}</b></span>
        <span>Petrol <b>₹{city.fuel_price?.toFixed(0)}</b></span>
      </div>
      {lastTick && (
        <p className="muted">Last tick: {lastTick.thinking} citizens thought, {lastTick.llm_calls} LLM calls, {lastTick.tick_seconds}s.</p>
      )}
    </div>
  )
}
