# Gmail Email Agent — Design Spec

**Date:** 2026-06-15
**Status:** Approved

---

## Context

Ciptronic Validator currently processes products via a web UI (two flows: Discovery/Flow A for text descriptions, Image Match/Flow B for mockup photos). Clients currently interact only through the web interface.

This spec describes an email agent that monitors a dedicated Gmail inbox, automatically processes incoming validation requests, and replies with a PDF report — extending the existing system without modifying its core logic.

---

## Goals

- Clients send validation requests by email (text description and/or mockup image attachment)
- An agent polls Gmail every 2–5 minutes, classifies the email, and runs the appropriate existing flow
- On completion, the agent replies to the client with the report as a PDF attachment
- An operator dashboard (`GET /email-jobs`) shows all processed emails and their status
- Ambiguous emails trigger an automatic clarification reply; the operator is not required to intervene

---

## Non-Goals (MVP)

- Real-time push notifications (Gmail Pub/Sub) — deferred; polling is sufficient
- Hybrid flow (text description + mockup in the same email as a single combined flow) — excluded per confirmed business requirement
- Web UI for clients — clients interact only via email
- Multi-language email support — Romanian/English only

---

## Architecture

### Approach

A new `email_agent/` Python module that imports directly from existing modules (`agents.discovery`, `agents.inspector`, `image_matcher.engine`, `db.repository`). Runs as a separate process (`python -m email_agent.poller`) alongside `uvicorn`.

Zero logic duplication — the email agent is purely an input adapter over the existing flows.

### New files

```
email_agent/
├── __init__.py
├── gmail_client.py      # OAuth2 auth + Gmail API: list/read/send messages
├── email_parser.py      # Extract subject, body, attachments; LLM classification
├── dispatcher.py        # Route to Flow A or Flow B; write email_jobs row
├── pdf_generator.py     # Render existing report HTML → PDF via WeasyPrint
├── notifier.py          # Send reply email with PDF attachment via Gmail API
└── poller.py            # Polling loop entry point (every 2 min)

db/
└── email_jobs.py        # CRUD for email_jobs table

web/
├── app.py               # Add GET /email-jobs + POST /email-jobs/{id}/retry
└── templates/
    └── email_jobs.html  # Monitoring dashboard
```

### Existing files changed

| File | Change |
|---|---|
| `db/schema.sql` | Add `email_jobs` table |
| `requirements.txt` | Add `google-auth-oauthlib`, `google-api-python-client`, `weasyprint` |
| `web/templates/base.html` | Add nav link to Email Jobs |
| `.gitignore` | Add `gmail_token.json`, `credentials.json` |

---

## Data Model

### `email_jobs` table

```sql
CREATE TABLE email_jobs (
    id                TEXT PRIMARY KEY,
    gmail_message_id  TEXT UNIQUE NOT NULL,   -- Gmail message ID for deduplication
    sender_email      TEXT NOT NULL,
    subject           TEXT,
    flow_type         TEXT,                   -- discovery | match | unclear | spam
    status            TEXT NOT NULL DEFAULT 'pending',
                                              -- pending | processing | done
                                              -- failed | needs_clarification | spam
    session_id        TEXT,                   -- FK → discovery_sessions or match_sessions
    error_message     TEXT,
    received_at       DATETIME NOT NULL,
    processed_at      DATETIME
);
```

`gmail_message_id` carries a UNIQUE constraint — the poller checks this before processing to prevent double-processing on restart or overlap.

---

## Email Processing Flow

```
poller.py (every 2 min)
  └─ gmail_client.list_unread()
       └─ for each message:
            skip if gmail_message_id already in email_jobs (deduplication)
            insert email_jobs row (status=pending)
            email_parser.classify(message) → {flow_type, description, attachments}
            if spam:
                update status=spam, done
            if unclear:
                notifier.send_clarification(sender)
                update status=needs_clarification, done
            if flow_type == "discovery":
                dispatcher.run_discovery(description) → session_id, report_id
                pdf_generator.render(report_id) → pdf_bytes
                notifier.send_report(sender, pdf_bytes)
                update status=done
            if flow_type == "match":
                dispatcher.run_match(attachments) → match_id, report_id
                pdf_generator.render(report_id) → pdf_bytes
                notifier.send_report(sender, pdf_bytes)
                update status=done
            on LLM error: retry ×2 with backoff; if still failing → status=failed
```

