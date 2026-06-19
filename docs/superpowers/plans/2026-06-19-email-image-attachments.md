# Email Image Attachments Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extrage imaginile din emailurile Gmail, stochează-le pe disc, trimite-le la LLM vision pentru extragerea câmpurilor vizuale, și afișează thumbnails în UI.

**Architecture:** `GmailClient` descarcă imaginile (inline sau via `attachmentId` pentru fișiere mari), le redimensionează la max 1024px și le salvează în `uploads/email_images/{gmail_id}/`. `email_extractor.extract()` alege între `complete_text()` și `complete_vision()` pe baza prezenței `image_paths`. O nouă rută web servește imaginile stocate pentru thumbnails în template.

**Tech Stack:** Python 3.10+, FastAPI, Pillow (deja instalat), Anthropic SDK vision, pytest

---

## Fișiere atinse

| Fișier | Modificare |
|--------|-----------|
| `email_agent/gmail_client.py` | `EmailMessage` + câmpuri noi, `_resize_image`, `_get_part_bytes`, `_walk_parts`, `_fetch_and_parse`, `image_save_dir` |
| `email_agent/email_extractor.py` | system prompt cu imagini, ramură `complete_vision` în `extract()` |
| `web/app.py` | `get_gmail_client()` injectează `image_save_dir`, rută nouă `/email-agent/image/{gmail_id}/{idx}` |
| `web/templates/email_requests.html` | thumbnails în `.email-group__info` |
| `web/static/styles.css` | clase `.email-group__thumbs`, `.email-thumb` |
| `tests/unit/test_gmail_client.py` | **creat nou** — teste pentru `_resize_image`, `_get_part_bytes`, `_walk_parts`, `_fetch_and_parse` |
| `tests/unit/test_email_extractor.py` | teste pentru ramura vision |
| `tests/e2e/test_email_agent_routes.py` | teste pentru ruta `/email-agent/image/` |

---

## Task 1: `EmailMessage` + `_resize_image`

**Files:**
- Modify: `email_agent/gmail_client.py`
- Create: `tests/unit/test_gmail_client.py`

- [ ] **Step 1: Crează fișierul de test și scrie testele pentru `_resize_image`**

Crează `tests/unit/test_gmail_client.py`:

```python
import base64
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image

from email_agent.gmail_client import EmailMessage, GmailClient, _resize_image


# ── helpers ──────────────────────────────────────────────────────────────────

def _png_bytes(w: int = 2000, h: int = 1500) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color=(100, 150, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _make_client(image_save_dir=None) -> GmailClient:
    """GmailClient cu __post_init__ ocolit — fără OAuth."""
    c = object.__new__(GmailClient)
    c.credentials_path = "creds.json"
    c.token_path = "token.json"
    c.image_save_dir = image_save_dir
    c._service = MagicMock()
    return c


# ── _resize_image ─────────────────────────────────────────────────────────────

def test_resize_image_caps_at_1024px():
    result = _resize_image(_png_bytes(2000, 1500))
    img = Image.open(BytesIO(result))
    assert max(img.size) <= 1024


def test_resize_image_output_is_jpeg():
    result = _resize_image(_png_bytes())
    img = Image.open(BytesIO(result))
    assert img.format == "JPEG"


def test_resize_image_small_image_not_upscaled():
    result = _resize_image(_png_bytes(100, 80))
    img = Image.open(BytesIO(result))
    assert img.size == (100, 80)
```

- [ ] **Step 2: Rulează testele — trebuie să PICEZE (ImportError)**

```bash
cd /Users/raduorghidan/Documents/work/tudor_radu/ciptronic-validator
.venv/bin/python -m pytest tests/unit/test_gmail_client.py -v 2>&1 | head -20
```

Expected: `ImportError: cannot import name '_resize_image' from 'email_agent.gmail_client'`

- [ ] **Step 3: Extinde `EmailMessage` și adaugă `_resize_image` în `email_agent/gmail_client.py`**

Adaugă `import io` și `from PIL import Image` la începutul fișierului (după importurile existente):

```python
import base64
import io
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from PIL import Image
```

Înlocuiește dataclass-ul `EmailMessage` existent:

