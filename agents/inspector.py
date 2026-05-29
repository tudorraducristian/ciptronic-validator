import base64
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from schemas import loader


PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "inspector.md"


Incredere = Literal["scăzut", "mediu", "ridicat"]
ALLOWED_INCREDERE = {"scăzut", "mediu", "ridicat"}


@dataclass
class ValidationItem:
    camp: str
    valoare_asteptata: object
    valoare_observata: object | None
    incredere: Incredere | None
    motiv: str


@dataclass
class ValidationReport:
    conform: list[ValidationItem] = field(default_factory=list)
    neconform: list[ValidationItem] = field(default_factory=list)
    nevizibil: list[ValidationItem] = field(default_factory=list)


def parse_report(text: str, schema: dict, spec: dict) -> ValidationReport:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Răspunsul Inspector nu e JSON valid: {e}") from e

    for key in ("conform", "neconform", "nevizibil"):
        if key not in data:
            raise ValueError(f"Lipsește lista '{key}' din răspuns")
        if not isinstance(data[key], list):
            raise ValueError(f"'{key}' trebuie să fie listă")

    conform = [_parse_item(i, in_nevizibil=False) for i in data["conform"]]
    neconform = [_parse_item(i, in_nevizibil=False) for i in data["neconform"]]
    nevizibil = [_parse_item(i, in_nevizibil=True) for i in data["nevizibil"]]

    applicable = set(loader.applicable_leaf_keys(schema, spec))
    reported = {i.camp for i in conform} | {i.camp for i in neconform} | {i.camp for i in nevizibil}
    missing = applicable - reported
    extra = reported - applicable
    if missing:
        raise ValueError(f"Câmpuri lipsă din raport: {sorted(missing)}")
    if extra:
        raise ValueError(f"Câmpuri neașteptate în raport: {sorted(extra)}")

    total = len(conform) + len(neconform) + len(nevizibil)
    if total != len(applicable):
        raise ValueError(f"Fiecare câmp trebuie raportat exact o dată. Raportate: {total}, așteptate: {len(applicable)}")

    return ValidationReport(conform=conform, neconform=neconform, nevizibil=nevizibil)


def _parse_item(raw: dict, in_nevizibil: bool) -> ValidationItem:
    if "camp" not in raw or "valoare_asteptata" not in raw:
        raise ValueError(f"Item incomplet: {raw}")
    if not raw.get("motiv"):
        raise ValueError(f"motiv lipsă pentru {raw.get('camp')}")

    if in_nevizibil:
        return ValidationItem(
            camp=raw["camp"], valoare_asteptata=raw["valoare_asteptata"],
            valoare_observata=None, incredere=None, motiv=raw["motiv"],
        )

    incredere = raw.get("incredere")
    if incredere not in ALLOWED_INCREDERE:
        raise ValueError(f"incredere invalidă pentru {raw['camp']}: '{incredere}' (permise: {sorted(ALLOWED_INCREDERE)})")
    if "valoare_observata" not in raw:
        raise ValueError(f"valoare_observata lipsă pentru {raw['camp']}")

    return ValidationItem(
        camp=raw["camp"], valoare_asteptata=raw["valoare_asteptata"],
        valoare_observata=raw["valoare_observata"], incredere=incredere,
        motiv=raw["motiv"],
    )


def build_messages(spec: dict, image_paths: list[str]) -> tuple[str, list[dict]]:
    system = PROMPT_PATH.read_text(encoding="utf-8")

    blocks: list[dict] = []
    for path in image_paths:
        data = Path(path).read_bytes()
        b64 = base64.standard_b64encode(data).decode("ascii")
        blocks.append({
            "type": "image",
            "source": {"type": "base64", "media_type": _media_type_for(path), "data": b64},
        })

    spec_text = json.dumps(spec, ensure_ascii=False, indent=2)
    text = (
        f"Specificația produsului (JSON):\n```json\n{spec_text}\n```\n\n"
        f"Pozele atașate: {len(image_paths)} (numerotate 1..{len(image_paths)}).\n\n"
        f"Analizează câmp cu câmp și emite raportul JSON."
    )
    blocks.append({"type": "text", "text": text})
    return system, blocks


def _media_type_for(path: str) -> str:
    p = path.lower()
    if p.endswith(".png"):
        return "image/png"
    if p.endswith(".gif"):
        return "image/gif"
    if p.endswith(".webp"):
        return "image/webp"
    return "image/jpeg"
