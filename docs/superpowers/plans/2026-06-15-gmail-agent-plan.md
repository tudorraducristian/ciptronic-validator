# Agent Email Gmail — Plan de Implementare

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adaugă un agent care verifică un inbox Gmail la fiecare 2 minute, clasifică emailurile primite cu LLM, rulează flow-ul Discovery sau Image Match corespunzător și răspunde clientului cu raportul ca PDF atașat.

**Architecture:** Modul nou `email_agent/` care importă direct din `agents`, `image_matcher.engine` și `db.repository` — zero duplicare de logică. Rulează ca proces separat (`python -m email_agent.poller`). Gmail API e mereu mock-uit în teste prin același pattern `_FakeGmail` ca `_FakeLLM` existent.

**Tech Stack:** Python 3.11+, FastAPI (existent), SQLite (existent), `google-auth-oauthlib>=1.2`, `google-api-python-client>=2.120`, `weasyprint>=62.0`, pytest (existent)

---

## Fișiere create / modificate

| Fișier | Acțiune | Responsabilitate |
|---|---|---|
| `db/schema.sql` | Modificat | Adaugă tabelul `email_jobs` |
| `db/email_jobs.py` | Creat | CRUD pentru `email_jobs` |
| `email_agent/__init__.py` | Creat | Marker pachet |
| `email_agent/gmail_client.py` | Creat | OAuth2 + Gmail API: citire inbox, trimitere email |
| `email_agent/email_parser.py` | Creat | Extragere text/atașamente + clasificare LLM |
| `email_agent/dispatcher.py` | Creat | Rutare Flow A / Flow B, creare sesiune în DB |
| `email_agent/pdf_generator.py` | Creat | Randare raport HTML → PDF (WeasyPrint) |
| `email_agent/notifier.py` | Creat | Trimitere email răspuns cu PDF atașat |
| `email_agent/poller.py` | Creat | Loop polling la 2 minute — entry point |
| `web/app.py` | Modificat | Adaugă `GET /email-jobs`, `POST /email-jobs/{id}/retry` |
| `web/templates/base.html` | Modificat | Link navigare → Email Jobs |
| `web/templates/email_jobs.html` | Creat | Panou monitorizare |
| `tests/unit/test_email_jobs_db.py` | Creat | Teste CRUD email_jobs |
| `tests/unit/test_email_parser.py` | Creat | Teste clasificare LLM |
| `tests/unit/test_dispatcher.py` | Creat | Teste rutare Flow A / B |
| `tests/unit/test_pdf_generator.py` | Creat | Test PDF non-gol |
| `tests/e2e/test_email_agent_routes.py` | Creat | Teste rute panou monitorizare |
| `requirements.txt` | Modificat | 3 dependențe noi |
| `.gitignore` | Modificat | Adaugă `gmail_token.json`, `credentials.json` |

---

## Task 1: Schema DB — tabelul `email_jobs`

**Fișiere:**
- Modificat: `db/schema.sql`
- Modificat: `tests/conftest.py` (fixture `conn` — automat prin schema.sql)
- Test: `tests/unit/test_email_jobs_db.py`

- [ ] **Step 1.1: Scrie testul care va eșua**

Creează `tests/unit/test_email_jobs_db.py`:

```python
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent.parent / "db" / "schema.sql"


def make_conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return c


def test_email_jobs_table_exists():
    conn = make_conn()
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='email_jobs'"
    )
    assert cur.fetchone() is not None


def test_email_jobs_unique_gmail_message_id():
    conn = make_conn()
    conn.execute(
        """INSERT INTO email_jobs
           (id, gmail_message_id, sender_email, status, received_at)
           VALUES ('id1', 'gid1', 'a@b.com', 'pending', datetime('now'))"""
    )
    conn.commit()
    import pytest
    with pytest.raises(Exception):
        conn.execute(
            """INSERT INTO email_jobs
               (id, gmail_message_id, sender_email, status, received_at)
               VALUES ('id2', 'gid1', 'c@d.com', 'pending', datetime('now'))"""
        )
        conn.commit()
```

- [ ] **Step 1.2: Rulează testul să confirmi că eșuează**

```
pytest tests/unit/test_email_jobs_db.py -v
```

Așteptat: FAIL — `email_jobs` table not found

- [ ] **Step 1.3: Adaugă tabelul în schema.sql**

Adaugă la sfârșitul `db/schema.sql`:

```sql
CREATE TABLE IF NOT EXISTS email_jobs (
    id                TEXT PRIMARY KEY,
    gmail_message_id  TEXT UNIQUE NOT NULL,
    sender_email      TEXT NOT NULL,
    subject           TEXT,
    flow_type         TEXT,
    status            TEXT NOT NULL DEFAULT 'pending',
    session_id        TEXT,
    error_message     TEXT,
    received_at       DATETIME NOT NULL,
    processed_at      DATETIME
);

CREATE INDEX IF NOT EXISTS idx_email_jobs_status
    ON email_jobs(status);
```

- [ ] **Step 1.4: Rulează testele să confirmi că trec**

```
pytest tests/unit/test_email_jobs_db.py -v
```

Așteptat: 2 PASSED

- [ ] **Step 1.5: Commit**

```
git add db/schema.sql tests/unit/test_email_jobs_db.py
git commit -m "feat(db): add email_jobs table"
```

---

## Task 2: CRUD `db/email_jobs.py`

**Fișiere:**
- Creat: `db/email_jobs.py`
- Test: `tests/unit/test_email_jobs_db.py` (extins)

- [ ] **Step 2.1: Adaugă testele pentru CRUD**

Adaugă în `tests/unit/test_email_jobs_db.py`:

