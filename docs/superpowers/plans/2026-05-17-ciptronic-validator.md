# Ciptronic Product Validator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the MVP of a two-agent web app (Discovery + Inspector) that converts vague product descriptions into structured JSON and validates finished products against that JSON using vision, with full TDD coverage on pure logic and DB, and HTMX-driven server-rendered UI.

**Architecture:** Layered modules (`agents/`, `prompts/`, `schemas/`, `db/`, `web/`). Pure functions in agents (build/parse), thin LLM client, SQLite repository. FastAPI + HTMX + Jinja for the UI. Stateless LLM calls — every request passes full context. MVP scope: tricou only; schemas are JSON files in `schemas/` so adding product types later requires no code changes.

**Tech Stack:** Python 3.10+, FastAPI, HTMX, Jinja2, SQLite, anthropic SDK (Claude Sonnet 4.6), pytest.

**Spec:** [`docs/superpowers/specs/2026-05-17-ciptronic-validator-design.md`](../specs/2026-05-17-ciptronic-validator-design.md)

**Working directory:** `C:\Users\40747\OneDrive\Documents\Jetson Nano\ciptronic_validator` (treat as project root in all commands).

---

## Task 1: Project scaffolding

Create the folder structure, dependency list, gitignore, env template, README skeleton, .claude permissions, and venv. This task does **not** add any application code — just the skeleton other tasks build into.

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `README.md`
- Create: `.claude/settings.local.json`
- Create: `agents/__init__.py` (empty)
- Create: `db/__init__.py` (empty)
- Create: `schemas/__init__.py` (empty)
- Create: `web/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `tests/unit/__init__.py` (empty)
- Create: `tests/integration/__init__.py` (empty)
- Create: `tests/e2e/__init__.py` (empty)
- Create: `prompts/.gitkeep` (placeholder so folder commits)
- Create: `tests/fixtures/.gitkeep`
- Create: `main.py` (empty)

- [ ] **Step 1: Create `requirements.txt`**

```
fastapi>=0.110
uvicorn[standard]>=0.27
jinja2>=3.1
python-multipart>=0.0.9
anthropic>=0.34
python-dotenv>=1.0
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27
```

`httpx` is needed by FastAPI's TestClient. `python-multipart` for file uploads. `python-dotenv` to read `.env` locally.

- [ ] **Step 2: Create `.gitignore`**

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.coverage

# venv
.venv/

# Environment
.env

# Runtime
uploads/
*.db
*.sqlite
*.sqlite3

# Test fixtures (images come from user; instructions are in fixtures/images/README.md)
tests/fixtures/images/*.jpg
tests/fixtures/images/*.jpeg
tests/fixtures/images/*.png
!tests/fixtures/images/README.md

# IDE
.vscode/
.idea/

# OS
Thumbs.db
.DS_Store
```

- [ ] **Step 3: Create `.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-api-...
ANTHROPIC_MODEL=claude-sonnet-4-6
DATABASE_PATH=./ciptronic.db
```

- [ ] **Step 4: Create `README.md` skeleton**

```markdown
# Ciptronic Product Validator

Aplicație web locală pentru specificarea și validarea vizuală a produselor personalizate.
Două fluxuri:
1. **Discovery** — descriere vagă → JSON structurat, prin întrebări țintite.
2. **Inspector** — JSON + poze → raport conform / neconform / nevizibil.

## Setup

Cerințe: Python 3.10+.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell sau cmd
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env            # editează .env cu cheia ta Anthropic
```

## Run

```bash
uvicorn main:app --reload
```

Apoi deschizi http://localhost:8000.

## Test

```bash
pytest
```

## Spec & plan

- [Design spec](docs/superpowers/specs/2026-05-17-ciptronic-validator-design.md)
- [Implementation plan](docs/superpowers/plans/2026-05-17-ciptronic-validator.md)
```

Checklist-ul manual și nota despre fixtures vor fi adăugate în Task 10.

- [ ] **Step 5: Create `.claude/settings.local.json`**

```json
{
  "permissions": {
    "allow": [
      "Bash(git init *)",
      "Bash(git add *)",
      "Bash(git commit -m ' *)",
      "Bash(git check-ignore *)",
      "Bash(python -m venv .venv)",
      "Bash(.venv/Scripts/pip.exe install *)",
      "Bash(.venv/Scripts/python.exe *)",
      "Bash(.venv/Scripts/pytest.exe *)",
      "Bash(.venv/Scripts/uvicorn.exe *)",
      "Bash(python *)",
      "Bash(pytest *)",
      "Bash(git *)"
    ]
  }
}
```

- [ ] **Step 6: Create empty package init files and placeholders**

Create these as empty files:
- `agents/__init__.py`
- `db/__init__.py`
- `schemas/__init__.py`
- `web/__init__.py`
- `tests/__init__.py`
- `tests/unit/__init__.py`
- `tests/integration/__init__.py`
- `tests/e2e/__init__.py`
- `main.py`

Create `prompts/.gitkeep` and `tests/fixtures/.gitkeep` (so the folders are tracked even though empty).

- [ ] **Step 7: Create the venv and install dependencies**

Run:
```bash
python -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
```

Expected: pip downloads and installs all packages, no errors.

- [ ] **Step 8: Sanity-check pytest works**

Run:
```bash
.venv\Scripts\pytest.exe --collect-only
```

Expected: pytest discovers 0 tests (no test files yet), exit code 0 with message `no tests ran`.

- [ ] **Step 9: Commit**

```bash
git add requirements.txt .gitignore .env.example README.md .claude/settings.local.json agents/__init__.py db/__init__.py schemas/__init__.py web/__init__.py tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py tests/e2e/__init__.py prompts/.gitkeep tests/fixtures/.gitkeep main.py
git commit -m "feat: project scaffolding (deps, gitignore, package skeleton)"
```

---

## Task 2: SQLite schema + repository

Build the data layer first. All CRUD goes through `db/repository.py` — pure functions that take an open connection. We test against an in-memory SQLite so tests are fast and isolated.

**Files:**
- Create: `db/schema.sql`
- Create: `db/repository.py`
- Create: `tests/unit/test_repository.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `db/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS discovery_sessions (
    id              TEXT PRIMARY KEY,
    product_type    TEXT NOT NULL,
    initial_description TEXT NOT NULL,
    state_json      TEXT NOT NULL,
    history_json    TEXT NOT NULL,
    status          TEXT NOT NULL
                    CHECK (status IN ('in_progress', 'complete', 'abandoned')),
    rounds_used     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_status
    ON discovery_sessions(status);

CREATE TABLE IF NOT EXISTS validation_reports (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES discovery_sessions(id),
    spec_json       TEXT NOT NULL,
    image_paths_json TEXT NOT NULL,
    conform_json     TEXT NOT NULL,
    neconform_json   TEXT NOT NULL,
    nevizibil_json   TEXT NOT NULL,
    raw_llm_response TEXT NOT NULL,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

- [ ] **Step 2: Create `tests/conftest.py` with shared fixtures**

```python
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
```

- [ ] **Step 3: Write failing tests for `create_session` and `get_session`**

Create `tests/unit/test_repository.py`:

```python
import json

from db import repository


def test_create_session_returns_uuid_and_persists(conn):
    sid = repository.create_session(
        conn,
        product_type="tricou",
        description="tricou navy cu logo",
    )
    assert isinstance(sid, str)
    assert len(sid) == 36  # uuid4 string length

    row = repository.get_session(conn, sid)
    assert row["product_type"] == "tricou"
    assert row["initial_description"] == "tricou navy cu logo"
    assert row["status"] == "in_progress"
    assert row["rounds_used"] == 0
    assert json.loads(row["state_json"]) == {}
    assert json.loads(row["history_json"]) == []


def test_get_session_returns_none_when_missing(conn):
    assert repository.get_session(conn, "no-such-id") is None
```

- [ ] **Step 4: Run test to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/unit/test_repository.py -v`
Expected: FAIL — ImportError or AttributeError, because `db/repository.py` is empty.

- [ ] **Step 5: Implement `create_session` and `get_session` in `db/repository.py`**

```python
import json
import sqlite3
import uuid


def create_session(conn: sqlite3.Connection,
                   product_type: str,
                   description: str) -> str:
    """Create a new discovery session with empty state and history.
    Returns the new session id (uuid4 string)."""
    sid = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO discovery_sessions
            (id, product_type, initial_description, state_json, history_json, status)
        VALUES (?, ?, ?, ?, ?, 'in_progress')
        """,
        (sid, product_type, description, "{}", "[]"),
    )
    conn.commit()
    return sid


def get_session(conn: sqlite3.Connection, session_id: str) -> sqlite3.Row | None:
    """Return the session row or None if not found."""
    cur = conn.execute(
        "SELECT * FROM discovery_sessions WHERE id = ?", (session_id,)
    )
    return cur.fetchone()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/unit/test_repository.py -v`
Expected: PASS — both tests green.

- [ ] **Step 7: Write failing test for `update_session_state` and `finalize_session`**

Append to `tests/unit/test_repository.py`:

```python
def test_update_session_state_persists_state_history_and_rounds(conn):
    sid = repository.create_session(conn, "tricou", "tricou navy")
    new_state = {"culoare_principala": "albastru navy"}
    new_history = [{"round": 1, "questions": [], "answers": {}}]

    repository.update_session_state(conn, sid, new_state, new_history, rounds=1)

    row = repository.get_session(conn, sid)
    assert json.loads(row["state_json"]) == new_state
    assert json.loads(row["history_json"]) == new_history
    assert row["rounds_used"] == 1
    assert row["status"] == "in_progress"


def test_finalize_session_sets_status_and_completed_at(conn):
    sid = repository.create_session(conn, "tricou", "tricou navy")

    repository.finalize_session(conn, sid)

    row = repository.get_session(conn, sid)
    assert row["status"] == "complete"
    assert row["completed_at"] is not None
```

- [ ] **Step 8: Run tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/unit/test_repository.py -v`
Expected: 2 tests fail with AttributeError on `update_session_state` and `finalize_session`.

- [ ] **Step 9: Implement `update_session_state` and `finalize_session`**

Append to `db/repository.py`:

```python
def update_session_state(conn: sqlite3.Connection,
                        session_id: str,
                        state: dict,
                        history: list,
                        rounds: int) -> None:
    """Update the session's partial state, conversation history, and round count."""
    conn.execute(
        """
        UPDATE discovery_sessions
        SET state_json = ?, history_json = ?, rounds_used = ?
        WHERE id = ?
        """,
        (json.dumps(state, ensure_ascii=False),
         json.dumps(history, ensure_ascii=False),
         rounds,
         session_id),
    )
    conn.commit()


def finalize_session(conn: sqlite3.Connection, session_id: str) -> None:
    """Mark the session as complete with the current timestamp."""
    conn.execute(
        """
        UPDATE discovery_sessions
        SET status = 'complete', completed_at = datetime('now')
        WHERE id = ?
        """,
        (session_id,),
    )
    conn.commit()
```

- [ ] **Step 10: Run tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/unit/test_repository.py -v`
Expected: PASS — all 4 tests green.

- [ ] **Step 11: Write failing tests for `save_report` and `get_report`**

Append to `tests/unit/test_repository.py`:

