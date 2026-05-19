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


def test_encode_image_too_large(tmp_path):
    path = tmp_path / "a.png"
    path.write_bytes(b"\x00" * (5 * 1024 * 1024 + 1))

    with pytest.raises(ValueError, match="exceeds 5MB"):
        encode_image(path)


def test_encode_image_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        encode_image(tmp_path / "nope.png")
