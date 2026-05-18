# Image Match Engine — Design

**Date:** 2026-05-18
**Author:** brainstorming session, Claude Code + user
**Status:** Approved (ready for implementation plan)

## Goal

Un motor stand-alone (CLI, neintegrat încă în UI) care compară perechi imagine-mockup vs. imagine-real-fotografie și produce un tabel de potrivire pe criterii. Lucrează în batch peste un folder de input.

Pentru fiecare pereche `<base>_sim.<ext>` + `<base>_real.<ext>`:

1. **Apel LLM 1 (sim → JSON):** Claude Sonnet 4.6 vision analizează mockup-ul și produce o listă liberă, detaliată, de criterii vizuale (`sim.json`).
2. **Apel LLM 2 (real + sim-JSON → tabel):** modelul primește poza reală împreună cu `sim.json` și completează un tabel de comparație rând cu rând, inclusiv rânduri pentru criterii prezente doar pe o parte.
3. **Output:** tabel ASCII printat în terminal + `compare.json` salvat pe disc.

Design-ul prioritizează: (a) script scurt și ușor de debug-uit, (b) funcții pure separate de I/O, (c) integrare ulterioară fără rescriere — import direct din viitorul UI.

Acest motor este **independent** de Discovery / Inspector agent-ul descris în `2026-05-17-ciptronic-validator-design.md`. Nu modifică și nu depinde de codul de acolo. Trăiește în paralel.

## Stack

- **Python 3.10+** (existent în `.venv`)
- **Anthropic SDK** (`anthropic`), model `claude-sonnet-4-6` (vision)
- **pytest** pentru teste pe funcțiile pure
- Fără dependențe noi peste asta. Tabelul ASCII se desenează cu f-string + `str.ljust`, fără `rich` sau `tabulate`.

## Architecture

### Structura de fișiere (noi, nu modifică nimic existent)

```
ciptronic_validator/
├── match_engine.py       # motor: funcții pure + un singur apel I/O (call_llm)
├── run_match.py          # CLI subțire: scanează folder, iterează perechi, printează
├── input/                # user-managed; conține perechile *_sim.* + *_real.*
├── output/               # generat; gitignored
│   └── <base>/
│       ├── sim.json
│       └── compare.json
└── tests/
    ├── test_match_engine.py
    └── fixtures/
        ├── valid_sim_response.json
        ├── invalid_sim_missing_id.json
        ├── valid_compare_response.json
        └── invalid_compare_count.json
```

### Frontiere între module

Toată logica trăiește în `match_engine.py`. O singură funcție este impură (`call_llm`). Restul sunt funcții pure care pot fi testate fără să atingem API-ul Anthropic.

| Funcție | Pură? | Rol |
|---|---|---|
| `find_pairs(folder)` | Da | Scanează folderul, returnează `[(base, sim_path, real_path), ...]`, avertizează pe orphans |
| `encode_image(path)` | Da | Returnează `(media_type, base64_data)` |
| `build_sim_messages(image_b64, media_type)` | Da | Compune mesajul pt apelul 1 |
| `parse_sim_response(text)` | Da | Validează JSON, ridică `ValueError` pe format invalid |
| `build_compare_messages(sim_report, image_b64, media_type)` | Da | Compune mesajul pt apelul 2 |
| `parse_compare_response(text)` | Da | Validează rânduri + summary recount |
| `render_table(report, width)` | Da | Tabel ASCII cu 4 coloane |
| `call_llm(system, messages, model)` | **Nu** | Wrapper subțire peste Anthropic SDK |
| `analyze_sim(sim_path)` | Nu | encode → build → call_llm → parse |
| `compare_real(sim_report, real_path)` | Nu | idem pt apelul 2 |
| `process_pair(base, sim, real, out_dir)` | Nu | pipeline complet pe o pereche |

`run_match.py` rămâne sub 50 linii: parsare argumente, apel `find_pairs`, loop peste perechi cu `process_pair`, print.

## Modelul de date

### `sim.json` — output al apelului 1

