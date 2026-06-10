"""Image match engine: pure functions + a single I/O wrapper.

Pure functions (find_pairs, encode_image, build_*_messages, parse_*_response,
render_table) are unit-tested in `tests/test_engine.py`. The single I/O
function (`call_llm`) and the orchestrators (analyze_sim, compare_real,
process_pair) are verified manually with the checklist in README.md.
"""
import base64
import io
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


_ALLOWED_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


def _detect_media_type(data: bytes) -> str | None:
    """Detect image media_type from magic bytes; None if unrecognized.

    Users frequently rename files (.png → .jpg) without re-exporting, so the
    extension is unreliable; Anthropic detects magic bytes and 400s on
    mismatches. We mirror that detection.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def encode_image(path: Path) -> tuple[str, str]:
    """Read an image file, return (media_type, base64_data).

    Raises ValueError on unsupported extension, unrecognized magic bytes, or
    files > 5MB. Raises FileNotFoundError if path does not exist.
    """
    ext = path.suffix.lower()
    if ext not in _ALLOWED_EXTS:
        raise ValueError(f"unsupported image extension: {ext!r}")
    data_bytes = path.read_bytes()
    if len(data_bytes) > _MAX_IMAGE_BYTES:
        raise ValueError(
            f"{path.name} ({len(data_bytes)} bytes) exceeds 5MB limit"
        )
    media_type = _detect_media_type(data_bytes)
    if media_type is None:
        raise ValueError(
            f"{path.name}: cannot detect image format from magic bytes"
        )
    return media_type, base64.b64encode(data_bytes).decode("ascii")


SIM_PROMPT = """You are a meticulous visual inspector analyzing a 2D product mockup image.

Your job: identify every distinguishable element of the product and return a
detailed structured JSON. The mockup is a clean 2D design (Figma / Illustrator /
Photoshop output) — colors are flat, edges are clean, no photographic noise.

## Strict rules

1. Respond with a SINGLE valid JSON object, no prose before or after.
2. All field values in Romanian, EXCEPT `id` which stays snake_case ASCII
   English (see rule 4). Use natural Romanian for `label`, `value`, `location`,
   `details`, and the `overall` block.
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
photo against its 2D mockup.

You receive TWO images and one JSON report:
- Image 1 — the MOCKUP (the 2D design).
- Image 2 — the REAL product photo.
- sim_report — a JSON analysis of the mockup (Image 1).

Compare the two images DIRECTLY, side by side, with your own eyes. The
sim_report is only a checklist of criteria to walk through — it is NOT ground
truth about the real product. You MUST measure every value on the REAL product
by looking at Image 2 yourself.

CRITICAL — do NOT anchor on the mockup. NEVER copy a value from sim_report (or
sim_details) into real_value / real_details. If the mockup says the logo is
centered at 50% and 5x6 cm, that tells you NOTHING about the real product — look
at Image 2 and report what is actually there (it may be smaller, off to one
side, a different layout). A real_value that merely echoes the sim_value is a
bug; describe what you genuinely observe in Image 2.

For EACH criterion in sim_report: locate it in Image 2, decide if it matches.
Additionally: identify criteria visible on the real product (Image 2) that were
NOT in sim_report (extras).

## Strict rules

1. Respond with a SINGLE valid JSON object, no prose.
2. All human-readable field values in Romanian (`criterion`, `sim_value`,
   `real_value`, `note`, `differences`, `details`, `real_overall`). EXCEPTION:
   keep `match_type` and `confidence` as the exact English enum tokens listed
   in rules 5-6 — the application matches on them programmatically.
3. One row per sim criterion (in order), then rows for extras found only on the
   real product.
4. `match: true` ONLY when both `sim_value` and `real_value` are non-null AND
   describe the same thing (semantically — "navy blue" and "dark navy" match;
   "navy blue" and "red" do not).
