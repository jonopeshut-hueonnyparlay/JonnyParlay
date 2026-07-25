"""Tests for engine/secrets_config.py -- specifically EDGEMODEL_DB_PATH.

Covers:
    - the hardcoded fallback default is a well-formed EdgeModel projections.db
      path (not asserting it exists on disk -- that would make the test
      machine-dependent; existence/fail-soft behavior is covered separately
      by tests/test_edgemodel_adapter.py::test_missing_db_is_failsoft)
    - EDGEMODEL_DB_PATH env var, when set, overrides the fallback default
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = REPO_ROOT / "engine"
sys.path.insert(0, str(ENGINE_DIR))


def test_edgemodel_db_path_fallback_is_well_formed():
    import secrets_config
    fallback = secrets_config.EDGEMODEL_DB_PATH
    assert fallback, "EDGEMODEL_DB_PATH must not be blank"
    p = Path(fallback)
    assert p.name == "projections.db"
    assert p.parent.name == "data"
    assert "EdgeModel" in str(p)


def test_edgemodel_db_path_env_override(monkeypatch):
    monkeypatch.setenv("EDGEMODEL_DB_PATH", r"C:\somewhere\else\projections.db")
    if "secrets_config" in sys.modules:
        del sys.modules["secrets_config"]
    import secrets_config
    assert secrets_config.EDGEMODEL_DB_PATH == r"C:\somewhere\else\projections.db"


@pytest.fixture(autouse=True)
def _restore_secrets_config_after_mutation():
    """Force a fresh, unmutated secrets_config import for any test file that
    runs after this one in the same session."""
    yield
    sys.modules.pop("secrets_config", None)
