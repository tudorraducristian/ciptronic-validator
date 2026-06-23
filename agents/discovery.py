import copy
import json
from dataclasses import dataclass
from pathlib import Path

from schemas import loader


PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "discovery.md"


@dataclass
class DiscoveryStep:
    state: dict
    intrebari: list[dict]
    done: bool


def _extract_json(text: str) -> dict:
    """Try a direct parse; if it fails (e.g. markdown code fences or prose
    around the object), fall back to the outermost {...} block."""
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError(f"Răspunsul LLM nu e JSON valid: {text[:80]!r}")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"Răspunsul LLM nu e JSON valid: {e}") from e


def parse_response(text: str) -> DiscoveryStep:
    data = _extract_json(text)

    for key in ("state", "intrebari", "done"):
        if key not in data:
            raise ValueError(f"Lipsește cheia '{key}' din răspunsul LLM")

    if not isinstance(data["state"], dict):
        raise ValueError("Cheia 'state' trebuie să fie obiect")
    if not isinstance(data["intrebari"], list):
        raise ValueError("Cheia 'intrebari' trebuie să fie listă")
    if not isinstance(data["done"], bool):
        raise ValueError("Cheia 'done' trebuie să fie boolean")

    return DiscoveryStep(state=data["state"], intrebari=data["intrebari"], done=data["done"])


_RETRY_HINT = "\n\nRăspunde STRICT cu JSON valid, fără text suplimentar."


def request_step(llm, system: str, user: str) -> DiscoveryStep:
    """Cere un pas Discovery de la LLM și parsează-l. La eșec de parsare,
    reîncearcă O SINGURĂ dată cu un hint de JSON strict, apoi propagă ValueError.

    Contract din spec: o reîncercare cu hint, a doua eșuare → ridică."""
    raw = llm.complete_text(system=system, user=user)
    try:
        return parse_response(raw)
    except ValueError:
        raw = llm.complete_text(system=system, user=user + _RETRY_HINT)
        return parse_response(raw)


def is_schema_complete(schema: dict, state: dict) -> tuple[bool, list[str]]:
    applicable = loader.applicable_leaf_keys(schema, state)
    missing: list[str] = []
    for key in applicable:
        value = _read_dotted(state, key)
        if value is None or value == "" or value == []:
            missing.append(key)
    return (len(missing) == 0, missing)


def _read_dotted(state: dict, dotted_key: str):
    parts = dotted_key.split(".")
    cur = state
    for p in parts:
        if not isinstance(cur, dict) or p not in cur:
            return None
        cur = cur[p]
    return cur


def merge_answers(state: dict, answers: dict) -> dict:
    new_state = copy.deepcopy(state)
    for key, value in answers.items():
        _write_dotted(new_state, key, value)
    return new_state


def _write_dotted(state: dict, dotted_key: str, value) -> None:
    parts = dotted_key.split(".")
    cur = state
    for p in parts[:-1]:
        if p not in cur or not isinstance(cur[p], dict):
            cur[p] = {}
        cur = cur[p]
    cur[parts[-1]] = value


def build_messages(schema: dict, initial_description: str,
                   state: dict, history: list) -> tuple[str, str]:
    system = PROMPT_PATH.read_text(encoding="utf-8")
    user = json.dumps({
        "schema": schema,
        "initial_description": initial_description,
        "current_state": state,
        "history": history,
    }, ensure_ascii=False, indent=2)
    return system, user