```python
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from db import email_jobs


def test_create_and_get_job():
    conn = make_conn()
    jid = email_jobs.create_job(
        conn,
        gmail_message_id="gid-001",
        sender_email="client@firma.ro",
        subject="Tricou polo",
        received_at="2026-06-15 10:00:00",
    )
    row = email_jobs.get_job(conn, jid)
    assert row["sender_email"] == "client@firma.ro"
    assert row["status"] == "pending"
    assert row["flow_type"] is None


def test_update_job_status():
    conn = make_conn()
    jid = email_jobs.create_job(
        conn,
        gmail_message_id="gid-002",
        sender_email="x@y.com",
        subject="Test",
        received_at="2026-06-15 10:00:00",
    )
    email_jobs.update_job_status(conn, jid, status="done", flow_type="discovery", session_id="sess-1")
    row = email_jobs.get_job(conn, jid)
    assert row["status"] == "done"
    assert row["flow_type"] == "discovery"
    assert row["session_id"] == "sess-1"
    assert row["processed_at"] is not None


def test_fail_job():
    conn = make_conn()
    jid = email_jobs.create_job(
        conn,
        gmail_message_id="gid-003",
        sender_email="x@y.com",
        subject="Test",
        received_at="2026-06-15 10:00:00",
    )
    email_jobs.fail_job(conn, jid, error_message="LLM timeout")
    row = email_jobs.get_job(conn, jid)
    assert row["status"] == "failed"
    assert row["error_message"] == "LLM timeout"


def test_list_jobs_ordered_by_received():
    conn = make_conn()
    email_jobs.create_job(conn, "gid-a", "a@b.com", "Primul", "2026-06-15 09:00:00")
    email_jobs.create_job(conn, "gid-b", "b@c.com", "Al doilea", "2026-06-15 10:00:00")
    rows = email_jobs.list_jobs(conn)
    assert rows[0]["subject"] == "Al doilea"
    assert rows[1]["subject"] == "Primul"


def test_job_exists_by_gmail_id():
    conn = make_conn()
    email_jobs.create_job(conn, "gid-x", "x@y.com", "Sub", "2026-06-15 10:00:00")
    assert email_jobs.exists_by_gmail_id(conn, "gid-x") is True
    assert email_jobs.exists_by_gmail_id(conn, "gid-missing") is False
```

- [ ] **Step 2.2: Rulează testele să confirmi că eșuează**

```
pytest tests/unit/test_email_jobs_db.py -v
```

Așteptat: FAIL — `cannot import name 'email_jobs'`

- [ ] **Step 2.3: Implementează `db/email_jobs.py`**

```python
import sqlite3
import uuid
from datetime import datetime, timezone


def create_job(
    conn: sqlite3.Connection,
    gmail_message_id: str,
    sender_email: str,
    subject: str | None,
    received_at: str,
) -> str:
    jid = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO email_jobs
            (id, gmail_message_id, sender_email, subject, status, received_at)
        VALUES (?, ?, ?, ?, 'pending', ?)
        """,
        (jid, gmail_message_id, sender_email, subject, received_at),
    )
    conn.commit()
    return jid


def get_job(conn: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
    cur = conn.execute("SELECT * FROM email_jobs WHERE id = ?", (job_id,))
    return cur.fetchone()


def update_job_status(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
    flow_type: str | None = None,
    session_id: str | None = None,
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        UPDATE email_jobs
        SET status = ?, flow_type = ?, session_id = ?, processed_at = ?
        WHERE id = ?
        """,
        (status, flow_type, session_id, now, job_id),
    )
    conn.commit()


def fail_job(conn: sqlite3.Connection, job_id: str, error_message: str) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    conn.execute(
        """
        UPDATE email_jobs
        SET status = 'failed', error_message = ?, processed_at = ?
        WHERE id = ?
        """,
        (error_message, now, job_id),
    )
    conn.commit()


def list_jobs(conn: sqlite3.Connection, limit: int = 100) -> list[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM email_jobs ORDER BY received_at DESC LIMIT ?", (limit,)
    )
    return cur.fetchall()


def exists_by_gmail_id(conn: sqlite3.Connection, gmail_message_id: str) -> bool:
    cur = conn.execute(
        "SELECT 1 FROM email_jobs WHERE gmail_message_id = ?", (gmail_message_id,)
    )
    return cur.fetchone() is not None
```

- [ ] **Step 2.4: Rulează testele**

```
pytest tests/unit/test_email_jobs_db.py -v
```

Așteptat: 7 PASSED

- [ ] **Step 2.5: Commit**

```
git add db/email_jobs.py tests/unit/test_email_jobs_db.py
git commit -m "feat(db): email_jobs CRUD"
```

---

## Task 3: `email_agent/gmail_client.py`

**Fișiere:**
- Creat: `email_agent/__init__.py`
- Creat: `email_agent/gmail_client.py`

Nu scriem teste de integrare pentru Gmail API real. Modulul expune o interfață clară pe care Task 4+ o vor mock-ui.

- [ ] **Step 3.1: Instalează dependențele**

```
.venv\Scripts\pip install google-auth-oauthlib>=1.2 google-api-python-client>=2.120
```

Adaugă în `requirements.txt`:
```
google-auth-oauthlib>=1.2
google-api-python-client>=2.120
```

- [ ] **Step 3.2: Creează `email_agent/__init__.py`**

```python
```
(fișier gol)

- [ ] **Step 3.3: Implementează `email_agent/gmail_client.py`**

