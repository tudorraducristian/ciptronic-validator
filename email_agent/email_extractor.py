import base64
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from email_agent.gmail_client import EmailMessage
from schemas import loader


class LLMClient(Protocol):
    def complete_text(self, system: str, user: str) -> str: ...
    def complete_vision(self, system: str, content_blocks: list[dict]) -> str: ...


_SYSTEM_PROMPT_BASE = """Ești un asistent care extrage cereri de produse personalizate din emailuri de business.

Emailurile sunt trimise de clienți care comandă produse textile personalizate.

Sarcina ta: analizează corpul emailului și extrage FIECARE tip de produs menționat ca o cerere separată.

Pentru fiecare cerere returnează un obiect JSON cu:
- "product_type": tipul de produs (folosește EXACT una din valorile din lista furnizată)
- "description": descrierea brută a acelui produs din email (1-2 propoziții)
- "prefilled_state": obiect cu câmpurile pe care le poți extrage cu CERTITUDINE din email,
  folosind EXACT cheile din schema furnizată

IMPORTANT:
- Nu inventa valori. Dacă un câmp nu e menționat explicit în email sau imagini, NU îl include.
- Folosește EXACT cheile din schema — nu traduce, nu redenumi.
- Returnează un array JSON, chiar dacă e gol ([]).
- Răspunde EXCLUSIV cu JSON valid, fără text suplimentar."""

_SYSTEM_PROMPT_WITH_IMAGES = _SYSTEM_PROMPT_BASE + """

Emailul conține imagini cu mockup-uri de produs. Folosește-le pentru a completa câmpurile vizuale: \
culoare_principala, branding.pozitie, branding.culori. \
Informațiile extrase din imagini au prioritate față de absența lor din text."""


@dataclass
class ProductRequest:
    email_sender: str
    email_subject: str
    email_date: str
    product_type: str
    description: str
    prefilled_state: dict
    missing_fields: list[str] = field(default_factory=list)


def _image_block(path: str) -> dict | None:
    try:
        data = base64.b64encode(Path(path).read_bytes()).decode()
    except OSError as exc:
        logging.warning("Imagine inaccesibilă, omisă: %s — %s", path, exc)
        return None
    # Always JPEG: _resize_image in gmail_client re-encodes every image to JPEG before saving
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": data},
    }


def extract(message: EmailMessage, llm: LLMClient) -> list[ProductRequest]:
    available_types = loader.available_product_types()

    schemas_text = ""
    schemas_map = {}
    for ptype in available_types:
        schema = loader.load_schema(ptype)
        schemas_map[ptype] = schema
        schemas_text += f'\nSchema pentru "{ptype}":\n{_schema_to_text(schema)}\n'

    user_content_dict = {
        "tipuri_disponibile": available_types,
        "scheme": schemas_text,
        "expeditor": message.sender,
        "subiect": message.subject,
        "data": message.date,
        "corp_email": message.body_text[:3000],
    }

    if message.image_paths:
        if message.other_attachment_names:
            user_content_dict["fisiere_atasate"] = message.other_attachment_names
        text_block = {"type": "text", "text": json.dumps(user_content_dict, ensure_ascii=False)}
        image_blocks = [b for p in message.image_paths if (b := _image_block(p)) is not None]
        raw = llm.complete_vision(
            system=_SYSTEM_PROMPT_WITH_IMAGES,
            content_blocks=[text_block] + image_blocks,
        )
    else:
        raw = llm.complete_text(
            system=_SYSTEM_PROMPT_BASE,
            user=json.dumps(user_content_dict, ensure_ascii=False),
        )

    items = _parse_json_array(raw)

    result = []
    for item in items:
        ptype = item.get("product_type")
        if ptype not in available_types:
            continue
        prefilled = item.get("prefilled_state", {})
        schema = schemas_map[ptype]
        missing = _compute_missing_fields(schema, prefilled)
        result.append(ProductRequest(
            email_sender=message.sender,
            email_subject=message.subject,
            email_date=message.date,
            product_type=ptype,
            description=item.get("description", ""),
            prefilled_state=prefilled,
            missing_fields=missing,
        ))
    return result


def _schema_to_text(schema: dict) -> str:
    lines = []
    for f in schema["fields"]:
        if f.get("type") == "object":
            for sub in f["subfields"]:
                key = f"{f['key']}.{sub['key']}"
                hint = sub.get("hint", "")
                label = sub.get("label", key)
                lines.append(f"  {key:<45} — {label}{' (' + hint + ')' if hint else ''}")
        else:
            hint = f.get("hint", "")
            lines.append(f"  {f['key']:<45} — {f['label']}{' (' + hint + ')' if hint else ''}")
    return "\n".join(lines)


def _compute_missing_fields(schema: dict, prefilled_state: dict) -> list[str]:
    all_keys = loader.leaf_keys(schema)
    missing = []
    for dotted_key in all_keys:
        parts = dotted_key.split(".")
        val = prefilled_state
        for p in parts:
            if not isinstance(val, dict) or p not in val:
                missing.append(dotted_key)
                break
            val = val[p]
    return missing


def _parse_json_array(text: str) -> list:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1:
            return []
        return json.loads(text[start:end + 1])
