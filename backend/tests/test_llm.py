"""The real-model path, tested against a fake OpenAI-compatible server."""

import asyncio
import json

import httpx
import pytest

from namma.agents.llm import OpenAICompatLLM
from namma.config import Settings
from namma.contracts import GodModeApply
from namma.godmode import GodMode
from namma.sim import Simulation
from namma.world import WorldEngine


def completion(content, prompt_tokens=100, completion_tokens=20):
    return {
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
    }


def fake_server(reply):
    """reply(request_body) -> (status, json) for each POST /chat/completions."""
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        seen.append(body)
        status, payload = reply(body, len(seen))
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler), seen


def llm_with(reply, **overrides):
    s = Settings()
    s.llm_provider = "openai"
    for k, v in overrides.items():
        setattr(s, k, v)
    transport, seen = fake_server(reply)
    return OpenAICompatLLM(s, transport=transport), seen, s


def test_request_shape_and_usage():
    llm, seen, _ = llm_with(lambda body, n: (200, completion('{"ok": true}')))
    out = asyncio.run(llm.complete_json("react", "sys", "user", {}))
    assert out == {"ok": True}
    assert seen[0]["response_format"] == {"type": "json_object"}
    assert seen[0]["model"] == "llama3.1:8b"
    assert [m["role"] for m in seen[0]["messages"]] == ["system", "user"]
    assert llm.stats.calls == 1 and llm.stats.prompt_tokens == 100 and llm.stats.completion_tokens == 20


def test_extracts_json_from_chatty_or_fenced_output():
    llm, _, _ = llm_with(lambda body, n: (200, completion('Sure! Here it is:\n```json\n{"a": 1}\n```\nHope that helps.')))
    assert asyncio.run(llm.complete_json("react", "s", "u", {})) == {"a": 1}


def test_retries_once_then_succeeds():
    llm, seen, _ = llm_with(lambda body, n: (500, {"error": "busy"}) if n == 1 else (200, completion('{"a": 2}')))
    assert asyncio.run(llm.complete_json("react", "s", "u", {})) == {"a": 2}
    assert len(seen) == 2


def test_gives_up_after_two_bad_answers():
    llm, _, _ = llm_with(lambda body, n: (200, completion("I cannot do that.")))
    with pytest.raises(RuntimeError):
        asyncio.run(llm.complete_json("react", "s", "u", {}))
    assert llm.stats.failures == 1


def test_godmode_llm_validates_and_falls_back():
    wards = list(WorldEngine.from_file(Settings().data_dir / "wards.sample.json").wards.values())
    good = {"headline": "MNCs arrive", "changes": [
        {"target": "whitefield", "metric": "jobs.it", "op": "mul", "value": 1.2},
        {"target": "city", "metric": "rent", "op": "mul", "value": 1.1},        # rent is not a city metric
        {"target": "mysuru", "metric": "rent", "op": "mul", "value": 1.1},      # unknown ward
    ]}
    llm, seen, s = llm_with(lambda body, n: (200, completion(json.dumps(good))), godmode_model="qwen2.5:7b")
    parsed = asyncio.run(GodMode(llm, s.godmode_model).parse("MNCs arrive in Whitefield", wards))
    assert parsed.parser == "llm" and len(parsed.changes) == 1 and len(parsed.warnings) == 2
    assert seen[0]["model"] == "qwen2.5:7b" and seen[0]["temperature"] == 0.2

    empty, _, _ = llm_with(lambda body, n: (200, completion('{"headline": "x", "changes": []}')))
    parsed = asyncio.run(GodMode(empty).parse("Metro fare goes up by 10%", wards))
    assert parsed.parser == "rules" and parsed.changes[0].metric == "metro_fare"
    assert any("keyword rules" in w for w in parsed.warnings)


def test_simulation_survives_messy_model_output(tmp_path):
    def reply(body, n):
        user = body["messages"][1]["content"]
        if "belief" in body["messages"][0]["content"]:
            return 200, completion('{"citizens": []}')
        ids = [json.loads(line)["id"] for line in user.split("\n") if line.startswith("{")]
        rows = [
            {"id": 99, "thought": "Rent is too much!", "mood_change": "-0.9", "action": "move", "move_to": "mysuru", "post": "ugh"},
            {"id": ids[1] if len(ids) > 1 else 0, "thought": 42, "mood_change": None, "action": "dance"},
        ]
        return 200, completion(json.dumps({"citizens": rows}))

    llm, _, s = llm_with(reply)
    s.runs_dir = tmp_path

    async def run():
        sim = Simulation(s, llm=llm)
        parsed = await sim.godmode.parse("Five MNCs open in Whitefield", list(sim.world.wards.values()))
        await sim.apply_godmode(GodModeApply(text=parsed.text, headline=parsed.headline, changes=parsed.changes))
        return sim, [await sim.tick() for _ in range(3)]

    sim, ticks = asyncio.run(run())
    for t in ticks:
        for u in t.citizens:
            assert -1 <= u.mood <= 1
            assert u.action in ("stay", "consider_moving", "move", "look_for_job", "protest", "post")
            assert u.ward_id in sim.world.wards
