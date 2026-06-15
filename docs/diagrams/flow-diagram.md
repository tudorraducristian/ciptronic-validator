# Ciptronic Validator — Diagramă de flux

Aplicație web locală cu două fluxuri paralele, independente, ambele persistate în `ciptronic.db` și folosind Claude Sonnet 4.6 (text + vision).

## Diagramă Mermaid

```mermaid
flowchart TD
    Start([Utilizator]) --> Landing["GET / — landing<br/>Două cards"]
    Landing -->|"Am o descriere"| A0
    Landing -->|"Am un mockup"| B0

    subgraph FLOW_A["FLUX A — Discovery + Inspector (text)"]
        A0["GET /sessions/new<br/>dropdown tip produs + textarea"] --> A1
        A1["POST /sessions<br/>load_schema → empty_state<br/>discovery LLM (runda 1)"] --> A2
        A2["GET /sessions/{id}<br/>stare câmpuri + întrebări"] --> A3{done &<br/>schema completă?}
        A3 -->|nu| A4["POST /sessions/{id}/answer<br/>merge_answers → discovery LLM<br/>HTMX swap rundă nouă"]
        A4 --> A5{rundă > 5?}
        A5 -->|da| A6["finalize forțat"]
        A5 -->|nu| A3
        A3 -->|da| A7["buton: Validează cu poze"]
        A6 --> A7
        A7 --> A8["GET /sessions/{id}/validate<br/>spec JSON + upload 1-4 poze"]
        A8 --> A9["POST /sessions/{id}/validate<br/>inspector VISION LLM<br/>parse_report → save_report"]
        A9 --> A10["GET /reports/{rid}<br/>3 zone: Conform / Neconform / Nevizibil"]
    end

    subgraph FLOW_B["FLUX B — Image Match (imagine)"]
        B0["GET /matches/new<br/>upload mockup (sim)"] --> B1
        B1["POST /matches<br/>analyze_sim — VISION LLM<br/>extrage criterii"] --> B2
        B2["GET /matches/{id}<br/>match_wait: listă criterii<br/>+ upload poză reală"] --> B3
        B3["POST /matches/{id}/real<br/>compare_real(sim_report, real)<br/>VISION LLM + 1 retry"] --> B4
        B4["GET /matches/{id}/report<br/>tabel rows + summary<br/>match_type / confidence"]
    end

    A1 -.-> DB[(SQLite ciptronic.db<br/>sessions · reports · match_sessions)]
    A9 -.-> DB
    B1 -.-> DB
    B3 -.-> DB

    A1 -.-> LLM{{Anthropic<br/>Claude Sonnet 4.6}}
    A9 -.-> LLM
    A4 -.-> LLM
    B1 -.-> LLM
    B3 -.-> LLM
```

## Diagramă ASCII (terminal)

```
                          ┌─────────────────────────┐
                          │   GET /  (landing page)  │
                          │   ┌───────┐  ┌────────┐  │
                          │   │descri-│  │ mockup │  │
                          │   │ ere   │  │        │  │
                          └───┴───┬───┴──┴───┬────┴──┘
              "Am o descriere"    │          │   "Am un mockup"
            ┌───────────────────◄─┘          └─►──────────────────┐
            ▼                                                      ▼
╔══════════════════════════════════╗          ╔══════════════════════════════════╗
║  FLUX A — Discovery + Inspector  ║          ║      FLUX B — Image Match        ║
╠══════════════════════════════════╣          ╠══════════════════════════════════╣
║ GET /sessions/new                ║          ║ GET /matches/new                 ║
║   dropdown tip + descriere       ║          ║   upload mockup (sim)            ║
║            │                     ║          ║            │                     ║
║            ▼                     ║          ║            ▼                     ║
║ POST /sessions                   ║          ║ POST /matches                    ║
║   schema → empty_state           ║          ║   analyze_sim()  [VISION LLM]    ║
║   discovery LLM  (runda 1)       ║          ║   → extrage criterii             ║
║            │                     ║          ║            │                     ║
║            ▼                     ║          ║            ▼                     ║
║ GET /sessions/{id}               ║          ║ GET /matches/{id}  (wait)        ║
║   stare câmpuri + întrebări      ║          ║   listă criterii + upload real   ║
║            │                     ║          ║            │                     ║
║      ┌─────┴──────┐              ║          ║            ▼                     ║
║   done & schema completă?        ║          ║ POST /matches/{id}/real          ║
║      │ nu       │ da             ║          ║   compare_real()  [VISION LLM]   ║
║      ▼          │                ║          ║   sim_report vs poză reală       ║
║ POST .../answer │                ║          ║   (+1 retry la parse fail)       ║
║  merge_answers  │                ║          ║            │                     ║
║  discovery LLM  │                ║          ║            ▼                     ║
║  (HTMX swap)    │                ║          ║ GET /matches/{id}/report         ║
║      │          │                ║          ║   tabel rows + summary           ║
║  runda > 5? ────┤ (finalize)     ║          ║   match_type / confidence        ║
║      └──►───────┤                ║          ╚══════════════════════════════════╝
║                 ▼                ║
║ GET .../validate                 ║
║   spec JSON + upload 1-4 poze    ║          ┌───────────────────────────────┐
║            │                     ║          │  SQLite  ciptronic.db         │
║            ▼                     ║   ◄──────│   • sessions                  │
║ POST .../validate                ║   toate  │   • reports                   │
║   inspector()  [VISION LLM]      ║   rutele │   • match_sessions            │
║   parse_report → save_report     ║   scriu  └───────────────────────────────┘
║            │                     ║
║            ▼                     ║          ┌───────────────────────────────┐
║ GET /reports/{rid}               ║   ◄──────│  Anthropic Claude Sonnet 4.6  │
║   Conform │ Neconform │ Nevizibil║   apeluri│  (text + vision)              │
╚══════════════════════════════════╝   LLM    └───────────────────────────────┘
```

## Pe scurt

- **Două fluxuri paralele** pornind din landing-ul `/`, complet independente, ambele persistate în `ciptronic.db`.
- **Flux A (text):** descriere vagă → întrebări iterative (max 5 runde, închidere forțată la a 5-a) → la `done` + schemă completă se trece la validarea cu 1–4 poze → raport pe trei zone (Conform / Neconform / Nevizibil).
- **Flux B (imagine):** mockup → `analyze_sim` extrage criteriile → poză reală → `compare_real` confruntă criteriu-cu-criteriu → tabel cu `match_type` și `confidence`.
- **Apeluri LLM:** runda de discovery și ambele apeluri vision (inspector, analyze_sim / compare_real) merg la Claude Sonnet 4.6; `compare_real` are un retry cu hint corectiv la eșec de parse.
