# Agent Email Gmail — Plan de Implementare (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adaugă pe pagina principală un buton „Verifică cereri pe e-mail" cu interval de date; aplicația citește emailurile dintr-un inbox Gmail dedicat, extrage cererile de produse cu LLM (folosind schema reală a fiecărui produs) și le prezintă grupate pe email sursă — cu chipuri pentru câmpurile extrase și câmpurile lipsă marcate — din care angajatul poate deschide direct sesiuni Discovery pre-completate.

**Architecture:** Modul nou `email_agent/` cu două fișiere (`gmail_client.py` + `email_extractor.py`). Două rute noi în `web/app.py`. UI pe `index.html` + `email_requests.html` + CSS nou în `styles.css`. Niciun tabel nou în DB — sesiunile Discovery create sunt identice cu cele create manual.

**Tech Stack:** Python 3.11+, FastAPI + Jinja2 (existente), SQLite (existent), `google-auth-oauthlib>=1.2`, `google-api-python-client>=2.120`, pytest (existent)

---

## Fișiere create / modificate

| Fișier | Acțiune | Responsabilitate |
|---|---|---|
| `email_agent/__init__.py` | Creat | Marker pachet |
| `email_agent/gmail_client.py` | Creat | OAuth2 + fetch emails by date range |
| `email_agent/email_extractor.py` | Creat | LLM extrage ProductRequest-uri folosind schema reală; calculează câmpurile lipsă |
| `web/app.py` | Modificat | Adaugă `POST /email-agent/fetch` și `POST /email-agent/create-session` |
| `web/templates/index.html` | Modificat | Adaugă secțiunea cu câmpuri dată + buton |
| `web/templates/email_requests.html` | Creat | Lista cereri grupată pe email, chipuri câmpuri, câmpuri lipsă |
| `web/static/styles.css` | Modificat | Stiluri noi: `.email-group`, `.request-card`, `.chip`, `.chip--missing`, `.badge-product` |
| `tests/unit/test_email_extractor.py` | Creat | Teste extragere + câmpuri lipsă |
| `tests/e2e/test_email_agent_routes.py` | Creat | Teste rute `/email-agent/*` |
| `requirements.txt` | Modificat | 2 dependențe noi |
| `.gitignore` | Modificat | `gmail_token.json`, `credentials.json` |

---

## Task 1: Dependențe + `.gitignore`

**Fișiere:**
- Modificat: `requirements.txt`
- Modificat: `.gitignore`

- [ ] **Step 1.1: Instalează dependențele**

```
.venv\Scripts\pip install "google-auth-oauthlib>=1.2" "google-api-python-client>=2.120"
```

- [ ] **Step 1.2: Adaugă în `requirements.txt`**

```
google-auth-oauthlib>=1.2
google-api-python-client>=2.120
```

- [ ] **Step 1.3: Adaugă în `.gitignore`** (la finalul fișierului)

```
# Gmail Agent
gmail_token.json
credentials.json
```

- [ ] **Step 1.4: Commit**

```
git add requirements.txt .gitignore
git commit -m "chore: add Gmail API dependencies and gitignore token files"
```

---

## Task 2: `email_agent/gmail_client.py`

**Fișiere:**
- Creat: `email_agent/__init__.py`
- Creat: `email_agent/gmail_client.py`

- [ ] **Step 2.1: Creează `email_agent/__init__.py`** (fișier gol)

- [ ] **Step 2.2: Implementează `email_agent/gmail_client.py`**