### LLM Classification Prompt (email_parser.py)

Claude receives the email subject + body text + list of attachment filenames/MIME types. It returns a JSON object:

```json
{
  "flow_type": "discovery" | "match" | "unclear" | "spam",
  "description": "<extracted product description if flow_type=discovery>",
  "mockup_attachment": "<filename if flow_type=match>",
  "real_photo_attachment": "<filename or null>"
}
```

If `flow_type=unclear`, the agent sends a templated clarification email explaining what information is needed.

---

## Authentication

Gmail API uses OAuth2:

1. Developer creates a Google Cloud project, enables Gmail API, downloads `credentials.json`
2. On first run of `poller.py`, browser opens for one-time authorization; token saved to `gmail_token.json` (gitignored)
3. Subsequent runs: token refreshes automatically via `google-auth-oauthlib`
4. `credentials.json` path configured via `.env` (`GMAIL_CREDENTIALS_PATH`)

The agent sends replies from the same Gmail address it reads from ("send as" via Gmail API).

---

## Error Handling

| Scenario | Behaviour |
|---|---|
| Email cannot be classified | Reply with clarification email; status → `needs_clarification` |
| Email is spam/irrelevant | Ignored silently; status → `spam`; no reply sent |
| Corrupt attachment / unsupported format | Reply to sender with specific error; status → `failed` |
| LLM timeout / rate limit | Retry ×2 with exponential backoff; if all fail → status → `failed` |
| Gmail API unavailable | Log error; poller continues on next cycle without crashing |
| Duplicate message (restart/overlap) | Skipped via `gmail_message_id` UNIQUE check |

---

## Operator Dashboard

`GET /email-jobs` — paginated table of all email jobs, newest first.

Columns: sender, subject, flow type, status (colour-coded), received timestamp, processed timestamp, link to report (if done), retry button (if failed).

`POST /email-jobs/{id}/retry` — re-queues a failed job for immediate reprocessing.

Summary counters at top: Done / Needs clarification / Failed.

---

## PDF Generation

`pdf_generator.py` renders the existing Jinja2 report template (same HTML used in the browser) to PDF bytes using **WeasyPrint**. The PDF is attached to the reply email with filename `raport-ciptronic-{report_id}.pdf`.

WeasyPrint requires the report's static CSS to be embedded or referenced as absolute file paths — the generator passes `base_url` pointing to the `web/static/` directory.

---

## Testing Strategy

Gmail API is always mocked in tests — `gmail_client.py` exposes a clean interface; tests inject a fake that returns hand-crafted email payloads. Same pattern as the existing `LLMClient` mock.

| Test | Verifies |
|---|---|
| `test_parser_flow_a` | Text-only email → classified `discovery`, description extracted |
| `test_parser_flow_b` | Image attachment email → classified `match`, attachment saved |
| `test_parser_unclear` | Ambiguous email → status `unclear`, clarification sent |
| `test_parser_spam` | Irrelevant email → ignored, no reply sent |
| `test_dispatcher_creates_session` | Dispatcher writes correct DB row for Flow A and Flow B |
| `test_deduplication` | Same `gmail_message_id` processed twice → second ignored |
| `test_llm_retry` | LLM fails once → auto-retry, second call succeeds |
| `test_pdf_generated` | Generated PDF is valid non-empty bytes |
| `test_email_jobs_panel` | `GET /email-jobs` returns 200, lists jobs from DB |

---

## New Dependencies

```
google-auth-oauthlib>=1.2
google-api-python-client>=2.120
weasyprint>=62.0
```

---

## Out of Scope

- Push webhook (Gmail Pub/Sub) — can be added later by replacing `poller.py` with a `POST /gmail-webhook` endpoint; all other modules unchanged
- Email threading (replies from clients to clarification emails) — deferred
- Multi-attachment Flow B (multiple mockups in one email) — deferred; MVP handles first image only
