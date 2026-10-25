import asyncio

from namma.contracts import GodModeApply
from namma.sim import Simulation


def test_godmode_ripple_reaches_citizens(settings):
    async def run():
        sim = Simulation(settings)
        calm = await sim.tick()
        assert calm.thinking == settings.idle_thinkers_per_tick  # calm city: only idle thinkers
        parsed = await sim.godmode.parse("Five MNCs open in Whitefield", list(sim.world.wards.values()))
        assert parsed.parser == "rules" and parsed.changes
        await sim.apply_godmode(GodModeApply(text=parsed.text, headline=parsed.headline, changes=parsed.changes))
        ticks = [await sim.tick() for _ in range(8)]
        return sim, calm, ticks

    sim, calm, ticks = asyncio.run(run())
    first = ticks[0]
    assert first.events and first.events[0].kind == "godmode"
    whitefield_minds = {m.persona.id for m in sim.minds.values() if m.persona.ward_id == "whitefield"}
    assert whitefield_minds & {u.id for u in first.citizens}
    assert sim.world.wards["whitefield"].rent > calm.wards[0].rent
    assert all(t.thinking <= settings.max_thinkers_per_tick for t in ticks)
    assert sim.run_file.exists() and len(sim.run_file.read_text().splitlines()) == 9
    view = sim.citizen_view(next(iter(whitefield_minds)))
    assert any("News:" in m.text for m in view.memories)