```python
import base64
import os
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email import encoders
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


@dataclass
class EmailMessage:
    gmail_id: str
    sender: str
    subject: str
    body_text: str
    attachments: list[dict]  # [{"filename": str, "mime_type": str, "data": bytes}]


@dataclass
class GmailClient:
    credentials_path: str = field(
        default_factory=lambda: os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
    )
    token_path: str = "gmail_token.json"

    def __post_init__(self):
        self._service = self._build_service()

    def _build_service(self):
        creds = None
        if Path(self.token_path).exists():
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)
            Path(self.token_path).write_text(creds.to_json())
        return build("gmail", "v1", credentials=creds)

    def list_unread(self) -> list[EmailMessage]:
        result = self._service.users().messages().list(
            userId="me", q="is:unread"
        ).execute()
        messages = result.get("messages", [])
        parsed = []
        for m in messages:
            msg = self._service.users().messages().get(
                userId="me", id=m["id"], format="full"
            ).execute()
            parsed.append(self._parse_message(msg))
        return parsed

    def mark_read(self, gmail_id: str) -> None:
        self._service.users().messages().modify(
            userId="me", id=gmail_id, body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    def send_email(self, to: str, subject: str, body: str, pdf_bytes: bytes | None = None,
                   pdf_filename: str = "raport.pdf") -> None:
        msg = MIMEMultipart()
        msg["to"] = to
        msg["subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))
        if pdf_bytes:
            part = MIMEBase("application", "pdf")
            part.set_payload(pdf_bytes)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{pdf_filename}"')
            msg.attach(part)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        self._service.users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()

    def _parse_message(self, msg: dict) -> EmailMessage:
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body_text = ""
        attachments = []
        self._walk_parts(msg["payload"], body_text_ref := [""], attachments)
        body_text = body_text_ref[0]
        return EmailMessage(
            gmail_id=msg["id"],
            sender=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            body_text=body_text,
            attachments=attachments,
        )

    def _walk_parts(self, payload: dict, body_ref: list, attachments: list) -> None:
        mime = payload.get("mimeType", "")
        if mime == "text/plain" and not payload.get("filename"):
            data = payload.get("body", {}).get("data", "")
            if data:
                body_ref[0] += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        elif payload.get("filename"):
            data = payload.get("body", {}).get("data", "")
            att_id = payload.get("body", {}).get("attachmentId")
            if att_id:
                pass  # fetched lazily; skip for interface clarity
            if data:
                attachments.append({
                    "filename": payload["filename"],
                    "mime_type": mime,
                    "data": base64.urlsafe_b64decode(data),
                })
        for part in payload.get("parts", []):
            self._walk_parts(part, body_ref, attachments)
```

- [ ] **Step 3.4: Commit**

```
git add email_agent/__init__.py email_agent/gmail_client.py requirements.txt
git commit -m "feat(email_agent): GmailClient wrapper (OAuth2 + list/send)"
```

---

## Task 4: `email_agent/email_parser.py` — clasificare LLM

**Fișiere:**
- Creat: `email_agent/email_parser.py`
- Test: `tests/unit/test_email_parser.py`

- [ ] **Step 4.1: Scrie testele care vor eșua**

Creează `tests/unit/test_email_parser.py`:

```python
import pytest
from email_agent.gmail_client import EmailMessage
from email_agent import email_parser


class FakeLLM:
    def __init__(self, response: str):
        self._response = response
        self.calls: list[tuple] = []

    def complete_text(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._response


def _make_msg(body="", attachments=None, subject="Test"):
    return EmailMessage(
        gmail_id="gid-1",
        sender="client@x.com",
        subject=subject,
        body_text=body,
        attachments=attachments or [],
    )


def test_classify_discovery():
    llm = FakeLLM('{"flow_type": "discovery", "description": "tricou polo navy", "mockup_attachment": null, "real_photo_attachment": null}')
    result = email_parser.classify(_make_msg(body="Am un tricou polo navy"), llm)
    assert result["flow_type"] == "discovery"
    assert result["description"] == "tricou polo navy"


def test_classify_match():
    llm = FakeLLM('{"flow_type": "match", "description": null, "mockup_attachment": "mockup.png", "real_photo_attachment": null}')
    msg = _make_msg(
        body="vezi mockup atasat",
        attachments=[{"filename": "mockup.png", "mime_type": "image/png", "data": b"\xff"}],
    )
    result = email_parser.classify(msg, llm)
    assert result["flow_type"] == "match"
    assert result["mockup_attachment"] == "mockup.png"


def test_classify_unclear():
    llm = FakeLLM('{"flow_type": "unclear", "description": null, "mockup_attachment": null, "real_photo_attachment": null}')
    result = email_parser.classify(_make_msg(body="salut"), llm)
    assert result["flow_type"] == "unclear"


def test_classify_spam():
    llm = FakeLLM('{"flow_type": "spam", "description": null, "mockup_attachment": null, "real_photo_attachment": null}')
    result = email_parser.classify(_make_msg(body="castigati premii"), llm)
    assert result["flow_type"] == "spam"


def test_classify_retries_on_llm_error():
    call_count = 0

    class FlakeyLLM:
        def complete_text(self, system, user):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("timeout")
            return '{"flow_type": "spam", "description": null, "mockup_attachment": null, "real_photo_attachment": null}'

    result = email_parser.classify(_make_msg(body="ceva"), FlakeyLLM())
    assert result["flow_type"] == "spam"
    assert call_count == 2


def test_classify_raises_after_max_retries():
    class AlwaysFailLLM:
        def complete_text(self, system, user):
            raise RuntimeError("always fails")

    with pytest.raises(RuntimeError):
        email_parser.classify(_make_msg(body="ceva"), AlwaysFailLLM(), max_retries=2)
```

- [ ] **Step 4.2: Rulează testele să confirmi că eșuează**

