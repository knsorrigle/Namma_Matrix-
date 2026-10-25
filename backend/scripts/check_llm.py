"""Check that the configured model works with Namma Matrix, and how fast it is.

Run from backend/ after setting up backend/.env:
  python scripts/check_llm.py

It sends one God Mode parse and one batch of citizen reactions, then prints
what came back, how long each call took and how many tokens it used.
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from namma.agents.citizen import REACT_SYSTEM, CitizenMind, react_user_prompt  # noqa: E402
from namma.agents.llm import make_llm  # noqa: E402
from namma.config import Settings  # noqa: E402
from namma.contracts import Persona  # noqa: E402
from namma.godmode import GodMode  # noqa: E402
from namma.world import WorldEngine  # noqa: E402


async def main() -> None:
    s = Settings()
    print(f"provider={s.llm_provider} url={s.llm_base_url} model={s.llm_model} godmode_model={s.godmode_model}")
    if s.llm_provider == "mock":
        print("LLM_PROVIDER is mock. Set LLM_PROVIDER=openai in backend/.env to test a real model.")
        return
    llm = make_llm(s)
    world = WorldEngine.from_file(s.data_dir / "wards.sample.json")
    wards = list(world.wards.values())

    t = time.perf_counter()
    parsed = await GodMode(llm, s.godmode_model).parse(
        "Three big MNCs open in Whitefield, but the government adds a heavy tax on them.", wards)
    print(f"\nGod Mode ({parsed.parser}, {time.perf_counter() - t:.1f}s): {parsed.headline}")
    for c in parsed.changes:
        print(f"  {c.target}.{c.metric} {c.op} {c.value}")
    for w in parsed.warnings:
        print(f"  warning: {w}")

    personas = [Persona(**p) for p in json.loads((s.data_dir / "citizens.sample.json").read_text())["citizens"][:5]]
    obs = ["Rent in Whitefield went up 6% to about Rs 25,400.", "News: Three big MNCs open in Whitefield campuses."]
    cards = [CitizenMind(p).prompt_card(obs, tick=1) for p in personas]
    user = react_user_prompt(cards, [w.model_dump() for w in wards])
    before = llm.stats.completion_tokens
    t = time.perf_counter()
    try:
        raw = await llm.complete_json("react", REACT_SYSTEM, user, {"citizens": cards})
    except Exception as exc:
        print(f"\nCitizen batch FAILED: {exc}")
        return
    secs = time.perf_counter() - t
    rows = raw.get("citizens", [])
    print(f"\nCitizen batch ({secs:.1f}s for {len(cards)} citizens, {len(rows)} answers):")
    for r in rows:
        print(f"  {r.get('id')} [{r.get('action')}, mood {r.get('mood_change')}] {r.get('thought')}")
    out = llm.stats.completion_tokens - before
    if out:
        print(f"\nOutput speed about {out / secs:.0f} tokens/s.")
    print(f"Totals: {llm.stats.calls} calls, {llm.stats.prompt_tokens} prompt tokens, "
          f"{llm.stats.completion_tokens} completion tokens, {llm.stats.failures} failures.")
    print(f"A tick with 10 thinking citizens is 2 batches, so roughly {2 * secs:.0f}s on this setup.")


if __name__ == "__main__":
    asyncio.run(main())
