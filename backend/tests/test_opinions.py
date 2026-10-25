import asyncio
import json

from namma.agents.citizen import CitizenMind
from namma.agents.llm import _mock_reaction
from namma.agents.opinions import apply_shift, seed_opinions, social_pull
from namma.config import Settings
from namma.contracts import OPINION_TOPICS, GodModeApply, Opinion, Persona
from namma.sim import Simulation

DATA = Settings().data_dir
PERSONAS = [Persona(**p) for p in json.loads((DATA / "citizens.sample.json").read_text())["citizens"]]


def _persona(**over):
    base = dict(id="t1", name="Test T.", age=30, gender="F", ward_id="whitefield", job="nurse", sector="services",
                income_band="middle", language="Kannada", family="lives alone", values=["community"], traits=["quiet"])
    return Persona(**{**base, **over})


def _avg(xs):
    xs = list(xs)
    return sum(xs) / len(xs)


def test_starting_opinions_come_from_the_persona():
    seeded = {p.id: seed_opinions(p) for p in PERSONAS}
    for ops in seeded.values():
        assert set(ops) == set(OPINION_TOPICS)
        assert all(-1 <= o.stance <= 1 and o.why for o in ops.values())
    it = _avg(seeded[p.id]["big_companies"].stance for p in PERSONAS if p.sector == "it")
    low = _avg(seeded[p.id]["big_companies"].stance for p in PERSONAS if p.sector != "it" and p.income_band == "low")
    assert it > low + 0.3
    metro = _avg(seeded[p.id]["metro"].stance for p in PERSONAS if p.commutes_by_metro)
    no_metro = _avg(seeded[p.id]["metro"].stance for p in PERSONAS if not p.commutes_by_metro)
    assert metro > no_metro
    assert seed_opinions(PERSONAS[0]) == seed_opinions(PERSONAS[0])  # same person, same start


def test_stubborn_people_resist_contrary_evidence():
    stubborn, open_minded = _persona(traits=["stubborn"]), _persona(traits=["curious", "sociable"])
    a = Opinion(stance=0.6, confidence=0.8, why="old reason")
    b = Opinion(stance=0.6, confidence=0.4, why="old reason")
    moved_a = apply_shift(a, -0.3, "new reason", stubborn)
    moved_b = apply_shift(b, -0.3, "new reason", open_minded)
    assert -0.05 < moved_a < 0 and moved_b < -0.2
    assert a.why == "old reason" and b.why == "new reason"
    # Evidence that agrees with what they think makes them surer, with diminishing returns near the extremes.
    c = Opinion(stance=0.6, confidence=0.8)
    assert apply_shift(c, 0.1, "more of the same", stubborn) == 0.02 and c.confidence > 0.8
    d = Opinion(stance=0.95, confidence=0.9)
    for _ in range(20):
        apply_shift(d, 0.3, "again", open_minded)
    assert d.stance < 1


def test_friends_only_sway_people_who_are_not_too_far_apart():
    p = _persona()
    near = Opinion(stance=0.2, confidence=0.3)
    far = Opinion(stance=-0.8, confidence=0.3)
    assert social_pull(near, 0.6, p) > 0 and near.stance > 0.2
    assert social_pull(far, 0.6, p) == 0 and far.stance == -0.8


def test_model_output_is_sanitised():
    mind = CitizenMind(_persona())
    mind.seed_opinions(1.0, 42)
    before = {k: o.stance for k, o in mind.state.opinions.items()}
    shifts = mind.apply_opinions([
        {"topic": "astrology", "shift": 0.3, "why": "not a topic"},
        {"topic": "metro", "shift": "a lot", "why": "not a number"},
        {"topic": "government", "shift": -5, "why": "they did nothing about the floods"},
        {"topic": "government", "shift": 0.3, "why": "a second answer for the same topic is ignored"},
    ], tick=1)
    assert set(shifts) == {"government"} and -0.3 <= shifts["government"] < 0
    assert mind.state.opinions["metro"].stance == before["metro"]
    assert mind.apply_opinions({"my_area": 0.2}, tick=2)  # {"topic": shift} also works
    assert mind.apply_opinions("nonsense", tick=3) == {}


def test_mock_protests_when_outspoken_and_angry():
    card = {"id": "t1", "name": "Test T.", "income_band": "low", "sector": "services", "ward": "koramangala",
            "mood": -0.5, "traits": ["outspoken"], "values": [], "observations": ["Nothing new today. An ordinary day."],
            "opinions": {"government": "strongly disagree (-0.7): the same roads flood every year"}}
    assert _mock_reaction(card)["action"] == "protest"
    assert _mock_reaction({**card, "traits": ["quiet"]})["action"] != "protest"


def test_same_news_moves_different_people_differently(settings):
    async def run():
        sim = Simulation(settings)
        start = {cid: {k: o.stance for k, o in m.state.opinions.items()} for cid, m in sim.minds.items()}
        parsed = await sim.godmode.parse("Three big MNCs open in Whitefield", list(sim.world.wards.values()))
        await sim.apply_godmode(GodModeApply(text=parsed.text, headline=parsed.headline, changes=parsed.changes))
        ticks = [await sim.tick() for _ in range(8)]
        return sim, start, ticks

    sim, start, ticks = asyncio.run(run())
    last = ticks[-1]
    assert set(last.opinions) == set(OPINION_TOPICS) and set(last.ward_opinions) == set(sim.world.wards)
    assert any(u.opinion_shifts for t in ticks for u in t.citizens)
    techies = [cid for cid, m in sim.minds.items() if m.persona.sector == "it" and m.persona.ward_id == "whitefield"]
    gain = _avg(sim.minds[c].state.opinions["big_companies"].stance - start[c]["big_companies"] for c in techies)
    assert gain > 0
    assert any(x.kind == "opinion" for m in sim.minds.values() for x in m.memory.recent(50))
