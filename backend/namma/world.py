"""World engine: ward state and the deterministic rules that move it each tick.

No LLM here. Plain rules keep the world predictable and testable; the LLM only
drives what citizens think and do. YOGI owns the rules in ``step``: the
numbers below are first guesses to be tuned against real data.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .contracts import SECTORS, CityParams, Ward, WorldChange, WorldEvent

START_DATE = date(2026, 11, 2)
TICK_DAYS = 1
APPROACH = 0.3  # share of the gap to a target closed each tick


class WorldEngine:
    def __init__(self, wards: list[Ward], city: CityParams | None = None):
        self.wards: dict[str, Ward] = {w.id: w for w in wards}
        self.city = city or CityParams()
        self.tick = 0
        self.events: list[WorldEvent] = []
        self._base = {w.id: w.model_copy(deep=True) for w in wards}
        self._base_city = self.city.model_copy()
        # Job levels God Mode asked for, before city-wide effects like tax.
        self._job_targets = {w.id: dict(w.jobs) for w in wards}

    @classmethod
    def from_file(cls, path: Path) -> "WorldEngine":
        raw = json.loads(path.read_text())
        return cls([Ward(**w) for w in raw["wards"]], CityParams(**raw.get("city", {})))

    @property
    def sim_date(self) -> str:
        return (START_DATE + timedelta(days=self.tick * TICK_DAYS)).isoformat()

    # --------------------------------------------------------- God Mode ----

    def apply_change(self, change: WorldChange) -> None:
        if change.target == "city":
            current = getattr(self.city, change.metric)
            setattr(self.city, change.metric, _apply(current, change.op, change.value))
            return
        ward = self.wards[change.target]
        if change.metric.startswith("jobs."):
            sector = change.metric.split(".", 1)[1]
            targets = self._job_targets[ward.id]
            targets[sector] = max(0, round(_apply(targets.get(sector, 0), change.op, change.value)))
            return  # jobs move toward the new target over the next ticks
        value = _apply(getattr(ward, change.metric), change.op, change.value)
        if change.metric == "population":
            value = round(value)
        setattr(ward, change.metric, max(0, value))
        if change.metric == "rent":
            # A direct rent change resets the baseline the market drifts toward.
            self._base[ward.id].rent = ward.rent

    def add_event(self, kind: str, headline: str, wards: list[str]) -> WorldEvent:
        ev = WorldEvent(tick=self.tick, kind=kind, headline=headline, wards=wards)
        self.events.append(ev)
        return ev

    # ------------------------------------------------------------ rules ----

    def step(self) -> None:
        self.tick += 1
        tax_gap = self.city.corporate_tax - self._base_city.corporate_tax
        for wid, ward in self.wards.items():
            base = self._base[wid]

            # Jobs drift toward their targets; higher corporate tax shrinks
            # the target for IT and, less so, services.
            for sector in SECTORS:
                target = self._job_targets[wid].get(sector, 0)
                if sector == "it":
                    target *= max(0.5, 1 - 0.006 * tax_gap)
                elif sector == "services":
                    target *= max(0.7, 1 - 0.002 * tax_gap)
                now = ward.jobs.get(sector, 0)
                ward.jobs[sector] = round(now + (target - now) * APPROACH)

            job_ratio = sum(ward.jobs.values()) / max(1, sum(base.jobs.values()))

            # Workers move closer to new jobs (newcomers to the city included).
            target_pop = base.population * job_ratio**0.6
            ward.population = round(ward.population + (target_pop - ward.population) * APPROACH / 3)
            pop_ratio = ward.population / max(1, base.population)

            # Rent follows demand: jobs nearby and people living here.
            target_rent = base.rent * job_ratio**1.2 * pop_ratio**0.8
            ward.rent = round(ward.rent + (target_rent - ward.rent) * APPROACH, 2)

            rent_ratio = ward.rent / base.rent
            ward.prices = round(100 * rent_ratio**0.3 * (self.city.fuel_price / self._base_city.fuel_price) ** 0.1, 2)
            ward.traffic = round(min(100.0, base.traffic * (0.5 * job_ratio + 0.5 * pop_ratio)), 2)
            ward.pollution = round(base.pollution * (0.6 + 0.4 * ward.traffic / max(1.0, base.traffic)), 2)

    def migrate(self, from_ward: str, to_ward: str, people: int) -> None:
        people = min(people, self.wards[from_ward].population)
        self.wards[from_ward].population -= people
        self.wards[to_ward].population += people

    def cheapest_ward(self, exclude: str) -> str:
        return min((w for w in self.wards.values() if w.id != exclude), key=lambda w: w.rent).id


def _apply(current: float, op: str, value: float) -> float:
    if op == "add":
        return current + value
    if op == "mul":
        return current * value
    return value