4a. POSITION AND SIZE ARE PART OF SAMENESS. For any placed or sized element
   (logo, graphic, print, text, badge, pocket, embroidery — anything that has a
   location or size on the garment), an element is NOT a match unless it also
   sits in the same place on the garment AND has the same relative size. A logo
   that is centered on the chest in the mockup but on the left chest on the real
   product is NOT a match. A logo (or text) that is clearly larger or smaller
   relative to the garment is NOT a match. In these cases set `match: false`,
   `match_type: "partial"`, and state the exact placement/size discrepancy in
   `differences` and `note`. Use `sim_details.position_normalized` and
   `sim_details.size_estimate_cm` as the mockup reference when present.
4b. Judge position and size RELATIVE TO GARMENT LANDMARKS — the collar, the
   shoulder seams, the vertical center line of the body, the chest width — NOT
   relative to the image frame. Ignore apparent shifts that are only artifacts
   of camera angle, perspective, folds, or how the garment is laid out or worn;
   flag ONLY differences that are intrinsic to how the design is printed or
   applied. When in doubt about whether a shift is intrinsic or just perspective,
   do not claim an exact match — use `partial` and explain the uncertainty.
4c. COLOR SHADE IS PART OF SAMENESS. If the real product reads as a visibly
   different shade or tone than the mockup (e.g. mint green vs sage green, navy
   vs royal blue) — even when both are loosely "a kind of green/blue" — that is
   `partial`. Record the shade you actually observe in real_value and the gap in
   differences. Do NOT dismiss a visible color difference as photo lighting or
   "calibration"; report what you see. Reserve `exact`/`semantic` for colors
   that genuinely read as the SAME shade, where only a faint lighting shift
   separates them.
4d. ORIENTATION, SIDE, AND MIRRORING. For every logo, graphic, or asymmetric
   mark, check explicitly: (a) Is it MIRRORED / flipped left-right compared to
   the mockup? For an asymmetric mark like a Nike swoosh, which way does the tip
   point and which way does the tail sweep? (b) Which side of the chest does it
   sit on — the wearer's left or right? A mirrored, rotated, or wrong-side logo
   is a real manufacturing defect → `partial`, never a match. State the
   orientation and side you observe in real_value.
4e. FIT / SILHOUETTE. A clearly different garment cut (e.g. slim/regular vs
   oversized) is `partial`, not a match — describe the real fit you observe.
5. `match_type` is one of: exact, semantic, partial, missing_in_real, extra_on_real.
   Use `partial` when the element is the same kind/content but differs in a
   real attribute — most importantly placement or relative size (rules 4a/4b),
   but also a meaningful color, shape, or finishing difference. `partial` always
   implies `match: false`.
6. `confidence` is one of: high, medium, low.
7. NEVER claim match: true for something you cannot see in the real photo.
   If a criterion is in sim but you cannot see it (back of product, occluded,
   out of frame), set real_value: null, match: false,
   match_type: "missing_in_real", confidence: "low", and explain in note.
8. note is mandatory — one sentence justifying the decision.
9. differences lists specific visual discrepancies, empty list when match is exact.
   Any placement or relative-size difference (rules 4a/4b) MUST appear here, not
   only in note.
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
    sim_report: dict,
    sim_b64: str,
    sim_media_type: str,
    real_b64: str,
    real_media_type: str,
    real_filename: str,
) -> tuple[str, list[dict]]:
    """Return (system_prompt, messages) for the comparison LLM call.

    Sends BOTH images — the mockup (Image 1) and the real product photo
    (Image 2) — so the model compares them visually instead of anchoring on the
    sim_report text and echoing the mockup's values.
    """
    sim_json = json.dumps(sim_report, indent=2, ensure_ascii=False)
    user_text = (
        f"The real product photo filename is {real_filename!r}. Use it verbatim "
        f"in the `real_image` field. Below is the mockup analysis (sim_report) — "
        f"a checklist only, NOT ground truth about the real product:\n\n"
        f"```json\n{sim_json}\n```\n\n"
        f"Return the JSON described in the system prompt."
    )

    def _image_block(media_type: str, data: str) -> dict:
        return {
            "type": "image",
            "source": {"type": "base64", "media_type": media_type, "data": data},
        }

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": "Image 1 — MOCKUP (the 2D design):"},
                _image_block(sim_media_type, sim_b64),
                {"type": "text", "text": "Image 2 — REAL product photo:"},
                _image_block(real_media_type, real_b64),
                {"type": "text", "text": user_text},
            ],
        }
    ]
    return COMPARE_PROMPT, messages