```python
import base64
import os
from dataclasses import dataclass, field
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


@dataclass
class EmailMessage:
    gmail_id: str
    sender: str
    subject: str
    body_text: str
    date: str  # RFC 2822 date string din header


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

    def fetch_emails(self, date_start: str, date_end: str) -> list[EmailMessage]:
        """Returnează emailurile primite între date_start și date_end (format YYYY-MM-DD)."""
        query = f"after:{date_start.replace('-', '/')} before:{date_end.replace('-', '/')}"
        result = self._service.users().messages().list(
            userId="me", q=query
        ).execute()
        messages = result.get("messages", [])
        return [self._fetch_and_parse(m["id"]) for m in messages]

    def _fetch_and_parse(self, msg_id: str) -> EmailMessage:
        msg = self._service.users().messages().get(
            userId="me", id=msg_id, format="full"
        ).execute()
        headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
        body_ref = [""]
        self._walk_parts(msg["payload"], body_ref)
        return EmailMessage(
            gmail_id=msg_id,
            sender=headers.get("From", ""),
            subject=headers.get("Subject", ""),
            body_text=body_ref[0],
            date=headers.get("Date", ""),
        )

    def _walk_parts(self, payload: dict, body_ref: list) -> None:
        mime = payload.get("mimeType", "")
        if mime == "text/plain" and not payload.get("filename"):
            data = payload.get("body", {}).get("data", "")
            if data:
                body_ref[0] += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        for part in payload.get("parts", []):
            self._walk_parts(part, body_ref)
```

- [ ] **Step 2.3: Commit**

```
git add email_agent/__init__.py email_agent/gmail_client.py
git commit -m "feat(email_agent): GmailClient — OAuth2 + fetch emails by date range"
```

---

## Task 3: `email_agent/email_extractor.py`

**Fișiere:**
- Creat: `email_agent/email_extractor.py`
- Test: `tests/unit/test_email_extractor.py`

### Ce face acest modul

1. Pentru fiecare email, construiește un prompt care include **schema reală** a fiecărui tip de produs disponibil (câmpuri, labels, hints) — LLM-ul returnează chei exacte din schemă, nu chei inventate.
2. După extracție, calculează `missing_fields` = câmpurile din schemă care **lipsesc** din `prefilled_state` — folosite în UI pentru chipurile galbene.

### Cum arată schema în prompt

`_schema_to_text(schema)` transformă `tricou.json` în:
```
  culoare_principala    — Culoare principală (ex: roșu, negru, alb melange)
  material              — Material (ex: bumbac 100%, poliester, mix)
  croiala               — Croială (regular / slim / oversize)
  guler                 — Tip guler (rotund / V / polo)
  maneci                — Mâneci (scurte / lungi / 3/4)
  branding.pozitie      — Poziție (ex: piept stâng, spate centru)
  branding.tehnica      — Tehnică (serigrafie / broderie / DTF / sublimare)
  branding.culori       — Culori (listă)
  branding.dimensiuni_aproximative — Dimensiuni aproximative (ex: 10cm x 10cm)
```

- [ ] **Step 3.1: Scrie testele care vor eșua**

Creează `tests/unit/test_email_extractor.py`:

```python
from email_agent.gmail_client import EmailMessage
from email_agent import email_extractor


class FakeLLM:
    def __init__(self, response: str):
        self._response = response
        self.calls: list = []

    def complete_text(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self._response


def _make_email(body: str, subject: str = "Cerere produse") -> EmailMessage:
    return EmailMessage(
        gmail_id="gid-1",
        sender="E-CABLAJE S.A. <office@ecablaje.ro>",
        subject=subject,
        body_text=body,
        date="Mon, 10 Jun 2026 09:00:00 +0300",
    )


def test_extract_single_product():
    llm = FakeLLM("""[
      {
        "product_type": "tricou",
        "description": "tricou polo navy cu broderie ECJ",
        "prefilled_state": {
          "culoare_principala": "navy",
          "guler": "polo",
          "branding": {"tehnica": "broderie", "culori": ["alb"]}
        }
      }
    ]""")
    requests = email_extractor.extract(_make_email("tricou polo navy cu broderie ECJ"), llm)
    assert len(requests) == 1
    assert requests[0].product_type == "tricou"
    assert requests[0].prefilled_state["culoare_principala"] == "navy"
    assert requests[0].email_sender == "E-CABLAJE S.A. <office@ecablaje.ro>"


def test_extract_multiple_products():
    llm = FakeLLM("""[
      {
        "product_type": "tricou",
        "description": "tricouri polo navy",
        "prefilled_state": {"culoare_principala": "navy", "guler": "polo"}
      },
      {
        "product_type": "tricou",
        "description": "tricouri albe maneci lungi",
        "prefilled_state": {"culoare_principala": "alb", "maneci": "lungi"}
      }
    ]""")
    requests = email_extractor.extract(
        _make_email("vreau tricouri polo navy si tricouri albe maneci lungi"), llm
    )
    assert len(requests) == 2


def test_extract_partial_fields_no_invention():
    llm = FakeLLM("""[
      {
        "product_type": "tricou",
        "description": "tricou polo cu broderie",
        "prefilled_state": {
          "guler": "polo",
          "branding": {"tehnica": "broderie"}
        }
      }
    ]""")
    requests = email_extractor.extract(_make_email("tricou polo cu broderie"), llm)
    assert len(requests) == 1
    # culoare_principala nu e menționată — nu trebuie să apară în prefilled_state
    assert "culoare_principala" not in requests[0].prefilled_state


def test_missing_fields_calculated_correctly():
    llm = FakeLLM("""[
      {
        "product_type": "tricou",
        "description": "tricou polo navy",
        "prefilled_state": {
          "culoare_principala": "navy",
          "guler": "polo"
        }
      }
    ]""")
    requests = email_extractor.extract(_make_email("tricou polo navy"), llm)
    assert len(requests) == 1
    # material, croiala, maneci, branding.* lipsesc din prefilled_state
    assert "material" in requests[0].missing_fields
    assert "croiala" in requests[0].missing_fields
    assert "branding.tehnica" in requests[0].missing_fields
    # câmpurile cunoscute NU sunt în missing_fields
    assert "culoare_principala" not in requests[0].missing_fields
    assert "guler" not in requests[0].missing_fields


def test_extract_returns_empty_on_no_products():
    llm = FakeLLM("[]")
    requests = email_extractor.extract(_make_email("multumesc pentru colaborare"), llm)
    assert requests == []


def test_extract_handles_json_fenced_response():
    llm = FakeLLM('```json\n[{"product_type": "tricou", "description": "tricou alb", "prefilled_state": {"culoare_principala": "alb"}}]\n```')
    requests = email_extractor.extract(_make_email("tricou alb"), llm)
    assert len(requests) == 1
    assert requests[0].prefilled_state["culoare_principala"] == "alb"


def test_prompt_includes_schema_fields(monkeypatch):
    """Verifică că promptul trimis LLM-ului conține câmpurile reale din schemă."""
    calls = []

    class CaptureLLM:
        def complete_text(self, system, user):
            calls.append(user)
            return "[]"

    email_extractor.extract(_make_email("test"), CaptureLLM())
    assert len(calls) == 1
    assert "culoare_principala" in calls[0]
    assert "branding.tehnica" in calls[0]
```

- [ ] **Step 3.2: Rulează testele să confirmi că eșuează**

```
pytest tests/unit/test_email_extractor.py -v
```

Așteptat: FAIL — `cannot import name 'email_extractor'`

- [ ] **Step 3.3: Implementează `email_agent/email_extractor.py`**

