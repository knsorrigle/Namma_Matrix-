"""Shared data contracts for Namma Matrix.

Every part of the system (world engine, citizens, God Mode, dashboard) talks in
these shapes. Change them only after the team agrees, and update
docs/contracts.md in the same pull request.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

SECTORS = ("it", "manufacturing", "services", "retail", "construction")

# Metrics God Mode may change on a single ward.
WARD_METRICS = ("rent", "prices", "traffic", "pollution", "population") + tuple(
    f"jobs.{s}" for s in SECTORS
)
# Metrics that apply to the whole city.
CITY_METRICS = ("corporate_tax", "metro_fare", "fuel_price")

Action = Literal["stay", "consider_moving", "move", "look_for_job", "protest", "post"]
IncomeBand = Literal["low", "middle", "high"]


# ---------------------------------------------------------------- world ----


class Ward(BaseModel):
    """State of one ward. Owned by the world engine."""

    id: str
    name: str
    lat: float
    lng: float
    population: int
    rent: float = Field(description="Average 1BHK rent, INR per month")
    jobs: dict[str, int] = Field(description="Jobs located in the ward, by sector")
    prices: float = Field(100.0, description="Cost-of-living index, 100 = start of run")
    traffic: float = Field(description="Congestion index, 0 to 100")
    pollution: float = Field(description="AQI-style index")
    mood: float = Field(0.0, ge=-1, le=1, description="Average citizen mood, -1 to 1")
    source_note: str = ""


class CityParams(BaseModel):
    """City-wide levers."""

    corporate_tax: float = Field(25.0, description="Percent")
    metro_fare: float = Field(40.0, description="Average fare, INR")
    fuel_price: float = Field(103.0, description="Petrol, INR per litre")


# ------------------------------------------------------------- citizens ----


class Persona(BaseModel):
    """Who a citizen is. Static for the whole run."""

    id: str
    name: str
    age: int
    gender: str
    ward_id: str
    job: str
    sector: str
    income_band: IncomeBand
    language: str
    family: str
    values: list[str]
    traits: list[str]
    commutes_by_metro: bool = False
    bio: str = ""


class MemoryItem(BaseModel):
    tick: int
    kind: Literal["observation", "thought", "reflection", "action"]
    text: str
    importance: int = Field(ge=1, le=10)


class CitizenState(BaseModel):
    """What changes about a citizen during a run."""

    id: str
    ward_id: str
    mood: float = Field(0.0, ge=-1, le=1)
    employed: bool = True
    beliefs: list[str] = Field(default_factory=list)
    last_thought: str = ""
    last_action: Action = "stay"
    considering_move: bool = False


class CitizenView(BaseModel):
    """Everything the citizen inspector shows for one person."""

    persona: Persona
    state: CitizenState
    friends: list[str]
    memories: list[MemoryItem]


# ------------------------------------------------------------- God Mode ----


class WorldChange(BaseModel):
    """One structured change produced by the God Mode parser."""

    target: str = Field(description='A ward id, or "city" for city-wide levers')
    metric: str
    op: Literal["add", "mul", "set"]
    value: float
    reason: str = ""

    @model_validator(mode="after")
    def _metric_fits_target(self) -> "WorldChange":
        allowed = CITY_METRICS if self.target == "city" else WARD_METRICS
        if self.metric not in allowed:
            raise ValueError(f"metric {self.metric!r} is not allowed for target {self.target!r}")
        if self.op == "mul" and not 0 < self.value <= 10:
            raise ValueError("mul value must be between 0 and 10")
        return self


class GodModeRequest(BaseModel):
    text: str = Field(min_length=3, max_length=500)


class GodModeParse(BaseModel):
    """The preview shown to the user before they apply a command."""

    text: str
    headline: str
    changes: list[WorldChange]
    warnings: list[str] = Field(default_factory=list)
    parser: Literal["llm", "rules"] = "rules"


class GodModeApply(BaseModel):
    text: str
    headline: str
    changes: list[WorldChange]


# --------------------------------------------------------- tick stream ----


class WorldEvent(BaseModel):
    tick: int
    kind: Literal["godmode", "news", "rumour", "shock"]
    headline: str
    wards: list[str]


class CitizenUpdate(BaseModel):
    id: str
    ward_id: str
    thought: str
    action: Action
    mood: float
    post: str | None = None


class FeedPost(BaseModel):
    tick: int
    citizen_id: str
    name: str
    ward_id: str
    text: str


class TickEvent(BaseModel):
    """Sent over the WebSocket after every tick."""

    type: Literal["tick"] = "tick"
    tick: int
    sim_date: str
    wards: list[Ward]
    city: CityParams
    citizens: list[CitizenUpdate]
    feed: list[FeedPost]
    events: list[WorldEvent]
    thinking: int = Field(description="Citizens that called the LLM this tick")
    llm_calls: int
    tick_seconds: float
