# Image Match Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone CLI engine that compares mockup-vs-real product image pairs using Claude Sonnet 4.6 vision, producing a per-criterion match table per pair.

**Architecture:** Self-contained Python package at `image_matcher/` (sibling of future Ciptronic Validator code). `engine.py` holds pure functions (find_pairs, encode_image, build/parse messages, render_table) plus a single I/O function (`call_llm`) plus thin orchestrators (analyze_sim, compare_real, process_pair). `run.py` is a thin CLI with `from .engine import …` (relative imports), invoked as `python -m image_matcher.run`. Pure functions are unit-tested with pytest; the LLM path is verified manually.

**Tech Stack:** Python 3.10+, anthropic SDK (claude-sonnet-4-6), pytest. No new dependencies. `requirements.txt` lives at project root (shared with future Ciptronic Validator code), `.venv/` is shared.

**Spec:** [`docs/superpowers/specs/2026-05-18-image-match-engine-design.md`](../specs/2026-05-18-image-match-engine-design.md)

**Working directory:** `C:\Users\40747\OneDrive\Documents\Jetson Nano\ciptronic_validator` (project root for all commands).

**Python interpreter for commands:** `.venv\Scripts\python.exe` (already created; `anthropic==0.102.0` and `pytest==9.0.3` already installed).

**Invocation convention:** All commands run from project root. The CLI uses `python -m image_matcher.run` (NOT `python image_matcher/run.py` — the `-m` form is required for relative imports inside the package).

---

## Task 1: Scaffolding

Create scaffolding files for the package + the root-level shared files. No application code yet.

**Files:**
- Create: `requirements.txt` (root)
- Create: `.gitignore` (root)
- Create: `image_matcher/__init__.py`
- Create: `image_matcher/engine.py` (module docstring only)
- Create: `image_matcher/run.py` (module docstring only)
- Create: `image_matcher/.env.example`
- Create: `image_matcher/README.md`
- Create: `image_matcher/input/.gitkeep` (empty)
- Create: `image_matcher/tests/test_engine.py` (empty, will be filled in next tasks)
- Create: `image_matcher/tests/fixtures/.gitkeep` (empty)

Note: no `image_matcher/tests/__init__.py`. Pytest discovers tests by path; making `tests/` a sub-package causes `from image_matcher.engine import …` to resolve confusingly.

- [ ] **Step 1: Create `requirements.txt` at project root**

```
anthropic>=0.102.0
pytest>=9.0.0
```

- [ ] **Step 2: Create `.gitignore` at project root**

```
.venv/
__pycache__/
*.pyc
.pytest_cache/

# image_matcher local artifacts
image_matcher/.env
image_matcher/input/*
!image_matcher/input/.gitkeep
image_matcher/output/
```

- [ ] **Step 3: Create `image_matcher/__init__.py`**

```python
"""Image match engine package.

Compares 2D product mockups against real product photos via Claude vision.
Public API: see `image_matcher.engine` for orchestrators
(`analyze_sim`, `compare_real`, `process_pair`).
"""
```

- [ ] **Step 4: Create `image_matcher/engine.py` with placeholder content**

```python
"""Image match engine: pure functions + a single I/O wrapper.

Pure functions (find_pairs, encode_image, build_*_messages, parse_*_response,
render_table) are unit-tested in `tests/test_engine.py`. The single I/O
function (`call_llm`) and the orchestrators (analyze_sim, compare_real,
process_pair) are verified manually with the checklist in README.md.
"""
```

- [ ] **Step 5: Create `image_matcher/run.py` with placeholder content**

```python
"""Thin CLI wrapper around `image_matcher.engine`.

Invoke from project root with: `python -m image_matcher.run`.
See `image_matcher/README.md` for usage.
"""
```

- [ ] **Step 6: Create `image_matcher/.env.example`**

```
ANTHROPIC_API_KEY=sk-ant-...
```

- [ ] **Step 7: Create `image_matcher/README.md`**

```markdown
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
```

- [ ] **Step 8: Create empty files**

Create these files with empty content:
- `image_matcher/input/.gitkeep`
- `image_matcher/tests/test_engine.py`
- `image_matcher/tests/fixtures/.gitkeep`

- [ ] **Step 9: Verify imports work**

Run: `.venv\Scripts\python.exe -c "import image_matcher; import image_matcher.engine; import image_matcher.run; print('ok')"`
Expected: `ok` (the placeholders are importable).

- [ ] **Step 10: Verify pytest discovers nothing**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/ -v`
Expected: `no tests ran` (file is empty).

- [ ] **Step 11: Commit**

```bash
git add requirements.txt .gitignore image_matcher/
git commit -m "feat(image_matcher): add package scaffolding"
```

---

## Task 2: `find_pairs` (TDD)

Implement folder scanning that returns sorted `(base, sim_path, real_path)` tuples.

**Files:**
- Modify: `image_matcher/engine.py`
- Modify: `image_matcher/tests/test_engine.py`

- [ ] **Step 1: Write the failing tests**

Write `image_matcher/tests/test_engine.py` (replaces empty content):

```python
"""Unit tests for image_matcher.engine pure functions."""
import logging
from pathlib import Path

import pytest

from image_matcher.engine import find_pairs


def _touch(path: Path) -> None:
    path.write_bytes(b"")


def test_find_pairs_basic(tmp_path):
    _touch(tmp_path / "tshirt_01_sim.png")
    _touch(tmp_path / "tshirt_01_real.jpg")
    _touch(tmp_path / "tshirt_02_sim.png")
    _touch(tmp_path / "tshirt_02_real.jpg")

    pairs = find_pairs(tmp_path)

    assert len(pairs) == 2
    bases = [base for base, _, _ in pairs]
    assert bases == ["tshirt_01", "tshirt_02"]
    assert pairs[0][1].name == "tshirt_01_sim.png"
    assert pairs[0][2].name == "tshirt_01_real.jpg"


def test_find_pairs_orphan_logs_warning(tmp_path, caplog):
    _touch(tmp_path / "tshirt_01_sim.png")
    _touch(tmp_path / "tshirt_02_real.jpg")

    with caplog.at_level(logging.WARNING):
        pairs = find_pairs(tmp_path)

    assert pairs == []
    log_text = caplog.text
    assert "tshirt_01" in log_text
    assert "tshirt_02" in log_text


def test_find_pairs_mixed_extensions(tmp_path):
    _touch(tmp_path / "a_sim.png")
    _touch(tmp_path / "a_real.jpg")
    _touch(tmp_path / "b_sim.webp")
    _touch(tmp_path / "b_real.jpeg")

    pairs = find_pairs(tmp_path)

    assert len(pairs) == 2
    assert pairs[0][0] == "a"
    assert pairs[1][0] == "b"


def test_find_pairs_empty_folder(tmp_path):
    assert find_pairs(tmp_path) == []


def test_find_pairs_ignores_unrelated_files(tmp_path):
    _touch(tmp_path / "a_sim.png")
    _touch(tmp_path / "a_real.jpg")
    _touch(tmp_path / "notes.txt")
    _touch(tmp_path / "random.png")

    pairs = find_pairs(tmp_path)

    assert len(pairs) == 1
    assert pairs[0][0] == "a"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: ImportError or "cannot import name 'find_pairs' from image_matcher.engine".

- [ ] **Step 3: Implement `find_pairs` in `image_matcher/engine.py`**

Add after the module docstring:

```python
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def find_pairs(folder: Path) -> list[tuple[str, Path, Path]]:
    """Scan folder for `<base>_sim.<ext>` + `<base>_real.<ext>` pairs.

    Returns a sorted list of (base, sim_path, real_path) tuples.
    Logs a warning for each base that has only one side (orphan) and
    excludes it from the result.
    """
    sims: dict[str, Path] = {}
    reals: dict[str, Path] = {}

    for entry in folder.iterdir():
        if not entry.is_file() or entry.suffix.lower() not in _IMAGE_EXTS:
            continue
        stem = entry.stem
        if stem.endswith("_sim"):
            sims[stem[:-4]] = entry
        elif stem.endswith("_real"):
            reals[stem[:-5]] = entry

    bases = sorted(set(sims) | set(reals))
    pairs: list[tuple[str, Path, Path]] = []
    for base in bases:
        sim = sims.get(base)
        real = reals.get(base)
        if sim is None or real is None:
            missing = "sim" if sim is None else "real"
            logger.warning("orphan pair: %s is missing the %s side", base, missing)
            continue
        pairs.append((base, sim, real))
    return pairs
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add image_matcher/engine.py image_matcher/tests/test_engine.py
git commit -m "feat(image_matcher): add find_pairs with orphan warning"
```

---

## Task 3: `encode_image` (TDD)

Read a file from disk, base64-encode it, and return `(media_type, b64_data)`. Enforce Anthropic's ~5MB limit.

**Files:**
- Modify: `image_matcher/engine.py`
- Modify: `image_matcher/tests/test_engine.py`

- [ ] **Step 1: Append failing tests**

Append to `image_matcher/tests/test_engine.py`:

```python
from image_matcher.engine import encode_image


def test_encode_image_png(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nfakecontent")

    media_type, data = encode_image(path)

    assert media_type == "image/png"
    assert isinstance(data, str)
    assert len(data) > 0


def test_encode_image_jpeg(tmp_path):
    path = tmp_path / "a.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0fakecontent")

    media_type, _ = encode_image(path)

    assert media_type == "image/jpeg"


def test_encode_image_jpeg_alt_extension(tmp_path):
    path = tmp_path / "a.jpeg"
    path.write_bytes(b"\xff\xd8\xff\xe0fakecontent")

    media_type, _ = encode_image(path)

    assert media_type == "image/jpeg"


def test_encode_image_webp(tmp_path):
    path = tmp_path / "a.webp"
    path.write_bytes(b"RIFF\x00\x00\x00\x00WEBPfake")

    media_type, _ = encode_image(path)

    assert media_type == "image/webp"


def test_encode_image_unsupported_extension(tmp_path):
    path = tmp_path / "a.gif"
    path.write_bytes(b"fake")

    with pytest.raises(ValueError, match="unsupported image extension"):
        encode_image(path)


def test_encode_image_too_large(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"\x00" * (5 * 1024 * 1024 + 1))

    with pytest.raises(ValueError, match="exceeds 5MB"):
        encode_image(path)


def test_encode_image_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        encode_image(tmp_path / "nope.png")
```

- [ ] **Step 2: Run tests to verify the new ones fail**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: ImportError on `encode_image`.

- [ ] **Step 3: Implement `encode_image`**

Add to `image_matcher/engine.py` (below `find_pairs`):

```python
import base64

_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


def encode_image(path: Path) -> tuple[str, str]:
    """Read an image file, return (media_type, base64_data).

    Raises ValueError on unsupported extension or files > 5MB.
    Raises FileNotFoundError if path does not exist.
    """
    ext = path.suffix.lower()
    media_type = _MEDIA_TYPES.get(ext)
    if media_type is None:
        raise ValueError(f"unsupported image extension: {ext!r}")
    data_bytes = path.read_bytes()
    if len(data_bytes) > _MAX_IMAGE_BYTES:
        raise ValueError(
            f"{path.name} ({len(data_bytes)} bytes) exceeds 5MB limit"
        )
    return media_type, base64.b64encode(data_bytes).decode("ascii")
```

Add `import base64` near the top (keep imports grouped).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: all tests pass (12 total now).

- [ ] **Step 5: Commit**

```bash
git add image_matcher/engine.py image_matcher/tests/test_engine.py
git commit -m "feat(image_matcher): add encode_image with size + extension checks"
```

---

## Task 4: `SIM_PROMPT` constant + `build_sim_messages` (TDD)

Add the system prompt for the sim analysis call and a function that composes the Anthropic messages payload.

**Files:**
- Modify: `image_matcher/engine.py`
- Modify: `image_matcher/tests/test_engine.py`

- [ ] **Step 1: Append failing tests**

```python
from image_matcher.engine import SIM_PROMPT, build_sim_messages


def test_sim_prompt_exists():
    assert isinstance(SIM_PROMPT, str)
    assert "JSON" in SIM_PROMPT
    assert "criteria" in SIM_PROMPT


def test_build_sim_messages_structure():
    system, messages = build_sim_messages("BASE64DATA", "image/png", "tshirt_01_sim.png")

    assert system == SIM_PROMPT
    assert isinstance(messages, list)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"

    content = messages[0]["content"]
    image_blocks = [b for b in content if b["type"] == "image"]
    text_blocks = [b for b in content if b["type"] == "text"]

    assert len(image_blocks) == 1
    assert image_blocks[0]["source"]["type"] == "base64"
    assert image_blocks[0]["source"]["media_type"] == "image/png"
    assert image_blocks[0]["source"]["data"] == "BASE64DATA"

    assert len(text_blocks) == 1
    assert "tshirt_01_sim.png" in text_blocks[0]["text"]
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: ImportError on `SIM_PROMPT` / `build_sim_messages`.

- [ ] **Step 3: Add `SIM_PROMPT` and `build_sim_messages` to `image_matcher/engine.py`**

```python
SIM_PROMPT = """You are a meticulous visual inspector analyzing a 2D product mockup image.

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

The filename of the image is provided in the user text block — copy it verbatim
into the `source_image` field.
"""


def build_sim_messages(
    image_b64: str, media_type: str, filename: str
) -> tuple[str, list[dict]]:
    """Return (system_prompt, messages) for the sim-analysis LLM call."""
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": (
                        f"Analyze this mockup. The source filename is "
                        f"{filename!r}. Return the JSON described in the system "
                        f"prompt."
                    ),
                },
            ],
        }
    ]
    return SIM_PROMPT, messages
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add image_matcher/engine.py image_matcher/tests/test_engine.py
git commit -m "feat(image_matcher): add SIM_PROMPT and build_sim_messages"
```

---

## Task 5: `parse_sim_response` (TDD)

Parse and validate the JSON returned by the sim-analysis LLM call.

**Files:**
- Modify: `image_matcher/engine.py`
- Modify: `image_matcher/tests/test_engine.py`

- [ ] **Step 1: Append failing tests**

```python
import json
from image_matcher.engine import parse_sim_response


def _valid_sim_dict():
    return {
        "source_image": "x.png",
        "overall": {"description": "a t-shirt"},
        "criteria": [
            {
                "id": "main_color",
                "label": "main color",
                "value": "navy blue",
                "location": "body",
                "details": {},
            },
            {
                "id": "chest_logo",
                "label": "chest logo",
                "value": "white circle",
                "location": "left chest",
                "details": {"shape": "circle"},
            },
        ],
    }


def test_parse_sim_response_valid():
    report = parse_sim_response(json.dumps(_valid_sim_dict()))
    assert report["source_image"] == "x.png"
    assert len(report["criteria"]) == 2
    assert report["criteria"][0]["id"] == "main_color"