```python
@dataclass
class EmailMessage:
    gmail_id: str
    sender: str
    subject: str
    body_text: str
    date: str  # RFC 2822 date string din header
    image_paths: list[str] = field(default_factory=list)
    other_attachment_names: list[str] = field(default_factory=list)
```

Adaugă funcția `_resize_image` la nivel de modul, **înainte** de clasa `GmailClient`:

```python
def _resize_image(data: bytes, max_px: int = 1024) -> bytes:
    img = Image.open(io.BytesIO(data))
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=85)
    return out.getvalue()
```

- [ ] **Step 4: Rulează testele — trebuie să TREACĂ**

```bash
.venv/bin/python -m pytest tests/unit/test_gmail_client.py -v
```

Expected: `3 passed`

- [ ] **Step 5: Verifică că testele existente nu s-au stricat**

```bash
.venv/bin/python -m pytest tests/unit/test_email_extractor.py tests/e2e/ -v
```

Expected: toate testele existente trec (EmailMessage are acum câmpuri cu default — calls existente rămân compatibile).

- [ ] **Step 6: Commit**

```bash
git add email_agent/gmail_client.py tests/unit/test_gmail_client.py
git commit -m "feat(email-agent): EmailMessage cu image_paths + _resize_image"
```

---

## Task 2: `GmailClient._get_part_bytes`

**Files:**
- Modify: `email_agent/gmail_client.py`
- Modify: `tests/unit/test_gmail_client.py`

- [ ] **Step 1: Adaugă testele pentru `_get_part_bytes` în `tests/unit/test_gmail_client.py`**

Adaugă la finalul fișierului:

```python
# ── _get_part_bytes ───────────────────────────────────────────────────────────

def test_get_part_bytes_inline_data():
    client = _make_client()
    raw = b"hello image bytes"
    encoded = base64.urlsafe_b64encode(raw).decode()
    result = client._get_part_bytes({"data": encoded}, "msg-1")
    assert result == raw
    client._service.users.return_value.messages.return_value.attachments.assert_not_called()


def test_get_part_bytes_fetches_attachment_id():
    client = _make_client()
    raw = b"large image bytes"
    encoded = base64.urlsafe_b64encode(raw).decode()
    (
        client._service.users.return_value
        .messages.return_value
        .attachments.return_value
        .get.return_value
        .execute.return_value
    ) = {"data": encoded}

    result = client._get_part_bytes({"attachmentId": "att-123"}, "msg-1")

    assert result == raw
    (
        client._service.users.return_value
        .messages.return_value
        .attachments.return_value
        .get.assert_called_once_with(userId="me", messageId="msg-1", id="att-123")
    )


def test_get_part_bytes_returns_none_when_empty():
    client = _make_client()
    assert client._get_part_bytes({}, "msg-1") is None
```

- [ ] **Step 2: Rulează testele noi — trebuie să PICEZE**

```bash
.venv/bin/python -m pytest tests/unit/test_gmail_client.py::test_get_part_bytes_inline_data -v
```

Expected: `AttributeError: '_get_part_bytes'`

- [ ] **Step 3: Adaugă metoda `_get_part_bytes` în clasa `GmailClient` din `email_agent/gmail_client.py`**

Adaugă metoda după `__post_init__`, înainte de `get_address`:

```python
def _get_part_bytes(self, body: dict, msg_id: str) -> bytes | None:
    data = body.get("data", "")
    if data:
        return base64.urlsafe_b64decode(data)
    att_id = body.get("attachmentId")
    if att_id:
        att = self._service.users().messages().attachments().get(
            userId="me", messageId=msg_id, id=att_id
        ).execute()
        return base64.urlsafe_b64decode(att.get("data", ""))
    return None
```

- [ ] **Step 4: Rulează toate testele din `test_gmail_client.py` — trebuie să TREACĂ**

```bash
.venv/bin/python -m pytest tests/unit/test_gmail_client.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add email_agent/gmail_client.py tests/unit/test_gmail_client.py
git commit -m "feat(email-agent): GmailClient._get_part_bytes cu suport attachmentId"
```

---