```python
def test_save_report_returns_uuid_and_persists_all_fields(conn):
    sid = repository.create_session(conn, "tricou", "tricou navy")
    spec = {"culoare_principala": "navy"}
    image_paths = ["uploads/abc/img1.jpg"]
    conform = [{"camp": "culoare_principala", "valoare_asteptata": "navy",
                "valoare_observata": "navy", "incredere": "ridicat", "motiv": "vizibil"}]
    neconform = []
    nevizibil = []
    raw = '{"conform":[...],"neconform":[],"nevizibil":[]}'

    rid = repository.save_report(conn, sid, spec, image_paths,
                                  conform, neconform, nevizibil, raw)
    assert len(rid) == 36

    row = repository.get_report(conn, rid)
    assert row["session_id"] == sid
    assert json.loads(row["spec_json"]) == spec
    assert json.loads(row["image_paths_json"]) == image_paths
    assert json.loads(row["conform_json"]) == conform
    assert json.loads(row["neconform_json"]) == neconform
    assert json.loads(row["nevizibil_json"]) == nevizibil
    assert row["raw_llm_response"] == raw


def test_get_report_returns_none_when_missing(conn):
    assert repository.get_report(conn, "no-such-id") is None
```

- [ ] **Step 12: Run tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/unit/test_repository.py -v`
Expected: 2 new tests fail with AttributeError on `save_report` / `get_report`.

- [ ] **Step 13: Implement `save_report` and `get_report`**

Append to `db/repository.py`:

```python
def save_report(conn: sqlite3.Connection,
                session_id: str,
                spec: dict,
                image_paths: list,
                conform: list,
                neconform: list,
                nevizibil: list,
                raw: str) -> str:
    """Persist a validation report. Returns the new report id (uuid4 string)."""
    rid = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO validation_reports
            (id, session_id, spec_json, image_paths_json,
             conform_json, neconform_json, nevizibil_json, raw_llm_response)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (rid, session_id,
         json.dumps(spec, ensure_ascii=False),
         json.dumps(image_paths, ensure_ascii=False),
         json.dumps(conform, ensure_ascii=False),
         json.dumps(neconform, ensure_ascii=False),
         json.dumps(nevizibil, ensure_ascii=False),
         raw),
    )
    conn.commit()
    return rid


def get_report(conn: sqlite3.Connection, report_id: str) -> sqlite3.Row | None:
    """Return the report row or None if not found."""
    cur = conn.execute(
        "SELECT * FROM validation_reports WHERE id = ?", (report_id,)
    )
    return cur.fetchone()
```

- [ ] **Step 14: Run all repository tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/unit/test_repository.py -v`
Expected: PASS — 6 tests green.

- [ ] **Step 15: Commit**

```bash
git add db/schema.sql db/repository.py tests/conftest.py tests/unit/test_repository.py
git commit -m "feat: SQLite schema and pure repository functions (CRUD on sessions and reports)"
```

---

## Task 3: Schema loader + tricou.json

Schemas live as JSON files in `schemas/`. The loader reads them and provides utilities the agents need (list of leaf keys, applicable keys given a state). Adding a new product type later = adding a JSON file, no code change.

**Files:**
- Create: `schemas/tricou.json`
- Create: `schemas/loader.py`
- Create: `tests/unit/test_schema_loader.py`

- [ ] **Step 1: Create `schemas/tricou.json`**

```json
{
  "id": "tricou",
  "name_ro": "Tricou",
  "fields": [
    {
      "key": "culoare_principala",
      "label": "Culoare principală",
      "hint": "ex: roșu, negru, alb melange"
    },
    {
      "key": "material",
      "label": "Material",
      "hint": "ex: bumbac 100%, poliester, mix"
    },
    {
      "key": "croiala",
      "label": "Croială",
      "hint": "regular / slim / oversize"
    },
    {
      "key": "guler",
      "label": "Tip guler",
      "hint": "rotund / V / polo"
    },
    {
      "key": "maneci",
      "label": "Mâneci",
      "hint": "scurte / lungi / 3/4"
    },
    {
      "key": "branding",
      "label": "Branding (logo/print/imprimeu)",
      "type": "object",
      "allow_none_value": "fără branding",
      "subfields": [
        {
          "key": "pozitie",
          "label": "Poziție",
          "hint": "ex: piept stâng, spate centru"
        },
        {
          "key": "tehnica",
          "label": "Tehnică",
          "hint": "serigrafie / broderie / DTF / sublimare"
        },
        {
          "key": "culori",
          "label": "Culori",
          "type": "list"
        },
        {
          "key": "dimensiuni_aproximative",
          "label": "Dimensiuni aproximative",
          "hint": "ex: 10cm x 10cm"
        }
      ]
    }
  ]
}
```

- [ ] **Step 2: Write failing tests for the loader**

Create `tests/unit/test_schema_loader.py`:

```python
import pytest

from schemas import loader


def test_load_schema_returns_dict():
    schema = loader.load_schema("tricou")
    assert schema["id"] == "tricou"
    assert schema["name_ro"] == "Tricou"
    assert isinstance(schema["fields"], list)


def test_load_schema_unknown_raises():
    with pytest.raises(FileNotFoundError):
        loader.load_schema("not-a-product")


def test_available_product_types_lists_tricou():
    types = loader.available_product_types()
    assert "tricou" in types


def test_leaf_keys_tricou_returns_nine_keys():
    schema = loader.load_schema("tricou")
    keys = loader.leaf_keys(schema)
    assert keys == [
        "culoare_principala",
        "material",
        "croiala",
        "guler",
        "maneci",
        "branding.pozitie",
        "branding.tehnica",
        "branding.culori",
        "branding.dimensiuni_aproximative",
    ]


def test_applicable_leaf_keys_with_active_branding():
    schema = loader.load_schema("tricou")
    state = {
        "culoare_principala": "navy", "material": "bumbac", "croiala": "slim",
        "guler": "rotund", "maneci": "scurte",
        "branding": {"pozitie": "piept stâng", "tehnica": "serigrafie",
                     "culori": ["alb"], "dimensiuni_aproximative": "10cm"}
    }
    keys = loader.applicable_leaf_keys(schema, state)
    assert len(keys) == 9


def test_applicable_leaf_keys_with_fara_branding():
    schema = loader.load_schema("tricou")
    state = {
        "culoare_principala": "navy", "material": "bumbac", "croiala": "slim",
        "guler": "rotund", "maneci": "scurte",
        "branding": {"pozitie": "fără branding", "tehnica": None,
                     "culori": [], "dimensiuni_aproximative": None}
    }
    keys = loader.applicable_leaf_keys(schema, state)
    # Pozitie still applies (to verify NO branding present); other 3 do not.
    assert keys == [
        "culoare_principala", "material", "croiala", "guler", "maneci",
        "branding.pozitie",
    ]


def test_empty_state_for_schema_initializes_branding_subobject():
    schema = loader.load_schema("tricou")
    state = loader.empty_state(schema)
    assert state["culoare_principala"] is None
    assert state["branding"]["pozitie"] is None
    assert state["branding"]["culori"] == []  # list default
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/unit/test_schema_loader.py -v`
Expected: FAIL — ImportError because `schemas/loader.py` is empty.

- [ ] **Step 4: Implement `schemas/loader.py`**

```python
import json
from pathlib import Path


SCHEMAS_DIR = Path(__file__).parent


def available_product_types() -> list[str]:
    """List product type ids based on JSON files in schemas/."""
    return sorted(p.stem for p in SCHEMAS_DIR.glob("*.json"))


def load_schema(product_type: str) -> dict:
    """Load and return the JSON schema for the given product type."""
    path = SCHEMAS_DIR / f"{product_type}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def leaf_keys(schema: dict) -> list[str]:
    """Return ALL leaf-field dotted keys for the schema, in declaration order.
    Object-typed fields expand into 'parent.child' keys."""
    out: list[str] = []
    for field in schema["fields"]:
        if field.get("type") == "object":
            for sub in field["subfields"]:
                out.append(f"{field['key']}.{sub['key']}")
        else:
            out.append(field["key"])
    return out


def applicable_leaf_keys(schema: dict, state: dict) -> list[str]:
    """Return the leaf keys that are applicable given the current state.
    For an object field with `allow_none_value`, when its first subfield
    matches that value, only the first subfield is applicable
    (the rest are not — see spec: 'fără branding' case)."""
    out: list[str] = []
    for field in schema["fields"]:
        if field.get("type") == "object":
            parent_state = state.get(field["key"]) or {}
            none_marker = field.get("allow_none_value")
            first_sub_key = field["subfields"][0]["key"]
            first_sub_value = parent_state.get(first_sub_key)
            if none_marker is not None and first_sub_value == none_marker:
                # only the 'marker' subfield is applicable
                out.append(f"{field['key']}.{first_sub_key}")
            else:
                for sub in field["subfields"]:
                    out.append(f"{field['key']}.{sub['key']}")
        else:
            out.append(field["key"])
    return out


def empty_state(schema: dict) -> dict:
    """Build an empty state dict for the schema.
    Scalars start as None, lists start as [], object fields are dicts of subfields."""
    state: dict = {}
    for field in schema["fields"]:
        if field.get("type") == "object":
            state[field["key"]] = {}
            for sub in field["subfields"]:
                state[field["key"]][sub["key"]] = [] if sub.get("type") == "list" else None
        elif field.get("type") == "list":
            state[field["key"]] = []
        else:
            state[field["key"]] = None
    return state
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/unit/test_schema_loader.py -v`
Expected: PASS — 7 tests green.

- [ ] **Step 6: Commit**

```bash
git add schemas/tricou.json schemas/loader.py tests/unit/test_schema_loader.py
git commit -m "feat: tricou schema + loader (leaf keys, applicable keys, empty state)"
```

---

## Task 4: LLM client wrapper

Thin wrapper over the Anthropic SDK. Two methods: `complete_text(system, user)` for Discovery and `complete_vision(system, content_blocks)` for Inspector. Real-API smoke test is skipped without an `ANTHROPIC_API_KEY`.

**Files:**
- Create: `agents/llm_client.py`
- Create: `tests/integration/test_llm_client.py`

- [ ] **Step 1: Implement `agents/llm_client.py`**

```python
import os
from dataclasses import dataclass
from typing import Any

import anthropic


DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
DEFAULT_MAX_TOKENS = 4096


@dataclass
class LLMClient:
    """Thin wrapper around anthropic.Anthropic.
    Reads ANTHROPIC_API_KEY from env (the SDK does this automatically)."""

    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS

    def __post_init__(self) -> None:
        self._client = anthropic.Anthropic()

    def complete_text(self, system: str, user: str) -> str:
        """One-shot text completion. Returns the assistant's text content."""
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _extract_text(resp)

    def complete_vision(self, system: str, content_blocks: list[dict[str, Any]]) -> str:
        """One-shot vision completion. content_blocks contains image and text blocks."""
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": content_blocks}],
        )
        return _extract_text(resp)


def _extract_text(response: Any) -> str:
    """Concatenate text blocks from the response. Ignores non-text content."""
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts)
```

- [ ] **Step 2: Write a real-API smoke test (skipped without key)**

Create `tests/integration/test_llm_client.py`:

```python
import os

import pytest

from agents.llm_client import LLMClient


pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping integration test",
)


def test_complete_text_returns_non_empty_response():
    client = LLMClient()
    text = client.complete_text(
        system="Răspunzi cu un singur cuvânt: 'ok'.",
        user="Spune 'ok'.",
    )
    assert isinstance(text, str)
    assert len(text.strip()) > 0
```

- [ ] **Step 3: Run integration test (it should pass if key exists, skip otherwise)**