Listă liberă de criterii vizuale identificate în mockup, plus un bloc `overall` care descrie imaginea holistic.

```json
{
  "source_image": "tshirt_01_sim.png",
  "overall": {
    "product_type_guess": "t-shirt",
    "view_angle": "front",
    "dominant_colors": ["navy blue", "white"],
    "background": "transparent / white mockup background",
    "description": "Navy blue crew-neck t-shirt with white circular chest logo and back text 'TEAM 2026'."
  },
  "criteria": [
    {
      "id": "main_color",
      "label": "main color",
      "value": "navy blue",
      "location": "entire shirt body",
      "details": {
        "color_name": "navy blue",
        "color_hex_approx": "#1B2A4E",
        "uniformity": "solid, no gradient",
        "coverage_pct": 95
      }
    },
    {
      "id": "chest_logo",
      "label": "chest logo",
      "value": "white circular logo with text 'CIP'",
      "location": "left chest",
      "details": {
        "shape": "circular",
        "primary_color": "white",
        "color_hex_approx": "#FFFFFF",
        "text_content": "CIP",
        "font_style": "bold sans-serif",
        "size_estimate_cm": "approx 10cm diameter",
        "position_normalized": { "x_pct": 25, "y_pct": 30 },
        "technique_hint": "screen print",
        "border": "none"
      }
    }
  ]
}
```

**Reguli validate de `parse_sim_response`:**
- `criteria` e listă non-vidă.
- Fiecare `id` e unic, snake_case, match pe `^[a-z0-9_]+$`.
- `label`, `value`, `location` sunt string-uri non-vide.
- `details` e dict (poate fi vid, conținut liber).
- `overall` e dict non-vid cu cel puțin `description`.

### `compare.json` — output al apelului 2

```json
{
  "pair": "tshirt_01",
  "sim_image": "tshirt_01_sim.png",
  "real_image": "tshirt_01_real.jpg",
  "real_overall": {
    "view_angle": "front",
    "lighting": "natural daylight, slight shadow on left",
    "image_quality": "sharp, in focus",
    "obstructions": []
  },
  "rows": [
    {
      "criterion": "main color",
      "sim_value": "navy blue",
      "real_value": "navy blue, slightly darker due to lighting",
      "sim_details": { "color_hex_approx": "#1B2A4E", "uniformity": "solid" },
      "real_details": { "color_hex_approx": "#15233F", "uniformity": "solid" },
      "match": true,
      "match_type": "semantic",
      "confidence": "high",
      "differences": ["hex slightly darker on real (shadow)"],
      "note": "color matches semantically; minor hex variation due to lighting"
    },
    {
      "criterion": "back text",
      "sim_value": "\"TEAM 2026\" in white block letters",
      "real_value": null,
      "sim_details": { "text_content": "TEAM 2026", "font_style": "block letters" },
      "real_details": null,
      "match": false,
      "match_type": "missing_in_real",
      "confidence": "low",
      "differences": ["back not visible in real photo"],
      "note": "cannot verify — real photo shows only front view"
    },
    {
      "criterion": "stitch line on shoulder",
      "sim_value": null,
      "real_value": "visible double-stitch at shoulder seam",
      "sim_details": null,
      "real_details": { "stitch_type": "double", "color": "navy" },
      "match": false,
      "match_type": "extra_on_real",
      "confidence": "high",
      "differences": ["detail present only on real product"],
      "note": "construction detail not depicted in mockup"
    }
  ],
  "summary": {
    "total": 3,
    "matched": 1,
    "mismatched": 2,
    "by_match_type": {
      "exact": 0, "semantic": 1, "partial": 0,
      "missing_in_real": 1, "extra_on_real": 1
    },
    "by_confidence": { "high": 2, "medium": 0, "low": 1 }
  }
}
```

