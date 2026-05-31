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
