# Ciptronic Validator — Unified Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the complete Ciptronic Validator web app — a local Romanian application with **two parallel flows** for validating personalized products: a text-based flow (Discovery + Inspector agents producing a Conform/Neconform/Nevizibil report) and an image-based flow (Image Match reusing the existing engine to produce a tabular comparison report). Landing page is a chooser between the two.

**Architecture:** Python 3.10 + FastAPI + HTMX + Jinja2 + SQLite + Anthropic Claude Sonnet 4.6. Pure-function agents (Discovery, Inspector), thin LLM client wrapper, SQLite repository with three tables (`discovery_sessions`, `validation_reports`, `match_sessions`). The existing `image_matcher/` package (engine + Streamlit) stays untouched; the web app imports `image_matcher.engine` as a library. Two-flow chooser at landing; flows never merge in MVP.

**Tech Stack:** Python 3.10+, FastAPI, HTMX, Jinja2, SQLite, anthropic SDK (Claude Sonnet 4.6), pytest, pytest-asyncio, httpx.

**Supersedes:** [2026-05-17-ciptronic-validator.md](2026-05-17-ciptronic-validator.md). The image_matcher engine plan ([2026-05-18-image-match-engine.md](2026-05-18-image-match-engine.md)) remains the source of record for the already-implemented Section 0; that work is referenced here as DONE.

**Working directory:** `C:\Users\40747\OneDrive\Documents\Jetson Nano\ciptronic_validator` (treat as project root in all commands).

**Mockups for reference:** see [docs/mockups/](../../mockups/) for the visual design system (Lora + Inter fonts, green CTA, two-flow chooser layout). Templates in this plan reuse the styles defined there.

---

## Status

| Section | Scope | Status |
|---|---|---|
| 0 | Image Match engine (`image_matcher/`) | ✓ DONE (per 2026-05-18 plan) |
| 1–6 | Project scaffolding, DB, schemas, LLM client, Discovery + Inspector agents | TODO |
| 7 | FastAPI scaffolding + two-flow chooser landing | TODO |
| 8 | Discovery web flow (Flow A web routes) | TODO |
| 9 | Inspector web flow (Flow A web routes) | TODO |
| 10 | Match web flow (Flow B web routes) | TODO |
| 11 | README + manual smoke test + tag | TODO |

---

## Section 0: Image Match Engine — ✓ DONE

Reference only. Do NOT re-execute. The folder `image_matcher/` is committed on branch `feat/image-matcher` and contains:

| Module | Purpose |
|---|---|
| `image_matcher/engine.py` | Pure functions + single I/O wrapper: `find_pairs`, `encode_image`, `build_sim_messages`, `parse_sim_response`, `build_compare_messages`, `parse_compare_response`, `render_table`, `call_llm`, `analyze_sim`, `compare_real`, `process_pair` |
| `image_matcher/app.py` | Standalone Streamlit UI consuming `process_pair`. Reused as a dev/debug tool (separate port from FastAPI). |
| `image_matcher/tests/` | 42 unit tests, all green. |
| `image_matcher/run.py` | CLI runner for batch processing pairs in a folder. |

Key public functions used by Section 10:

```python
# from image_matcher.engine
analyze_sim(sim_path: Path, model: str = "claude-sonnet-4-6") -> dict
# returns: {"criteria": [{"id": "...", "label": "...", "description": "...", "details": {...}}, ...]}

compare_real(real_path: Path, sim_report: dict, model: str = "claude-sonnet-4-6", max_tokens: int = 8192) -> dict
# returns: {"rows": [{"criterion": "...", "sim_value": "...", "real_value": "...", "match": bool, "match_type": "exact|partial|missing|extra", "confidence": "low|medium|high", "note": "..."}, ...], "summary": {...}}
```

