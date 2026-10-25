import asyncio
import json

from namma.agents.voice import archetype_for, load_pack, situation_for, voice_card
from namma.config import Settings
from namma.contracts import GodModeApply, Persona
from namma.sim import Simulation

DATA = Settings().data_dir
PERSONAS = [Persona(**p) for p in json.loads((DATA / "citizens.sample.json").read_text())["citizens"]]


def test_every_sample_citizen_gets_a_voice():
    pack = load_pack(DATA)
    kinds = {archetype_for(p, pack)["id"] for p in PERSONAS}
    assert {"genz_techie", "gig_driver", "small_business", "service_worker"} <= kinds


def test_situation_detection():
    assert situation_for(["Rent in Whitefield went up 4% to about Rs 25,000."]) == "rent_up"
    assert situation_for(["There are 5% more it jobs in Whitefield now."]) == "jobs_up"
    assert situation_for(["The government raised the metro fare from 40 to 48."]) == "cost_up"
    assert situation_for(['Your friend Neha E. posted: "rent hike again"']) == "heard"
    assert situation_for([]) == "calm"


def test_voice_card_has_example_and_chatter():
    techie = next(p for p in PERSONAS if p.sector == "it" and p.age <= 30)
    card = voice_card(techie, ["Rent in Whitefield went up 4% to about Rs 25,000."], DATA)
    assert card["voice"]["type"] == "genz_techie"
    assert "landlord" in card["voice"]["example"]
    assert len(card["local_chatter"]) == 2


def test_mock_citizens_speak_in_voice(settings):
    async def run():
        sim = Simulation(settings)
        parsed = await sim.godmode.parse("Metro fare goes up by 25%", list(sim.world.wards.values()))
        await sim.apply_godmode(GodModeApply(text=parsed.text, headline=parsed.headline, changes=parsed.changes))
        return await sim.tick()

    tick = asyncio.run(run())
    pack = load_pack(DATA)
    lines = {a["examples"]["cost_up"] for a in pack["archetypes"]}
    assert any(u.thought in lines for u in tick.citizens)
