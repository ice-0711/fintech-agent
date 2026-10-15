import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents.store import JobStore  # noqa: E402


class FakeClock:
    def __init__(self, start: float = 1_790_000_000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "jobs.sqlite3"


@pytest.fixture
def store(db_path, clock):
    s = JobStore(db_path, clock=clock)
    yield s
    s.close()


def job_request(**overrides):
    req = {
        "ticker": "2330",
        "mode": "dual",
        "cutoff_at": "2026-09-30T13:30:00+08:00",
        "source_snapshot_id": "snap-fixture-001",
        "idempotency_key": "idem-001",
    }
    req.update(overrides)
    return req


@pytest.fixture(autouse=True)
def isolated_tool_registry():
    """Each test starts with no registered tool bodies (other suites, e.g. evaluation/,
    import agents.register_tools which registers B's implementations globally)."""
    from agents.tools import _REGISTRY

    saved = dict(_REGISTRY)
    _REGISTRY.clear()
    yield
    _REGISTRY.clear()
    _REGISTRY.update(saved)
