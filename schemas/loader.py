import json
from pathlib import Path


SCHEMAS_DIR = Path(__file__).parent


def available_product_types() -> list[str]:
    return sorted(p.stem for p in SCHEMAS_DIR.glob("*.json"))


def load_schema(product_type: str) -> dict:
    path = SCHEMAS_DIR / f"{product_type}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def leaf_keys(schema: dict) -> list[str]:
    out: list[str] = []
    for field in schema["fields"]:
        if field.get("type") == "object":
            for sub in field["subfields"]:
                out.append(f"{field['key']}.{sub['key']}")
        else:
            out.append(field["key"])
    return out


def applicable_leaf_keys(schema: dict, state: dict) -> list[str]:
    out: list[str] = []
    for field in schema["fields"]:
        if field.get("type") == "object":
            parent_state = state.get(field["key"]) or {}
            none_marker = field.get("allow_none_value")
            first_sub_key = field["subfields"][0]["key"]
            first_sub_value = parent_state.get(first_sub_key)
            if none_marker is not None and first_sub_value == none_marker:
                out.append(f"{field['key']}.{first_sub_key}")
            else:
                for sub in field["subfields"]:
                    out.append(f"{field['key']}.{sub['key']}")
        else:
            out.append(field["key"])
    return out


def empty_state(schema: dict) -> dict:
    state: dict = {}
    for field in schema["fields"]:
        if field.get("type") == "object":
            state[field["key"]] = {}
            for sub in field["subfields"]:
                state[field["key"]][sub["key"]] = [] if sub.get("type") == "list" else None
        elif field.get("type") == "list":
            state[field["key"]] = []
        else:
            state[field["key"]] = None
    return state
