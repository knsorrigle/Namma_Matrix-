export default function Feed({ feed, events, wards }) {
  const name = (id) => wards.find((w) => w.id === id)?.name ?? id
  return (
    <div className="panel feed">
      <h3>World events</h3>
      {events.length === 0 && <p className="hint">Nothing has happened yet. Try God Mode.</p>}
      {events.slice().reverse().map((e, i) => (
        <div key={i} className={`event ${e.kind}`}>
          <b>Day {e.tick}</b> {e.headline} <span className="muted">{e.wards.length ? e.wards.map(name).join(', ') : 'whole city'}</span>
        </div>
      ))}
      <h3>Citizen posts</h3>
      {feed.length === 0 && <p className="hint">No posts yet.</p>}
      {feed.map((p, i) => (
        <div key={i} className="post">
          <b>{p.name}</b> <span className="muted">· {name(p.ward_id)} · day {p.tick}</span>
          <div>{p.text}</div>
        </div>
      ))}
    </div>
  )
}
