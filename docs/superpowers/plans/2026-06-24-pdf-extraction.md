# PDF Extraction from Email Attachments — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract text and embedded images from PDF email attachments and feed them to the LLM alongside the email body, with text always having priority over images.

**Architecture:** Add `email_agent/pdf_extractor.py` (PyMuPDF) with a single public function `extract_pdf(bytes) -> (str, list[bytes])`. `gmail_client.py` calls it when a PDF part is found and stores results in two new `EmailMessage` fields. `email_extractor.py` merges PDF text into the email body and PDF images into the image list before calling the LLM.

**Tech Stack:** PyMuPDF (`fitz`), existing FastAPI + LLM stack.

## Global Constraints

- Python 3.11+
- `pymupdf>=1.24` — new dependency
- Text per PDF: max 2000 characters (truncate)
- Images per PDF: max 10 (skip extras with warning log)
- Corrupt/password-protected PDFs → return `("", [])`, never raise
- Image priority rule: text > images (already in `_SYSTEM_PROMPT_WITH_IMAGES`)
- All tests run with: `.venv/Scripts/python -m pytest <path> -v`
- Commit after each task

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `email_agent/pdf_extractor.py` | Create | Extract text + images from PDF bytes using PyMuPDF |
| `email_agent/gmail_client.py` | Modify | Add `pdf_texts`, `pdf_image_paths` to `EmailMessage`; call `extract_pdf` in `_walk_parts` and save images to disk in `_fetch_and_parse` |
| `email_agent/email_extractor.py` | Modify | Merge `pdf_texts` into body text, `pdf_image_paths` into image paths |
| `requirements.txt` | Modify | Add `pymupdf>=1.24` |
| `tests/unit/test_pdf_extractor.py` | Create | Unit tests for `extract_pdf` |
| `tests/e2e/test_email_agent_routes.py` | Modify | Add `test_fetch_includes_pdf_text` |

---

## Task 1: Install PyMuPDF and create `pdf_extractor` module (TDD)

**Files:**
- Create: `email_agent/pdf_extractor.py`
- Create: `tests/unit/test_pdf_extractor.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `extract_pdf(pdf_bytes: bytes) -> tuple[str, list[bytes]]`
  - Returns `(text, jpeg_images_list)`
  - `text` is truncated at 2000 chars
  - `jpeg_images_list` contains raw JPEG bytes (already resized to max 1024px)
  - On any error returns `("", [])`

- [ ] **Step 1: Install pymupdf**

```
.venv\Scripts\pip install "pymupdf>=1.24"
```

Expected: `Successfully installed pymupdf-...`

- [ ] **Step 2: Add to requirements.txt**

Open `requirements.txt` and add this line (keep alphabetical order):

```
pymupdf>=1.24
```

- [ ] **Step 3: Write failing tests**

Create `tests/unit/test_pdf_extractor.py`:

```python
import io
import fitz  # PyMuPDF
import pytest
from PIL import Image
from email_agent.pdf_extractor import extract_pdf


