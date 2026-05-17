# Ciptronic Product Validator — Design

**Date:** 2026-05-17
**Author:** brainstorming session, Claude Code + user
**Status:** Approved (ready for implementation plan)

## Goal

O aplicație web locală, în limba română, care automatizează două etape ale comenzilor de produse personalizate la Ciptronic:

1. **Discovery Agent** — transformă o descriere vagă a clientului ("o bluză cu logo pe piept") într-un JSON structurat complet, punând întrebări țintite, grupate, în maximum 5 runde.
2. **Inspector Agent** — primește JSON-ul rezultat + 1–4 poze ale produsului finit și emite un raport cu trei categorii: `conform[]`, `neconform[]`, `nevizibil[]`, marcând explicit ce nu se poate vedea în poze.

Proiectul folosește același workflow superpowers (brainstorming → spec → plan → TDD → review) ca `sp_learn`. Atât rezultatul cât și procesul contează.

## Stack

- **Limbaj:** Python 3.10+
- **Web:** FastAPI + HTMX + Jinja2 (server-rendered partials, fără framework JS)
- **DB:** SQLite (un singur fișier, fără server)
- **LLM:** Anthropic SDK, model **Claude Sonnet 4.6** (`claude-sonnet-4-6`) — același model pentru text și vision
- **Teste:** pytest
- **OS dezvoltare:** Windows (paralel cu sp_learn)

### De ce acest stack

- **FastAPI + HTMX** vs SPA: aplicația e local-first, un user, fluxuri liniare. HTMX dă interactivitate suficientă (swap partial-uri server-rendered) fără a întreține un build de frontend. Jinja e Python-native.
- **SQLite** vs in-memory: brief-ul cere persistență; SQLite e zero-config, e un fișier, suportă JSON-in-column nativ pentru schemele dinamice de produs.
- **Claude Sonnet 4.6** vs 4.5 (din brief original): 4.6 e curent, are vision, e mai puternic la prețuri similare. Decizia confirmată în brainstorming.

## Architecture

### Structura de foldere

```
ciptronic_validator/
├── agents/
│   ├── __init__.py
│   ├── discovery.py        # pur: build_messages, parse_response, is_complete, merge
│   ├── inspector.py        # pur: build_messages (cu base64), parse_report
│   └── llm_client.py       # wrapper subțire peste Anthropic SDK
├── prompts/
│   ├── discovery.md        # prompt sistem versionat, română
│   └── inspector.md
├── schemas/
│   └── tricou.json         # MVP; sapca.json/hanorac.json vin după MVP
├── db/
│   ├── schema.sql          # CREATE TABLE
│   └── repository.py       # funcții CRUD pure pe sessions și reports
├── web/
│   ├── app.py              # FastAPI: route-uri
│   └── templates/
│       ├── base.html       # layout, CSS minim inline
│       ├── index.html      # landing
│       ├── session.html    # vederea sesiunii Discovery
│       ├── _session_body.html  # partial HTMX swap-uit
│       ├── validate.html   # form upload
│       └── report.html     # raportul Inspector
├── uploads/                # poze încărcate, organizate per sesiune (gitignored)
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── e2e/
│   └── fixtures/
├── docs/superpowers/
│   ├── specs/2026-05-17-ciptronic-validator-design.md
│   └── plans/2026-05-17-ciptronic-validator.md
├── main.py                 # uvicorn entry point
├── requirements.txt
├── .env.example            # ANTHROPIC_API_KEY=...
├── .gitignore
└── README.md
```

### Frontiere între module

Modulele sunt separate astfel încât să răspundă curat la întrebările: *ce face*, *cu ce*, *cum se testează*.

| Modul | Ce face | Depinde de | Testabil cum |
|---|---|---|---|
| `agents/discovery.py` | Pur: build_messages, parse_response, is_schema_complete, merge_answers | doar JSON schema, fără rețea | Unit, cu fixtures de răspunsuri LLM |
| `agents/inspector.py` | Pur: build_messages (citește poze de pe disc + base64), parse_report (validare "fiecare câmp exact o dată") | dataclasses, base64 | Unit, cu fixtures |
| `agents/llm_client.py` | Apelează Anthropic API, returnează text | `anthropic` SDK, `ANTHROPIC_API_KEY` | Un singur integration test happy-path; restul cu mock |
| `db/repository.py` | CRUD pe sessions și reports | `sqlite3` | Unit, cu SQLite in-memory |
| `web/app.py` | Route-uri FastAPI; orchestrează agenți + DB | toate de mai sus | E2E cu FastAPI TestClient + LLM mock |

