import pytest

from schemas import loader


def test_load_schema_returns_dict():
    schema = loader.load_schema("tricou")
    assert schema["id"] == "tricou"
    assert schema["name_ro"] == "Tricou"
    assert isinstance(schema["fields"], list)


def test_load_schema_unknown_raises():
    with pytest.raises(FileNotFoundError):
        loader.load_schema("not-a-product")


def test_available_product_types_lists_tricou():
    types = loader.available_product_types()
    assert "tricou" in types


def test_leaf_keys_tricou_returns_nine_keys():
    schema = loader.load_schema("tricou")
    keys = loader.leaf_keys(schema)
    assert keys == [
        "culoare_principala", "material", "croiala", "guler", "maneci",
        "branding.pozitie", "branding.tehnica", "branding.culori",
        "branding.dimensiuni_aproximative",
    ]


def test_applicable_leaf_keys_with_active_branding():
    schema = loader.load_schema("tricou")
    state = {
        "culoare_principala": "navy", "material": "bumbac", "croiala": "slim",
        "guler": "rotund", "maneci": "scurte",
        "branding": {"pozitie": "piept stâng", "tehnica": "serigrafie",
                     "culori": ["alb"], "dimensiuni_aproximative": "10cm"}
    }
    keys = loader.applicable_leaf_keys(schema, state)
    assert len(keys) == 9


def test_applicable_leaf_keys_with_fara_branding():
    schema = loader.load_schema("tricou")
    state = {
        "culoare_principala": "navy", "material": "bumbac", "croiala": "slim",
        "guler": "rotund", "maneci": "scurte",
        "branding": {"pozitie": "fără branding", "tehnica": None,
                     "culori": [], "dimensiuni_aproximative": None}
    }
    keys = loader.applicable_leaf_keys(schema, state)
    assert keys == [
        "culoare_principala", "material", "croiala", "guler", "maneci",
        "branding.pozitie",
    ]


def test_empty_state_for_schema_initializes_branding_subobject():
    schema = loader.load_schema("tricou")
    state = loader.empty_state(schema)
    assert state["culoare_principala"] is None
    assert state["branding"]["pozitie"] is None
    assert state["branding"]["culori"] == []