```python
import json
from dataclasses import dataclass, field

from email_agent.gmail_client import EmailMessage
from schemas import loader


SYSTEM_PROMPT = """Ești un asistent care extrage cereri de produse personalizate din emailuri de business.

Emailurile sunt trimise de clienți care comandă produse textile personalizate.

Sarcina ta: analizează corpul emailului și extrage FIECARE tip de produs menționat ca o cerere separată.

Pentru fiecare cerere returnează un obiect JSON cu:
- "product_type": tipul de produs (folosește EXACT una din valorile din lista furnizată)
- "description": descrierea brută a acelui produs din email (1-2 propoziții)
- "prefilled_state": obiect cu câmpurile pe care le poți extrage cu CERTITUDINE din email,
  folosind EXACT cheile din schema furnizată (inclusiv notația cu punct pentru subcâmpuri,
  ex: "branding.tehnica", NU "branding": {"tehnica": ...} pentru câmpuri individuale —
  EXCEPȚIE: dacă extragi mai multe subcâmpuri ale aceluiași obiect, grupează-le în obiect)

IMPORTANT:
- Nu inventa valori. Dacă un câmp nu e menționat explicit în email, NU îl include.
- Folosește EXACT cheile din schema — nu traduce, nu redenumi.
- Returnează un array JSON, chiar dacă e gol ([]).
- Răspunde EXCLUSIV cu JSON valid, fără text suplimentar."""


@dataclass
class ProductRequest:
    email_sender: str
    email_subject: str
    email_date: str
    product_type: str
    description: str
    prefilled_state: dict
    missing_fields: list[str] = field(default_factory=list)


def extract(message: EmailMessage, llm) -> list[ProductRequest]:
    available_types = loader.available_product_types()

    # Construiește textul schemelor pentru toate tipurile disponibile
    schemas_text = ""
    schemas_map = {}
    for ptype in available_types:
        schema = loader.load_schema(ptype)
        schemas_map[ptype] = schema
        schemas_text += f'\nSchema pentru "{ptype}":\n{_schema_to_text(schema)}\n'

    user_content = json.dumps({
        "tipuri_disponibile": available_types,
        "scheme": schemas_text,
        "expeditor": message.sender,
        "subiect": message.subject,
        "data": message.date,
        "corp_email": message.body_text[:3000],
    }, ensure_ascii=False)

    raw = llm.complete_text(system=SYSTEM_PROMPT, user=user_content)
    items = _parse_json_array(raw)

    result = []
    for item in items:
        ptype = item.get("product_type")
        if ptype not in available_types:
            continue
        prefilled = item.get("prefilled_state", {})
        schema = schemas_map[ptype]
        missing = _compute_missing_fields(schema, prefilled)
        result.append(ProductRequest(
            email_sender=message.sender,
            email_subject=message.subject,
            email_date=message.date,
            product_type=ptype,
            description=item.get("description", ""),
            prefilled_state=prefilled,
            missing_fields=missing,
        ))
    return result


def _schema_to_text(schema: dict) -> str:
    lines = []
    for f in schema["fields"]:
        if f.get("type") == "object":
            for sub in f["subfields"]:
                key = f"{f['key']}.{sub['key']}"
                hint = sub.get("hint", "")
                lines.append(f"  {key:<45} — {sub['label']}{' (' + hint + ')' if hint else ''}")
        else:
            hint = f.get("hint", "")
            lines.append(f"  {f['key']:<45} — {f['label']}{' (' + hint + ')' if hint else ''}")
    return "\n".join(lines)


def _compute_missing_fields(schema: dict, prefilled_state: dict) -> list[str]:
    """Returnează cheile din schemă care lipsesc din prefilled_state."""
    all_keys = loader.leaf_keys(schema)
    missing = []
    for dotted_key in all_keys:
        parts = dotted_key.split(".")
        val = prefilled_state
        for p in parts:
            if not isinstance(val, dict) or p not in val:
                missing.append(dotted_key)
                break
            val = val[p]
    return missing


def _parse_json_array(text: str) -> list:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            return []
        return json.loads(text[start:end + 1])
```

- [ ] **Step 3.4: Rulează testele**

```
pytest tests/unit/test_email_extractor.py -v
```

Așteptat: 7 PASSED

- [ ] **Step 3.5: Commit**

```
git add email_agent/email_extractor.py tests/unit/test_email_extractor.py
git commit -m "feat(email_agent): email_extractor — schema-aware LLM extraction + missing fields"
```

---

## Task 4: Rute web `POST /email-agent/fetch` și `POST /email-agent/create-session`

**Fișiere:**
- Modificat: `web/app.py`
- Test: `tests/e2e/test_email_agent_routes.py`

- [ ] **Step 4.1: Scrie testele care vor eșua**

Creează `tests/e2e/test_email_agent_routes.py`:

