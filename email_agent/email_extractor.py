import json
from dataclasses import dataclass, field

from email_agent.gmail_client import EmailMessage
from schemas import loader


SYSTEM_PROMPT = """Ești un asistent care extrage cereri de produse personalizate din emailuri de business.

Emailurile sunt trimise de clienți care comandă produse textile personalizate.

Sarcina ta: analizează corpul emailului și extrage FIECARE tip de produs menționat ca o cerere separată.

Pentru fiecare cerere returnează un obiect JSON cu:
- "product_type": tipul de produs (folosește EXACT una din valorile din lista furnizată)
- "description": descrierea brută a acelui produs din email (1-2 propoziții)
- "prefilled_state": obiect cu câmpurile pe care le poți extrage cu CERTITUDINE din email,
  folosind EXACT cheile din schema furnizată

IMPORTANT:
- Nu inventa valori. Dacă un câmp nu e menționat explicit în email, NU îl include.
- Folosește EXACT cheile din schema — nu traduce, nu redenumi.
- Returnează un array JSON, chiar dacă e gol ([]).
- Răspunde EXCLUSIV cu JSON valid, fără text suplimentar."""


@dataclass
class ProductRequest:
    email_sender: str
    email_subject: str
    email_date: str
    product_type: str
    description: str
    prefilled_state: dict
    missing_fields: list[str] = field(default_factory=list)


def extract(message: EmailMessage, llm) -> list[ProductRequest]:
    available_types = loader.available_product_types()

    schemas_text = ""
    schemas_map = {}
    for ptype in available_types:
        schema = loader.load_schema(ptype)
        schemas_map[ptype] = schema
        schemas_text += f'\nSchema pentru "{ptype}":\n{_schema_to_text(schema)}\n'

    user_content = json.dumps({
        "tipuri_disponibile": available_types,
        "scheme": schemas_text,
        "expeditor": message.sender,
        "subiect": message.subject,
        "data": message.date,
        "corp_email": message.body_text[:3000],
    }, ensure_ascii=False)

    raw = llm.complete_text(system=SYSTEM_PROMPT, user=user_content)
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
