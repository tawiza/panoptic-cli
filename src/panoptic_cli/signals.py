"""Algorithme micro-signaux — cœur "puissant" de panoptic.

Trois familles, six détecteurs, un score 0-100 par signal.

A. Émergence (projets latents)
  A1  projet MRAe récent, pas encore dans ADEME/projets-env
  A2  opérateur en sprint (N projets récents >> moyenne)

B. Opposition naissante  (déclenche 3AYNE alarmé si signal ≥ ALARM_THRESHOLD)
  B1  contestation < 60j + projet actif dans ≤ 15 km ou même commune
  B2  département "ceinture de résistance" (taux opposition > 60 %)

C. Anomalies structurelles
  C1  paradoxe opérateur : part de marché ≥ 10 %, 0 contestation
  C2  divergence registres : même projet, écart surface/puissance > 15 %
  C3  opacité opérateur : name/operator_raw générique ou NULL sur projet actif

Pondération (tawiza, 2026-04-21) :
  P2 "opposition naissante" est la priorité alarme.
  Paradoxe GLHD reste très visible, mais "il n'urge pas" → score élevé sans déclencher alarme.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from panoptic_cli.search import ContestationRow, ProjectRow, SearchResult


# --- Scoring (choix éditorial, à affiner au retour terrain) ----------------

SIGNAL_WEIGHTS: dict[str, int] = {
    "B1_opposition_naissante": 75,   # déclencheur 3AYNE alarmé
    "C1_paradoxe_operateur":    80,  # plus visible mais pas alarme
    "A1_projet_latent_mrae":    65,
    "B2_ceinture_resistance":   55,
    "C2_divergence_registres":  50,
    "C3_opacite_operateur":     40,
    "A2_hausse_operateur":      40,
}

ALARM_THRESHOLD = 70  # 3AYNE alarmé si un signal >= ce score
_ALARM_KINDS = {"B1_opposition_naissante"}  # restreint P2 comme validé

# Fenêtres temporelles (jours)
WINDOW_RECENT = 60
WINDOW_LATENT_MRAE = 90
WINDOW_SURGE = 90
WINDOW_SURGE_BASELINE = 180  # baseline = fenêtre immédiatement avant

# Seuils thématiques
GEO_RADIUS_KM = 15.0
DIVERGENCE_RATIO = 0.15
MARKET_SHARE_PARADOX = 10.0  # pct
DEPT_OPPOSITION_RESISTANCE = 0.60
SURGE_MULTIPLIER = 3


# --- Modèles ----------------------------------------------------------------


@dataclass
class Signal:
    kind: str                       # ex. "B1_opposition_naissante"
    score: int                      # 0-100
    scope: str                      # "zone" / "project" / "operator" / "dept"
    title: str                      # ligne courte affichée
    detail: str = ""                # précision une ligne
    refs: list[str] = field(default_factory=list)  # projects / contestations concernés


@dataclass
class GlobalContext:
    """Pré-calculs globaux pour détecteurs non-locaux."""
    operator_power: dict[str, float] = field(default_factory=dict)
    total_power: float = 0.0
    operator_contestations: dict[str, int] = field(default_factory=dict)
    dept_projects: dict[str, int] = field(default_factory=dict)
    dept_contestations: dict[str, int] = field(default_factory=dict)


# --- Contexte global --------------------------------------------------------


def compute_global_context(db_path: Path) -> GlobalContext:
    """Scanne toute la SQLite pour les agrégats nécessaires aux signaux C et B2."""
    ctx = GlobalContext()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        # parts de marché puissance par opérateur canonical
        # (à défaut de canonical propre, on utilise operator_raw normalisé)
        for r in conn.execute(
            "SELECT operator_raw, power_mwc FROM projects WHERE power_mwc IS NOT NULL"
        ):
            op = _op_canon(r["operator_raw"])
            if not op:
                continue
            ctx.operator_power[op] = ctx.operator_power.get(op, 0.0) + float(r["power_mwc"])
            ctx.total_power += float(r["power_mwc"])

        # opérateurs apparaissant dans contestations (via match)
        for r in conn.execute(
            """
            SELECT p.operator_raw
            FROM project_contestation_match m
            JOIN projects p ON p.project_id = m.project_id
            """
        ):
            op = _op_canon(r["operator_raw"])
            if op:
                ctx.operator_contestations[op] = ctx.operator_contestations.get(op, 0) + 1

        # projets par dept (pour taux ceinture résistance)
        for r in conn.execute(
            "SELECT code_dept, COUNT(*) AS n FROM projects WHERE code_dept != '' GROUP BY code_dept"
        ):
            ctx.dept_projects[r["code_dept"]] = r["n"]

        # contestations par dept
        for r in conn.execute(
            "SELECT code_dept, COUNT(*) AS n FROM contestations WHERE code_dept IS NOT NULL GROUP BY code_dept"
        ):
            ctx.dept_contestations[r["code_dept"]] = r["n"]
    finally:
        conn.close()
    return ctx


def _op_canon(raw: str | None) -> str | None:
    if not raw:
        return None
    r = raw.strip()
    low = r.lower()
    if not r or low in {"—", "-", "inconnu", "projet", "sans nom", "na"}:
        return None
    # normalisation ultra-simple ; la vraie canonicalisation est côté to_sqlite.py
    return r.upper()


# --- Utilitaires temps / géo ------------------------------------------------


def _days_since(iso: str | None) -> int | None:
    if not iso:
        return None
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - dt).days


def _haversine(lat1: float | None, lon1: float | None,
               lat2: float | None, lon2: float | None) -> float | None:
    if None in (lat1, lon1, lat2, lon2):
        return None
    from math import radians, sin, cos, asin, sqrt
    R = 6371.0
    φ1, φ2 = radians(lat1), radians(lat2)
    dφ = radians(lat2 - lat1)
    dλ = radians(lon2 - lon1)
    a = sin(dφ / 2) ** 2 + cos(φ1) * cos(φ2) * sin(dλ / 2) ** 2
    return 2 * R * asin(sqrt(a))


# --- Détecteurs A (émergence) ----------------------------------------------


def _detect_A1_projet_latent_mrae(projects: Iterable[ProjectRow]) -> list[Signal]:
    out = []
    for p in projects:
        if p.seen_in_sources == ["mrae"] or (
            "mrae" in p.seen_in_sources
            and "ademe_agrivolt" not in p.seen_in_sources
            and "projets_env" not in p.seen_in_sources
        ):
            out.append(
                Signal(
                    kind="A1_projet_latent_mrae",
                    score=SIGNAL_WEIGHTS["A1_projet_latent_mrae"],
                    scope="project",
                    title=f"projet latent — {p.name or '(sans nom)'}",
                    detail=(
                        f"visible uniquement dans MRAe à "
                        f"{p.commune or '(commune ?)'} ({p.code_dept or '??'}) — "
                        f"pas encore dans registres ADEME / projets-environnement"
                    ),
                    refs=[p.project_id],
                )
            )
    return out


def _detect_A2_hausse_operateur(projects: Iterable[ProjectRow]) -> list[Signal]:
    # surveillé plus tard (nécessite `first_seen_at` par projet dans la zone).
    # Stub : désactivé en MVP pour éviter le bruit, réactiver quand first_seen_at
    # sera fiable dans toutes les sources.
    return []


# --- Détecteurs B (opposition) ---------------------------------------------


def _detect_B1_opposition_naissante(
    projects: list[ProjectRow],
    contestations: list[ContestationRow],
) -> list[Signal]:
    out = []
    for c in contestations:
        days = _days_since(c.date_event)
        if days is None or days > WINDOW_RECENT:
            continue
        # cherche projet actif dans commune / proche
        near = []
        for p in projects:
            if p.status in {"abandonne", "refuse"}:
                continue
            same_commune = (
                p.commune and c.commune
                and p.commune.strip().lower() == c.commune.strip().lower()
            )
            dist = _haversine(p.latitude, p.longitude, c.latitude, c.longitude)
            close = dist is not None and dist <= GEO_RADIUS_KM
            if same_commune or close:
                near.append((p, dist))
        if near:
            # le signal B1 ne peut tirer qu'une fois par contestation
            p, dist = near[0]
            near_label = "même commune" if (
                p.commune and c.commune
                and p.commune.strip().lower() == c.commune.strip().lower()
            ) else f"~{dist:.0f} km"
            out.append(
                Signal(
                    kind="B1_opposition_naissante",
                    score=SIGNAL_WEIGHTS["B1_opposition_naissante"],
                    scope="zone",
                    title=f"opposition naissante — {c.commune or '(commune ?)'}",
                    detail=(
                        f"contestation gagnée il y a {days} jours · projet actif "
                        f"« {p.name or '(sans nom)'} » à {near_label}"
                    ),
                    refs=[c.contestation_id, p.project_id],
                )
            )
    return out


def _detect_B2_ceinture_resistance(
    zone_dept: str | None, ctx: GlobalContext
) -> list[Signal]:
    if not zone_dept:
        return []
    projects = ctx.dept_projects.get(zone_dept, 0)
    contests = ctx.dept_contestations.get(zone_dept, 0)
    total = projects + contests
    if total < 3:
        return []
    rate = contests / total if total else 0.0
    if rate < DEPT_OPPOSITION_RESISTANCE:
        return []
    return [
        Signal(
            kind="B2_ceinture_resistance",
            score=SIGNAL_WEIGHTS["B2_ceinture_resistance"],
            scope="dept",
            title=f"ceinture de résistance — dépt {zone_dept}",
            detail=(
                f"{contests} contestations pour {projects} projets identifiés "
                f"({rate * 100:.0f} % d'opposition documentée)"
            ),
            refs=[zone_dept],
        )
    ]


# --- Détecteurs C (anomalies) -----------------------------------------------


def _detect_C1_paradoxe_operateur(
    projects: list[ProjectRow], ctx: GlobalContext
) -> list[Signal]:
    out = []
    seen_ops: set[str] = set()
    for p in projects:
        op = _op_canon(p.operator)
        if not op or op in seen_ops:
            continue
        seen_ops.add(op)
        if ctx.total_power == 0:
            continue
        share = ctx.operator_power.get(op, 0.0) / ctx.total_power * 100
        if share < MARKET_SHARE_PARADOX:
            continue
        contest_count = ctx.operator_contestations.get(op, 0)
        if contest_count == 0:
            out.append(
                Signal(
                    kind="C1_paradoxe_operateur",
                    score=SIGNAL_WEIGHTS["C1_paradoxe_operateur"],
                    scope="operator",
                    title=f"silence suspect — {op}",
                    detail=(
                        f"{share:.0f} % de la puissance agrivoltaïque recensée, "
                        f"0 contestation documentée dans la base"
                    ),
                    refs=[op],
                )
            )
    return out


def _detect_C2_divergence_registres(
    projects: list[ProjectRow], db_path: Path
) -> list[Signal]:
    # Divergence : la DB canonical ne garde qu'une valeur par champ, donc on
    # doit comparer les source_rows individuelles. Simplifié ici : on signale
    # les projets visibles par plusieurs sources — l'écart précis nécessite
    # une reconstitution des rows amont, à faire dans une future version.
    # MVP : on se concentre sur C1 et C3. C2 revient avec un détecteur complet.
    return []


def _detect_C3_opacite_operateur(projects: list[ProjectRow]) -> list[Signal]:
    out = []
    for p in projects:
        op = p.operator
        generic = op is None or op.strip() in {"—", "", "-"} or (
            op and op.strip().lower() in {"projet", "inconnu", "sans nom", "na"}
        )
        if not generic:
            continue
        # signale seulement les projets d'une certaine échelle (>= 10 MWc)
        if p.power_mwc is None or p.power_mwc < 10:
            continue
        out.append(
            Signal(
                kind="C3_opacite_operateur",
                score=SIGNAL_WEIGHTS["C3_opacite_operateur"],
                scope="project",
                title=f"opacité opérateur — {p.name or p.commune or '(?)'}",
                detail=(
                    f"{p.power_mwc:.0f} MWc à "
                    f"{p.commune or '(commune ?)'} ({p.code_dept or '??'}) "
                    f"sans opérateur déclaré"
                ),
                refs=[p.project_id],
            )
        )
    return out


# --- Entrée principale ------------------------------------------------------


def detect(result: SearchResult, db_path: Path) -> list[Signal]:
    """Produit la liste de signaux pour un résultat de recherche.

    Ordre : priorité éditoriale décroissante (P2 opposition d'abord),
    puis décroissant par score.
    """
    ctx = compute_global_context(db_path)
    signals: list[Signal] = []
    signals += _detect_B1_opposition_naissante(result.projects, result.contestations)

    # dept extrait du zone_label si présent (format "département 47")
    zone_dept = _zone_dept_from_label(result.zone_label)
    signals += _detect_B2_ceinture_resistance(zone_dept, ctx)

    signals += _detect_A1_projet_latent_mrae(result.projects)
    signals += _detect_A2_hausse_operateur(result.projects)

    signals += _detect_C1_paradoxe_operateur(result.projects, ctx)
    signals += _detect_C3_opacite_operateur(result.projects)

    # tri : priorité alarme d'abord, puis score
    def _rank(s: Signal) -> tuple[int, int]:
        alarm_bias = 1000 if s.kind in _ALARM_KINDS else 0
        return (-(s.score + alarm_bias), 0)

    signals.sort(key=_rank)
    return signals


def _zone_dept_from_label(label: str) -> str | None:
    import re
    m = re.search(r"\b(\d{2,3}|2A|2B)\b", label)
    return m.group(1) if m else None


def is_alarm(signals: Iterable[Signal]) -> bool:
    return any(s.kind in _ALARM_KINDS and s.score >= ALARM_THRESHOLD for s in signals)
