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
