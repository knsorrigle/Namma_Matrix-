from fastapi.testclient import TestClient

from namma.server import create_app


def test_api_flow(settings):
    with TestClient(create_app(settings)) as client:
        state = client.get("/api/state").json()
        assert len(state["wards"]) == 5 and len(state["citizens"]) == 25

        parsed = client.post("/api/godmode/parse", json={"text": "Metro fare hike of 20%"}).json()
        assert parsed["changes"][0]["metric"] == "metro_fare"

        with client.websocket_connect("/ws") as ws:
            assert ws.receive_json()["type"] == "hello"
            applied = client.post("/api/godmode/apply", json=parsed)
            assert applied.status_code == 200
            assert ws.receive_json()["type"] == "godmode"
            client.post("/api/control", json={"action": "step"})
            tick = ws.receive_json()
            assert tick["type"] == "tick" and tick["tick"] == 1 and tick["city"]["metro_fare"] == 48

        cid = state["citizens"][0]["id"]
        view = client.get(f"/api/citizens/{cid}").json()
        assert view["persona"]["id"] == cid
        assert client.get("/api/citizens/nope").status_code == 404


def test_apply_rejects_unknown_ward(settings):
    with TestClient(create_app(settings)) as client:
        bad = {"text": "x", "headline": "x", "changes": [{"target": "mysore", "metric": "rent", "op": "mul", "value": 1.1}]}
        assert client.post("/api/godmode/apply", json=bad).status_code == 422
