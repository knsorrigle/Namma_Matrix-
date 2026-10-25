"""LLM clients.

Both clients share one method, ``complete_json``. The real client sends the
prompt to an OpenAI-compatible server (Ollama locally, Groq when hosted). The
mock client ignores the prompt and builds a plausible answer from ``payload``,
so the whole simulation runs on any laptop with no model installed.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from ..config import Settings
from .opinions import rule_shifts, stance_of
from .voice import situation_for


@dataclass
class LLMStats:
    calls: int = 0
    failures: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0


class LLM(Protocol):
    stats: LLMStats

    async def complete_json(
        self, task: str, system: str, user: str, payload: dict[str, Any], model: str | None = None
    ) -> dict[str, Any]: ...


def _extract_json(text: str) -> dict[str, Any]:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


class OpenAICompatLLM:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.stats = LLMStats()
        self._sem = asyncio.Semaphore(max(1, settings.llm_concurrency))
        self._client = httpx.AsyncClient(
            base_url=settings.llm_base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {settings.llm_api_key}"},
            timeout=180,
            transport=transport,
        )

    async def complete_json(self, task, system, user, payload, model=None):
        body = {
            "model": model or self.settings.llm_model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2 if task == "godmode" else 0.8,
            "response_format": {"type": "json_object"},
        }
        last_error: Exception | None = None
        for _ in range(2):
            try:
                async with self._sem:
                    started = time.perf_counter()
                    resp = await self._client.post("/chat/completions", json=body)
                    self.stats.seconds += time.perf_counter() - started
                resp.raise_for_status()
                data = resp.json()
                usage = data.get("usage") or {}
                self.stats.calls += 1
                self.stats.prompt_tokens += usage.get("prompt_tokens", 0)
                self.stats.completion_tokens += usage.get("completion_tokens", 0)
                return _extract_json(data["choices"][0]["message"]["content"])
            except (httpx.HTTPError, ValueError, KeyError) as exc:
                last_error = exc
        self.stats.failures += 1
        raise RuntimeError(f"LLM call failed: {last_error}")


class MockLLM:
    """Deterministic stand-in for a model. Good enough to build and test against."""

    def __init__(self, settings: Settings | None = None):
        self.stats = LLMStats()

    async def complete_json(self, task, system, user, payload, model=None):
        self.stats.calls += 1
        self.stats.prompt_tokens += len(system + user) // 4
        if task == "react":
            return {"citizens": [_mock_reaction(c, payload.get("cheapest_ward")) for c in payload["citizens"]]}
        if task == "reflect":
            return {"citizens": [_mock_reflection(c) for c in payload["citizens"]]}
        if task == "godmode":
            # The rule parser stands in for the model in mock mode.
            raise RuntimeError("mock LLM does not parse God Mode commands")
        raise ValueError(f"unknown task {task!r}")


def _mock_reaction(c: dict[str, Any], cheapest_ward: str | None = None) -> dict[str, Any]:
    own = [o.lower() for o in c["observations"] if not o.startswith("Your friend")]
    obs = " ".join(own)
    heard = len(own) < len(c["observations"])
    first = c["name"].split()[0]
    action, mood, post = "stay", 0.0, None
    if "rent in" in obs and "went up" in obs:
        if c["income_band"] == "low":
            thought = f"Rent is climbing again. On my salary I can't keep this up, maybe I should look at a cheaper area."
            action, mood = "consider_moving", -0.3
            post = "Rent hike again in my area. How are working people supposed to live here?"
            if c["mood"] < -0.4 and cheapest_ward and cheapest_ward != c["ward"]:
                thought = "That's it. I can't afford this anymore. I'm moving somewhere cheaper, even if the commute is longer."
                action = "move"
                return {"id": c["id"], "thought": thought, "mood_change": -0.1, "action": action, "move_to": cheapest_ward, "post": post}
        elif c["income_band"] == "middle":
            thought = "Another rent increase. It stings, but moving means a longer commute. Let me wait and see."
            mood = -0.15
        else:
            thought = "Rents are going up around here, which probably means the area is doing well."
            mood = 0.05
    elif "rent in" in obs and "came down" in obs:
        thought = "Rents have eased a little around here. Maybe I can finally save something this month."
        mood = 0.15
    elif "jobs" in obs and (" more " in obs or "open" in obs):
        if c["sector"] == "it":
            thought = "New companies are hiring nearby. Good time to ask for a raise or switch."
            mood, action = 0.25, "look_for_job"
        else:
            thought = "Lots of new offices coming up. More customers maybe, but more traffic for sure."
            mood = 0.05
    elif "jobs" in obs and (" fewer " in obs or "shut" in obs):
        thought = "People are talking about layoffs. I hope my company is safe."
        mood = -0.25
    elif "tax" in obs:
        thought = "A new tax on the big companies. They will pass it on to us somehow."
        mood = -0.05
    elif "fare" in obs:
        if c.get("commutes_by_metro"):
            thought = "Metro fare went up. That's real money every month for my commute."
            mood, post = -0.2, "Metro fare hike is unfair to daily commuters."
        else:
            thought = "Heard the metro fare went up. Glad I don't take it every day."
    elif heard:
        thought = "Everyone in my circle is talking about rents. Maybe they have a point."
        mood = -0.05
    else:
        thought = f"Normal day. Work, traffic, chai, home. {first} needs a holiday."
    # Speak in the citizen's Bengaluru voice when the voice pack has a line for this situation.
    example = (c.get("voice") or {}).get("example")
    if example:
        thought = example
        if post:
            post = example
    # Behaviour follows opinions: strong distrust plus a bad mood turns into action.
    ops = c.get("opinions") or {}
    if action in ("stay", "post") and stance_of(ops.get("government")) <= -0.6 and c["mood"] < -0.3 and "outspoken" in c.get("traits", []):
        action = "protest"
        post = post or "Enough is enough. Going to Freedom Park this weekend, who's coming?"
    elif action == "stay" and stance_of(ops.get("my_area")) <= -0.5 and c["mood"] < -0.3:
        action = "consider_moving"
    shifts = rule_shifts(c, c.get("situation") or situation_for(c["observations"]))
    return {"id": c["id"], "thought": thought, "mood_change": mood, "action": action, "move_to": None, "post": post,
            "opinions": shifts}


def _mock_reflection(c: dict[str, Any]) -> dict[str, Any]:
    ops = c.get("opinions") or {}
    strongest = max(ops, key=lambda k: abs(stance_of(ops[k])), default=None)
    if strongest and abs(stance_of(ops[strongest])) >= 0.6:
        why = ops[strongest].split(": ", 1)[-1]
        belief = f"The more I see, the surer I am: {why}."
    elif c["mood"] < -0.3:
        belief = "Bengaluru is becoming too expensive for people like me."
    elif c["mood"] > 0.3:
        belief = "Things are looking up for me in this city."
    else:
        belief = "The city keeps changing, and I have to keep adjusting."
    return {"id": c["id"], "belief": belief}


def make_llm(settings: Settings) -> LLM:
    if settings.llm_provider == "mock":
        return MockLLM(settings)
    return OpenAICompatLLM(settings)