The compare flow uses `max_tokens=8192` (set in image_matcher's CLI; we mirror this in Section 10).

---

## Task 1: Project scaffolding

Create the folder structure, dependency list, gitignore, env template, README skeleton, .claude permissions. This task does **not** add application code beyond what `image_matcher/` already provides — it sets up the rest of the package skeleton.

**Files:**
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Create: `.env.example`
- Modify: `README.md` (skeleton only; full version in Task 11)
- Create: `.claude/settings.local.json` (if not exists)
- Create: `agents/__init__.py` (empty)
- Create: `db/__init__.py` (empty)
- Create: `schemas/__init__.py` (empty)
- Create: `web/__init__.py` (empty)
- Create: `tests/__init__.py` (empty)
- Create: `tests/unit/__init__.py` (empty)
- Create: `tests/integration/__init__.py` (empty)
- Create: `tests/e2e/__init__.py` (empty)
- Create: `prompts/.gitkeep`
- Create: `tests/fixtures/.gitkeep`
- Create: `main.py` (empty)

- [ ] **Step 1: Update `requirements.txt`** (keep existing `anthropic`, `streamlit`, etc. from image_matcher)

```
fastapi>=0.110
uvicorn[standard]>=0.27
jinja2>=3.1
python-multipart>=0.0.9
anthropic>=0.34
python-dotenv>=1.0
streamlit>=1.30
pytest>=8.0
pytest-asyncio>=0.23
httpx>=0.27
```

If a `requirements.txt` already exists from image_matcher, ensure all of the above are present (add missing lines, do not delete existing pins).

- [ ] **Step 2: Update `.gitignore`** (preserve existing image_matcher entries)

Ensure these entries exist (add any missing):

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

# image_matcher runtime output (already gitignored, kept for clarity)
image_matcher/output/
image_matcher/input/

# Test fixtures
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
UPLOADS_DIR=./uploads
```

- [ ] **Step 4: Create `README.md` skeleton** (full version comes in Task 11)

```markdown
# Ciptronic Product Validator

Aplicație web locală pentru specificarea și validarea vizuală a produselor personalizate.

Două fluxuri paralele:
1. **Discovery + Inspector** (text) — descriere → JSON → raport pe 3 zone.
2. **Image Match** (imagine) — mockup → criterii → raport tabelar.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# editează .env
```

## Run

```bash
.venv\Scripts\uvicorn.exe main:app --reload
```

Open http://localhost:8000.

## Spec & plan

- [Implementation plan](docs/superpowers/plans/2026-05-27-ciptronic-validator-unified.md)
- [Mockups](docs/mockups/_index.html)
```

- [ ] **Step 5: Create `.claude/settings.local.json` (if not exists)**

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

Create as empty files:
- `agents/__init__.py`
- `db/__init__.py`
- `schemas/__init__.py`
- `web/__init__.py`
- `tests/__init__.py`
- `tests/unit/__init__.py`
- `tests/integration/__init__.py`
- `tests/e2e/__init__.py`
- `main.py`

Create `prompts/.gitkeep` and `tests/fixtures/.gitkeep`.

- [ ] **Step 7: Ensure venv exists and install dependencies**

```bash
python -m venv .venv      # skip if .venv/ already exists
.venv\Scripts\pip.exe install -r requirements.txt
```

Expected: pip installs all packages without errors.

- [ ] **Step 8: Sanity-check pytest discovers nothing yet**

```bash
.venv\Scripts\pytest.exe --collect-only tests/
```

Expected: 0 tests collected from `tests/` (image_matcher tests are in `image_matcher/tests/` and use a separate collection root — leave them alone).

- [ ] **Step 9: Commit**

```bash
git add requirements.txt .gitignore .env.example README.md .claude/settings.local.json agents/__init__.py db/__init__.py schemas/__init__.py web/__init__.py tests/__init__.py tests/unit/__init__.py tests/integration/__init__.py tests/e2e/__init__.py prompts/.gitkeep tests/fixtures/.gitkeep main.py
git commit -m "feat: project scaffolding for unified Ciptronic Validator (FastAPI + HTMX + agents)"
```

---

## Task 2: SQLite schema + repository (three tables)

Data layer. Three tables: `discovery_sessions` (Flow A), `validation_reports` (Flow A reports), `match_sessions` (Flow B sessions + reports — combined since image_matcher returns a single doc).

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

CREATE TABLE IF NOT EXISTS match_sessions (
    id                  TEXT PRIMARY KEY,
    sim_image_path      TEXT NOT NULL,
    real_image_path     TEXT,
    sim_report_json     TEXT NOT NULL,
    compare_report_json TEXT,
    status              TEXT NOT NULL
                        CHECK (status IN ('awaiting_real', 'complete', 'failed')),
    created_at          TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at        TEXT
);

CREATE INDEX IF NOT EXISTS idx_match_status
    ON match_sessions(status);
```

- [ ] **Step 2: Create `tests/conftest.py` with the shared `conn` fixture**

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

- [ ] **Step 3: Write failing tests for `create_session` / `get_session`**

Create `tests/unit/test_repository.py`:

```python
import json

from db import repository


def test_create_session_returns_uuid_and_persists(conn):
    sid = repository.create_session(conn, product_type="tricou", description="tricou navy cu logo")
    assert isinstance(sid, str) and len(sid) == 36

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

- [ ] **Step 4: Run tests — expect FAIL** (`repository.py` empty)

```bash
.venv\Scripts\pytest.exe tests/unit/test_repository.py -v
```

- [ ] **Step 5: Implement `create_session` and `get_session` in `db/repository.py`**

```python
import json
import sqlite3
import uuid


def create_session(conn: sqlite3.Connection, product_type: str, description: str) -> str:
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
    cur = conn.execute("SELECT * FROM discovery_sessions WHERE id = ?", (session_id,))
    return cur.fetchone()
```

- [ ] **Step 6: Run tests — expect PASS**

- [ ] **Step 7: Write failing tests for `update_session_state` / `finalize_session`**

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

- [ ] **Step 8: Run — expect FAIL**

- [ ] **Step 9: Implement both functions in `db/repository.py`**

```python
def update_session_state(conn: sqlite3.Connection, session_id: str,
                         state: dict, history: list, rounds: int) -> None:
    conn.execute(
        """
        UPDATE discovery_sessions
        SET state_json = ?, history_json = ?, rounds_used = ?
        WHERE id = ?
        """,
        (json.dumps(state, ensure_ascii=False),
         json.dumps(history, ensure_ascii=False),
         rounds, session_id),
    )
    conn.commit()


def finalize_session(conn: sqlite3.Connection, session_id: str) -> None:
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

- [ ] **Step 10: Run — expect PASS**

- [ ] **Step 11: Write failing tests for `save_report` / `get_report`**

```python
def test_save_report_returns_uuid_and_persists_all_fields(conn):
    sid = repository.create_session(conn, "tricou", "tricou navy")
    spec = {"culoare_principala": "navy"}
    image_paths = ["uploads/abc/img1.jpg"]
    conform = [{"camp": "culoare_principala", "valoare_asteptata": "navy",
                "valoare_observata": "navy", "incredere": "ridicat", "motiv": "vizibil"}]
    neconform, nevizibil = [], []
    raw = '{"conform":[...],"neconform":[],"nevizibil":[]}'

    rid = repository.save_report(conn, sid, spec, image_paths, conform, neconform, nevizibil, raw)
    assert len(rid) == 36

    row = repository.get_report(conn, rid)
    assert row["session_id"] == sid
    assert json.loads(row["spec_json"]) == spec
    assert json.loads(row["image_paths_json"]) == image_paths
    assert json.loads(row["conform_json"]) == conform


def test_get_report_returns_none_when_missing(conn):
    assert repository.get_report(conn, "no-such-id") is None
```

- [ ] **Step 12: Run — expect FAIL**

- [ ] **Step 13: Implement `save_report` / `get_report`**

```python
def save_report(conn: sqlite3.Connection, session_id: str, spec: dict, image_paths: list,
                conform: list, neconform: list, nevizibil: list, raw: str) -> str:
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
    cur = conn.execute("SELECT * FROM validation_reports WHERE id = ?", (report_id,))
    return cur.fetchone()
```

- [ ] **Step 14: Run — expect PASS** (4 Flow-A tests green)

- [ ] **Step 15: Write failing tests for `match_sessions` CRUD**

```python
def test_create_match_session_returns_uuid_and_persists(conn):
    mid = repository.create_match_session(
        conn,
        sim_image_path="uploads/match/abc/sim.png",
        sim_report={"criteria": [{"id": "color", "label": "Color", "description": "navy"}]},
    )
    assert len(mid) == 36

    row = repository.get_match_session(conn, mid)
    assert row["sim_image_path"] == "uploads/match/abc/sim.png"
    assert row["real_image_path"] is None
    assert row["status"] == "awaiting_real"
    assert json.loads(row["sim_report_json"])["criteria"][0]["id"] == "color"
    assert row["compare_report_json"] is None


def test_get_match_session_returns_none_when_missing(conn):
    assert repository.get_match_session(conn, "no-such-id") is None


def test_update_match_compare_report_sets_real_path_status_and_report(conn):
    mid = repository.create_match_session(
        conn, sim_image_path="x/sim.png", sim_report={"criteria": []}
    )
    compare = {"rows": [{"criterion": "color", "match": True}], "summary": {"matched": 1}}
    repository.update_match_compare_report(
        conn, mid, real_image_path="x/real.png", compare_report=compare,
    )
    row = repository.get_match_session(conn, mid)
    assert row["real_image_path"] == "x/real.png"
    assert row["status"] == "complete"
    assert row["completed_at"] is not None
    assert json.loads(row["compare_report_json"]) == compare


def test_fail_match_session_sets_status(conn):
    mid = repository.create_match_session(
        conn, sim_image_path="x/sim.png", sim_report={"criteria": []}
    )
    repository.fail_match_session(conn, mid)
    row = repository.get_match_session(conn, mid)
    assert row["status"] == "failed"
```

- [ ] **Step 16: Run — expect FAIL** (functions don't exist)

- [ ] **Step 17: Implement match_session functions**

Append to `db/repository.py`:

```python
def create_match_session(conn: sqlite3.Connection, sim_image_path: str, sim_report: dict) -> str:
    mid = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO match_sessions
            (id, sim_image_path, sim_report_json, status)
        VALUES (?, ?, ?, 'awaiting_real')
        """,
        (mid, sim_image_path, json.dumps(sim_report, ensure_ascii=False)),
    )
    conn.commit()
    return mid


def get_match_session(conn: sqlite3.Connection, match_id: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM match_sessions WHERE id = ?", (match_id,))
    return cur.fetchone()


def update_match_compare_report(conn: sqlite3.Connection, match_id: str,
                                real_image_path: str, compare_report: dict) -> None:
    conn.execute(
        """
        UPDATE match_sessions
        SET real_image_path = ?, compare_report_json = ?,
            status = 'complete', completed_at = datetime('now')
        WHERE id = ?
        """,
        (real_image_path,
         json.dumps(compare_report, ensure_ascii=False),
         match_id),
    )
    conn.commit()


def fail_match_session(conn: sqlite3.Connection, match_id: str) -> None:
    conn.execute(
        "UPDATE match_sessions SET status = 'failed' WHERE id = ?",
        (match_id,),
    )
    conn.commit()
```

- [ ] **Step 18: Run all repository tests — expect PASS** (8 tests green)

- [ ] **Step 19: Commit**

```bash
git add db/schema.sql db/repository.py tests/conftest.py tests/unit/test_repository.py
git commit -m "feat: SQLite schema (3 tables) and repository functions for both flows"
```

---

## Task 3: Schema loader + tricou.json

Product schemas live as JSON files in `schemas/`. The loader provides utilities for leaf keys and applicability-based filtering. Used only by Flow A (Discovery + Inspector).

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
    { "key": "culoare_principala", "label": "Culoare principală",
      "hint": "ex: roșu, negru, alb melange" },
    { "key": "material", "label": "Material",
      "hint": "ex: bumbac 100%, poliester, mix" },
    { "key": "croiala", "label": "Croială",
      "hint": "regular / slim / oversize" },
    { "key": "guler", "label": "Tip guler",
      "hint": "rotund / V / polo" },
    { "key": "maneci", "label": "Mâneci",
      "hint": "scurte / lungi / 3/4" },
    {
      "key": "branding", "label": "Branding (logo/print/imprimeu)",
      "type": "object",
      "allow_none_value": "fără branding",
      "subfields": [
        { "key": "pozitie", "label": "Poziție",
          "hint": "ex: piept stâng, spate centru" },
        { "key": "tehnica", "label": "Tehnică",
          "hint": "serigrafie / broderie / DTF / sublimare" },
        { "key": "culori", "label": "Culori", "type": "list" },
        { "key": "dimensiuni_aproximative", "label": "Dimensiuni aproximative",
          "hint": "ex: 10cm x 10cm" }
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
        "culoare_principala", "material", "croiala", "guler", "maneci",
        "branding.pozitie", "branding.tehnica", "branding.culori",
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
    assert keys == [
        "culoare_principala", "material", "croiala", "guler", "maneci",
        "branding.pozitie",
    ]


def test_empty_state_for_schema_initializes_branding_subobject():
    schema = loader.load_schema("tricou")
    state = loader.empty_state(schema)
    assert state["culoare_principala"] is None
    assert state["branding"]["pozitie"] is None
    assert state["branding"]["culori"] == []
```

- [ ] **Step 3: Run — expect FAIL**

- [ ] **Step 4: Implement `schemas/loader.py`**

```python
import json
from pathlib import Path


SCHEMAS_DIR = Path(__file__).parent


def available_product_types() -> list[str]:
    return sorted(p.stem for p in SCHEMAS_DIR.glob("*.json"))


def load_schema(product_type: str) -> dict:
    path = SCHEMAS_DIR / f"{product_type}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def leaf_keys(schema: dict) -> list[str]:
    out: list[str] = []
    for field in schema["fields"]:
        if field.get("type") == "object":
            for sub in field["subfields"]:
                out.append(f"{field['key']}.{sub['key']}")
        else:
            out.append(field["key"])
    return out


def applicable_leaf_keys(schema: dict, state: dict) -> list[str]:
    out: list[str] = []
    for field in schema["fields"]:
        if field.get("type") == "object":
            parent_state = state.get(field["key"]) or {}
            none_marker = field.get("allow_none_value")
            first_sub_key = field["subfields"][0]["key"]
            first_sub_value = parent_state.get(first_sub_key)
            if none_marker is not None and first_sub_value == none_marker:
                out.append(f"{field['key']}.{first_sub_key}")
            else:
                for sub in field["subfields"]:
                    out.append(f"{field['key']}.{sub['key']}")
        else:
            out.append(field["key"])
    return out


def empty_state(schema: dict) -> dict:
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

- [ ] **Step 5: Run — expect PASS** (7 tests green)

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
    """Thin wrapper around anthropic.Anthropic. Reads ANTHROPIC_API_KEY from env."""

    model: str = DEFAULT_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS

    def __post_init__(self) -> None:
        self._client = anthropic.Anthropic()

    def complete_text(self, system: str, user: str) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return _extract_text(resp)

    def complete_vision(self, system: str, content_blocks: list[dict[str, Any]]) -> str:
        resp = self._client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=[{"role": "user", "content": content_blocks}],
        )
        return _extract_text(resp)


def _extract_text(response: Any) -> str:
    parts = []
    for block in response.content:
        if block.type == "text":
            parts.append(block.text)
    return "".join(parts)
```

- [ ] **Step 2: Create real-API smoke test (skipped without key)**

Create `tests/integration/test_llm_client.py`:

```python
import os

import pytest

from agents.llm_client import LLMClient


pytestmark = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
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

- [ ] **Step 3: Run integration test**

```bash
.venv\Scripts\pytest.exe tests/integration/test_llm_client.py -v
```

Expected: PASS or SKIPPED depending on API key. Either is green.

- [ ] **Step 4: Run all tests so far**

```bash
.venv\Scripts\pytest.exe -v tests/
```

Expected: ~18 PASSED, 0-1 SKIPPED.

- [ ] **Step 5: Commit**

```bash
git add agents/llm_client.py tests/integration/test_llm_client.py
git commit -m "feat: thin Anthropic SDK wrapper (text + vision) with integration smoke test"
```

---

## Task 5: Discovery agent

Pure functions: `build_messages`, `parse_response`, `is_schema_complete`, `merge_answers`. Prompt template lives in `prompts/discovery.md`.

**Files:**
- Create: `prompts/discovery.md`
- Create: `agents/discovery.py`
- Create: `tests/unit/test_discovery.py`
- Create: `tests/fixtures/llm_responses/discovery_round1.json`
- Create: `tests/fixtures/llm_responses/discovery_round2_done.json`
- Create: `tests/fixtures/llm_responses/discovery_invalid.txt`

- [ ] **Step 1: Create `prompts/discovery.md`**

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

\`\`\`json
{
  "state": { /* schema completată parțial cu valorile cunoscute */ },
  "intrebari": [
    { "id": "<cheia câmpului sau cheia.subcheia>",
      "text": "<întrebarea în română>",
      "variante": ["<opțiune1>", "<opțiune2>"] }
  ],
  "done": <true|false>
}
\`\`\`

Pentru sub-câmpuri de branding, `id` este `branding.pozitie`, etc.
Câmpul `variante` e opțional.

Când `done: true`, lista `intrebari` e goală.
```

- [ ] **Step 2: Create fixture `tests/fixtures/llm_responses/discovery_round1.json`**

```json
{
  "state": {
    "culoare_principala": "albastru navy",
    "material": null, "croiala": null, "guler": null, "maneci": null,
    "branding": {
      "pozitie": "piept stâng", "tehnica": null,
      "culori": [], "dimensiuni_aproximative": null
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
    "culoare_principala": "albastru navy", "material": "bumbac 100%",
    "croiala": "slim", "guler": "rotund", "maneci": "scurte",
    "branding": {
      "pozitie": "piept stâng", "tehnica": "serigrafie",
      "culori": ["alb"], "dimensiuni_aproximative": "10cm x 10cm"
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

- [ ] **Step 6: Run — expect FAIL**

- [ ] **Step 7: Implement `parse_response` and `DiscoveryStep` in `agents/discovery.py`**

```python
import json
from dataclasses import dataclass


@dataclass
class DiscoveryStep:
    state: dict
    intrebari: list[dict]
    done: bool


def parse_response(text: str) -> DiscoveryStep:
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

    return DiscoveryStep(state=data["state"], intrebari=data["intrebari"], done=data["done"])
```

- [ ] **Step 8: Run — expect PASS**

- [ ] **Step 9: Write failing tests for `is_schema_complete`**

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

- [ ] **Step 10: Run — expect FAIL**

- [ ] **Step 11: Implement `is_schema_complete`**

```python
from schemas import loader


def is_schema_complete(schema: dict, state: dict) -> tuple[bool, list[str]]:
    applicable = loader.applicable_leaf_keys(schema, state)
    missing: list[str] = []
    for key in applicable:
        value = _read_dotted(state, key)
        if value is None or value == "" or value == []:
            missing.append(key)
    return (len(missing) == 0, missing)


def _read_dotted(state: dict, dotted_key: str):
    parts = dotted_key.split(".")
    cur = state
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur
```

- [ ] **Step 12: Run — expect PASS**

- [ ] **Step 13: Write failing tests for `merge_answers`**

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
    assert state["material"] is None
    assert new_state["material"] == "bumbac"
```

- [ ] **Step 14: Run — expect FAIL**

- [ ] **Step 15: Implement `merge_answers`**

```python
import copy


def merge_answers(state: dict, answers: dict) -> dict:
    new_state = copy.deepcopy(state)
    for key, value in answers.items():
        _write_dotted(new_state, key, value)
    return new_state


def _write_dotted(state: dict, dotted_key: str, value) -> None:
    parts = dotted_key.split(".")
    cur = state
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value
```

- [ ] **Step 16: Run — expect PASS**

- [ ] **Step 17: Write failing test for `build_messages`**

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

- [ ] **Step 18: Run — expect FAIL**

- [ ] **Step 19: Implement `build_messages`**

```python
from pathlib import Path


PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "discovery.md"


def build_messages(schema: dict, initial_description: str,
                   state: dict, history: list) -> tuple[str, str]:
    system = PROMPT_PATH.read_text(encoding="utf-8")
    user = json.dumps({
        "schema": schema,
        "initial_description": initial_description,
        "current_state": state,
        "history": history,
    }, ensure_ascii=False, indent=2)
    return system, user
```

- [ ] **Step 20: Run all discovery tests — expect PASS** (10 tests green)

- [ ] **Step 21: Commit**

```bash
git add prompts/discovery.md agents/discovery.py tests/unit/test_discovery.py tests/fixtures/llm_responses/discovery_round1.json tests/fixtures/llm_responses/discovery_round2_done.json tests/fixtures/llm_responses/discovery_invalid.txt
git commit -m "feat: Discovery agent (build_messages, parse_response, is_complete, merge)"
```

---

## Task 6: Inspector agent

Pure functions: `build_messages` (base64 images) and `parse_report` (strict validation that each applicable field appears exactly once).

**Files:**
- Create: `prompts/inspector.md`
- Create: `agents/inspector.py`
- Create: `tests/unit/test_inspector.py`
- Create: `tests/fixtures/llm_responses/inspector_full.json`
- Create: `tests/fixtures/llm_responses/inspector_missing_field.json`
- Create: `tests/fixtures/llm_responses/inspector_fara_branding.json`
- Create: `tests/fixtures/images/README.md`

- [ ] **Step 1: Create `prompts/inspector.md`**

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
4. Pentru fiecare câmp, motivul trebuie să fie concret și verificabil.
5. Confidence: `scăzut` = indicii indirecte; `mediu` = vizibil dar nu optim;
   `ridicat` = clar vizibil și fără ambiguitate.

## Reguli structurale

6. Fiecare câmp-frunză aplicabil al schemei apare EXACT O DATĂ într-una
   din cele trei liste: `conform`, `neconform`, `nevizibil`.
7. Pentru `branding` activ (cu valori non-null), raportezi toate cele 4
   sub-câmpuri.
8. Pentru `branding` marcat "fără branding", raportezi DOAR `branding.pozitie`
   (verifici că pozele NU arată niciun logo/print). Celelalte 3 sub-câmpuri
   nu se raportează. Apariția neașteptată a unui branding = neconform pe
   `branding.pozitie`.
9. Toate textele răspunsului sunt în limba română.

## Output

\`\`\`json
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
\`\`\`
```

- [ ] **Step 2: Create fixture `tests/fixtures/llm_responses/inspector_full.json`**

```json
{
  "conform": [
    { "camp": "culoare_principala", "valoare_asteptata": "albastru navy",
      "valoare_observata": "albastru navy", "incredere": "ridicat",
      "motiv": "culoarea e clar vizibilă în pozele 1 și 2" },
    { "camp": "croiala", "valoare_asteptata": "slim",
      "valoare_observata": "slim", "incredere": "ridicat",
      "motiv": "fitting strâns vizibil în poza 1" },
    { "camp": "guler", "valoare_asteptata": "rotund",
      "valoare_observata": "rotund", "incredere": "ridicat",
      "motiv": "guler rotund clasic în poza 1" },
    { "camp": "maneci", "valoare_asteptata": "scurte",
      "valoare_observata": "scurte", "incredere": "ridicat",
      "motiv": "mâneci scurte clar vizibile" },
    { "camp": "branding.pozitie", "valoare_asteptata": "piept stâng",
      "valoare_observata": "piept stâng", "incredere": "ridicat",
      "motiv": "logo pe piept stâng, poza 1" },
    { "camp": "branding.culori", "valoare_asteptata": ["alb"],
      "valoare_observata": "alb", "incredere": "ridicat",
      "motiv": "logo alb pe fond navy" }
  ],
  "neconform": [
    { "camp": "branding.tehnica", "valoare_asteptata": "serigrafie",
      "valoare_observata": "pare DTF", "incredere": "mediu",
      "motiv": "în poza 3 logo-ul are textură ridicată caracteristică DTF" }
  ],
  "nevizibil": [
    { "camp": "material", "valoare_asteptata": "bumbac 100%",
      "motiv": "țesătura nu apare în closeup în niciuna dintre poze" },
    { "camp": "branding.dimensiuni_aproximative", "valoare_asteptata": "10cm x 10cm",
      "motiv": "nicio referință de scară în poze" }
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
    { "camp": "branding.culori", "valoare_asteptata": ["alb"], "motiv": "neclară" },
    { "camp": "branding.dimensiuni_aproximative", "valoare_asteptata": "10cm",
      "motiv": "neclară" }
  ]
}
```

(Note: `material` intentionally missing to test the validator.)

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
      "motiv": "nu apare niciun logo în poze" }
  ],
  "neconform": [],
  "nevizibil": [
    { "camp": "material", "valoare_asteptata": "bumbac 100%",
      "motiv": "țesătura nu apare în closeup" }
  ]
}
```

- [ ] **Step 5: Create `tests/fixtures/images/README.md`**

```markdown
# Test fixture images

Gitignored. Provide local files for manual smoke tests:
- `tricou_navy_serigrafie.jpg` — front shot of a navy slim t-shirt, white logo on left chest.
- `tricou_navy_back.jpg` — back view.
- Optional: any other product photos.

Resolution ≥ 800x600.
```

- [ ] **Step 6: Write failing tests for `parse_report`**

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
        "culoare_principala": "albastru navy", "material": "bumbac 100%",
        "croiala": "slim", "guler": "rotund", "maneci": "scurte",
        "branding": {
            "pozitie": "piept stâng", "tehnica": "serigrafie",
            "culori": ["alb"], "dimensiuni_aproximative": "10cm x 10cm",
        },
    }


@pytest.fixture
def spec_fara_branding():
    return {
        "culoare_principala": "albastru navy", "material": "bumbac 100%",
        "croiala": "slim", "guler": "rotund", "maneci": "scurte",
        "branding": {
            "pozitie": "fără branding", "tehnica": None,
            "culori": [], "dimensiuni_aproximative": None,
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
    assert len(all_camps) == 9 and len(set(all_camps)) == 9


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

- [ ] **Step 7: Run — expect FAIL**

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
    valoare_observata: object | None
    incredere: Incredere | None
    motiv: str


@dataclass
class ValidationReport:
    conform: list[ValidationItem] = field(default_factory=list)
    neconform: list[ValidationItem] = field(default_factory=list)
    nevizibil: list[ValidationItem] = field(default_factory=list)


def parse_report(text: str, schema: dict, spec: dict) -> ValidationReport:
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
    reported = {i.camp for i in conform} | {i.camp for i in neconform} | {i.camp for i in nevizibil}
    missing = applicable - reported
    extra = reported - applicable
    if missing:
        raise ValueError(f"Câmpuri lipsă din raport: {sorted(missing)}")
    if extra:
        raise ValueError(f"Câmpuri neașteptate în raport: {sorted(extra)}")

    total = len(conform) + len(neconform) + len(nevizibil)
    if total != len(applicable):
        raise ValueError(f"Fiecare câmp trebuie raportat exact o dată. Raportate: {total}, așteptate: {len(applicable)}")

    return ValidationReport(conform=conform, neconform=neconform, nevizibil=nevizibil)


def _parse_item(raw: dict, in_nevizibil: bool) -> ValidationItem:
    if "camp" not in raw or "valoare_asteptata" not in raw:
        raise ValueError(f"Item incomplet: {raw}")
    if not raw.get("motiv"):
        raise ValueError(f"motiv lipsă pentru {raw.get('camp')}")

    if in_nevizibil:
        return ValidationItem(
            camp=raw["camp"], valoare_asteptata=raw["valoare_asteptata"],
            valoare_observata=None, incredere=None, motiv=raw["motiv"],
        )

    incredere = raw.get("incredere")
    if incredere not in ALLOWED_INCREDERE:
        raise ValueError(f"incredere invalidă pentru {raw['camp']}: '{incredere}' (permise: {sorted(ALLOWED_INCREDERE)})")
    if "valoare_observata" not in raw:
        raise ValueError(f"valoare_observata lipsă pentru {raw['camp']}")

    return ValidationItem(
        camp=raw["camp"], valoare_asteptata=raw["valoare_asteptata"],
        valoare_observata=raw["valoare_observata"], incredere=incredere,
        motiv=raw["motiv"],
    )
```

- [ ] **Step 9: Run — expect PASS** (4 parser tests green)

- [ ] **Step 10: Write failing test for `build_messages` with image encoding**

Append to `tests/unit/test_inspector.py`:

```python
import base64


def _write_tiny_jpeg(path: Path) -> None:
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
    assert content_blocks[0]["type"] == "image"
    assert content_blocks[0]["source"]["type"] == "base64"
    assert content_blocks[0]["source"]["media_type"] == "image/jpeg"
    text_block = content_blocks[-1]
    assert text_block["type"] == "text"
    assert "culoare_principala" in text_block["text"]


def test_build_messages_handles_multiple_images(tmp_path, spec_active_branding):
    img1 = tmp_path / "img1.jpg"
    img2 = tmp_path / "img2.jpg"
    _write_tiny_jpeg(img1)
    _write_tiny_jpeg(img2)

    _, content_blocks = inspector.build_messages(
        spec=spec_active_branding, image_paths=[str(img1), str(img2)],
    )
    image_blocks = [b for b in content_blocks if b["type"] == "image"]
    assert len(image_blocks) == 2
```

- [ ] **Step 11: Run — expect FAIL**

- [ ] **Step 12: Implement `build_messages`**

Append to `agents/inspector.py`:

```python
import base64
from pathlib import Path


PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "inspector.md"


def build_messages(spec: dict, image_paths: list[str]) -> tuple[str, list[dict]]:
    system = PROMPT_PATH.read_text(encoding="utf-8")

    blocks: list[dict] = []
    for path in image_paths:
        data = Path(path).read_bytes()
        b64 = base64.standard_b64encode(data).decode("ascii")
        blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": _media_type_for(path), "data": b64},
        })

    spec_text = json.dumps(spec, ensure_ascii=False, indent=2)
    text = (
        f"Specificația produsului (JSON):\n```json\n{spec_text}\n```\n\n"
        f"Pozele atașate: {len(image_paths)} (numerotate 1..{len(image_paths)}).\n\n"
        f"Analizează câmp cu câmp și emite raportul JSON."
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

- [ ] **Step 13: Run all inspector tests — expect PASS** (6 tests green)

- [ ] **Step 14: Commit**

```bash
git add prompts/inspector.md agents/inspector.py tests/unit/test_inspector.py tests/fixtures/llm_responses/inspector_full.json tests/fixtures/llm_responses/inspector_missing_field.json tests/fixtures/llm_responses/inspector_fara_branding.json tests/fixtures/images/README.md
git commit -m "feat: Inspector agent (build_messages with vision, parse_report with strict validation)"
```

---

## Task 7: FastAPI scaffolding + two-flow chooser landing

Create the web layer skeleton: app instance, base template, **chooser landing** (not the old single form), and the new-session form pages.

**Key change from 2026-05-17 plan:** the landing (`GET /`) is now a chooser with two cards. The Flow A form lives at `GET /sessions/new`. The Flow B upload lives at `GET /matches/new`.

**Files:**
- Create: `web/app.py`
- Create: `web/templates/base.html`
- Create: `web/templates/index.html` (chooser)
- Create: `web/templates/sessions_new.html` (Flow A form)
- Create: `web/static/styles.css` (copy from `docs/mockups/styles.css`)
- Create: `main.py`
- Create: `tests/e2e/test_routes.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Copy `docs/mockups/styles.css` to `web/static/styles.css`**

The mockup design system is the production design system. Copy the file verbatim from `docs/mockups/styles.css` into `web/static/styles.css`.

- [ ] **Step 2: Create `web/templates/base.html`**

```html
<!DOCTYPE html>
<html lang="ro">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Ciptronic Product Validator{% endblock %}</title>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
    <link rel="stylesheet" href="/static/styles.css">
</head>
<body>
    <header class="topbar">
        <div class="topbar__inner">
            <a class="brand" href="/">
                <span class="brand__mark">C</span>
                Ciptronic Validator
            </a>
            <span class="topbar__meta">{% block topbar_meta %}{% endblock %}</span>
        </div>
    </header>
    {% block content %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3: Create `web/templates/index.html` (chooser)**

```html
{% extends "base.html" %}
{% block topbar_meta %}v0.2 · MVP local{% endblock %}
{% block content %}
<main class="page page--narrow">
    <h1>Validare produs personalizat</h1>
    <p>
      Alege felul în care vrei să specifici produsul. Ambele rute duc la un raport de
      validare, dar pleacă de la inputuri diferite și produc rapoarte diferite.
    </p>

    <div class="choice-grid">
      <a class="choice-card" href="/sessions/new">
        <span class="choice-card__glyph">Aa</span>
        <h2 class="choice-card__title">Am o descriere</h2>
        <p class="choice-card__desc">
          Pornești de la o descriere în cuvinte. Asistentul îți pune întrebări țintite
          și completează un checklist structurat. La final, validează produsul finit pe
          poze cu un raport <strong>Conform / Neconform / Nevizibil</strong>.
        </p>
        <div class="choice-card__meta">
          <span>Discovery → Inspector</span><span>·</span>
          <span>schemă fixă pe tip produs</span>
        </div>
        <span class="choice-card__cta">Începe specificare <span aria-hidden="true">→</span></span>
      </a>

      <a class="choice-card" href="/matches/new">
        <span class="choice-card__glyph">▣</span>
        <h2 class="choice-card__title">Am un mockup</h2>
        <p class="choice-card__desc">
          Pornești de la o imagine de referință. Sistemul extrage criteriile vizuale
          și le compară cu poza produsului finit, criteriu cu criteriu. Raport sub
          formă de <strong>tabel</strong>.
        </p>
        <div class="choice-card__meta">
          <span>Image Match</span><span>·</span><span>agnostic la tip produs</span>
        </div>
        <span class="choice-card__cta">Încarcă mockup <span aria-hidden="true">→</span></span>
      </a>
    </div>
</main>
{% endblock %}
```

- [ ] **Step 4: Create `web/templates/sessions_new.html` (Flow A form)**

```html
{% extends "base.html" %}
{% block topbar_meta %}Discovery & Inspector · pas 1/3{% endblock %}
{% block content %}
<main class="page page--narrow">
    <h1>Începe o specificare nouă</h1>
    <p>
      Descrie pe scurt produsul comandat de client. Asistentul îți pune întrebări
      țintite (maximum 5 runde) și completează specificația. La final, validezi cu poze.
    </p>

    <form class="card" hx-post="/sessions" hx-swap="none">
        <div class="field">
            <label class="field__label" for="product_type">Tip produs</label>
            <select class="select" id="product_type" name="product_type" required>
                {% for pt in product_types %}
                <option value="{{ pt }}">{{ pt|capitalize }}</option>
                {% endfor %}
            </select>
            <span class="field__hint">Alege tipul; schema specifică ghidează întrebările.</span>
        </div>

        <div class="field">
            <label class="field__label" for="initial_description">Descriere inițială</label>
            <textarea class="textarea" id="initial_description" name="initial_description"
                      required rows="4"
                      placeholder="ex: O bluză cu logo pe piept stâng, culoare navy, mâneci scurte."></textarea>
            <span class="field__hint">Limbajul natural al clientului — nu e nevoie să fie completă.</span>
        </div>

        <div class="row-actions">
            <a href="/" class="btn btn--ghost"><span aria-hidden="true">←</span> Înapoi la alegere flux</a>
            <button type="submit" class="btn btn--primary btn--lg">
                Începe specificare <span aria-hidden="true">→</span>
            </button>
        </div>
    </form>
</main>
{% endblock %}
```

- [ ] **Step 5: Create `main.py`**

```python
from web.app import app

# uvicorn main:app --reload picks up this object.
```

- [ ] **Step 6: Modify `tests/conftest.py` — add FastAPI client fixture**

Append to `tests/conftest.py`:

```python
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
```

- [ ] **Step 7: Write failing E2E tests for landing, sessions form, healthz**

Create `tests/e2e/test_routes.py`:

```python
def test_landing_page_is_chooser(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Am o descriere" in r.text
    assert "Am un mockup" in r.text
    assert "/sessions/new" in r.text
    assert "/matches/new" in r.text


def test_sessions_new_page_renders_form(client):
    r = client.get("/sessions/new")
    assert r.status_code == 200
    assert "Începe o specificare" in r.text
    assert "tricou" in r.text.lower()


def test_healthz(client):
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.text.strip('"') == "ok"
```

- [ ] **Step 8: Run — expect FAIL** (no `web/app.py` yet)

- [ ] **Step 9: Implement `web/app.py` (landing + sessions/new + healthz only)**

POST /sessions and the rest of Flow A are added in Task 8.

```python
import os
import sqlite3
from pathlib import Path
from contextlib import contextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from schemas import loader


BASE_DIR = Path(__file__).parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./ciptronic.db")
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", str(BASE_DIR.parent / "uploads")))
SCHEMA_PATH = BASE_DIR.parent / "db" / "schema.sql"

UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


app = FastAPI(title="Ciptronic Product Validator")
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


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
    return TEMPLATES.TemplateResponse("index.html", {"request": request})


@app.get("/sessions/new", response_class=HTMLResponse)
def sessions_new(request: Request):
    return TEMPLATES.TemplateResponse(
        "sessions_new.html",
        {"request": request, "product_types": loader.available_product_types()},
    )


@app.get("/healthz", response_class=Response)
def healthz():
    return Response(content="ok", media_type="text/plain")
```

- [ ] **Step 10: Run E2E tests — expect PASS** (3 tests green)

- [ ] **Step 11: Manual smoke test — boot the server**

```bash
.venv\Scripts\uvicorn.exe main:app --port 8765
```

Open `http://localhost:8765/`. Verify:
- Chooser landing displays with two cards
- Click "Am o descriere" → `/sessions/new` form displays
- Click "Înapoi la alegere flux" → back to chooser
- Click "Am un mockup" → 404 (Task 10 implements `/matches/new`)
- `/healthz` returns `ok`

Stop with Ctrl+C.

- [ ] **Step 12: Commit**

```bash
git add web/app.py web/templates/base.html web/templates/index.html web/templates/sessions_new.html web/static/styles.css main.py tests/conftest.py tests/e2e/test_routes.py
git commit -m "feat: FastAPI scaffolding, two-flow chooser landing, sessions/new form"
```

---

## Task 8: Discovery web flow

Add Flow A web routes: `POST /sessions` (creates session + runs first round), `GET /sessions/{id}` (view), `POST /sessions/{id}/answer` (HTMX partial swap).

**Files:**
- Modify: `web/app.py`
- Create: `web/templates/session.html`
- Create: `web/templates/_session_body.html`
- Modify: `tests/e2e/test_routes.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Create `web/templates/_session_body.html`** (the HTMX swap target)

```html
<div id="session-body">
    <aside class="card">
        <h2 class="card__title">Stare specificație <small>(Runda {{ rounds_used }} / 5)</small></h2>
        <ul class="checklist">
            {% for entry in field_state %}
            <li>
                <span class="checklist__icon {{ 'checklist__icon--done' if entry.filled else 'checklist__icon--pending' }}">
                    {{ '✓' if entry.filled else '·' }}
                </span>
                <div>
                    <span class="checklist__key">{{ entry.label }}</span>
                    <span class="checklist__value {{ '' if entry.filled else 'checklist__value--empty' }}">
                        {{ entry.display_value if entry.filled else 'nu s-a răspuns încă' }}
                    </span>
                </div>
            </li>
            {% endfor %}
        </ul>
    </aside>

    {% if done %}
    <section class="card">
        <h2 style="font-family: var(--ff-sans); font-size: 18px;">
            Specificare completă <span class="badge badge--success">✓ done</span>
        </h2>
        <div class="callout">
            <strong>Toate câmpurile completate.</strong> Poți continua cu validarea vizuală.
        </div>
        <div class="row-actions" style="justify-content: flex-end;">
            <a class="btn btn--primary btn--lg" href="/sessions/{{ session_id }}/validate">
                Validează cu poze <span aria-hidden="true">→</span>
            </a>
        </div>
    </section>
    {% elif intrebari %}
    <section class="card">
        <h2 style="font-family: var(--ff-sans); font-size: 18px;">Întrebări pentru tine</h2>
        <form hx-post="/sessions/{{ session_id }}/answer"
              hx-target="#session-body" hx-swap="outerHTML">
            {% for q in intrebari %}
            <div class="question">
                <div class="question__id">câmp: {{ q.id }}</div>
                <label class="question__text">{{ q.text }}</label>
                {% if q.variante %}
                    <div class="radio-group" role="radiogroup">
                    {% for v in q.variante %}
                    <label class="radio">
                        <input type="radio" name="answer.{{ q.id }}" value="{{ v }}" required>
                        {{ v }}
                    </label>
                    {% endfor %}
                    </div>
                {% else %}
                    <input class="input" type="text" name="answer.{{ q.id }}" required>
                {% endif %}
            </div>
            {% endfor %}
            <div class="row-actions">
                <span class="muted" style="font-size: 13px;">Răspunde și trimite.</span>
                <button type="submit" class="btn btn--primary">Trimite răspunsurile →</button>
            </div>
        </form>
    </section>
    {% else %}
    <section class="card">
        <div class="callout">
            <strong>Sesiunea s-a închis după 5 runde fără completare totală.</strong>
            Câmpurile rămase nemarcate sunt afișate ca (necunoscut) mai sus.
        </div>
        <div class="row-actions" style="justify-content: flex-end;">
            <a class="btn btn--primary" href="/sessions/{{ session_id }}/validate">
                Continuă către validare →
            </a>
        </div>
    </section>
    {% endif %}
</div>
```

- [ ] **Step 2: Create `web/templates/session.html`**

```html
{% extends "base.html" %}
{% block topbar_meta %}Sesiune <code>{{ session_id[:8] }}</code> · {{ product_type|capitalize }}{% endblock %}
{% block content %}
<main class="page page--wide">
    <h1>Specificare {{ product_type }}</h1>
    <p class="muted" style="margin-bottom: var(--s-6);">
        Descriere inițială: <em>„{{ initial_description }}"</em>
    </p>
    <section class="discovery">
        {% include "_session_body.html" %}
    </section>
</main>
{% endblock %}
```

- [ ] **Step 3: Modify `tests/conftest.py` — add `_FakeLLM` and `fake_llm` fixture**

Append to `tests/conftest.py`:

```python
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
```

- [ ] **Step 4: Add Discovery flow tests**

Append to `tests/e2e/test_routes.py`:

```python
from pathlib import Path

FIXTURES = Path(__file__).parent.parent / "fixtures" / "llm_responses"


def _create_session(client, fake_llm):
    fake_llm.queue_text((FIXTURES / "discovery_round1.json").read_text(encoding="utf-8"))
    r = client.post(
        "/sessions",
        data={"product_type": "tricou", "initial_description": "tricou navy cu logo pe piept"},
    )
    return r.headers["HX-Redirect"]


def test_create_session_returns_hx_redirect(client, fake_llm):
    fake_llm.queue_text((FIXTURES / "discovery_round1.json").read_text(encoding="utf-8"))
    r = client.post(
        "/sessions",
        data={"product_type": "tricou", "initial_description": "tricou navy cu logo"},
    )
    assert r.status_code == 200
    assert "HX-Redirect" in r.headers
    assert r.headers["HX-Redirect"].startswith("/sessions/")


def test_get_session_after_creation_shows_partial_state(client, fake_llm):
    url = _create_session(client, fake_llm)
    r = client.get(url)
    assert r.status_code == 200
    assert "albastru navy" in r.text


def test_submit_answers_returns_partial_with_done_when_llm_finishes(client, fake_llm):
    url = _create_session(client, fake_llm)
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
    assert "Specificare completă" in r.text or "done" in r.text
    assert "Validează cu poze" in r.text
```

- [ ] **Step 5: Run — expect FAIL** (routes don't exist)

- [ ] **Step 6: Implement Discovery routes in `web/app.py`**

Add imports at the top of `web/app.py`:

```python
import json
from typing import Any

from fastapi import Form, HTTPException

from agents import discovery
from agents.llm_client import LLMClient
from db import repository
```

Add `MAX_ROUNDS` constant and LLM helper near the top:

```python
MAX_ROUNDS = 5
_llm_singleton: Any = None


def get_llm_client() -> Any:
    """Lazily build a singleton LLMClient. Tests patch this function."""
    global _llm_singleton
    if _llm_singleton is None:
        _llm_singleton = LLMClient()
    return _llm_singleton
```

Append the route handlers and helpers:

```python
@app.post("/sessions")
def create_session(product_type: str = Form(...), initial_description: str = Form(...)):
    schema = loader.load_schema(product_type)
    initial_state = loader.empty_state(schema)

    llm = get_llm_client()
    system, user = discovery.build_messages(
        schema=schema, initial_description=initial_description,
        state=initial_state, history=[],
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
        request=request, session_id=session_id,
        product_type=row["product_type"],
        initial_description=row["initial_description"],
        schema=schema, state=state,
        intrebari=last_questions, rounds_used=row["rounds_used"],
        done=(row["status"] == "complete"),
    )
    return TEMPLATES.TemplateResponse("session.html", ctx)


@app.post("/sessions/{session_id}/answer", response_class=HTMLResponse)
async def submit_answers(session_id: str, request: Request):
    form = await request.form()
    answers = {k[len("answer."):]: v for k, v in form.items() if k.startswith("answer.")}

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
            repository.update_session_state(conn, session_id, merged_state, history, rounds=MAX_ROUNDS)
            repository.finalize_session(conn, session_id)
            ctx = _build_session_context(
                request=request, session_id=session_id,
                product_type=row["product_type"],
                initial_description=row["initial_description"],
                schema=schema, state=merged_state,
                intrebari=[], rounds_used=MAX_ROUNDS, done=True,
            )
            return TEMPLATES.TemplateResponse("_session_body.html", ctx)

        llm = get_llm_client()
        system, user = discovery.build_messages(
            schema=schema, initial_description=row["initial_description"],
            state=merged_state, history=history,
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
            request=request, session_id=session_id,
            product_type=row["product_type"],
            initial_description=row["initial_description"],
            schema=schema, state=step.state,
            intrebari=step.intrebari, rounds_used=next_round, done=is_done,
        )
        return TEMPLATES.TemplateResponse("_session_body.html", ctx)


def _build_session_context(*, request, session_id, product_type, initial_description,
                           schema, state, intrebari, rounds_used, done) -> dict:
    applicable = loader.applicable_leaf_keys(schema, state)
    field_state = []
    for f in schema["fields"]:
        if f.get("type") == "object":
            for sub in f["subfields"]:
                dotted = f"{f['key']}.{sub['key']}"
                if dotted not in applicable:
                    continue
                value = (state.get(f["key"]) or {}).get(sub["key"])
                field_state.append(_field_entry(f"{f['label']} → {sub['label']}", value))
        else:
            field_state.append(_field_entry(f["label"], state.get(f["key"])))

    return {
        "request": request, "session_id": session_id,
        "product_type": product_type, "initial_description": initial_description,
        "field_state": field_state, "intrebari": intrebari,
        "rounds_used": rounds_used, "done": done,
    }


def _field_entry(label: str, value) -> dict:
    filled = value is not None and value != "" and value != []
    display = ", ".join(str(v) for v in value) if isinstance(value, list) else (str(value) if value is not None else "")
    return {"label": label, "filled": filled, "display_value": display}
```

- [ ] **Step 7: Run E2E tests — expect PASS** (6 tests green)

- [ ] **Step 8: Run the full test suite**

```bash
.venv\Scripts\pytest.exe tests/ -v
```

Expected: ~40 PASSED, 0-1 SKIPPED (10 repo + 7 schema + 1 integration + 10 discovery + 6 inspector + 6 e2e).

- [ ] **Step 9: Manual smoke test — Discovery cycle in browser**

Set `ANTHROPIC_API_KEY` in `.env`, run `.venv\Scripts\uvicorn.exe main:app --port 8765`.

Open `http://localhost:8765/` → click "Am o descriere" → enter `tricou navy cu logo pe piept` → submit. Land on session view with state + questions. Submit answers. Verify partial swap.

- [ ] **Step 10: Commit**

```bash
git add web/app.py web/templates/session.html web/templates/_session_body.html tests/conftest.py tests/e2e/test_routes.py
git commit -m "feat: Discovery web flow (session view, answer submit, HTMX partial, 5-round cap)"
```

---

## Task 9: Inspector web flow (upload + report)

Add `GET /sessions/{id}/validate`, `POST /sessions/{id}/validate` (multipart upload + LLM call), `GET /reports/{id}`.

**Files:**
- Modify: `web/app.py`
- Create: `web/templates/validate.html`
- Create: `web/templates/report.html`
- Modify: `tests/e2e/test_routes.py`

- [ ] **Step 1: Create `web/templates/validate.html`**

```html
{% extends "base.html" %}
{% block topbar_meta %}Sesiune <code>{{ session_id[:8] }}</code> · pas 2/3{% endblock %}
{% block content %}
<main class="page">
    <h1>Încarcă pozele produsului</h1>
    <p>Pentru a verifica vizual fiecare câmp, încarcă minim o poză. Recomandăm 2–4 poze.</p>

    <div class="callout" style="margin-bottom: var(--s-5);">
        <strong>Restricții:</strong> JPG / PNG / WEBP · max <strong>5 MB</strong> per poză.
    </div>

    <details class="card" style="margin-bottom: var(--s-4);">
        <summary><strong>Specificație curentă</strong></summary>
        <pre style="overflow:auto;">{{ spec_pretty }}</pre>
    </details>

    <form class="card" action="/sessions/{{ session_id }}/validate" method="post"
          enctype="multipart/form-data">
        <h2 class="card__title">Slot-uri de încărcare</h2>
        <div class="upload-grid">
            <div class="upload-slot">
                <div class="upload-slot__label">
                    <span>Poza 1</span><span class="badge badge--required">obligatoriu</span>
                </div>
                <input type="file" name="image1" accept="image/*" required>
            </div>
            <div class="upload-slot">
                <div class="upload-slot__label">
                    <span>Poza 2</span><span class="badge badge--neutral">opțional</span>
                </div>
                <input type="file" name="image2" accept="image/*">
            </div>
            <div class="upload-slot">
                <div class="upload-slot__label">
                    <span>Poza 3</span><span class="badge badge--neutral">opțional</span>
                </div>
                <input type="file" name="image3" accept="image/*">
            </div>
            <div class="upload-slot">
                <div class="upload-slot__label">
                    <span>Poza 4</span><span class="badge badge--neutral">opțional</span>
                </div>
                <input type="file" name="image4" accept="image/*">
            </div>
        </div>
        <div class="row-actions">
            <a href="/sessions/{{ session_id }}" class="btn btn--ghost">
                <span aria-hidden="true">←</span> Înapoi la specificare
            </a>
            <button type="submit" class="btn btn--primary btn--lg">
                Rulează validarea <span aria-hidden="true">→</span>
            </button>
        </div>
    </form>
</main>
{% endblock %}
```

- [ ] **Step 2: Create `web/templates/report.html`**

```html
{% extends "base.html" %}
{% block topbar_meta %}Raport <code>{{ report_id[:8] }}</code>{% endblock %}
{% block content %}
<main class="page page--wide">
    <h1>Raport validare</h1>
    <p style="margin-bottom: var(--s-6);">
        Total câmpuri raportate: {{ (conform|length) + (neconform|length) + (nevizibil|length) }}.
    </p>

    <section class="report-zone report-zone--conform">
        <header class="report-zone__header">
            <span class="report-zone__icon">✓</span>
            <h2 class="report-zone__title">Conform</h2>
            <span class="report-zone__count">{{ conform|length }}</span>
        </header>
        {% for item in conform %}
        <article class="report-item">
            <div class="report-item__head">
                <span class="report-item__field">{{ item.camp }}</span>
                <span class="badge badge--success">încredere: {{ item.incredere }}</span>
            </div>
            <dl style="margin: 0;">
                <div class="report-item__row"><dt>Așteptat</dt><dd>{{ item.valoare_asteptata }}</dd></div>
                <div class="report-item__row"><dt>Observat</dt><dd>{{ item.valoare_observata }}</dd></div>
            </dl>
            <p class="report-item__reason">{{ item.motiv }}</p>
        </article>
        {% endfor %}
    </section>

    <section class="report-zone report-zone--neconform">
        <header class="report-zone__header">
            <span class="report-zone__icon">✗</span>
            <h2 class="report-zone__title">Neconform</h2>
            <span class="report-zone__count">{{ neconform|length }}</span>
        </header>
        {% for item in neconform %}
        <article class="report-item">
            <div class="report-item__head">
                <span class="report-item__field">{{ item.camp }}</span>
                <span class="badge badge--danger">încredere: {{ item.incredere }}</span>
            </div>
            <dl style="margin: 0;">
                <div class="report-item__row"><dt>Așteptat</dt><dd>{{ item.valoare_asteptata }}</dd></div>
                <div class="report-item__row"><dt>Observat</dt><dd>{{ item.valoare_observata }}</dd></div>
            </dl>
            <p class="report-item__reason">{{ item.motiv }}</p>
        </article>
        {% endfor %}
    </section>

    <section class="report-zone report-zone--nevizibil">
        <header class="report-zone__header">
            <span class="report-zone__icon">?</span>
            <h2 class="report-zone__title">Nevizibil</h2>
            <span class="report-zone__count">{{ nevizibil|length }}</span>
        </header>
        {% for item in nevizibil %}
        <article class="report-item">
            <div class="report-item__head">
                <span class="report-item__field">{{ item.camp }}</span>
            </div>
            <dl style="margin: 0;">
                <div class="report-item__row"><dt>Așteptat</dt><dd>{{ item.valoare_asteptata }}</dd></div>
            </dl>
            <p class="report-item__reason">{{ item.motiv }}</p>
        </article>
        {% endfor %}
    </section>

    <div class="row-actions" style="margin-top: var(--s-6);">
        <a href="/" class="btn btn--secondary">Începe sesiune nouă</a>
    </div>
</main>
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
    fake_llm.queue_text((FIXTURES / "discovery_round2_done.json").read_text(encoding="utf-8"))
    r = client.post(
        "/sessions",
        data={"product_type": "tricou", "initial_description": "tricou navy cu logo"},
    )
    return r.headers["HX-Redirect"].rsplit("/", 1)[-1]


def test_get_validate_page_shows_upload_form(client, fake_llm):
    sid = _complete_session(client, fake_llm)
    r = client.get(f"/sessions/{sid}/validate")
    assert r.status_code == 200
    assert "image1" in r.text


def test_post_validate_runs_inspector_and_redirects_to_report(client, fake_llm):
    sid = _complete_session(client, fake_llm)
    fake_llm.queue_vision((FIXTURES / "inspector_full.json").read_text(encoding="utf-8"))
    files = {"image1": ("front.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    r = client.post(f"/sessions/{sid}/validate", files=files, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["Location"].startswith("/reports/")


def test_report_view_shows_three_zones(client, fake_llm):
    sid = _complete_session(client, fake_llm)
    fake_llm.queue_vision((FIXTURES / "inspector_full.json").read_text(encoding="utf-8"))
    files = {"image1": ("front.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    r = client.post(f"/sessions/{sid}/validate", files=files, follow_redirects=False)
    location = r.headers["Location"]

    r = client.get(location)
    assert r.status_code == 200
    assert "Conform" in r.text
    assert "Neconform" in r.text
    assert "Nevizibil" in r.text
    assert "albastru navy" in r.text
```

- [ ] **Step 4: Run — expect FAIL**

- [ ] **Step 5: Implement Inspector routes in `web/app.py`**

Add to imports:

```python
from fastapi import UploadFile, File
from agents import inspector
```

Add constant:

```python
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
```

Append route handlers:

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
            "request": request, "session_id": session_id,
            "spec_pretty": json.dumps(spec, ensure_ascii=False, indent=2),
        },
    )


@app.post("/sessions/{session_id}/validate")
async def run_validation(
    session_id: str, request: Request,
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
        session_uploads = UPLOADS_DIR / session_id
        session_uploads.mkdir(parents=True, exist_ok=True)
        image_paths: list[str] = []
        for i, f in enumerate(upload_files, start=1):
            content = await f.read()
            if len(content) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(status_code=413, detail=f"Poza {i} depășește 5MB")
            ext = ".png" if f.content_type == "image/png" else ".jpg"
            path = session_uploads / f"img{i}{ext}"
            path.write_bytes(content)
            image_paths.append(str(path))

        llm = get_llm_client()
        system, content_blocks = inspector.build_messages(spec=spec, image_paths=image_paths)
        raw = llm.complete_vision(system=system, content_blocks=content_blocks)
        try:
            report = inspector.parse_report(raw, schema, spec)
        except ValueError as e:
            raise HTTPException(status_code=502, detail=f"Răspuns Inspector invalid: {e}")

        rid = repository.save_report(
            conn, session_id=session_id, spec=spec, image_paths=image_paths,
            conform=[_item_to_dict(i) for i in report.conform],
            neconform=[_item_to_dict(i) for i in report.neconform],
            nevizibil=[_item_to_dict(i) for i in report.nevizibil],
            raw=raw,
        )

    return Response(status_code=303, headers={"Location": f"/reports/{rid}"})


def _item_to_dict(item) -> dict:
    return {
        "camp": item.camp, "valoare_asteptata": item.valoare_asteptata,
        "valoare_observata": item.valoare_observata,
        "incredere": item.incredere, "motiv": item.motiv,
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
            "request": request, "report_id": report_id,
            "conform": json.loads(row["conform_json"]),
            "neconform": json.loads(row["neconform_json"]),
            "nevizibil": json.loads(row["nevizibil_json"]),
        },
    )
```

- [ ] **Step 6: Run E2E tests — expect PASS** (9 tests green: 6 from before + 3 new)

- [ ] **Step 7: Run full suite**

```bash
.venv\Scripts\pytest.exe tests/ -v
```

Expected: ~43 PASSED, 0-1 SKIPPED (40 + 3 inspector e2e tests).

- [ ] **Step 8: Commit**

```bash
git add web/app.py web/templates/validate.html web/templates/report.html tests/e2e/test_routes.py
git commit -m "feat: Inspector web flow (upload form, vision call, report view, three-zone display)"
```

---

## Task 10: Match web flow (Flow B integration with image_matcher)

Wrap the existing `image_matcher.engine` in FastAPI routes. New: `GET /matches/new`, `POST /matches` (upload sim → analyze_sim), `GET /matches/{id}` (criteria + upload real form), `POST /matches/{id}/real` (compare_real), `GET /matches/{id}/report` (tabular report).

**Files:**
- Modify: `web/app.py`
- Create: `web/templates/match_new.html`
- Create: `web/templates/match_wait.html`
- Create: `web/templates/match_report.html`
- Modify: `tests/e2e/test_routes.py`
- Modify: `tests/conftest.py` (add fake for image_matcher engine functions)

- [ ] **Step 1: Create `web/templates/match_new.html`**

```html
{% extends "base.html" %}
{% block topbar_meta %}Image Match · pas 1/3{% endblock %}
{% block content %}
<main class="page page--narrow">
    <h1>Încarcă mockup-ul produsului</h1>
    <p>
        Sistemul va extrage automat criteriile vizuale și le va compara cu poza produsului real.
    </p>

    <div class="callout" style="margin-bottom: var(--s-5);">
        <strong>Acceptăm:</strong> JPG, PNG, WEBP · max <strong>5 MB</strong>.
    </div>

    <form action="/matches" method="post" enctype="multipart/form-data">
        <div class="single-upload">
            <span class="single-upload__glyph">▣</span>
            <p class="single-upload__title">Trage mockup-ul aici</p>
            <p class="single-upload__hint">sau apasă pentru a alege un fișier</p>
            <input type="file" name="sim" accept="image/*" required>
        </div>
        <div class="row-actions">
            <a href="/" class="btn btn--ghost"><span aria-hidden="true">←</span> Înapoi la alegere flux</a>
            <button type="submit" class="btn btn--primary btn--lg">
                Continuă cu mockup-ul <span aria-hidden="true">→</span>
            </button>
        </div>
    </form>

    <p class="muted" style="font-size: 13px; margin-top: var(--s-5); text-align: center;">
        Pasul următor: sistemul analizează mockup-ul cu Claude Sonnet 4.6 vision (5–10 s).
    </p>
</main>
{% endblock %}
```

- [ ] **Step 2: Create `web/templates/match_wait.html`**

```html
{% extends "base.html" %}
{% block topbar_meta %}Match <code>{{ match_id[:8] }}</code> · pas 2/3{% endblock %}
{% block content %}
<main class="page page--wide">
    <h1>Criterii detectate în mockup</h1>
    <p style="margin-bottom: var(--s-5);">
        Sistemul a analizat artwork-ul și a extras
        <strong>{{ criteria|length }} criterii vizuale</strong>.
    </p>

    <div class="discovery">
        <aside class="card">
            <h2 class="card__title">Criterii extrase</h2>
            <ol class="criteria-list">
                {% for c in criteria %}
                <li>
                    <span class="criteria-list__num">{{ loop.index }}</span>
                    <div>
                        <span class="criteria-list__label">{{ c.label }}</span>
                        <span class="criteria-list__desc">{{ c.description }}</span>
                    </div>
                </li>
                {% endfor %}
            </ol>
        </aside>

        <section class="card">
            <h2 style="font-family: var(--ff-sans); font-size: 18px;">
                Adaugă poza produsului real
                <span class="badge badge--info">await real</span>
            </h2>
            <p>O singură poză, frontală, cu produsul finit.</p>

            <form action="/matches/{{ match_id }}/real" method="post" enctype="multipart/form-data">
                <div class="single-upload">
                    <span class="single-upload__glyph">▤</span>
                    <p class="single-upload__title">Trage poza produsului real aici</p>
                    <p class="single-upload__hint">sau apasă pentru a alege un fișier</p>
                    <input type="file" name="real" accept="image/*" required>
                </div>
                <div class="row-actions">
                    <a href="/matches/new" class="btn btn--ghost">
                        <span aria-hidden="true">←</span> Schimbă mockup-ul
                    </a>
                    <button type="submit" class="btn btn--primary btn--lg">
                        Compară cu mockup-ul <span aria-hidden="true">→</span>
                    </button>
                </div>
            </form>
        </section>
    </div>
</main>
{% endblock %}
```

- [ ] **Step 3: Create `web/templates/match_report.html`**

```html
{% extends "base.html" %}
{% block topbar_meta %}Match <code>{{ match_id[:8] }}</code> · pas 3/3{% endblock %}
{% block content %}
<main class="page page--wide">
    <h1>Raport comparație</h1>

    <div class="match-summary">
        <div class="match-summary__chip">
            <div class="match-summary__chip__label">Total criterii</div>
            <div class="match-summary__chip__value">{{ rows|length }}</div>
        </div>
        <div class="match-summary__chip match-summary__chip--match">
            <div class="match-summary__chip__label">Match</div>
            <div class="match-summary__chip__value">{{ summary.matched }}</div>
        </div>
        <div class="match-summary__chip match-summary__chip--mismatch">
            <div class="match-summary__chip__label">Mismatch</div>
            <div class="match-summary__chip__value">{{ summary.mismatched }}</div>
        </div>
    </div>

    <div class="match-table-wrap">
        <table class="match-table">
            <thead>
                <tr>
                    <th style="width: 40px;"></th>
                    <th>Criteriu</th>
                    <th>Sim (mockup)</th>
                    <th>Real (produs)</th>
                    <th style="width: 110px;">Tip</th>
                </tr>
            </thead>
            <tbody>
            {% for row in rows %}
                <tr class="{{ 'is-match' if row.match else 'is-mismatch' }}{{ ' is-extra' if row.match_type == 'extra' else '' }}">
                    <td>
                        {% if row.match %}
                            <span class="match-table__icon match-table__icon--ok">✓</span>
                        {% elif row.match_type == 'extra' %}
                            <span class="match-table__icon match-table__icon--extra">+</span>
                        {% else %}
                            <span class="match-table__icon match-table__icon--bad">✗</span>
                        {% endif %}
                    </td>
                    <td>
                        <div class="match-table__criterion">{{ row.criterion }}</div>
                        {% if row.note %}<div class="match-table__note">{{ row.note }}</div>{% endif %}
                    </td>
                    <td class="match-table__value">{{ row.sim_value or '—' }}</td>
                    <td class="match-table__value">{{ row.real_value or '—' }}</td>
                    <td>
                        {% set badge_class = 'badge--success' if row.match else 'badge--danger' %}
                        {% if row.match_type == 'extra' %}{% set badge_class = 'badge--warn' %}{% endif %}
                        <span class="badge {{ badge_class }}">{{ row.match_type }}</span>
                    </td>
                </tr>
            {% endfor %}
            </tbody>
        </table>
    </div>

    <div class="row-actions" style="margin-top: var(--s-6);">
        <a href="/" class="btn btn--secondary">Începe o nouă validare</a>
    </div>
</main>
{% endblock %}
```

- [ ] **Step 4: Modify `tests/conftest.py` — add `fake_image_engine` fixture**

Append to `tests/conftest.py`:

```python
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

    def fake_compare_real(real_path, sim_report, model="claude-sonnet-4-6", max_tokens=8192):
        _Engine.compare_calls.append((str(real_path), sim_report))
        return _Engine.compare_response

    from web import app as web_app
    monkeypatch.setattr(web_app, "analyze_sim", fake_analyze_sim)
    monkeypatch.setattr(web_app, "compare_real", fake_compare_real)

    return _Engine
```

- [ ] **Step 5: Write failing E2E tests for the Match flow**

Append to `tests/e2e/test_routes.py`:

```python
def test_get_matches_new_shows_upload_form(client):
    r = client.get("/matches/new")
    assert r.status_code == 200
    assert "Încarcă mockup-ul" in r.text
    assert 'name="sim"' in r.text


def test_post_matches_runs_analyze_sim_and_redirects(client, fake_image_engine):
    fake_image_engine.sim_response = {
        "criteria": [
            {"id": "color", "label": "Color principal", "description": "navy uniform"},
            {"id": "logo_pos", "label": "Logo poziție", "description": "piept stâng"},
        ]
    }
    files = {"sim": ("mockup.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    r = client.post("/matches", files=files, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["Location"].startswith("/matches/")
    assert len(fake_image_engine.analyze_calls) == 1


def test_get_match_session_shows_criteria_and_real_upload(client, fake_image_engine):
    fake_image_engine.sim_response = {
        "criteria": [{"id": "color", "label": "Color", "description": "navy"}]
    }
    files = {"sim": ("mockup.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    r = client.post("/matches", files=files, follow_redirects=False)
    match_url = r.headers["Location"]

    r = client.get(match_url)
    assert r.status_code == 200
    assert "Criterii detectate" in r.text
    assert "Color" in r.text
    assert 'name="real"' in r.text


def test_post_match_real_runs_compare_and_redirects_to_report(client, fake_image_engine):
    fake_image_engine.sim_response = {"criteria": [{"id": "color", "label": "Color", "description": "x"}]}
    fake_image_engine.compare_response = {
        "rows": [{"criterion": "Color", "sim_value": "navy", "real_value": "navy",
                  "match": True, "match_type": "exact", "confidence": "high", "note": ""}],
        "summary": {"matched": 1, "mismatched": 0, "total": 1},
    }
    files = {"sim": ("mockup.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    r = client.post("/matches", files=files, follow_redirects=False)
    match_id = r.headers["Location"].rsplit("/", 1)[-1]

    files = {"real": ("real.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    r = client.post(f"/matches/{match_id}/real", files=files, follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["Location"] == f"/matches/{match_id}/report"
    assert len(fake_image_engine.compare_calls) == 1


def test_match_report_shows_rows_table(client, fake_image_engine):
    fake_image_engine.sim_response = {"criteria": [{"id": "c1", "label": "Color", "description": "x"}]}
    fake_image_engine.compare_response = {
        "rows": [{"criterion": "Color", "sim_value": "navy", "real_value": "navy",
                  "match": True, "match_type": "exact", "confidence": "high", "note": ""}],
        "summary": {"matched": 1, "mismatched": 0, "total": 1},
    }
    files = {"sim": ("m.png", io.BytesIO(_tiny_jpeg_bytes()), "image/png")}
    r = client.post("/matches", files=files, follow_redirects=False)
    match_id = r.headers["Location"].rsplit("/", 1)[-1]
    files = {"real": ("r.jpg", io.BytesIO(_tiny_jpeg_bytes()), "image/jpeg")}
    client.post(f"/matches/{match_id}/real", files=files, follow_redirects=False)

    r = client.get(f"/matches/{match_id}/report")
    assert r.status_code == 200
    assert "Color" in r.text
    assert "navy" in r.text
    assert "exact" in r.text
```

- [ ] **Step 6: Run — expect FAIL** (Match routes don't exist)

- [ ] **Step 7: Implement Match routes in `web/app.py`**

Add imports at the top of `web/app.py`:

```python
from image_matcher.engine import analyze_sim, compare_real
```

(Re-exporting these at module level lets tests patch them via `monkeypatch.setattr(web_app, "analyze_sim", ...)`.)

Append the route handlers:

```python
@app.get("/matches/new", response_class=HTMLResponse)
def match_new(request: Request):
    return TEMPLATES.TemplateResponse("match_new.html", {"request": request})


@app.post("/matches")
async def create_match(sim: UploadFile = File(...)):
    content = await sim.read()
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(status_code=413, detail="Mockup-ul depășește 5MB")

    # Save sim file under uploads/match-staging/ first; rename to uploads/{match_id}/ after we have the id
    import uuid as _uuid
    match_id_prefix = str(_uuid.uuid4())
    match_uploads = UPLOADS_DIR / "match" / match_id_prefix
    match_uploads.mkdir(parents=True, exist_ok=True)

    ext = ".png" if sim.content_type == "image/png" else ".jpg"
    if sim.filename and sim.filename.lower().endswith(".webp"):
        ext = ".webp"
    sim_path = match_uploads / f"sim{ext}"
    sim_path.write_bytes(content)

    try:
        sim_report = analyze_sim(sim_path)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"analyze_sim a eșuat: {e}")

    with get_conn() as conn:
        match_id = repository.create_match_session(
            conn, sim_image_path=str(sim_path), sim_report=sim_report,
        )

    return Response(status_code=303, headers={"Location": f"/matches/{match_id}"})


@app.get("/matches/{match_id}", response_class=HTMLResponse)
def view_match(match_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_match_session(conn, match_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Match inexistent")

    sim_report = json.loads(row["sim_report_json"])
    criteria = sim_report.get("criteria", [])

    return TEMPLATES.TemplateResponse(
        "match_wait.html",
        {"request": request, "match_id": match_id, "criteria": criteria},
    )


@app.post("/matches/{match_id}/real")
async def upload_match_real(match_id: str, real: UploadFile = File(...)):
    with get_conn() as conn:
        row = repository.get_match_session(conn, match_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Match inexistent")
        if row["status"] != "awaiting_real":
            raise HTTPException(status_code=409, detail="Match nu așteaptă poză reală")

        content = await real.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(status_code=413, detail="Poza reală depășește 5MB")

        sim_path = Path(row["sim_image_path"])
        match_dir = sim_path.parent
        ext = ".png" if real.content_type == "image/png" else ".jpg"
        if real.filename and real.filename.lower().endswith(".webp"):
            ext = ".webp"
        real_path = match_dir / f"real{ext}"
        real_path.write_bytes(content)

        sim_report = json.loads(row["sim_report_json"])
        try:
            compare_report = compare_real(real_path, sim_report, max_tokens=8192)
        except Exception as e:
            repository.fail_match_session(conn, match_id)
            raise HTTPException(status_code=502, detail=f"compare_real a eșuat: {e}")

        repository.update_match_compare_report(
            conn, match_id, real_image_path=str(real_path), compare_report=compare_report,
        )

    return Response(status_code=303, headers={"Location": f"/matches/{match_id}/report"})


@app.get("/matches/{match_id}/report", response_class=HTMLResponse)
def view_match_report(match_id: str, request: Request):
    with get_conn() as conn:
        row = repository.get_match_session(conn, match_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Match inexistent")
        if row["status"] != "complete":
            raise HTTPException(status_code=409, detail="Raport indisponibil — match nu e complet")

    compare_report = json.loads(row["compare_report_json"])

    return TEMPLATES.TemplateResponse(
        "match_report.html",
        {
            "request": request, "match_id": match_id,
            "rows": compare_report.get("rows", []),
            "summary": compare_report.get("summary", {"matched": 0, "mismatched": 0}),
        },
    )
```

- [ ] **Step 8: Run Match E2E tests — expect PASS** (5 tests green)

- [ ] **Step 9: Run full suite**

```bash
.venv\Scripts\pytest.exe tests/ -v
```

Expected: ~48 PASSED (43 from before + 5 Match), 0-1 SKIPPED.

- [ ] **Step 10: Manual smoke test — Match flow end-to-end**

With `ANTHROPIC_API_KEY` set, run `.venv\Scripts\uvicorn.exe main:app --port 8765`.

Open `http://localhost:8765/` → click "Am un mockup" → upload a mockup PNG (e.g. an existing `image_matcher/input/Tricou_05_sim.png`) → wait ~10s → land on criteria view → upload a real photo → wait ~15s → land on report table.

Verify rows display, summary chips show counts, badges show match types.

- [ ] **Step 11: Commit**

```bash
git add web/app.py web/templates/match_new.html web/templates/match_wait.html web/templates/match_report.html tests/conftest.py tests/e2e/test_routes.py
git commit -m "feat: Match web flow (sim upload → analyze_sim → criteria, real upload → compare_real → report table)"
```

---

## Task 11: README + manual smoke test + tag

Final polish. Fill in the README with both flows documented, run the manual checklist end-to-end against a real Claude API, capture observations, tag the MVP.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace `README.md` with the complete version**

```markdown
# Ciptronic Product Validator

Aplicație web locală pentru specificarea și validarea vizuală a produselor personalizate. Două fluxuri paralele:

1. **Discovery + Inspector** (flux text) — descriere vagă a clientului → JSON structurat, prin întrebări țintite (max 5 runde). Apoi: JSON + 1-4 poze ale produsului finit → raport pe trei zone (conform / neconform / nevizibil).
2. **Image Match** (flux imagine) — mockup / artwork → criterii vizuale extrase automat. Apoi: criterii + poză produs real → raport tabelar cu match-uri și discrepanțe, criteriu cu criteriu.

Stack: Python 3.10+, FastAPI, HTMX, Jinja2, SQLite, Anthropic Claude Sonnet 4.6. Rulează local, single-user.

## Setup

Cerințe: Python 3.10+. Cont Anthropic cu cheie de API.

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows PowerShell sau cmd
# source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
# editează .env și pune ANTHROPIC_API_KEY
```

## Run

```bash
.venv\Scripts\uvicorn.exe main:app --reload
```

Deschide http://localhost:8000. Landing-ul îți cere să alegi între flux text și flux imagine.

Image_matcher Streamlit (dev tool standalone, rămâne separat):

```bash
.venv\Scripts\streamlit.exe run image_matcher/app.py
```

## Test

```bash
.venv\Scripts\pytest.exe tests/
```

Pentru testele de integrare cu API real:

```bash
$env:ANTHROPIC_API_KEY = "sk-ant-..."
.venv\Scripts\pytest.exe tests/integration -v
```

## Structura proiectului

```
agents/             logica pură Flow A + wrapper LLM
prompts/            prompturile sistem (versionate)
schemas/            scheme JSON pe tipuri de produs (extensibil)
db/                 schema SQL (3 tabele) + repository functions
web/                FastAPI + templates Jinja + static CSS
image_matcher/      Image Match engine + Streamlit UI (sub-proiect intact)
tests/              unit / integration / e2e + fixtures
docs/               specs, plans, mockups
main.py             entry point uvicorn
```

## Adaugă un tip de produs nou (Flow A)

1. Creează `schemas/<nume>.json` cu același format ca `tricou.json`.
2. Restart server.
3. Noul produs apare automat în dropdown-ul de pe `/sessions/new`.

Nu modifici cod. Flow B (Image Match) e agnostic la tip produs, nu e afectat.

## Manual smoke test checklist

După `uvicorn main:app --reload`, deschide http://localhost:8000.

### Flow A (descriere)

- [ ] Landing arată două cards: „Am o descriere" și „Am un mockup"
- [ ] Click „Am o descriere" → `/sessions/new` se deschide cu dropdown + textarea
- [ ] Submit cu descriere `tricou navy cu logo pe piept stâng` → redirect la `/sessions/{id}`
- [ ] Stare specificație arată câmpurile pre-completate (culoare, mâneci, branding.poziție)
- [ ] Întrebări în română, max 4 per rundă
- [ ] Submit la întrebări declanșează HTMX swap, rundă nouă apare
- [ ] La done=true, butonul „Validează cu poze" apare
- [ ] La 5 runde fără completare, sesiunea se închide forțat
- [ ] „fără branding" la prima rundă completează branding și sare peste sub-câmpuri
- [ ] Upload 1-4 poze acceptat (JPG/PNG/WEBP, max 5MB)
- [ ] Raport afișează 3 zone (Conform / Neconform / Nevizibil)
- [ ] Pentru poză exclusiv din față, câmpuri spate în „Nevizibil"
- [ ] Restart uvicorn → sesiunile vechi în DB (`ciptronic.db`)

### Flow B (mockup)

- [ ] Click „Am un mockup" → `/matches/new` se deschide
- [ ] Upload mockup (ex. `image_matcher/input/Tricou_05_sim.png`) → spinner ~10s → redirect la `/matches/{id}`
- [ ] Criteriile extrase afișate în listă numerotată
- [ ] Upload poză produs real → spinner ~15s → redirect la `/matches/{id}/report`
- [ ] Raport: chips summary (Total / Match / Mismatch) + tabel rows
- [ ] Fiecare rând afișează: criteriu, sim_value, real_value, match icon (✓/✗/+), match_type (exact/partial/extra/missing)
- [ ] Restart uvicorn → match-urile vechi în DB

### Ambele

- [ ] `/healthz` returnează `ok`
- [ ] Ctrl+C: server stop curat

## Spec & plan

- [Implementation plan](docs/superpowers/plans/2026-05-27-ciptronic-validator-unified.md)
- [Image Match engine plan](docs/superpowers/plans/2026-05-18-image-match-engine.md) (sub-proiect ✓ done)
- [Original Discovery + Inspector spec](docs/superpowers/specs/2026-05-17-ciptronic-validator-design.md)
- [Mockups](docs/mockups/_index.html)
```

- [ ] **Step 2: Run the manual checklist end-to-end against real LLM**

Set `ANTHROPIC_API_KEY` in `.env`, run `uvicorn main:app --reload`, walk through both flows in the browser. Tick the boxes. For each failure:
- Bug in code → fix immediately or file an issue.
- Prompt issue → iterate `prompts/discovery.md` or `prompts/inspector.md`.
- Missing feature → add to a follow-up plan, NOT to MVP.

- [ ] **Step 3: Run the full test suite one more time**

```bash
.venv\Scripts\pytest.exe -v
```

Expected: 48+ PASSED, 0-1 SKIPPED.

- [ ] **Step 4: Tag the MVP**

```bash
git add README.md
git commit -m "docs: complete README with both flows, setup, manual checklist"
git tag -a mvp-v0.2 -m "MVP: two-flow validator (Discovery+Inspector + Image Match)"
```

- [ ] **Step 5: Final commit summary**

```bash
git log --oneline
```

Expected: ~13 commits since branch root (Tasks 1-11 + image_matcher commits + spec/plan commits), tagged `mvp-v0.2`.

---

## Out of scope (NOT in this MVP — for follow-up plans)

- Hybrid flow (mockup + text constraints overlaid). Explicitly excluded in brainstorming; rare in practice.
- `schemas/sapca.json`, `schemas/hanorac.json` — drop-in additions, no code changes.
- Camera capture in the browser (`getUserMedia` + canvas).
- Multi-user / authentication.
- Editable spec view between Discovery and Inspector.
- Re-run Inspector or Image Match on the same session with new images.
- Listing / searching / paginating past sessions and reports (history page).
- Export report as PDF or Excel.
- Filtering match history by product type (Flow B is agnostic by design).
- Background job queue for long LLM calls (currently blocks the request thread; OK for single-user local app).
