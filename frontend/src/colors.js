// Mood runs from -1 (angry) to +1 (happy).
export function moodColor(m) {
  const t = Math.max(-1, Math.min(1, m ?? 0))
  const lerp = (a, b, k) => Math.round(a + (b - a) * k)
  const [neg, mid, pos] = [[214, 69, 69], [232, 178, 60], [46, 160, 103]]
  const [from, to, k] = t < 0 ? [mid, neg, -t] : [mid, pos, t]
  return `rgb(${lerp(from[0], to[0], k)}, ${lerp(from[1], to[1], k)}, ${lerp(from[2], to[2], k)})`
}

// Sequential blue for values between lo and hi.
export function scaleColor(v, lo, hi) {
  const k = hi > lo ? (v - lo) / (hi - lo) : 0.5
  const light = Math.round(82 - k * 47)
  return `hsl(212, 70%, ${light}%)`
}

export const METRICS = {
  mood: { label: 'Mood', fmt: (w) => `${w.mood >= 0 ? '+' : ''}${w.mood.toFixed(2)}` },
  rent: { label: 'Rent', fmt: (w) => `₹${Math.round(w.rent).toLocaleString('en-IN')}` },
  population: { label: 'Population', fmt: (w) => w.population.toLocaleString('en-IN') },
  traffic: { label: 'Traffic', fmt: (w) => w.traffic.toFixed(0) },
}

export function wardColor(ward, wards, metric) {
  if (metric === 'mood') return moodColor(ward.mood)
  const values = wards.map((w) => w[metric])
  return scaleColor(ward[metric], Math.min(...values), Math.max(...values))
}