_MATCH_TYPES = {"exact", "semantic", "partial", "missing_in_real", "extra_on_real"}
_CONFIDENCES = {"high", "medium", "low"}


def _summarize(rows: list[dict]) -> dict:
    """Build the summary block from rows. `match` is treated as the source of
    truth (it is itself derived from match_type), so callers can mutate rows —
    e.g. downgrade a mirrored logo to `partial` — and re-summarize."""
    by_match_type = {mt: 0 for mt in _MATCH_TYPES}
    by_confidence = {c: 0 for c in _CONFIDENCES}
    for r in rows:
        by_match_type[r["match_type"]] += 1
        if r.get("confidence") in by_confidence:
            by_confidence[r["confidence"]] += 1
    matched = sum(1 for r in rows if r["match"] is True)
    return {
        "total": len(rows),
        "matched": matched,
        "mismatched": len(rows) - matched,
        "by_match_type": by_match_type,
        "by_confidence": by_confidence,
    }


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
        # `match` is a pure function of `match_type`: only exact/semantic
        # equivalence counts as a match. The LLM frequently returns match=true
        # alongside match_type="partial" (e.g. a logo that is present but
        # mispositioned or resized), which would wrongly inflate the matched
        # count and show a green tick. Derive it deterministically — same
        # rationale as recomputing the summary below — rather than trusting the
        # LLM's boolean.
        row["match"] = row["match_type"] in ("exact", "semantic")

        sim_val = row.get("sim_value")
        real_val = row.get("real_value")
        if row["match"] and (sim_val is None or real_val is None):
            raise ValueError(
                f"row {i}: match_type {row['match_type']!r} requires both "
                f"sim_value and real_value to be non-null"
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
    summary = _summarize(rows)
    llm_summary = data.get("summary")
    if isinstance(llm_summary, dict) and (
        llm_summary.get("total") != summary["total"]
        or llm_summary.get("matched") != summary["matched"]
    ):
        logger.info(
            "compare summary diverged from rows (LLM: total=%s matched=%s; "
            "actual: total=%s matched=%s) — recomputed",
            llm_summary.get("total"), llm_summary.get("matched"),
            summary["total"], summary["matched"],
        )
    data["summary"] = summary
    return data


# ---- Logo orientation / mirroring sub-check -------------------------------
# The main compare model reliably misses left-right mirroring of a logo (a known
# vision-model weakness). We isolate the question: crop and enlarge the logo from
# both images and ask one focused call ONLY about orientation. The mirror is
# obvious once the mark is enlarged side by side.

ORIENTATION_PROMPT = """You inspect logos/graphics for ONE thing: left-right ORIENTATION.

For each logo you receive two enlarged crops — the MOCKUP version and the REAL
version. Decide whether the REAL logo is MIRRORED (horizontally flipped) relative
to the mockup.

Reason explicitly about which way asymmetric parts point. For a Nike swoosh: does
the sharp tip point up to the LEFT or up to the RIGHT, and on which side is the
thick rounded end? For text: does it read normally or backwards? If the real
version is the left-right mirror image of the mockup, it is mirrored.

Ignore color, size, position, fabric, lighting and background — ONLY orientation.

Respond with a SINGLE JSON object, no prose:
{ "logos": [ { "label": "<the logo label given>", "mirrored": true | false,
              "mockup_points": "<direction in mockup, Romanian>",
              "real_points": "<direction in real, Romanian>",
              "note": "<one sentence, Romanian>" } ] }
Keep the keys and booleans exactly as shown; all human-readable text in Romanian."""


def _logo_criteria(sim_report: dict) -> list[dict]:
    """Pick sim criteria that are placed graphics/logos worth an orientation
    check — they have a normalized position and look like a mark, not a fabric
    property."""
    out = []
    for c in sim_report.get("criteria", []):
        if not isinstance(c, dict):
            continue
        d = c.get("details") or {}
        pos = d.get("position_normalized")
        if not (isinstance(pos, dict) and "x_pct" in pos and "y_pct" in pos):
            continue
        hay = f"{c.get('id', '')} {c.get('label', '')}".lower()
        looks_graphic = bool(d.get("shape")) or any(
            k in hay for k in ("logo", "grafic", "graphic", "swoosh", "emblem",
                               "sigl", "print", "imprim", "copac", "text")
        )
        if looks_graphic:
            out.append(c)
    return out


def _crop_logo_b64(path: Path, x_pct: float, y_pct: float, zoom: int = 3) -> str:
    """Return a base64 PNG of an enlarged crop centered on (x_pct, y_pct). The
    box is generous so the logo stays in frame even when the real product is
    framed differently from the mockup."""
    from PIL import Image

    im = Image.open(path).convert("RGB")
    w, h = im.size
    cx, cy = w * x_pct / 100.0, h * y_pct / 100.0
    bw, bh = w * 0.34, h * 0.24
    box = (
        max(0, int(cx - bw / 2)), max(0, int(cy - bh / 2)),
        min(w, int(cx + bw / 2)), min(h, int(cy + bh / 2)),
    )
    crop = im.crop(box)
    crop = crop.resize((max(1, crop.width * zoom), max(1, crop.height * zoom)))
    buf = io.BytesIO()
    crop.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def build_orientation_messages(
    logos: list[dict], sim_path: Path, real_path: Path
) -> tuple[str, list[dict]]:
    """Build the focused orientation call: per logo, an enlarged mockup crop and
    real crop, labeled. `logos` are sim criteria (each with a position)."""
    content: list[dict] = []
    for c in logos:
        pos = c["details"]["position_normalized"]
        x, y = pos["x_pct"], pos["y_pct"]
        label = c.get("label") or c.get("id")
        content.append({"type": "text", "text": f"Logo: {label!r} — MOCKUP:"})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png",
                       "data": _crop_logo_b64(sim_path, x, y)},
        })
        content.append({"type": "text", "text": f"Logo: {label!r} — REAL:"})
        content.append({
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png",
                       "data": _crop_logo_b64(real_path, x, y)},
        })
    content.append({"type": "text", "text": (
        "For each logo above decide if the REAL crop is mirrored vs the MOCKUP "
        "crop. Return the JSON described in the system prompt."
    )})
    return ORIENTATION_PROMPT, [{"role": "user", "content": content}]


