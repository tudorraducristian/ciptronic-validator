from pathlib import Path

import pytest

from agents import discovery
from schemas import loader


FIXTURES = Path(__file__).parent.parent / "fixtures" / "llm_responses"


@pytest.fixture
def schema_tricou():
    return loader.load_schema("tricou")


def test_parse_response_valid_round1(schema_tricou):
    raw = (FIXTURES / "discovery_round1.json").read_text(encoding="utf-8")
    step = discovery.parse_response(raw)
    assert step.done is False
    assert step.state["culoare_principala"] == "albastru navy"
    assert step.state["branding"]["pozitie"] == "piept stâng"
    assert len(step.intrebari) == 3
    ids = {q["id"] for q in step.intrebari}
    assert {"material", "croiala", "branding.tehnica"} == ids


def test_parse_response_done(schema_tricou):
    raw = (FIXTURES / "discovery_round2_done.json").read_text(encoding="utf-8")
    step = discovery.parse_response(raw)
    assert step.done is True
    assert step.intrebari == []
    assert step.state["material"] == "bumbac 100%"


def test_parse_response_invalid_raises():
    raw = (FIXTURES / "discovery_invalid.txt").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="JSON"):
        discovery.parse_response(raw)


def test_parse_response_strips_markdown_code_fences(schema_tricou):
    inner = (FIXTURES / "discovery_round1.json").read_text(encoding="utf-8")
    fenced = f"```json\n{inner}\n```"
    step = discovery.parse_response(fenced)
    assert step.done is False
    assert step.state["culoare_principala"] == "albastru navy"
    assert len(step.intrebari) == 3


def test_is_schema_complete_true_for_full_state(schema_tricou):
    state = {
        "culoare_principala": "navy", "material": "bumbac 100%",
        "croiala": "slim", "guler": "rotund", "maneci": "scurte",
        "branding": {"pozitie": "piept stâng", "tehnica": "serigrafie",
                     "culori": ["alb"], "dimensiuni_aproximative": "10cm x 10cm"}
    }
    complete, missing = discovery.is_schema_complete(schema_tricou, state)
    assert complete is True
    assert missing == []


def test_is_schema_complete_true_for_fara_branding(schema_tricou):
    state = {
        "culoare_principala": "navy", "material": "bumbac 100%",
        "croiala": "slim", "guler": "rotund", "maneci": "scurte",
        "branding": {"pozitie": "fără branding", "tehnica": None,
                     "culori": [], "dimensiuni_aproximative": None}
    }
    complete, missing = discovery.is_schema_complete(schema_tricou, state)
    assert complete is True
    assert missing == []


def test_is_schema_complete_false_with_missing_fields(schema_tricou):
    state = {
        "culoare_principala": "navy", "material": None,
        "croiala": "slim", "guler": "rotund", "maneci": "scurte",
        "branding": {"pozitie": "piept stâng", "tehnica": None,
                     "culori": [], "dimensiuni_aproximative": None}
    }
    complete, missing = discovery.is_schema_complete(schema_tricou, state)
    assert complete is False
    assert set(missing) == {"material", "branding.tehnica",
                            "branding.culori", "branding.dimensiuni_aproximative"}


def test_merge_answers_flat_key():
    state = {"material": None, "croiala": None}
    new_state = discovery.merge_answers(state, {"material": "bumbac 100%"})
    assert new_state["material"] == "bumbac 100%"
    assert new_state["croiala"] is None


def test_merge_answers_dotted_key():
    state = {"branding": {"pozitie": None, "tehnica": None,
                          "culori": [], "dimensiuni_aproximative": None}}
    new_state = discovery.merge_answers(state, {
        "branding.pozitie": "piept stâng",
        "branding.tehnica": "serigrafie",
    })
    assert new_state["branding"]["pozitie"] == "piept stâng"
    assert new_state["branding"]["tehnica"] == "serigrafie"


def test_merge_answers_returns_new_dict_without_mutating_input():
    state = {"material": None}
    new_state = discovery.merge_answers(state, {"material": "bumbac"})
    assert state["material"] is None
    assert new_state["material"] == "bumbac"


def test_build_messages_returns_system_and_user_strings(schema_tricou):
    system, user = discovery.build_messages(
        schema=schema_tricou,
        initial_description="tricou navy cu logo pe piept",
        state={"culoare_principala": "navy"},
        history=[{"round": 1, "questions": [], "answers": {}}],
    )
    assert isinstance(system, str) and len(system) > 100
    assert "Ești asistentul Ciptronic" in system

    import json as _json
    payload = _json.loads(user)
    assert payload["schema"]["id"] == "tricou"
    assert payload["initial_description"] == "tricou navy cu logo pe piept"
    assert payload["current_state"]["culoare_principala"] == "navy"
    assert payload["history"] == [{"round": 1, "questions": [], "answers": {}}]
