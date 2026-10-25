"""Settings, read from environment variables (or backend/.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    env_file = BACKEND_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()


def _env(name: str, default: str) -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    # "mock" runs with no model at all; "openai" talks to any OpenAI-compatible
    # server: Ollama (default URL), Groq, or similar.
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "mock"))
    llm_base_url: str = field(default_factory=lambda: _env("LLM_BASE_URL", "http://localhost:11434/v1"))
    llm_api_key: str = field(default_factory=lambda: _env("LLM_API_KEY", "ollama"))
    llm_model: str = field(default_factory=lambda: _env("LLM_MODEL", "llama3.1:8b"))
    # God Mode makes few calls and accuracy matters, so it may use a stronger model.
    godmode_model: str = field(default_factory=lambda: _env("GODMODE_MODEL", _env("LLM_MODEL", "llama3.1:8b")))
    llm_concurrency: int = field(default_factory=lambda: int(_env("LLM_CONCURRENCY", "1")))

    data_dir: Path = field(default_factory=lambda: Path(_env("DATA_DIR", str(BACKEND_DIR / "data"))))
    runs_dir: Path = field(default_factory=lambda: Path(_env("RUNS_DIR", str(BACKEND_DIR / "runs"))))

    # Cost controls: at most this many citizens call the LLM per tick, in
    # batches of this size. Idle thinkers keep the calm city alive.
    max_thinkers_per_tick: int = field(default_factory=lambda: int(_env("MAX_THINKERS", "10")))
    batch_size: int = field(default_factory=lambda: int(_env("BATCH_SIZE", "5")))
    idle_thinkers_per_tick: int = field(default_factory=lambda: int(_env("IDLE_THINKERS", "2")))
    tick_interval_s: float = field(default_factory=lambda: float(_env("TICK_INTERVAL", "3")))
    seed: int = field(default_factory=lambda: int(_env("SEED", "42")))
    # Chance per tick that a citizen talks a topic over with a friend (no LLM call).
    chat_rate: float = field(default_factory=lambda: float(_env("CHAT_RATE", "0.15")))
