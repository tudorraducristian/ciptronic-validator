# Ciptronic Validator — Diagramă de arhitectură

Aplicație web locală (single-user) pe straturi: web subțire (FastAPI + HTMX) peste logica de domeniu din `agents/` (Flux A) și `image_matcher/engine.py` (Flux B), cu persistență SQLite și apeluri la Claude Sonnet 4.6.

## Diagramă Mermaid

```mermaid
flowchart TB
    subgraph CLIENT["Browser (single-user, local)"]
        UI["HTML + HTMX + Jinja2 templates<br/>web/templates · web/static/styles.css"]
    end

    subgraph ENTRY["Entry point"]
        MAIN["main.py → uvicorn<br/>from web.app import app"]
    end

    subgraph WEB["Web layer — web/app.py (FastAPI)"]
        RA["Rute Flux A<br/>/sessions · /answer · /validate · /reports"]
        RB["Rute Flux B<br/>/matches · /real · /report"]
        HZ["/healthz · / (landing)"]
    end

    subgraph AGENTS["Agent layer — agents/"]
        DISC["discovery.py<br/>build_messages · parse_response<br/>merge_answers · is_schema_complete"]
        INSP["inspector.py<br/>build_messages · parse_report"]
        LLMC["llm_client.py<br/>LLMClient: complete_text / complete_vision"]
    end

    subgraph ENGINE["image_matcher/engine.py"]
        ENG["analyze_sim · compare_real<br/>encode_image · parse_* · call_llm"]
    end

    subgraph SCHEMASL["schemas/"]
        SCH["loader.py + *.json (tricou.json)<br/>available_product_types · load_schema<br/>empty_state · applicable_leaf_keys"]
    end

    subgraph DATA["db/ — persistență"]
        REPO["repository.py<br/>create/update/finalize/save"]
        SQL["schema.sql<br/>discovery_sessions · validation_reports · match_sessions"]
    end

    subgraph PROMPTS["prompts/"]
        PR["discovery.md · inspector.md<br/>(SIM/COMPARE prompts inline în engine)"]
    end

    EXT{{"Anthropic API<br/>Claude Sonnet 4.6"}}
    DB[(SQLite<br/>ciptronic.db)]
    FS[/"Filesystem<br/>uploads/"/]

    STREAMLIT["image_matcher/app.py · run.py<br/>(Streamlit standalone, dev tool)"]

    UI <--> WEB
    MAIN --> WEB
    RA --> DISC & INSP & SCH & REPO
    RB --> ENG & REPO
    DISC --> PR
    INSP --> PR
    DISC -.-> LLMC
    INSP -.-> LLMC
    LLMC --> EXT
    ENG --> EXT
    REPO --> DB
    SQL -. init .-> DB
    RA --> FS
    RB --> FS
    STREAMLIT --> ENG
```

## Diagramă ASCII

```
┌──────────────────────────────────────────────────────────────────────────┐
│  BROWSER (local, single-user)   HTML + HTMX + Jinja2 (web/templates)       │
└───────────────────────────────┬────────────────────────────────────────────┘
                                 │ HTTP
                    ┌────────────▼─────────────┐        main.py → uvicorn
                    │   WEB LAYER  web/app.py   │◄────── (from web.app import app)
                    │   FastAPI routes          │
                    │  ┌─────────────────────┐  │
                    │  │ Flux A: /sessions   │  │
                    │  │   /answer /validate │  │
                    │  │   /reports          │  │
                    │  ├─────────────────────┤  │
                    │  │ Flux B: /matches    │  │
                    │  │   /real /report     │  │
                    │  └─────────────────────┘  │
                    └──┬─────────┬─────────┬─────┘
          ┌────────────┘         │         └──────────────┐
          ▼                      ▼                        ▼
┌──────────────────┐   ┌──────────────────┐   ┌─────────────────────────┐
│ AGENTS (Flux A)  │   │ image_matcher/   │   │ schemas/loader.py        │
│ discovery.py     │   │ engine.py        │   │  + tricou.json           │
│ inspector.py     │   │ analyze_sim      │   │ load_schema/empty_state  │
│ llm_client.py    │   │ compare_real     │   └─────────────────────────┘
└───────┬──────────┘   └────────┬─────────┘
        │ prompts/               │  (prompts inline)         ┌───────────────┐
        │ discovery.md           │                           │ db/repository │
        │ inspector.md           │                           │  + schema.sql │
        ▼                        ▼                            └──────┬────────┘
   ┌─────────────────────────────────────┐                          │
   │   Anthropic API — Claude Sonnet 4.6  │                          ▼
   │   (complete_text / complete_vision)  │                  ┌───────────────┐
   └─────────────────────────────────────┘                  │ SQLite        │
                                                             │ ciptronic.db  │
   ┌─────────────────────────────────────┐                  │ • discovery_  │
   │  uploads/  (poze sim/real/validare)  │◄── Web layer     │   sessions    │
   └─────────────────────────────────────┘    scrie fișiere │ • validation_ │
                                                             │   reports     │
   ┌─────────────────────────────────────────┐              │ • match_      │
   │ image_matcher/app.py + run.py (Streamlit)│──► engine.py │   sessions    │
   │ dev tool standalone, separat de FastAPI  │              └───────────────┘
   └─────────────────────────────────────────┘
```

## Note de arhitectură

- **Strat web subțire:** `web/app.py` orchestrează, dar nu conține logică de domeniu — deleagă la `agents/` (Flux A) și `image_matcher/engine.py` (Flux B).
- **Două căi LLM diferite:** Flux A trece prin `LLMClient` (wrapper subțire, prompturi în `prompts/*.md`); Flux B are propriul `call_llm` în engine (cu retry + prompturi inline). Ambele lovesc același model Sonnet 4.6.
- **Funcții pure vs. I/O:** atât `agents/` cât și `engine.py` separă parsarea/validarea (testabile unit) de apelurile API (verificate manual).
- **Extensibilitate fără cod:** un tip de produs nou = doar un `schemas/<nume>.json`; `loader.py` îl ridică automat în dropdown.
- **Streamlit-ul rămâne separat:** `image_matcher/app.py` e un dev tool standalone care refolosește același `engine.py`, fără să atingă FastAPI sau DB-ul.
