"""Recherche SQLite : exécute un ZoneFilter sur la DB panoptic embarquée."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from rapidfuzz import fuzz
    _FUZZ_OK = True
except ImportError:
    _FUZZ_OK = False

from panoptic_cli.query import ZoneFilter

# La DB est embarquée dans le package. L'utilisateur peut la surcharger via
# la variable d'env PANOPTIC_DB (tests, dev).
import os  # noqa: E402


def _default_db_path() -> Path:
    # Cascade env → ~/.cache/panoptic (après `panoptic update`) → bundle
    from panoptic_cli.sync import effective_db_path
    return effective_db_path()


@dataclass
class ProjectRow:
    project_id: str
    name: str | None
    commune: str | None
    code_dept: str | None
    power_mwc: float | None
    surface_ha: float | None
    operator: str | None
    status: str | None
    year: int | None
    latitude: float | None
    longitude: float | None
    seen_in_sources: list[str] = field(default_factory=list)
    operator_canonical: str | None = None     # v0.3
    operator_siren: str | None = None         # v0.3


@dataclass
class ContestationRow:
    contestation_id: str
    commune: str | None
    code_dept: str | None
    type: str | None
    date_event: str | None
    acteur_nom: str | None
    issue_status: str | None
    latitude: float | None
    longitude: float | None
    summary: str | None


@dataclass
class SearchResult:
    zone_label: str
    projects: list[ProjectRow]
    contestations: list[ContestationRow]
    meta: dict[str, str]
    freshness_days: int | None  # âge max parmi les sources
    operators: list = field(default_factory=list)   # v0.3 : list[OperatorRow]


def _row_to_project(r: sqlite3.Row) -> ProjectRow:
    try:
        sources = json.loads(r["seen_in_sources"]) if r["seen_in_sources"] else []
    except (TypeError, json.JSONDecodeError):
        sources = []
    # v0.3 : operator_canonical + operator_siren (peut être absent si DB v0.2)
    keys = r.keys()
    op_canonical = r["operator_canonical"] if "operator_canonical" in keys else None
    op_siren = r["operator_siren"] if "operator_siren" in keys else None
    return ProjectRow(
        project_id=r["project_id"],
        name=r["name"],
        commune=r["commune"],
        code_dept=r["code_dept"],
        power_mwc=r["power_mwc"],
        surface_ha=r["surface_ha"],
        operator=r["operator_raw"],
        status=r["status"],
        year=r["year_commissioned"],
        latitude=r["latitude"],
        longitude=r["longitude"],
        seen_in_sources=sources,
        operator_canonical=op_canonical,
        operator_siren=op_siren,
    )


def _row_to_contestation(r: sqlite3.Row) -> ContestationRow:
    return ContestationRow(
        contestation_id=r["contestation_id"],
        commune=r["commune"],
        code_dept=r["code_dept"],
        type=r["type"],
        date_event=r["date_event"],
        acteur_nom=r["acteur_nom"],
        issue_status=r["issue_status"],
        latitude=r["latitude"],
        longitude=r["longitude"],
        summary=r["summary"],
    )


def _fetch_projects(conn: sqlite3.Connection, zf: ZoneFilter) -> list[ProjectRow]:
    if zf.kind == "all":
        rows = conn.execute("SELECT * FROM projects ORDER BY code_dept, commune").fetchall()
        return [_row_to_project(r) for r in rows]

    if zf.kind == "commune":
        # fuzzy : on charge tout le dept si un hint est possible, sinon tout
        raw_name = next((v for k, v in zf.sql_predicates if k == "commune_fuzzy"), None)
        rows = conn.execute("SELECT * FROM projects WHERE commune IS NOT NULL").fetchall()
        if raw_name and _FUZZ_OK:
            scored = [
                (fuzz.ratio(raw_name.lower(), (r["commune"] or "").lower()), r)
                for r in rows
            ]
            scored = [(s, r) for s, r in scored if s >= 80]
            scored.sort(key=lambda t: -t[0])
            return [_row_to_project(r) for _s, r in scored]
        return []

    if zf.kind == "cp_or_insee":
        insee = next((v for k, v in zf.sql_predicates if k == "code_commune"), None)
        dept = next((v for k, v in zf.sql_predicates if k == "code_dept"), None)
        rows = conn.execute(
            "SELECT * FROM projects WHERE code_commune = ? OR code_dept = ? ORDER BY commune",
            (insee, dept),
        ).fetchall()
        return [_row_to_project(r) for r in rows]

    # dept (défaut)
    dept = next((v for k, v in zf.sql_predicates if k == "code_dept"), None)
    rows = conn.execute(
        "SELECT * FROM projects WHERE code_dept = ? ORDER BY commune, name",
        (dept,),
    ).fetchall()
    return [_row_to_project(r) for r in rows]


def _fetch_contestations(conn: sqlite3.Connection, zf: ZoneFilter) -> list[ContestationRow]:
    if zf.kind == "all":
        rows = conn.execute(
            "SELECT * FROM contestations ORDER BY date_event DESC"
        ).fetchall()
        return [_row_to_contestation(r) for r in rows]
    if zf.kind == "dept":
        dept = next((v for k, v in zf.sql_predicates if k == "code_dept"), None)
        rows = conn.execute(
            "SELECT * FROM contestations WHERE code_dept = ? ORDER BY date_event DESC",
            (dept,),
        ).fetchall()
        return [_row_to_contestation(r) for r in rows]
    if zf.kind == "cp_or_insee":
        dept = next((v for k, v in zf.sql_predicates if k == "code_dept"), None)
        rows = conn.execute(
            "SELECT * FROM contestations WHERE code_dept = ? ORDER BY date_event DESC",
            (dept,),
        ).fetchall()
        return [_row_to_contestation(r) for r in rows]
    if zf.kind == "commune":
        raw_name = next((v for k, v in zf.sql_predicates if k == "commune_fuzzy"), None)
        all_rows = conn.execute("SELECT * FROM contestations").fetchall()
        if raw_name and _FUZZ_OK:
            out = []
            for r in all_rows:
                if r["commune"] and fuzz.ratio(raw_name.lower(), r["commune"].lower()) >= 80:
                    out.append(_row_to_contestation(r))
            return out
    return []


def _compute_freshness_days(meta: dict[str, str]) -> int | None:
    gen = meta.get("generated_at")
    if not gen:
        return None
    try:
        dt = datetime.fromisoformat(gen.replace("Z", "+00:00"))
    except ValueError:
        return None
    age = datetime.now(timezone.utc) - dt
    return age.days


def search(zf: ZoneFilter, db_path: Path | None = None) -> SearchResult:
    path = db_path or _default_db_path()
    if not path.exists():
        raise FileNotFoundError(
            f"DB panoptic introuvable : {path}\n"
            "Le binaire est peut-être corrompu, ou lance `panoptic update`."
        )
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        projects = _fetch_projects(conn, zf)
        contestations = _fetch_contestations(conn, zf)
        meta = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM meta").fetchall()}
    finally:
        conn.close()

    # v0.3 : charge les opérateurs uniques liés aux projets de la zone
    sirens_in_zone = {p.operator_siren for p in projects if p.operator_siren}
    from panoptic_cli.operators import load_operators_for_sirens
    operators = load_operators_for_sirens(path, sirens_in_zone)

    return SearchResult(
        zone_label=zf.label,
        projects=projects,
        contestations=contestations,
        meta=meta,
        freshness_days=_compute_freshness_days(meta),
        operators=operators,
    )
