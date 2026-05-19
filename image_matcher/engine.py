"""Image match engine: pure functions + a single I/O wrapper.

Pure functions (find_pairs, encode_image, build_*_messages, parse_*_response,
render_table) are unit-tested in `tests/test_engine.py`. The single I/O
function (`call_llm`) and the orchestrators (analyze_sim, compare_real,
process_pair) are verified manually with the checklist in README.md.
"""
import base64
import json
import logging
import os
import re
import time
from pathlib import Path

from anthropic import Anthropic, APIStatusError, RateLimitError

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

    # Summary is fully derivable from rows; recompute it instead of trusting the
    # LLM. Sonnet 4.6 reliably gets row-level decisions right but mis-counts
    # totals/distributions in long lists, so we use rows as the source of truth.
    matched_count = sum(1 for r in rows if r["match"] is True)
    by_match_type = {mt: 0 for mt in _MATCH_TYPES}
    by_confidence = {c: 0 for c in _CONFIDENCES}
    for r in rows:
        by_match_type[r["match_type"]] += 1
        by_confidence[r["confidence"]] += 1
    llm_summary = data.get("summary")
    if isinstance(llm_summary, dict) and (
        llm_summary.get("total") != len(rows)
        or llm_summary.get("matched") != matched_count
    ):
        logger.info(
            "compare summary diverged from rows (LLM: total=%s matched=%s; "
            "actual: total=%s matched=%s) — recomputed",
            llm_summary.get("total"), llm_summary.get("matched"),
            len(rows), matched_count,
        )
    data["summary"] = {
        "total": len(rows),
        "matched": matched_count,
        "mismatched": len(rows) - matched_count,
        "by_match_type": by_match_type,
        "by_confidence": by_confidence,
    }
    return data


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
    raw = call_llm(system, messages, model=model, max_tokens=8192)
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
        raw = call_llm(system, retry_messages, model=model, max_tokens=8192)
        report = parse_compare_response(raw)  # raises if still bad
    report["real_image"] = real_path.name
    return report


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