def parse_orientation_response(text: str) -> dict:
    """Return {label_lower: mirrored_bool}. Lenient: anything unparseable yields
    an empty dict so the sub-check can never break the main report."""
    try:
        data = _extract_json(text)
    except ValueError:
        return {}
    if not isinstance(data, dict):
        return {}
    result: dict[str, bool] = {}
    for item in (data.get("logos") or []):
        if isinstance(item, dict) and item.get("label") is not None:
            result[str(item["label"]).strip().lower()] = bool(item.get("mirrored"))
    return result


def detect_mirrored_logos(
    sim_report: dict, sim_path: Path, real_path: Path,
    model: str = "claude-sonnet-4-6",
) -> dict:
    """Focused sub-check: which logos are mirrored on the real product. Returns
    {label_lower: True} for mirrored logos. Never raises — any failure logs and
    returns {}, so the main report is unaffected."""
    try:
        logos = _logo_criteria(sim_report)
        if not logos:
            return {}
        system, messages = build_orientation_messages(logos, sim_path, real_path)
        raw = call_llm(system, messages, model=model, max_tokens=1024)
        verdicts = parse_orientation_response(raw)
        return {label: True for label, m in verdicts.items() if m}
    except Exception as e:  # pragma: no cover - defensive, exercised live
        logger.warning("logo orientation sub-check failed: %s", e)
        return {}


