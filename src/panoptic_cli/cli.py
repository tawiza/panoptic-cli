"""Point d'entrée CLI. Une commande pour tous.

Usage :
  panoptic 47                    # dépt 47 (Lot-et-Garonne)
  panoptic 47250                 # code postal → dépt auto
  panoptic "Pujo-le-Plan"        # commune (fuzzy)
  panoptic freshness             # état 3AYNE + sources
  panoptic --help                # aide
"""

from __future__ import annotations

import sys

import typer
from rich.console import Console

from panoptic_cli import __version__
from panoptic_cli.mascotte import EyeState, render as mascotte_render
from panoptic_cli.query import resolve
from panoptic_cli.render import render_report
from panoptic_cli.search import search, _default_db_path, _compute_freshness_days
from panoptic_cli.signals import detect as detect_signals

app = typer.Typer(
    name="panoptic",
    help="panoptic — un regard sur l'agrivoltaïsme français.",
    no_args_is_help=True,
    add_completion=False,
    rich_markup_mode="rich",
)

console = Console()


def _version_callback(v: bool) -> None:
    if v:
        console.print(f"panoptic-tawiza [bold orange3]{__version__}[/]")
        raise typer.Exit()


@app.callback()
def _root(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Affiche la version et quitte.",
    ),
) -> None:
    pass


@app.command()
def search_cmd(
    zone: str = typer.Argument(..., help="département (47), CP, INSEE ou commune"),
    html_out: str | None = typer.Option(
        None, "--html", help="écrire un rapport HTML auto-suffisant (ex. rapport.html)"
    ),
) -> None:
    """Recherche les projets agrivoltaïques dans une zone."""
    zf = resolve(zone)
    try:
        result = search(zf)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(code=2)
    signals = detect_signals(result, _default_db_path())
    render_report(result, signals)
    if html_out:
        from pathlib import Path

        from panoptic_cli.html_render import write_html_report

        path = Path(html_out).expanduser().resolve()
        write_html_report(result, signals, path)
        console.print(f"\n[dim]rapport HTML écrit →[/] [orange3]{path}[/]")


@app.command()
def update(
    force: bool = typer.Option(False, "--force", help="télécharger même si la DB locale est à jour"),
) -> None:
    """Rafraîchit la DB locale depuis panoptic.tawiza.fr/data/."""
    import urllib.error

    from panoptic_cli.sync import (
        CACHED_DB_PATH,
        fetch_manifest,
        local_version,
        needs_update,
        download_db,
        effective_db_path,
    )

    current_path = effective_db_path()
    current_v = local_version(current_path)
    console.print(f"  DB locale : [bold]{current_v or 'aucune'}[/] ({current_path})")
    console.print(f"  manifest  : [dim]fetching panoptic.tawiza.fr/data/manifest.json…[/]")

    try:
        manifest = fetch_manifest()
    except urllib.error.URLError as e:
        console.print(f"[red]impossible de joindre le CDN : {e.reason}[/]")
        raise typer.Exit(code=3)
    except Exception as e:
        console.print(f"[red]erreur manifest : {e}[/]")
        raise typer.Exit(code=3)

    console.print(f"  distant   : [bold]{manifest.version}[/] · "
                  f"{manifest.counts.get('projects_canonical', '?')} projets · "
                  f"{manifest.sqlite_size_bytes / 1024:.0f} KB")

    if not force and not needs_update(current_v, manifest.version):
        console.print(f"[orange3]DB déjà à jour.[/] Passe [dim]--force[/] pour retélécharger.")
        return

    console.print(f"  téléchargement → [dim]{CACHED_DB_PATH}[/]")
    try:
        download_db(manifest, CACHED_DB_PATH)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        raise typer.Exit(code=4)
    except urllib.error.URLError as e:
        console.print(f"[red]téléchargement échoué : {e.reason}[/]")
        raise typer.Exit(code=4)

    console.print(f"[orange3]✓ DB mise à jour : {manifest.version}[/]")


