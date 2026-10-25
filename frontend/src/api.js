// Thin wrappers over the backend API. Shapes follow docs/contracts.md.

async function post(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) throw new Error(`${path} failed: ${res.status} ${await res.text()}`)
  return res.json()
}

export const control = (action, speed = 1) => post('/api/control', { action, speed })
export const parseGodMode = (text) => post('/api/godmode/parse', { text })
export const applyGodMode = (parsed) => post('/api/godmode/apply', parsed)
export const getCitizen = (id) => fetch(`/api/citizens/${id}`).then((r) => r.json())

// Opens the live stream and reconnects if the backend restarts.
export function connect(onMessage, onStatus) {
  let ws
  let closed = false
  const open = () => {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws'
    ws = new WebSocket(`${proto}://${location.host}/ws`)
    ws.onopen = () => onStatus(true)
    ws.onmessage = (e) => onMessage(JSON.parse(e.data))
    ws.onclose = () => {
      onStatus(false)
      if (!closed) setTimeout(open, 1500)
    }
  }
  open()
  return () => {
    closed = true
    ws?.close()
  }
}
