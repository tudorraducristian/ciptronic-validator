# Ciptronic Product Validator

Aplicație web locală pentru specificarea și validarea vizuală a produselor personalizate. Două fluxuri paralele:

1. **Discovery + Inspector** (flux text) — descriere vagă a clientului → JSON structurat, prin întrebări țintite (max 5 runde). Apoi: JSON + 1-4 poze ale produsului finit → raport pe trei zone (conform / neconform / nevizibil).
2. **Image Match** (flux imagine) — mockup / artwork → criterii vizuale extrase automat. Apoi: criterii + poză produs real → raport tabelar cu match-uri și discrepanțe, criteriu cu criteriu.

Stack: Python 3.10+, FastAPI, HTMX, Jinja2, SQLite, Anthropic Claude Sonnet 4.6. Rulează local, single-user.

## Setup

Cerințe: Python 3.10+. Cont Anthropic cu cheie de API.

```bash
python -m venv .venv
.venv\Scripts\activate         # Windows PowerShell sau cmd
# source .venv/bin/activate    # macOS/Linux
pip install -r requirements.txt
cp .env.example .env
# editează .env și pune ANTHROPIC_API_KEY
```

## Run

```bash
.venv\Scripts\uvicorn.exe main:app --reload
```

Deschide http://localhost:8000. Landing-ul îți cere să alegi între flux text și flux imagine.

Image_matcher Streamlit (dev tool standalone, rămâne separat):

```bash
.venv\Scripts\streamlit.exe run image_matcher/app.py
```

## Test

```bash
.venv\Scripts\pytest.exe tests/
```

Pentru testele de integrare cu API real:

```bash
$env:ANTHROPIC_API_KEY = "sk-ant-..."
.venv\Scripts\pytest.exe tests/integration -v
```

## Structura proiectului

```
agents/             logica pură Flow A + wrapper LLM
prompts/            prompturile sistem (versionate)
schemas/            scheme JSON pe tipuri de produs (extensibil)
db/                 schema SQL (3 tabele) + repository functions
web/                FastAPI + templates Jinja + static CSS
image_matcher/      Image Match engine + Streamlit UI (sub-proiect intact)
tests/              unit / integration / e2e + fixtures
docs/               specs, plans, mockups
main.py             entry point uvicorn
```

## Adaugă un tip de produs nou (Flow A)

1. Creează `schemas/<nume>.json` cu același format ca `tricou.json`.
2. Restart server.
3. Noul produs apare automat în dropdown-ul de pe `/sessions/new`.

Nu modifici cod. Flow B (Image Match) e agnostic la tip produs, nu e afectat.

## Manual smoke test checklist

După `uvicorn main:app --reload`, deschide http://localhost:8000.

### Flow A (descriere)

- [ ] Landing arată două cards: „Am o descriere" și „Am un mockup"
- [ ] Click „Am o descriere" → `/sessions/new` se deschide cu dropdown + textarea
- [ ] Submit cu descriere `tricou navy cu logo pe piept stâng` → redirect la `/sessions/{id}`
- [ ] Stare specificație arată câmpurile pre-completate (culoare, mâneci, branding.poziție)
- [ ] Întrebări în română, max 4 per rundă
- [ ] Submit la întrebări declanșează HTMX swap, rundă nouă apare
- [ ] La done=true, butonul „Validează cu poze" apare
- [ ] La 5 runde fără completare, sesiunea se închide forțat
- [ ] „fără branding" la prima rundă completează branding și sare peste sub-câmpuri
- [ ] Upload 1-4 poze acceptat (JPG/PNG/WEBP, max 5MB)
- [ ] Raport afișează 3 zone (Conform / Neconform / Nevizibil)
- [ ] Pentru poză exclusiv din față, câmpuri spate în „Nevizibil"
- [ ] Restart uvicorn → sesiunile vechi în DB (`ciptronic.db`)

### Flow B (mockup)

- [ ] Click „Am un mockup" → `/matches/new` se deschide
- [ ] Upload mockup (ex. `image_matcher/input/Tricou_05_sim.png`) → spinner ~10s → redirect la `/matches/{id}`
- [ ] Criteriile extrase afișate în listă numerotată
- [ ] Upload poză produs real → spinner ~15s → redirect la `/matches/{id}/report`
- [ ] Raport: chips summary (Total / Match / Mismatch) + tabel rows
- [ ] Fiecare rând afișează: criteriu, sim_value, real_value, match icon (✓/✗/+), match_type (exact/partial/extra/missing)
- [ ] Restart uvicorn → match-urile vechi în DB

### Ambele

- [ ] `/healthz` returnează `ok`
- [ ] Ctrl+C: server stop curat

## Spec & plan

- [Implementation plan](docs/superpowers/plans/2026-05-27-ciptronic-validator-unified.md)
- [Image Match engine plan](docs/superpowers/plans/2026-05-18-image-match-engine.md) (sub-proiect ✓ done)
- [Original Discovery + Inspector spec](docs/superpowers/specs/2026-05-17-ciptronic-validator-design.md)
- [Mockups](docs/mockups/_index.html)