```
pytest tests/unit/test_email_parser.py -v
```

Așteptat: FAIL — `cannot import name 'email_parser'`

- [ ] **Step 4.3: Implementează `email_agent/email_parser.py`**

```python
import json
import time

from email_agent.gmail_client import EmailMessage


SYSTEM_PROMPT = """Ești un clasificator de emailuri pentru Ciptronic Validator.
Analizează emailul primit și returnează EXCLUSIV un obiect JSON cu structura:
{
  "flow_type": "discovery" | "match" | "unclear" | "spam",
  "description": "<descriere produs extrasă din corp, sau null>",
  "mockup_attachment": "<numele fișierului imagine mockup, sau null>",
  "real_photo_attachment": "<numele fișierului poză reală, dacă există, sau null>"
}

Reguli:
- "discovery": emailul conține o descriere text a unui produs de validat (fără imagini sau cu imagini irelevante)
- "match": emailul conține cel puțin o imagine atașată care pare un mockup de produs Ciptronic
- "unclear": emailul există dar nu poți determina intenția
- "spam": emailul este irelevant sau nesolicitat
Răspunde DOAR cu JSON, fără text suplimentar."""


def classify(message: EmailMessage, llm, max_retries: int = 3) -> dict:
    attachment_list = [
        {"filename": a["filename"], "mime_type": a["mime_type"]}
        for a in message.attachments
    ]
    user_content = json.dumps({
        "subject": message.subject,
        "body": message.body_text[:2000],
        "attachments": attachment_list,
    }, ensure_ascii=False)

    last_error = None
    for attempt in range(max_retries):
        try:
            raw = llm.complete_text(system=SYSTEM_PROMPT, user=user_content)
            return _parse_classification(raw)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
    raise last_error


def _parse_classification(text: str) -> dict:
    text = text.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError(f"Răspuns LLM invalid: {text[:80]!r}")
        data = json.loads(text[start:end + 1])

    valid_types = {"discovery", "match", "unclear", "spam"}
    if data.get("flow_type") not in valid_types:
        raise ValueError(f"flow_type invalid: {data.get('flow_type')!r}")
    return data
```

- [ ] **Step 4.4: Rulează testele**

```
pytest tests/unit/test_email_parser.py -v
```

Așteptat: 6 PASSED

- [ ] **Step 4.5: Commit**

```
git add email_agent/email_parser.py tests/unit/test_email_parser.py
git commit -m "feat(email_agent): email_parser — LLM classification with retry"
```

---

## Task 5: `email_agent/dispatcher.py` — rutare Flow A / Flow B

**Fișiere:**
- Creat: `email_agent/dispatcher.py`
- Test: `tests/unit/test_dispatcher.py`

- [ ] **Step 5.1: Scrie testele care vor eșua**

Creează `tests/unit/test_dispatcher.py`:

```python
import sqlite3
from pathlib import Path
import pytest

SCHEMA_PATH = Path(__file__).parent.parent.parent / "db" / "schema.sql"


def make_conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    return c


class FakeLLM:
    def __init__(self):
        self.responses = []

    def queue(self, r):
        self.responses.append(r)

    def complete_text(self, system, user):
        return self.responses.pop(0)

    def complete_vision(self, system, content_blocks):
        return self.responses.pop(0)


DISCOVERY_DONE = '{"state": {"tip_produs": "tricou", "culoare": "navy"}, "intrebari": [], "done": true}'
INSPECTOR_RESPONSE = '{"conform": ["culoare"], "neconform": [], "nevizibil": [], "raw": ""}'
SIM_REPORT = {"criteria": [{"name": "culoare", "value": "navy"}]}
COMPARE_REPORT = {"rows": [{"criterion": "culoare", "match": true}], "summary": {"matched": 1, "mismatched": 0}}


def test_dispatch_discovery_creates_session_and_report(tmp_path):
    from email_agent import dispatcher

    conn = make_conn()
    llm = FakeLLM()
    llm.queue(DISCOVERY_DONE)
    llm.queue(INSPECTOR_RESPONSE)

    tiny_jpeg = (
        b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
        b"\xff\xdb\x00C\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t"
        b"\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a"
        b"\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342\x1e"
        b"\xff\xd9"
    )
    image_path = tmp_path / "photo.jpg"
    image_path.write_bytes(tiny_jpeg)

    result = dispatcher.dispatch_discovery(
        conn=conn,
        llm=llm,
        description="tricou navy cu logo",
        product_type="tricou",
        image_paths=[str(image_path)],
        uploads_dir=tmp_path,
    )
    assert result["session_id"] is not None
    assert result["report_id"] is not None


def test_dispatch_match_creates_match_session(tmp_path):
    from email_agent import dispatcher

    conn = make_conn()

    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
        b"\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    sim_path = tmp_path / "mockup.png"
    sim_path.write_bytes(tiny_png)

    def fake_analyze(path, model=None):
        return SIM_REPORT

    result = dispatcher.dispatch_match(
        conn=conn,
        sim_image_path=str(sim_path),
        analyze_fn=fake_analyze,
        uploads_dir=tmp_path,
    )
    assert result["match_id"] is not None
    assert result["status"] == "awaiting_real"


def test_dispatch_match_with_real_photo(tmp_path):
    from email_agent import dispatcher

    conn = make_conn()

    tiny_png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00"
        b"\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx"
        b"\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    sim_path = tmp_path / "mockup.png"
    real_path = tmp_path / "real.png"
    sim_path.write_bytes(tiny_png)
    real_path.write_bytes(tiny_png)

    def fake_analyze(path, model=None):
        return SIM_REPORT

    def fake_compare(sim_report, sim_path, real_path, model=None, max_tokens=None):
        return COMPARE_REPORT

    result = dispatcher.dispatch_match(
        conn=conn,
        sim_image_path=str(sim_path),
        analyze_fn=fake_analyze,
        uploads_dir=tmp_path,
        real_image_path=str(real_path),
        compare_fn=fake_compare,
    )
    assert result["status"] == "complete"
    assert result["match_id"] is not None
```

