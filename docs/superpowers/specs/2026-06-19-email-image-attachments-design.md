# Email Image Attachments — Design Spec

**Data:** 2026-06-19
**Scope:** Extinderea email agent-ului pentru a extrage, stoca și trimite la LLM imaginile atașate emailurilor de comandă.

---

## Context

Email-urile primite pe `comenzi.ciptronic@gmail.com` conțin frecvent mockup-uri vizuale ca imagini atașate (JPEG/PNG inline via CID). Aceste imagini sunt singura sursă pentru câmpuri precum `branding.pozitie`, `branding.culori` și `culoare_principala`. Implementarea actuală a `GmailClient._walk_parts()` extrage exclusiv `text/plain` — imaginile sunt ignorate complet.

---

## Obiectiv

1. Extrage imaginile din emailuri via Gmail API (inclusiv atașamente mari returnate ca `attachmentId`).
2. Redimensionează și stochează imaginile pe disc (`uploads/email_images/{gmail_id}/`).
3. Trimite imaginile la LLM împreună cu textul emailului (apel `complete_vision`).
4. Afișează thumbnails discrete ale imaginilor în interfața web, lângă subiectul emailului.

---

## Modelul de date

### `EmailMessage` (modificat)

```python
@dataclass
class EmailMessage:
    gmail_id: str
    sender: str
    subject: str
    body_text: str
    date: str
    image_paths: list[str] = field(default_factory=list)          # nou: paths pe disc
    other_attachment_names: list[str] = field(default_factory=list)  # nou: nume PDF etc.
```

- `image_paths` — paths absolute ale imaginilor JPEG redimensionate, în ordinea din email.
- `other_attachment_names` — numele fișierelor non-imagine (PDF, DOCX etc.), transmise LLM-ului ca hint textual. Nu sunt stocate pe disc.

---

## `GmailClient` — modificări

### Parametru nou: `image_save_dir`

```python
@dataclass
class GmailClient:
    credentials_path: str = ...
    token_path: str = "gmail_token.json"
    image_save_dir: str | None = None   # nou
```

Dacă `None`, imaginile nu se salvează pe disc (comportament util în teste). Web app-ul injectează `str(UPLOADS_DIR / "email_images")`.

### `_resize_image(data, max_px=1024)` — funcție pură la nivel de modul

```python
def _resize_image(data: bytes, max_px: int = 1024) -> bytes:
    img = Image.open(io.BytesIO(data))
    img.thumbnail((max_px, max_px), Image.LANCZOS)
    out = io.BytesIO()
    img.convert("RGB").save(out, format="JPEG", quality=85)
    return out.getvalue()
```

Redimensionează la max 1024px pe latura lungă, re-encodează JPEG. Pillow e deja instalat.

### `_get_part_bytes(body, msg_id)` — metodă nouă

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

Gmail returnează `attachmentId` în loc de date inline pentru atașamente >~2MB (cazul tipic pentru screenshots PNG de 2MB). Fără această metodă, imaginile mari ar fi ignorate silențios.

### `_walk_parts(payload, body_ref, images_ref, names_ref, msg_id)` — semnătură extinsă

Față de varianta actuală (`payload, body_ref`), colectează acum și imagini și PDF-uri:

- `image/*` → `_get_part_bytes()` + `_resize_image()` → append la `images_ref`
- `application/pdf` sau filename cu `.pdf` → append filename la `names_ref`
- `text/plain` fără filename → comportament existent

### `_fetch_and_parse(msg_id)` — adaptare

Inițializează `images_ref=[]`, `names_ref=[]`, le pasează la `_walk_parts`. Dacă `image_save_dir` e setat, salvează fiecare imagine redimensionată la `{image_save_dir}/{gmail_id}/{idx:02d}.jpg` și populează `image_paths`. Returnează `EmailMessage` extins.

---

## `email_extractor.py` — modificări

