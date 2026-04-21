"""Tests smoke : vérifient que l'import + la CLI de base fonctionnent.

Utilise la DB SQLite embarquée dans le package. Pas de réseau, pas de PG.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from panoptic_cli.query import resolve
from panoptic_cli.search import search
from panoptic_cli.signals import detect as detect_signals
from panoptic_cli.sync import CACHED_DB_PATH, effective_db_path, local_version


def _bundled_db() -> Path:
    path = Path(__file__).parent.parent / "src" / "panoptic_cli" / "data" / "panoptic.sqlite"
    assert path.exists(), f"DB embarquée manquante : {path}"
    return path


def test_bundled_db_has_schema() -> None:
    conn = sqlite3.connect(_bundled_db())
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert {"projects", "contestations", "project_sources", "meta"} <= tables


def test_bundled_db_has_version() -> None:
    v = local_version(_bundled_db())
    assert v is not None
    assert len(v) == len("YYYY-MM-DD")


def test_zone_resolver_dept() -> None:
    zf = resolve("47")
    assert zf.kind == "dept"
    assert any(col == "code_dept" and val == "47" for col, val in zf.sql_predicates)


def test_zone_resolver_commune_fuzzy() -> None:
    zf = resolve("Pujo-le-Plan")
    assert zf.kind == "commune"


def test_search_returns_results(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PANOPTIC_DB", str(_bundled_db()))
    result = search(resolve("47"))
    assert len(result.projects) >= 1
    assert result.meta.get("version") is not None


def test_signals_detect_without_crash(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PANOPTIC_DB", str(_bundled_db()))
    result = search(resolve("47"))
    signals = detect_signals(result, _bundled_db())
    # should produce something for 47 (GLHD paradox at least)
    assert isinstance(signals, list)


def test_effective_db_falls_back_to_bundle() -> None:
    # Sans cache user, la DB effective doit être celle du bundle.
    if CACHED_DB_PATH.exists():
        pytest.skip("cache user existe, skip")
    path = effective_db_path()
    assert path.exists()