## Task 3: `GmailClient._walk_parts` + `_fetch_and_parse` + `image_save_dir`

**Files:**
- Modify: `email_agent/gmail_client.py`
- Modify: `tests/unit/test_gmail_client.py`

- [ ] **Step 1: Adaugă testele în `tests/unit/test_gmail_client.py`**

Adaugă la finalul fișierului:

```python
# ── _walk_parts ───────────────────────────────────────────────────────────────

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode()


def test_walk_parts_collects_text():
    client = _make_client()
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64(b"hello email")}, "filename": None},
        ],
    }
    body_ref, images_ref, names_ref = [""], [], []
    client._walk_parts(payload, body_ref, images_ref, names_ref, "msg-1")
    assert body_ref[0] == "hello email"


def test_walk_parts_collects_image():
    client = _make_client()
    raw_img = _png_bytes(50, 50)
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {
                "mimeType": "image/jpeg",
                "filename": "test.jpg",
                "body": {"data": _b64(raw_img)},
            },
        ],
    }
    body_ref, images_ref, names_ref = [""], [], []
    client._walk_parts(payload, body_ref, images_ref, names_ref, "msg-1")
    assert len(images_ref) == 1
    img = Image.open(BytesIO(images_ref[0]))
    assert img.format == "JPEG"


def test_walk_parts_collects_pdf_name():
    client = _make_client()
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "application/pdf", "filename": "logo.pdf", "body": {}},
        ],
    }
    body_ref, images_ref, names_ref = [""], [], []
    client._walk_parts(payload, body_ref, images_ref, names_ref, "msg-1")
    assert names_ref == ["logo.pdf"]
    assert images_ref == []


def test_walk_parts_ignores_image_without_data():
    client = _make_client()
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "image/jpeg", "filename": "empty.jpg", "body": {}},
        ],
    }
    body_ref, images_ref, names_ref = [""], [], []
    client._walk_parts(payload, body_ref, images_ref, names_ref, "msg-1")
    assert images_ref == []


# ── _fetch_and_parse ──────────────────────────────────────────────────────────

def _gmail_message_payload(text: bytes, img_bytes: bytes | None = None) -> dict:
    parts = [{"mimeType": "text/plain", "body": {"data": _b64(text)}}]
    if img_bytes:
        parts.append({
            "mimeType": "image/jpeg",
            "filename": "mock.jpg",
            "body": {"data": _b64(img_bytes)},
        })
    return {
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "sender@example.com"},
                {"name": "Subject", "value": "Test subject"},
                {"name": "Date", "value": "Mon, 10 Jun 2026 09:00:00 +0300"},
            ],
            "parts": parts,
        }
    }


def test_fetch_and_parse_no_images(tmp_path):
    client = _make_client(image_save_dir=str(tmp_path / "email_images"))
    (
        client._service.users.return_value
        .messages.return_value
        .get.return_value
        .execute.return_value
    ) = _gmail_message_payload(b"corpo email")

    msg = client._fetch_and_parse("msg-123")

    assert msg.body_text == "corpo email"
    assert msg.image_paths == []


def test_fetch_and_parse_saves_images(tmp_path):
    client = _make_client(image_save_dir=str(tmp_path / "email_images"))
    (
        client._service.users.return_value
        .messages.return_value
        .get.return_value
        .execute.return_value
    ) = _gmail_message_payload(b"corpo email", _png_bytes(50, 50))

    msg = client._fetch_and_parse("msg-123")

    assert len(msg.image_paths) == 1
    assert Path(msg.image_paths[0]).is_file()
    assert "msg-123" in msg.image_paths[0]


def test_fetch_and_parse_no_save_when_dir_is_none():
    client = _make_client(image_save_dir=None)
    (
        client._service.users.return_value
        .messages.return_value
        .get.return_value
        .execute.return_value
    ) = _gmail_message_payload(b"corpo email", _png_bytes(50, 50))

    msg = client._fetch_and_parse("msg-123")

    assert msg.image_paths == []
```

- [ ] **Step 2: Rulează testele noi — trebuie să PICEZE**

```bash
.venv/bin/python -m pytest tests/unit/test_gmail_client.py -k "walk_parts or fetch_and_parse" -v
```

