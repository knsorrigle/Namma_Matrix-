import { useEffect, useReducer } from 'react'
import { connect } from './api.js'

const initial = { connected: false, playing: false, bubbles: {}, tick: 0, simDate: '', provider: '', wards: [], city: {}, citizens: {}, feed: [], events: [], lastTick: null }

function reducer(state, msg) {
  switch (msg.type) {
    case 'status':
      return { ...state, connected: msg.connected }
    case 'hello':
      return {
        ...state,
        tick: msg.tick,
        simDate: msg.sim_date,
        provider: msg.llm_provider,
        playing: msg.playing,
        wards: msg.wards,
        city: msg.city,
        citizens: Object.fromEntries(msg.citizens.map((c) => [c.id, c])),
        events: msg.events,
      }
    case 'tick': {
      const citizens = { ...state.citizens }
      const bubbles = { ...state.bubbles }
      for (const u of msg.citizens) {
        bubbles[u.id] = { text: u.post || u.thought, post: Boolean(u.post), action: u.action, tick: msg.tick }
        const c = citizens[u.id]
        if (!c) continue
        citizens[u.id] = {
          ...c,
          state: { ...c.state, ward_id: u.ward_id, mood: u.mood, last_thought: u.thought, last_action: u.action },
        }
      }
      return {
        ...state,
        tick: msg.tick,
        simDate: msg.sim_date,
        wards: msg.wards,
        city: msg.city,
        citizens,
        bubbles,
        feed: [...msg.feed.slice().reverse(), ...state.feed].slice(0, 100),
        events: [...state.events, ...msg.events.filter((e) => !state.events.some((x) => x.tick === e.tick && x.headline === e.headline))],
        lastTick: msg,
      }
    }
    case 'godmode':
      return { ...state, events: [...state.events, msg.event] }
    default:
      return state
  }
}

// The whole live world, kept in sync with the backend over the WebSocket.
export function useWorld() {
  const [state, dispatch] = useReducer(reducer, initial)
  useEffect(() => connect(dispatch, (connected) => dispatch({ type: 'status', connected })), [])
  return state
}
