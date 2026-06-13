"""Smoke + behavior tests for name_norm.normalize_name."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "engine"))

import pytest

from name_norm import normalize_name


def test_returns_str():
    assert isinstance(normalize_name("LeBron James"), str)


def test_non_empty_for_real_name():
    assert normalize_name("LeBron James") != ""


def test_handles_accents_without_crashing():
    out = normalize_name("Nikola Jokić")
    assert isinstance(out, str) and out != ""


def test_empty_string_graceful():
    # Must not raise; result is a string.
    assert isinstance(normalize_name(""), str)


@pytest.mark.parametrize("name", ["Nikola Jokić", "LeBron James", ""])
def test_idempotent(name):
    once = normalize_name(name)
    assert normalize_name(once) == once


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