Codul "greu" (agenți + DB) e 100% testabil fără să atingem Anthropic API. Filosofia sp_learn aplicată la o app mai mare.

## Modelul de date

### Schemele de produs ca fișiere JSON

Pentru extensibilitate ("adaug șapcă fără să schimb cod"), schemele trăiesc în `schemas/*.json`, nu în DB. Adăugarea unui tip nou = un fișier nou; deployment-ul nu necesită migrare.

Format pentru `schemas/tricou.json`:

```json
{
  "id": "tricou",
  "name_ro": "Tricou",
  "fields": [
    { "key": "culoare_principala", "label": "Culoare principală",
      "hint": "ex: roșu, negru, alb melange" },
    { "key": "material", "label": "Material",
      "hint": "ex: bumbac 100%, poliester, mix" },
    { "key": "croiala", "label": "Croială",
      "hint": "regular / slim / oversize" },
    { "key": "guler", "label": "Tip guler",
      "hint": "rotund / V / polo" },
    { "key": "maneci", "label": "Mâneci",
      "hint": "scurte / lungi / 3/4" },
    { "key": "branding", "label": "Branding (logo/print/imprimeu)",
      "type": "object",
      "allow_none_value": "fără branding",
      "subfields": [
        { "key": "pozitie", "label": "Poziție",
          "hint": "ex: piept stâng, spate centru" },
        { "key": "tehnica", "label": "Tehnică",
          "hint": "serigrafie / broderie / DTF / sublimare" },
        { "key": "culori", "label": "Culori", "type": "list" },
        { "key": "dimensiuni_aproximative", "label": "Dimensiuni aproximative",
          "hint": "ex: 10cm x 10cm" }
      ]
    }
  ]
}
```

**Notă vs ANEXA brief-ului:** schema brief-ului avea `tip_produs` ca prim câmp al checklist-ului. În acest design, `tip_produs` e *metadata* a schemei (cheile `id` și `name_ro`) — nu un câmp pe care îl întrebăm pe user, pentru că userul alege explicit tipul dintr-un dropdown pe pagina landing înainte să introducă descrierea. Această decizie a fost luată explicit în brainstorming: simplifică Discovery (zero ambiguitate, zero rundă pentru "ce produs e ăsta?"), cu compromisul că pierdem capacitatea descrisă în brief de a infera tipul din descriere.

**Comportamentul `branding`:** mereu prezent în schemă ca obiect. `allow_none_value` îi permite să fie marcat explicit "fără branding" — atunci sub-câmpurile rămân null și nu sunt întrebate. Inspector verifică absența brandingului dacă spec-ul îl marchează astfel.

### Schema SQLite

```sql
-- db/schema.sql

CREATE TABLE discovery_sessions (
    id              TEXT PRIMARY KEY,          -- uuid4
    product_type    TEXT NOT NULL,             -- "tricou", "sapca", ...
    initial_description TEXT NOT NULL,
    state_json      TEXT NOT NULL,             -- JSON parțial, evoluează
    history_json    TEXT NOT NULL,             -- [{round, intrebari, raspunsuri}, ...]
    status          TEXT NOT NULL
                    CHECK (status IN ('in_progress', 'complete', 'abandoned')),
    rounds_used     INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at    TEXT
);

CREATE INDEX idx_sessions_status ON discovery_sessions(status);

CREATE TABLE validation_reports (
    id              TEXT PRIMARY KEY,          -- uuid4
    session_id      TEXT NOT NULL REFERENCES discovery_sessions(id),
    spec_json       TEXT NOT NULL,             -- copie a state_json la momentul validării
    image_paths_json TEXT NOT NULL,            -- ["uploads/{id}/img1.jpg", ...]
    conform_json     TEXT NOT NULL,
    neconform_json   TEXT NOT NULL,
    nevizibil_json   TEXT NOT NULL,
    raw_llm_response TEXT NOT NULL,            -- text brut, pentru debug
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**De ce JSON-in-TEXT, nu tabele relaționale per câmp:** schema produsului e dinamică — un tricou are alte câmpuri decât o șapcă. EAV ar fi oribil; migrare per produs ar fi inacceptabilă. SQLite are `json_extract` dacă vrem să interogăm ulterior.

**Imaginile pe disc**, nu în DB: `uploads/{session_id}/img1.jpg`. DB ține doar calea.

### Repository API (`db/repository.py`)

Funcții pure care primesc o conexiune deja deschisă — testabile cu SQLite in-memory.

```python
def create_session(conn, product_type: str, description: str) -> str: ...
def update_session_state(conn, session_id: str, state: dict, history: list, rounds: int) -> None: ...
def finalize_session(conn, session_id: str) -> None: ...
def get_session(conn, session_id: str) -> dict: ...