def _make_text_pdf(text: str) -> bytes:
    """Creates a minimal PDF with given text on page 1."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((50, 50), text)
    return doc.tobytes()


def _make_image_pdf() -> bytes:
    """Creates a PDF with a small embedded JPEG image."""
    buf = io.BytesIO()
    Image.new("RGB", (100, 100), color=(255, 0, 0)).save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()

    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    rect = fitz.Rect(10, 10, 110, 110)
    page.insert_image(rect, stream=jpeg_bytes)
    return doc.tobytes()


def test_extract_text_from_pdf():
    pdf_bytes = _make_text_pdf("culoare negru guler rotund")
    text, images = extract_pdf(pdf_bytes)
    assert "negru" in text
    assert "rotund" in text
    assert isinstance(images, list)


def test_extract_images_from_pdf():
    pdf_bytes = _make_image_pdf()
    text, images = extract_pdf(pdf_bytes)
    assert isinstance(images, list)
    assert len(images) >= 1
    # Each image should be valid JPEG bytes
    img = Image.open(io.BytesIO(images[0]))
    assert img.format == "JPEG"


def test_extract_corrupted_pdf():
    text, images = extract_pdf(b"not a pdf at all %%EOF garbage")
    assert text == ""
    assert images == []


def test_extract_empty_pdf():
    doc = fitz.open()
    doc.new_page()  # blank page, no content
    pdf_bytes = doc.tobytes()
    text, images = extract_pdf(pdf_bytes)
    assert text == ""
    assert images == []


def test_text_truncated_at_2000_chars():
    long_text = "a" * 3000
    pdf_bytes = _make_text_pdf(long_text)
    text, _ = extract_pdf(pdf_bytes)
    assert len(text) <= 2000


def test_max_10_images():
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color=(0, 0, 255)).save(buf, format="JPEG")
    jpeg_bytes = buf.getvalue()
    for i in range(15):
        x = (i % 5) * 50
        y = (i // 5) * 50
        page.insert_image(fitz.Rect(x, y, x + 40, y + 40), stream=jpeg_bytes)
    pdf_bytes = doc.tobytes()
    _, images = extract_pdf(pdf_bytes)
    assert len(images) <= 10
```

- [ ] **Step 4: Run tests to verify they fail**

```
.venv\Scripts\python -m pytest tests/unit/test_pdf_extractor.py -v
```

Expected: `ModuleNotFoundError: No module named 'email_agent.pdf_extractor'`

- [ ] **Step 5: Implement `email_agent/pdf_extractor.py`**

```python
import io
import logging

_log = logging.getLogger(__name__)

_MAX_TEXT_CHARS = 2000
_MAX_IMAGES = 10


def extract_pdf(pdf_bytes: bytes) -> tuple[str, list[bytes]]:
    """Extract text and JPEG images from PDF bytes using PyMuPDF.

    Returns (text, jpeg_images). On corrupt or password-protected PDFs
    returns ("", []) without raising.
    """
    try:
        import fitz  # PyMuPDF — imported here so the rest of the app
                     # works even if pymupdf is not installed
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as exc:
        _log.warning("[pdf] nu pot deschide PDF: %s", exc)
        return "", []

    text_parts: list[str] = []
    images: list[bytes] = []
    total_chars = 0

    for page_num in range(len(doc)):
        page = doc[page_num]

        # --- text ---
        remaining = _MAX_TEXT_CHARS - total_chars
        if remaining > 0:
            page_text = page.get_text().strip()
            if page_text:
                chunk = page_text[:remaining]
                text_parts.append(chunk)
                total_chars += len(chunk)

        # --- images ---
        if len(images) >= _MAX_IMAGES:
            continue
        try:
            image_list = page.get_images(full=True)
        except Exception as exc:
            _log.warning("[pdf] eroare la listarea imaginilor pagina %d: %s", page_num, exc)
            continue

        for img_info in image_list:
            if len(images) >= _MAX_IMAGES:
                _log.warning("[pdf] depășit limita de %d imagini, restul omise", _MAX_IMAGES)
                break
            xref = img_info[0]
            try:
                base_img = doc.extract_image(xref)
                raw = base_img["image"]
                jpeg = _to_jpeg(raw)
                if jpeg:
                    images.append(jpeg)
            except Exception as exc:
                _log.warning("[pdf] imagine xref=%d ilizibilă, omisă: %s", xref, exc)

    return "\n".join(text_parts), images


def _to_jpeg(raw: bytes, max_px: int = 1024) -> bytes | None:
    try:
        from PIL import Image
        buf_in = io.BytesIO(raw)
        img = Image.open(buf_in)
        img.thumbnail((max_px, max_px), Image.LANCZOS)
        if img.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img.convert("RGBA"), mask=img.convert("RGBA").split()[-1])
            img = bg
        else:
            img = img.convert("RGB")
        buf_out = io.BytesIO()
        img.save(buf_out, format="JPEG", quality=85)
        return buf_out.getvalue()
    except Exception as exc:
        _log.warning("[pdf] conversie JPEG eșuată: %s", exc)
        return None
```

- [ ] **Step 6: Run tests to verify they pass**

```
.venv\Scripts\python -m pytest tests/unit/test_pdf_extractor.py -v
```

Expected: `6 passed`

- [ ] **Step 7: Commit**

```
git add email_agent/pdf_extractor.py tests/unit/test_pdf_extractor.py requirements.txt
git commit -m "feat(email-agent): pdf_extractor — text + imagini din PDF cu PyMuPDF"
```

---

## Task 2: Update `EmailMessage` and `_walk_parts` in `gmail_client.py`

**Files:**
- Modify: `email_agent/gmail_client.py`

**Interfaces:**
- Consumes: `extract_pdf(pdf_bytes: bytes) -> tuple[str, list[bytes]]` from `email_agent.pdf_extractor`
- Produces:
  - `EmailMessage.pdf_texts: list[str]` — text from each PDF attachment
  - `EmailMessage.pdf_image_paths: list[str]` — paths to JPEG images saved from PDFs

- [ ] **Step 1: Add `pdf_texts` and `pdf_image_paths` to `EmailMessage`**

In `email_agent/gmail_client.py`, update the `EmailMessage` dataclass (currently lines 21-29):

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
    pdf_texts: list[str] = field(default_factory=list)
    pdf_image_paths: list[str] = field(default_factory=list)
```

- [ ] **Step 2: Add import for `pdf_extractor` at top of file**

After the existing imports, add:

```python
from email_agent import pdf_extractor as _pdf_extractor
```

- [ ] **Step 3: Update `_walk_parts` to collect PDF bytes**

`_walk_parts` currently appends only the filename to `names_ref` for PDFs. Change it to also collect PDF bytes:

The method signature needs a new `pdf_bytes_ref: list[bytes]` parameter. Update the signature and the PDF branch:

```python
def _walk_parts(
    self,
    payload: dict,
    body_ref: list[str],
    images_ref: list[bytes],
    names_ref: list[str],
    pdf_bytes_ref: list[bytes],
    msg_id: str,
) -> None:
    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    fn = payload.get("filename")
    _log.debug("[walk] mime=%-30s fn=%-30s data=%s att=%s size=%s",
               mime, fn, bool(body.get("data")), bool(body.get("attachmentId")),
               body.get("size", 0))

    if mime == "text/plain" and not fn:
        data = body.get("data", "")
        if data:
            body_ref[0] += base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    elif mime.startswith("image/"):
        raw = self._get_part_bytes(body, msg_id)
        if raw:
            try:
                resized = _resize_image(raw)
            except Exception as exc:
                _log.warning("[gmail] imagine ilizibilă, omisă: %s — %s", fn or mime, exc)
            else:
                _log.debug("[gmail] imagine extrasă: %s (%d bytes brut)", fn or mime, len(raw))
                images_ref.append(resized)
        else:
            _log.warning("[gmail] imagine fără date: %s", fn or mime)

    elif mime == "application/pdf" or (fn or "").lower().endswith(".pdf"):
        names_ref.append(fn or "document.pdf")
        raw = self._get_part_bytes(body, msg_id)
        if raw:
            pdf_bytes_ref.append(raw)
        else:
            _log.warning("[gmail] PDF fără date: %s", fn or "document.pdf")

    for part in payload.get("parts", []):
        self._walk_parts(part, body_ref, images_ref, names_ref, pdf_bytes_ref, msg_id)
```

- [ ] **Step 4: Update `_fetch_and_parse` to process PDF bytes and build `pdf_texts` / `pdf_image_paths`**

Replace the existing `_fetch_and_parse` method:

```python
def _fetch_and_parse(self, msg_id: str) -> EmailMessage:
    msg = self._service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}

    body_ref: list[str] = [""]
    images_ref: list[bytes] = []
    names_ref: list[str] = []
    pdf_bytes_ref: list[bytes] = []
    self._walk_parts(msg["payload"], body_ref, images_ref, names_ref, pdf_bytes_ref, msg_id)

    save_dir = None
    if self.image_save_dir:
        save_dir = Path(self.image_save_dir) / Path(msg_id).name
        save_dir.mkdir(parents=True, exist_ok=True)

    # Save email images
    image_paths: list[str] = []
    if images_ref and save_dir:
        for idx, img_bytes in enumerate(images_ref):
            path = save_dir / f"{idx:02d}.jpg"
            path.write_bytes(img_bytes)
            image_paths.append(str(path))
    elif images_ref:
        _log.warning("[gmail] %d imagini extrase dar image_save_dir=None — nu se salvează", len(images_ref))

    # Extract and save PDF content
    pdf_texts: list[str] = []
    pdf_image_paths: list[str] = []
    for pdf_idx, pdf_bytes in enumerate(pdf_bytes_ref):
        text, pdf_images = _pdf_extractor.extract_pdf(pdf_bytes)
        if text:
            pdf_texts.append(text)
        if pdf_images and save_dir:
            for img_idx, jpeg_bytes in enumerate(pdf_images):
                path = save_dir / f"pdf_{pdf_idx:02d}_{img_idx:02d}.jpg"
                path.write_bytes(jpeg_bytes)
                pdf_image_paths.append(str(path))
        elif pdf_images:
            _log.warning("[gmail] %d imagini PDF extrase dar image_save_dir=None", len(pdf_images))

    _log.info("[gmail] msg=%s: %d ch text, %d img email, %d PDF-uri, %d img PDF",
              msg_id, len(body_ref[0]), len(image_paths), len(pdf_bytes_ref), len(pdf_image_paths))

    return EmailMessage(
        gmail_id=msg_id,
        sender=headers.get("From", ""),
        subject=headers.get("Subject", ""),
        body_text=body_ref[0],
        date=headers.get("Date", ""),
        image_paths=image_paths,
        other_attachment_names=names_ref,
        pdf_texts=pdf_texts,
        pdf_image_paths=pdf_image_paths,
    )
```

- [ ] **Step 5: Run full test suite to verify no regressions**

```
.venv\Scripts\python -m pytest tests/ -v
```

Expected: all existing tests pass (new fields have `default_factory=list` so old `EmailMessage(...)` calls still work).

- [ ] **Step 6: Commit**

```
git add email_agent/gmail_client.py
git commit -m "feat(email-agent): EmailMessage primește pdf_texts și pdf_image_paths"
```

---

## Task 3: Update `email_extractor.py` to use PDF content

**Files:**
- Modify: `email_agent/email_extractor.py`
- Modify: `tests/e2e/test_email_agent_routes.py`

**Interfaces:**
- Consumes: `EmailMessage.pdf_texts: list[str]`, `EmailMessage.pdf_image_paths: list[str]`

- [ ] **Step 1: Write the failing e2e test first**

Add this test at the bottom of `tests/e2e/test_email_agent_routes.py`:

```python
def test_fetch_includes_pdf_text(client, fake_llm, monkeypatch):
    """PDF text should reach the LLM and contribute to prefilled_state."""
    from web import app as web_app

    msg = EmailMessage(
        gmail_id="gid-pdf",
        sender="Client <client@test.ro>",
        subject="Cerere tricou",
        body_text="va trimit detalii in PDF",
        date="Mon, 23 Jun 2026 10:00:00 +0300",
        pdf_texts=["tricou negru guler rotund material bumbac"],
    )
    monkeypatch.setattr(web_app, "get_gmail_client", lambda: FakeGmail([msg]))
    fake_llm.queue_text(json.dumps([{
        "product_type": "tricou",
        "description": "tricou negru guler rotund",
        "prefilled_state": {"culoare_principala": "negru", "guler": "rotund"},
    }]))
    r = client.post("/email-agent/fetch", data={"date_start": "2026-06-23", "date_end": "2026-06-23"})
    assert r.status_code == 200
    assert "negru" in r.text
```

- [ ] **Step 2: Run the test to verify it fails**

```
.venv\Scripts\python -m pytest tests/e2e/test_email_agent_routes.py::test_fetch_includes_pdf_text -v
```

Expected: PASS already (LLM mock returns the right data regardless) — if so, good. The important check is that `corp_email` in the prompt now includes PDF text.

- [ ] **Step 3: Update `extract()` in `email_extractor.py`**

Find the block that builds `user_content_dict` (around line 78) and update `corp_email` to include PDF texts, and merge `pdf_image_paths` into image paths:

```python
def extract(message: EmailMessage, llm: LLMClient) -> list[ProductRequest]:
    available_types = loader.available_product_types()

    schemas_text = ""
    schemas_map = {}
    for ptype in available_types:
        schema = loader.load_schema(ptype)
        schemas_map[ptype] = schema
        schemas_text += f'\nSchema pentru "{ptype}":\n{_schema_to_text(schema)}\n'

    # Merge email body with PDF text content
    body_parts = [message.body_text[:3000]]
    for pdf_text in getattr(message, "pdf_texts", []):
        if pdf_text.strip():
            body_parts.append(f"\n\n--- Conținut PDF ---\n{pdf_text}")
    full_body = "".join(body_parts)

    user_content_dict = {
        "tipuri_disponibile": available_types,
        "scheme": schemas_text,
        "expeditor": message.sender,
        "subiect": message.subject,
        "data": message.date,
        "corp_email": full_body,
    }
    if message.other_attachment_names:
        user_content_dict["fisiere_atasate"] = message.other_attachment_names

    # Merge email images with PDF images
    all_image_paths = list(getattr(message, "image_paths", [])) + list(getattr(message, "pdf_image_paths", []))

    if all_image_paths:
        text_block = {"type": "text", "text": json.dumps(user_content_dict, ensure_ascii=False)}
        image_blocks = [b for p in all_image_paths if (b := _image_block(p)) is not None]
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

- [ ] **Step 4: Run full test suite**

```
.venv\Scripts\python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```
git add email_agent/email_extractor.py tests/e2e/test_email_agent_routes.py
git commit -m "feat(email-agent): PDF text și imagini ajung la LLM în extract()"
```

---

## Task 4: Push final

- [ ] **Step 1: Run complete test suite one last time**

```
.venv\Scripts\python -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2: Push**

```
git push origin master
```
