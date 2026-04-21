"""Résolution de la zone demandée par l'utilisateur.

Entrée : string libre tel que tapé par le militant :
  - "47"                      → département
  - "47250"                   → code postal
  - "47001"                   → code INSEE commune
  - "Allons"                  → nom de commune (fuzzy)
  - "Lot-et-Garonne"          → nom de département
  - "44.2,0.6+30km"           → latitude,longitude + rayon (pas MVP)

Sortie : un `ZoneFilter` avec les prédicats SQL à appliquer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ZoneFilter:
    kind: str                    # "dept" / "commune" / "cp" / "insee" / "all"
    label: str                   # ce qu'on affiche à l'utilisateur
    # prédicats SQL (column, value) ; plusieurs possibles, combinés en OR
    sql_predicates: list[tuple[str, str]]


_DEPT_NAMES: dict[str, str] = {
    # raccourci minimum pour le MVP, complété progressivement
    "lot-et-garonne": "47",
    "landes": "40",
    "vaucluse": "84",
    "gard": "30",
    "gers": "32",
    "aveyron": "12",
    "ardeche": "07",
    "alpes-de-haute-provence": "04",
    "puy-de-dome": "63",
    "tarn": "81",
    "ariege": "09",
    "herault": "34",
    "drome": "26",
    "correze": "19",
    "charente": "16",
    "charente-maritime": "17",
    "alpes-maritimes": "06",
    "manche": "50",
    "nievre": "58",
    "allier": "03",
}


def _normalize(s: str) -> str:
    try:
        from unidecode import unidecode
        s = unidecode(s)
    except ImportError:
        pass
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def resolve(raw: str) -> ZoneFilter:
    """Parse l'entrée utilisateur en ZoneFilter.

    Heuristiques (ordre important) :
      1. 2 chiffres ou "2A"/"2B"/"97X" → code département
      2. 5 chiffres commençant par un dept valide → code postal
      3. 5 chiffres (hors pattern CP) → code INSEE commune
      4. chaîne matchant un nom de département connu → dept
      5. sinon → nom de commune (recherche fuzzy côté search.py)
    """
    raw = raw.strip()
    if not raw:
        return ZoneFilter("all", "toute la France", [])

    # 1. département : 2 digits, "2A"/"2B", ou DOM 97X
    if re.fullmatch(r"\d{2}", raw) or raw.upper() in {"2A", "2B"}:
        code = raw.zfill(2).upper() if raw.upper() in {"2A", "2B"} else raw.zfill(2)
        return ZoneFilter(
            "dept",
            f"département {code}",
            [("code_dept", code)],
        )
    if re.fullmatch(r"97[1-6]", raw):
        return ZoneFilter(
            "dept",
            f"DOM {raw}",
            [("code_dept", raw)],
        )

    # 2. code postal / INSEE — 5 chiffres
    if re.fullmatch(r"\d{5}", raw):
        # heuristique : le dept est les 2 premiers digits (sauf DOM)
        dept = raw[:3] if raw.startswith("97") else raw[:2]
        return ZoneFilter(
            "cp_or_insee",
            f"{raw} (département {dept})",
            [
                ("code_commune", raw),  # INSEE
                ("code_dept", dept),     # CP → restreindre au dept
            ],
        )

    # 3. nom de département connu
    norm = _normalize(raw)
    if norm in _DEPT_NAMES:
        code = _DEPT_NAMES[norm]
        return ZoneFilter(
            "dept",
            f"{raw} ({code})",
            [("code_dept", code)],
        )

    # 4. commune — recherche fuzzy déléguée à search.py
    return ZoneFilter(
        "commune",
        f"commune « {raw} »",
        [("commune_fuzzy", raw)],
    )
