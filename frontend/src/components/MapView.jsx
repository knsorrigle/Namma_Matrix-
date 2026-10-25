import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import { METRICS, moodColor, wardColor } from '../colors.js'
import { avatarFor } from '../avatars.js'

const STYLE = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution: '© OpenStreetMap contributors',
    },
  },
  layers: [{ id: 'osm', type: 'raster', source: 'osm', paint: { 'raster-saturation': -0.8, 'raster-brightness-max': 0.85 } }],
}
const EMPTY = { type: 'FeatureCollection', features: [] }
const BUBBLE_TICKS = 3 // a thought stays up for this many ticks
const ROTATE_MS = 4000 // wards with several speakers take turns, one bubble at a time
const MAX_CHARS = 120

function point(lng, lat, properties) {
  return { type: 'Feature', geometry: { type: 'Point', coordinates: [lng, lat] }, properties }
}

function shorten(text) {
  return text.length > MAX_CHARS ? `${text.slice(0, MAX_CHARS - 1)}…` : text
}

// Which citizen's bubble each ward shows right now. Posts and moves go first.
function speakers(citizens, bubbles, tick, now, selectedId) {
  const byWard = {}
  for (const c of Object.values(citizens)) {
    const b = bubbles[c.id]
    if (!b || tick - b.tick >= BUBBLE_TICKS) continue
    ;(byWard[c.state.ward_id] ||= []).push({ id: c.id, b })
  }
  const shown = new Set()
  const selectedWard = citizens[selectedId]?.state.ward_id
  for (const [wid, list] of Object.entries(byWard)) {
    if (wid === selectedWard && bubbles[selectedId]) continue // the selected citizen speaks for their ward
    const rank = ({ b }) => (b.post ? 2 : 0) + (b.action === 'move' || b.action === 'consider_moving' ? 1 : 0) + b.tick / 1e6
    list.sort((x, y) => rank(y) - rank(x))
    shown.add(list[Math.floor(now / ROTATE_MS) % list.length].id)
  }
  if (selectedId && bubbles[selectedId]) shown.add(selectedId)
  return shown
}

export default function MapView({ wards, citizens, bubbles, tick, metric, selectedId, onSelect }) {
  const container = useRef(null)
  const map = useRef(null)
  const labels = useRef({})
  const people = useRef({})
  const onSelectRef = useRef(onSelect)
  const [ready, setReady] = useState(false)
  const [now, setNow] = useState(Date.now())
  onSelectRef.current = onSelect

  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [])

  useEffect(() => {
    const m = new maplibregl.Map({ container: container.current, style: STYLE, center: [77.66, 12.96], zoom: 10.6 })
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-left')
    m.on('load', () => {
      m.addSource('wards', { type: 'geojson', data: EMPTY })
      m.addLayer({
        id: 'wards',
        type: 'circle',
        source: 'wards',
        paint: {
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 9, ['*', ['get', 'r'], 0.6], 13, ['*', ['get', 'r'], 5]],
          'circle-color': ['get', 'color'],
          'circle-opacity': 0.3,
          'circle-stroke-color': ['get', 'color'],
          'circle-stroke-width': 2,
        },
      })
      setReady(true)
    })
    map.current = m
    return () => m.remove()
  }, [])

  // Frame the study wards once, with room above for speech bubbles.
  const framed = useRef(false)
  useEffect(() => {
    if (!ready || !wards.length || framed.current) return
    const lngs = wards.map((w) => w.lng)
    const lats = wards.map((w) => w.lat)
    map.current.fitBounds([[Math.min(...lngs), Math.min(...lats)], [Math.max(...lngs), Math.max(...lats)]], {
      padding: { top: 170, bottom: 110, left: 140, right: 140 },
      duration: 0,
    })
    framed.current = true
  }, [ready, wards])

  // Wards: coloured circles plus a label with the chosen metric.
  useEffect(() => {
    const m = map.current
    if (!ready || !wards.length) return
    m.getSource('wards').setData({
      type: 'FeatureCollection',
      features: wards.map((w) => point(w.lng, w.lat, { id: w.id, r: Math.sqrt(w.population) / 9, color: wardColor(w, wards, metric) })),
    })
    for (const w of wards) {
      let marker = labels.current[w.id]
      if (!marker) {
        const el = document.createElement('div')
        el.className = 'ward-label'
        marker = new maplibregl.Marker({ element: el, offset: [0, 84] }).setLngLat([w.lng, w.lat]).addTo(m)
        labels.current[w.id] = marker
      }
      marker.getElement().innerHTML = `<b>${w.name}</b><span>${METRICS[metric].fmt(w)}</span>`
    }
  }, [ready, wards, metric])

  // Citizens: a little character each, standing in a ring around their ward,
  // with a speech bubble when they have something on their mind.
  useEffect(() => {
    const m = map.current
    if (!ready || !wards.length) return
    const byId = Object.fromEntries(wards.map((w) => [w.id, w]))
    const shown = speakers(citizens, bubbles, tick, now, selectedId)
    const groups = {}
    for (const c of Object.values(citizens)) (groups[c.state.ward_id] ||= []).push(c)

    for (const [wid, list] of Object.entries(groups)) {
      const w = byId[wid]
      if (!w) continue
      list.sort((a, b) => a.id.localeCompare(b.id))
      // A ring in screen pixels, so characters never pile up when zoomed out.
      const radius = 30 + 4 * list.length
      list.forEach((c, i) => {
        const a = (2 * Math.PI * i) / list.length - Math.PI / 2
        const lngLat = [w.lng, w.lat]
        const offset = [radius * Math.cos(a), radius * Math.sin(a) + 15]
        let marker = people.current[c.id]
        if (!marker) {
          const el = document.createElement('div')
          el.className = 'citizen'
          el.innerHTML = `<div class="bubble"></div><button class="avatar" title="${c.name}">${avatarFor(c)}</button>`
          el.querySelector('.avatar').addEventListener('click', (e) => {
            e.stopPropagation()
            onSelectRef.current(c.id)
          })
          el.querySelector('.bubble').addEventListener('click', () => onSelectRef.current(c.id))
          marker = new maplibregl.Marker({ element: el, anchor: 'bottom' }).setLngLat(lngLat).addTo(m)
          people.current[c.id] = marker
        }
        marker.setLngLat(lngLat).setOffset(offset)
        const el = marker.getElement()
        const bubble = el.querySelector('.bubble')
        const b = bubbles[c.id]
        const visible = shown.has(c.id)
        el.classList.toggle('selected', c.id === selectedId)
        el.classList.toggle('speaking', visible)
        el.style.setProperty('--mood', moodColor(c.state.mood))
        el.style.zIndex = c.id === selectedId ? 30 : visible ? 20 : 1
        if (visible) {
          bubble.className = `bubble${b.post ? ' post' : ''}`
          bubble.innerHTML = `<b>${c.name.split(' ')[0]}${b.post ? ' posted' : ''}</b>${shorten(b.text)}`
        }
      })
    }
  }, [ready, wards, citizens, bubbles, tick, now, selectedId])

  return <div ref={container} className="map" />
}
