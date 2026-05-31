from pathlib import Path

import pytest

from agents import inspector
from schemas import loader


FIXTURES = Path(__file__).parent.parent / "fixtures" / "llm_responses"


@pytest.fixture
def schema_tricou():
    return loader.load_schema("tricou")


@pytest.fixture
def spec_active_branding():
    return {
        "culoare_principala": "albastru navy", "material": "bumbac 100%",
        "croiala": "slim", "guler": "rotund", "maneci": "scurte",
        "branding": {
            "pozitie": "piept stâng", "tehnica": "serigrafie",
            "culori": ["alb"], "dimensiuni_aproximative": "10cm x 10cm",
        },
    }


@pytest.fixture
def spec_fara_branding():
    return {
        "culoare_principala": "albastru navy", "material": "bumbac 100%",
        "croiala": "slim", "guler": "rotund", "maneci": "scurte",
        "branding": {
            "pozitie": "fără branding", "tehnica": None,
            "culori": [], "dimensiuni_aproximative": None,
        },
    }


def test_parse_report_full_fixture_returns_dataclass(schema_tricou, spec_active_branding):
    raw = (FIXTURES / "inspector_full.json").read_text(encoding="utf-8")
    report = inspector.parse_report(raw, schema_tricou, spec_active_branding)
    assert len(report.conform) == 6
    assert len(report.neconform) == 1
    assert len(report.nevizibil) == 2

    all_camps = (
        [i.camp for i in report.conform]
        + [i.camp for i in report.neconform]
        + [i.camp for i in report.nevizibil]
    )
    assert len(all_camps) == 9 and len(set(all_camps)) == 9


def test_parse_report_active_branding_raises_when_field_missing(schema_tricou, spec_active_branding):
    raw = (FIXTURES / "inspector_missing_field.json").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="material"):
        inspector.parse_report(raw, schema_tricou, spec_active_branding)


def test_parse_report_fara_branding_expects_only_six_fields(schema_tricou, spec_fara_branding):
    raw = (FIXTURES / "inspector_fara_branding.json").read_text(encoding="utf-8")
    report = inspector.parse_report(raw, schema_tricou, spec_fara_branding)
    all_camps = (
        [i.camp for i in report.conform]
        + [i.camp for i in report.neconform]
        + [i.camp for i in report.nevizibil]
    )
    assert len(all_camps) == 6
    assert "branding.tehnica" not in all_camps
    assert "branding.culori" not in all_camps
    assert "branding.dimensiuni_aproximative" not in all_camps


def test_parse_report_invalid_incredere_raises(schema_tricou, spec_active_branding):
    bad = '{"conform": [{"camp": "culoare_principala", "valoare_asteptata": "navy", "valoare_observata": "navy", "incredere": "foarte ridicat", "motiv": "x"}], "neconform": [], "nevizibil": []}'
    with pytest.raises(ValueError, match="incredere"):
        inspector.parse_report(bad, schema_tricou, spec_active_branding)


def test_parse_report_strips_markdown_code_fences(schema_tricou, spec_active_branding):
    inner = (FIXTURES / "inspector_full.json").read_text(encoding="utf-8")
    fenced = f"```json\n{inner}\n```"
    report = inspector.parse_report(fenced, schema_tricou, spec_active_branding)
    assert len(report.conform) == 6
    assert len(report.neconform) == 1
    assert len(report.nevizibil) == 2


import base64


def _write_tiny_jpeg(path: Path) -> None:
    jpeg_b64 = (
        "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQ"
        "EBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB/8AAEQgAAQABAwEiAA"
        "IRAQMRAf/EABQAAQAAAAAAAAAAAAAAAAAAAAj/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8"
        "QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAh"
        "EDEQA/AL+AB//Z"
    )
    path.write_bytes(base64.b64decode(jpeg_b64))


def test_build_messages_encodes_images_as_base64(tmp_path, spec_active_branding):
    img_path = tmp_path / "img1.jpg"
    _write_tiny_jpeg(img_path)

    system, content_blocks = inspector.build_messages(
        spec=spec_active_branding,
        image_paths=[str(img_path)],
    )
    assert "inspectorul vizual Ciptronic" in system
    assert content_blocks[0]["type"] == "image"
    assert content_blocks[0]["source"]["type"] == "base64"
    assert content_blocks[0]["source"]["media_type"] == "image/jpeg"
    text_block = content_blocks[-1]
    assert text_block["type"] == "text"
    assert "culoare_principala" in text_block["text"]


def test_build_messages_handles_multiple_images(tmp_path, spec_active_branding):
    img1 = tmp_path / "img1.jpg"
    img2 = tmp_path / "img2.jpg"
    _write_tiny_jpeg(img1)
    _write_tiny_jpeg(img2)

    _, content_blocks = inspector.build_messages(
        spec=spec_active_branding, image_paths=[str(img1), str(img2)],
    )
    image_blocks = [b for b in content_blocks if b["type"] == "image"]
    assert len(image_blocks) == 2