- [ ] **Step 5.2: Rulează testele să confirmi că eșuează**

```
pytest tests/unit/test_dispatcher.py -v
```

Așteptat: FAIL — `cannot import name 'dispatcher'`

- [ ] **Step 5.3: Implementează `email_agent/dispatcher.py`**

```python
import shutil
import sqlite3
import uuid
from pathlib import Path

from agents import discovery, inspector
from db import repository


def dispatch_discovery(
    conn: sqlite3.Connection,
    llm,
    description: str,
    product_type: str,
    image_paths: list[str],
    uploads_dir: Path,
) -> dict:
    from schemas import loader
    schema = loader.load_schema(product_type)
    initial_state = loader.empty_state(schema)

    system, user = discovery.build_messages(
        schema=schema,
        initial_description=description,
        state=initial_state,
        history=[],
    )
    raw = llm.complete_text(system=system, user=user)
    step = discovery.parse_response(raw)

    sid = repository.create_session(conn, product_type, description)
    history = [{"round": 1, "questions": step.intrebari, "answers": None}]
    repository.update_session_state(conn, sid, step.state, history, rounds=1)
    repository.finalize_session(conn, sid)

    saved_paths = []
    for img_path in image_paths:
        dest = uploads_dir / f"{uuid.uuid4()}{Path(img_path).suffix}"
        shutil.copy(img_path, dest)
        saved_paths.append(str(dest))

    system_i, user_i = inspector.build_messages(
        spec=step.state, image_paths=saved_paths
    )
    raw_i = llm.complete_vision(system=system_i, content_blocks=user_i)
    result = inspector.parse_response(raw_i)

    rid = repository.save_report(
        conn, sid,
        spec=step.state,
        image_paths=saved_paths,
        conform=result.conform,
        neconform=result.neconform,
        nevizibil=result.nevizibil,
        raw=raw_i,
    )
    return {"session_id": sid, "report_id": rid}


def dispatch_match(
    conn: sqlite3.Connection,
    sim_image_path: str,
    analyze_fn,
    uploads_dir: Path,
    real_image_path: str | None = None,
    compare_fn=None,
) -> dict:
    dest_sim = uploads_dir / f"{uuid.uuid4()}{Path(sim_image_path).suffix}"
    shutil.copy(sim_image_path, dest_sim)

    sim_report = analyze_fn(str(dest_sim))
    mid = repository.create_match_session(conn, str(dest_sim), sim_report)

    if real_image_path and compare_fn:
        dest_real = uploads_dir / f"{uuid.uuid4()}{Path(real_image_path).suffix}"
        shutil.copy(real_image_path, dest_real)
        compare_report = compare_fn(sim_report, str(dest_sim), str(dest_real))
        repository.update_match_compare_report(conn, mid, str(dest_real), compare_report)
        return {"match_id": mid, "status": "complete"}

    return {"match_id": mid, "status": "awaiting_real"}
```

- [ ] **Step 5.4: Rulează testele**

```
pytest tests/unit/test_dispatcher.py -v
```

Așteptat: 3 PASSED

- [ ] **Step 5.5: Commit**

```
git add email_agent/dispatcher.py tests/unit/test_dispatcher.py
git commit -m "feat(email_agent): dispatcher — Flow A/B routing"
```

---

## Task 6: `email_agent/pdf_generator.py` — raport → PDF

**Fișiere:**
- Creat: `email_agent/pdf_generator.py`
- Test: `tests/unit/test_pdf_generator.py`

- [ ] **Step 6.1: Instalează WeasyPrint**

```
.venv\Scripts\pip install weasyprint>=62.0
```

Adaugă în `requirements.txt`:
```
weasyprint>=62.0
```

- [ ] **Step 6.2: Scrie testul care va eșua**

Creează `tests/unit/test_pdf_generator.py`:

```python
from email_agent import pdf_generator


def test_pdf_from_html_is_nonempty():
    html = "<html><body><h1>Raport test</h1><p>Conform: culoare</p></body></html>"
    result = pdf_generator.render_html_to_pdf(html)
    assert isinstance(result, bytes)
    assert len(result) > 100
    assert result[:4] == b"%PDF"
```

- [ ] **Step 6.3: Rulează testul să confirmi că eșuează**

```
pytest tests/unit/test_pdf_generator.py -v
```

Așteptat: FAIL — `cannot import name 'pdf_generator'`

- [ ] **Step 6.4: Implementează `email_agent/pdf_generator.py`**

```python
from pathlib import Path
import weasyprint


STATIC_DIR = Path(__file__).parent.parent / "web" / "static"


def render_html_to_pdf(html: str) -> bytes:
    base_url = STATIC_DIR.as_uri() + "/"
    return weasyprint.HTML(string=html, base_url=base_url).write_pdf()
```

- [ ] **Step 6.5: Rulează testul**

```
pytest tests/unit/test_pdf_generator.py -v
```

Așteptat: 1 PASSED

- [ ] **Step 6.6: Commit**

```
git add email_agent/pdf_generator.py tests/unit/test_pdf_generator.py requirements.txt
git commit -m "feat(email_agent): pdf_generator — WeasyPrint HTML to PDF"
```

---

## Task 7: `email_agent/notifier.py` — trimitere email cu PDF

