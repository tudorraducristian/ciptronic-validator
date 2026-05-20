"""Unit tests for image_matcher.engine pure functions."""
import logging
from pathlib import Path

import pytest

from image_matcher.engine import find_pairs


def _touch(path: Path) -> None:
    path.write_bytes(b"")


def test_find_pairs_basic(tmp_path):
    _touch(tmp_path / "tshirt_01_sim.png")
    _touch(tmp_path / "tshirt_01_real.jpg")
    _touch(tmp_path / "tshirt_02_sim.png")
    _touch(tmp_path / "tshirt_02_real.jpg")

    pairs = find_pairs(tmp_path)

    assert len(pairs) == 2
    bases = [base for base, _, _ in pairs]
    assert bases == ["tshirt_01", "tshirt_02"]
    assert pairs[0][1].name == "tshirt_01_sim.png"
    assert pairs[0][2].name == "tshirt_01_real.jpg"


def test_find_pairs_orphan_logs_warning(tmp_path, caplog):
    _touch(tmp_path / "tshirt_01_sim.png")
    _touch(tmp_path / "tshirt_02_real.jpg")

    with caplog.at_level(logging.WARNING):
        pairs = find_pairs(tmp_path)

    assert pairs == []
    log_text = caplog.text
    assert "tshirt_01" in log_text
    assert "tshirt_02" in log_text


def test_find_pairs_mixed_extensions(tmp_path):
    _touch(tmp_path / "a_sim.png")
    _touch(tmp_path / "a_real.jpg")
    _touch(tmp_path / "b_sim.webp")
    _touch(tmp_path / "b_real.jpeg")

    pairs = find_pairs(tmp_path)

    assert len(pairs) == 2
    assert pairs[0][0] == "a"
    assert pairs[1][0] == "b"


def test_find_pairs_empty_folder(tmp_path):
    assert find_pairs(tmp_path) == []


def test_find_pairs_ignores_unrelated_files(tmp_path):
    _touch(tmp_path / "a_sim.png")
    _touch(tmp_path / "a_real.jpg")
    _touch(tmp_path / "notes.txt")
    _touch(tmp_path / "random.png")

    pairs = find_pairs(tmp_path)

    assert len(pairs) == 1
    assert pairs[0][0] == "a"


from image_matcher.engine import encode_image


def test_encode_image_png(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"\x89PNG\r\n\x1a\nfakecontent")

    media_type, data = encode_image(path)

    assert media_type == "image/png"
    assert isinstance(data, str)
    assert len(data) > 0


def test_encode_image_jpeg(tmp_path):
    path = tmp_path / "a.jpg"
    path.write_bytes(b"\xff\xd8\xff\xe0fakecontent")

    media_type, _ = encode_image(path)

    assert media_type == "image/jpeg"


def test_encode_image_jpeg_alt_extension(tmp_path):
    path = tmp_path / "a.jpeg"
    path.write_bytes(b"\xff\xd8\xff\xe0fakecontent")

    media_type, _ = encode_image(path)

    assert media_type == "image/jpeg"


def test_encode_image_webp(tmp_path):
    path = tmp_path / "a.webp"
    path.write_bytes(b"RIFF\x00\x00\x00\x00WEBPfake")

    media_type, _ = encode_image(path)

    assert media_type == "image/webp"


def test_encode_image_unsupported_extension(tmp_path):
    path = tmp_path / "a.gif"
    path.write_bytes(b"fake")

    with pytest.raises(ValueError, match="unsupported image extension"):
        encode_image(path)


def test_encode_image_png_renamed_as_jpg(tmp_path):
    # Real-world: user renames .png to .jpg without re-exporting; magic bytes
    # win over the extension so Anthropic gets the correct media_type.
    path = tmp_path / "mislabeled.jpg"
    path.write_bytes(b"\x89PNG\r\n\x1a\nfakecontent")

    media_type, _ = encode_image(path)

    assert media_type == "image/png"


def test_encode_image_unrecognized_magic_bytes(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"not an image at all")

    with pytest.raises(ValueError, match="cannot detect image format"):
        encode_image(path)


def test_encode_image_too_large(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"\x00" * (5 * 1024 * 1024 + 1))

    with pytest.raises(ValueError, match="exceeds 5MB"):
        encode_image(path)


def test_encode_image_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        encode_image(tmp_path / "nope.png")


from image_matcher.engine import SIM_PROMPT, build_sim_messages


def test_sim_prompt_exists():
    assert isinstance(SIM_PROMPT, str)
    assert "JSON" in SIM_PROMPT
    assert "criteria" in SIM_PROMPT


def test_build_sim_messages_structure():
    system, messages = build_sim_messages("BASE64DATA", "image/png", "tshirt_01_sim.png")

    assert system == SIM_PROMPT
    assert isinstance(messages, list)
    assert len(messages) == 1
    assert messages[0]["role"] == "user"

    content = messages[0]["content"]
    image_blocks = [b for b in content if b["type"] == "image"]
    text_blocks = [b for b in content if b["type"] == "text"]

    assert len(image_blocks) == 1
    assert image_blocks[0]["source"]["type"] == "base64"
    assert image_blocks[0]["source"]["media_type"] == "image/png"
    assert image_blocks[0]["source"]["data"] == "BASE64DATA"

    assert len(text_blocks) == 1
    assert "tshirt_01_sim.png" in text_blocks[0]["text"]


