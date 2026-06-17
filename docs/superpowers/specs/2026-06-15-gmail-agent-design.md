# Agent Email Gmail — Spec de Design (v2)

**Data:** 2026-06-17
**Status:** Aprobat

---

## Context

Ciptronic Validator are deja două fluxuri operaționale: Discovery (descriere text → specificație completă) și Image Match (mockup → comparare vizuală). Ambele sunt declanșate manual de angajat.

Clienții trimit cereri de personalizare pe email (ex. „vreau 50 tricouri polo cu broderie ECJ, font Bion Wide, 6 cm, culoare navy"). Până acum angajatul copia manual informațiile din email în formularul Discovery. Acest spec descrie o extensie care automatizează acel pas: angajatul alege un interval de date, aplicația citește emailurile și returnează o listă de cereri pre-extrase, gata de deschis ca sesiuni Discovery.

---

## Obiective

- Angajatul selectează un interval de date și apasă un buton pe pagina principală
- Aplicația citește toate emailurile primite în acel interval dintr-un inbox Gmail dedicat
- Un LLM extrage cererile de produse din fiecare email (un email poate genera mai multe cereri)
- Angajatul vede o listă de cereri; dă click pe una → se deschide o sesiune Discovery pre-completată
- Câmpurile cunoscute sunt deja populate; agentul pune întrebări doar pentru ce lipsește

---

## Non-Obiective (excluse explicit)

- Polling automat în fundal — nu există niciun proces care rulează periodic
- Clasificare spam/unclear — inbox-ul e dedicat exclusiv cererilor de produse
- Generare PDF sau trimitere răspuns pe email
- Panou de monitorizare și tabel `email_jobs`
- Retry mechanism pentru job-uri
- Flow B (Image Match) declanșat din email — doar Discovery

---

## Arhitectură

### Abordare

Două componente noi:

1. **`email_agent/gmail_client.py`** — wrapper OAuth2 care autentifică și returnează emailurile dintr-un interval de date. Aceeași structură ca în v1, fără `mark_read` și `send_email`.

2. **`email_agent/email_extractor.py`** — primește conținutul unui email și returnează o listă de cereri extrase (una per tip de produs menționat), fiecare cu câmpurile schemei completate cât mai mult posibil.

Rutele noi din `web/app.py` leagă cele două componente de UI. Nu există proces separat de polling.

### Fișiere noi

```
email_agent/
├── __init__.py
├── gmail_client.py      # OAuth2 + fetch emails by date range
└── email_extractor.py   # LLM: extrage cereri de produse din email

web/
└── templates/
    └── email_requests.html  # Lista de cereri extrase
```

### Fișiere existente modificate

| Fișier | Modificare |
|---|---|
| `web/app.py` | Adaugă `POST /email-agent/fetch` și `POST /email-agent/create-session` |
| `web/templates/index.html` | Adaugă câmpuri dată + buton deasupra celor două carduri existente |
| `requirements.txt` | Adaugă `google-auth-oauthlib>=1.2`, `google-api-python-client>=2.120` |
| `.gitignore` | Adaugă `gmail_token.json`, `credentials.json` |

---

## Fluxul complet

```
Angajat completează "De la" + "Până la" → apasă "Verifică cereri pe e-mail"
  └─ POST /email-agent/fetch {date_start, date_end}
       └─ gmail_client.fetch_emails(date_start, date_end) → listă EmailMessage
            └─ pentru fiecare email:
                 email_extractor.extract(email) → listă ProductRequest
                 (un email cu 3 tipuri de produse → 3 ProductRequest)
       └─ returnează HTML cu lista de cereri grupate pe email sursă

Angajat dă click pe o cerere
  └─ POST /email-agent/create-session {product_type, prefilled_state_json}
       └─ repository.create_session(conn, product_type, description)
       └─ repository.update_session_state(conn, sid, prefilled_state, ...)
       └─ redirect → GET /sessions/{sid}  (interfața Discovery existentă, câmpuri pre-completate)
```

---

## Model de date

### `ProductRequest` (obiect în memorie, nu în DB)

```python
@dataclass
class ProductRequest:
    email_sender: str        # expeditor email
    email_subject: str       # subiect email
    email_date: str          # data primirii
    product_type: str        # ex. "tricou", "hanorac" — cheie din schemas/
    prefilled_state: dict    # câmpurile extrase; câmpurile necunoscute lipsesc sau sunt null
    description: str         # descrierea brută din email pentru acest produs
```

Nu se adaugă tabele noi în DB. Sesiunile Discovery create sunt identice cu cele create manual — același tabel `discovery_sessions`, același flux.

---

## Extragere LLM (`email_extractor.py`)

LLM-ul primește:
- Corpul emailului (text)
- Lista de tipuri de produse disponibile în aplicație (din `schemas/loader.available_product_types()`)
- Schema completă a fiecărui tip de produs identificat (câmpurile disponibile)

LLM-ul returnează un array JSON, câte un obiect per tip de produs menționat:

```json
[
  {
    "product_type": "tricou",
    "description": "tricou polo cu broderie ECJ, font Bion Wide, 6 cm, culoare navy",
    "prefilled_state": {
      "tip_produs": "polo",
      "culoare": "navy",
      "branding": {
        "tehnica": "broderie",
        "text": "ECJ",
        "font": "Bion Wide",
        "dimensiune_cm": 6
      }
    }
  },
  {
    "product_type": "hanorac",
    "description": "hanorace simple fără personalizare",
    "prefilled_state": {
      "tip_produs": "hanorac"
    }
  }
]
```

Câmpurile pe care LLM-ul nu le poate extrage din email lipsesc din `prefilled_state` (nu se inventează valori).

---

## UI — modificări pe pagina principală

Deasupra celor două carduri existente („Am o descriere" / „Am un mockup"), se adaugă o secțiune:

```
┌─────────────────────────────────────────────────────┐
│  Verifică cereri pe e-mail                          │
│  De la: [____/____/______]  Până la: [____/____/____]│
│                        [Verifică cereri pe e-mail]  │
└─────────────────────────────────────────────────────┘

── sau ──

[Am o descriere]    [Am un mockup]
```

După apăsarea butonului, lista de cereri apare pe aceeași pagină (HTMX swap) sau pe o pagină dedicată `/email-requests`.

Fiecare rând din listă afișează:
- Expeditor + dată email
- Tip produs
- Sumar câmpuri extrase (ex. „broderie ECJ · font Bion Wide · culoare navy")
- Buton „Deschide sesiune"

---

## Autentificare Gmail

Identic cu v1:

1. Developer creează proiect Google Cloud, activează Gmail API, descarcă `credentials.json`
2. La primul acces pe ruta `/email-agent/fetch`, dacă `gmail_token.json` lipsește → redirect către OAuth2 flow (browser)
3. Token salvat în `gmail_token.json` (gitignored), reîmprospătat automat
4. `GMAIL_CREDENTIALS_PATH` configurat în `.env`

Scopes necesare: `gmail.readonly` (nu mai avem nevoie de `gmail.send`).

---

## Gestionarea erorilor

| Scenariu | Comportament |
|---|---|
| Gmail API indisponibil | Eroare 502 cu mesaj prietenos în UI |
| Token expirat / lipsă | Redirect către re-autentificare OAuth2 |
| Email fără conținut text | Cererea e omisă silențios din rezultate |
| LLM nu poate extrage niciun produs | Rândul apare în listă cu mesaj „Nu s-au putut extrage produse" |
| Interval de date gol (niciun email) | Mesaj „Niciun email găsit în intervalul selectat" |

---

## Testare

Gmail API este mereu mock-uit în teste prin același pattern `_FakeGmail` (analog `_FakeLLM` existent).

| Test | Verifică |
|---|---|
| `test_fetch_emails_in_range` | `gmail_client.fetch_emails(start, end)` returnează doar emailurile din interval |
| `test_extract_single_product` | Email cu un singur produs → lista cu un `ProductRequest` |
| `test_extract_multiple_products` | Email cu 3 tipuri → lista cu 3 `ProductRequest` |
| `test_extract_partial_fields` | Câmpurile nedescrise lipsesc din `prefilled_state`, nu sunt null/inventate |
| `test_create_session_from_request` | `POST /email-agent/create-session` creează sesiune în DB cu starea pre-completată și redirect |
| `test_fetch_route_returns_list` | `POST /email-agent/fetch` returnează 200 cu lista de cereri în HTML |
| `test_fetch_route_empty_interval` | Niciun email în interval → mesaj corespunzător |

---

## Dependențe noi

```
google-auth-oauthlib>=1.2
google-api-python-client>=2.120
```