**Reguli validate de `parse_compare_response`:**
- `rows` e listă non-vidă.
- `match_type ∈ {exact, semantic, partial, missing_in_real, extra_on_real}`.
- `confidence ∈ {high, medium, low}`.
- `match: true` ⇒ `sim_value` și `real_value` ambele non-null.
- `match_type == "missing_in_real"` ⇒ `real_value == null`.
- `match_type == "extra_on_real"` ⇒ `sim_value == null`.
- `note` e string non-empty.
- `summary.total == len(rows)`.
- `summary.matched + summary.mismatched == summary.total`.
- `by_match_type` și `by_confidence` recount-uite de cod, comparate cu cele din răspuns.

### Tabelul ASCII (terminal)

```
┌──────────────────────┬──────────────────────────┬──────────────────────────┬───────┐
│ Criterion            │ Sim                      │ Real                     │ Match │
├──────────────────────┼──────────────────────────┼──────────────────────────┼───────┤
│ main color           │ navy blue                │ navy blue, slightly d…   │   ✓   │
│ back text            │ "TEAM 2026" in white b…  │ —                        │   ✗   │
│ stitch on shoulder   │ —                        │ visible double-stitch…   │   ✗   │
└──────────────────────┴──────────────────────────┴──────────────────────────┴───────┘
```

Valori lungi trunchiate cu `…` la limita coloanei (default 80 chars total). `null` → `—`.

## Prompts (inline în `match_engine.py`)

### `SIM_PROMPT`

```
You are a meticulous visual inspector analyzing a 2D product mockup image.

Your job: identify every distinguishable element of the product and return a
detailed structured JSON. The mockup is a clean 2D design (Figma / Illustrator /
Photoshop output) — colors are flat, edges are clean, no photographic noise.

## Strict rules

1. Respond with a SINGLE valid JSON object, no prose before or after.
2. All field values in English.
3. NEVER invent: if you cannot see something clearly, omit it. Do not write
   "unknown" or guess.
4. Each criterion `id` must be unique, snake_case, ASCII (e.g. "chest_logo").
5. `value` must be concrete and visually verifiable. Avoid vague terms.
6. `location` describes where on the product the element is.
7. `details` is a free-form dict — add any sub-fields that are visually evident.
   Suggested categories per element type:
   - Color: color_name, color_hex_approx, uniformity, coverage_pct
   - Logo/graphic: shape, primary_color, secondary_colors, size_estimate_cm,
     position_normalized ({x_pct, y_pct}), technique_hint, border
   - Text: text_content, font_style, text_color, text_size_estimate
   - Garment construction: length, shape, ribbing, cuff, seam_type
8. List EVERY visible criterion, not just the obvious ones.
9. The `overall` block describes the image holistically.

## Output schema

{
  "source_image": "<filename>",
  "overall": { "product_type_guess": "...", "view_angle": "...",
               "dominant_colors": [...], "background": "...",
               "description": "<one sentence>" },
  "criteria": [
    { "id": "snake_case_id", "label": "...", "value": "...",
      "location": "...", "details": { /* free-form */ } }
  ]
}
```

### `COMPARE_PROMPT`

```
You are a meticulous visual inspector comparing a real product photo against
a previously-analyzed 2D mockup.

You receive: a JSON report from the mockup (sim_report) and a photo of the
real product.

For EACH criterion in sim_report: find it in the real photo, decide match.
Additionally: identify criteria visible on the real product that were NOT in
sim_report (extras).

## Strict rules

1. Respond with a SINGLE valid JSON object, no prose.
2. All field values in English.
3. One row per sim criterion (in order), then rows for extras.
4. match: true ONLY when both values non-null AND semantically equivalent.
5. match_type ∈ {exact, semantic, partial, missing_in_real, extra_on_real}.
6. confidence ∈ {high, medium, low}.
7. NEVER claim match: true for something you cannot see in the real photo.
   Not visible → real_value: null, match: false, match_type: missing_in_real,
   confidence: low, explain in note.
8. note is mandatory — one sentence justifying the decision.
9. differences lists specific visual discrepancies, empty when exact.
10. real_details mirrors structure of sim_details where possible.
11. summary.total == len(rows). matched + mismatched == total.
12. real_overall describes the photo itself (angle, lighting, quality, obstructions).
```

