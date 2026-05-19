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