import json
from image_matcher.engine import parse_sim_response


def _valid_sim_dict():
    return {
        "source_image": "x.png",
        "overall": {"description": "a t-shirt"},
        "criteria": [
            {
                "id": "main_color",
                "label": "main color",
                "value": "navy blue",
                "location": "body",
                "details": {},
            },
            {
                "id": "chest_logo",
                "label": "chest logo",
                "value": "white circle",
                "location": "left chest",
                "details": {"shape": "circle"},
            },
        ],
    }


def test_parse_sim_response_valid():
    report = parse_sim_response(json.dumps(_valid_sim_dict()))
    assert report["source_image"] == "x.png"
    assert len(report["criteria"]) == 2
    assert report["criteria"][0]["id"] == "main_color"


def test_parse_sim_response_strips_prose_wrapping():
    payload = "Here you go:\n" + json.dumps(_valid_sim_dict()) + "\nDone."
    # The LLM may pad despite instructions; parser should still extract.
    report = parse_sim_response(payload)
    assert report["criteria"][0]["id"] == "main_color"


def test_parse_sim_response_invalid_json():
    with pytest.raises(ValueError, match="not valid JSON"):
        parse_sim_response("totally not json")


def test_parse_sim_response_missing_criteria():
    d = _valid_sim_dict()
    del d["criteria"]
    with pytest.raises(ValueError, match="criteria"):
        parse_sim_response(json.dumps(d))


def test_parse_sim_response_missing_overall():
    d = _valid_sim_dict()
    del d["overall"]
    with pytest.raises(ValueError, match="overall"):
        parse_sim_response(json.dumps(d))


def test_parse_sim_response_empty_criteria():
    d = _valid_sim_dict()
    d["criteria"] = []
    with pytest.raises(ValueError, match="empty"):
        parse_sim_response(json.dumps(d))


def test_parse_sim_response_duplicate_id():
    d = _valid_sim_dict()
    d["criteria"][1]["id"] = "main_color"
    with pytest.raises(ValueError, match="duplicate"):
        parse_sim_response(json.dumps(d))


def test_parse_sim_response_invalid_id_format():
    d = _valid_sim_dict()
    d["criteria"][0]["id"] = "Main Color"
    with pytest.raises(ValueError, match="invalid id"):
        parse_sim_response(json.dumps(d))


def test_parse_sim_response_missing_criterion_field():
    d = _valid_sim_dict()
    del d["criteria"][0]["value"]
    with pytest.raises(ValueError, match="value"):
        parse_sim_response(json.dumps(d))


from image_matcher.engine import COMPARE_PROMPT, build_compare_messages


def test_compare_prompt_exists():
    assert isinstance(COMPARE_PROMPT, str)
    assert "match" in COMPARE_PROMPT
    assert "missing_in_real" in COMPARE_PROMPT


def test_build_compare_messages_structure():
    sim_report = _valid_sim_dict()
    system, messages = build_compare_messages(
        sim_report, "B64", "image/jpeg", "tshirt_01_real.jpg"
    )

    assert system == COMPARE_PROMPT
    assert len(messages) == 1
    content = messages[0]["content"]

    image_blocks = [b for b in content if b["type"] == "image"]
    text_blocks = [b for b in content if b["type"] == "text"]

    assert len(image_blocks) == 1
    assert image_blocks[0]["source"]["media_type"] == "image/jpeg"
    assert image_blocks[0]["source"]["data"] == "B64"

    assert len(text_blocks) == 1
    text = text_blocks[0]["text"]
    assert "tshirt_01_real.jpg" in text
    # The sim_report JSON should be embedded so the LLM sees it.
    assert "main_color" in text
    assert "chest_logo" in text


from image_matcher.engine import parse_compare_response


def _valid_compare_dict():
    return {
        "pair": "t01",
        "sim_image": "t01_sim.png",
        "real_image": "t01_real.jpg",
        "real_overall": {
            "view_angle": "front",
            "lighting": "daylight",
            "image_quality": "sharp",
            "obstructions": [],
        },
        "rows": [
            {
                "criterion": "main color",
                "sim_value": "navy",
                "real_value": "navy",
                "sim_details": {"color_hex_approx": "#1B2A4E"},
                "real_details": {"color_hex_approx": "#15233F"},
                "match": True,
                "match_type": "semantic",
                "confidence": "high",
                "differences": ["minor hex drift"],
                "note": "matches semantically",
            },
            {
                "criterion": "back text",
                "sim_value": "TEAM 2026",
                "real_value": None,
                "sim_details": {"text_content": "TEAM 2026"},
                "real_details": None,
                "match": False,
                "match_type": "missing_in_real",
                "confidence": "low",
                "differences": ["back not visible"],
                "note": "cannot verify back",
            },
        ],
        "summary": {
            "total": 2,
            "matched": 1,
            "mismatched": 1,
            "by_match_type": {
                "exact": 0,
                "semantic": 1,
                "partial": 0,
                "missing_in_real": 1,
                "extra_on_real": 0,
            },
            "by_confidence": {"high": 1, "medium": 0, "low": 1},
        },
    }


