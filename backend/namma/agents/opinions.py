"""Opinions: what each citizen thinks about the city, and how that changes.

Every citizen holds a stance on five topics, from -1 (strongly disagree) to +1
(strongly agree), a confidence, and a reason in their own words.

1. Start: stances come from the persona. An IT worker leans towards new tech
   parks, a long-time resident who values a clean environment leans against
   them. A little per-citizen noise keeps two similar people from being clones.
2. Experience: when something happens, the model (or the mock) proposes a
   shift with a reason. The mind filters it through the person's psychology:
   evidence that agrees with what they already think lands in full, evidence
   against it is discounted by how sure they are (confirmation bias), and
   stubborn people move less.
3. Friends: friends' posts and everyday chats pull opinions together, but only
   between people who are not too far apart already (bounded confidence, after
   Deffuant et al. 2000). That is how echo chambers and polarisation emerge
   without anyone being told to form them.
"""

from __future__ import annotations

import random
import re
from statistics import pstdev
from typing import Iterable

from ..contracts import OPINION_TOPICS, Opinion, Persona, TopicStats

MAX_SHIFT = 0.3  # the most one piece of news can move a stance
BOUND = 0.8  # friends further apart than this don't sway each other
SOCIAL_RATE = 0.12  # how far a friend pulls you, before your own openness

LABELS = {"big_companies": "big companies", "government": "the government", "metro": "the metro",
          "my_area": "my area", "future_here": "my future here"}

TRAIT_OPENNESS = {"stubborn": 0.5, "sceptical": 0.8, "sociable": 1.2, "curious": 1.25, "anxious": 1.1}
TRAIT_CONFIDENCE = {"stubborn": 0.25, "outspoken": 0.1, "sceptical": 0.1, "curious": -0.1, "anxious": -0.1, "quiet": -0.05}


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def openness(persona: Persona) -> float:
    """How easily this person is moved by evidence and friends (about 0.4 to 1.6)."""
    o = 1.0
    for t in persona.traits:
        o *= TRAIT_OPENNESS.get(t, 1.0)
    return o


def stance_word(stance: float) -> str:
    if stance >= 0.6:
        return "strongly agree"
    if stance >= 0.2:
        return "agree"
    if stance > -0.2:
        return "unsure"
    if stance > -0.6:
        return "disagree"
    return "strongly disagree"


# ------------------------------------------------------------------ seed ----