@app.command()
def operators(
    alarm: bool = typer.Option(False, "--alarm", help="uniquement les opérateurs en alarme (rachat récent, cascade offshore)"),
    foreign: bool = typer.Option(False, "--foreign", help="uniquement les opérateurs sous contrôle étranger"),
    top: int = typer.Option(20, "--top", help="limite le nombre d'opérateurs affichés"),
) -> None:
    """Cascade actionnariale : opérateurs et signaux D1-D7."""
    from panoptic_cli.operators import load_all_operators

    path = _default_db_path()
    if not path.exists():
        console.print(f"[red]DB introuvable : {path}[/]")
        raise typer.Exit(code=2)

    ops = load_all_operators(path, alarm_only=alarm, foreign_only=foreign, limit=top)
    if not ops:
        console.print("[dim](aucun opérateur trouvé — peut-être DB v0.2 sans migration v0.3 ?)[/]")
        raise typer.Exit(code=0)

    # Header sobre
    from panoptic_cli.mascotte import EyeState, render as mascotte_render
    any_alarm = any(o.is_alarm for o in ops)
    state = EyeState.ALARME if any_alarm else EyeState.ATTENTIF
    eye = mascotte_render(state)
    console.print(eye.rich_text)
    console.print(
        f"[bold {eye.accent_color}]3AYNE · {eye.label}[/] "
        f"— cascade actionnariale agrivoltaïque\n"
    )

    # Filtres appliqués
    filters = []
    if alarm: filters.append("alarme seulement")
    if foreign: filters.append("contrôle étranger seulement")
    if filters:
        console.print(f"[dim]filtres : {' · '.join(filters)}[/]")
    console.print(f"[bold]{len(ops)}[/] opérateur{'s' if len(ops) > 1 else ''} · triés par score de signal puis empreinte RNE\n")

    from rich.table import Table
    from panoptic_cli.operators import SIGNAL_LABELS

    for op in ops:
        marker = "⚠" if op.is_alarm else "·"
        marker_style = "red3 bold" if op.is_alarm else "orange3"
        console.print(
            f"[{marker_style}]{marker}[/] [bold]{op.canonical_name}[/] "
            f"[dim](SIREN {op.siren})[/]",
            end="",
        )
        if op.ultimate_country and op.ultimate_country != "FRA":
            console.print(f"  [red3]\\[{op.country_label}][/]", end="")
        if op.n_subsidiaries_rne:
            console.print(f"  [dim]· {op.n_subsidiaries_rne} SPV au RNE[/]", end="")
        console.print()

        if op.president_is_legal and op.president_current:
            console.print(f"      [dim]président :[/] [italic]{op.president_current}[/]")

        for sig in sorted(op.signals, key=lambda s: -s.score)[:4]:
            color = "red3" if sig.is_alarm else "orange3" if sig.score >= 60 else "grey50"
            label = SIGNAL_LABELS.get(sig.kind, sig.kind)
            console.print(f"      [{color}]{label}[/] [dim][score {sig.score}][/]")
            if sig.detail and sig.is_alarm:
                console.print(f"        [dim italic]{sig.detail}[/]")
        console.print()


@app.command()
def freshness() -> None:
    """État des sources et de 3AYNE."""
    import sqlite3
    path = _default_db_path()
    if not path.exists():
        console.print(f"[red]DB introuvable : {path}[/]")
        raise typer.Exit(code=2)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    meta = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM meta").fetchall()}
    sources = list(conn.execute("SELECT source, last_crawled, rows_count FROM source_freshness").fetchall())
    conn.close()

    days = _compute_freshness_days(meta)
    state = EyeState.DORMANT if (days is None or days > 14) else (
        EyeState.EVEILLE if days < 1 else EyeState.ATTENTIF
    )
    eye = mascotte_render(state)
    console.print(eye.rich_text)
    console.print(
        f"[bold {eye.accent_color}]3AYNE · {eye.label}[/] "
        f"— [dim italic]{eye.caption}[/]\n"
    )
    console.print(f"  version DB : [bold]{meta.get('version', '?')}[/] ({days} jours)")
    console.print(f"  projets canoniques : [bold]{meta.get('projects_canonical', '?')}[/]")
    console.print(f"  contestations : [bold]{meta.get('contestations', '?')}[/]")
    console.print()
    console.print("  sources :")
    for s in sources:
        console.print(
            f"    [dim]·[/] {s['source']:<25s} "
            f"[dim]rows[/] [bold]{s['rows_count']}[/]"
        )
    console.print()


# Permet `panoptic 47` (sans sous-commande "search") en interceptant sys.argv
def main() -> None:
    argv = sys.argv[1:]
    if argv and not argv[0].startswith("-") and argv[0] not in {"search-cmd", "freshness", "update", "operators"}:
        sys.argv = [sys.argv[0], "search-cmd"] + argv
    app()


if __name__ == "__main__":
    main()
