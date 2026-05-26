# image_matcher

Standalone CLI for comparing 2D product mockups against real product photos
using Claude Sonnet 4.6 vision. Lives as a self-contained Python package at
the project root.

## Setup

From the project root:

1. Activate venv: `.venv\Scripts\Activate.ps1`
2. Copy env template: `Copy-Item image_matcher\.env.example image_matcher\.env`
3. Edit `image_matcher\.env` and put your real key after `ANTHROPIC_API_KEY=`.
4. Export it into the session:
   `$env:ANTHROPIC_API_KEY = ((Get-Content image_matcher\.env) -match '^ANTHROPIC_API_KEY=' -replace 'ANTHROPIC_API_KEY=','')`
5. Place pairs in `image_matcher/input/` named `<base>_sim.<ext>` and `<base>_real.<ext>`.

## Run

From project root:

```
python -m image_matcher.run
```

Outputs go to `image_matcher/output/<base>/sim.json` and
`image_matcher/output/<base>/compare.json`. ASCII table prints to terminal.

## Run UI

From project root, with `ANTHROPIC_API_KEY` set:

```
streamlit run image_matcher/app.py
```

The browser opens at `http://localhost:8501`. Type a pair name (letters,
digits and `_` only), upload the mockup in the left slot ("Imagine sim") and
the real photo in the right slot ("Imagine real"), then click "Analizează".
After ~30-60s the result table appears with three metrics (Total / Matched /
Mismatched) and one row per criterion. Uploaded files are written to
`image_matcher/input/<name>_sim.<ext>` / `<name>_real.<ext>` and the
comparison report to `image_matcher/output/<name>/compare.json`.

The CLI workflow (`python -m image_matcher.run`) keeps working unchanged.

## Tests

From project root:

```
python -m pytest image_matcher/tests/ -v
```

## Manual verification checklist

After setting `ANTHROPIC_API_KEY` in the environment:

- [ ] `python -m pytest image_matcher/tests/ -v` → all pass, sub 2s
- [ ] Place `image_matcher/input/tshirt_01_sim.png` + `image_matcher/input/tshirt_01_real.jpg`
- [ ] `python -m image_matcher.run` → ASCII table printed with aligned columns
- [ ] `image_matcher/output/tshirt_01/sim.json` exists, has ≥ 4 criteria with non-empty `details`
- [ ] `image_matcher/output/tshirt_01/compare.json` exists, `summary.total == len(rows)`
- [ ] An element absent in real (e.g. back text) → row marked `missing_in_real`, `confidence: low`
- [ ] An element extra on real (e.g. visible stitch detail) → row marked `extra_on_real`
- [ ] Add a second pair `tshirt_02_*` → batch runs both, prints `[1/2]` and `[2/2]`
- [ ] An orphan pair (one side missing) → warning logged, pair skipped, batch continues
