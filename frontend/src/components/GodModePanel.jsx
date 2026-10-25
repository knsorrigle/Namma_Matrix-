import { useState } from 'react'
import { applyGodMode, parseGodMode } from '../api.js'

const EXAMPLES = [
  'Three big MNCs open in Whitefield, but the government adds a heavy tax on them.',
  'Metro fare goes up by 25%',
  'Two IT companies shut down offices in Electronic City',
  'Rent control in Koramangala and Malleshwaram',
]

export default function GodModePanel({ wards }) {
  const [text, setText] = useState('')
  const [preview, setPreview] = useState(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState('')
  const wardName = (id) => (id === 'city' ? 'Whole city' : wards.find((w) => w.id === id)?.name ?? id)

  async function parse() {
    setBusy(true)
    setMessage('')
    try {
      setPreview(await parseGodMode(text))
    } catch (e) {
      setMessage(e.message)
    } finally {
      setBusy(false)
    }
  }

  async function apply() {
    setBusy(true)
    try {
      const event = await applyGodMode({ text: preview.text, headline: preview.headline, changes: preview.changes })
      setMessage(`Applied: ${event.headline.replace(/\.$/, '')}. Citizens will find out as they go about their day.`)
      setPreview(null)
      setText('')
    } catch (e) {
      setMessage(e.message)
    } finally {
      setBusy(false)
    }
  }

  const editChange = (i, value) =>
    setPreview({ ...preview, changes: preview.changes.map((c, j) => (j === i ? { ...c, value: Number(value) } : c)) })
  const dropChange = (i) => setPreview({ ...preview, changes: preview.changes.filter((_, j) => j !== i) })

  return (
    <div className="panel godmode">
      <p className="hint">Rewrite the world in plain English. You will see the parsed changes before anything happens.</p>
      <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Three big MNCs open in Whitefield…" rows={3} />
      <div className="examples">
        {EXAMPLES.map((ex) => (
          <button key={ex} className="chip" onClick={() => setText(ex)}>{ex}</button>
        ))}
      </div>
      <button className="primary" disabled={busy || text.trim().length < 3} onClick={parse}>
        {busy && !preview ? 'Parsing…' : 'Preview changes'}
      </button>

      {preview && (
        <div className="preview">
          <div className="headline">📰 {preview.headline}</div>
          <div className="muted">Parsed by {preview.parser === 'llm' ? 'the LLM' : 'keyword rules'}</div>
          <table>
            <thead><tr><th>Where</th><th>What</th><th>Change</th><th /></tr></thead>
            <tbody>
              {preview.changes.map((c, i) => (
                <tr key={i}>
                  <td>{wardName(c.target)}</td>
                  <td>{c.metric}</td>
                  <td>
                    {c.op === 'mul' ? '×' : c.op === 'add' ? '+' : '='}
                    <input type="number" step="0.01" value={c.value} onChange={(e) => editChange(i, e.target.value)} />
                  </td>
                  <td><button className="link" onClick={() => dropChange(i)}>remove</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {preview.warnings.map((w) => <div key={w} className="warning">{w}</div>)}
          <div className="row">
            <button className="primary" disabled={busy || !preview.changes.length} onClick={apply}>Apply to the world</button>
            <button onClick={() => setPreview(null)}>Cancel</button>
          </div>
        </div>
      )}
      {message && <div className="message">{message}</div>}
    </div>
  )
}
