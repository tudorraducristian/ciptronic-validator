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
