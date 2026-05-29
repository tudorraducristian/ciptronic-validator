# Ciptronic Product Validator

Aplicație web locală pentru specificarea și validarea vizuală a produselor personalizate.

Două fluxuri paralele:
1. **Discovery + Inspector** (text) — descriere → JSON → raport pe 3 zone.
2. **Image Match** (imagine) — mockup → criterii → raport tabelar.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# editează .env
```

## Run

```bash
.venv\Scripts\uvicorn.exe main:app --reload
```

Open http://localhost:8000.

## Spec & plan

- [Implementation plan](docs/superpowers/plans/2026-05-27-ciptronic-validator-unified.md)
- [Mockups](docs/mockups/_index.html)