def save_report(conn, session_id: str, spec: dict, image_paths: list[str],
                conform: list, neconform: list, nevizibil: list, raw: str) -> str: ...
def get_report(conn, report_id: str) -> dict: ...
```

## Discovery Agent

### Flux

```
┌─────────────────────────────────────────────────────────────┐
│ Runda 0 (start)                                             │
│   user selectează tip produs + tastează descrierea          │
│   → backend creează sesiune cu state vid                    │
│   → backend apelează LLM cu (schema, descriere, state vid)  │
│   ← LLM returnează (state parțial, întrebări, done=false)   │
│   → UI afișează întrebările                                 │
└─────────────────────────────────────────────────────────────┘
                          ↓ user răspunde
┌─────────────────────────────────────────────────────────────┐
│ Runda N (N=1..5)                                            │
│   backend merge(state, raspunsuri) → state_nou              │
│   backend apelează LLM cu (schema, state_nou, history)      │
│   ← LLM returnează (state actualizat, întrebări, done)      │
│   cod validează: toate câmpurile non-null?                  │
│     da, și done=true       → finalize, trecem la Inspector  │
│     done=true dar lipsesc → force another round cu hint     │
│     done=false              → afișează întrebări noi        │
│   dacă rounds_used == 5     → finalize cu marcaje "missing" │
└─────────────────────────────────────────────────────────────┘
```

Fiecare apel LLM este o **funcție pură**: system prompt static + un singur user message care conține tot contextul (schema, state, history). Nu folosim message threading nativ Claude (alternarea user/assistant). Trade-off: testarea trivială, debugging liniar, fiecare apel reproducibil cu un singur snapshot.

### Contract I/O LLM

**Input** (`build_messages`):
```python
system = open("prompts/discovery.md").read()
user = json.dumps({
    "schema": <dict din schemas/tricou.json>,
    "initial_description": "O bluză cu logo pe piept",
    "current_state": <dict, parțial>,
    "history": [
        {"round": 1, "questions": [...], "answers": {...}},
        {"round": 2, "questions": [...], "answers": {...}}
    ]
}, ensure_ascii=False, indent=2)
```

**Output** (JSON strict):
```json
{
  "state": {
    "culoare_principala": "albastru navy",
    "material": null,
    "croiala": null,
    "guler": null,
    "maneci": null,
    "branding": {
      "pozitie": "piept stâng",
      "tehnica": null,
      "culori": [],
      "dimensiuni_aproximative": null
    }
  },
  "intrebari": [
    { "id": "material", "text": "Ce material preferi?",
      "variante": ["bumbac 100%", "bumbac+poliester", "poliester"] },
    { "id": "branding.tehnica", "text": "Ce tehnică de aplicare a logo-ului?",
      "variante": ["serigrafie", "broderie", "DTF", "sublimare"] }
  ],
  "done": false
}
```

`parse_response` validează formatul cu Pydantic. Pe failure → o singură retry cu hint "JSON strict, te rog". A doua eșuare → 500 către UI cu mesaj clar.

### Prompt — `prompts/discovery.md`

```markdown
Ești asistentul Ciptronic pentru specificarea produselor personalizate.
Rolul tău: pornind de la o descriere vagă a clientului, completezi metodic
un checklist de caracteristici prin întrebări țintite, în limba română.

## Reguli stricte

