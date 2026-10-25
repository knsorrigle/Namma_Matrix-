import { useEffect, useRef, useState } from 'react'
import maplibregl from 'maplibre-gl'
import { METRICS, moodColor, wardColor } from '../colors.js'

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
const RING = 0.011 // degrees, about 1.2 km: how far citizen dots sit from the ward centre

function point(lng, lat, properties) {
  return { type: 'Feature', geometry: { type: 'Point', coordinates: [lng, lat] }, properties }
}

export default function MapView({ wards, citizens, metric, selectedId, onSelect }) {
  const container = useRef(null)
  const map = useRef(null)
  const labels = useRef({})
  const onSelectRef = useRef(onSelect)
  const [ready, setReady] = useState(false)
  onSelectRef.current = onSelect

  useEffect(() => {
    const m = new maplibregl.Map({ container: container.current, style: STYLE, center: [77.66, 12.96], zoom: 10.4 })
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
          'circle-opacity': 0.35,
          'circle-stroke-color': ['get', 'color'],
          'circle-stroke-width': 2,
        },
      })
      m.addSource('citizens', { type: 'geojson', data: EMPTY })
      m.addLayer({
        id: 'citizens',
        type: 'circle',
        source: 'citizens',
        paint: {
          'circle-radius': ['case', ['get', 'selected'], 9, 6],
          'circle-color': ['get', 'color'],
          'circle-stroke-color': ['case', ['get', 'selected'], '#111', '#fff'],
          'circle-stroke-width': ['case', ['get', 'selected'], 3, 1.5],
        },
      })
      m.on('click', 'citizens', (e) => onSelectRef.current(e.features[0].properties.id))
      m.on('mouseenter', 'citizens', () => (m.getCanvas().style.cursor = 'pointer'))
      m.on('mouseleave', 'citizens', () => (m.getCanvas().style.cursor = ''))
      setReady(true)
    })
    map.current = m
    return () => m.remove()
  }, [])

  useEffect(() => {
    const m = map.current
    if (!ready || !wards.length) return
    const byId = Object.fromEntries(wards.map((w) => [w.id, w]))

    m.getSource('wards').setData({
      type: 'FeatureCollection',
      features: wards.map((w) => point(w.lng, w.lat, { id: w.id, r: Math.sqrt(w.population) / 9, color: wardColor(w, wards, metric) })),
    })

    const groups = {}
    for (const c of Object.values(citizens)) (groups[c.state.ward_id] ||= []).push(c)
    const features = []
    for (const [wid, list] of Object.entries(groups)) {
      const w = byId[wid]
      if (!w) continue
      list.sort((a, b) => a.id.localeCompare(b.id))
      list.forEach((c, i) => {
        const a = (2 * Math.PI * i) / list.length
        features.push(point(w.lng + RING * Math.cos(a), w.lat + RING * Math.sin(a), { id: c.id, color: moodColor(c.state.mood), selected: c.id === selectedId }))
      })
    }
    m.getSource('citizens').setData({ type: 'FeatureCollection', features })

    for (const w of wards) {
      let marker = labels.current[w.id]
      if (!marker) {
        const el = document.createElement('div')
        el.className = 'ward-label'
        marker = new maplibregl.Marker({ element: el, offset: [0, -50] }).setLngLat([w.lng, w.lat]).addTo(m)
        labels.current[w.id] = marker
      }
      marker.getElement().innerHTML = `<b>${w.name}</b><span>${METRICS[metric].fmt(w)}</span>`
    }
  }, [ready, wards, citizens, metric, selectedId])

  return <div ref={container} className="map" />
}
