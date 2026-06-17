# Agent Email Gmail — Plan de Implementare (v2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adaugă pe pagina principală un buton „Verifică cereri pe e-mail" cu interval de date; aplicația citește emailurile dintr-un inbox Gmail dedicat, extrage cererile de produse cu LLM și le prezintă ca o listă din care angajatul poate deschide direct sesiuni Discovery pre-completate.

**Architecture:** Modul nou `email_agent/` cu două fișiere (`gmail_client.py` + `email_extractor.py`). Două rute noi în `web/app.py`. UI pe `index.html`. Niciun tabel nou în DB — sesiunile Discovery create sunt identice cu cele create manual.

**Tech Stack:** Python 3.11+, FastAPI + Jinja2 (existente), SQLite (existent), `google-auth-oauthlib>=1.2`, `google-api-python-client>=2.120`, pytest (existent)

---

## Fișiere create / modificate

| Fișier | Acțiune | Responsabilitate |
|---|---|---|
| `email_agent/__init__.py` | Creat | Marker pachet |
| `email_agent/gmail_client.py` | Creat | OAuth2 + fetch emails by date range |
| `email_agent/email_extractor.py` | Creat | LLM: extrage ProductRequest-uri din email |
| `web/app.py` | Modificat | Adaugă `POST /email-agent/fetch` și `POST /email-agent/create-session` |
| `web/templates/index.html` | Modificat | Adaugă secțiunea cu câmpuri dată + buton |
| `web/templates/email_requests.html` | Creat | Lista de cereri extrase (parțial HTMX) |
| `tests/unit/test_email_extractor.py` | Creat | Teste extragere cereri din email |
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

- [ ] **Step 1.3: Adaugă în `.gitignore`** (la finalul fișierului, după secțiunea IDE)

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

Modulul expune o interfață clară (`fetch_emails`) pe care testele o vor mock-ui. Nu scriem teste de integrare pentru Gmail API real.

- [ ] **Step 2.1: Creează `email_agent/__init__.py`**

Fișier gol:
```python
```

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

## Task 3: `email_agent/email_extractor.py` — extragere cereri LLM

**Fișiere:**
- Creat: `email_agent/email_extractor.py`
- Test: `tests/unit/test_email_extractor.py`

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
        "description": "tricou polo navy cu broderie ECJ, font Bion Wide, 6 cm",
        "prefilled_state": {
          "tip_produs": "polo",
          "culoare": "navy",
          "branding": {"tehnica": "broderie", "text": "ECJ", "font": "Bion Wide", "dimensiune_cm": 6}
        }
      }
    ]""")
    requests = email_extractor.extract(_make_email("vreau tricouri polo navy cu broderie ECJ"), llm)
    assert len(requests) == 1
    assert requests[0].product_type == "tricou"
    assert requests[0].prefilled_state["culoare"] == "navy"
    assert requests[0].email_sender == "E-CABLAJE S.A. <office@ecablaje.ro>"


def test_extract_multiple_products():
    llm = FakeLLM("""[
      {
        "product_type": "tricou",
        "description": "tricouri polo navy",
        "prefilled_state": {"tip_produs": "polo", "culoare": "navy"}
      },
      {
        "product_type": "hanorac",
        "description": "hanorace gri fara personalizare",
        "prefilled_state": {"culoare": "gri"}
      },
      {
        "product_type": "tricou",
        "description": "jachete fleece negre",
        "prefilled_state": {"culoare": "negru"}
      }
    ]""")
    requests = email_extractor.extract(
        _make_email("vreau tricouri polo navy, hanorace gri si jachete fleece negre"), llm
    )
    assert len(requests) == 3


def test_extract_partial_fields_no_invention():
    llm = FakeLLM("""[
      {
        "product_type": "tricou",
        "description": "tricou polo cu broderie",
        "prefilled_state": {
          "branding": {"tehnica": "broderie"}
        }
      }
    ]""")
    requests = email_extractor.extract(_make_email("tricou polo cu broderie"), llm)
    assert len(requests) == 1
    assert "culoare" not in requests[0].prefilled_state


def test_extract_returns_empty_on_no_products():
    llm = FakeLLM("[]")
    requests = email_extractor.extract(_make_email("multumesc pentru colaborare"), llm)
    assert requests == []


def test_extract_handles_json_fenced_response():
    llm = FakeLLM('```json\n[{"product_type": "tricou", "description": "tricou alb", "prefilled_state": {"culoare": "alb"}}]\n```')
    requests = email_extractor.extract(_make_email("tricou alb"), llm)
    assert len(requests) == 1
    assert requests[0].prefilled_state["culoare"] == "alb"
```

- [ ] **Step 3.2: Rulează testele să confirmi că eșuează**

```
pytest tests/unit/test_email_extractor.py -v
```

Așteptat: FAIL — `cannot import name 'email_extractor'`

- [ ] **Step 3.3: Implementează `email_agent/email_extractor.py`**

```python
import json
from dataclasses import dataclass

from email_agent.gmail_client import EmailMessage
from schemas import loader


SYSTEM_PROMPT = """Ești un asistent care extrage cereri de produse personalizate din emailuri de business.