1. RĂSPUNZI EXCLUSIV cu un obiect JSON valid, fără text înainte sau după.
2. Întrebările tale sunt în română, scurte (max o propoziție), clare.
3. Maximum 4 întrebări per rundă. Grupează-le tematic.
4. Pentru câmpuri cu opțiuni standard (croială, guler, tehnică), oferă o
   listă `variante` ca să ușurezi răspunsul userului.
5. Nu inventa. Dacă o caracteristică nu apare în descriere și nici în
   răspunsurile userului, las-o `null` și întreab-o la runda următoare.
6. Pentru câmpul `branding`: dacă userul spune "fără branding/print/logo"
   sau echivalent, completează-l ca:
   { "pozitie": "fără branding", "tehnica": null, "culori": [],
     "dimensiuni_aproximative": null }
   și consideră-l complet.
7. Marchezi `done: true` DOAR când toate câmpurile (inclusiv sub-câmpurile
   `branding` sau marcajul "fără branding") sunt non-null.
8. Dacă userul răspunde ambiguu sau contradictoriu, întreabă clarificator
   la runda următoare — NU presupune.

## Input

Vei primi în mesajul user un JSON cu:
- `schema`: definiția completă a checklist-ului pentru tipul de produs
- `initial_description`: ce a scris userul la start
- `current_state`: checklist-ul completat parțial până acum
- `history`: rundele anterioare (întrebări puse și răspunsuri primite)

## Output

Returnezi un obiect JSON cu structura:

\`\`\`json
{
  "state": { /* schema completată parțial cu valorile cunoscute */ },
  "intrebari": [
    { "id": "<cheia câmpului sau cheia.subcheia>",
      "text": "<întrebarea în română>",
      "variante": ["<opțiune1>", "<opțiune2>"] }
  ],
  "done": <true|false>
}
\`\`\`

Pentru sub-câmpuri de branding, `id` este `branding.pozitie`, `branding.tehnica`, etc.
Câmpul `variante` e opțional — îl pui doar când are sens să oferi opțiuni standard.

Când `done: true`, lista `intrebari` e goală.
```

### API intern `agents/discovery.py`

```python
def build_messages(schema: dict, initial_description: str,
                   state: dict, history: list) -> tuple[str, str]:
    """Returnează (system_prompt, user_message). Pur."""

def parse_response(text: str) -> DiscoveryStep:
    """Parsează JSON-ul LLM-ului. Ridică ValueError pe format invalid."""

def is_schema_complete(schema: dict, state: dict) -> tuple[bool, list[str]]:
    """Verifică dacă toate câmpurile schemei sunt non-null (sau 'fără branding').
    Returnează (complete, missing_keys)."""

def merge_answers(state: dict, answers: dict) -> dict:
    """Aplică răspunsurile peste state. Suportă chei cu punct (branding.tehnica)."""
```

## Inspector Agent

### Flux

```
Pre-condiții: o sesiune Discovery cu status='complete'

user încarcă 1–4 poze
→ backend salvează în uploads/{session_id}/img{N}.jpg
→ backend citește pozele, base64
→ backend apelează LLM vision cu (spec, imagini)
← LLM returnează (conform[], neconform[], nevizibil[])
→ backend salvează report în DB
→ UI afișează rezultatul în trei zone
```

Un singur apel LLM. Toate imaginile + spec-ul intră într-un singur user message. Inspector nu pune întrebări userului.

### Contract I/O LLM

**Input** către Claude:
- `system`: `prompts/inspector.md`
- `messages`: un singur user message conținând:
  - blocuri `image` pentru fiecare poză (base64)
  - bloc `text` cu spec-ul JSON și numărul pozelor

**Output** așteptat (JSON strict):
```json
{
  "conform": [
    { "camp": "culoare_principala",
      "valoare_asteptata": "albastru navy",
      "valoare_observata": "albastru navy",
      "incredere": "ridicat",
      "motiv": "culoarea e clar vizibilă în pozele 1 și 2" }
  ],
  "neconform": [
    { "camp": "branding.tehnica",
      "valoare_asteptata": "serigrafie",
      "valoare_observata": "pare DTF (suprafață mat-plastică, nu absorbită în țesătură)",
      "incredere": "mediu",
      "motiv": "în poza 3 se vede o textură ridicată, caracteristică DTF" }
  ],
  "nevizibil": [
    { "camp": "material",
      "valoare_asteptata": "bumbac 100%",
      "motiv": "țesătura nu se vede de aproape în niciuna dintre poze" }
  ]
}
```

