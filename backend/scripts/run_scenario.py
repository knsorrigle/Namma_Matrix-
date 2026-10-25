"""Run a scenario headless and save it as a replay.

Example:
  python scripts/run_scenario.py --ticks 20 --at 3 \
      --command "Three big MNCs open in Whitefield, but the government adds a heavy tax on them."

The replay lands in backend/runs/ as JSONL, one TickEvent per line, which the
dashboard can play back without any live model calls.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from namma.config import Settings  # noqa: E402
from namma.contracts import GodModeApply  # noqa: E402
from namma.sim import Simulation  # noqa: E402


async def main(args: argparse.Namespace) -> None:
    sim = Simulation(Settings())
    for _ in range(args.ticks):
        if args.command and sim.world.tick == args.at:
            parsed = await sim.godmode.parse(args.command, list(sim.world.wards.values()))
            print(f"\nGOD MODE ({parsed.parser}): {parsed.headline}")
            for c in parsed.changes:
                print(f"  {c.target}.{c.metric} {c.op} {c.value}")
            for w in parsed.warnings:
                print(f"  warning: {w}")
            await sim.apply_godmode(GodModeApply(text=parsed.text, headline=parsed.headline, changes=parsed.changes))
        ev = await sim.tick()
        rents = "  ".join(f"{w.id[:6]} Rs{w.rent:,.0f} mood {w.mood:+.2f}" for w in ev.wards)
        print(f"\ntick {ev.tick} {ev.sim_date}  thinking {ev.thinking}  llm calls {ev.llm_calls}  {ev.tick_seconds}s\n  {rents}")
        for u in ev.citizens[: args.show]:
            print(f"  {sim.minds[u.id].persona.name:16} [{u.action}] {u.thought}")
        for p in ev.feed:
            print(f"  POST {p.name}: {p.text}")
    s = sim.llm.stats
    print(f"\nLLM calls {s.calls}, failures {s.failures}, prompt tokens {s.prompt_tokens}, completion tokens {s.completion_tokens}")
    print(f"replay saved to {sim.run_file}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticks", type=int, default=12)
    ap.add_argument("--at", type=int, default=2, help="tick at which to apply the command")
    ap.add_argument("--command", default="Three big MNCs open in Whitefield, but the government adds a heavy tax on them.")
    ap.add_argument("--show", type=int, default=4, help="thoughts to print per tick")
    asyncio.run(main(ap.parse_args()))
