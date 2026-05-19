"""Image match engine: pure functions + a single I/O wrapper.

Pure functions (find_pairs, encode_image, build_*_messages, parse_*_response,
render_table) are unit-tested in `tests/test_engine.py`. The single I/O
function (`call_llm`) and the orchestrators (analyze_sim, compare_real,
process_pair) are verified manually with the checklist in README.md.
"""
import base64
import json
import logging
import re
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