**Reguli formale (validate în cod, nu doar în prompt):**
- Fiecare **câmp-frunză aplicabil** al schemei apare **exact o dată** în una din cele trei liste. Pentru schema tricou, câmpurile-frunză sunt: `culoare_principala`, `material`, `croiala`, `guler`, `maneci`, `branding.pozitie`, `branding.tehnica`, `branding.culori`, `branding.dimensiuni_aproximative` (9 câmpuri când branding e activ).
- **Excepție pentru "fără branding"**: dacă spec-ul are `branding.pozitie = "fără branding"`, atunci în raport apare **doar** `branding.pozitie` (verifică absența logo-ului). Celelalte 3 sub-câmpuri (`tehnica`, `culori`, `dimensiuni`) **nu se raportează** — nu sunt aplicabile. Total câmpuri raportate în acest caz: 6.
- `incredere` are doar valorile `"scăzut" | "mediu" | "ridicat"`.
- `motiv` e obligatoriu (în special pentru `nevizibil`).
- Pentru `branding` marcat "fără branding" în spec, apariția unui logo în poze = neconform pe `branding.pozitie`.

### Prompt — `prompts/inspector.md`

```markdown
Ești inspectorul vizual Ciptronic pentru produse personalizate.
Primești specificația unui produs (JSON) și 1-4 poze cu produsul finit.
Verifici, câmp cu câmp, dacă produsul fotografiat corespunde specificației.

## Reguli de onestitate (cele mai importante)

1. RĂSPUNZI EXCLUSIV cu un obiect JSON valid, fără text înainte sau după.
2. NU PRESUPUNE conformitate pentru câmpuri pe care NU LE POȚI VEDEA în poze.
   Dacă pozele sunt din față și specificația cere ceva pe spate — câmpul
   merge în `nevizibil`, NU în `conform`.
3. Onestitatea e prioritară față de completitudine. E mai bine să marchezi
   3 câmpuri ca `nevizibil` decât să spui "conform" fără dovadă.
4. Pentru fiecare câmp, motivul trebuie să fie concret și verificabil
   ("se vede în poza 2 marginea gulerului rotund"), nu vag ("pare ok").
5. Confidence: `scăzut` = doar indicii indirecte; `mediu` = vizibil dar nu
   din unghi optim; `ridicat` = clar vizibil și fără ambiguitate.

## Reguli structurale

6. Fiecare câmp-frunză aplicabil al schemei apare EXACT O DATĂ într-una
   din cele trei liste: `conform`, `neconform`, `nevizibil`.
7. Pentru `branding` activ (cu valori non-null), raportezi toate cele 4
   sub-câmpuri: `branding.pozitie`, `branding.tehnica`, `branding.culori`,
   `branding.dimensiuni_aproximative`.
8. Pentru `branding` marcat "fără branding" (spec are
   `branding.pozitie = "fără branding"`), raportezi DOAR `branding.pozitie`
   (verifici că pozele NU arată niciun logo/print). Celelalte 3 sub-câmpuri
   nu se raportează — nu sunt aplicabile. Apariția neașteptată a unui
   branding = neconform pe `branding.pozitie`.
9. Toate textele răspunsului sunt în limba română.

## Output

\`\`\`json
{
  "conform": [
    { "camp": "<key>", "valoare_asteptata": "<>", "valoare_observata": "<>",
      "incredere": "scăzut|mediu|ridicat", "motiv": "<>" }
  ],
  "neconform": [ /* idem */ ],
  "nevizibil": [
    { "camp": "<key>", "valoare_asteptata": "<>",
      "motiv": "<de ce nu se poate vedea>" }
  ]
}
\`\`\`
```

### API intern `agents/inspector.py`

```python
def build_messages(spec: dict, image_paths: list[str]) -> tuple[str, list[dict]]:
    """Returnează (system_prompt, messages list cu image blocks).
    Citește pozele de pe disc, le encodează base64."""

def parse_report(text: str, schema: dict) -> ValidationReport:
    """Parsează JSON-ul. Validează: fiecare câmp al schemei apare exact o dată,
    incredere e în setul permis, motiv non-empty. Ridică ValueError altfel."""
```

