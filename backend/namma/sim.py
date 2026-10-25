"""The simulation loop: world rules, then citizens perceive, think and act."""

from __future__ import annotations

import asyncio
import json
import random
import time
from datetime import datetime
from pathlib import Path

from .agents.citizen import (
    REACT_SYSTEM,
    REFLECT_SYSTEM,
    CitizenMind,
    react_user_prompt,
    reflect_user_prompt,
)
from .agents.llm import LLM, make_llm
from .config import Settings
from .contracts import (
    CitizenUpdate,
    CitizenView,
    FeedPost,
    GodModeApply,
    Persona,
    TickEvent,
    WorldEvent,
)
from .godmode import GodMode
from .world import WorldEngine

# Each full mind stands for a slice of its ward's crowd. When it moves, this
# share of its ward moves with it (the crowd copies the nearest full mind).
CROWD_FOLLOW_SHARE = 0.004


class Simulation:
    def __init__(self, settings: Settings, llm: LLM | None = None):
        self.settings = settings
        self.llm = llm or make_llm(settings)
        self.world = WorldEngine.from_file(settings.data_dir / "wards.sample.json")
        personas = [Persona(**p) for p in json.loads((settings.data_dir / "citizens.sample.json").read_text())["citizens"]]
        self.minds: dict[str, CitizenMind] = {p.id: CitizenMind(p, settings.data_dir) for p in personas}
        self.godmode = GodMode(self.llm, settings.godmode_model)
        self.rng = random.Random(settings.seed)
        self._build_social_graph()
        self._pending_events: list[WorldEvent] = []
        self._lock = asyncio.Lock()
        self.history: list[TickEvent] = []
        settings.runs_dir.mkdir(parents=True, exist_ok=True)
        self.run_file: Path = settings.runs_dir / f"run-{datetime.now():%Y%m%d-%H%M%S}.jsonl"
        # Prime every citizen's view of the world so the first tick only
        # reports real changes.
        for mind in self.minds.values():
            mind.perceive(self.world, [])

    # ------------------------------------------------------------ setup ----

    def _build_social_graph(self) -> None:
        """Friends: neighbours in the same ward plus coworkers in the same sector."""
        minds = list(self.minds.values())
        for m in minds:
            same_ward = [o.persona.id for o in minds if o is not m and o.persona.ward_id == m.persona.ward_id]
            same_sector = [o.persona.id for o in minds if o is not m and o.persona.sector == m.persona.sector and o.persona.id not in same_ward]
            m.friends = self.rng.sample(same_ward, min(2, len(same_ward))) + self.rng.sample(same_sector, min(2, len(same_sector)))

    # --------------------------------------------------------- God Mode ----

    async def apply_godmode(self, cmd: GodModeApply) -> WorldEvent:
        async with self._lock:
            for change in cmd.changes:
                self.world.apply_change(change)
            wards = sorted({c.target for c in cmd.changes if c.target != "city"})
            # City-wide changes reach everyone; local ones only the named wards.
            # Others hear about it later, from friends.
            ev = self.world.add_event("godmode", cmd.headline, [] if any(c.target == "city" for c in cmd.changes) else wards)
            self._pending_events.append(ev)
            return ev

    # ------------------------------------------------------------- tick ----

    async def tick(self) -> TickEvent:
        async with self._lock:
            started = time.perf_counter()
            calls_before = self.llm.stats.calls
            self.world.step()
            events, self._pending_events = self._pending_events, []

            noticed: dict[str, list[tuple[str, int]]] = {}
            for mind in self.minds.values():
                obs = mind.perceive(self.world, events)
                for text, importance in obs:
                    mind.memory.add(self.world.tick, "observation", text, importance)
                if obs:
                    noticed[mind.persona.id] = obs

            thinkers = self._pick_thinkers(noticed)
            updates = await self._react(thinkers, noticed)
            await self._reflect()
            feed = self._spread_posts(updates)
            self._update_ward_mood()

            event = TickEvent(
                tick=self.world.tick,
                sim_date=self.world.sim_date,
                # Copies, so history and replays don't change as the world moves on.
                wards=[w.model_copy(deep=True) for w in self.world.wards.values()],
                city=self.world.city.model_copy(),
                citizens=updates,
                feed=feed,
                events=events,
                thinking=len(thinkers),
                llm_calls=self.llm.stats.calls - calls_before,
                tick_seconds=round(time.perf_counter() - started, 3),
            )
            self.history.append(event)
            with self.run_file.open("a") as f:
                f.write(event.model_dump_json() + "\n")
            return event

    def _pick_thinkers(self, noticed: dict[str, list[tuple[str, int]]]) -> list[CitizenMind]:
        # Most important news first, capped to control cost.
        ranked = sorted(noticed, key=lambda cid: -max(i for _, i in noticed[cid]))
        chosen = ranked[: self.settings.max_thinkers_per_tick]
        idle = [cid for cid in self.minds if cid not in noticed]
        self.rng.shuffle(idle)
        room = max(0, self.settings.max_thinkers_per_tick - len(chosen))
        chosen += idle[: min(room, self.settings.idle_thinkers_per_tick)]
        return [self.minds[cid] for cid in chosen]

    async def _react(self, thinkers: list[CitizenMind], noticed: dict) -> list[CitizenUpdate]:
        if not thinkers:
            return []
        tick = self.world.tick
        wards = [w.model_dump() for w in self.world.wards.values()]
        ward_ids = set(self.world.wards)
        size = max(1, self.settings.batch_size)
        batches = [thinkers[i : i + size] for i in range(0, len(thinkers), size)]

        async def run(batch: list[CitizenMind]) -> list[CitizenUpdate]:
            cards = [m.prompt_card([t for t, _ in noticed.get(m.persona.id, [])] or ["Nothing new today. An ordinary day."], tick) for m in batch]
            payload = {"citizens": cards, "cheapest_ward": min(wards, key=lambda w: w["rent"])["id"]}
            try:
                raw = await self.llm.complete_json("react", REACT_SYSTEM, react_user_prompt(cards, wards), payload)
                rows = [r for r in raw.get("citizens", []) if isinstance(r, dict)] if isinstance(raw.get("citizens"), list) else []
                by_id = {str(r.get("id")): r for r in rows}
                # Small models sometimes garble ids; if the count matches, trust the order.
                if len(rows) == len(batch) and not all(m.persona.id in by_id for m in batch):
                    by_id = {m.persona.id: r for m, r in zip(batch, rows)}
            except Exception:
                by_id = {}
            out = []
            for m in batch:
                r = by_id.get(m.persona.id) or {"thought": m.state.last_thought or "...", "mood_change": 0, "action": "stay"}
                update, move_to = m.apply_reaction(r, tick, ward_ids)
                if move_to:
                    self._move(m, move_to)
                    update.ward_id = m.state.ward_id
                out.append(update)
            return out

        results = await asyncio.gather(*(run(b) for b in batches))
        return [u for batch in results for u in batch]

    async def _reflect(self) -> None:
        due = [m for m in self.minds.values() if m.wants_reflection()][: self.settings.batch_size]
        if not due:
            return
        cards = [{"id": m.persona.id, "name": m.persona.name, "mood": m.state.mood,
                  "memories": [x.text for x in m.memory.recent(12)]} for m in due]
        try:
            raw = await self.llm.complete_json("reflect", REFLECT_SYSTEM, reflect_user_prompt(cards), {"citizens": cards})
            by_id = {str(r.get("id")): str(r.get("belief", "")) for r in raw.get("citizens", []) if isinstance(r, dict)}
        except Exception:
            return
        for m in due:
            m.apply_reflection(by_id.get(m.persona.id, ""), self.world.tick)

    def _move(self, mind: CitizenMind, to_ward: str) -> None:
        from_ward = mind.state.ward_id
        crowd = round(self.world.wards[from_ward].population * CROWD_FOLLOW_SHARE)
        self.world.migrate(from_ward, to_ward, crowd + 1)
        mind.state.ward_id = to_ward
        mind.memory.add(self.world.tick, "action", f"I moved from {self.world.wards[from_ward].name} to {self.world.wards[to_ward].name}.", 9)

    def _spread_posts(self, updates: list[CitizenUpdate]) -> list[FeedPost]:
        feed = []
        for u in updates:
            if not u.post:
                continue
            author = self.minds[u.id]
            feed.append(FeedPost(tick=self.world.tick, citizen_id=u.id, name=author.persona.name, ward_id=u.ward_id, text=u.post))
            for fid in author.friends:
                self.minds[fid].inbox.append(f"Your friend {author.persona.name} posted: \"{u.post}\"")
        return feed

    def _update_ward_mood(self) -> None:
        for wid, ward in self.world.wards.items():
            moods = [m.state.mood for m in self.minds.values() if m.state.ward_id == wid]
            ward.mood = round(sum(moods) / len(moods), 3) if moods else 0.0

    # ---------------------------------------------------------- queries ----

    def citizen_view(self, cid: str) -> CitizenView:
        m = self.minds[cid]
        return CitizenView(persona=m.persona, state=m.state, friends=m.friends, memories=m.memory.recent(30))