**Fișiere:**
- Creat: `email_agent/notifier.py`

Notifier-ul este un wrapper subțire peste `GmailClient.send_email`. Nu scriem teste separate — e acoperit la nivelul e2e în Task 9.

- [ ] **Step 7.1: Implementează `email_agent/notifier.py`**

```python
from email_agent.gmail_client import GmailClient

CLARIFICATION_BODY = """Bună ziua,

Am primit emailul dumneavoastră, dar nu am putut determina tipul cererii.

Pentru a procesa cererea, vă rugăm să trimiteți unul dintre:
  - O DESCRIERE TEXT a produsului (pentru validare specificație)
  - O IMAGINE MOCKUP atașată (pentru comparare vizuală)

Vă mulțumim,
Ciptronic Validator"""

REPORT_BODY = """Bună ziua,

Raportul de validare pentru produsul dumneavoastră este atașat la acest email.

Vă mulțumim,
Ciptronic Validator"""


def send_clarification(gmail: GmailClient, to: str, subject: str) -> None:
    gmail.send_email(
        to=to,
        subject=f"Re: {subject} — informații suplimentare necesare",
        body=CLARIFICATION_BODY,
    )


def send_report(
    gmail: GmailClient,
    to: str,
    subject: str,
    pdf_bytes: bytes,
    report_id: str,
) -> None:
    gmail.send_email(
        to=to,
        subject=f"Re: {subject} — Raport Ciptronic",
        body=REPORT_BODY,
        pdf_bytes=pdf_bytes,
        pdf_filename=f"raport-ciptronic-{report_id}.pdf",
    )
```

- [ ] **Step 7.2: Commit**

```
git add email_agent/notifier.py
git commit -m "feat(email_agent): notifier — send clarification and report emails"
```

---

## Task 8: `email_agent/poller.py` — loop polling

**Fișiere:**
- Creat: `email_agent/poller.py`

- [ ] **Step 8.1: Implementează `email_agent/poller.py`**

```python
"""
Entry point: python -m email_agent.poller
Env vars required:
  ANTHROPIC_API_KEY
  GMAIL_CREDENTIALS_PATH  (default: credentials.json)
  DATABASE_PATH           (default: ./ciptronic.db)
  UPLOADS_DIR             (default: ./uploads)
  POLL_INTERVAL_SECONDS   (default: 120)
"""

import logging
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from agents.llm_client import LLMClient
from db import email_jobs
from email_agent.gmail_client import GmailClient, EmailMessage
from email_agent import email_parser, dispatcher, notifier, pdf_generator

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

DATABASE_PATH = os.environ.get("DATABASE_PATH", "./ciptronic.db")
UPLOADS_DIR = Path(os.environ.get("UPLOADS_DIR", "./uploads"))
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL_SECONDS", "120"))


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def process_message(message: EmailMessage, gmail: GmailClient, llm: LLMClient) -> None:
    conn = get_conn()
    try:
        if email_jobs.exists_by_gmail_id(conn, message.gmail_id):
            log.info("Mesaj deja procesat: %s", message.gmail_id)
            return

        received = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        job_id = email_jobs.create_job(
            conn,
            gmail_message_id=message.gmail_id,
            sender_email=message.sender,
            subject=message.subject,
            received_at=received,
        )
        log.info("Job creat %s pentru <%s>", job_id, message.sender)

        classification = email_parser.classify(message, llm)
        flow_type = classification["flow_type"]

        if flow_type == "spam":
            email_jobs.update_job_status(conn, job_id, status="spam", flow_type="spam")
            gmail.mark_read(message.gmail_id)
            return

        if flow_type == "unclear":
            notifier.send_clarification(gmail, message.sender, message.subject)
            email_jobs.update_job_status(conn, job_id, status="needs_clarification", flow_type="unclear")
            gmail.mark_read(message.gmail_id)
            return

        if flow_type == "discovery":
            result = dispatcher.dispatch_discovery(
                conn=conn,
                llm=llm,
                description=classification.get("description", message.body_text),
                product_type="tricou",
                image_paths=[],
                uploads_dir=UPLOADS_DIR,
            )
            html = _render_report_html(result["report_id"], conn)
            pdf_bytes = pdf_generator.render_html_to_pdf(html)
            notifier.send_report(gmail, message.sender, message.subject, pdf_bytes, result["report_id"])
            email_jobs.update_job_status(conn, job_id, status="done", flow_type="discovery", session_id=result["session_id"])

        elif flow_type == "match":
            sim_att = next(
                (a for a in message.attachments if a["filename"] == classification.get("mockup_attachment")),
                message.attachments[0] if message.attachments else None,
            )
            if not sim_att:
                raise ValueError("Atașament mockup negăsit în email")

            import tempfile
            with tempfile.NamedTemporaryFile(suffix=Path(sim_att["filename"]).suffix, delete=False) as tmp:
                tmp.write(sim_att["data"])
                sim_tmp_path = tmp.name

            real_tmp_path = None
            real_att_name = classification.get("real_photo_attachment")
            if real_att_name:
                real_att = next((a for a in message.attachments if a["filename"] == real_att_name), None)
                if real_att:
                    with tempfile.NamedTemporaryFile(suffix=Path(real_att["filename"]).suffix, delete=False) as tmp:
                        tmp.write(real_att["data"])
                        real_tmp_path = tmp.name

            from image_matcher.engine import analyze_sim, compare_real
            result = dispatcher.dispatch_match(
                conn=conn,
                sim_image_path=sim_tmp_path,
                analyze_fn=analyze_sim,
                uploads_dir=UPLOADS_DIR,
                real_image_path=real_tmp_path,
                compare_fn=compare_real if real_tmp_path else None,
            )
            html = _render_match_html(result["match_id"], conn)
            pdf_bytes = pdf_generator.render_html_to_pdf(html)
            notifier.send_report(gmail, message.sender, message.subject, pdf_bytes, result["match_id"])
            email_jobs.update_job_status(conn, job_id, status="done", flow_type="match", session_id=result["match_id"])

        gmail.mark_read(message.gmail_id)
        log.info("Job %s finalizat cu succes", job_id)

    except Exception as e:
        log.exception("Eroare la procesarea mesajului %s", message.gmail_id)
        try:
            email_jobs.fail_job(conn, job_id, error_message=str(e))
        except Exception:
            pass
    finally:
        conn.close()


def _render_report_html(report_id: str, conn: sqlite3.Connection) -> str:
    from db import repository
    from jinja2 import Environment, FileSystemLoader
    row = repository.get_report(conn, report_id)
    import json
    env = Environment(loader=FileSystemLoader(str(Path(__file__).parent.parent / "web" / "templates")))
    tmpl = env.get_template("report.html")
    return tmpl.render(
        report_id=report_id,
        spec=json.loads(row["spec_json"]),
        conform=json.loads(row["conform_json"]),
        neconform=json.loads(row["neconform_json"]),
        nevizibil=json.loads(row["nevizibil_json"]),
    )


def _render_match_html(match_id: str, conn: sqlite3.Connection) -> str:
    from db import repository
    from jinja2 import Environment, FileSystemLoader
    import json
    row = repository.get_match_session(conn, match_id)
    env = Environment(loader=FileSystemLoader(str(Path(__file__).parent.parent / "web" / "templates")))
    tmpl = env.get_template("match_report.html")
    compare = json.loads(row["compare_report_json"]) if row["compare_report_json"] else {}
    return tmpl.render(match_id=match_id, compare_report=compare)


def run_once(gmail: GmailClient, llm: LLMClient) -> None:
    messages = gmail.list_unread()
    log.info("Găsite %d mesaje necitite", len(messages))
    for message in messages:
        process_message(message, gmail, llm)


def main() -> None:
    gmail = GmailClient()
    llm = LLMClient()
    log.info("Poller pornit. Interval: %ds", POLL_INTERVAL)
    while True:
        try:
            run_once(gmail, llm)
        except Exception:
            log.exception("Eroare în ciclul de polling")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
```