def _leanings(p: Persona, rent_ratio: float) -> dict[str, list[tuple[float, str]]]:
    """Persona factors that push each topic, with the reason the citizen would give."""
    low, it = p.income_band == "low", p.sector == "it"
    v, t = set(p.values), set(p.traits)
    f: dict[str, list[tuple[float, str]]] = {k: [] for k in OPINION_TOPICS}

    f["big_companies"] += [
        (0.5 if it else 0.0, "I work in IT, so new companies mean more jobs and better hikes for me"),
        (0.15 if p.sector in ("services", "retail") else 0.0, "more offices nearby means more customers"),
        (-0.25 if low and not it else 0.0, "every new tech park pushes rents up for people like me"),
        (0.25 if "career growth" in v else 0.0, "big companies are where careers grow"),
        (-0.3 if "clean environment" in v else 0.0, "tech parks mean more concrete, traffic and fewer trees"),
        (-0.2 if "tradition" in v else 0.0, "the old Bengaluru is disappearing under glass buildings"),
        (-0.2 if p.age >= 55 else 0.0, "I've watched the garden city turn into traffic jams"),
    ]
    f["government"] += [
        (-0.1, "roads, water and garbage never seem to get fixed"),
        (-0.3 if "sceptical" in t else 0.0, "I don't trust what the government promises"),
        (0.25 if "optimistic" in t else 0.0, "slowly, things like the metro are getting built"),
        (0.15 if "stability" in v or "tradition" in v else 0.0, "at least things run and the city keeps working"),
        (-0.15 if low else 0.0, "nobody in power thinks about workers like me"),
    ]
    f["metro"] += [
        (0.45 if p.commutes_by_metro else 0.0, "the metro saves me hours of traffic every week"),
        (-0.15 if low and not p.commutes_by_metro else 0.0, "the metro doesn't reach where I need to go, and it costs more than the bus"),
        (0.2 if "clean environment" in v else 0.0, "more metro means fewer vehicles and cleaner air"),
        (0.1 if p.age < 30 else 0.0, "the metro is the one thing in this city that works on time"),
    ]
    f["my_area"] += [
        (0.2, "my area has everything I need nearby"),
        (-0.35 if low and rent_ratio > 1.1 else 0.0, "rent here eats most of my salary"),
        (0.2 if "community" in v else 0.0, "I know my neighbours and the shopkeepers here"),
        (0.2 if p.age >= 55 else 0.0, "I've lived here for decades, this is home"),
        (-0.15 if "clean environment" in v else 0.0, "the traffic and dust here keep getting worse"),
    ]
    f["future_here"] += [
        (0.15, "this city has more opportunities than my native place"),
        (0.2 if "career growth" in v or "ambitious" in t else 0.0, "my career can only grow in a city like this"),
        (-0.2 if "anxious" in t else 0.0, "I worry about how long I can afford to stay"),
        (-0.15 if low else 0.0, "it gets harder every year to make ends meet here"),
        (0.1 if p.age < 30 else 0.0, "I'm young and this is where things happen"),
        (0.15 if p.age >= 55 else 0.0, "my whole life is here now"),
    ]
    return f


def seed_opinions(persona: Persona, rent_ratio: float = 1.0, seed: int = 42) -> dict[str, Opinion]:
    """A citizen's starting opinions, from who they are. rent_ratio = their ward's rent / city average."""
    rng = random.Random(f"{seed}-{persona.id}")
    confidence = 0.5 + sum(TRAIT_CONFIDENCE.get(t, 0.0) for t in persona.traits)
    out = {}
    for topic, factors in _leanings(persona, rent_ratio).items():
        stance = _clamp(sum(w for w, _ in factors) + rng.uniform(-0.15, 0.15))
        main = max(factors, key=lambda f: abs(f[0]) if f[0] * stance > 0 else 0)
        why = main[1] if main[0] * stance > 0 else "I haven't really made up my mind about this"
        out[topic] = Opinion(stance=round(stance, 3), confidence=round(_clamp(confidence + abs(stance) * 0.2, 0.2, 0.95), 3), why=why)
    return out


# ----------------------------------------------------------------- update ----


def apply_shift(op: Opinion, shift: float, why: str, persona: Persona, weight: float = 1.0) -> float:
    """Move one opinion by a proposed shift, filtered by the person. Returns the applied change."""
    shift = _clamp(shift, -MAX_SHIFT, MAX_SHIFT) * weight * openness(persona)
    agrees = shift * op.stance >= 0
    if agrees:
        shift *= 1 - abs(op.stance)  # views firm up more slowly the stronger they already are
    else:
        shift *= 1 - op.confidence  # confirmation bias: contrary evidence is discounted
    before = op.stance
    op.stance = round(_clamp(op.stance + shift), 3)
    applied = op.stance - before
    if agrees:
        op.confidence = round(min(0.95, op.confidence + abs(applied) * 0.3), 3)
    else:
        op.confidence = round(max(0.2, op.confidence - abs(applied) * 0.5), 3)
    if abs(applied) >= 0.05 and why:
        op.why = why.strip()[:160]
    return round(applied, 3)


def social_pull(mine: Opinion, theirs: float, persona: Persona) -> float:
    """A friend's stance pulls mine closer, unless we're too far apart to listen. Returns the change."""
    gap = theirs - mine.stance
    if abs(gap) > BOUND:
        return 0.0
    change = SOCIAL_RATE * openness(persona) * (1 - mine.confidence) * gap
    mine.stance = round(_clamp(mine.stance + change), 3)
    return round(change, 3)


