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
    assert situation_for(["News: Heavy rain floods Koramangala underpasses"]) == "flood"
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
    lines = {line for a in pack["archetypes"] for line in a["examples"]["cost_up"]}
    assert any(u.thought in lines for u in tick.citizens)


def _write_csv(path, rows):
    import csv

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def test_build_voice_from_form_and_notes(tmp_path):
    import shutil

    from namma.agents.voice_build import run

    shutil.copytree(DATA / "voice", tmp_path / "voice")
    shutil.copytree(DATA / "pulse", tmp_path / "pulse")
    q = {
        "consent": "I'm 18 or older and okay with my answers being used as described above",
        "age": "Your age group",
        "work": "What do you do?",
        "money": "How tight is money for you each month?",
        "rent_up": "Your landlord says rent goes up by Rs 3,000 from next month.",
        "phrases": "Words or phrases you and your friends use all the time (separate with commas)",
        "choice": "If your rent went up 20%, what would you actually do?",
    }
    techie = {q["consent"]: "Yes", q["age"]: "23-27", q["work"]: "IT or tech job", q["money"]: "Manageable",
              q["rent_up"]: "bro 3k hike?? call me on 98450 12345, PG it is", q["phrases"]: "scene, en guru, ok",
              q["choice"]: "Move to a PG or share a flat"}
    driver = {q["consent"]: "Yes", q["age"]: "36-54", q["work"]: "Auto, cab or delivery driver", q["money"]: "Tight",
              q["rent_up"]: "Saar 3000 jaasti, meter rate same only", q["phrases"]: "saar", q["choice"]: "Stay and adjust"}
    no_consent = {**techie, q["consent"]: "", q["rent_up"]: "should never appear anywhere"}
    _write_csv(tmp_path / "survey" / "responses.csv", [techie, driver, no_consent])
    _write_csv(tmp_path / "survey" / "field_notes.csv", [
        {"date": "2026-10-28", "source": "reddit", "topic": "rent", "resident_type": "Gen Z techie",
         "take": "Brokers ask two months rent as fee, u/someone says people just pay it", "phrases": "broker scene",
         "reaction": "piled on"},
        {"date": "2026-10-28", "source": "reddit", "topic": "weather", "resident_type": "Not sure",
         "take": "Off-topic note", "phrases": "", "reaction": "joked"},
    ])

    summary = run(tmp_path)
    assert summary["voice"]["kept"] == 2
    assert summary["voice"]["rent_choice"] == {"Move to a PG or share a flat": 1, "Stay and adjust": 1}
    assert summary["pulse"]["skipped"] == 1

    collected = json.loads((tmp_path / "voice" / "collected.json").read_text())
    techie_line = collected["archetypes"]["genz_techie"]["examples"]["rent_up"][0]
    assert "98450" not in techie_line and "PG it is" in techie_line
    assert collected["archetypes"]["gig_driver"]["examples"]["rent_up"] == ["Saar 3000 jaasti, meter rate same only"]
    assert "broker scene" in collected["archetypes"]["genz_techie"]["phrases"]
    assert "should never appear" not in json.dumps(collected)

    pulse = json.loads((tmp_path / "pulse" / "pulse.json").read_text())
    assert pulse["topics"]["rent"] == ["Brokers ask two months rent as fee, says people just pay it"]
    assert pulse["topics"]["flood"]  # topics without notes keep the sample takes

    pack = load_pack(tmp_path)  # the voice pack now carries the real lines too
    genz = next(a for a in pack["archetypes"] if a["id"] == "genz_techie")
    assert techie_line in genz["examples"]["rent_up"] and len(genz["examples"]["rent_up"]) == 2
