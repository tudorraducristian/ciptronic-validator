# Agent Email Gmail — Spec de Design

**Data:** 2026-06-15
**Status:** Aprobat

---

## Context

Ciptronic Validator procesează în prezent produse printr-o interfață web (două fluxuri: Discovery/Flow A pentru descrieri text, Image Match/Flow B pentru poze mockup). Clienții interacționează exclusiv prin interfața web.

Acest spec descrie un agent email care monitorizează un inbox Gmail dedicat, procesează automat cererile de validare primite și răspunde cu un raport PDF — extinde sistemul existent fără a modifica logica de bază.

---

## Obiective

- Clienții trimit cereri de validare pe email (descriere text și/sau imagine mockup atașată)
- Un agent verifică Gmail-ul la fiecare 2–5 minute, clasifică emailul și rulează flow-ul corespunzător deja existent
- La finalizare, agentul răspunde clientului cu raportul ca fișier PDF atașat
- Un panou de monitorizare pentru operatori (`GET /email-jobs`) afișează toate emailurile procesate și statusul lor
- Emailurile ambigue declanșează automat un răspuns de clarificare; operatorul nu trebuie să intervină

---

## Non-Obiective (MVP)

- Notificări în timp real prin push (Gmail Pub/Sub) — amânat; polling-ul e suficient
- Flux hibrid (descriere text + mockup în același email ca un flux combinat) — exclus conform cerinței de business confirmate
- Interfață web pentru clienți — clienții interacționează exclusiv prin email
- Suport multi-limbă — doar română/engleză

---

## Arhitectură

### Abordare

Un nou modul Python `email_agent/` care importă direct din modulele existente (`agents.discovery`, `agents.inspector`, `image_matcher.engine`, `db.repository`). Rulează ca proces separat (`python -m email_agent.poller`) alături de `uvicorn`.

Zero duplicare de logică — agentul email este pur și simplu un adaptor de intrare peste fluxurile existente.

### Fișiere noi

```
email_agent/
├── __init__.py
├── gmail_client.py      # Autentificare OAuth2 + Gmail API: listare/citire/trimitere mesaje
├── email_parser.py      # Extragere subiect, corp, atașamente; clasificare LLM
├── dispatcher.py        # Rutare spre Flow A sau Flow B; scriere rând email_jobs
├── pdf_generator.py     # Randare HTML raport existent → PDF via WeasyPrint
├── notifier.py          # Trimitere email de răspuns cu PDF atașat via Gmail API
└── poller.py            # Loop de polling — punct de intrare (la fiecare 2 min)

db/
└── email_jobs.py        # CRUD pentru tabelul email_jobs

web/
├── app.py               # Adaugă GET /email-jobs + POST /email-jobs/{id}/retry
└── templates/
    └── email_jobs.html  # Panou de monitorizare
```

### Fișiere existente modificate

| Fișier | Modificare |
|---|---|
| `db/schema.sql` | Adaugă tabelul `email_jobs` |
| `requirements.txt` | Adaugă `google-auth-oauthlib`, `google-api-python-client`, `weasyprint` |
| `web/templates/base.html` | Adaugă link de navigare către Email Jobs |
| `.gitignore` | Adaugă `gmail_token.json`, `credentials.json` |

---

## Model de date

### Tabelul `email_jobs`

```sql
CREATE TABLE email_jobs (
    id                TEXT PRIMARY KEY,
    gmail_message_id  TEXT UNIQUE NOT NULL,   -- ID mesaj Gmail pentru deduplicare
    sender_email      TEXT NOT NULL,
    subject           TEXT,
    flow_type         TEXT,                   -- discovery | match | unclear | spam
    status            TEXT NOT NULL DEFAULT 'pending',
                                              -- pending | processing | done
                                              -- failed | needs_clarification | spam
    session_id        TEXT,                   -- FK → discovery_sessions sau match_sessions
    error_message     TEXT,
    received_at       DATETIME NOT NULL,
    processed_at      DATETIME
);
```

`gmail_message_id` are constrângere UNIQUE — poller-ul verifică acest câmp înainte de procesare pentru a preveni procesarea dublă la repornire sau suprapunere.

---

## Fluxul de procesare email

```
poller.py (la fiecare 2 min)
  └─ gmail_client.list_unread()
       └─ pentru fiecare mesaj:
            sari dacă gmail_message_id există deja în email_jobs (deduplicare)
            inserează rând email_jobs (status=pending)
            email_parser.classify(mesaj) → {flow_type, description, atașamente}
            dacă spam:
                actualizează status=spam, gata
            dacă unclear:
                notifier.send_clarification(expeditor)
                actualizează status=needs_clarification, gata
            dacă flow_type == "discovery":
                dispatcher.run_discovery(descriere) → session_id, report_id
                pdf_generator.render(report_id) → pdf_bytes
                notifier.send_report(expeditor, pdf_bytes)
                actualizează status=done
            dacă flow_type == "match":
                dispatcher.run_match(atașamente) → match_id, report_id
                pdf_generator.render(report_id) → pdf_bytes
                notifier.send_report(expeditor, pdf_bytes)
                actualizează status=done
            la eroare LLM: retry ×2 cu backoff; dacă tot eșuează → status=failed
```