Emailurile sunt trimise de clienți care comandă produse textile personalizate (tricouri, hanorace, jachete, șepci etc.).

Sarcina ta: analizează corpul emailului și extrage FIECARE tip de produs menționat ca o cerere separată.

Pentru fiecare cerere returnează un obiect JSON cu:
- "product_type": tipul de produs (folosește exact una din valorile din lista furnizată)
- "description": descrierea brută a acelui produs din email (propoziție sau frază scurtă)
- "prefilled_state": obiect cu câmpurile pe care le poți extrage cu CERTITUDINE din email

IMPORTANT:
- Nu inventa valori. Dacă un câmp nu e menționat explicit, NU îl include în prefilled_state.
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


def extract(message: EmailMessage, llm) -> list[ProductRequest]:
    available_types = loader.available_product_types()
    user_content = json.dumps({
        "tipuri_disponibile": available_types,
        "expeditor": message.sender,
        "subiect": message.subject,
        "data": message.date,
        "corp_email": message.body_text[:3000],
    }, ensure_ascii=False)

    raw = llm.complete_text(system=SYSTEM_PROMPT, user=user_content)
    items = _parse_json_array(raw)

    return [
        ProductRequest(
            email_sender=message.sender,
            email_subject=message.subject,
            email_date=message.date,
            product_type=item["product_type"],
            description=item.get("description", ""),
            prefilled_state=item.get("prefilled_state", {}),
        )
        for item in items
        if item.get("product_type") in available_types
    ]


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

Așteptat: 5 PASSED

- [ ] **Step 3.5: Commit**

