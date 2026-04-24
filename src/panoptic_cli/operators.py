"""Lecture de la table operators (schéma v0.3).

Expose :
  - OperatorRow           : dataclass compacte d'un opérateur
  - OperatorSignal        : un signal actionnarial (D1-D7)
  - load_operators_for_sirens(db, sirens) : opérateurs liés à une liste de SIREN
  - load_all_operators(db, limit, filters) : tous les opérateurs (commande dédiée)
  - is_operator_in_alarm(op)          : helper pour déclencher 3AYNE
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


SIGNAL_ALARM_KINDS = {"D3_rachat_recent", "D7_cascade_offshore"}
SIGNAL_LABELS = {
    "D1_controle_etranger":    "contrôle étranger",
    "D2_fonds_infrastructure": "fonds d'infrastructure",
    "D3_rachat_recent":        "rachat récent",
    "D4_empreinte_massive":    "empreinte massive",
    "D5_micro_capital":        "micro-capital sur gros projet",
    "D6_opacite_be":           "bénéficiaires non déclarés",
    "D7_cascade_offshore":     "cascade via juridiction offshore",
}


@dataclass
class OperatorSignal:
    kind: str
    score: int
    title: str
    detail: str
    source: str
    is_alarm: bool


@dataclass
class OperatorRow:
    siren: str
    canonical_name: str
    denomination_rne: str | None
    n_subsidiaries_rne: int           # filiales présidées directement par la mère
    n_subsidiaries_rne_group: int     # filiales via le groupe étendu (holdings inclus)
    president_current: str | None
    president_is_legal: bool
    ultimate_country: str
    max_signal_score: int
    signals: list[OperatorSignal] = field(default_factory=list)

    @property
    def is_alarm(self) -> bool:
        return any(s.is_alarm for s in self.signals)

    @property
    def country_label(self) -> str:
        # juridictions fréquentes → libellé humain
        return {
            "FRA": "France", "IRL": "Irlande", "ESP": "Espagne",
            "DEU": "Allemagne", "CHE": "Suisse", "LUX": "Luxembourg",
            "NLD": "Pays-Bas", "ITA": "Italie", "GBR": "Royaume-Uni",
            "USA": "États-Unis", "CAN": "Canada",
        }.get(self.ultimate_country, self.ultimate_country)


def _parse_signals(signals_json: str | None) -> list[OperatorSignal]:
    if not signals_json:
        return []
    try:
        data = json.loads(signals_json)
    except json.JSONDecodeError:
        return []
    return [
        OperatorSignal(
            kind=s.get("kind", ""),
            score=int(s.get("score", 0)),
            title=s.get("title", ""),
            detail=s.get("detail", ""),
            source=s.get("source", ""),
            is_alarm=bool(s.get("is_alarm", False)),
        )
        for s in data if isinstance(s, dict)
    ]


def _row_to_operator(r: sqlite3.Row) -> OperatorRow:
    keys = r.keys()
    # n_subsidiaries_rne_group absent sur v0.3 pre-B3, fallback sur n_subsidiaries_rne
    n_solo = r["n_subsidiaries_rne"] or 0
    n_group = (r["n_subsidiaries_rne_group"]
               if "n_subsidiaries_rne_group" in keys else None) or 0
    return OperatorRow(
        siren=r["siren"],
        canonical_name=r["canonical_name"],
        denomination_rne=r["denomination_rne"],
        n_subsidiaries_rne=n_solo,
        n_subsidiaries_rne_group=max(n_group, n_solo),
        president_current=r["president_current"],
        president_is_legal=bool(r["president_is_legal"]),
        ultimate_country=r["ultimate_country"] or "FRA",
        max_signal_score=r["max_signal_score"] or 0,
        signals=_parse_signals(r["signals_json"]),
    )


def _has_operators_table(conn: sqlite3.Connection) -> bool:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='operators'"
    ).fetchall()
    return bool(rows)


def load_operators_for_sirens(db_path: Path, sirens: set[str]) -> list[OperatorRow]:
    """Charge les opérateurs dont le SIREN est dans la liste donnée.

    Retourne une liste triée par max_signal_score desc. Retourne [] si la table
    operators n'existe pas (ex. DB v0.2 sans migration v0.3).
    """
    if not sirens:
        return []
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if not _has_operators_table(conn):
            return []
        placeholders = ",".join("?" * len(sirens))
        rows = conn.execute(
            f"SELECT * FROM operators WHERE siren IN ({placeholders}) "
            "ORDER BY max_signal_score DESC, n_subsidiaries_rne DESC",
            tuple(sirens),
        ).fetchall()
        return [_row_to_operator(r) for r in rows]
    finally:
        conn.close()


def load_all_operators(
    db_path: Path,
    *,
    limit: int | None = None,
    alarm_only: bool = False,
    foreign_only: bool = False,
    min_score: int = 0,
) -> list[OperatorRow]:
    """Charge tous les opérateurs avec filtres optionnels."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        if not _has_operators_table(conn):
            return []
        where = ["1=1"]
        params: list = []
        if alarm_only:
            where.append("max_signal_score >= 75")
        elif min_score > 0:
            where.append("max_signal_score >= ?")
            params.append(min_score)
        if foreign_only:
            where.append("ultimate_country != 'FRA'")
        sql = (
            f"SELECT * FROM operators WHERE {' AND '.join(where)} "
            "ORDER BY max_signal_score DESC, n_subsidiaries_rne DESC"
        )
        if limit:
            sql += f" LIMIT {int(limit)}"
        rows = conn.execute(sql, params).fetchall()
        return [_row_to_operator(r) for r in rows]
    finally:
        conn.close()


def any_operator_in_alarm(operators: list[OperatorRow]) -> bool:
    return any(op.is_alarm for op in operators)