### System prompt — paragraf adițional (activ doar când există imagini)

> *"Emailul conține imagini cu mockup-uri de produs. Folosește-le pentru a completa câmpurile vizuale: `culoare_principala`, `branding.pozitie`, `branding.culori`. Informațiile extrase din imagini au prioritate față de absența lor din text."*

### Logica de apel LLM

```python
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
    raw = llm.complete_vision(system=SYSTEM_PROMPT, content_blocks=[text_block] + image_blocks)
else:
    raw = llm.complete_text(system=SYSTEM_PROMPT, user=json.dumps(user_content_dict, ...))
```

Extractor-ul citește bytes-urile de pe disc la momentul apelului LLM. Nu ține imagini în memorie pe termen lung.

---

## `web/app.py` — modificări

### `get_gmail_client()` — injectare `image_save_dir`

```python
def get_gmail_client():
    global _gmail_singleton
    if _gmail_singleton is None:
        _gmail_singleton = GmailClient(
            image_save_dir=str(UPLOADS_DIR / "email_images")
        )
    return _gmail_singleton
```

### Rută nouă: servire imagini email

```python
@app.get("/email-agent/image/{gmail_id}/{idx}")
def email_image(gmail_id: str, idx: int):
    path = UPLOADS_DIR / "email_images" / gmail_id / f"{idx:02d}.jpg"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Imagine indisponibilă")
    return FileResponse(path)
```

Ruta e scopată strict la cele două segmente de path (`gmail_id` + index numeric) — nu expune directorul `uploads/` mai larg.

---

## Template `email_requests.html` — modificări

Thumbnails discrete (48×48px) lângă subiectul emailului, vizibile înainte ca operatorul să deschidă sesiunea:

```html
<div class="email-group__info">
  <span class="email-group__sender">{{ group.email.sender }}</span>
  <span class="email-group__subject">{{ group.email.subject }}</span>
  {% if group.email.image_paths %}
  <div class="email-group__thumbs">
    {% for i in range(group.email.image_paths | length) %}
    <img src="/email-agent/image/{{ group.email.gmail_id }}/{{ i }}"
         class="email-thumb" alt="atașament {{ loop.index }}">
    {% endfor %}
  </div>
  {% endif %}
</div>
```

CSS adăugat în `static/styles.css`:
```css
.email-group__thumbs { display: flex; gap: 4px; margin-top: 4px; }
.email-thumb {
    width: 48px; height: 48px; object-fit: cover;
    border-radius: 4px; border: 1px solid var(--c-border);
    cursor: pointer;
}
.email-thumb:hover { opacity: 0.85; }
```

---

## Strategie de testare

### Unit — `tests/unit/test_email_extractor.py`
- Test cu `image_paths` populat → verifică că se apelează `llm.complete_vision()` (nu `complete_text()`)
- Test fără imagini → verifică că se apelează `llm.complete_text()` (comportament existent păstrat)

### Unit — `tests/unit/test_gmail_client.py` (nou)
- Mock Gmail API → `body.data` gol + `attachmentId` prezent → verifică că se face apelul `attachments().get()`
- Mock Gmail API → `body.data` prezent → verifică că NU se face apelul `attachments().get()`
- `_resize_image` cu imagine reală → verifică că output-ul e JPEG și dimensiunea e ≤ 1024px

### E2E — `tests/e2e/test_email_agent_routes.py`
- Mock `GmailClient` cu `image_paths` populat cu fișiere temporare → verifică că ruta `/email-agent/image/` returnează 200
- Verifică că ruta returnează 404 când fișierul lipsește

---

## Ce NU este în scope

- Curățare automată a imaginilor vechi din `uploads/email_images/` (lăsat pentru o iterație viitoare)
- Suport PDF → conversie la imagine (PDF-urile sunt menționate textual, nu vizualizate)
- Lightbox / click-to-expand pentru thumbnails în UI