```
git add email_agent/email_extractor.py tests/unit/test_email_extractor.py
git commit -m "feat(email_agent): email_extractor — LLM product request extraction"
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
from email_agent.email_extractor import ProductRequest


class FakeGmail:
    def __init__(self, messages: list[EmailMessage]):
        self._messages = messages

    def fetch_emails(self, date_start: str, date_end: str) -> list[EmailMessage]:
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

    fake_gmail = FakeGmail([_make_email()])
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: fake_gmail)

    fake_llm.queue_text(json.dumps([{
        "product_type": "tricou",
        "description": "tricou polo navy cu broderie ECJ",
        "prefilled_state": {"culoare": "navy"},
    }]))

    r = client.post(
        "/email-agent/fetch",
        data={"date_start": "2026-06-01", "date_end": "2026-06-12"},
    )
    assert r.status_code == 200
    assert "tricou" in r.text
    assert "E-CABLAJE" in r.text


def test_fetch_empty_interval(client, monkeypatch):
    from web import app as web_app

    fake_gmail = FakeGmail([])
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: fake_gmail)

    r = client.post(
        "/email-agent/fetch",
        data={"date_start": "2026-06-01", "date_end": "2026-06-12"},
    )
    assert r.status_code == 200
    assert "Niciun email" in r.text


def test_create_session_from_request(client, fake_llm):
    prefilled = {"culoare": "navy", "branding": {"tehnica": "broderie"}}
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


def test_create_session_session_has_prefilled_state(client, fake_llm):
    prefilled = {"culoare": "navy"}
    fake_llm.queue_text(json.dumps({
        "state": {"culoare": "navy", "material": None},
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

- [ ] **Step 4.3: Adaugă rutele în `web/app.py`**

Adaugă după importurile existente:

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

Adaugă la sfârșitul rutelor (înainte de EOF):

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
            request,
            "email_requests.html",
            {"requests": [], "date_start": date_start, "date_end": date_end},
        )

    llm = get_llm_client()
    all_requests = []
    for msg in messages:
        extracted = email_extractor.extract(msg, llm)
        all_requests.extend(extracted)

    return TEMPLATES.TemplateResponse(
        request,
        "email_requests.html",
        {"requests": all_requests, "date_start": date_start, "date_end": date_end},
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

Așteptat: 4 PASSED

- [ ] **Step 4.5: Rulează suita completă**

```
pytest -v
```

Așteptat: toate testele existente PASSED + 4 noi

- [ ] **Step 4.6: Commit**

```
git add web/app.py tests/e2e/test_email_agent_routes.py
git commit -m "feat(web): POST /email-agent/fetch and /email-agent/create-session"
```

---

## Task 5: Template `web/templates/email_requests.html`

**Fișiere:**
- Creat: `web/templates/email_requests.html`

- [ ] **Step 5.1: Creează `web/templates/email_requests.html`**

```html
{% if requests %}
<section class="email-requests">
  <h2>Cereri extrase ({{ requests|length }})</h2>
  <p class="subtitle">
    Interval: {{ date_start }} – {{ date_end }}.
    Dă click pe „Deschide sesiune" pentru a porni Discovery cu câmpurile pre-completate.
  </p>

  <div class="request-list">
    {% for req in requests %}
    <div class="request-card">
      <div class="request-card__header">
        <span class="request-card__sender">{{ req.email_sender }}</span>
        <span class="request-card__date">{{ req.email_date }}</span>
        <span class="request-card__subject">{{ req.email_subject }}</span>
      </div>
      <div class="request-card__body">
        <span class="request-card__type">{{ req.product_type }}</span>
        <p class="request-card__desc">{{ req.description }}</p>
        {% if req.prefilled_state %}
        <ul class="request-card__fields">
          {% for key, val in req.prefilled_state.items() %}
          <li><strong>{{ key }}:</strong>
            {% if val is mapping %}
              {% for k2, v2 in val.items() %}{{ k2 }}: {{ v2 }}{% if not loop.last %}, {% endif %}{% endfor %}
            {% else %}
              {{ val }}
            {% endif %}
          </li>
          {% endfor %}
        </ul>
        {% endif %}
      </div>
      <div class="request-card__footer">
        <form method="post" action="/email-agent/create-session">
          <input type="hidden" name="product_type" value="{{ req.product_type }}">
          <input type="hidden" name="description" value="{{ req.description }}">
          <input type="hidden" name="prefilled_state_json" value="{{ req.prefilled_state | tojson }}">
          <button type="submit" class="btn"
            hx-post="/email-agent/create-session"
            hx-include="closest form"
            hx-target="body">
            Deschide sesiune →
          </button>
        </form>
      </div>
    </div>
    {% endfor %}
  </div>
</section>

{% else %}
<section class="email-requests email-requests--empty">
  <p>Niciun email găsit în intervalul <strong>{{ date_start }} – {{ date_end }}</strong>.</p>
</section>
{% endif %}
```

- [ ] **Step 5.2: Commit**

```
git add web/templates/email_requests.html
git commit -m "feat(web): email_requests template — lista cereri extrase"
```

---

## Task 6: UI pe pagina principală (`index.html`)

**Fișiere:**
- Modificat: `web/templates/index.html`

- [ ] **Step 6.1: Modifică `web/templates/index.html`**

Înlocuiește tot conținutul blocului `{% block content %}`:

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
        <div class="email-fetch-form__fields">
          <label>
            De la
            <input type="date" name="date_start" required>
          </label>
          <label>
            Până la
            <input type="date" name="date_end" required>
          </label>
        </div>
        <button type="submit" class="btn">
          Verifică cereri pe e-mail
        </button>
        <span id="email-fetch-spinner" class="htmx-indicator">Se încarcă…</span>
      </form>
      <div id="email-results"></div>
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

- [ ] **Step 6.2: Rulează suita de teste să nu existe regresii**

```
pytest -v
```

Așteptat: toate PASSED

- [ ] **Step 6.3: Commit**

```
git add web/templates/index.html
git commit -m "feat(web): add email fetch section to landing page"
```

---

## Task 7: Smoke test manual

- [ ] **Step 7.1: Pornește serverul**

```
.venv\Scripts\python -m uvicorn main:app --env-file .env --port 8000
```

- [ ] **Step 7.2: Verifică pagina principală**

Deschide `http://localhost:8000/` — trebuie să apară secțiunea „Cereri din e-mail" cu câmpurile dată + buton, deasupra cardurilor existente.

- [ ] **Step 7.3: Rulează suita completă de teste**

```
pytest -v
```

Așteptat: toate PASSED

- [ ] **Step 7.4: Commit final**

```
git add .
git commit -m "feat(email_agent): MVP Gmail agent — extragere cereri + sesiuni Discovery pre-completate"
```