Schema completă de output e descrisă în prompt (vezi `parse_compare_response` pentru validări).

## Eroare-handling

- Toate `parse_*` ridică `ValueError` cu mesaj concret citând câmpul lipsă/invalid.
- `call_llm` are **un singur retry** pe rate-limit / 5xx. Pe orice altă eroare, re-raise cu context (`f"sim analysis failed for {path}: {e}"`).
- Dacă `parse_compare_response` eșuează, `compare_real` retry-uiește **o singură dată** cu un hint adăugat la mesaj (`"Your previous response had: {error}. Please correct and return valid JSON."`). A doua eșuare → raise.
- În `run_match.py`, o pereche care eșuează e logată și skipped; batch-ul continuă pe restul.

## Strategia de testare

| Layer | Testează | Cu | Dependențe |
|---|---|---|---|
| **Unit** | `find_pairs`, `encode_image`, `build_*_messages`, `parse_*_response`, `render_table` | pytest + fixtures JSON | Niciuna |
| **Manual** | Apelul LLM real, terminalul, batch-ul | Checklist README | Doar API key |

### Test cases

- `find_pairs`: basic, orphan warning, mixed extensions (.png/.jpg/.jpeg/.webp pe ambele părți)
- `encode_image`: returnează media_type corect pentru .png vs .jpg, ridică pe fișier inexistent
- `build_sim_messages`: structură mesaj corectă, image block prezent, prompt-ul e SIM_PROMPT
- `build_compare_messages`: image block + text block cu sim_report JSON embed
- `parse_sim_response`: valid, invalid JSON, missing field, duplicate ids, invalid id format, empty criteria
- `parse_compare_response`: valid, summary mismatch, invalid match_type, `match: true` cu null, missing_in_real cu real_value non-null
- `render_table`: basic, long values, null values, tabel gol

Fixtures sunt mici (3-4 criterii fiecare), nu snapshot-uri gigantice.

### Checklist manual (în README)

```
După setarea ANTHROPIC_API_KEY:
- [ ] pytest tests/ → toate trec, sub 2s
- [ ] input/tshirt_01_sim.png + input/tshirt_01_real.jpg
- [ ] python run_match.py → tabel ASCII cu coloane aliniate
- [ ] output/tshirt_01/sim.json: >= 4 criterii cu `details` non-vide
- [ ] output/tshirt_01/compare.json: summary.total == len(rows)
- [ ] Detaliu absent în real → missing_in_real + confidence: low
- [ ] Detaliu extra pe real → extra_on_real
- [ ] A doua pereche → batch [1/2], [2/2]
- [ ] Pereche orphan → warning + skip, restul continuă
```

## CLI

```bash
python run_match.py [--folder input/] [--output output/] [--model claude-sonnet-4-6]
```

Default: `--folder input/`, `--output output/`. Toate sunt opționale.

## Out of scope pentru MVP

- Paralelizare pe perechi (design-ul permite, dar foreach serial e suficient)
- Cache `sim.json` (mockup-ul nu se reanalizează dacă n-a fost schimbat)
- Comparație 1:N (un sim, mai multe reale)
- Export markdown/CSV/HTML al tabelului
- Resize automat al imaginilor peste limita Anthropic
- Auto-fallback între modele Claude
- Integrare UI

## Open questions / decisions

- **Limită mărime imagine:** Anthropic acceptă max ~5MB / 8000px. `encode_image` verifică și ridică `ValueError` cu mesaj clar dacă depășește. Resize manual înainte de rulare.
- **Model fallback:** dacă Sonnet 4.6 dă rate-limit insistent, flag `--model claude-opus-4-7`. Manual, nu automat.
- **Output format:** doar JSON. Tabelul ASCII e prezent doar în stdout, nu salvat.
- **Re-rulare:** ștergi `output/<base>/` ca să forțezi refresh. Nu detectează automat schimbarea de input.