def test_parse_sim_response_strips_prose_wrapping():
    payload = "Here you go:\n" + json.dumps(_valid_sim_dict()) + "\nDone."
    # The LLM may pad despite instructions; parser should still extract.
    report = parse_sim_response(payload)
    assert report["criteria"][0]["id"] == "main_color"


def test_parse_sim_response_invalid_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_sim_response("totally not json")


def test_parse_sim_response_missing_criteria():
    d = _valid_sim_dict()
    del d["criteria"]
    with pytest.raises(ValueError, match="criteria"):
        parse_sim_response(json.dumps(d))


def test_parse_sim_response_missing_overall():
    d = _valid_sim_dict()
    del d["overall"]
    with pytest.raises(ValueError, match="overall"):
        parse_sim_response(json.dumps(d))


def test_parse_sim_response_empty_criteria():
    d = _valid_sim_dict()
    d["criteria"] = []
    with pytest.raises(ValueError, match="empty"):
        parse_sim_response(json.dumps(d))


def test_parse_sim_response_duplicate_id():
    d = _valid_sim_dict()
    d["criteria"][1]["id"] = "main_color"
    with pytest.raises(ValueError, match="duplicate"):
        parse_sim_response(json.dumps(d))


def test_parse_sim_response_invalid_id_format():
    d = _valid_sim_dict()
    d["criteria"][0]["id"] = "Main Color"
    with pytest.raises(ValueError, match="invalid id"):
        parse_sim_response(json.dumps(d))


def test_parse_sim_response_missing_criterion_field():
    d = _valid_sim_dict()
    del d["criteria"][0]["value"]
    with pytest.raises(ValueError, match="value"):
        parse_sim_response(json.dumps(d))
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: ImportError on `parse_sim_response`.

- [ ] **Step 3: Implement `parse_sim_response`**

Add to `image_matcher/engine.py`:

```python
import json
import re

_ID_PATTERN = re.compile(r"^[a-z0-9_]+$")


def _extract_json(text: str) -> dict:
    """Try direct parse first; if it fails, find the outermost {...} block."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"not valid JSON: {text[:80]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"not valid JSON: {e}") from e


def parse_sim_response(text: str) -> dict:
    """Parse and validate the sim-analysis JSON. Raise ValueError on any issue."""
    data = _extract_json(text)
    if not isinstance(data, dict):
        raise ValueError("response must be a JSON object")
    if "overall" not in data or not isinstance(data["overall"], dict):
        raise ValueError("missing or invalid 'overall' object")
    if not data["overall"].get("description"):
        raise ValueError("overall must contain non-empty 'description'")
    if "criteria" not in data:
        raise ValueError("missing 'criteria' list")
    if not isinstance(data["criteria"], list) or not data["criteria"]:
        raise ValueError("'criteria' must be a non-empty list")

    seen_ids: set[str] = set()
    required = ("id", "label", "value", "location")
    for i, c in enumerate(data["criteria"]):
        if not isinstance(c, dict):
            raise ValueError(f"criterion {i} is not an object")
        for field in required:
            if not c.get(field):
                raise ValueError(f"criterion {i}: missing or empty field {field!r}")
        cid = c["id"]
        if not _ID_PATTERN.match(cid):
            raise ValueError(f"criterion {i}: invalid id format {cid!r}")
        if cid in seen_ids:
            raise ValueError(f"duplicate criterion id {cid!r}")
        seen_ids.add(cid)
        if "details" not in c:
            c["details"] = {}
        elif not isinstance(c["details"], dict):
            raise ValueError(f"criterion {cid!r}: details must be an object")
    return data
```

Add `import json` and `import re` near the existing imports.

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add image_matcher/engine.py image_matcher/tests/test_engine.py
git commit -m "feat(image_matcher): add parse_sim_response with validation"
```

---

## Task 6: `COMPARE_PROMPT` constant + `build_compare_messages` (TDD)

Add the comparison prompt and a function that composes the messages payload for the second LLM call.

**Files:**
- Modify: `image_matcher/engine.py`
- Modify: `image_matcher/tests/test_engine.py`

- [ ] **Step 1: Append failing tests**

```python
from image_matcher.engine import COMPARE_PROMPT, build_compare_messages


def test_compare_prompt_exists():
    assert isinstance(COMPARE_PROMPT, str)
    assert "match" in COMPARE_PROMPT
    assert "missing_in_real" in COMPARE_PROMPT


def test_build_compare_messages_structure():
    sim_report = _valid_sim_dict()
    system, messages = build_compare_messages(
        sim_report, "B64", "image/jpeg", "tshirt_01_real.jpg"
    )

    assert system == COMPARE_PROMPT
    assert len(messages) == 1
    content = messages[0]["content"]

    image_blocks = [b for b in content if b["type"] == "image"]
    text_blocks = [b for b in content if b["type"] == "text"]

    assert len(image_blocks) == 1
    assert image_blocks[0]["source"]["media_type"] == "image/jpeg"
    assert image_blocks[0]["source"]["data"] == "B64"

    assert len(text_blocks) == 1
    text = text_blocks[0]["text"]
    assert "tshirt_01_real.jpg" in text
    # The sim_report JSON should be embedded so the LLM sees it.
    assert "main_color" in text
    assert "chest_logo" in text
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: ImportError.

- [ ] **Step 3: Add `COMPARE_PROMPT` and `build_compare_messages`**

```python
COMPARE_PROMPT = """You are a meticulous visual inspector comparing a real product
photo against a previously-analyzed 2D mockup.

You receive: a JSON report from the mockup (sim_report) and a photo of the
real product.

For EACH criterion in sim_report: find it in the real photo, decide if it
matches. Additionally: identify criteria visible on the real product that were
NOT in sim_report (extras).

## Strict rules

1. Respond with a SINGLE valid JSON object, no prose.
2. All field values in English.
3. One row per sim criterion (in order), then rows for extras found only on the
   real product.
4. `match: true` ONLY when both `sim_value` and `real_value` are non-null AND
   describe the same thing (semantically — "navy blue" and "dark navy" match;
   "navy blue" and "red" do not).
5. `match_type` is one of: exact, semantic, partial, missing_in_real, extra_on_real.
6. `confidence` is one of: high, medium, low.
7. NEVER claim match: true for something you cannot see in the real photo.
   If a criterion is in sim but you cannot see it (back of product, occluded,
   out of frame), set real_value: null, match: false,
   match_type: "missing_in_real", confidence: "low", and explain in note.
8. note is mandatory — one sentence justifying the decision.
9. differences lists specific visual discrepancies, empty list when match is exact.
10. real_details mirrors the structure of sim_details where possible.
11. summary.total must equal len(rows). summary.matched + summary.mismatched
    must equal summary.total. Recount carefully.
12. real_overall describes the photo: view_angle, lighting, image_quality,
    obstructions.

## Output schema

{
  "pair": "<base name>",
  "sim_image": "<from sim_report.source_image>",
  "real_image": "<filename from user message>",
  "real_overall": {
    "view_angle": "...", "lighting": "...",
    "image_quality": "...", "obstructions": []
  },
  "rows": [
    {
      "criterion": "<label or new label for extras>",
      "sim_value": "<sim value or null if extra_on_real>",
      "real_value": "<real value or null if missing_in_real>",
      "sim_details": { /* from sim_report or null */ },
      "real_details": { /* what you observe or null */ },
      "match": true | false,
      "match_type": "exact | semantic | partial | missing_in_real | extra_on_real",
      "confidence": "high | medium | low",
      "differences": ["..."],
      "note": "<one-sentence justification>"
    }
  ],
  "summary": {
    "total": <int>, "matched": <int>, "mismatched": <int>,
    "by_match_type": { "exact": <int>, "semantic": <int>, "partial": <int>,
                        "missing_in_real": <int>, "extra_on_real": <int> },
    "by_confidence": { "high": <int>, "medium": <int>, "low": <int> }
  }
}
"""


def build_compare_messages(
    sim_report: dict, image_b64: str, media_type: str, filename: str
) -> tuple[str, list[dict]]:
    """Return (system_prompt, messages) for the comparison LLM call."""
    sim_json = json.dumps(sim_report, indent=2, ensure_ascii=False)
    user_text = (
        f"The real product photo filename is {filename!r}. Use it verbatim in "
        f"the `real_image` field. The mockup analysis (sim_report) is:\n\n"
        f"```json\n{sim_json}\n```\n\n"
        f"Return the JSON described in the system prompt."
    )
    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {"type": "text", "text": user_text},
            ],
        }
    ]
    return COMPARE_PROMPT, messages
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add image_matcher/engine.py image_matcher/tests/test_engine.py
git commit -m "feat(image_matcher): add COMPARE_PROMPT and build_compare_messages"
```

