import sqlite3
from pathlib import Path
import pytest


SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


@pytest.fixture
def conn():
    """In-memory SQLite connection with schema applied."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield c
    c.close()


from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI TestClient bound to an isolated DB + uploads dir."""
    db_path = tmp_path / "test.db"
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("UPLOADS_DIR", str(uploads_dir))

    from web import app as web_app
    # Force re-evaluation of env-derived module constants
    import importlib
    importlib.reload(web_app)
    web_app.init_database()
    return TestClient(web_app.app)


class _FakeLLM:
    """Replacement for LLMClient used in E2E tests."""

    def __init__(self):
        self.text_responses: list[str] = []
        self.vision_responses: list[str] = []
        self.text_calls: list[tuple[str, str]] = []
        self.vision_calls: list[tuple[str, list]] = []

    def queue_text(self, response: str) -> None:
        self.text_responses.append(response)

    def queue_vision(self, response: str) -> None:
        self.vision_responses.append(response)

    def complete_text(self, system: str, user: str) -> str:
        self.text_calls.append((system, user))
        if not self.text_responses:
            raise RuntimeError("FakeLLM: no queued text responses")
        return self.text_responses.pop(0)

    def complete_vision(self, system: str, content_blocks: list) -> str:
        self.vision_calls.append((system, content_blocks))
        if not self.vision_responses:
            raise RuntimeError("FakeLLM: no queued vision responses")
        return self.vision_responses.pop(0)


@pytest.fixture
def fake_llm(monkeypatch):
    fake = _FakeLLM()
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_llm_client", lambda: fake)
    return fake


@pytest.fixture
def fake_image_engine(monkeypatch):
    """Patch image_matcher.engine functions used by web routes.
    Tests set .sim_response / .compare_response before triggering the route."""
    class _Engine:
        sim_response: dict = {"criteria": []}
        compare_response: dict = {"rows": [], "summary": {"matched": 0, "mismatched": 0}}
        analyze_calls: list = []
        compare_calls: list = []

        @classmethod
        def reset(cls):
            cls.analyze_calls = []
            cls.compare_calls = []

    _Engine.reset()

    def fake_analyze_sim(sim_path, model="claude-sonnet-4-6"):
        _Engine.analyze_calls.append(str(sim_path))
        return _Engine.sim_response

    def fake_compare_real(sim_report, real_path, model="claude-sonnet-4-6", max_tokens=8192):
        _Engine.compare_calls.append((sim_report, str(real_path)))
        return _Engine.compare_response

    from web import app as web_app
    monkeypatch.setattr(web_app, "analyze_sim", fake_analyze_sim)
    monkeypatch.setattr(web_app, "compare_real", fake_compare_real)

    return _Engine