Expected: multiple failures (`TypeError` pentru `_walk_parts` cu semnătură veche)

- [ ] **Step 3: Actualizează `GmailClient` în `email_agent/gmail_client.py`**

Adaugă câmpul `image_save_dir` în dataclass (după `token_path`):

```python
@dataclass
class GmailClient:
    credentials_path: str = field(
        default_factory=lambda: os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials.json")
    )
    token_path: str = "gmail_token.json"
    image_save_dir: str | None = None
```

Înlocuiește metoda `_walk_parts` existentă:

```python
def _walk_parts(
    self,
    payload: dict,
    body_ref: list,
    images_ref: list,
    names_ref: list,
    msg_id: str,
) -> None:
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})

    if mime == "text/plain" and not payload.get("filename"):
        data = body.get("data", "")
        if data:
            body_ref[0] += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    elif mime.startswith("image/"):
        raw = self._get_part_bytes(body, msg_id)
        if raw:
            images_ref.append(_resize_image(raw))

    elif mime == "application/pdf" or (payload.get("filename") or "").lower().endswith(".pdf"):
        fn = payload.get("filename") or "document.pdf"
        names_ref.append(fn)

    for part in payload.get("parts", []):
        self._walk_parts(part, body_ref, images_ref, names_ref, msg_id)
```

Înlocuiește metoda `_fetch_and_parse` existentă:

```python
def _fetch_and_parse(self, msg_id: str) -> EmailMessage:
    msg = self._service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}

    body_ref: list[str] = [""]
    images_ref: list[bytes] = []
    names_ref: list[str] = []
    self._walk_parts(msg["payload"], body_ref, images_ref, names_ref, msg_id)

    image_paths: list[str] = []
    if images_ref and self.image_save_dir:
        save_dir = Path(self.image_save_dir) / msg_id
        save_dir.mkdir(parents=True, exist_ok=True)
        for idx, img_bytes in enumerate(images_ref):
            path = save_dir / f"{idx:02d}.jpg"
            path.write_bytes(img_bytes)
            image_paths.append(str(path))

    return EmailMessage(
        gmail_id=msg_id,
        sender=headers.get("From", ""),
        subject=headers.get("Subject", ""),
        body_text=body_ref[0],
        date=headers.get("Date", ""),
        image_paths=image_paths,
        other_attachment_names=names_ref,
    )
```

- [ ] **Step 4: Rulează toate testele din `test_gmail_client.py` — trebuie să TREACĂ**

```bash
.venv/bin/python -m pytest tests/unit/test_gmail_client.py -v
```

Expected: `13 passed`

- [ ] **Step 5: Verifică că testele existente nu s-au stricat**

```bash
.venv/bin/python -m pytest tests/unit/ tests/e2e/ -v
```

Expected: toate testele existente trec.

- [ ] **Step 6: Commit**

```bash
git add email_agent/gmail_client.py tests/unit/test_gmail_client.py
git commit -m "feat(email-agent): GmailClient extrage imagini, attachmentId, salvează pe disc"
```

---

## Task 4: `email_extractor.extract()` — ramura vision

**Files:**
- Modify: `email_agent/email_extractor.py`
- Modify: `tests/unit/test_email_extractor.py`

- [ ] **Step 1: Adaugă testele pentru ramura vision în `tests/unit/test_email_extractor.py`**

Adaugă la finalul fișierului (după testele existente):