---

## Task 7: `parse_compare_response` (TDD)

Parse + strictly validate the comparison JSON.

**Files:**
- Modify: `image_matcher/engine.py`
- Modify: `image_matcher/tests/test_engine.py`

- [ ] **Step 1: Append failing tests**

```python
from image_matcher.engine import parse_compare_response


def _valid_compare_dict():
    return {
        "pair": "t01",
        "sim_image": "t01_sim.png",
        "real_image": "t01_real.jpg",
        "real_overall": {
            "view_angle": "front",
            "lighting": "daylight",
            "image_quality": "sharp",
            "obstructions": [],
        },
        "rows": [
            {
                "criterion": "main color",
                "sim_value": "navy",
                "real_value": "navy",
                "sim_details": {"color_hex_approx": "#1B2A4E"},
                "real_details": {"color_hex_approx": "#15233F"},
                "match": True,
                "match_type": "semantic",
                "confidence": "high",
                "differences": ["minor hex drift"],
                "note": "matches semantically",
            },
            {
                "criterion": "back text",
                "sim_value": "TEAM 2026",
                "real_value": None,
                "sim_details": {"text_content": "TEAM 2026"},
                "real_details": None,
                "match": False,
                "match_type": "missing_in_real",
                "confidence": "low",
                "differences": ["back not visible"],
                "note": "cannot verify back",
            },
        ],
        "summary": {
            "total": 2,
            "matched": 1,
            "mismatched": 1,
            "by_match_type": {
                "exact": 0,
                "semantic": 1,
                "partial": 0,
                "missing_in_real": 1,
                "extra_on_real": 0,
            },
            "by_confidence": {"high": 1, "medium": 0, "low": 1},
        },
    }


def test_parse_compare_response_valid():
    report = parse_compare_response(json.dumps(_valid_compare_dict()))
    assert len(report["rows"]) == 2
    assert report["summary"]["total"] == 2


def test_parse_compare_response_invalid_match_type():
    d = _valid_compare_dict()
    d["rows"][0]["match_type"] = "wrong"
    with pytest.raises(ValueError, match="match_type"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_invalid_confidence():
    d = _valid_compare_dict()
    d["rows"][0]["confidence"] = "definitely"
    with pytest.raises(ValueError, match="confidence"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_match_true_with_null():
    d = _valid_compare_dict()
    d["rows"][1]["match"] = True  # row has real_value None
    with pytest.raises(ValueError, match="match=true"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_missing_in_real_with_non_null_real():
    d = _valid_compare_dict()
    d["rows"][1]["real_value"] = "something"  # but match_type is missing_in_real
    with pytest.raises(ValueError, match="missing_in_real"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_summary_total_mismatch():
    d = _valid_compare_dict()
    d["summary"]["total"] = 5
    with pytest.raises(ValueError, match="summary.total"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_summary_matched_mismatched_sum_wrong():
    d = _valid_compare_dict()
    d["summary"]["matched"] = 2
    d["summary"]["mismatched"] = 2
    with pytest.raises(ValueError, match="matched"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_empty_note():
    d = _valid_compare_dict()
    d["rows"][0]["note"] = ""
    with pytest.raises(ValueError, match="note"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_extra_on_real_with_non_null_sim():
    d = _valid_compare_dict()
    d["rows"].append(
        {
            "criterion": "stitch",
            "sim_value": "something",  # should be null for extra_on_real
            "real_value": "double stitch",
            "sim_details": None,
            "real_details": {"stitch_type": "double"},
            "match": False,
            "match_type": "extra_on_real",
            "confidence": "high",
            "differences": ["extra"],
            "note": "extra on real",
        }
    )
    d["summary"]["total"] = 3
    d["summary"]["mismatched"] = 2
    d["summary"]["by_match_type"]["extra_on_real"] = 1
    d["summary"]["by_confidence"]["high"] = 2
    with pytest.raises(ValueError, match="extra_on_real"):
        parse_compare_response(json.dumps(d))
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: ImportError on `parse_compare_response`.

- [ ] **Step 3: Implement `parse_compare_response`**

Add to `image_matcher/engine.py`:

```python
_MATCH_TYPES = {"exact", "semantic", "partial", "missing_in_real", "extra_on_real"}
_CONFIDENCES = {"high", "medium", "low"}


def parse_compare_response(text: str) -> dict:
    """Parse and validate the comparison JSON. Raise ValueError on any issue."""
    data = _extract_json(text)
    if not isinstance(data, dict):
        raise ValueError("response must be a JSON object")

    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("'rows' must be a non-empty list")

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"row {i} is not an object")
        for field in ("criterion", "match", "match_type", "confidence", "note"):
            if field not in row:
                raise ValueError(f"row {i}: missing field {field!r}")
        if not isinstance(row["note"], str) or not row["note"].strip():
            raise ValueError(f"row {i}: note must be a non-empty string")
        if row["match_type"] not in _MATCH_TYPES:
            raise ValueError(
                f"row {i}: invalid match_type {row['match_type']!r}, "
                f"allowed: {sorted(_MATCH_TYPES)}"
            )
        if row["confidence"] not in _CONFIDENCES:
            raise ValueError(
                f"row {i}: invalid confidence {row['confidence']!r}, "
                f"allowed: {sorted(_CONFIDENCES)}"
            )
        sim_val = row.get("sim_value")
        real_val = row.get("real_value")
        if row["match"] is True and (sim_val is None or real_val is None):
            raise ValueError(
                f"row {i}: cannot have match=true with a null value"
            )
        if row["match_type"] == "missing_in_real" and real_val is not None:
            raise ValueError(
                f"row {i}: match_type=missing_in_real requires real_value=null"
            )
        if row["match_type"] == "extra_on_real" and sim_val is not None:
            raise ValueError(
                f"row {i}: match_type=extra_on_real requires sim_value=null"
            )

    summary = data.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("missing or invalid 'summary' object")
    if summary.get("total") != len(rows):
        raise ValueError(
            f"summary.total={summary.get('total')} but rows has {len(rows)}"
        )
    matched_count = sum(1 for r in rows if r["match"] is True)
    mismatched_count = len(rows) - matched_count
    if summary.get("matched") != matched_count:
        raise ValueError(
            f"summary.matched={summary.get('matched')} but actual is {matched_count}"
        )
    if summary.get("mismatched") != mismatched_count:
        raise ValueError(
            f"summary.mismatched={summary.get('mismatched')} but actual is "
            f"{mismatched_count}"
        )
    return data
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add image_matcher/engine.py image_matcher/tests/test_engine.py
git commit -m "feat(image_matcher): add parse_compare_response with strict validation"
```

---

## Task 8: `render_table` (TDD)

ASCII table with 4 columns, truncation on long values, `—` for nulls.

**Files:**
- Modify: `image_matcher/engine.py`
- Modify: `image_matcher/tests/test_engine.py`

- [ ] **Step 1: Append failing tests**

```python
from image_matcher.engine import render_table