Run: `.venv\Scripts\pytest.exe tests/integration/test_llm_client.py -v`
Expected: PASS (real call) if `ANTHROPIC_API_KEY` is set, SKIPPED otherwise. Either is green.

- [ ] **Step 4: Run all tests so far**

Run: `.venv\Scripts\pytest.exe -v`
Expected: 13 PASSED + 1 PASSED/SKIPPED.

- [ ] **Step 5: Commit**

```bash
git add agents/llm_client.py tests/integration/test_llm_client.py
git commit -m "feat: thin Anthropic SDK wrapper (text + vision) with integration smoke test"
```

---

## Task 5: Discovery agent

The Discovery agent has four pure functions: `build_messages`, `parse_response`, `is_schema_complete`, `merge_answers`. All unit-tested with fixture JSON. The prompt template lives in `prompts/discovery.md`.

**Files:**
- Create: `prompts/discovery.md`
- Create: `agents/discovery.py`
- Create: `tests/unit/test_discovery.py`
- Create: `tests/fixtures/llm_responses/discovery_round1.json`
- Create: `tests/fixtures/llm_responses/discovery_round2_done.json`
- Create: `tests/fixtures/llm_responses/discovery_invalid.txt`

- [ ] **Step 1: Create the system prompt `prompts/discovery.md`**

```markdown
Ești asistentul Ciptronic pentru specificarea produselor personalizate.
Rolul tău: pornind de la o descriere vagă a clientului, completezi metodic
un checklist de caracteristici prin întrebări țintite, în limba română.

## Reguli stricte

1. RĂSPUNZI EXCLUSIV cu un obiect JSON valid, fără text înainte sau după.
2. Întrebările tale sunt în română, scurte (max o propoziție), clare.
3. Maximum 4 întrebări per rundă. Grupează-le tematic.
4. Pentru câmpuri cu opțiuni standard (croială, guler, tehnică), oferă o
   listă `variante` ca să ușurezi răspunsul userului.
5. Nu inventa. Dacă o caracteristică nu apare în descriere și nici în
   răspunsurile userului, las-o `null` și întreab-o la runda următoare.
6. Pentru câmpul `branding`: dacă userul spune "fără branding/print/logo"
   sau echivalent, completează-l ca:
   { "pozitie": "fără branding", "tehnica": null, "culori": [],
     "dimensiuni_aproximative": null }
   și consideră-l complet.
7. Marchezi `done: true` DOAR când toate câmpurile (inclusiv sub-câmpurile
   `branding` sau marcajul "fără branding") sunt non-null.
8. Dacă userul răspunde ambiguu sau contradictoriu, întreabă clarificator
   la runda următoare — NU presupune.

## Input

Vei primi în mesajul user un JSON cu:
- `schema`: definiția completă a checklist-ului pentru tipul de produs
- `initial_description`: ce a scris userul la start
- `current_state`: checklist-ul completat parțial până acum
- `history`: rundele anterioare (întrebări puse și răspunsuri primite)

## Output

Returnezi un obiect JSON cu structura:

```json
{
  "state": { /* schema completată parțial cu valorile cunoscute */ },
  "intrebari": [
    { "id": "<cheia câmpului sau cheia.subcheia>",
      "text": "<întrebarea în română>",
      "variante": ["<opțiune1>", "<opțiune2>"] }
  ],
  "done": <true|false>
}
```

Pentru sub-câmpuri de branding, `id` este `branding.pozitie`, `branding.tehnica`, etc.
Câmpul `variante` e opțional — îl pui doar când are sens să oferi opțiuni standard.

Când `done: true`, lista `intrebari` e goală.
```

- [ ] **Step 2: Create fixture `tests/fixtures/llm_responses/discovery_round1.json`**

```json
{
  "state": {
    "culoare_principala": "albastru navy",
    "material": null,
    "croiala": null,
    "guler": null,
    "maneci": null,
    "branding": {
      "pozitie": "piept stâng",
      "tehnica": null,
      "culori": [],
      "dimensiuni_aproximative": null
    }
  },
  "intrebari": [
    { "id": "material", "text": "Ce material preferi?",
      "variante": ["bumbac 100%", "bumbac+poliester", "poliester"] },
    { "id": "croiala", "text": "Ce croială?",
      "variante": ["regular", "slim", "oversize"] },
    { "id": "branding.tehnica", "text": "Ce tehnică de aplicare a logo-ului?",
      "variante": ["serigrafie", "broderie", "DTF", "sublimare"] }
  ],
  "done": false
}
```

- [ ] **Step 3: Create fixture `tests/fixtures/llm_responses/discovery_round2_done.json`**

```json
{
  "state": {
    "culoare_principala": "albastru navy",
    "material": "bumbac 100%",
    "croiala": "slim",
    "guler": "rotund",
    "maneci": "scurte",
    "branding": {
      "pozitie": "piept stâng",
      "tehnica": "serigrafie",
      "culori": ["alb"],
      "dimensiuni_aproximative": "10cm x 10cm"
    }
  },
  "intrebari": [],
  "done": true
}
```

- [ ] **Step 4: Create fixture `tests/fixtures/llm_responses/discovery_invalid.txt`**

```
Salut! Hai sa iti zic ce am inteles despre tricoul tau:
- e navy
- are logo pe piept
Ce alte detalii ai?
```

(This is intentionally NOT JSON, used to test parse failure.)

- [ ] **Step 5: Write failing tests for `parse_response`**

Create `tests/unit/test_discovery.py`:

```python
from pathlib import Path

import pytest

from agents import discovery
from schemas import loader


FIXTURES = Path(__file__).parent.parent / "fixtures" / "llm_responses"


@pytest.fixture
def schema_tricou():
    return loader.load_schema("tricou")


def test_parse_response_valid_round1(schema_tricou):
    raw = (FIXTURES / "discovery_round1.json").read_text(encoding="utf-8")
    step = discovery.parse_response(raw)
    assert step.done is False
    assert step.state["culoare_principala"] == "albastru navy"
    assert step.state["branding"]["pozitie"] == "piept stâng"
    assert len(step.intrebari) == 3
    ids = {q["id"] for q in step.intrebari}
    assert {"material", "croiala", "branding.tehnica"} == ids


def test_parse_response_done(schema_tricou):
    raw = (FIXTURES / "discovery_round2_done.json").read_text(encoding="utf-8")
    step = discovery.parse_response(raw)
    assert step.done is True
    assert step.intrebari == []
    assert step.state["material"] == "bumbac 100%"


def test_parse_response_invalid_raises():
    raw = (FIXTURES / "discovery_invalid.txt").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        discovery.parse_response(raw)
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/unit/test_discovery.py -v`
Expected: FAIL — ImportError because `agents/discovery.py` is empty.

- [ ] **Step 7: Implement `parse_response` and `DiscoveryStep` in `agents/discovery.py`**

```python
import json
from dataclasses import dataclass


@dataclass
class DiscoveryStep:
    """A single round's output from the Discovery LLM."""
    state: dict
    intrebari: list[dict]
    done: bool


def parse_response(text: str) -> DiscoveryStep:
    """Parse the LLM's JSON output. Raises ValueError on invalid input."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Răspunsul LLM nu e JSON valid: {e}") from e

    for key in ("state", "intrebari", "done"):
        if key not in data:
            raise ValueError(f"Lipsește cheia '{key}' din răspunsul LLM")

    if not isinstance(data["state"], dict):
        raise ValueError("Cheia 'state' trebuie să fie obiect")
    if not isinstance(data["intrebari"], list):
        raise ValueError("Cheia 'intrebari' trebuie să fie listă")
    if not isinstance(data["done"], bool):
        raise ValueError("Cheia 'done' trebuie să fie boolean")

    return DiscoveryStep(
        state=data["state"],
        intrebari=data["intrebari"],
        done=data["done"],
    )
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/unit/test_discovery.py -v`
Expected: PASS — 3 tests green.

- [ ] **Step 9: Write failing tests for `is_schema_complete`**

Append to `tests/unit/test_discovery.py`:

```python
def test_is_schema_complete_true_for_full_state(schema_tricou):
    state = {
        "culoare_principala": "navy", "material": "bumbac 100%",
        "croiala": "slim", "guler": "rotund", "maneci": "scurte",
        "branding": {"pozitie": "piept stâng", "tehnica": "serigrafie",
                     "culori": ["alb"], "dimensiuni_aproximative": "10cm x 10cm"}
    }
    complete, missing = discovery.is_schema_complete(schema_tricou, state)
    assert complete is True
    assert missing == []


def test_is_schema_complete_true_for_fara_branding(schema_tricou):
    state = {
        "culoare_principala": "navy", "material": "bumbac 100%",
        "croiala": "slim", "guler": "rotund", "maneci": "scurte",
        "branding": {"pozitie": "fără branding", "tehnica": None,
                     "culori": [], "dimensiuni_aproximative": None}
    }
    complete, missing = discovery.is_schema_complete(schema_tricou, state)
    assert complete is True
    assert missing == []


def test_is_schema_complete_false_with_missing_fields(schema_tricou):
    state = {
        "culoare_principala": "navy", "material": None,
        "croiala": "slim", "guler": "rotund", "maneci": "scurte",
        "branding": {"pozitie": "piept stâng", "tehnica": None,
                     "culori": [], "dimensiuni_aproximative": None}
    }
    complete, missing = discovery.is_schema_complete(schema_tricou, state)
    assert complete is False
    assert set(missing) == {"material", "branding.tehnica",
                            "branding.culori", "branding.dimensiuni_aproximative"}
```

- [ ] **Step 10: Run tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/unit/test_discovery.py -v`
Expected: 3 new tests fail with AttributeError on `is_schema_complete`.

- [ ] **Step 11: Implement `is_schema_complete`**

Append to `agents/discovery.py`:

```python
from schemas import loader


def is_schema_complete(schema: dict, state: dict) -> tuple[bool, list[str]]:
    """Check whether every applicable leaf key is non-null/non-empty.
    Returns (complete, list_of_missing_keys)."""
    applicable = loader.applicable_leaf_keys(schema, state)
    missing: list[str] = []
    for key in applicable:
        value = _read_dotted(state, key)
        if value is None or value == "" or value == []:
            missing.append(key)
    return (len(missing) == 0, missing)


def _read_dotted(state: dict, dotted_key: str):
    """Read 'a.b' from state by traversing dict keys."""
    parts = dotted_key.split(".")
    cur = state
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur
```

- [ ] **Step 12: Run tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/unit/test_discovery.py -v`
Expected: PASS — 6 tests green.

- [ ] **Step 13: Write failing tests for `merge_answers`**

Append to `tests/unit/test_discovery.py`:

```python
def test_merge_answers_flat_key():
    state = {"material": None, "croiala": None}
    new_state = discovery.merge_answers(state, {"material": "bumbac 100%"})
    assert new_state["material"] == "bumbac 100%"
    assert new_state["croiala"] is None


def test_merge_answers_dotted_key():
    state = {"branding": {"pozitie": None, "tehnica": None,
                          "culori": [], "dimensiuni_aproximative": None}}
    new_state = discovery.merge_answers(state, {
        "branding.pozitie": "piept stâng",
        "branding.tehnica": "serigrafie",
    })
    assert new_state["branding"]["pozitie"] == "piept stâng"
    assert new_state["branding"]["tehnica"] == "serigrafie"


def test_merge_answers_returns_new_dict_without_mutating_input():
    state = {"material": None}
    new_state = discovery.merge_answers(state, {"material": "bumbac"})
    assert state["material"] is None  # original unchanged
    assert new_state["material"] == "bumbac"
```