```python
# ── ramura vision ─────────────────────────────────────────────────────────────

import tempfile
from pathlib import Path as _Path
from io import BytesIO as _BytesIO
from PIL import Image as _Image


class _FakeLLMBoth:
    """FakeLLM care înregistrează ambele tipuri de apeluri."""
    def __init__(self, response: str):
        self._response = response
        self.text_calls: list = []
        self.vision_calls: list = []

    def complete_text(self, system: str, user: str) -> str:
        self.text_calls.append((system, user))
        return self._response

    def complete_vision(self, system: str, content_blocks: list) -> str:
        self.vision_calls.append((system, content_blocks))
        return self._response


def _jpeg_file(tmp_path, idx: int = 0) -> str:
    buf = _BytesIO()
    _Image.new("RGB", (10, 10), color=(255, 0, 0)).save(buf, format="JPEG")
    path = _Path(tmp_path) / f"img{idx:02d}.jpg"
    path.write_bytes(buf.getvalue())
    return str(path)


def _make_email_with_images(tmp_path, body: str = "tricou polo navy") -> EmailMessage:
    return EmailMessage(
        gmail_id="gid-img",
        sender="E-CABLAJE S.A. <office@ecablaje.ro>",
        subject="Cerere produse",
        body_text=body,
        date="Mon, 10 Jun 2026 09:00:00 +0300",
        image_paths=[_jpeg_file(tmp_path, 0)],
    )


def test_extract_uses_vision_when_images_present(tmp_path):
    llm = _FakeLLMBoth('[{"product_type":"tricou","description":"polo","prefilled_state":{"culoare_principala":"navy"}}]')
    requests = email_extractor.extract(_make_email_with_images(tmp_path), llm)
    assert len(llm.vision_calls) == 1
    assert len(llm.text_calls) == 0
    assert len(requests) == 1


def test_extract_uses_text_when_no_images():
    llm = _FakeLLMBoth("[]")
    msg = _make_email("test fara imagini")
    email_extractor.extract(msg, llm)
    assert len(llm.text_calls) == 1
    assert len(llm.vision_calls) == 0


def test_extract_vision_content_blocks_include_text_and_image(tmp_path):
    llm = _FakeLLMBoth("[]")
    email_extractor.extract(_make_email_with_images(tmp_path), llm)
    _, content_blocks = llm.vision_calls[0]
    types = [b["type"] for b in content_blocks]
    assert "text" in types
    assert "image" in types


def test_extract_vision_includes_pdf_names_in_text(tmp_path):
    llm = _FakeLLMBoth("[]")
    msg = _make_email_with_images(tmp_path)
    msg.other_attachment_names = ["Logo ECJ.pdf"]
    email_extractor.extract(msg, llm)
    _, content_blocks = llm.vision_calls[0]
    text_block = next(b for b in content_blocks if b["type"] == "text")
    assert "Logo ECJ.pdf" in text_block["text"]


def test_extract_vision_image_block_is_base64_jpeg(tmp_path):
    llm = _FakeLLMBoth("[]")
    email_extractor.extract(_make_email_with_images(tmp_path), llm)
    _, content_blocks = llm.vision_calls[0]
    img_block = next(b for b in content_blocks if b["type"] == "image")
    assert img_block["source"]["type"] == "base64"
    assert img_block["source"]["media_type"] == "image/jpeg"
```

- [ ] **Step 2: Rulează testele noi — trebuie să PICEZE**

```bash
.venv/bin/python -m pytest tests/unit/test_email_extractor.py -k "vision" -v
```

Expected: `AttributeError` sau test failures (metoda `complete_vision` nu e apelată încă)

- [ ] **Step 3: Actualizează `email_agent/email_extractor.py`**

Adaugă la importuri (după `import json`):

```python
import base64
import json
from dataclasses import dataclass, field
from pathlib import Path

from email_agent.gmail_client import EmailMessage
from schemas import loader
```

Înlocuiește `SYSTEM_PROMPT` cu două constante:

```python
_SYSTEM_PROMPT_BASE = """Ești un asistent care extrage cereri de produse personalizate din emailuri de business.

Emailurile sunt trimise de clienți care comandă produse textile personalizate.

Sarcina ta: analizează corpul emailului și extrage FIECARE tip de produs menționat ca o cerere separată.

Pentru fiecare cerere returnează un obiect JSON cu:
- "product_type": tipul de produs (folosește EXACT una din valorile din lista furnizată)
- "description": descrierea brută a acelui produs din email (1-2 propoziții)
- "prefilled_state": obiect cu câmpurile pe care le poți extrage cu CERTITUDINE din email,
  folosind EXACT cheile din schema furnizată

IMPORTANT:
- Nu inventa valori. Dacă un câmp nu e menționat explicit în email sau imagini, NU îl include.
- Folosește EXACT cheile din schema — nu traduce, nu redenumi.
- Returnează un array JSON, chiar dacă e gol ([]).
- Răspunde EXCLUSIV cu JSON valid, fără text suplimentar."""

_SYSTEM_PROMPT_WITH_IMAGES = _SYSTEM_PROMPT_BASE + """

Emailul conține imagini cu mockup-uri de produs. Folosește-le pentru a completa câmpurile vizuale: \
culoare_principala, branding.pozitie, branding.culori. \
Informațiile extrase din imagini au prioritate față de absența lor din text."""
```

