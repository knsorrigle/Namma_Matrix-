# Contracts

The shapes every part of Namma Matrix agrees on. The source of truth is
`backend/namma/contracts.py`; this page explains it. Change both together.

## 1. Ward (owner: YOGI)

```json
{
  "id": "whitefield", "name": "Whitefield", "lat": 12.9698, "lng": 77.75,
  "population": 52000,
  "rent": 24000,
  "jobs": {"it": 38000, "manufacturing": 2500, "services": 9000, "retail": 4000, "construction": 3000},
  "prices": 100, "traffic": 78, "pollution": 92, "mood": 0.0,
  "source_note": "population: GBA 2025 ward file; rent: estimate from listings, Oct 2026"
}
```

- `rent`: average 1BHK rent, INR per month.
- `prices`: cost-of-living index, 100 at the start of a run.
- `traffic`: 0 to 100. `pollution`: AQI-style.
- `mood`: average mood of the ward's citizens, -1 to 1. Computed, not seeded.
- Sectors are fixed: `it`, `manufacturing`, `services`, `retail`, `construction`.

City-wide levers live in `city`: `corporate_tax` (percent), `metro_fare` (INR), `fuel_price` (INR/litre).

## 2. Persona (owner: BABU)

```json
{
  "id": "c01", "name": "Manjunath N.", "age": 23, "gender": "M",
  "ward_id": "whitefield", "job": "QA tester", "sector": "it", "income_band": "middle",
  "language": "Kannada", "family": "shares a flat with two friends",
  "values": ["independence", "family first"], "traits": ["sociable", "curious"],
  "commutes_by_metro": true, "bio": "..."
}
```

- Names use a first name and an initial only, so no surname hints at caste or community.
- `income_band`: `low`, `middle` or `high`. `sector` must be one of the five sectors.

## 3. God Mode change (owner: Alpharnog)

```json
{"target": "whitefield", "metric": "jobs.it", "op": "mul", "value": 1.15, "reason": "three MNC campuses"}
{"target": "city", "metric": "corporate_tax", "op": "add", "value": 8, "reason": "heavy tax on MNCs"}
```

- `target`: a ward id, or `"city"`.
- Ward metrics: `rent`, `prices`, `traffic`, `pollution`, `population`, `jobs.<sector>`.
- City metrics: `corporate_tax`, `metro_fare`, `fuel_price`.
- `op`: `add`, `mul` (multiply, 0 to 10) or `set`.
- Job changes set a target; jobs move toward it over the next ticks, so effects ripple.

API: `POST /api/godmode/parse {"text"}` returns a preview
`{"text", "headline", "changes", "warnings", "parser"}`. The user can edit it, then
`POST /api/godmode/apply {"text", "headline", "changes"}` applies it.

## 4. Tick stream (owner: Alpharnog, read by USMAN)

`/ws` sends a `hello` message with the full state on connect, then one `tick` per tick:

```json
{
  "type": "tick", "tick": 12, "sim_date": "2026-11-14",
  "wards": [ /* Ward */ ], "city": { /* city levers */ },
  "citizens": [{"id": "c01", "ward_id": "whitefield", "thought": "...", "action": "consider_moving", "mood": -0.3, "post": null}],
  "feed": [{"tick": 12, "citizen_id": "c05", "name": "Anusha Q.", "ward_id": "whitefield", "text": "..."}],
  "events": [{"tick": 12, "kind": "godmode", "headline": "...", "wards": ["whitefield"]}],
  "thinking": 7, "llm_calls": 2, "tick_seconds": 4.1
}
```

- `citizens` lists only the citizens who thought this tick.
- `actions`: `stay`, `consider_moving`, `move`, `look_for_job`, `protest`, `post`.
- After a God Mode apply, the socket also sends `{"type": "godmode", "event": {...}}`.
- Every tick is also appended to `backend/runs/run-<time>.jsonl`, which is what replays play back.

Other endpoints: `GET /api/state`, `POST /api/control {"action": "play"|"pause"|"step", "speed"}`,
`GET /api/citizens/{id}` (persona, state, friends, memories), `GET /api/stats` (LLM calls and tokens).