```python
import json
from email_agent.gmail_client import EmailMessage


class FakeGmail:
    def __init__(self, messages):
        self._messages = messages

    def fetch_emails(self, date_start, date_end):
        return self._messages


def _make_email(body="tricou polo navy cu broderie ECJ"):
    return EmailMessage(
        gmail_id="gid-1",
        sender="E-CABLAJE S.A. <office@ecablaje.ro>",
        subject="Cerere produse iunie",
        body_text=body,
        date="Mon, 10 Jun 2026 09:00:00 +0300",
    )


def test_fetch_returns_list_with_results(client, fake_llm, monkeypatch):
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: FakeGmail([_make_email()]))

    fake_llm.queue_text(json.dumps([{
        "product_type": "tricou",
        "description": "tricou polo navy cu broderie ECJ",
        "prefilled_state": {"culoare_principala": "navy", "guler": "polo"},
    }]))

    r = client.post(
        "/email-agent/fetch",
        data={"date_start": "2026-06-01", "date_end": "2026-06-12"},
    )
    assert r.status_code == 200
    assert "tricou" in r.text
    assert "E-CABLAJE" in r.text
    assert "navy" in r.text


def test_fetch_shows_missing_fields(client, fake_llm, monkeypatch):
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: FakeGmail([_make_email()]))

    fake_llm.queue_text(json.dumps([{
        "product_type": "tricou",
        "description": "tricou polo navy",
        "prefilled_state": {"culoare_principala": "navy"},
    }]))

    r = client.post(
        "/email-agent/fetch",
        data={"date_start": "2026-06-01", "date_end": "2026-06-12"},
    )
    assert r.status_code == 200
    # câmpurile lipsă trebuie să apară în HTML
    assert "material" in r.text


def test_fetch_groups_by_email(client, fake_llm, monkeypatch):
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: FakeGmail([_make_email()]))

    # un email cu 2 cereri
    fake_llm.queue_text(json.dumps([
        {"product_type": "tricou", "description": "polo navy", "prefilled_state": {"culoare_principala": "navy"}},
        {"product_type": "tricou", "description": "tricou alb", "prefilled_state": {"culoare_principala": "alb"}},
    ]))

    r = client.post(
        "/email-agent/fetch",
        data={"date_start": "2026-06-01", "date_end": "2026-06-12"},
    )
    assert r.status_code == 200
    # expeditorul apare o singură dată (grupare)
    assert r.text.count("E-CABLAJE") == 1


def test_fetch_empty_interval(client, monkeypatch):
    from web import app as web_app
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: FakeGmail([]))

    r = client.post(
        "/email-agent/fetch",
        data={"date_start": "2026-06-01", "date_end": "2026-06-12"},
    )
    assert r.status_code == 200
    assert "Niciun email" in r.text


def test_create_session_from_request(client, fake_llm):
    prefilled = {"culoare_principala": "navy", "branding": {"tehnica": "broderie"}}
    fake_llm.queue_text(json.dumps({
        "state": prefilled,
        "intrebari": [{"camp": "material", "intrebare": "Ce material?"}],
        "done": False,
    }))

    r = client.post(
        "/email-agent/create-session",
        data={
            "product_type": "tricou",
            "description": "tricou polo navy cu broderie ECJ",
            "prefilled_state_json": json.dumps(prefilled),
        },
    )
    assert r.status_code == 200
    assert "HX-Redirect" in r.headers
    assert r.headers["HX-Redirect"].startswith("/sessions/")


def test_create_session_has_prefilled_state(client, fake_llm):
    prefilled = {"culoare_principala": "navy"}
    fake_llm.queue_text(json.dumps({
        "state": {"culoare_principala": "navy"},
        "intrebari": [{"camp": "material", "intrebare": "Ce material?"}],
        "done": False,
    }))

    r = client.post(
        "/email-agent/create-session",
        data={
            "product_type": "tricou",
            "description": "tricou polo navy",
            "prefilled_state_json": json.dumps(prefilled),
        },
    )
    session_url = r.headers["HX-Redirect"]
    r2 = client.get(session_url)
    assert r2.status_code == 200
    assert "navy" in r2.text
```

- [ ] **Step 4.2: Rulează testele să confirmi că eșuează**

```
pytest tests/e2e/test_email_agent_routes.py -v
```

Așteptat: FAIL — rutele nu există

- [ ] **Step 4.3: Adaugă în `web/app.py`**

După importurile existente:

```python
from email_agent.gmail_client import GmailClient
from email_agent import email_extractor

_gmail_singleton = None

def get_gmail_client():
    global _gmail_singleton
    if _gmail_singleton is None:
        _gmail_singleton = GmailClient()
    return _gmail_singleton
```

Rute noi la sfârșitul fișierului:

```python
@app.post("/email-agent/fetch", response_class=HTMLResponse)
def email_agent_fetch(
    request: Request,
    date_start: str = Form(...),
    date_end: str = Form(...),
):
    gmail = get_gmail_client()
    messages = gmail.fetch_emails(date_start, date_end)

    if not messages:
        return TEMPLATES.TemplateResponse(
            request, "email_requests.html",
            {"groups": [], "date_start": date_start, "date_end": date_end},
        )

    llm = get_llm_client()
    # Grupăm cererile pe email sursă: list of {email, requests}
    groups = []
    for msg in messages:
        extracted = email_extractor.extract(msg, llm)
        if extracted:
            groups.append({"email": msg, "requests": extracted})

    return TEMPLATES.TemplateResponse(
        request, "email_requests.html",
        {"groups": groups, "date_start": date_start, "date_end": date_end},
    )


@app.post("/email-agent/create-session")
def email_agent_create_session(
    product_type: str = Form(...),
    description: str = Form(...),
    prefilled_state_json: str = Form(...),
):
    prefilled_state = json.loads(prefilled_state_json)
    schema = loader.load_schema(product_type)

    llm = get_llm_client()
    system, user = discovery.build_messages(
        schema=schema,
        initial_description=description,
        state=prefilled_state,
        history=[],
    )
    raw = llm.complete_text(system=system, user=user)
    step = discovery.parse_response(raw)

    merged_state = discovery.merge_answers(prefilled_state, step.state)

    with get_conn() as conn:
        sid = repository.create_session(conn, product_type, description)
        history = [{"round": 1, "questions": step.intrebari, "answers": None}]
        repository.update_session_state(conn, sid, merged_state, history, rounds=1)
        if step.done:
            complete, _ = discovery.is_schema_complete(schema, merged_state)
            if complete:
                repository.finalize_session(conn, sid)

    return Response(status_code=200, headers={"HX-Redirect": f"/sessions/{sid}"})
```

- [ ] **Step 4.4: Rulează testele**

```
pytest tests/e2e/test_email_agent_routes.py -v
```

Așteptat: 6 PASSED

- [ ] **Step 4.5: Rulează suita completă**

```
pytest -v
```

Așteptat: toate testele existente + 6 noi PASSED

- [ ] **Step 4.6: Commit**

```
git add web/app.py tests/e2e/test_email_agent_routes.py
git commit -m "feat(web): POST /email-agent/fetch (grouped) and /email-agent/create-session"
```

---

## Task 5: CSS pentru componentele noi

**Fișiere:**
- Modificat: `web/static/styles.css`

- [ ] **Step 5.1: Adaugă la sfârșitul `web/static/styles.css`**