Înlocuiește funcția `extract()`:

```python
def extract(message: EmailMessage, llm) -> list[ProductRequest]:
    available_types = loader.available_product_types()

    schemas_text = ""
    schemas_map = {}
    for ptype in available_types:
        schema = loader.load_schema(ptype)
        schemas_map[ptype] = schema
        schemas_text += f'\nSchema pentru "{ptype}":\n{_schema_to_text(schema)}\n'

    user_content_dict = {
        "tipuri_disponibile": available_types,
        "scheme": schemas_text,
        "expeditor": message.sender,
        "subiect": message.subject,
        "data": message.date,
        "corp_email": message.body_text[:3000],
    }

    if message.image_paths:
        if message.other_attachment_names:
            user_content_dict["fisiere_atasate"] = message.other_attachment_names
        text_block = {"type": "text", "text": json.dumps(user_content_dict, ensure_ascii=False)}
        image_blocks = [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": base64.b64encode(Path(p).read_bytes()).decode(),
                },
            }
            for p in message.image_paths
        ]
        raw = llm.complete_vision(
            system=_SYSTEM_PROMPT_WITH_IMAGES,
            content_blocks=[text_block] + image_blocks,
        )
    else:
        raw = llm.complete_text(
            system=_SYSTEM_PROMPT_BASE,
            user=json.dumps(user_content_dict, ensure_ascii=False),
        )

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
```

- [ ] **Step 4: Rulează toate testele extractor — trebuie să TREACĂ**

```bash
.venv/bin/python -m pytest tests/unit/test_email_extractor.py -v
```

Expected: toate testele trec. Verifică în special că `test_prompt_includes_schema_fields` trece (testul vechi foloseşte `complete_text`, nu `complete_vision`).

- [ ] **Step 5: Rulează toate testele proiectului**

```bash
.venv/bin/python -m pytest tests/unit/ tests/e2e/ -v
```

Expected: toate trec.

- [ ] **Step 6: Commit**

```bash
git add email_agent/email_extractor.py tests/unit/test_email_extractor.py
git commit -m "feat(email-agent): extractor alege vision/text pe baza image_paths"
```

---

## Task 5: Rută web `/email-agent/image/` + `get_gmail_client()` cu `image_save_dir`

**Files:**
- Modify: `web/app.py`
- Modify: `tests/e2e/test_email_agent_routes.py`

- [ ] **Step 1: Adaugă testele e2e în `tests/e2e/test_email_agent_routes.py`**

Adaugă la finalul fișierului:

```python
# ── ruta /email-agent/image/ ──────────────────────────────────────────────────

def test_email_image_route_returns_file(client):
    from web import app as web_app
    from PIL import Image
    from io import BytesIO

    gmail_id = "test-gmail-id-img"
    img_dir = web_app.UPLOADS_DIR / "email_images" / gmail_id
    img_dir.mkdir(parents=True)
    buf = BytesIO()
    Image.new("RGB", (10, 10), color=(0, 128, 255)).save(buf, format="JPEG")
    (img_dir / "00.jpg").write_bytes(buf.getvalue())

    r = client.get(f"/email-agent/image/{gmail_id}/0")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/")


def test_email_image_route_404_when_file_missing(client):
    r = client.get("/email-agent/image/nonexistent-id/0")
    assert r.status_code == 404


def test_email_image_route_404_for_invalid_index(client):
    from web import app as web_app
    from PIL import Image
    from io import BytesIO

    gmail_id = "test-gmail-id-idx"
    img_dir = web_app.UPLOADS_DIR / "email_images" / gmail_id
    img_dir.mkdir(parents=True)
    buf = BytesIO()
    Image.new("RGB", (10, 10)).save(buf, format="JPEG")
    (img_dir / "00.jpg").write_bytes(buf.getvalue())

    r = client.get(f"/email-agent/image/{gmail_id}/99")
    assert r.status_code == 404
```