### Prompt clasificare LLM (email_parser.py)

Claude primește subiectul emailului + textul corpului + lista numelor de fișiere/tipuri MIME ale atașamentelor. Returnează un obiect JSON:

```json
{
  "flow_type": "discovery" | "match" | "unclear" | "spam",
  "description": "<descriere produs extrasă dacă flow_type=discovery>",
  "mockup_attachment": "<nume fișier dacă flow_type=match>",
  "real_photo_attachment": "<nume fișier sau null>"
}
```

Dacă `flow_type=unclear`, agentul trimite un email de clarificare șablon care explică ce informații sunt necesare.

---

## Autentificare

Gmail API folosește OAuth2:

1. Dezvoltatorul creează un proiect Google Cloud, activează Gmail API, descarcă `credentials.json`
2. La primul run al `poller.py`, browserul se deschide pentru autorizare unică; token-ul se salvează în `gmail_token.json` (în gitignore)
3. La rulările ulterioare: token-ul se reîmprospătează automat via `google-auth-oauthlib`
4. Calea către `credentials.json` se configurează prin `.env` (`GMAIL_CREDENTIALS_PATH`)

Agentul trimite răspunsuri de pe aceeași adresă Gmail din care citește ("send as" via Gmail API).

---

## Gestionarea erorilor

| Scenariu | Comportament |
|---|---|
| Emailul nu poate fi clasificat | Răspuns cu email de clarificare; status → `needs_clarification` |
| Email spam/irelevant | Ignorat silențios; status → `spam`; niciun răspuns trimis |
| Atașament corupt / format nesuportat | Răspuns la expeditor cu eroarea specifică; status → `failed` |
| Timeout LLM / limită de rată | Retry ×2 cu backoff exponențial; dacă toate eșuează → status → `failed` |
| Gmail API indisponibil | Eroarea se loghează; poller-ul continuă la ciclul următor fără crash |
| Mesaj duplicat (repornire/suprapunere) | Sărit prin verificarea UNIQUE pe `gmail_message_id` |

---

## Panoul de monitorizare pentru operatori

`GET /email-jobs` — tabel paginat cu toate job-urile email, cele mai noi primele.

Coloane: expeditor, subiect, tip flow, status (codificat cu culori), timestamp primit, timestamp procesat, link la raport (dacă done), buton retry (dacă failed).

Contoare sumar în partea de sus: Procesate / Necesită clarificare / Eșuate.

`POST /email-jobs/{id}/retry` — repune în coadă un job eșuat pentru reprocesare imediată.

---

## Generare PDF

`pdf_generator.py` randează șablonul Jinja2 de raport existent (același HTML folosit în browser) în bytes PDF folosind **WeasyPrint**. PDF-ul este atașat emailului de răspuns cu numele fișierului `raport-ciptronic-{report_id}.pdf`.

WeasyPrint necesită ca CSS-ul static al raportului să fie inclus sau referit ca căi absolute — generatorul transmite `base_url` care indică directorul `web/static/`.

---

## Strategie de testare

Gmail API este mereu mock-uit în teste — `gmail_client.py` expune o interfață clară; testele injectează un fake care returnează payload-uri de email construite manual. Același pattern ca mock-ul `LLMClient` existent.

| Test | Verifică |
|---|---|
| `test_parser_flow_a` | Email doar cu text → clasificat `discovery`, descrierea extrasă |
| `test_parser_flow_b` | Email cu imagine atașată → clasificat `match`, atașamentul salvat |
| `test_parser_unclear` | Email ambiguu → status `unclear`, email de clarificare trimis |
| `test_parser_spam` | Email irelevant → ignorat, niciun răspuns trimis |
| `test_dispatcher_creates_session` | Dispatcher-ul scrie rândul corect în DB pentru Flow A și Flow B |
| `test_deduplication` | Același `gmail_message_id` procesat de două ori → al doilea ignorat |
| `test_llm_retry` | LLM eșuează o dată → retry automat, al doilea apel reușește |
| `test_pdf_generated` | PDF-ul generat are bytes valizi și non-goi |
| `test_email_jobs_panel` | `GET /email-jobs` returnează 200 și listează job-urile din DB |

---

## Dependențe noi

```
google-auth-oauthlib>=1.2
google-api-python-client>=2.120
weasyprint>=62.0
```

---

## În afara scopului

- Webhook push (Gmail Pub/Sub) — poate fi adăugat ulterior prin înlocuirea `poller.py` cu un endpoint `POST /gmail-webhook`; toate celelalte module rămân neschimbate
- Threading email (răspunsuri de la clienți la emailurile de clarificare) — amânat
- Atașamente multiple în Flow B (mai multe mockup-uri într-un singur email) — amânat; MVP gestionează doar prima imagine