```css
/* ========== Email Agent — cereri din email ========== */

/* Secțiunea de pe landing */
.email-fetch-section {
  margin-bottom: var(--s-6);
  padding-bottom: var(--s-6);
  border-bottom: 1px solid var(--c-border);
}
.email-fetch-section h2 {
  font-size: 18px;
  margin-bottom: var(--s-4);
}
.email-fetch-form {
  display: flex;
  align-items: flex-end;
  gap: var(--s-4);
  flex-wrap: wrap;
}
.email-fetch-form label {
  display: flex;
  flex-direction: column;
  gap: var(--s-2);
  font-size: 13px;
  font-weight: 600;
  color: var(--c-text-muted);
}
.email-fetch-form input[type="date"] {
  font-family: inherit;
  font-size: 14px;
  padding: 8px 12px;
  border: 1px solid var(--c-border-2);
  border-radius: var(--r-md);
  background: var(--c-surface);
  color: var(--c-text);
  min-width: 160px;
}
.email-fetch-form input[type="date"]:focus {
  outline: none;
  border-color: var(--c-info);
  box-shadow: 0 0 0 3px rgba(30,41,59,0.1);
}
.htmx-indicator { display: none; font-size: 13px; color: var(--c-text-soft); }
.htmx-request .htmx-indicator { display: inline; }

/* Sumarul rezultatelor */
.email-results-summary {
  display: flex;
  align-items: center;
  gap: var(--s-4);
  padding: 10px 14px;
  background: var(--c-accent-soft);
  border: 1px solid #BBF7D0;
  border-radius: var(--r-md);
  font-size: 13px;
  color: var(--c-accent-ink);
  margin-bottom: var(--s-5);
}

/* Grup email */
.email-group { margin-bottom: var(--s-6); }
.email-group__header {
  display: flex;
  align-items: center;
  gap: var(--s-3);
  padding: 10px 14px;
  background: var(--c-surface-2);
  border: 1px solid var(--c-border);
  border-radius: var(--r-lg) var(--r-lg) 0 0;
}
.email-group__avatar {
  width: 32px; height: 32px;
  background: var(--c-info);
  color: #fff;
  border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700;
  flex-shrink: 0;
}
.email-group__info { flex: 1; min-width: 0; }
.email-group__sender {
  font-weight: 600;
  font-size: 14px;
  color: var(--c-text);
  display: block;
}
.email-group__subject {
  font-size: 12px;
  color: var(--c-text-soft);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
}
.email-group__date {
  font-size: 12px;
  color: var(--c-text-soft);
  flex-shrink: 0;
}

/* Card cerere */
.request-card {
  background: var(--c-surface);
  border: 1px solid var(--c-border);
  border-top: none;
  padding: var(--s-4) var(--s-5);
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--s-4);
  align-items: start;
}
.request-card:last-child {
  border-radius: 0 0 var(--r-lg) var(--r-lg);
}
.request-card + .request-card {
  border-top: 1px dashed var(--c-border);
}

/* Badge tip produs */
.badge-product {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 999px;
  background: #E0E7FF;
  color: #312E81;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin-bottom: var(--s-2);
}

/* Descriere brută */
.request-card__desc {
  font-size: 13px;
  color: var(--c-text-soft);
  font-style: italic;
  margin: var(--s-2) 0 var(--s-3);
}

/* Chipuri câmpuri */
.field-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s-2);
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 3px 10px;
  border-radius: var(--r-sm);
  border: 1px solid var(--c-border);
  background: var(--c-surface-2);
  color: var(--c-text);
}
.chip__key {
  font-weight: 600;
  color: var(--c-text-soft);
  font-size: 11px;
}
.chip__val { font-weight: 500; }
.chip--missing {
  background: var(--c-warn-soft);
  border-color: #FDE68A;
  color: var(--c-warn-ink);
  font-size: 11px;
  font-style: italic;
}

/* Stare goală */
.email-results-empty {
  padding: var(--s-7) var(--s-5);
  text-align: center;
  color: var(--c-text-soft);
  font-size: 14px;
}

/* Separator landing */
.divider {
  border: none;
  border-top: 1px solid var(--c-border);
  margin: var(--s-6) 0;
}
```

- [ ] **Step 5.2: Commit**

```
git add web/static/styles.css
git commit -m "feat(web): CSS pentru email agent — email-group, request-card, chip"
```

---

## Task 6: Template `web/templates/email_requests.html`

**Fișiere:**
- Creat: `web/templates/email_requests.html`

- [ ] **Step 6.1: Creează `web/templates/email_requests.html`**