- [ ] **Step 14: Run tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/unit/test_discovery.py -v`
Expected: 3 new tests fail.

- [ ] **Step 15: Implement `merge_answers`**

Append to `agents/discovery.py`:

```python
import copy


def merge_answers(state: dict, answers: dict) -> dict:
    """Return a new state with answers merged in. Supports dotted keys
    (e.g. 'branding.tehnica'). Does not mutate the input state."""
    new_state = copy.deepcopy(state)
    for key, value in answers.items():
        _write_dotted(new_state, key, value)
    return new_state


def _write_dotted(state: dict, dotted_key: str, value) -> None:
    """Write a value at 'a.b.c' in state, creating intermediate dicts if needed."""
    parts = dotted_key.split(".")
    cur = state
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value
```

- [ ] **Step 16: Run tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/unit/test_discovery.py -v`
Expected: PASS — 9 tests green.

- [ ] **Step 17: Write failing test for `build_messages`**

Append to `tests/unit/test_discovery.py`:

```python
def test_build_messages_returns_system_and_user_strings(schema_tricou):
    system, user = discovery.build_messages(
        schema=schema_tricou,
        initial_description="tricou navy cu logo pe piept",
        state={"culoare_principala": "navy"},
        history=[{"round": 1, "questions": [], "answers": {}}],
    )
    assert isinstance(system, str) and len(system) > 100
    assert "Ești asistentul Ciptronic" in system

    import json as _json
    payload = _json.loads(user)
    assert payload["schema"]["id"] == "tricou"
    assert payload["initial_description"] == "tricou navy cu logo pe piept"
    assert payload["current_state"]["culoare_principala"] == "navy"
    assert payload["history"] == [{"round": 1, "questions": [], "answers": {}}]
```

- [ ] **Step 18: Run test to verify it fails**

Run: `.venv\Scripts\pytest.exe tests/unit/test_discovery.py::test_build_messages_returns_system_and_user_strings -v`
Expected: FAIL on AttributeError.

- [ ] **Step 19: Implement `build_messages`**

Append to `agents/discovery.py`:

```python
from pathlib import Path


PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "discovery.md"


def build_messages(schema: dict, initial_description: str,
                   state: dict, history: list) -> tuple[str, str]:
    """Build (system_prompt, user_message_json) for one Discovery round.
    Pure: no network calls, no disk writes."""
    system = PROMPT_PATH.read_text(encoding="utf-8")
    user = json.dumps({
        "schema": schema,
        "initial_description": initial_description,
        "current_state": state,
        "history": history,
    }, ensure_ascii=False, indent=2)
    return system, user
```

- [ ] **Step 20: Run all discovery tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/unit/test_discovery.py -v`
Expected: PASS — 10 tests green.

- [ ] **Step 21: Commit**

```bash
git add prompts/discovery.md agents/discovery.py tests/unit/test_discovery.py tests/fixtures/llm_responses/discovery_round1.json tests/fixtures/llm_responses/discovery_round2_done.json tests/fixtures/llm_responses/discovery_invalid.txt
git commit -m "feat: Discovery agent (build_messages, parse_response, is_complete, merge)"
```

---

## Task 6: Inspector agent

The Inspector agent has two functions: `build_messages` (with base64-encoded images) and `parse_report` (with code-side validation that each applicable field appears exactly once). Dataclasses model the report.

**Files:**
- Create: `prompts/inspector.md`
- Create: `agents/inspector.py`
- Create: `tests/unit/test_inspector.py`
- Create: `tests/fixtures/llm_responses/inspector_full.json`
- Create: `tests/fixtures/llm_responses/inspector_missing_field.json`
- Create: `tests/fixtures/llm_responses/inspector_fara_branding.json`
- Create: `tests/fixtures/images/README.md`

- [ ] **Step 1: Create the system prompt `prompts/inspector.md`**

```markdown
Ești inspectorul vizual Ciptronic pentru produse personalizate.
Primești specificația unui produs (JSON) și 1-4 poze cu produsul finit.
Verifici, câmp cu câmp, dacă produsul fotografiat corespunde specificației.

## Reguli de onestitate (cele mai importante)

1. RĂSPUNZI EXCLUSIV cu un obiect JSON valid, fără text înainte sau după.
2. NU PRESUPUNE conformitate pentru câmpuri pe care NU LE POȚI VEDEA în poze.
   Dacă pozele sunt din față și specificația cere ceva pe spate — câmpul
   merge în `nevizibil`, NU în `conform`.
3. Onestitatea e prioritară față de completitudine. E mai bine să marchezi
   3 câmpuri ca `nevizibil` decât să spui "conform" fără dovadă.
4. Pentru fiecare câmp, motivul trebuie să fie concret și verificabil
   ("se vede în poza 2 marginea gulerului rotund"), nu vag ("pare ok").
5. Confidence: `scăzut` = doar indicii indirecte; `mediu` = vizibil dar nu
   din unghi optim; `ridicat` = clar vizibil și fără ambiguitate.

## Reguli structurale

6. Fiecare câmp-frunză aplicabil al schemei apare EXACT O DATĂ într-una
   din cele trei liste: `conform`, `neconform`, `nevizibil`.
7. Pentru `branding` activ (cu valori non-null), raportezi toate cele 4
   sub-câmpuri: `branding.pozitie`, `branding.tehnica`, `branding.culori`,
   `branding.dimensiuni_aproximative`.
8. Pentru `branding` marcat "fără branding" (spec are
   `branding.pozitie = "fără branding"`), raportezi DOAR `branding.pozitie`
   (verifici că pozele NU arată niciun logo/print). Celelalte 3 sub-câmpuri
   nu se raportează — nu sunt aplicabile. Apariția neașteptată a unui
   branding = neconform pe `branding.pozitie`.
9. Toate textele răspunsului sunt în limba română.

## Output

```json
{
  "conform": [
    { "camp": "<key>", "valoare_asteptata": "<>", "valoare_observata": "<>",
      "incredere": "scăzut|mediu|ridicat", "motiv": "<>" }
  ],
  "neconform": [ /* idem */ ],
  "nevizibil": [
    { "camp": "<key>", "valoare_asteptata": "<>",
      "motiv": "<de ce nu se poate vedea>" }
  ]
}
```
```

- [ ] **Step 2: Create fixture `tests/fixtures/llm_responses/inspector_full.json`**

```json
{
  "conform": [
    {
      "camp": "culoare_principala",
      "valoare_asteptata": "albastru navy",
      "valoare_observata": "albastru navy",
      "incredere": "ridicat",
      "motiv": "culoarea este clar vizibilă în pozele 1 și 2"
    },
    {
      "camp": "croiala",
      "valoare_asteptata": "slim",
      "valoare_observata": "slim",
      "incredere": "ridicat",
      "motiv": "fitting strâns pe corp, vizibil în poza 1"
    },
    {
      "camp": "guler",
      "valoare_asteptata": "rotund",
      "valoare_observata": "rotund",
      "incredere": "ridicat",
      "motiv": "guler rotund clasic vizibil în poza 1"
    },
    {
      "camp": "maneci",
      "valoare_asteptata": "scurte",
      "valoare_observata": "scurte",
      "incredere": "ridicat",
      "motiv": "mâneci scurte vizibile clar"
    },
    {
      "camp": "branding.pozitie",
      "valoare_asteptata": "piept stâng",
      "valoare_observata": "piept stâng",
      "incredere": "ridicat",
      "motiv": "logo poziționat clar pe piept stâng, poza 1"
    },
    {
      "camp": "branding.culori",
      "valoare_asteptata": ["alb"],
      "valoare_observata": "alb",
      "incredere": "ridicat",
      "motiv": "logo alb pe fond navy"
    }
  ],
  "neconform": [
    {
      "camp": "branding.tehnica",
      "valoare_asteptata": "serigrafie",
      "valoare_observata": "pare DTF",
      "incredere": "mediu",
      "motiv": "în poza 3 logo-ul are textură ridicată; serigrafia ar fi mai plată"
    }
  ],
  "nevizibil": [
    {
      "camp": "material",
      "valoare_asteptata": "bumbac 100%",
      "motiv": "țesătura nu apare în closeup în niciuna dintre poze"
    },
    {
      "camp": "branding.dimensiuni_aproximative",
      "valoare_asteptata": "10cm x 10cm",
      "motiv": "nicio referință de scară în poze pentru a estima dimensiunea"
    }
  ]
}
```

- [ ] **Step 3: Create fixture `tests/fixtures/llm_responses/inspector_missing_field.json`**

```json
{
  "conform": [
    { "camp": "culoare_principala", "valoare_asteptata": "navy",
      "valoare_observata": "navy", "incredere": "ridicat", "motiv": "vizibil" },
    { "camp": "croiala", "valoare_asteptata": "slim",
      "valoare_observata": "slim", "incredere": "ridicat", "motiv": "vizibil" },
    { "camp": "guler", "valoare_asteptata": "rotund",
      "valoare_observata": "rotund", "incredere": "ridicat", "motiv": "vizibil" },
    { "camp": "maneci", "valoare_asteptata": "scurte",
      "valoare_observata": "scurte", "incredere": "ridicat", "motiv": "vizibil" },
    { "camp": "branding.pozitie", "valoare_asteptata": "piept stâng",
      "valoare_observata": "piept stâng", "incredere": "ridicat", "motiv": "vizibil" }
  ],
  "neconform": [],
  "nevizibil": [
    { "camp": "branding.tehnica", "valoare_asteptata": "serigrafie",
      "motiv": "neclară" },
    { "camp": "branding.culori", "valoare_asteptata": ["alb"],
      "motiv": "neclară" },
    { "camp": "branding.dimensiuni_aproximative", "valoare_asteptata": "10cm",
      "motiv": "neclară" }
  ]
}
```

(Note: `material` is intentionally missing from all three lists.)

- [ ] **Step 4: Create fixture `tests/fixtures/llm_responses/inspector_fara_branding.json`**

```json
{
  "conform": [
    { "camp": "culoare_principala", "valoare_asteptata": "navy",
      "valoare_observata": "navy", "incredere": "ridicat", "motiv": "vizibil" },
    { "camp": "croiala", "valoare_asteptata": "slim",
      "valoare_observata": "slim", "incredere": "ridicat", "motiv": "vizibil" },
    { "camp": "guler", "valoare_asteptata": "rotund",
      "valoare_observata": "rotund", "incredere": "ridicat", "motiv": "vizibil" },
    { "camp": "maneci", "valoare_asteptata": "scurte",
      "valoare_observata": "scurte", "incredere": "ridicat", "motiv": "vizibil" },
    { "camp": "branding.pozitie", "valoare_asteptata": "fără branding",
      "valoare_observata": "fără branding", "incredere": "ridicat",
      "motiv": "nu apare niciun logo/print în niciuna din poze" }
  ],
  "neconform": [],
  "nevizibil": [
    { "camp": "material", "valoare_asteptata": "bumbac 100%",
      "motiv": "țesătura nu apare în closeup" }
  ]
}
```

(Six fields total — the three other branding subfields are excluded per the "fără branding" rule.)

- [ ] **Step 5: Create `tests/fixtures/images/README.md`**

```markdown
# Test fixture images

These are gitignored. Provide:

- `tricou_navy_serigrafie.jpg` — front shot of a navy slim-fit t-shirt with a white logo on left chest, serigraphy-applied.
- `tricou_navy_dtf.jpg` — same product but with the logo applied with DTF (raised texture).
- `tricou_navy_back.jpg` — back view of the same tricou (no branding on back).

You can use your own photos or stock images. Resolution: anything ≥ 800x600 is fine.
```

- [ ] **Step 6: Write failing tests for `parse_report` with the full fixture**

Create `tests/unit/test_inspector.py`:

```python
from pathlib import Path

import pytest

from agents import inspector
from schemas import loader


FIXTURES = Path(__file__).parent.parent / "fixtures" / "llm_responses"


@pytest.fixture
def schema_tricou():
    return loader.load_schema("tricou")


@pytest.fixture
def spec_active_branding():
    return {
        "culoare_principala": "albastru navy",
        "material": "bumbac 100%",
        "croiala": "slim",
        "guler": "rotund",
        "maneci": "scurte",
        "branding": {
            "pozitie": "piept stâng",
            "tehnica": "serigrafie",
            "culori": ["alb"],
            "dimensiuni_aproximative": "10cm x 10cm",
        },
    }


@pytest.fixture
def spec_fara_branding():
    return {
        "culoare_principala": "albastru navy",
        "material": "bumbac 100%",
        "croiala": "slim",
        "guler": "rotund",
        "maneci": "scurte",
        "branding": {
            "pozitie": "fără branding",
            "tehnica": None,
            "culori": [],
            "dimensiuni_aproximative": None,
        },
    }


def test_parse_report_full_fixture_returns_dataclass(schema_tricou, spec_active_branding):
    raw = (FIXTURES / "inspector_full.json").read_text(encoding="utf-8")
    report = inspector.parse_report(raw, schema_tricou, spec_active_branding)
    assert len(report.conform) == 6
    assert len(report.neconform) == 1
    assert len(report.nevizibil) == 2

    all_camps = (
        [i.camp for i in report.conform]
        + [i.camp for i in report.neconform]
        + [i.camp for i in report.nevizibil]
    )
    assert len(all_camps) == 9  # all leaf keys for active branding
    assert len(set(all_camps)) == 9  # exactly once each


def test_parse_report_active_branding_raises_when_field_missing(schema_tricou, spec_active_branding):
    raw = (FIXTURES / "inspector_missing_field.json").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="material"):
        inspector.parse_report(raw, schema_tricou, spec_active_branding)


def test_parse_report_fara_branding_expects_only_six_fields(schema_tricou, spec_fara_branding):
    raw = (FIXTURES / "inspector_fara_branding.json").read_text(encoding="utf-8")
    report = inspector.parse_report(raw, schema_tricou, spec_fara_branding)
    all_camps = (
        [i.camp for i in report.conform]
        + [i.camp for i in report.neconform]
        + [i.camp for i in report.nevizibil]
    )
    assert len(all_camps) == 6
    assert "branding.tehnica" not in all_camps
    assert "branding.culori" not in all_camps
    assert "branding.dimensiuni_aproximative" not in all_camps


def test_parse_report_invalid_incredere_raises(schema_tricou, spec_active_branding):
    bad = '{"conform": [{"camp": "culoare_principala", "valoare_asteptata": "navy", "valoare_observata": "navy", "incredere": "foarte ridicat", "motiv": "x"}], "neconform": [], "nevizibil": []}'
    with pytest.raises(ValueError, match="incredere"):
        inspector.parse_report(bad, schema_tricou, spec_active_branding)
```

- [ ] **Step 7: Run tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/unit/test_inspector.py -v`
Expected: FAIL — ImportError because `agents/inspector.py` is empty.

- [ ] **Step 8: Implement dataclasses and `parse_report` in `agents/inspector.py`**

```python
import json
from dataclasses import dataclass, field
from typing import Literal

from schemas import loader


Incredere = Literal["scăzut", "mediu", "ridicat"]
ALLOWED_INCREDERE = {"scăzut", "mediu", "ridicat"}


@dataclass
class ValidationItem:
    camp: str
    valoare_asteptata: object
    valoare_observata: object | None  # None for nevizibil
    incredere: Incredere | None  # None for nevizibil
    motiv: str


@dataclass
class ValidationReport:
    conform: list[ValidationItem] = field(default_factory=list)
    neconform: list[ValidationItem] = field(default_factory=list)
    nevizibil: list[ValidationItem] = field(default_factory=list)


def parse_report(text: str, schema: dict, spec: dict) -> ValidationReport:
    """Parse the LLM's JSON report.

    Validates:
    - JSON is well-formed
    - All three lists are present
    - Every applicable leaf key (per schema+spec) appears exactly once
    - 'incredere' is one of the allowed values for conform/neconform items
    - 'motiv' is non-empty for every item
    """
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Răspunsul Inspector nu e JSON valid: {e}") from e

    for key in ("conform", "neconform", "nevizibil"):
        if key not in data:
            raise ValueError(f"Lipsește lista '{key}' din răspuns")
        if not isinstance(data[key], list):
            raise ValueError(f"'{key}' trebuie să fie listă")

    conform = [_parse_item(i, in_nevizibil=False) for i in data["conform"]]
    neconform = [_parse_item(i, in_nevizibil=False) for i in data["neconform"]]
    nevizibil = [_parse_item(i, in_nevizibil=True) for i in data["nevizibil"]]

    applicable = set(loader.applicable_leaf_keys(schema, spec))
    reported = (
        {i.camp for i in conform}
        | {i.camp for i in neconform}
        | {i.camp for i in nevizibil}
    )
    missing = applicable - reported
    extra = reported - applicable
    if missing:
        raise ValueError(f"Câmpuri lipsă din raport: {sorted(missing)}")
    if extra:
        raise ValueError(f"Câmpuri neașteptate în raport: {sorted(extra)}")

    total = len(conform) + len(neconform) + len(nevizibil)
    if total != len(applicable):
        raise ValueError(
            f"Fiecare câmp trebuie raportat exact o dată. "
            f"Raportate: {total}, așteptate: {len(applicable)}"
        )

    return ValidationReport(conform=conform, neconform=neconform, nevizibil=nevizibil)


def _parse_item(raw: dict, in_nevizibil: bool) -> ValidationItem:
    if "camp" not in raw or "valoare_asteptata" not in raw:
        raise ValueError(f"Item incomplet: {raw}")
    if not raw.get("motiv"):
        raise ValueError(f"motiv lipsă pentru {raw.get('camp')}")

    if in_nevizibil:
        return ValidationItem(
            camp=raw["camp"],
            valoare_asteptata=raw["valoare_asteptata"],
            valoare_observata=None,
            incredere=None,
            motiv=raw["motiv"],
        )

    incredere = raw.get("incredere")
    if incredere not in ALLOWED_INCREDERE:
        raise ValueError(
            f"incredere invalidă pentru {raw['camp']}: '{incredere}' "
            f"(permise: {sorted(ALLOWED_INCREDERE)})"
        )
    if "valoare_observata" not in raw:
        raise ValueError(f"valoare_observata lipsă pentru {raw['camp']}")

    return ValidationItem(
        camp=raw["camp"],
        valoare_asteptata=raw["valoare_asteptata"],
        valoare_observata=raw["valoare_observata"],
        incredere=incredere,  # type: ignore[arg-type]
        motiv=raw["motiv"],
    )
```

- [ ] **Step 9: Run tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/unit/test_inspector.py -v`
Expected: PASS — 4 tests green.

- [ ] **Step 10: Write failing test for `build_messages` with image encoding**

We need an actual binary image to test base64 encoding. Use Python's built-in to generate a tiny valid JPEG for the test (no external files needed).

Append to `tests/unit/test_inspector.py`:

```python
import base64


def _write_tiny_jpeg(path: Path) -> None:
    """Write the smallest possible valid JPEG (a single white pixel)."""
    # Minimal JPEG bytes (1x1 white pixel)
    jpeg_b64 = (
        "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQ"
        "EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB/8AAEQgAAQABAwEiAA"
        "IRAQMRAf/EABQAAQAAAAAAAAAAAAAAAAAAAAj/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8"
        "QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAh"
        "EDEQA/AL+AB//Z"
    )
    path.write_bytes(base64.b64decode(jpeg_b64))


def test_build_messages_encodes_images_as_base64(tmp_path, spec_active_branding):
    img_path = tmp_path / "img1.jpg"
    _write_tiny_jpeg(img_path)

    system, content_blocks = inspector.build_messages(
        spec=spec_active_branding,
        image_paths=[str(img_path)],
    )
    assert "inspectorul vizual Ciptronic" in system

    # First block(s) are image, last block is text
    assert content_blocks[0]["type"] == "image"
    assert content_blocks[0]["source"]["type"] == "base64"
    assert content_blocks[0]["source"]["media_type"] == "image/jpeg"
    assert len(content_blocks[0]["source"]["data"]) > 0

    text_block = content_blocks[-1]
    assert text_block["type"] == "text"
    assert "culoare_principala" in text_block["text"]


def test_build_messages_handles_multiple_images(tmp_path, spec_active_branding):
    img1 = tmp_path / "img1.jpg"
    img2 = tmp_path / "img2.jpg"
    _write_tiny_jpeg(img1)
    _write_tiny_jpeg(img2)

    _, content_blocks = inspector.build_messages(
        spec=spec_active_branding,
        image_paths=[str(img1), str(img2)],
    )
    image_blocks = [b for b in content_blocks if b["type"] == "image"]
    assert len(image_blocks) == 2
```

- [ ] **Step 11: Run tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/unit/test_inspector.py::test_build_messages_encodes_images_as_base64 -v`
Expected: FAIL — AttributeError on `build_messages`.

- [ ] **Step 12: Implement `build_messages`**

Append to `agents/inspector.py`:

```python
import base64
from pathlib import Path


PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "inspector.md"


def build_messages(spec: dict, image_paths: list[str]) -> tuple[str, list[dict]]:
    """Build (system_prompt, content_blocks) for the Inspector vision call.
    Reads each image from disk and encodes it as base64.
    The text block (containing the spec) is appended LAST so the model sees
    images first, then instructions referencing them by index."""
    system = PROMPT_PATH.read_text(encoding="utf-8")

    blocks: list[dict] = []
    for path in image_paths:
        data = Path(path).read_bytes()
        b64 = base64.standard_b64encode(data).decode("ascii")
        media_type = _media_type_for(path)
        blocks.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": media_type,
                "data": b64,
            },
        })

    spec_text = json.dumps(spec, ensure_ascii=False, indent=2)
    text = (
        f"Specificația produsului (JSON):\n```json\n{spec_text}\n```\n\n"
        f"Pozele atașate: {len(image_paths)} (numerotate 1..{len(image_paths)} "
        f"în ordinea de mai sus).\n\n"
        f"Analizează pozele câmp cu câmp conform regulilor și emite raportul JSON."
    )
    blocks.append({"type": "text", "text": text})

    return system, blocks


def _media_type_for(path: str) -> str:
    p = path.lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".gif"):
        return "image/gif"
    if p.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"
```