- [ ] **Step 8.2: Commit**

```
git add email_agent/poller.py
git commit -m "feat(email_agent): poller — main polling loop"
```

---

## Task 9: Rute web + panou monitorizare

**Fișiere:**
- Modificat: `web/app.py`
- Creat: `web/templates/email_jobs.html`
- Modificat: `web/templates/base.html`
- Test: `tests/e2e/test_email_agent_routes.py`

- [ ] **Step 9.1: Scrie testele care vor eșua**

Creează `tests/e2e/test_email_agent_routes.py`:

```python
import sqlite3
from pathlib import Path

SCHEMA_PATH = Path(__file__).parent.parent.parent / "db" / "schema.sql"


def _seed_jobs(conn):
    conn.execute(
        """INSERT INTO email_jobs
           (id, gmail_message_id, sender_email, subject, flow_type, status, received_at)
           VALUES ('j1', 'gid1', 'a@b.com', 'Tricou polo', 'discovery', 'done', '2026-06-15 10:00:00')"""
    )
    conn.execute(
        """INSERT INTO email_jobs
           (id, gmail_message_id, sender_email, subject, flow_type, status, received_at)
           VALUES ('j2', 'gid2', 'x@y.com', 'Cerere', 'unclear', 'needs_clarification', '2026-06-15 09:00:00')"""
    )
    conn.execute(
        """INSERT INTO email_jobs
           (id, gmail_message_id, sender_email, subject, flow_type, status, error_message, received_at)
           VALUES ('j3', 'gid3', 'z@w.com', 'Fail', 'match', 'failed', 'LLM timeout', '2026-06-15 08:00:00')"""
    )
    conn.commit()


def test_email_jobs_panel_renders(client):
    import sqlite3
    conn = sqlite3.connect(client.app.state.db_path if hasattr(client.app, 'state') else ':memory:')
    # Seed via direct DB
    from web import app as web_app
    import os
    db_path = os.environ.get("DATABASE_PATH", "./ciptronic.db")
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    _seed_jobs(c)
    c.close()

    r = client.get("/email-jobs")
    assert r.status_code == 200
    assert "Tricou polo" in r.text
    assert "a@b.com" in r.text
    assert "done" in r.text


def test_email_jobs_panel_shows_all_statuses(client):
    import os, sqlite3
    db_path = os.environ.get("DATABASE_PATH", "./ciptronic.db")
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    _seed_jobs(c)
    c.close()

    r = client.get("/email-jobs")
    assert r.status_code == 200
    assert "needs_clarification" in r.text or "Necesită clarificare" in r.text
    assert "failed" in r.text or "Eșuat" in r.text


def test_retry_failed_job(client):
    import os, sqlite3
    db_path = os.environ.get("DATABASE_PATH", "./ciptronic.db")
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    _seed_jobs(c)
    c.close()

    r = client.post("/email-jobs/j3/retry")
    assert r.status_code in (200, 303)


def test_retry_nonexistent_job_returns_404(client):
    r = client.post("/email-jobs/nonexistent/retry")
    assert r.status_code == 404
```

- [ ] **Step 9.2: Rulează testele să confirmi că eșuează**

```
pytest tests/e2e/test_email_agent_routes.py -v
```

Așteptat: FAIL — ruta `/email-jobs` nu există

