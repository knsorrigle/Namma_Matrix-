"""FastAPI app: REST for control and God Mode, a WebSocket for the live tick stream.

Run with:  uvicorn namma.server:app --reload
"""

from __future__ import annotations

import asyncio
import contextlib
import json
from typing import Literal

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import Settings
from .contracts import CitizenView, GodModeApply, GodModeParse, GodModeRequest, TickEvent, WorldEvent
from .sim import Simulation


class Control(BaseModel):
    action: Literal["play", "pause", "step"]
    speed: float = Field(1.0, gt=0, le=20)


class Runner:
    """Owns the simulation and the clients watching it."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.sim = Simulation(settings)
        self.clients: set[WebSocket] = set()
        self.playing = False
        self.speed = 1.0
        self._task: asyncio.Task | None = None

    async def broadcast(self, message: dict) -> None:
        dead = []
        for ws in self.clients:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    async def step(self) -> TickEvent:
        event = await self.sim.tick()
        await self.broadcast(json.loads(event.model_dump_json()))
        return event

    async def _loop(self) -> None:
        while self.playing:
            await self.step()
            await asyncio.sleep(self.settings.tick_interval_s / self.speed)

    def play(self) -> None:
        self.playing = True
        if not self._task or self._task.done():
            self._task = asyncio.create_task(self._loop())

    async def pause(self) -> None:
        self.playing = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task

    def snapshot(self) -> dict:
        sim = self.sim
        return {
            "type": "hello",
            "tick": sim.world.tick,
            "sim_date": sim.world.sim_date,
            "playing": self.playing,
            "llm_provider": self.settings.llm_provider,
            "wards": [w.model_dump() for w in sim.world.wards.values()],
            "city": sim.world.city.model_dump(),
            "citizens": [
                {**m.persona.model_dump(), "state": m.state.model_dump()} for m in sim.minds.values()
            ],
            "events": [e.model_dump() for e in sim.world.events[-20:]],
            "opinions": {k: v.model_dump() for k, v in sim.opinion_summary()[0].items()},
        }


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    runner = Runner(settings)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        await runner.pause()

    app = FastAPI(title="Namma Matrix", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.runner = runner

    @app.get("/api/state")
    async def state() -> dict:
        return runner.snapshot()

    @app.post("/api/control")
    async def control(body: Control) -> dict:
        runner.speed = body.speed
        if body.action == "play":
            runner.play()
        elif body.action == "pause":
            await runner.pause()
        else:
            await runner.step()
        return {"playing": runner.playing, "speed": runner.speed, "tick": runner.sim.world.tick}

    @app.post("/api/godmode/parse", response_model=GodModeParse)
    async def godmode_parse(body: GodModeRequest) -> GodModeParse:
        return await runner.sim.godmode.parse(body.text, list(runner.sim.world.wards.values()))

    @app.post("/api/godmode/apply", response_model=WorldEvent)
    async def godmode_apply(body: GodModeApply) -> WorldEvent:
        for c in body.changes:
            if c.target != "city" and c.target not in runner.sim.world.wards:
                raise HTTPException(422, f"unknown ward {c.target!r}")
        event = await runner.sim.apply_godmode(body)
        await runner.broadcast({"type": "godmode", "event": event.model_dump()})
        return event

    @app.get("/api/citizens/{cid}", response_model=CitizenView)
    async def citizen(cid: str) -> CitizenView:
        if cid not in runner.sim.minds:
            raise HTTPException(404, "no such citizen")
        return runner.sim.citizen_view(cid)

    @app.get("/api/stats")
    async def stats() -> dict:
        s = runner.sim.llm.stats
        return {"provider": settings.llm_provider, "model": settings.llm_model, **s.__dict__,
                "run_file": str(runner.sim.run_file)}

    @app.websocket("/ws")
    async def ws(socket: WebSocket) -> None:
        await socket.accept()
        runner.clients.add(socket)
        await socket.send_json(runner.snapshot())
        try:
            while True:
                await socket.receive_text()  # clients only listen; keep the socket open
        except WebSocketDisconnect:
            runner.clients.discard(socket)

    return app


app = create_app()