```html
{% if groups %}
<div class="email-results-summary">
  <span>✓ <strong>{{ groups|sum(attribute='requests')|list|length }} cereri</strong> extrase</span>
  <span>·</span>
  <span><strong>{{ groups|length }} email{% if groups|length != 1 %}uri{% endif %}</strong> procesate</span>
  <span>·</span>
  <span>Câmpurile cunoscute sunt pre-completate — Discovery va întreba doar ce lipsește</span>
</div>

{% for group in groups %}
<div class="email-group">
  <div class="email-group__header">
    <div class="email-group__avatar">
      {{ group.email.sender | truncate(2, True, '') | upper }}
    </div>
    <div class="email-group__info">
      <span class="email-group__sender">{{ group.email.sender }}</span>
      <span class="email-group__subject">{{ group.email.subject }}</span>
    </div>
    <span class="email-group__date">{{ group.email.date }}</span>
  </div>

  {% for req in group.requests %}
  <div class="request-card">
    <div>
      <span class="badge-product">{{ req.product_type }}</span>
      {% if group.requests|length > 1 %}
      <span style="font-size:12px;color:var(--c-text-soft);margin-left:8px;">
        cerere {{ loop.index }} din {{ group.requests|length }}
      </span>
      {% endif %}

      <p class="request-card__desc">„{{ req.description }}"</p>

      <div class="field-chips">
        {% for key, val in req.prefilled_state.items() %}
          {% if val is mapping %}
            {% for k2, v2 in val.items() %}
            <div class="chip">
              <span class="chip__key">{{ key }}.{{ k2 }}</span>
              <span class="chip__val">
                {% if v2 is iterable and v2 is not string %}{{ v2 | join(', ') }}{% else %}{{ v2 }}{% endif %}
              </span>
            </div>
            {% endfor %}
          {% else %}
          <div class="chip">
            <span class="chip__key">{{ key }}</span>
            <span class="chip__val">
              {% if val is iterable and val is not string %}{{ val | join(', ') }}{% else %}{{ val }}{% endif %}
            </span>
          </div>
          {% endif %}
        {% endfor %}

        {% for missing_key in req.missing_fields %}
        <div class="chip chip--missing">{{ missing_key }} — necunoscut</div>
        {% endfor %}
      </div>
    </div>

    <form method="post" action="/email-agent/create-session">
      <input type="hidden" name="product_type" value="{{ req.product_type }}">
      <input type="hidden" name="description" value="{{ req.description }}">
      <input type="hidden" name="prefilled_state_json" value="{{ req.prefilled_state | tojson }}">
      <button type="submit" class="btn btn--primary"
        hx-post="/email-agent/create-session"
        hx-include="closest form"
        hx-target="body">
        Deschide sesiune →
      </button>
    </form>
  </div>
  {% endfor %}
</div>
{% endfor %}

{% else %}
<div class="email-results-empty">
  Niciun email găsit în intervalul <strong>{{ date_start }} – {{ date_end }}</strong>.
</div>
{% endif %}
```

- [ ] **Step 6.2: Commit**

```
git add web/templates/email_requests.html
git commit -m "feat(web): email_requests template — grupat pe email, chipuri câmpuri, lipsă marcate"
```

---

## Task 7: UI pe pagina principală (`index.html`)

**Fișiere:**
- Modificat: `web/templates/index.html`

- [ ] **Step 7.1: Înlocuiește tot conținutul `web/templates/index.html`**

```html
{% extends "base.html" %}
{% block title %}Ciptronic Validator{% endblock %}
{% block content %}
<main class="page page--narrow">
    <h1>Validare produs personalizat</h1>

    <section class="email-fetch-section">
      <h2>Cereri din e-mail</h2>
      <form
        hx-post="/email-agent/fetch"
        hx-target="#email-results"
        hx-swap="innerHTML"
        hx-indicator="#email-fetch-spinner"
        class="email-fetch-form"
      >
        <label>
          De la
          <input type="date" name="date_start" required>
        </label>
        <label>
          Până la
          <input type="date" name="date_end" required>
        </label>
        <button type="submit" class="btn btn--primary">
          Verifică cereri pe e-mail
        </button>
        <span id="email-fetch-spinner" class="htmx-indicator">Se încarcă…</span>
      </form>
      <div id="email-results" style="margin-top: var(--s-5);"></div>
    </section>

    <hr class="divider">

    <p>Sau pornește manual un flux nou:</p>

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

- [ ] **Step 7.2: Rulează suita completă**

```
pytest -v
```

Așteptat: toate PASSED

- [ ] **Step 7.3: Commit**

```
git add web/templates/index.html
git commit -m "feat(web): landing page — secțiune email fetch cu HTMX"
```

---

## Task 8: Smoke test manual

- [ ] **Step 8.1: Pornește serverul**

```
.venv\Scripts\python -m uvicorn main:app --env-file .env --port 8000
```

- [ ] **Step 8.2: Verifică pagina principală**

Deschide `http://localhost:8000/` — trebuie să apară secțiunea „Cereri din e-mail" cu câmpurile dată + buton, deasupra separatorului și cardurilor existente.

- [ ] **Step 8.3: Rulează suita completă de teste**

```
pytest -v
```

Așteptat: toate PASSED

- [ ] **Step 8.4: Commit final**

```
git add .
git commit -m "feat(email_agent): MVP Gmail agent — extragere schema-aware, grupare email, UI complet"
```