def apply_mirror_downgrades(report: dict, mirrored: dict) -> dict:
    """Downgrade compare rows whose logo is mirrored to `partial` and recompute
    the summary. Matches a row to a mirrored label by normalized equality or
    containment. Mutates and returns `report`."""
    if not mirrored:
        return report
    for row in report.get("rows", []):
        crit = str(row.get("criterion", "")).strip().lower()
        if not crit:
            continue
        hit = any(
            crit == label or label in crit or crit in label
            for label in mirrored
        )
        if hit and row.get("match_type") in ("exact", "semantic"):
            row["match_type"] = "partial"
            row["match"] = False
            diffs = row.get("differences") or []
            diffs.append("Logo oglindit orizontal (stânga-dreapta) față de mockup.")
            row["differences"] = diffs
            note = (row.get("note") or "").strip()
            row["note"] = (note + " Logoul este oglindit față de mockup.").strip()
    report["summary"] = _summarize(report["rows"])
    return report


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
    # Strip whitespace: httpx/h11 rejects headers with leading/trailing
    # whitespace as LocalProtocolError, which the Anthropic SDK surfaces as
    # the deeply misleading "Connection error." Defensive trim avoids it.
    client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"].strip())
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
    sim_report: dict,
    sim_path: Path,
    real_path: Path,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 8192,
) -> dict:
    """Read both images → call LLM with sim_report → parse → return compare_report.

    Sends the mockup AND the real photo so the model compares them visually
    rather than echoing the sim_report. One retry with a corrective hint if
    parse fails the first time. 8192 covers ~17-20 criteria; products with 30+
    criteria may need a higher cap.
    """
    sim_media_type, sim_b64 = encode_image(sim_path)
    real_media_type, real_b64 = encode_image(real_path)
    system, messages = build_compare_messages(
        sim_report, sim_b64, sim_media_type, real_b64, real_media_type,
        real_path.name,
    )
    raw = call_llm(system, messages, model=model, max_tokens=max_tokens)
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
        raw = call_llm(system, retry_messages, model=model, max_tokens=max_tokens)
        report = parse_compare_response(raw)  # raises if still bad

    # Focused follow-up: the main model misses left-right logo mirroring, so we
    # ask a dedicated call on enlarged logo crops and downgrade mirrored logos.
    mirrored = detect_mirrored_logos(sim_report, sim_path, real_path, model=model)
    report = apply_mirror_downgrades(report, mirrored)

    report["real_image"] = real_path.name
    return report


def process_pair(
    base: str,
    sim_path: Path,
    real_path: Path,
    output_dir: Path,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 8192,
) -> dict:
    """Full pipeline for one pair. Saves sim.json + compare.json under
    output_dir/<base>/. Returns the compare report. `max_tokens` caps the
    compare call only; sim analysis uses the call_llm default (4096)."""
    pair_dir = output_dir / base
    pair_dir.mkdir(parents=True, exist_ok=True)

    sim_report = analyze_sim(sim_path, model=model)
    (pair_dir / "sim.json").write_text(
        json.dumps(sim_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    compare_report = compare_real(
        sim_report, sim_path, real_path, model=model, max_tokens=max_tokens
    )
    compare_report["pair"] = base  # canonical, overrides whatever LLM wrote
    (pair_dir / "compare.json").write_text(
        json.dumps(compare_report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return compare_report