def test_parse_compare_response_valid():
    report = parse_compare_response(json.dumps(_valid_compare_dict()))
    assert len(report["rows"]) == 2
    assert report["summary"]["total"] == 2


def test_parse_compare_response_invalid_match_type():
    d = _valid_compare_dict()
    d["rows"][0]["match_type"] = "wrong"
    with pytest.raises(ValueError, match="match_type"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_invalid_confidence():
    d = _valid_compare_dict()
    d["rows"][0]["confidence"] = "definitely"
    with pytest.raises(ValueError, match="confidence"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_match_true_with_null():
    d = _valid_compare_dict()
    d["rows"][1]["match"] = True  # row has real_value None
    with pytest.raises(ValueError, match="match=true"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_missing_in_real_with_non_null_real():
    d = _valid_compare_dict()
    d["rows"][1]["real_value"] = "something"  # but match_type is missing_in_real
    with pytest.raises(ValueError, match="missing_in_real"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_summary_total_autofixed():
    d = _valid_compare_dict()
    d["summary"]["total"] = 5  # wrong; rows has 2
    report = parse_compare_response(json.dumps(d))
    assert report["summary"]["total"] == 2


def test_parse_compare_response_summary_counts_autofixed():
    d = _valid_compare_dict()
    d["summary"]["matched"] = 2  # wrong; only 1 row has match=true
    d["summary"]["mismatched"] = 2
    report = parse_compare_response(json.dumps(d))
    assert report["summary"]["matched"] == 1
    assert report["summary"]["mismatched"] == 1


def test_parse_compare_response_summary_by_match_type_autofixed():
    d = _valid_compare_dict()
    d["summary"]["by_match_type"] = {
        "exact": 99, "semantic": 0, "partial": 0,
        "missing_in_real": 0, "extra_on_real": 0,
    }
    report = parse_compare_response(json.dumps(d))
    bmt = report["summary"]["by_match_type"]
    assert bmt["semantic"] == 1
    assert bmt["missing_in_real"] == 1
    assert bmt["exact"] == 0


def test_parse_compare_response_summary_by_confidence_autofixed():
    d = _valid_compare_dict()
    d["summary"]["by_confidence"] = {"high": 99, "medium": 0, "low": 0}
    report = parse_compare_response(json.dumps(d))
    bc = report["summary"]["by_confidence"]
    assert bc["high"] == 1
    assert bc["medium"] == 0
    assert bc["low"] == 1


def test_parse_compare_response_missing_summary_built_from_rows():
    d = _valid_compare_dict()
    del d["summary"]
    report = parse_compare_response(json.dumps(d))
    assert report["summary"]["total"] == 2
    assert report["summary"]["matched"] == 1
    assert report["summary"]["mismatched"] == 1
    assert report["summary"]["by_match_type"]["semantic"] == 1
    assert report["summary"]["by_confidence"]["high"] == 1


def test_parse_compare_response_empty_note():
    d = _valid_compare_dict()
    d["rows"][0]["note"] = ""
    with pytest.raises(ValueError, match="note"):
        parse_compare_response(json.dumps(d))


def test_parse_compare_response_extra_on_real_with_non_null_sim():
    d = _valid_compare_dict()
    d["rows"].append(
        {
            "criterion": "stitch",
            "sim_value": "something",  # should be null for extra_on_real
            "real_value": "double stitch",
            "sim_details": None,
            "real_details": {"stitch_type": "double"},
            "match": False,
            "match_type": "extra_on_real",
            "confidence": "high",
            "differences": ["extra"],
            "note": "extra on real",
        }
    )
    d["summary"]["total"] = 3
    d["summary"]["mismatched"] = 2
    d["summary"]["by_match_type"]["extra_on_real"] = 1
    d["summary"]["by_confidence"]["high"] = 2
    with pytest.raises(ValueError, match="extra_on_real"):
        parse_compare_response(json.dumps(d))


from image_matcher.engine import render_table


def test_render_table_basic():
    report = _valid_compare_dict()
    out = render_table(report)
    assert "Criterion" in out
    assert "Sim" in out
    assert "Real" in out
    assert "Match" in out
    assert "main color" in out
    assert "✓" in out
    assert "✗" in out


def test_render_table_null_displays_dash():
    report = _valid_compare_dict()
    out = render_table(report)
    # row with real_value=None should show em-dash
    assert "—" in out


def test_render_table_truncates_long_values():
    report = _valid_compare_dict()
    report["rows"][0]["sim_value"] = "a" * 200
    out = render_table(report, width=80)
    assert "…" in out
    longest_line = max(len(line) for line in out.splitlines())
    assert longest_line <= 80