```python
@dataclass
class ValidationItem:
    camp: str
    valoare_asteptata: str
    valoare_observata: str | None      # None pentru nevizibil
    incredere: Literal["scăzut", "mediu", "ridicat"] | None  # None pentru nevizibil
    motiv: str

@dataclass
class ValidationReport:
    conform: list[ValidationItem]
    neconform: list[ValidationItem]
    nevizibil: list[ValidationItem]
```

Dacă LLM-ul ratează un câmp → retry o dată cu hint "ți-a lipsit câmpul X". Failure a doua oară → 500 cu mesaj.

## API contracts + UI flow

### Endpoint-uri FastAPI

| Method | Path | Scop | Returnează |
|---|---|---|---|
| `GET` | `/` | Landing: dropdown tip produs + textarea descriere | HTML complet |
| `POST` | `/sessions` | Creează sesiune (form: `product_type`, `initial_description`) | `HX-Redirect: /sessions/{id}` |
| `GET` | `/sessions/{id}` | Vederea sesiunii | HTML complet |
| `POST` | `/sessions/{id}/answer` | Trimite răspunsurile rundei | HTML **partial** (swap pe `#session-body`) |
| `GET` | `/sessions/{id}/validate` | Form upload imagini | HTML complet |
| `POST` | `/sessions/{id}/validate` | Upload multipart, rulează Inspector | `HX-Redirect: /reports/{id}` |
| `GET` | `/reports/{id}` | Raport pe trei zone | HTML complet |
| `GET` | `/healthz` | Health check | `"ok"` |

### Payload-uri form-data

`POST /sessions`:
```
product_type=tricou
initial_description=O+bluză+cu+logo+pe+piept+stâng%2C+culoare+navy
```

`POST /sessions/{id}/answer` (chei dinamice prefixate `answer.`):
```
answer.material=bumbac+100%25
answer.croiala=slim
answer.branding.tehnica=serigrafie
```

`POST /sessions/{id}/validate`:
```
multipart/form-data:
  image1: <file>
  image2: <file>     (opțional)
  image3: <file>     (opțional)
  image4: <file>     (opțional)
```

### Pagini UI

**Landing (`index.html`):** dropdown produs + textarea + buton "Începe specificare".

**Sesiune Discovery (`session.html`):** două zone — stare checklist (read-only, cu ✓ și ·) și întrebări (formular cu radio buttons unde sunt `variante`, input text altfel). Submit → HTMX swap pe `#session-body`. La `done`, partial-ul afișează CTA "Validează cu poze →".

**Upload (`validate.html`):** 4 file inputs (primul obligatoriu, restul opționale) + buton "Rulează validarea".

**Raport (`report.html`):** trei zone vizuale distincte — Conform / Neconform / Nevizibil, fiecare item cu câmp, valori și motiv.

CSS minim, inline în `base.html`. Fără framework UI.

## Strategia de testare

Filosofie sp_learn: **logica pură 100% acoperită cu pytest, partea I/O (LLM real, browser) verificată cu checklist manual.**

| Layer | Testează | Cu | Dependențe |
|---|---|---|---|
| **Unit** (`tests/unit/`) | `agents/*` pure, `db/repository.py` | pytest + fixtures JSON | Niciuna |
| **Integration** (`tests/integration/`) | `agents/llm_client.py` un happy-path real | pytest + ANTHROPIC_API_KEY | Anthropic API |
| **E2E** (`tests/e2e/`) | Route-uri FastAPI cu LLM stub | FastAPI TestClient | Niciuna |
| **Manual** | UI în browser + LLM real | Checklist README | Browser, API key |

### Structura folderului `tests/`

```
tests/
├── conftest.py                 # fixtures: schema_tricou, mock_llm
├── unit/
│   ├── test_discovery.py
│   ├── test_inspector.py
│   └── test_repository.py
├── integration/
│   └── test_llm_client.py      # @pytest.mark.skipif fără API key
├── e2e/
│   └── test_routes.py
└── fixtures/
    ├── schemas/tricou.json
    ├── llm_responses/          # JSON-uri snapshot
    └── images/                 # gitignored
```