def test_render_table_basic():
    report = _valid_compare_dict()
    out = render_table(report)
    assert "Criterion" in out
    assert "Sim" in out
    assert "Real" in out
    assert "Match" in out
    assert "main color" in out
    assert "✓" in out
    assert "✗" in out


def test_render_table_null_displays_dash():
    report = _valid_compare_dict()
    out = render_table(report)
    # row with real_value=None should show em-dash
    assert "—" in out


def test_render_table_truncates_long_values():
    report = _valid_compare_dict()
    report["rows"][0]["sim_value"] = "a" * 200
    out = render_table(report, width=80)
    assert "…" in out
    longest_line = max(len(line) for line in out.splitlines())
    assert longest_line <= 80
```

- [ ] **Step 2: Run tests to verify failure**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `render_table`**

```python
def render_table(report: dict, width: int = 80) -> str:
    """Render the compare report as an ASCII table that fits within `width`.

    Columns: Criterion | Sim | Real | Match. Long values are truncated with `…`;
    null values are rendered as `—`.
    """
    rows = report.get("rows", [])
    if not rows:
        return "(no rows)"

    # Fixed-width Match column (✓/✗ inside |   X   |): 5 inner chars.
    match_col = 5
    borders_overhead = 13  # 5 vertical bars + 4 padding pairs (1 space each side)
    available = max(width - match_col - borders_overhead, 24)
    # Split available evenly across the three text columns.
    col_w = available // 3
    crit_w = col_w
    sim_w = col_w
    real_w = available - crit_w - sim_w

    def cell(value, w: int) -> str:
        if value is None:
            text = "—"
        else:
            text = str(value)
        if len(text) > w:
            text = text[: w - 1] + "…"
        return text.ljust(w)

    sep_top = "┌" + "─" * (crit_w + 2) + "┬" + "─" * (sim_w + 2) + "┬" + "─" * (real_w + 2) + "┬" + "─" * (match_col + 2) + "┐"
    sep_mid = "├" + "─" * (crit_w + 2) + "┼" + "─" * (sim_w + 2) + "┼" + "─" * (real_w + 2) + "┼" + "─" * (match_col + 2) + "┤"
    sep_bot = "└" + "─" * (crit_w + 2) + "┴" + "─" * (sim_w + 2) + "┴" + "─" * (real_w + 2) + "┴" + "─" * (match_col + 2) + "┘"

    def row(c, s, r, m):
        return (
            f"│ {cell(c, crit_w)} │ {cell(s, sim_w)} │ {cell(r, real_w)} "
            f"│ {m.center(match_col)} │"
        )

    lines = [sep_top, row("Criterion", "Sim", "Real", "Match"), sep_mid]
    for r in rows:
        mark = "✓" if r["match"] else "✗"
        lines.append(row(r["criterion"], r.get("sim_value"), r.get("real_value"), mark))
    lines.append(sep_bot)
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify pass**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/test_engine.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add image_matcher/engine.py image_matcher/tests/test_engine.py
git commit -m "feat(image_matcher): add render_table with truncation and null handling"
```

---

## Task 9: `call_llm` + orchestrators

Add the single I/O function and the three orchestrators that compose pure pieces. These are NOT unit-tested — the manual checklist covers them.

**Files:**
- Modify: `image_matcher/engine.py`

- [ ] **Step 1: Implement `call_llm`**

Add to `image_matcher/engine.py`:

```python
import os
import time

from anthropic import Anthropic, APIStatusError, RateLimitError


def call_llm(
    system: str,
    messages: list[dict],
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
) -> str:
    """Single API call to Anthropic. One retry on rate-limit or 5xx.

    Returns the text body of the first content block. Raises any other error
    with context preserved.
    """
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    for attempt in range(2):
        try:
            resp = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            return resp.content[0].text
        except (RateLimitError, APIStatusError) as e:
            status = getattr(e, "status_code", None)
            if attempt == 0 and (isinstance(e, RateLimitError) or (status and 500 <= status < 600)):
                logger.warning("retry-able LLM error (%s); retrying once", e)
                time.sleep(2)
                continue
            raise
    raise RuntimeError("unreachable")
```

- [ ] **Step 2: Implement `analyze_sim`**

```python
def analyze_sim(sim_path: Path, model: str = "claude-sonnet-4-6") -> dict:
    """Read sim image → call LLM → parse → return validated sim_report."""
    media_type, b64 = encode_image(sim_path)
    system, messages = build_sim_messages(b64, media_type, sim_path.name)
    raw = call_llm(system, messages, model=model)
    try:
        report = parse_sim_response(raw)
    except ValueError as e:
        raise ValueError(f"sim parse failed for {sim_path.name}: {e}") from e
    # Ensure the report carries the actual filename even if the LLM dropped it.
    report["source_image"] = sim_path.name
    return report
```

- [ ] **Step 3: Implement `compare_real`**

```python
def compare_real(
    sim_report: dict, real_path: Path, model: str = "claude-sonnet-4-6"
) -> dict:
    """Read real image → call LLM with sim_report → parse → return compare_report.

    One retry with a corrective hint if parse fails the first time.
    """
    media_type, b64 = encode_image(real_path)
    system, messages = build_compare_messages(
        sim_report, b64, media_type, real_path.name
    )
    raw = call_llm(system, messages, model=model)
    try:
        report = parse_compare_response(raw)
    except ValueError as first_error:
        logger.warning(
            "compare parse failed for %s: %s — retrying with hint",
            real_path.name,
            first_error,
        )
        retry_messages = [
            *messages,
            {"role": "assistant", "content": raw},
            {
                "role": "user",
                "content": (
                    f"Your previous response had this validation error: "
                    f"{first_error}. Please correct and return ONLY the valid "
                    f"JSON object."
                ),
            },
        ]
        raw = call_llm(system, retry_messages, model=model)
        report = parse_compare_response(raw)  # raises if still bad
    report["real_image"] = real_path.name
    return report
