"""God Mode: turn a plain-English command into structured world changes.

The LLM parser is tried first. Its output is validated against the
WorldChange contract, and anything invalid is dropped with a warning. If the
LLM is unavailable or returns nothing usable, a keyword rule parser takes
over, so the demo never depends on a model behaving.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from .agents.llm import LLM
from .contracts import CITY_METRICS, WARD_METRICS, GodModeParse, Ward, WorldChange

GODMODE_SYSTEM = """You convert a natural-language command about a simulated Bengaluru into structured world changes.
Return only JSON: {"headline": str, "changes": [{"target", "metric", "op", "value", "reason"}]}
- headline: a one-line news headline citizens would read, under 90 characters.
- target: a ward id from the list, or "city" for city-wide levers.
- metric for a ward: %s
- metric for "city": %s
- op: "add" (add value), "mul" (multiply by value, e.g. 1.15 for +15%%), or "set".
- Jobs are counts, so prefer "mul" for job changes. corporate_tax is in percent points, so "add" 8 means +8 points.
- Only include changes the command implies. If no ward is named for a local change, pick the most fitting ward.
Example: "Three big MNCs open in Whitefield, but the government taxes them heavily" ->
{"headline": "Three MNCs open Whitefield campuses as state hikes corporate tax",
 "changes": [{"target": "whitefield", "metric": "jobs.it", "op": "mul", "value": 1.15, "reason": "three MNC campuses"},
             {"target": "city", "metric": "corporate_tax", "op": "add", "value": 8, "reason": "heavy tax on MNCs"}]}"""

_NUM_WORDS = {"a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
              "ten": 10, "few": 3, "several": 4, "many": 5, "big": 1}
_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent|per cent)")
_UP = ("raise", "rais", "increase", "hike", "up", "more", "higher", "heav", "add", "double", "spike", "jump")
_DOWN = ("cut", "reduce", "lower", "drop", "fewer", "less", "slash", "remove", "decrease", "fall")


class GodMode:
    def __init__(self, llm: LLM, model: str | None = None):
        self.llm = llm
        self.model = model

    async def parse(self, text: str, wards: list[Ward]) -> GodModeParse:
        try:
            return await self._parse_llm(text, wards)
        except Exception as exc:  # any LLM trouble falls back to rules
            result = parse_rules(text, wards)
            if not isinstance(exc, RuntimeError) or "mock" not in str(exc):
                result.warnings.append(f"LLM parser unavailable ({exc}); used keyword rules.")
            return result

    async def _parse_llm(self, text: str, wards: list[Ward]) -> GodModeParse:
        system = GODMODE_SYSTEM % (", ".join(WARD_METRICS), ", ".join(CITY_METRICS))
        user = "Wards: " + json.dumps([{"id": w.id, "name": w.name} for w in wards]) + f"\nCommand: {text}"
        raw = await self.llm.complete_json("godmode", system, user, {"text": text}, model=self.model)
        ward_ids = {w.id for w in wards}
        changes, warnings = [], []
        for item in raw.get("changes", []):
            try:
                change = WorldChange(**item)
            except (ValidationError, TypeError) as exc:
                warnings.append(f"Dropped an invalid change {item}: {exc}")
                continue
            if change.target != "city" and change.target not in ward_ids:
                warnings.append(f"Dropped a change for unknown ward {change.target!r}")
                continue
            changes.append(change)
        if not changes:
            raise ValueError("LLM returned no valid changes")
        headline = str(raw.get("headline") or text)[:120]
        return GodModeParse(text=text, headline=headline, changes=changes, warnings=warnings, parser="llm")


# ------------------------------------------------------------ rules ----


def _has(text: str, words: tuple[str, ...]) -> bool:
    return any(re.search(rf"\b{re.escape(w)}", text) for w in words)


def _direction(text: str) -> int:
    if _has(text, _DOWN):
        return -1
    return 1


def _count(text: str, noun: str) -> int:
    m = re.search(rf"\b(\d+|{'|'.join(_NUM_WORDS)})\s+(?:\w+\s+){{0,2}}{noun}", text)
    if not m:
        return 1
    token = m.group(1)
    return int(token) if token.isdigit() else _NUM_WORDS[token]


def _wards_in(text: str, wards: list[Ward]) -> list[str]:
    found = []
    for w in wards:
        names = {w.name.lower(), w.id.replace("_", " ")}
        if any(n in text for n in names):
            found.append(w.id)
    return found


def parse_rules(text: str, wards: list[Ward]) -> GodModeParse:
    lowered = text.lower()
    all_named = _wards_in(lowered, wards)
    clauses = [c for c in re.split(r"\bbut\b|\bwhile\b|;|\.|,|\band then\b", lowered) if c.strip()]
    changes: list[WorldChange] = []
    warnings: list[str] = []

    def local(clause: str, metric: str, op: str, value: float, reason: str, fallback: str | None = None) -> None:
        targets = _wards_in(clause, wards) or all_named or ([fallback] if fallback else [w.id for w in wards])
        for t in targets:
            changes.append(WorldChange(target=t, metric=metric, op=op, value=round(value, 4), reason=reason))

    top_it = max(wards, key=lambda w: w.jobs.get("it", 0)).id

    for clause in clauses:
        pct_m = _PCT.search(clause)
        pct = float(pct_m.group(1)) / 100 if pct_m else None
        sign = _direction(clause)

        if "tax" in clause:
            points = (pct * 100) if pct else (8 if "heav" in clause else 5)
            changes.append(WorldChange(target="city", metric="corporate_tax", op="add", value=sign * points, reason=clause.strip()))
        elif "fare" in clause:
            changes.append(WorldChange(target="city", metric="metro_fare", op="mul", value=1 + sign * (pct or 0.2), reason=clause.strip()))
        elif _has(clause, ("petrol", "fuel", "diesel")):
            changes.append(WorldChange(target="city", metric="fuel_price", op="mul", value=1 + sign * (pct or 0.1), reason=clause.strip()))
        elif _has(clause, ("layoff", "lay off", "shut", "close", "leave", "exit")) and _has(clause, ("mnc", "it ", "tech", "compan", "startup", "office")):
            n = _count(clause, r"(?:mnc|compan|startup|office)")
            local(clause, "jobs.it", "mul", 1 - (pct or min(0.5, 0.05 * n)), clause.strip(), top_it)
        elif _has(clause, ("mnc", "tech park", "it compan", "startup", "campus", "it hub")):
            n = _count(clause, r"(?:mnc|compan|startup|campus|tech)")
            factor = 1 + sign * (pct or min(0.5, 0.05 * n))
            local(clause, "jobs.it", "mul", factor, clause.strip(), top_it)
        elif _has(clause, ("factory", "factories", "manufactur", "plant")):
            local(clause, "jobs.manufacturing", "mul", 1 + sign * (pct or 0.1), clause.strip())
        elif "rent" in clause:
            if _has(clause, ("cap", "control", "freeze")):
                local(clause, "rent", "mul", 0.95, clause.strip())
            else:
                local(clause, "rent", "mul", 1 + sign * (pct or 0.1), clause.strip())
        elif _has(clause, ("flood", "rain", "waterlog")):
            local(clause, "traffic", "add", 25, clause.strip())
        elif "metro" in clause and _has(clause, ("line", "station", "open")):
            local(clause, "traffic", "mul", 0.85, clause.strip())
            local(clause, "rent", "mul", 1.05, clause.strip())
        elif _has(clause, ("migrant", "people move", "influx", "population")):
            local(clause, "population", "mul", 1 + sign * (pct or 0.05), clause.strip())

    if not changes:
        warnings.append("No known change found. Try naming jobs, rent, tax, metro fare, fuel, factories or a flood, and a ward.")
    headline = text.strip()[:1].upper() + text.strip()[1:120]
    return GodModeParse(text=text, headline=headline, changes=changes, warnings=warnings, parser="rules")