- [ ] **Step 13: Run all inspector tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/unit/test_inspector.py -v`
Expected: PASS — 6 tests green.

- [ ] **Step 14: Commit**

```bash
git add prompts/inspector.md agents/inspector.py tests/unit/test_inspector.py tests/fixtures/llm_responses/inspector_full.json tests/fixtures/llm_responses/inspector_missing_field.json tests/fixtures/llm_responses/inspector_fara_branding.json tests/fixtures/images/README.md
git commit -m "feat: Inspector agent (build_messages with vision, parse_report with strict validation)"
```

---

## Task 7: FastAPI scaffolding + landing page

Create the web layer skeleton: app instance, base template with CSS, landing page (`GET /`), session create (`POST /sessions`), and the main entry point.

**Files:**
- Create: `web/app.py`
- Create: `web/templates/base.html`
- Create: `web/templates/index.html`
- Create: `main.py`
- Create: `tests/e2e/test_routes.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Create `web/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="ro">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Ciptronic Product Validator{% endblock %}</title>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 800px;
            margin: 2rem auto;
            padding: 0 1.5rem;
            color: #1a1a1a;
            line-height: 1.5;
        }
        h1, h2, h3 { line-height: 1.2; }
        .card {
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1rem;
            background: #fff;
        }
        label { display: block; font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem; }
        input[type="text"], select, textarea {
            width: 100%;
            padding: 0.6rem;
            border: 1px solid #ccc;
            border-radius: 6px;
            font-size: 1rem;
            font-family: inherit;
        }
        textarea { min-height: 100px; resize: vertical; }
        button {
            background: #2563eb;
            color: white;
            border: none;
            padding: 0.7rem 1.4rem;
            border-radius: 6px;
            font-size: 1rem;
            cursor: pointer;
            margin-top: 1rem;
        }
        button:hover { background: #1e40af; }
        .field-list { list-style: none; padding: 0; }
        .field-list li { padding: 0.3rem 0; }
        .field-list .done { color: #16a34a; }
        .field-list .missing { color: #9ca3af; }
        .zone-conform { border-left: 4px solid #16a34a; padding-left: 1rem; }
        .zone-neconform { border-left: 4px solid #dc2626; padding-left: 1rem; }
        .zone-nevizibil { border-left: 4px solid #9ca3af; padding-left: 1rem; }
        .confidence-ridicat { color: #16a34a; font-weight: 600; }
        .confidence-mediu { color: #d97706; font-weight: 600; }
        .confidence-scazut { color: #dc2626; font-weight: 600; }
    </style>
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: Create `web/templates/index.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Ciptronic Product Validator</h1>
<p>Specifică un produs personalizat și validează-l vizual.</p>

<form class="card" hx-post="/sessions" hx-swap="none">
    <label for="product_type">Tip produs</label>
    <select id="product_type" name="product_type" required>
        {% for pt in product_types %}
        <option value="{{ pt }}">{{ pt|capitalize }}</option>
        {% endfor %}
    </select>

    <label for="initial_description">Descriere</label>
    <textarea id="initial_description" name="initial_description" required
              placeholder="ex: o bluză cu logo pe piept, navy, bumbac"></textarea>

    <button type="submit">Începe specificare →</button>
</form>
{% endblock %}
```

- [ ] **Step 3: Create `main.py`**

```python
from web.app import app

# `uvicorn main:app --reload` finds this app object.
```

- [ ] **Step 4: Modify `tests/conftest.py` to add a FastAPI client fixture**

Replace the file with:

```python
import sqlite3
from pathlib import Path
import pytest
from fastapi.testclient import TestClient


SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


@pytest.fixture
def conn():
    """In-memory SQLite connection with schema applied."""
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield c
    c.close()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """FastAPI TestClient bound to an isolated DB and uploads dir."""
    db_path = tmp_path / "test.db"
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    monkeypatch.setenv("DATABASE_PATH", str(db_path))
    monkeypatch.setenv("UPLOADS_DIR", str(uploads_dir))

    # Import AFTER env vars are set so app reads them.
    from web import app as web_app
    web_app.init_database()  # ensures schema is applied to the test DB
    return TestClient(web_app.app)
```

- [ ] **Step 5: Write a failing E2E test for `GET /` and `POST /sessions`**

Create `tests/e2e/test_routes.py`:

```python
def test_landing_page_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Ciptronic Product Validator" in response.text
    assert "tricou" in response.text.lower()


def test_create_session_returns_hx_redirect(client):
    response = client.post(
        "/sessions",
        data={"product_type": "tricou", "initial_description": "tricou navy cu logo"},
    )
    assert response.status_code == 200
    assert "HX-Redirect" in response.headers
    redirect_to = response.headers["HX-Redirect"]
    assert redirect_to.startswith("/sessions/")


def test_healthz(client):
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.text.strip('"') == "ok"
```

- [ ] **Step 6: Run E2E tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/e2e/test_routes.py -v`
Expected: FAIL — `web/app.py` doesn't exist or has no app.

- [ ] **Step 7: Implement `web/app.py`**

For Task 7 we implement only landing + POST /sessions + healthz. Discovery and Inspector flows come in Tasks 8 and 9.

```python
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from db import repository
from schemas import loader


BASE_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./ciptronic.db")
SCHEMA_PATH = BASE_DIR.parent / "db" / "schema.sql"


app = FastAPI(title="Ciptronic Product Validator")


def init_database() -> None:
    """Apply the schema to the DB path from env. Idempotent."""
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn():
    """Yield a SQLite connection with row_factory configured."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@app.on_event("startup")
def _startup() -> None:
    init_database()


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return TEMPLATES.TemplateResponse(
        "index.html",
        {"request": request, "product_types": loader.available_product_types()},
    )


@app.post("/sessions")
def create_session(product_type: str = Form(...), initial_description: str = Form(...)):
    with get_conn() as conn:
        sid = repository.create_session(conn, product_type, initial_description)
    return Response(status_code=200, headers={"HX-Redirect": f"/sessions/{sid}"})


@app.get("/healthz", response_class=Response)
def healthz():
    return Response(content="ok", media_type="text/plain")
```

- [ ] **Step 8: Run E2E tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/e2e/test_routes.py -v`
Expected: PASS — 3 tests green.

- [ ] **Step 9: Manual smoke test — boot the server**

Run: `.venv\Scripts\uvicorn.exe main:app --port 8765`
Expected: server starts. In a browser, open `http://localhost:8765/` — landing page renders with "Tricou" in the dropdown. Stop with Ctrl+C.

- [ ] **Step 10: Commit**

```bash
git add web/app.py web/templates/base.html web/templates/index.html main.py tests/conftest.py tests/e2e/test_routes.py
git commit -m "feat: FastAPI scaffolding, landing page, POST /sessions, healthz"
```

---

## Task 8: Discovery web flow (sessions + answers)

Add the routes that drive the Discovery loop: viewing a session, submitting answers, swapping the HTMX partial. The LLM is mocked in E2E tests so we don't hit the real API.

**Files:**
- Modify: `web/app.py`
- Create: `web/templates/session.html`
- Create: `web/templates/_session_body.html`
- Modify: `tests/e2e/test_routes.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Create `web/templates/_session_body.html` (the HTMX swap target)**

```html
<div id="session-body">
    <div class="card">
        <h3>Stare checklist <small>(Runda {{ rounds_used }} / 5)</small></h3>
        <ul class="field-list">
            {% for entry in field_state %}
            <li class="{{ 'done' if entry.filled else 'missing' }}">
                {{ '✓' if entry.filled else '·' }}
                <strong>{{ entry.label }}:</strong>
                {{ entry.display_value if entry.filled else '(necunoscut)' }}
            </li>
            {% endfor %}
        </ul>
    </div>

    {% if done %}
    <div class="card">
        <h3>✓ Specificație completă</h3>
        <p>Toate câmpurile sunt acoperite.</p>
        <a href="/sessions/{{ session_id }}/validate">
            <button type="button">Validează cu poze →</button>
        </a>
    </div>
    {% elif intrebari %}
    <form class="card"
          hx-post="/sessions/{{ session_id }}/answer"
          hx-target="#session-body"
          hx-swap="outerHTML">
        <h3>Întrebări</h3>
        {% for q in intrebari %}
        <label>{{ q.text }}</label>
        {% if q.variante %}
            {% for v in q.variante %}
            <label style="font-weight:normal; display:block;">
                <input type="radio" name="answer.{{ q.id }}" value="{{ v }}" required>
                {{ v }}
            </label>
            {% endfor %}
        {% else %}
            <input type="text" name="answer.{{ q.id }}" required>
        {% endif %}
        {% endfor %}
        <button type="submit">Trimite răspunsuri</button>
    </form>
    {% else %}
    <div class="card">
        <p>Sesiunea s-a închis după 5 runde fără completare totală.
        Câmpurile rămase nemarcate sunt afișate ca (necunoscut) mai sus.</p>
        <a href="/sessions/{{ session_id }}/validate">
            <button type="button">Continuă către validare</button>
        </a>
    </div>
    {% endif %}
</div>
```

- [ ] **Step 2: Create `web/templates/session.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Sesiune {{ session_id[:8] }} — {{ product_type|capitalize }}</h1>
<p><em>"{{ initial_description }}"</em></p>
{% include "_session_body.html" %}
{% endblock %}
```

- [ ] **Step 3: Modify `tests/conftest.py` to add an LLM mock fixture**

Append to `tests/conftest.py`:

```python
class _FakeLLM:
    """Replacement for LLMClient used in E2E tests.
    Pop responses off a FIFO queue when called."""

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
    """Patch web.app.get_llm_client to return a FakeLLM instance."""
    fake = _FakeLLM()
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_llm_client", lambda: fake)
    return fake
```

- [ ] **Step 4: Write failing E2E tests for Discovery flow**

Append to `tests/e2e/test_routes.py`:

```python
from pathlib import Path


FIXTURES = Path(__file__).parent.parent / "fixtures" / "llm_responses"


def _create_session(client, fake_llm):
    fake_llm.queue_text((FIXTURES / "discovery_round1.json").read_text(encoding="utf-8"))
    response = client.post(
        "/sessions",
        data={"product_type": "tricou", "initial_description": "tricou navy cu logo pe piept"},
    )
    return response.headers["HX-Redirect"]


def test_get_session_after_creation_shows_partial_state(client, fake_llm):
    url = _create_session(client, fake_llm)

    r = client.get(url)
    assert r.status_code == 200
    assert "albastru navy" in r.text  # filled by round 1
    assert "Ce material" in r.text or "material" in r.text


def test_submit_answers_returns_partial_with_done_when_llm_finishes(client, fake_llm):
    url = _create_session(client, fake_llm)
    # Round 2: LLM marks done=true
    fake_llm.queue_text((FIXTURES / "discovery_round2_done.json").read_text(encoding="utf-8"))

    r = client.post(
        url + "/answer",
        data={
            "answer.material": "bumbac 100%",
            "answer.croiala": "slim",
            "answer.branding.tehnica": "serigrafie",
        },
    )
    assert r.status_code == 200
    assert "Specificație completă" in r.text
    assert "Validează cu poze" in r.text


def test_session_after_five_rounds_force_closes(client, fake_llm):
    url = _create_session(client, fake_llm)
    # Queue 4 more "not done" responses (rounds 2-5)
    for _ in range(4):
        fake_llm.queue_text((FIXTURES / "discovery_round1.json").read_text(encoding="utf-8"))

    for _ in range(4):
        client.post(url + "/answer", data={"answer.material": "bumbac 100%"})

    # After round 5, the partial body should NOT show new questions —
    # it should show the force-close message OR done if the schema lucked
    # out (which it won't with the round1 fixture).
    r = client.get(url)
    assert "Runda 5" in r.text or "Runda 5 / 5" in r.text