- [ ] **Step 9.3: Adaugă rutele în `web/app.py`**

Adaugă după importuri (lângă celelalte importuri din `db`):

```python
from db import email_jobs as email_jobs_repo
```

Adaugă la sfârșitul secțiunii de rute (înainte de sfârșitul fișierului):

```python
@app.get("/email-jobs", response_class=HTMLResponse)
def list_email_jobs(request: Request):
    with get_conn() as conn:
        jobs = email_jobs_repo.list_jobs(conn)
    done = sum(1 for j in jobs if j["status"] == "done")
    unclear = sum(1 for j in jobs if j["status"] == "needs_clarification")
    failed = sum(1 for j in jobs if j["status"] == "failed")
    return TEMPLATES.TemplateResponse(
        request,
        "email_jobs.html",
        {"jobs": jobs, "count_done": done, "count_unclear": unclear, "count_failed": failed},
    )


@app.post("/email-jobs/{job_id}/retry")
def retry_email_job(job_id: str):
    with get_conn() as conn:
        row = email_jobs_repo.get_job(conn, job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Job inexistent")
        email_jobs_repo.update_job_status(conn, job_id, status="pending")
    return Response(status_code=200, headers={"HX-Redirect": "/email-jobs"})
```

- [ ] **Step 9.4: Creează `web/templates/email_jobs.html`**

```html
{% extends "base.html" %}
{% block title %}Email Jobs{% endblock %}
{% block content %}
<h1>Email Jobs</h1>

<div class="counters" style="display:flex;gap:1rem;margin-bottom:1.5rem;">
  <span class="badge badge--green">{{ count_done }} Procesate</span>
  <span class="badge badge--yellow">{{ count_unclear }} Necesită clarificare</span>
  <span class="badge badge--red">{{ count_failed }} Eșuate</span>
</div>

<table class="table">
  <thead>
    <tr>
      <th>Expeditor</th>
      <th>Subiect</th>
      <th>Flow</th>
      <th>Status</th>
      <th>Primit</th>
      <th>Procesat</th>
      <th>Acțiuni</th>
    </tr>
  </thead>
  <tbody>
    {% for job in jobs %}
    <tr>
      <td>{{ job.sender_email }}</td>
      <td>{{ job.subject or "—" }}</td>
      <td>{{ job.flow_type or "—" }}</td>
      <td><span class="status status--{{ job.status }}">{{ job.status }}</span></td>
      <td>{{ job.received_at }}</td>
      <td>{{ job.processed_at or "—" }}</td>
      <td>
        {% if job.status == "failed" or job.status == "needs_clarification" %}
        <form method="post" action="/email-jobs/{{ job.id }}/retry">
          <button type="submit" class="btn btn--small">Reprocesează</button>
        </form>
        {% endif %}
        {% if job.session_id and job.flow_type == "discovery" %}
        <a href="/reports/{{ job.session_id }}" class="btn btn--small btn--secondary">Raport</a>
        {% elif job.session_id and job.flow_type == "match" %}
        <a href="/matches/{{ job.session_id }}/report" class="btn btn--small btn--secondary">Raport</a>
        {% endif %}
      </td>
    </tr>
    {% else %}
    <tr><td colspan="7" style="text-align:center;">Niciun job procesat încă.</td></tr>
    {% endfor %}
  </tbody>
</table>
{% endblock %}
```

- [ ] **Step 9.5: Adaugă link în `web/templates/base.html`**

Găsește navigarea existentă în `base.html` și adaugă:

```html
<a href="/email-jobs">Email Jobs</a>
```

- [ ] **Step 9.6: Rulează testele**

```
pytest tests/e2e/test_email_agent_routes.py -v
```

Așteptat: 4 PASSED

- [ ] **Step 9.7: Rulează suita completă să nu existe regresii**

```
pytest -v
```

Așteptat: toate testele existente + cele 4 noi PASSED

- [ ] **Step 9.8: Commit**

```
git add web/app.py web/templates/email_jobs.html web/templates/base.html tests/e2e/test_email_agent_routes.py
git commit -m "feat(web): email jobs dashboard — GET /email-jobs, POST /email-jobs/{id}/retry"
```

---

## Task 10: `.gitignore` + configurare OAuth2

**Fișiere:**
- Modificat: `.gitignore`

- [ ] **Step 10.1: Adaugă în `.gitignore`**

```
gmail_token.json
credentials.json
```

- [ ] **Step 10.2: Documentează în `.env.example` (dacă există) sau în comentariul din poller**

Adaugă la finalul `.env` (sau creează `.env.example`):

```
# Gmail Agent
GMAIL_CREDENTIALS_PATH=credentials.json
POLL_INTERVAL_SECONDS=120
```

- [ ] **Step 10.3: Commit**

```
git add .gitignore
git commit -m "chore: gitignore gmail_token.json and credentials.json"
```

---

## Task 11: Smoke test manual end-to-end

- [ ] **Step 11.1: Rulează suita completă de teste**

```
pytest -v
```

Așteptat: toate testele PASSED (niciun FAILED)

- [ ] **Step 11.2: Pornește serverul și verifică panoul**

```
.venv\Scripts\python -m uvicorn main:app --env-file .env --port 8000
```

Deschide `http://localhost:8000/email-jobs` — trebuie să afișeze tabelul gol cu mesajul "Niciun job procesat încă."

- [ ] **Step 11.3: Verifică navigarea**

Deschide `http://localhost:8000/` — trebuie să existe link "Email Jobs" în navigare.

- [ ] **Step 11.4: Commit final**

```
git add .
git commit -m "feat(email_agent): MVP complet — Gmail polling agent + panou monitorizare"
```