```

- [ ] **Step 4: Implement `process_pair`**

```python
def process_pair(
    base: str,
    sim_path: Path,
    real_path: Path,
    output_dir: Path,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """Full pipeline for one pair. Saves sim.json + compare.json under
    output_dir/<base>/. Returns the compare report."""
    pair_dir = output_dir / base
    pair_dir.mkdir(parents=True, exist_ok=True)

    sim_report = analyze_sim(sim_path, model=model)
    (pair_dir / "sim.json").write_text(
        json.dumps(sim_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    compare_report = compare_real(sim_report, real_path, model=model)
    compare_report["pair"] = base  # canonical, overrides whatever LLM wrote
    (pair_dir / "compare.json").write_text(
        json.dumps(compare_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return compare_report
```

- [ ] **Step 5: Run all existing tests as a regression check**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/ -v`
Expected: all pure-function tests still pass.

- [ ] **Step 6: Commit**

```bash
git add image_matcher/engine.py
git commit -m "feat(image_matcher): add call_llm and orchestrators"
```

---

## Task 10: `image_matcher/run.py` CLI

Thin CLI wrapper using relative imports. Defaults resolve relative to the package location so the command works from any cwd.

**Files:**
- Modify: `image_matcher/run.py`

- [ ] **Step 1: Replace placeholder with the CLI**

```python
"""Thin CLI wrapper around `image_matcher.engine`.

Invoke from project root with: `python -m image_matcher.run`.
See `image_matcher/README.md` for usage.
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from .engine import find_pairs, process_pair, render_table

_PACKAGE_DIR = Path(__file__).resolve().parent
_DEFAULT_INPUT = _PACKAGE_DIR / "input"
_DEFAULT_OUTPUT = _PACKAGE_DIR / "output"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare sim vs real product images.",
        prog="python -m image_matcher.run",
    )
    parser.add_argument("--folder", type=Path, default=_DEFAULT_INPUT,
                        help="Folder containing *_sim.* and *_real.* pairs.")
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT,
                        help="Folder where per-pair output is written.")
    parser.add_argument("--model", default="claude-sonnet-4-6",
                        help="Anthropic model id.")
    parser.add_argument("--verbose", action="store_true",
                        help="Enable INFO logging.")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(name)s: %(message)s",
    )

    if not args.folder.exists():
        print(f"input folder not found: {args.folder}", file=sys.stderr)
        return 2

    pairs = find_pairs(args.folder)
    if not pairs:
        print(f"no pairs found in {args.folder}/")
        return 0

    failures = 0
    for i, (base, sim, real) in enumerate(pairs, 1):
        print(f"\n[{i}/{len(pairs)}] {base}:")
        print(f"  → analyzing {sim.name} ... (via LLM)")
        try:
            report = process_pair(base, sim, real, args.output, model=args.model)
        except Exception as e:  # batch must continue
            print(f"  ✗ failed: {e}", file=sys.stderr)
            failures += 1
            continue
        print(render_table(report))
        print(f"  → {args.output / base / 'compare.json'} saved")

    if failures:
        print(f"\n{failures} pair(s) failed; see logs above.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test the CLI (no API call yet)**

Run: `.venv\Scripts\python.exe -m image_matcher.run --folder nonexistent`
Expected: `input folder not found: nonexistent`, exit code 2.

Run: `.venv\Scripts\python.exe -m image_matcher.run`
Expected: `no pairs found in <…>image_matcher\input/`, exit code 0 (folder is empty).

- [ ] **Step 3: Commit**

```bash
git add image_matcher/run.py
git commit -m "feat(image_matcher): add run.py CLI for batch processing"
```

---

## Task 11: Manual verification checklist

Append the manual checklist into the package README and run end-to-end with one real pair.

**Files:**
- Modify: `image_matcher/README.md`

- [ ] **Step 1: Append the manual checklist section**

Append to `image_matcher/README.md`:

```markdown

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
```

- [ ] **Step 2: Run unit tests one more time**

Run: `.venv\Scripts\python.exe -m pytest image_matcher/tests/ -v`
Expected: all unit tests pass.

- [ ] **Step 3: Commit**

```bash
git add image_matcher/README.md
git commit -m "docs(image_matcher): add manual verification checklist"
```

- [ ] **Step 4: Manual end-to-end smoke** (requires `ANTHROPIC_API_KEY`)

1. Place a mockup and a photo pair into `image_matcher/input/`, e.g. `image_matcher/input/tshirt_01_sim.png` + `image_matcher/input/tshirt_01_real.jpg`.
2. `$env:ANTHROPIC_API_KEY = "sk-ant-..."` (PowerShell).
3. `.venv\Scripts\python.exe -m image_matcher.run --verbose`
4. Walk through every item of the checklist above. Report any failures.

This step does NOT auto-pass. The implementer reports back to the user; user verifies and approves before declaring MVP complete.

---

## Task 12: Streamlit UI (planned 2026-05-26)

Add a minimal Streamlit UI on top of the existing engine. The engine code is NOT modified — the UI imports `find_pairs` and `process_pair` and reuses them. Goal: replace the terminal-only experience with a single page where the user picks a pair, sees both images side by side, presses a button, and gets the result table in the browser.

**Files:**
- Modify: `requirements.txt` (root)
- Create: `image_matcher/app.py`
- Create: `image_matcher/theme.css`
- Modify: `image_matcher/README.md`
- NOT modified: `image_matcher/engine.py`, `image_matcher/run.py`, `image_matcher/tests/`

**Constraint:** ~2.5-3 hours total. No new abstractions, no refactor. UI is a single file plus one CSS file, single page, vertical layout.

**Design choice (locked):** Streamlit. Confirmed by user 2026-05-26. Rationale: Python-only, library is standard for "tool with input → process → output" demos, ~95 lines of UI cover everything needed, engine stays intact, easy to explain at presentation time.

**Distilled principles from `image_matcher/CLAUDE.md` + `Front-end design.md`** (the workflow-specific rules — Tailwind CDN, Puppeteer screenshots, `node serve.mjs`, reference-image matching — are **not** applicable to a Python/Streamlit/Windows stack and are skipped; we keep only the aesthetic principles that we *can* apply by injecting CSS into Streamlit):
- **Distinctive typography**: avoid Inter/Roboto/Arial/system defaults. Pair a display serif with a clean sans. Apply tight tracking on large headings, generous line-height on body.
- **Custom palette, not default**: avoid default Streamlit blue/red and default Tailwind indigo/blue. Define semantic CSS variables.
- **Layered shadows, not flat**: surfaces have an elevation system (base → elevated), not all on the same z-plane.
- **Animations** on `transform` and `opacity` only, with spring-style easing. Never `transition-all`.
- **Interactive states**: hover, focus-visible, active, disabled — distinct and visible.
- **Atmosphere**: subtle background tint + soft texture instead of flat white.
- **One BOLD direction**, executed with precision: chosen direction is *editorial / atelier* — referencing fashion magazines + quality inspection. Cream/ivory base, charcoal ink, single vermilion accent.

**Layout (locked, upload-only flow):**
- Centered single-column page (`layout="centered"`).
- Title (serif display) + one-line caption (italic).
- `st.text_input` where the user types a pair base name (e.g. `Tricou_05`). Validated against `^[A-Za-z0-9_]+$`.
- Two `st.file_uploader` widgets side by side: one for the sim image, one for the real image. Accept `png|jpg|jpeg|webp`.
- When both files are uploaded: side-by-side preview with original filenames as captions.
- Single primary button "Analizează", **disabled** until base name is valid AND both files uploaded. Spinner during the LLM call.
- On click: files are saved to `image_matcher/input/<base>_sim.<ext>` + `<base>_real.<ext>` (so the engine's existing path-based API can consume them); then `process_pair` is called.
- After the call: three metrics (Total / Matched / Mismatched) + `st.dataframe` with columns Criterion / Sim / Real / Match (✅/❌).
- `@st.cache_data` keyed by `(base, sim_path_str, real_path_str)` so re-clicks on the same inputs don't re-spend tokens.
- The selector with existing pairs in `input/` is **NOT** part of the UI. The user works exclusively via upload. Files written to `input/` are a side-effect of the upload, not surfaced in the UI.
- Custom CSS is loaded from a sibling file `image_matcher/theme.css` and injected once at top of `app.py` via `st.markdown(unsafe_allow_html=True)`.

- [ ] **Step 1: Add streamlit to root requirements.txt**

Modify `requirements.txt` (root) to:

```
anthropic>=0.102.0
pytest>=9.0.0
streamlit>=1.40.0
```

Then install: `.venv\Scripts\pip.exe install streamlit>=1.40.0`.

Verify: `.venv\Scripts\python.exe -c "import streamlit; print(streamlit.__version__)"` prints a version ≥ 1.40.

- [ ] **Step 2: Create `image_matcher/app.py` with the full UI**

```python
"""Streamlit UI for image_matcher.

Run from project root with: `streamlit run image_matcher/app.py`.
The engine logic (process_pair) is reused untouched.
"""
import re
from pathlib import Path

import streamlit as st

from image_matcher.engine import process_pair

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"
_THEME_CSS_PATH = Path(__file__).parent / "theme.css"

_SUPPORTED_EXTS = ("png", "jpg", "jpeg", "webp")
_BASE_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")

st.set_page_config(page_title="Image Match", layout="centered")

# Inject custom theme. Kept in a sibling file so app.py stays focused on logic.
st.markdown(
    f"<style>{_THEME_CSS_PATH.read_text(encoding='utf-8')}</style>",
    unsafe_allow_html=True,
)


def _match_icon(is_match: bool) -> str:
    # Geometric Unicode symbols, not emoji. ui-ux-pro-max + CLAUDE.md both
    # forbid emoji-as-icons; ✓ / ✗ render as flat text glyphs.
    return "✓" if is_match else "✗"


@st.cache_data(show_spinner=False)
def _run_pair(base: str, sim_str: str, real_str: str) -> dict:
    """Cached wrapper around process_pair. Streamlit hashes by argument values,
    so the LLM is re-called only when the inputs change."""
    return process_pair(base, Path(sim_str), Path(real_str), OUTPUT_DIR)


st.title("Image Match — Sim vs Real")
st.caption("Compară un mockup 2D cu fotografia produsului real.")

base_raw = st.text_input(
    "Nume pereche:",
    placeholder="ex: Tricou_05 (litere, cifre și _)",
)
base = base_raw.strip()
base_valid = bool(base) and bool(_BASE_NAME_RE.match(base))
if base and not base_valid:
    st.warning("Numele poate conține doar litere, cifre și `_` (fără spații).")

col_sim, col_real = st.columns(2)
with col_sim:
    sim_file = st.file_uploader(
        "Imagine sim (mockup)", type=list(_SUPPORTED_EXTS), key="sim_upload",
    )
with col_real:
    real_file = st.file_uploader(
        "Imagine real", type=list(_SUPPORTED_EXTS), key="real_upload",
    )

if sim_file and real_file:
    prev_sim, prev_real = st.columns(2)
    with prev_sim:
        st.image(sim_file, caption=sim_file.name, use_container_width=True)
    with prev_real:
        st.image(real_file, caption=real_file.name, use_container_width=True)

st.divider()

ready = base_valid and (sim_file is not None) and (real_file is not None)
if st.button(
    "Analizează",
    type="primary",
    use_container_width=True,
    disabled=not ready,
):
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    sim_ext = Path(sim_file.name).suffix.lower()
    real_ext = Path(real_file.name).suffix.lower()
    sim_path = INPUT_DIR / f"{base}_sim{sim_ext}"
    real_path = INPUT_DIR / f"{base}_real{real_ext}"
    sim_path.write_bytes(sim_file.getvalue())
    real_path.write_bytes(real_file.getvalue())

    try:
        with st.spinner("Analizez perechea cu Claude... (poate dura 30-60s)"):
            report = _run_pair(base, str(sim_path), str(real_path))
    except KeyError:
        st.error(
            "Lipsește variabila de mediu ANTHROPIC_API_KEY. "
            "Setează-o înainte să pornești UI-ul."
        )
        st.stop()
    except Exception as e:
        st.error(f"Eroare la analiză: {e}")
        st.stop()

    summary = report["summary"]
    c1, c2, c3 = st.columns(3)
    c1.metric("Total", summary["total"])
    c2.metric("Matched", summary["matched"])
    c3.metric("Mismatched", summary["mismatched"])

    table_rows = [
        {
            "Criterion": r["criterion"],
            "Sim": r.get("sim_value") or "—",
            "Real": r.get("real_value") or "—",
            "Match": _match_icon(r["match"]),
        }
        for r in report["rows"]
    ]
    st.dataframe(table_rows, use_container_width=True, hide_index=True)
    st.caption(
        f"Rezultatul complet a fost salvat în "
        f"{OUTPUT_DIR / base}/compare.json"
    )
```

- [ ] **Step 2b: Create `image_matcher/theme.css` with the editorial/atelier theme**

Single file, ~80 lines. Targets Streamlit's stable `data-testid` selectors. Applies the distilled principles: font pairing, custom palette, layered shadows, animations on transform/opacity, distinct interactive states.

```css
/* image_matcher/theme.css — editorial/atelier theme for the Streamlit UI.
 *
 * Aesthetic direction (locked): ivory canvas, charcoal ink, single vermilion
 * accent. Fonts: Fraunces (variable serif display) + Geist (body). Avoids
 * generic Streamlit/Tailwind defaults; principles distilled from
 * image_matcher/CLAUDE.md and Front-end design.md. */

@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600;9..144,700&family=Geist:wght@400;500;600&display=swap');

:root {
  --bg-ivory:    #F5F1EA;
  --bg-card:     #FFFFFF;
  --ink:         #1A1817;
  --ink-muted:   #5C5650;
  --accent:      #C13B1A;       /* vermilion */
  --accent-soft: rgba(193, 59, 26, 0.08);
  --border:      #E0DAD0;
  --shadow-sm:   0 1px 2px rgba(26, 24, 23, 0.04),
                 0 2px 8px rgba(26, 24, 23, 0.04);
  --shadow-md:   0 4px 12px rgba(26, 24, 23, 0.06),
                 0 8px 24px rgba(26, 24, 23, 0.05);
  --ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1);
}

[data-testid="stAppViewContainer"] { background: var(--bg-ivory); }
[data-testid="stHeader"] { background: transparent; }

html, body,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] label,
.stTextInput input,
.stFileUploader,
[data-testid="stMetricLabel"],
[data-testid="stMetricValue"] {
  font-family: 'Geist', -apple-system, BlinkMacSystemFont, sans-serif !important;
  color: var(--ink);
}

[data-testid="stMarkdownContainer"] h1 {
  font-family: 'Fraunces', Georgia, serif !important;
  font-weight: 600;
  font-variation-settings: "opsz" 144, "SOFT" 50;
  letter-spacing: -0.025em;
  color: var(--ink);
  margin-bottom: 0.25rem;
}

[data-testid="stCaptionContainer"] {
  font-family: 'Fraunces', Georgia, serif !important;
  font-style: italic;
  color: var(--ink-muted);
  font-size: 1rem;
}

.stTextInput input {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 2px;
  transition: border-color 0.15s ease-out, box-shadow 0.15s ease-out;
}
.stTextInput input:focus-visible {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
  outline: none;
}

[data-testid="stFileUploader"] section {
  background: var(--bg-card);
  border: 1.5px dashed var(--border);
  border-radius: 4px;
  transition: border-color 0.15s ease-out, background 0.15s ease-out;
}
[data-testid="stFileUploader"] section:hover {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.stButton > button[kind="primary"] {
  background: var(--ink);
  color: var(--bg-ivory);
  border: none;
  border-radius: 2px;
  padding: 0.75rem 1.5rem;
  font-family: 'Geist', sans-serif;
  font-weight: 500;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  font-size: 0.8rem;
  box-shadow: var(--shadow-sm);
  transition: transform 0.18s var(--ease-spring),
              box-shadow 0.18s ease-out,
              background 0.18s ease-out;
}
.stButton > button[kind="primary"]:hover:not(:disabled) {
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
  background: var(--accent);
}
.stButton > button[kind="primary"]:active:not(:disabled) {
  transform: translateY(0);
}
.stButton > button[kind="primary"]:focus-visible:not(:disabled) {
  outline: none;
  box-shadow: 0 0 0 3px var(--accent-soft), var(--shadow-md);
}
.stButton > button[kind="primary"]:disabled {
  opacity: 0.4;
  cursor: not-allowed;
  box-shadow: none;
}

[data-testid="stMetric"] {
  background: var(--bg-card);
  padding: 1rem 1.25rem;
  border-radius: 4px;
  border-left: 3px solid var(--accent);
  box-shadow: var(--shadow-sm);
}
[data-testid="stMetricValue"] {
  font-family: 'Fraunces', Georgia, serif !important;
  font-weight: 600;
  font-variation-settings: "opsz" 144;
}

[data-testid="stDataFrame"] {
  border: 1px solid var(--border);
  border-radius: 4px;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

hr { border-color: var(--border); opacity: 0.6; }

/* Accessibility: respect user OS-level reduced-motion preference. */
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
  }
  .stButton > button[kind="primary"]:hover:not(:disabled) {
    transform: none;
  }
}
```

Verify the file is syntactically valid CSS by opening it in any browser DevTools after Step 3 — Streamlit silently swallows broken CSS, so a quick `cat image_matcher/theme.css | head -20` to confirm no garbled chars + visual check in browser is enough.

- [ ] **Step 3: Smoke-test (no API call)**

Run: `.venv\Scripts\streamlit.exe run image_matcher/app.py`

Expected: browser opens at `http://localhost:8501`, page shows title, the "Nume pereche" input is visible, two file uploaders side by side, and the "Analizează" button is **disabled** (grayed out).

Functional checks:
- [ ] Type `bad name!` in the base input → warning appears about allowed characters.
- [ ] Type `Test_01` → warning disappears but button stays disabled (no files yet).
- [ ] Upload one image → button still disabled.
- [ ] Upload the second image → previews show side by side, button becomes enabled.
- [ ] Try uploading a `.gif` → uploader rejects it (only `png/jpg/jpeg/webp` accepted).

Visual checks (theme applied):
- [ ] Background is ivory/cream (not white).
- [ ] Title is a serif (Fraunces), NOT the default Streamlit sans.
- [ ] Caption under title is italic serif, muted gray.
- [ ] File-uploader zones have dashed borders that turn vermilion on hover.
- [ ] Disabled button looks deliberately disabled (low opacity, no shadow); enabled button is charcoal with subtle shadow.
- [ ] Hovering the enabled button lifts it slightly (translateY) and turns it vermilion.

Accessibility checks (from ui-ux-pro-max Pre-Delivery Checklist):
- [ ] Tabbing with keyboard: focus on the enabled button shows a visible ring (`:focus-visible` style) — not removed.
- [ ] OS-level "reduce motion" enabled (Windows Settings → Accessibility → Visual effects → off): button no longer lifts on hover, no animations play.
- [ ] No emoji icons in the rendered table — only `✓` / `✗` glyphs.

Do NOT click "Analizează" yet (no API call in this step). Close with Ctrl+C in terminal.

- [ ] **Step 4: End-to-end test with a real upload** (requires `ANTHROPIC_API_KEY`)

1. `$env:ANTHROPIC_API_KEY = "sk-ant-..."` (PowerShell).
2. `.venv\Scripts\streamlit.exe run image_matcher/app.py`
3. In the "Nume pereche" field, type `UI_Test_01`.
4. In the sim uploader: drag-and-drop `image_matcher/input/Geaca_01_sim.png` (or any sim PNG from disk).
5. In the real uploader: drag-and-drop `image_matcher/input/Geaca_01_real.png`.
6. Verify previews appear and the button is now enabled.
7. Click "Analizează".
8. Verify:
   - [ ] Spinner appears during the call.
   - [ ] After ~30-60s, three metrics show non-zero values (around Total=14, Matched=12, Mismatched=2 — exact numbers can drift slightly between LLM runs).
   - [ ] Table renders with one row per criterion.
   - [ ] Rows with `match: false` show ❌; the rest show ✅.
   - [ ] On disk: `image_matcher/input/UI_Test_01_sim.png` and `UI_Test_01_real.png` were saved.
   - [ ] On disk: `image_matcher/output/UI_Test_01/compare.json` exists.
   - [ ] Re-clicking "Analizează" without changing inputs returns instantly (cache hit, no second LLM call).
9. Stop the server with Ctrl+C. Optionally delete `image_matcher/input/UI_Test_01_*` and `image_matcher/output/UI_Test_01/` after the test.

If the API key is missing, the UI shows a clear error and stops — no traceback.

- [ ] **Step 5: Update `image_matcher/README.md`**

Append a new section after the existing "Run" section:

```markdown

## Run UI

From project root, with `ANTHROPIC_API_KEY` set:

```
streamlit run image_matcher/app.py
```

The browser opens at `http://localhost:8501`. Pick a pair from the dropdown,
press "Analizează", get the comparison table in the page.
```

- [ ] **Step 6: Commit**

```bash
git add requirements.txt image_matcher/app.py image_matcher/theme.css image_matcher/README.md
git commit -m "feat(image_matcher): add Streamlit UI with editorial theme"
```

---

## Done criteria

- All 11 tasks completed and committed.
- `python -m pytest image_matcher/tests/ -v` passes locally.
- Manual checklist all green on one real pair.
- Branch is whichever you're working on (master or feat/mvp-implementation); no merge to remote until you decide.

---

## Done criteria (UI, Task 12)

- `streamlit run image_matcher/app.py` opens a page with: base-name input, two upload widgets, disabled "Analizează" button.
- Typing an invalid base name shows a clear warning; uploading anything other than `png/jpg/jpeg/webp` is rejected by the widget.
- With a valid base name and both files uploaded, the button enables and clicking it: saves the files to `image_matcher/input/<base>_sim.<ext>` + `<base>_real.<ext>`, calls `process_pair`, then renders three metrics and a table with one row per criterion.
- Re-clicking with the same inputs is instant (cache hit, no second LLM call).
- Missing `ANTHROPIC_API_KEY` produces a clean error in the UI, not a traceback.
- **Theme applied**: ivory background, Fraunces serif title, Geist body, dashed uploader borders, vermilion hover state on button, layered shadow on metric cards. Visibly distinct from default Streamlit.
- No change required in `engine.py`, `run.py`, or any test file. CLI workflow (`python -m image_matcher.run`) keeps working unchanged.

---

## Notes on future integration

The package is designed to merge cleanly with the future Ciptronic Validator code:

- `image_matcher` is a self-contained Python package — UI code calls `from image_matcher.engine import process_pair`.
- `output_dir` is a parameter, so the UI can pass `Path("uploads") / session_id` instead of the CLI default.
- If you later prefer the engine to live under `agents/` (matching the Ciptronic naming convention), rename the folder with `git mv image_matcher agents` and rename `engine.py` to `matcher.py` if desired. The internal relative imports keep working; only external consumers update their import path.
- `requirements.txt` at root is shared; future tasks append `fastapi`, `jinja2`, etc.
