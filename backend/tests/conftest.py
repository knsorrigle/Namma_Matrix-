import pytest

from namma.config import Settings


@pytest.fixture
def settings(tmp_path):
    s = Settings()
    s.llm_provider = "mock"
    s.runs_dir = tmp_path / "runs"
    s.tick_interval_s = 0.01
    return s
