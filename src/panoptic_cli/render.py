"""Rendu terminal avec 3AYNE en en-tête.

Philosophie :
  - toujours 3AYNE en haut (mascotte non-désactivable)
  - zéro emoji, sobre, palette ocre/crème/rouge-terre
  - un rapport tient dans une fenêtre terminal standard (80 col)
  - l'absence de data est affichée honnêtement (on ne cache pas le vide)
"""

from __future__ import annotations

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from panoptic_cli.mascotte import EyeState, render as mascotte_render
from panoptic_cli.search import SearchResult
from panoptic_cli.signals import Signal, is_alarm


console = Console()


def _choose_eye_state(result: SearchResult, signals: list[Signal]) -> EyeState:
    # P2 "opposition naissante" (B1) déclenche alarme en priorité éditoriale
    if is_alarm(signals):
        return EyeState.ALARME
    days = result.freshness_days
    if days is None:
        return EyeState.DORMANT
    if days > 14:
        return EyeState.DORMANT
    if days < 1:
        return EyeState.EVEILLE
    return EyeState.ATTENTIF


def _header(result: SearchResult, signals: list[Signal]) -> Panel:
    state = _choose_eye_state(result, signals)
    eye = mascotte_render(state)
    title = Text()
    title.append("\npanoptic", style="bold orange3")
    title.append(" · un regard sur l'agrivoltaïsme français\n", style="dim")
    title.append(f"3AYNE · {eye.label}  ", style=f"bold {eye.accent_color}")
    title.append(f"— {eye.caption}", style="dim italic")
    body = Group(eye.rich_text, title)
    return Panel(body, border_style="orange3", padding=(0, 2))


def _overview(result: SearchResult) -> Text:
    t = Text()
    t.append(f"\nzone : ", style="dim")
    t.append(f"{result.zone_label}\n", style="bold")
    n_proj = len(result.projects)
    n_con = len(result.contestations)
    total_mwc = sum((p.power_mwc or 0.0) for p in result.projects)
    total_ha = sum((p.surface_ha or 0.0) for p in result.projects)
    t.append(f"{n_proj} projet{'s' if n_proj > 1 else ''} · ", style="orange3")
    t.append(f"{n_con} contestation{'s' if n_con > 1 else ''} CNPrV\n")
    if total_mwc:
        t.append(f"puissance cumulée : ", style="dim")
        t.append(f"{total_mwc:.0f} MWc", style="bold")
        if total_ha:
            t.append(f" · {total_ha:.0f} ha", style="dim")
        t.append("\n")
    return t


def _projects_table(result: SearchResult, limit: int = 20) -> Table | Text:
    if not result.projects:
        return Text("\n(aucun projet trouvé dans cette zone)\n", style="italic dim")
    table = Table(
        title=None,
        border_style="grey50",
        show_lines=False,
        pad_edge=False,
        padding=(0, 1),
    )
    table.add_column("projet", style="bold", no_wrap=False, max_width=34)
    table.add_column("commune", style="dim", no_wrap=True, max_width=22)
    table.add_column("MWc", style="orange3", justify="right")
    table.add_column("statut", style="dim")
    table.add_column("opérateur", style="", no_wrap=False, max_width=22)
    table.add_column("sources", style="grey50", no_wrap=True)

    shown = result.projects[:limit]
    for p in shown:
        name = (p.name or "(sans nom)").strip()
        if len(name) > 32:
            name = name[:30] + "…"
        mwc = f"{p.power_mwc:.1f}" if p.power_mwc else "—"
        status = (p.status or "").replace("_", " ")
        op = p.operator or "—"
        if len(op) > 20:
            op = op[:18] + "…"
        sources_abbr = ",".join(
            {
                "ademe_agrivolt": "ADEME",
                "mrae": "MRAe",
                "projets_env": "PE",
                "cnprv_victoires": "CNPrV",
            }.get(s, s[:4])
            for s in p.seen_in_sources
        )
        table.add_row(name, (p.commune or "—")[:22], mwc, status, op, sources_abbr)

    if len(result.projects) > limit:
        table.caption = f"+ {len(result.projects) - limit} autres — utilise `--all` pour tout voir"
        table.caption_style = "dim italic"
    return table


def _contestations_block(result: SearchResult) -> Text:
    if not result.contestations:
        return Text("")
    t = Text()
    t.append("\ncontestations CNPrV dans la zone\n", style="bold")
    for c in result.contestations[:10]:
        commune = c.commune or "(commune ?)"
        date = c.date_event or "date ?"
        issue = c.issue_status or "en cours"
        t.append("  • ", style="red3")
        t.append(f"{commune}", style="bold")
        t.append(f" · {date[:10]} · {issue}", style="dim")
        if c.acteur_nom:
            t.append(f" · {c.acteur_nom[:48]}", style="dim italic")
        t.append("\n")
    if len(result.contestations) > 10:
        t.append(f"  … et {len(result.contestations) - 10} autres\n", style="dim italic")
    return t


def _footer(result: SearchResult) -> Text:
    t = Text("\n")
    t.append("─" * 60 + "\n", style="grey50")
    gen_date = result.meta.get("version", "?")
    days = result.freshness_days
    age = f"il y a {days} jour{'s' if (days or 0) > 1 else ''}" if days is not None else "inconnu"
    t.append("data  ", style="dim")
    t.append(f"{gen_date} ({age})", style="dim")
    t.append("  ·  ", style="grey50")
    t.append("sources ", style="dim")
    t.append("ADEME · MRAe · projets-environnement · CNPrV", style="dim")
    t.append("\n")
    t.append("licence ", style="dim")
    t.append("CC-BY-SA", style="dim")
    t.append("  ·  ", style="grey50")
    t.append("site ", style="dim")
    t.append("panoptic.tawiza.fr", style="orange3")
    t.append("\n")
    return t


def _signals_block(signals: list[Signal]) -> Text:
    if not signals:
        return Text("")
    # classe chaque signal par famille pour hiérarchie visuelle
    alarms = [s for s in signals if s.kind.startswith("B")]
    anomalies = [s for s in signals if s.kind.startswith("C")]
    emerging = [s for s in signals if s.kind.startswith("A")]

    t = Text()
    t.append("\nmicro-signaux détectés", style="bold")
    t.append(f"  ({len(signals)})\n", style="dim")

    def _render_family(label: str, color: str, marker: str, group: list[Signal]) -> None:
        if not group:
            return
        t.append(f"\n  {label}\n", style=f"bold {color}")
        for s in group[:5]:
            t.append(f"    {marker} ", style=color)
            t.append(f"{s.title}", style="bold")
            t.append(f"  [score {s.score}]\n", style="dim")
            if s.detail:
                t.append(f"      {s.detail}\n", style="dim italic")
        if len(group) > 5:
            t.append(f"    … {len(group) - 5} autres\n", style="dim italic")

    _render_family("opposition", "red3", "⚠", alarms)
    _render_family("anomalie structurelle", "orange3", "●", anomalies)
    _render_family("émergence", "yellow3", "↗", emerging)
    return t


def render_report(result: SearchResult, signals: list[Signal] | None = None) -> None:
    signals = signals or []
    console.print(_header(result, signals))
    console.print(Align.left(_overview(result)))
    console.print(_projects_table(result))
    console.print(_contestations_block(result))
    console.print(_signals_block(signals))
    console.print(_footer(result))
