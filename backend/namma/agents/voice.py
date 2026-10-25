"""Bengaluru voice: how a citizen sounds, and what the city is saying.

The voice pack (data/voice/voice_pack.json) gives each kind of resident a
speaking style, a few local phrases and one example line per situation. The
city pulse (data/pulse/) holds short anonymised takes on local issues. Both go
into the citizen's prompt card, so the model writes in a local voice without
any fine-tuning.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from ..contracts import Persona

SITUATION_TOPIC = {"rent_up": "rent", "rent_down": "rent", "jobs_up": "jobs", "jobs_down": "layoffs",
                   "cost_up": "cost", "heard": "rent", "calm": "traffic"}


@lru_cache(maxsize=4)
def load_pack(data_dir: Path) -> dict:
    path = data_dir / "voice" / "voice_pack.json"
    return json.loads(path.read_text()) if path.exists() else {"archetypes": []}


@lru_cache(maxsize=4)
def load_pulse(data_dir: Path) -> dict:
    for name in ("pulse.json", "pulse.sample.json"):
        path = data_dir / "pulse" / name
        if path.exists():
            return json.loads(path.read_text())
    return {"topics": {}}


def archetype_for(persona: Persona, pack: dict) -> dict | None:
    for a in pack["archetypes"]:
        m = a["match"]
        if "sectors" in m and persona.sector not in m["sectors"]:
            continue
        if "jobs" in m and persona.job not in m["jobs"]:
            continue
        if "income_bands" in m and persona.income_band not in m["income_bands"]:
            continue
        if "max_age" in m and persona.age > m["max_age"]:
            continue
        if "min_age" in m and persona.age < m["min_age"]:
            continue
        return a
    return None


def situation_for(observations: list[str]) -> str:
    own = " ".join(o.lower() for o in observations if not o.startswith("Your friend"))
    heard = any(o.startswith("Your friend") for o in observations)
    if "rent in" in own and "went up" in own:
        return "rent_up"
    if "rent in" in own and "came down" in own:
        return "rent_down"
    if "jobs" in own and (" more " in own or "open" in own):
        return "jobs_up"
    if "jobs" in own and (" fewer " in own or "shut" in own):
        return "jobs_down"
    if any(w in own for w in ("tax", "fare", "petrol")):
        return "cost_up"
    return "heard" if heard else "calm"


def _pick(items: list, key: str, n: int) -> list:
    """Deterministic choice per citizen, so the same person keeps the same flavour."""
    if not items:
        return []
    start = sum(map(ord, key)) % len(items)
    return [items[(start + i) % len(items)] for i in range(min(n, len(items)))]


def voice_card(persona: Persona, observations: list[str], data_dir: Path) -> dict:
    """The voice and local-chatter part of a citizen's prompt card."""
    pack, pulse = load_pack(data_dir), load_pulse(data_dir)
    situation = situation_for(observations)
    card: dict = {"situation": situation}
    archetype = archetype_for(persona, pack)
    if archetype:
        card["voice"] = {
            "type": archetype["id"],
            "style": archetype["style"],
            "phrases": _pick(archetype["phrases"], persona.id, 4),
            "example": archetype["examples"].get(situation),
        }
    chatter = pulse["topics"].get(SITUATION_TOPIC[situation], [])
    if chatter and situation != "calm":
        card["local_chatter"] = _pick(chatter, persona.id + situation, 2)
    return card
