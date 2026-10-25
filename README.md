# Namma Matrix

A living, AI-simulated Bengaluru. LLM-driven citizens live in real wards, and a
God Mode textbox lets you rewrite the world in plain English and watch society react.

Mini project, Department of CSE, Navkis College of Engineering.

## Run it (Mac)

You need Python 3.11+ and Node 20+. On a Mac with Homebrew:

```bash
brew install python@3.12 node
```

**Backend** (terminal 1):

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn namma.server:app --reload
```

**Dashboard** (terminal 2):

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, press **Play**, then try a God Mode command.

By default the backend runs with a **mock LLM**: citizens give simple, sensible
reactions without any model installed, so everyone can develop on any laptop.

### Use a real model (Ollama)

```bash
brew install ollama
OLLAMA_CONTEXT_LENGTH=8192 ollama serve   # leave running in its own terminal
ollama pull llama3.1:8b                    # about 5 GB
cp backend/.env.example backend/.env       # then set LLM_PROVIDER=openai
cd backend && python scripts/check_llm.py  # one God Mode parse + one citizen batch, with timings
```

`OLLAMA_CONTEXT_LENGTH=8192` matters: a batch of five citizens is about 1,300 prompt
tokens plus the answer, and older Ollama versions cut prompts at 2,048 tokens without
telling you. Restart the backend after changing `.env`. The same settings work for Groq
or any OpenAI-compatible API; see `backend/.env.example`.

Cost per tick: with at most 10 thinking citizens in batches of 5, a tick is 2 LLM calls,
roughly 2,700 prompt tokens and 700 output tokens (estimated from the prompt sizes;
`check_llm.py` prints your real numbers). On a laptop that is about half a minute per busy
tick, and calm ticks need only one small call.

### Run a scenario without the dashboard

```bash
cd backend
python scripts/run_scenario.py --ticks 20 --at 3 \
  --command "Three big MNCs open in Whitefield, but the government adds a heavy tax on them."
```

It prints each tick and saves a replay to `backend/runs/` (one JSON line per tick).

### Tests

```bash
cd backend && pytest
```

## How it works

```
God Mode text ──► parser (LLM, keyword fallback) ──► preview ──► apply
                                                                  │
                                         world engine (wards, rules, ticks)
                                                                  │
                     citizens perceive changes ──► think (batched LLM calls) ──► act
                                                                  │
                                       tick stream over WebSocket ──► dashboard
```

- **World engine** (`backend/namma/world.py`): ward state and plain-code rules. No LLM.
- **Citizens** (`backend/namma/agents/`): persona, memory stream, reflection. A citizen only
  calls the LLM when something it can notice changed, and five citizens share one call.
- **God Mode** (`backend/namma/godmode.py`): text to structured `WorldChange`s, validated
  against the contract before anything is applied.
- **Server** (`backend/namma/server.py`): FastAPI REST + `/ws` WebSocket.
- **Dashboard** (`frontend/`): React + MapLibre. Map, God Mode, citizen inspector, feed, city table.

All shapes passed between parts are in [`docs/contracts.md`](docs/contracts.md).

### Making them sound like Bengalureans

No fine-tuning. Each citizen's prompt carries local context instead:

- **Voice pack** (`backend/data/voice/voice_pack.json`): eight kinds of resident (Gen Z techie,
  auto and delivery drivers, kirana and darshini owners, long-time residents and more), each
  with a speaking style, local phrases and an example line per situation. The example sets the
  tone; the model is told not to copy it. The mock LLM speaks these lines directly.
- **City pulse** (`backend/data/pulse/`): short anonymised takes on what the city argues about
  (rent, jobs, layoffs, fares, traffic, floods). A citizen reacting to a rent hike sees two of them.

Both grow from what the team collects, with no APIs and nothing copied:

- **Google Form**: real Bengalureans answer "what would you text your friend if ...". Each answer
  is matched to a resident type and becomes an example line and slang for it.
- **Field notes**: we read Reddit, Instagram and real conversations and write one-line takes in our
  own words. These become the city pulse.

Export both as CSV into `backend/data/survey/` (git ignores that folder), then run
`python scripts/build_voice.py`. It writes `data/voice/collected.json` and `data/pulse/pulse.json`;
read both before committing them.

On the map, every citizen is a little character, and what they think pops up in a speech
bubble above their head: one bubble per ward at a time, posts in yellow.

## Who owns what

| Area | Owner | Main files |
| --- | --- | --- |
| Agents, God Mode, backend, integration | Alpharnog | `backend/namma/agents/`, `godmode.py`, `sim.py`, `server.py` |
| World and data | YOGI | `backend/namma/world.py`, `backend/data/wards*.json` |
| Dashboard | USMAN | `frontend/` |
| Research, personas, evaluation, report | BABU | `backend/data/citizens*.json`, `backend/scripts/make_personas.py`, `docs/` |

See [`CONTRIBUTING.md`](CONTRIBUTING.md) for how we work in git.

## Status

The ward and citizen data in `backend/data/` are **placeholders** so the system runs.
They get replaced with sourced figures (GBA wards, Census 2011 proportions) and
demographics-based personas.