- [ ] **Step 2: Rulează testele noi — trebuie să PICEZE**

```bash
.venv/bin/python -m pytest tests/e2e/test_email_agent_routes.py -k "image_route" -v
```

Expected: `404` sau `405` pentru toate (ruta nu există încă)

- [ ] **Step 3: Actualizează `web/app.py`**

Înlocuiește funcția `get_gmail_client()` existentă:

```python
def get_gmail_client() -> Any:
    """Lazily build a singleton GmailClient. Tests patch this function."""
    global _gmail_singleton
    if _gmail_singleton is None:
        _gmail_singleton = GmailClient(
            image_save_dir=str(UPLOADS_DIR / "email_images")
        )
    return _gmail_singleton
```

Adaugă ruta nouă după ruta `/email-agent/fetch` (în jurul liniei 735):

```python
@app.get("/email-agent/image/{gmail_id}/{idx}")
def email_image(gmail_id: str, idx: int):
    path = UPLOADS_DIR / "email_images" / gmail_id / f"{idx:02d}.jpg"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Imagine indisponibilă")
    return FileResponse(path)
```

- [ ] **Step 4: Rulează testele noi — trebuie să TREACĂ**

```bash
.venv/bin/python -m pytest tests/e2e/test_email_agent_routes.py -k "image_route" -v
```

Expected: `3 passed`

- [ ] **Step 5: Rulează toate testele**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: toate trec.

- [ ] **Step 6: Commit**

```bash
git add web/app.py tests/e2e/test_email_agent_routes.py
git commit -m "feat(web): ruta /email-agent/image/{gmail_id}/{idx} + get_gmail_client cu image_save_dir"
```

---

## Task 6: Template thumbnails + CSS

**Files:**
- Modify: `web/templates/email_requests.html`
- Modify: `web/static/styles.css`

- [ ] **Step 1: Adaugă thumbnails în `web/templates/email_requests.html`**

Înlocuiește blocul `<div class="email-group__info">` existent (liniile 23–26):

```html
    <div class="email-group__info">
      <span class="email-group__sender">{{ group.email.sender }}</span>
      <span class="email-group__subject">{{ group.email.subject }}</span>
      {% if group.email.image_paths %}
      <div class="email-group__thumbs">
        {% for i in range(group.email.image_paths | length) %}
        <img src="/email-agent/image/{{ group.email.gmail_id }}/{{ i }}"
             class="email-thumb"
             alt="atașament {{ loop.index }}">
        {% endfor %}
      </div>
      {% endif %}
    </div>
```

- [ ] **Step 2: Adaugă clasele CSS în `web/static/styles.css`**

Adaugă la finalul fișierului:

```css
/* ── email thumbnails ───────────────────────────────────────────── */
.email-group__thumbs {
  display: flex;
  gap: var(--s-1);
  margin-top: var(--s-2);
}
.email-thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 4px;
  border: 1px solid var(--c-border);
  cursor: pointer;
}
.email-thumb:hover { opacity: 0.85; }
```

- [ ] **Step 3: Pornește serverul și verifică vizual**

```bash
.venv/bin/python -m uvicorn web.app:app --reload
```

Deschide `http://localhost:8000`, apasă "Verifică cereri pe e-mail" cu un interval care conține emailuri cu imagini. Verifică:
- Thumbnails de 48×48px apar lângă subiectul emailului
- Thumbnails nu apar pentru emailuri fără imagini
- Click pe thumbnail nu dă eroare (nu avem lightbox, browserul deschide imaginea)

- [ ] **Step 4: Rulează toate testele o ultimă dată**

```bash
.venv/bin/python -m pytest tests/ -v
```

Expected: toate trec.

- [ ] **Step 5: Commit final**

```bash
git add web/templates/email_requests.html web/static/styles.css
git commit -m "feat(web): thumbnails imagini email în email_requests template"
```