```

- [ ] **Step 5: Run E2E tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/e2e/test_routes.py -v`
Expected: 3 new tests fail — routes don't exist yet.

- [ ] **Step 6: Implement the Discovery routes in `web/app.py`**

Add this code to `web/app.py` (and the helper functions it needs). The full diff is large; here is the augmented file:

```python
import json
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates

from agents import discovery
from agents.llm_client import LLMClient
from db import repository
from schemas import loader


BASE_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./ciptronic.db")
SCHEMA_PATH = BASE_DIR.parent / "db" / "schema.sql"

MAX_ROUNDS = 5

_llm_singleton: LLMClient | None = None


def get_llm_client() -> Any:
    """Lazily build a singleton LLMClient. Tests patch this function."""
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = LLMClient()
    return _llm_singleton


app = FastAPI(title="Ciptronic Product Validator")


def init_database() -> None:
    conn = sqlite3.connect(DATABASE_PATH)
    try:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


@app.on_event("startup")
def _startup() -> None:
    init_database()


@app.get("/", response_class=HTMLResponse)
def landing(request: Request):
    return TEMPLATES.TemplateResponse(
        "index.html",
        {"request": request, "product_types": loader.available_product_types()},
    )


@app.post("/sessions")
def create_session(product_type: str = Form(...), initial_description: str = Form(...)):
    schema = loader.load_schema(product_type)
    initial_state = loader.empty_state(schema)

    # Run the very first Discovery round immediately so the user lands on a
    # session view that already has questions to answer.
    llm = get_llm_client()
    system, user = discovery.build_messages(
        schema=schema,
        initial_description=initial_description,
        state=initial_state,
        history=[],
    )
    raw = llm.complete_text(system=system, user=user)
    step = discovery.parse_response(raw)

    with get_conn() as conn:
        sid = repository.create_session(conn, product_type, initial_description)
        history = [{"round": 1, "questions": step.intrebari, "answers": None}]
        repository.update_session_state(conn, sid, step.state, history, rounds=1)
        if step.done:
            complete, _ = discovery.is_schema_complete(schema, step.state)
            if complete:
                repository.finalize_session(conn, sid)

    return Response(status_code=200, headers={"HX-Redirect": f"/sessions/{sid}"})


@app.get("/sessions/{session_id}", response_class=HTMLResponse)
def view_session(session_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_session(conn, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")

    schema = loader.load_schema(row["product_type"])
    state = json.loads(row["state_json"])
    history = json.loads(row["history_json"])
    last_questions = history[-1]["questions"] if history else []

    ctx = _build_session_context(
        request=request,
        session_id=session_id,
        product_type=row["product_type"],
        initial_description=row["initial_description"],
        schema=schema,
        state=state,
        intrebari=last_questions,
        rounds_used=row["rounds_used"],
        done=(row["status"] == "complete"),
    )
    return TEMPLATES.TemplateResponse("session.html", ctx)


@app.post("/sessions/{session_id}/answer", response_class=HTMLResponse)
async def submit_answers(session_id: str, request: Request):
    form = await request.form()
    answers = {
        k[len("answer."):]: v
        for k, v in form.items()
        if k.startswith("answer.")
    }

    with get_conn() as conn:
        row = repository.get_session(conn, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")
        if row["status"] == "complete":
            raise HTTPException(status_code=409, detail="Sesiune deja completă")

        schema = loader.load_schema(row["product_type"])
        state = json.loads(row["state_json"])
        history = json.loads(row["history_json"])
        rounds = row["rounds_used"]

        merged_state = discovery.merge_answers(state, answers)
        if history:
            history[-1]["answers"] = answers

        next_round = rounds + 1
        if next_round > MAX_ROUNDS:
            # Hard cap: stop calling LLM, force-close the session.
            repository.update_session_state(conn, session_id, merged_state,
                                            history, rounds=MAX_ROUNDS)
            repository.finalize_session(conn, session_id)
            ctx = _build_session_context(
                request=request,
                session_id=session_id,
                product_type=row["product_type"],
                initial_description=row["initial_description"],
                schema=schema,
                state=merged_state,
                intrebari=[],
                rounds_used=MAX_ROUNDS,
                done=True,
            )
            return TEMPLATES.TemplateResponse("_session_body.html", ctx)

        llm = get_llm_client()
        system, user = discovery.build_messages(
            schema=schema,
            initial_description=row["initial_description"],
            state=merged_state,
            history=history,
        )
        raw = llm.complete_text(system=system, user=user)
        step = discovery.parse_response(raw)

        history.append({"round": next_round, "questions": step.intrebari, "answers": None})

        complete, _ = discovery.is_schema_complete(schema, step.state)
        is_done = step.done and complete

        repository.update_session_state(conn, session_id, step.state, history, rounds=next_round)
        if is_done:
            repository.finalize_session(conn, session_id)

        ctx = _build_session_context(
            request=request,
            session_id=session_id,
            product_type=row["product_type"],
            initial_description=row["initial_description"],
            schema=schema,
            state=step.state,
            intrebari=step.intrebari,
            rounds_used=next_round,
            done=is_done,
        )
        return TEMPLATES.TemplateResponse("_session_body.html", ctx)


def _build_session_context(*, request, session_id, product_type, initial_description,
                           schema, state, intrebari, rounds_used, done) -> dict:
    """Build the Jinja context for both full session.html and _session_body.html.
    Computes the displayable field state list."""
    applicable = loader.applicable_leaf_keys(schema, state)
    field_state = []
    for field in schema["fields"]:
        if field.get("type") == "object":
            for sub in field["subfields"]:
                dotted = f"{field['key']}.{sub['key']}"
                if dotted not in applicable:
                    continue
                value = (state.get(field["key"]) or {}).get(sub["key"])
                field_state.append(_field_entry(f"{field['label']} → {sub['label']}", value))
        else:
            field_state.append(_field_entry(field["label"], state.get(field["key"])))

    return {
        "request": request,
        "session_id": session_id,
        "product_type": product_type,
        "initial_description": initial_description,
        "field_state": field_state,
        "intrebari": intrebari,
        "rounds_used": rounds_used,
        "done": done,
    }


def _field_entry(label: str, value) -> dict:
    filled = value is not None and value != "" and value != []
    if isinstance(value, list):
        display = ", ".join(str(v) for v in value)
    else:
        display = str(value) if value is not None else ""
    return {"label": label, "filled": filled, "display_value": display}


@app.get("/healthz", response_class=Response)
def healthz():
    return Response(content="ok", media_type="text/plain")
```

- [ ] **Step 7: Run E2E tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/e2e/test_routes.py -v`
Expected: PASS — all 6 tests green (3 original + 3 new Discovery flow).

- [ ] **Step 8: Run the full test suite**

Run: `.venv\Scripts\pytest.exe -v`
Expected: PASS — 25+ tests green (1 skipped if no API key).

- [ ] **Step 9: Manual smoke test — Discovery cycle in browser**

Set `ANTHROPIC_API_KEY` in `.env`, then run `.venv\Scripts\uvicorn.exe main:app --port 8765`.

Open `http://localhost:8765/`. Enter `tricou navy cu logo pe piept`. Submit. You should land on a session view with state and questions. Submit answers. Verify the partial swaps.

Stop the server.

- [ ] **Step 10: Commit**

```bash
git add web/app.py web/templates/session.html web/templates/_session_body.html tests/conftest.py tests/e2e/test_routes.py
git commit -m "feat: Discovery web flow (session view, answer submit, HTMX partial, 5-round cap)"
```

---

## Task 9: Inspector web flow (upload + report)

Add the routes that drive the Inspector validation: upload form, image-receiving POST that runs the LLM, and the report view.

**Files:**
- Modify: `web/app.py`
- Create: `web/templates/validate.html`
- Create: `web/templates/report.html`
- Modify: `tests/e2e/test_routes.py`

- [ ] **Step 1: Create `web/templates/validate.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Validare vizuală — {{ session_id[:8] }}</h1>

<details class="card">
    <summary><strong>Specificație curentă</strong></summary>
    <pre style="overflow:auto;">{{ spec_pretty }}</pre>
</details>

<form class="card" action="/sessions/{{ session_id }}/validate" method="post"
      enctype="multipart/form-data">
    <p>Încarcă 1–4 poze ale produsului finit (.jpg/.png).</p>

    <label>Poza 1 (obligatorie)</label>
    <input type="file" name="image1" accept="image/jpeg,image/png" required>

    <label>Poza 2 (opțională)</label>
    <input type="file" name="image2" accept="image/jpeg,image/png">

    <label>Poza 3 (opțională)</label>
    <input type="file" name="image3" accept="image/jpeg,image/png">

    <label>Poza 4 (opțională)</label>
    <input type="file" name="image4" accept="image/jpeg,image/png">

    <button type="submit">Rulează validarea</button>
</form>
{% endblock %}
```

- [ ] **Step 2: Create `web/templates/report.html`**

```html
{% extends "base.html" %}
{% block content %}
<h1>Raport validare {{ report_id[:8] }}</h1>

<div class="card zone-conform">
    <h2>✓ Conform ({{ conform|length }})</h2>
    {% if conform %}
    {% for item in conform %}
    <div style="margin-bottom: 1rem;">
        <strong>{{ item.camp }}:</strong> {{ item.valoare_asteptata }}<br>
        observat: {{ item.valoare_observata }}
        <span class="confidence-{{ item.incredere|replace('ă','a')|replace('ț','t') }}">[{{ item.incredere }}]</span><br>
        <small>{{ item.motiv }}</small>
    </div>
    {% endfor %}
    {% else %}<p>Niciun câmp conform.</p>{% endif %}
</div>

<div class="card zone-neconform">
    <h2>✗ Neconform ({{ neconform|length }})</h2>
    {% if neconform %}
    {% for item in neconform %}
    <div style="margin-bottom: 1rem;">
        <strong>{{ item.camp }}:</strong> {{ item.valoare_asteptata }}<br>
        observat: {{ item.valoare_observata }}
        <span class="confidence-{{ item.incredere|replace('ă','a')|replace('ț','t') }}">[{{ item.incredere }}]</span><br>
        <small>{{ item.motiv }}</small>
    </div>
    {% endfor %}
    {% else %}<p>Niciun câmp neconform.</p>{% endif %}
</div>

<div class="card zone-nevizibil">
    <h2>? Nevizibil ({{ nevizibil|length }})</h2>
    {% if nevizibil %}
    {% for item in nevizibil %}
    <div style="margin-bottom: 1rem;">
        <strong>{{ item.camp }}:</strong> {{ item.valoare_asteptata }}<br>
        <small>{{ item.motiv }}</small>
    </div>
    {% endfor %}
    {% else %}<p>Toate câmpurile au fost evaluate.</p>{% endif %}
</div>

<p><a href="/">← Înapoi la pagina principală</a></p>
{% endblock %}
```

- [ ] **Step 3: Write failing E2E tests for the Inspector flow**

Append to `tests/e2e/test_routes.py`:

```python
import base64
import io


def _tiny_jpeg_bytes() -> bytes:
    jpeg_b64 = (
        "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQ"
        "EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB/8AAEQgAAQABAwEiAA"
        "IRAQMRAf/EABQAAQAAAAAAAAAAAAAAAAAAAAj/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8"
        "QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAh"
        "EDEQA/AL+AB//Z"
    )
    return base64.b64decode(jpeg_b64)


def _complete_session(client, fake_llm) -> str:
    """Helper: create a session and drive it to 'complete' via mocked LLM."""
    fake_llm.queue_text((FIXTURES / "discovery_round2_done.json").read_text(encoding="utf-8"))
    r = client.post(
        "/sessions",
        data={"product_type": "tricou", "initial_description": "tricou navy cu logo"},
    )
    return r.headers["HX-Redirect"].rsplit("/", 1)[-1]  # bare session id


def test_get_validate_page_shows_upload_form(client, fake_llm):
    sid = _complete_session(client, fake_llm)
    r = client.get(f"/sessions/{sid}/validate")
    assert r.status_code == 200
    assert "Încarcă 1" in r.text or "Încarcă" in r.text
    assert "image1" in r.text


def test_post_validate_runs_inspector_and_redirects_to_report(client, fake_llm):
    sid = _complete_session(client, fake_llm)
    fake_llm.queue_vision(
        (FIXTURES / "inspector_full.json").read_text(encoding="utf-8")
    )

    files = {
        "image1": ("front.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg"),
    }
    r = client.post(f"/sessions/{sid}/validate", files=files, follow_redirects=False)
    assert r.status_code in (200, 303)
    if r.status_code == 303:
        location = r.headers["Location"]
    else:
        location = r.headers.get("HX-Redirect", "")
    assert location.startswith("/reports/")


def test_report_view_shows_three_zones(client, fake_llm):
    sid = _complete_session(client, fake_llm)
    fake_llm.queue_vision(
        (FIXTURES / "inspector_full.json").read_text(encoding="utf-8")
    )
    files = {"image1": ("front.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    r = client.post(f"/sessions/{sid}/validate", files=files, follow_redirects=False)
    location = r.headers.get("Location") or r.headers["HX-Redirect"]

    r = client.get(location)
    assert r.status_code == 200
    assert "Conform" in r.text
    assert "Neconform" in r.text
    assert "Nevizibil" in r.text
    assert "albastru navy" in r.text  # from inspector_full.json
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `.venv\Scripts\pytest.exe tests/e2e/test_routes.py -v`
Expected: 3 new tests fail — Inspector routes don't exist.

- [ ] **Step 5: Implement the Inspector routes in `web/app.py`**

Add to the top of `web/app.py`:

```python
from fastapi import UploadFile, File
from agents import inspector
```

Add `UPLOADS_DIR` constant near the other constants:

```python
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", str(BASE_DIR.parent / "uploads")))
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
```

Add `MAX_FILE_SIZE` constant:

```python
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB per image
```

Append these route handlers:

```python
@app.get("/sessions/{session_id}/validate", response_class=HTMLResponse)
def validate_page(session_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_session(conn, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")
        if row["status"] != "complete":
            raise HTTPException(status_code=409, detail="Sesiunea nu e completă încă")

    spec = json.loads(row["state_json"])
    return TEMPLATES.TemplateResponse(
        "validate.html",
        {
            "request": request,
            "session_id": session_id,
            "spec_pretty": json.dumps(spec, ensure_ascii=False, indent=2),
        },
    )


@app.post("/sessions/{session_id}/validate")
async def run_validation(
    session_id: str,
    request: Request,
    image1: UploadFile = File(...),
    image2: UploadFile | None = File(None),
    image3: UploadFile | None = File(None),
    image4: UploadFile | None = File(None),
):
    with get_conn() as conn:
        row = repository.get_session(conn, session_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Sesiune inexistentă")
        if row["status"] != "complete":
            raise HTTPException(status_code=409, detail="Sesiunea nu e completă încă")

        spec = json.loads(row["state_json"])
        schema = loader.load_schema(row["product_type"])

        upload_files = [f for f in (image1, image2, image3, image4) if f is not None]
        if len(upload_files) > 4:
            raise HTTPException(status_code=400, detail="Maximum 4 poze")

        # Save uploaded files to disk
        session_uploads = UPLOADS_DIR / session_id
        session_uploads.mkdir(parents=True, exist_ok=True)
        image_paths: list[str] = []
        for i, f in enumerate(upload_files, start=1):
            content = await f.read()
            if len(content) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"Poza {i} depășește limita de 5MB",
                )
            ext = ".jpg"
            if f.content_type == "image/png":
                ext = ".png"
            path = session_uploads / f"img{i}{ext}"
            path.write_bytes(content)
            image_paths.append(str(path))

        # Build messages and call the LLM
        llm = get_llm_client()
        system, content_blocks = inspector.build_messages(spec=spec, image_paths=image_paths)
        raw = llm.complete_vision(system=system, content_blocks=content_blocks)
        try:
            report = inspector.parse_report(raw, schema, spec)
        except ValueError as e:
            raise HTTPException(
                status_code=502,
                detail=f"Răspunsul Inspector nu e valid: {e}",
            )

        # Persist
        rid = repository.save_report(
            conn,
            session_id=session_id,
            spec=spec,
            image_paths=image_paths,
            conform=[_item_to_dict(i) for i in report.conform],
            neconform=[_item_to_dict(i) for i in report.neconform],
            nevizibil=[_item_to_dict(i) for i in report.nevizibil],
            raw=raw,
        )

    # Browser-form POST → 303 to the report page
    return Response(status_code=303, headers={"Location": f"/reports/{rid}"})


def _item_to_dict(item) -> dict:
    return {
        "camp": item.camp,
        "valoare_asteptata": item.valoare_asteptata,
        "valoare_observata": item.valoare_observata,
        "incredere": item.incredere,
        "motiv": item.motiv,
    }


@app.get("/reports/{report_id}", response_class=HTMLResponse)
def view_report(report_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_report(conn, report_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Raport inexistent")

    return TEMPLATES.TemplateResponse(
        "report.html",
        {
            "request": request,
            "report_id": report_id,
            "conform": json.loads(row["conform_json"]),
            "neconform": json.loads(row["neconform_json"]),
            "nevizibil": json.loads(row["nevizibil_json"]),
        },
    )
```

- [ ] **Step 6: Run E2E tests to verify they pass**

Run: `.venv\Scripts\pytest.exe tests/e2e/test_routes.py -v`
Expected: PASS — all 9 tests green.

- [ ] **Step 7: Run the full test suite**

Run: `.venv\Scripts\pytest.exe -v`
Expected: PASS — 28+ tests green (1 skipped if no API key).

- [ ] **Step 8: Commit**

```bash
git add web/app.py web/templates/validate.html web/templates/report.html tests/e2e/test_routes.py
git commit -m "feat: Inspector web flow (upload form, vision call, report view, three-zone display)"
```

---

## Task 10: README + manual smoke test + tag

Final polish. Fill in the README's manual test checklist, run the app end-to-end against a real Claude API, capture observations, and tag the MVP.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md` with the complete version**

```markdown
# Ciptronic Product Validator

Aplicație web locală pentru specificarea și validarea vizuală a produselor personalizate.

Două fluxuri:
1. **Discovery** — descriere vagă a clientului → JSON structurat, prin întrebări țintite, în maximum 5 runde.
2. **Inspector** — JSON + 1-4 poze ale produsului finit → raport pe trei zone: conform / neconform / nevizibil.

Aplicație Python (FastAPI + HTMX + Jinja + SQLite + Claude Sonnet 4.6). Rulează local. Single-user.

## Setup

Cerințe: Python 3.10+. Cont Anthropic cu o cheie de API.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell sau cmd
# source .venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
# editează .env și pune cheia ANTHROPIC_API_KEY
```

## Run

```bash
.venv\Scripts\uvicorn.exe main:app --reload
```

Deschide http://localhost:8000.

## Test

```bash
.venv\Scripts\pytest.exe
```

Pentru testele de integrare cu API-ul real:

```bash
$env:ANTHROPIC_API_KEY = "sk-ant-..."   # PowerShell
.venv\Scripts\pytest.exe tests/integration -v
```

## Structura proiectului

```
agents/         logica pură + wrapper LLM
prompts/        prompturile sistem (versionate)
schemas/        scheme JSON pe tipuri de produs (extensibil)
db/             schema SQL + repository functions
web/            FastAPI + templates Jinja
tests/          unit / integration / e2e + fixtures
main.py         entry point uvicorn
```

## Adaugă un tip de produs nou

1. Creează `schemas/<nume>.json` cu același format ca `tricou.json`.
2. Restart server.
3. Noul produs apare automat în dropdown-ul de pe landing.

Nu modifici cod.

## Manual test checklist

După `uvicorn main:app --reload`:

- [ ] / se deschide; dropdown listează "Tricou"
- [ ] Descriere "tricou navy cu logo pe piept stâng" → /sessions/{id} se deschide
- [ ] Pagina sesiunii arată câmpuri pre-completate de LLM (culoare, poziție branding)
- [ ] Întrebările sunt în română, max 4
- [ ] Radio buttons și input text funcționează; submit declanșează rundă nouă
- [ ] Răspunsul "fără branding" se acceptă (testul: spune-i la prima rundă; verifică în stare că `branding.pozitie = "fără branding"` și restul de sub-câmpuri sunt sărite)
- [ ] După max 5 runde, sesiunea închide oricum cu un mesaj de force-close
- [ ] /sessions/{id}/validate primește între 1-4 poze
- [ ] Raportul afișează cele 3 zone (conform / neconform / nevizibil)
- [ ] Pentru o poză exclusiv din față, câmpurile spate sunt în "nevizibil"
- [ ] Pentru un produs fără branding real, raportul include doar `branding.pozitie` (nu și sub-câmpurile)
- [ ] Restart uvicorn → sesiunile vechi sunt încă în DB (`ciptronic.db`)
- [ ] Pe Ctrl+C: server stop curat

## Spec & plan

- [Design spec](docs/superpowers/specs/2026-05-17-ciptronic-validator-design.md)
- [Implementation plan](docs/superpowers/plans/2026-05-17-ciptronic-validator.md)
```

- [ ] **Step 2: Run the manual checklist end-to-end against the real LLM**

Set up a real API key in `.env`, run `uvicorn main:app --reload`, and walk through the checklist. Note any issues.

For each broken item:
- If it's a bug in the code → file an issue or fix immediately.
- If it's a prompt issue → iterate the prompt file (`prompts/discovery.md` or `prompts/inspector.md`).
- If it's a missing feature → add to a follow-up plan, NOT to MVP.

- [ ] **Step 3: Run the full test suite one more time**

Run: `.venv\Scripts\pytest.exe -v`
Expected: 28+ PASSED, 1 SKIPPED (if no API key in env).

- [ ] **Step 4: Tag the MVP**

```bash
git add README.md
git commit -m "docs: complete README with setup, run, test, manual checklist"
git tag -a mvp-v0.1 -m "MVP: tricou Discovery + Inspector end-to-end"
```

- [ ] **Step 5: Final commit summary**

Run: `git log --oneline`
Expected: ~10 commits corresponding to Tasks 1-10, plus the initial spec commit, with a tag `mvp-v0.1`.

---

## Out of scope (NOT in MVP — for follow-up plans)

- Add `schemas/sapca.json` and `schemas/hanorac.json` (drop-in, no code changes needed once added).
- Camera capture in the browser (`getUserMedia` + canvas).
- Multi-user / authentication.
- Editable spec view between Discovery and Inspector (currently read-only at validate time).
- Re-run Inspector with new images on the same session (DB schema supports it, UI doesn't yet).
- Listing/searching past sessions and reports.
- Export report as PDF or Excel.