def opinion_card(opinions: dict[str, Opinion]) -> dict[str, str]:
    """Compact form for the prompt: 'disagree (-0.4): rent here eats most of my salary'."""
    return {k: f"{stance_word(o.stance)} ({o.stance:+.1f}): {o.why}" for k, o in opinions.items()}


def stance_of(card_value: str | None) -> float:
    """Read the number back out of an opinion_card line (the mock model uses this)."""
    m = re.search(r"\(([+-]\d+(?:\.\d+)?)\)", card_value or "")
    return float(m.group(1)) if m else 0.0


def summarize(opinions: Iterable[dict[str, Opinion]]) -> dict[str, TopicStats]:
    """City-wide view per topic: average stance, who agrees, who disagrees, how split it is."""
    groups = list(opinions)
    out = {}
    for topic in OPINION_TOPICS:
        xs = [g[topic].stance for g in groups if topic in g]
        if not xs:
            continue
        out[topic] = TopicStats(
            mean=round(sum(xs) / len(xs), 3),
            agree=round(sum(x >= 0.2 for x in xs) / len(xs), 3),
            disagree=round(sum(x <= -0.2 for x in xs) / len(xs), 3),
            spread=round(pstdev(xs), 3),
        )
    return out


# ------------------------------------------------------------- mock rules ----


def rule_shifts(c: dict, situation: str) -> list[dict]:
    """What the mock model proposes for a situation. A real model writes its own."""
    low, it = c["income_band"] == "low", c["sector"] == "it"
    metro, green = c.get("commutes_by_metro"), "clean environment" in c.get("values", [])
    s: list[dict] = []
    if situation == "rent_up":
        s.append({"topic": "my_area", "shift": -0.25 if low else -0.1, "why": "rents here keep climbing faster than my pay"})
        if not it:
            s.append({"topic": "big_companies", "shift": -0.15 if low else -0.05, "why": "every new office nearby pushes my rent up"})
        if low:
            s.append({"topic": "future_here", "shift": -0.1, "why": "I'm not sure how long I can afford this city"})
    elif situation == "rent_down":
        s.append({"topic": "my_area", "shift": 0.1, "why": "rent has finally eased a little around here"})
    elif situation == "jobs_up":
        if it:
            s += [{"topic": "big_companies", "shift": 0.2, "why": "new companies hiring nearby means better offers for me"},
                  {"topic": "future_here", "shift": 0.1, "why": "there's real growth happening here"}]
        elif green:
            s.append({"topic": "big_companies", "shift": -0.1, "why": "more offices means more traffic and dust"})
        else:
            s.append({"topic": "big_companies", "shift": 0.05, "why": "new offices bring more customers and work"})
    elif situation == "jobs_down":
        s.append({"topic": "big_companies", "shift": -0.15, "why": "these companies drop people the moment profits dip"})
        if it:
            s.append({"topic": "future_here", "shift": -0.15, "why": "layoffs make me wonder if I should stay"})
    elif situation == "cost_up":
        obs = " ".join(c.get("observations", [])).lower()
        if "fare" in obs:
            s.append({"topic": "metro", "shift": -0.2 if metro else -0.05, "why": "the metro is getting too costly for a daily commute"})
            s.append({"topic": "government", "shift": -0.15 if metro else -0.05, "why": "they raise fares instead of fixing anything"})
        elif "tax" in obs:
            s.append({"topic": "government", "shift": -0.1 if it else 0.05,
                      "why": "taxing companies only drives jobs away" if it else "good, the big companies should pay their share"})
        else:
            s.append({"topic": "government", "shift": -0.1, "why": "prices go up and nobody in charge does anything"})
    elif situation == "flood":
        s += [{"topic": "government", "shift": -0.25, "why": "the same roads flood every year and nothing changes"},
              {"topic": "my_area", "shift": -0.15, "why": "one hour of rain and my street turns into a lake"}]
    return s
