"""Full-mind citizens: perceive, remember, react, reflect.

A citizen only calls the LLM when something in its world changed (or when it
is picked as an idle thinker), and several citizens share one LLM call. That
keeps a 25-citizen city cheap enough to run on a laptop.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from ..contracts import CitizenState, CitizenUpdate, Persona, WorldEvent
from .memory import MemoryStream

if TYPE_CHECKING:
    from ..world import WorldEngine

ACTIONS = ("stay", "consider_moving", "move", "look_for_job", "protest", "post")
RENT_NOTICE = 0.03  # a 3% move in rent is noticed
JOBS_NOTICE = 0.03


class CitizenMind:
    def __init__(self, persona: Persona):
        self.persona = persona
        self.state = CitizenState(id=persona.id, ward_id=persona.ward_id)
        self.memory = MemoryStream()
        self.friends: list[str] = []
        self.inbox: list[str] = []  # messages from friends, read on the next tick
        self._seen_rent: float | None = None
        self._seen_ward: str | None = None
        self._seen_jobs: float | None = None
        self._seen_city: dict[str, float] = {}

    # -------------------------------------------------------- perceive ----

    def perceive(self, world: "WorldEngine", new_events: list[WorldEvent]) -> list[tuple[str, int]]:
        """Return (observation, importance) pairs for what this citizen noticed."""
        p, ward = self.persona, world.wards[self.state.ward_id]
        obs: list[tuple[str, int]] = []

        # Small drifts add up: the reference only moves once a change is noticed.
        if self._seen_rent is None or self._seen_ward != ward.id:
            self._seen_rent, self._seen_ward = ward.rent, ward.id
        change = ward.rent / self._seen_rent - 1
        if abs(change) >= RENT_NOTICE:
            verb = "went up" if change > 0 else "came down"
            obs.append((f"Rent in {ward.name} {verb} {abs(change):.0%} to about Rs {ward.rent:,.0f}.", 6 if change > 0 else 4))
            self._seen_rent = ward.rent
        jobs_here = ward.jobs.get(p.sector, 0)
        if not self._seen_jobs:
            self._seen_jobs = jobs_here
        change = jobs_here / max(1, self._seen_jobs) - 1
        if abs(change) >= JOBS_NOTICE:
            word = "more" if change > 0 else "fewer"
            obs.append((f"There are {abs(change):.0%} {word} {p.sector} jobs in {ward.name} now.", 6))
            self._seen_jobs = jobs_here

        city = world.city.model_dump()
        for key, label in (("corporate_tax", "corporate tax"), ("metro_fare", "metro fare"), ("fuel_price", "petrol price")):
            before = self._seen_city.get(key)
            if before is not None and city[key] != before:
                verb = "raised" if city[key] > before else "cut"
                importance = 7 if (key == "metro_fare" and p.commutes_by_metro) else 4
                obs.append((f"The government {verb} the {label} from {before:g} to {city[key]:g}.", importance))

        for ev in new_events:
            if self.state.ward_id in ev.wards or not ev.wards:
                obs.append((f"News: {ev.headline}", 5))

        for msg in self.inbox:
            obs.append((msg, 3))
        self.inbox = []

        self._seen_city = city
        return obs

    # ---------------------------------------------------------- prompt ----

    def prompt_card(self, observations: list[str], tick: int) -> dict:
        p = self.persona
        memories = self.memory.retrieve(" ".join(observations) or p.job, now=tick, k=5)
        return {
            "id": p.id,
            "name": p.name,
            "age": p.age,
            "job": p.job,
            "sector": p.sector,
            "income_band": p.income_band,
            "ward": self.state.ward_id,
            "family": p.family,
            "values": p.values,
            "traits": p.traits,
            "commutes_by_metro": p.commutes_by_metro,
            "mood": round(self.state.mood, 2),
            "beliefs": self.state.beliefs[-2:],
            "memories": [m.text for m in memories],
            "observations": observations,
        }

    # ----------------------------------------------------------- react ----

    def apply_reaction(self, r: dict, tick: int, ward_ids: set[str]) -> tuple[CitizenUpdate, str | None]:
        """Apply one LLM reaction. Returns the update and the ward to move to, if any."""
        thought = str(r.get("thought") or "").strip()[:400] or "..."
        try:
            delta = float(r.get("mood_change") or 0)
        except (TypeError, ValueError):
            delta = 0.0
        delta = max(-0.5, min(0.5, delta))
        self.state.mood = max(-1.0, min(1.0, self.state.mood * 0.9 + delta))

        action = r.get("action") if r.get("action") in ACTIONS else "stay"
        move_to = r.get("move_to")
        if action == "move" and (move_to not in ward_ids or move_to == self.state.ward_id):
            action = "consider_moving"
        self.state.last_action = action
        self.state.considering_move = action in ("consider_moving", "move")
        self.state.last_thought = thought

        self.memory.add(tick, "thought", thought, 4)
        if action != "stay":
            self.memory.add(tick, "action", f"I decided to {action.replace('_', ' ')}.", 5)

        post = r.get("post")
        post = str(post).strip()[:280] if post else None
        return CitizenUpdate(
            id=self.persona.id,
            ward_id=self.state.ward_id,
            thought=thought,
            action=action,
            mood=round(self.state.mood, 3),
            post=post,
        ), (move_to if action == "move" else None)

    def wants_reflection(self) -> bool:
        return self.memory.importance_since_reflection >= 25

    def apply_reflection(self, belief: str, tick: int) -> None:
        belief = belief.strip()[:300]
        if belief and belief not in self.state.beliefs[-3:]:
            self.state.beliefs.append(belief)
            self.memory.add(tick, "reflection", belief, 8)
        self.memory.importance_since_reflection = 0


REACT_SYSTEM = """You simulate residents of Bengaluru, India, in 2026 for a university research simulation.
Every resident is fictional. For each resident, write their private inner thought, in first person,
reacting to what they just noticed, consistent with their persona, memories and beliefs.
Rules:
- 1 or 2 sentences per thought, natural Indian English. A Kannada or Hindi word is fine.
- People react differently: income, job, family and values matter. Not everyone is upset.
- Never mention or stereotype caste or religion. Keep politics about policies, not parties.
- mood_change is between -0.5 and 0.5.
- action is one of: stay, consider_moving, move, look_for_job, protest, post.
- move_to is a ward id from the list only when action is move, otherwise null.
- post is a short public social media post, or null. Most residents do not post.
Return only JSON: {"citizens": [{"id", "thought", "mood_change", "action", "move_to", "post"}]}"""

REFLECT_SYSTEM = """You simulate residents of Bengaluru, India, for a research simulation. Each resident is fictional.
For each resident, read their recent memories and write ONE belief they now hold about their life or city,
in first person, under 25 words. Never mention or stereotype caste or religion.
Return only JSON: {"citizens": [{"id", "belief"}]}"""


def react_user_prompt(cards: list[dict], wards: list[dict]) -> str:
    return (
        "Wards (id: name, rent): "
        + "; ".join(f"{w['id']}: {w['name']}, Rs {w['rent']:,.0f}" for w in wards)
        + "\n\nResidents:\n"
        + "\n".join(json.dumps(c, ensure_ascii=False) for c in cards)
    )


def reflect_user_prompt(cards: list[dict]) -> str:
    return "Residents:\n" + "\n".join(json.dumps(c, ensure_ascii=False) for c in cards)