### Checklist manual (va intra în README)

```
După `uvicorn main:app --reload`:

- [ ] / se deschide; dropdown listează "Tricou"
- [ ] Descriere "tricou navy cu logo pe piept" → /sessions/{id} se deschide
- [ ] Stare arată câmpurile pre-completate de LLM
- [ ] Întrebările sunt în română, grupate (max 4)
- [ ] Radio buttons funcționează; submit declanșează rundă nouă
- [ ] După max 5 runde, sesiunea închide oricum
- [ ] "fără branding" se acceptă și completează sub-câmpurile
- [ ] /sessions/{id}/validate primește 1-4 poze
- [ ] /reports/{id} arată cele 3 zone
- [ ] Pentru poză exclusiv din față, câmpurile "spate" merg în "nevizibil"
- [ ] Restart uvicorn → sesiunile vechi sunt încă în DB
```

## MVP — pași la nivel înalt

MVP-ul livrează **fluxul complet end-to-end pentru tricou**. Generalizarea la șapcă/hanorac vine după, doar adăugând fișiere în `schemas/`.

```
Pas 1 — Scaffolding proiect
  └─ folder, .venv, requirements.txt, .gitignore, .env.example, README skeleton,
     .claude/settings.local.json

Pas 2 — Modelul de date
  └─ db/schema.sql, db/repository.py (CRUD pe sessions + reports)
     TDD pe repository cu SQLite in-memory

Pas 3 — Schema loader + tricou.json
  └─ schemas/tricou.json, schemas/loader.py
     TDD pe loader

Pas 4 — LLM client wrapper
  └─ agents/llm_client.py: wrapper subțire peste anthropic SDK
     un integration test smoke (skip fără API key)

Pas 5 — Discovery agent
  └─ prompts/discovery.md
     agents/discovery.py: build_messages, parse_response,
                          is_schema_complete, merge_answers
     TDD complet cu fixtures de răspunsuri LLM

Pas 6 — Inspector agent
  └─ prompts/inspector.md
     agents/inspector.py: build_messages (cu base64), parse_report
                          + validarea "fiecare câmp exact o dată"
     TDD complet cu fixtures

Pas 7 — FastAPI scaffolding + landing
  └─ web/app.py, web/templates/base.html, index.html
     GET / + POST /sessions
     E2E test cu TestClient

Pas 8 — Discovery flow în web
  └─ GET /sessions/{id}, POST /sessions/{id}/answer
     templates: session.html + _session_body.html (partial HTMX)
     E2E test pentru ciclul complet de runde (cu LLM mock)

Pas 9 — Inspector flow în web
  └─ GET /sessions/{id}/validate, POST /sessions/{id}/validate
     GET /reports/{id}
     templates: validate.html, report.html
     E2E test cu pozele de fixture

Pas 10 — Polish + checklist manual
  └─ README cu instalare + checklist manual
     Test end-to-end cu LLM real, 1-2 produse reale
     Commit final, tag MVP
```

**Criteriul de "MVP terminat":** pot crea o sesiune nouă, răspund la întrebări până la `done`, încarc 1-2 poze, primesc un raport pe trei zone. Pe tricou. Cu LLM real. Cu DB persistent între restart-uri.

## Out of scope pentru MVP (explicit)

- Multi-user / autentificare
- Camera browser (doar upload de fișiere)
- Editare manuală a câmpurilor după Discovery (read-only înainte de validare)
- Export PDF/Excel al raportului
- Liste / search / paginare peste sesiuni vechi
- Tipuri de produs noi peste tricou (schema e extensibilă, fișierele vin după)
- Re-rulare validare pe aceeași sesiune cu poze diferite (DB suportă, UI nu)

## Open questions / decizii rezervate pentru implementare

- **Concurența pe SQLite**: aplicația e single-user, scrierile sunt rare; nu ne așteptăm la conflicte. `check_same_thread=False` + un singur writer e suficient. Reevaluăm dacă vreodată devine multi-user.
- **Limita de mărime poze**: 5MB per poză (limită server FastAPI), 20MB total per request. Validăm la upload, mesaj de eroare clar.
- **Expirare sesiuni**: niciuna în MVP. Add `--cleanup-older-than-days` la nevoie.
