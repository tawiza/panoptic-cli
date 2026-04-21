"""Export rapport HTML auto-suffisant (H1 du design doc).

Un seul fichier, CSS inline, SVG 3AYNE embarqué. Aucune dépendance externe :
le militant peut l'envoyer par mail, WhatsApp, Signal, clé USB — ça marche
hors-ligne, sur n'importe quel navigateur.

Palette et typo alignées sur panoptic.tawiza.fr (ocre `#b45309`, crème
`#faf5ef`, rouge terre `#C1554D`, forêt `#2D6A4F`).
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from panoptic_cli.search import SearchResult
from panoptic_cli.signals import Signal, is_alarm


# SVG 3AYNE officiel web (simplifié viewBox 40×16), embarqué inline.
_3AYNE_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 40 16"
  shape-rendering="crispEdges" class="eye-svg" aria-label="3AYNE">
  <g fill="currentColor">
    <rect x="8" y="0" width="1" height="2"/><rect x="14" y="0" width="1" height="2"/>
    <rect x="20" y="0" width="1" height="2"/><rect x="26" y="0" width="1" height="2"/>
    <rect x="32" y="0" width="1" height="2"/>
    <rect x="6" y="3" width="1" height="1"/><rect x="7" y="2" width="2" height="1"/>
    <rect x="9" y="2" width="4" height="1"/><rect x="13" y="2" width="4" height="1"/>
    <rect x="17" y="2" width="6" height="1"/><rect x="23" y="2" width="4" height="1"/>
    <rect x="27" y="2" width="4" height="1"/><rect x="31" y="2" width="2" height="1"/>
    <rect x="33" y="3" width="1" height="1"/>
    <rect x="8" y="13" width="2" height="1"/><rect x="10" y="14" width="20" height="1"/>
    <rect x="30" y="13" width="2" height="1"/>
  </g>
  <g fill="#f3ebdd">
    <rect x="8" y="4" width="24" height="8"/><rect x="9" y="3" width="22" height="1"/>
    <rect x="9" y="12" width="22" height="1"/><rect x="11" y="13" width="18" height="1"/>
  </g>
  <g fill="#b45309">
    <rect x="15" y="4" width="10" height="1"/><rect x="14" y="5" width="12" height="1"/>
    <rect x="13" y="6" width="14" height="1"/><rect x="13" y="7" width="14" height="1"/>
    <rect x="13" y="8" width="14" height="1"/><rect x="13" y="9" width="14" height="1"/>
    <rect x="14" y="10" width="12" height="1"/><rect x="15" y="11" width="10" height="1"/>
  </g>
  <g fill="#C1554D">
    <rect x="16" y="5" width="8" height="1"/><rect x="15" y="6" width="10" height="1"/>
    <rect x="15" y="7" width="10" height="1"/><rect x="15" y="8" width="10" height="1"/>
    <rect x="15" y="9" width="10" height="1"/><rect x="16" y="10" width="8" height="1"/>
  </g>
  <g fill="#1a1612"><rect x="18" y="6" width="4" height="4"/></g>
  <rect x="18" y="6" width="1" height="1" fill="#faf5ef"/>
</svg>"""


_STYLE = """
:root {
  --bg: #faf5ef; --bg-deep: #f3ebdd;
  --ink: #1a1612; --ink-soft: #3a342c; --ink-mute: #7a6e5e;
  --line: #d8cfbf;
  --ocre: #b45309; --terre: #C1554D; --foret: #2D6A4F; --gold: #D4A843;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg); color: var(--ink); padding: 32px 20px;
  font-family: "Instrument Serif", Georgia, ui-serif, serif;
  line-height: 1.5; max-width: 960px; margin: 0 auto;
}
header.banner {
  display: flex; gap: 24px; align-items: center;
  padding-bottom: 18px; border-bottom: 2px solid var(--ocre);
  margin-bottom: 28px; color: var(--ocre);
}
.banner .eye-svg { width: 80px; height: 32px; flex: 0 0 80px; }
.banner h1 {
  font-size: 34px; letter-spacing: -0.01em; font-weight: 500; color: var(--ink);
}
.banner .subtitle {
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 12px; letter-spacing: 0.12em; text-transform: uppercase;
  color: var(--ink-mute); margin-top: 4px;
}
.state-pill {
  margin-left: auto; font-family: "JetBrains Mono", ui-monospace, monospace;
  padding: 6px 14px; border-radius: 18px; font-size: 12px;
  letter-spacing: 0.08em; text-transform: uppercase;
  border: 1px solid var(--line); background: #fff;
}
.state-alarm { color: var(--terre); border-color: var(--terre); }
.state-awake { color: var(--ocre); border-color: var(--ocre); }
.state-dim   { color: var(--ink-mute); }

h2 {
  font-size: 22px; font-weight: 500; letter-spacing: -0.005em;
  margin: 32px 0 14px; color: var(--ink);
}
.overview {
  background: #fff; border: 1px solid var(--line); border-radius: 6px;
  padding: 18px 24px; font-size: 17px;
}
.overview strong { color: var(--ocre); }

table {
  width: 100%; border-collapse: collapse; margin: 14px 0 24px;
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 13px; background: #fff;
}
th, td {
  text-align: left; padding: 9px 12px;
  border-bottom: 1px solid var(--line); vertical-align: top;
}
th { color: var(--ink-mute); font-weight: 500; letter-spacing: 0.05em;
     text-transform: uppercase; font-size: 11px; background: #fdfbf7; }
td.mwc { text-align: right; color: var(--ocre); font-weight: 600; }
td.src { font-size: 11px; color: var(--ink-mute); }
tr:hover td { background: #fcf8f0; }

ul.contests { list-style: none; padding: 0; }
ul.contests li {
  padding: 10px 14px; border-left: 3px solid var(--terre);
  margin: 6px 0; background: #fff; border-radius: 0 4px 4px 0;
  font-size: 15px;
}
ul.contests .date { color: var(--ink-mute); font-size: 13px; }
ul.contests .acteur { color: var(--ink-mute); font-size: 13px; font-style: italic; }

.signals { margin-top: 28px; }
.signal-group h3 {
  font-size: 13px; letter-spacing: 0.08em; text-transform: uppercase;
  color: var(--ink-mute); margin: 16px 0 6px; font-family: "JetBrains Mono", ui-monospace, monospace;
}
.signal {
  background: #fff; border-left: 3px solid var(--ocre);
  padding: 12px 16px; margin: 6px 0; border-radius: 0 4px 4px 0;
}
.signal.opposition { border-left-color: var(--terre); }
.signal.anomaly { border-left-color: var(--gold); }
.signal.emergence { border-left-color: var(--foret); }
.signal .title { font-size: 16px; font-weight: 500; }
.signal .score {
  color: var(--ink-mute); font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 12px; margin-left: 8px;
}
.signal .detail { font-size: 14px; color: var(--ink-soft); font-style: italic; margin-top: 3px; }

footer.source-foot {
  margin-top: 42px; padding-top: 18px;
  border-top: 1px solid var(--line);
  font-family: "JetBrains Mono", ui-monospace, monospace;
  font-size: 11px; letter-spacing: 0.06em;
  color: var(--ink-mute);
}
footer a { color: var(--ocre); text-decoration: none; }
.empty { font-style: italic; color: var(--ink-mute); padding: 10px 0; }
"""


def _e(s: str | None) -> str:
    return html.escape(s) if s else ""


def _state_class(result: SearchResult, signals: list[Signal]) -> tuple[str, str, str]:
    if is_alarm(signals):
        return "state-alarm", "alarmé", "micro-signal détecté"
    days = result.freshness_days
    if days is None or days > 14:
        return "state-dim", "dormant", "data périmée"
    if days < 1:
        return "state-awake", "éveillé", "data fraîche"
    return "state-awake", "attentif", "data raisonnable"


def _project_rows(result: SearchResult) -> str:
    if not result.projects:
        return '<tr><td colspan="6" class="empty">Aucun projet dans cette zone.</td></tr>'
    rows = []
    src_short = {"ademe_agrivolt": "ADEME", "mrae": "MRAe",
                 "projets_env": "projets-env", "cnprv_victoires": "CNPrV"}
    for p in result.projects:
        sources = ", ".join(src_short.get(s, s) for s in p.seen_in_sources)
        rows.append(
            "<tr>"
            f"<td><strong>{_e(p.name or '(sans nom)')}</strong></td>"
            f"<td>{_e(p.commune or '—')}</td>"
            f"<td class='mwc'>{(f'{p.power_mwc:.1f}' if p.power_mwc else '—')}</td>"
            f"<td>{_e(p.status or '—')}</td>"
            f"<td>{_e(p.operator or '—')}</td>"
            f"<td class='src'>{_e(sources)}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def _contest_list(result: SearchResult) -> str:
    if not result.contestations:
        return "<p class='empty'>Aucune contestation documentée dans cette zone.</p>"
    items = []
    for c in result.contestations:
        parts = [f"<strong>{_e(c.commune or '(commune ?)')}</strong>"]
        if c.date_event:
            parts.append(f"<span class='date'>· {_e(c.date_event[:10])}</span>")
        if c.issue_status:
            parts.append(f"<span class='date'>· {_e(c.issue_status)}</span>")
        if c.acteur_nom:
            parts.append(f"<span class='acteur'>· {_e(c.acteur_nom[:60])}</span>")
        items.append(f"<li>{' '.join(parts)}</li>")
    return "<ul class='contests'>" + "\n".join(items) + "</ul>"


def _signal_block(signals: list[Signal]) -> str:
    if not signals:
        return "<p class='empty'>Aucun micro-signal détecté dans cette zone.</p>"

    def _family(title: str, css_class: str, kinds_prefix: str) -> str:
        group = [s for s in signals if s.kind.startswith(kinds_prefix)]
        if not group:
            return ""
        rows = "\n".join(
            f"<div class='signal {css_class}'>"
            f"<span class='title'>{_e(s.title)}</span>"
            f"<span class='score'>[score {s.score}]</span>"
            + (f"<div class='detail'>{_e(s.detail)}</div>" if s.detail else "")
            + "</div>"
            for s in group
        )
        return f"<div class='signal-group'><h3>{title}</h3>{rows}</div>"

    return (
        _family("opposition", "opposition", "B")
        + _family("anomalie structurelle", "anomaly", "C")
        + _family("émergence", "emergence", "A")
    )


def build_html(result: SearchResult, signals: list[Signal]) -> str:
    state_cls, state_label, state_caption = _state_class(result, signals)
    n_proj = len(result.projects)
    n_con = len(result.contestations)
    total_mwc = sum(p.power_mwc or 0.0 for p in result.projects)
    total_ha = sum(p.surface_ha or 0.0 for p in result.projects)
    gen_now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    db_ver = result.meta.get("version", "?")

    overview_parts = [
        f"<strong>{n_proj}</strong> projet{'s' if n_proj > 1 else ''}",
        f"<strong>{n_con}</strong> contestation{'s' if n_con > 1 else ''} CNPrV",
    ]
    if total_mwc:
        overview_parts.append(f"puissance cumulée <strong>{total_mwc:.0f} MWc</strong>")
    if total_ha:
        overview_parts.append(f"{total_ha:.0f} ha")

    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<title>panoptic · {_e(result.zone_label)}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="panoptic — rapport agrivoltaïque local · {_e(result.zone_label)}">
<meta name="robots" content="noindex">
<style>{_STYLE}</style>
</head>
<body>
  <header class="banner">
    {_3AYNE_SVG}
    <div>
      <h1>panoptic · {_e(result.zone_label)}</h1>
      <p class="subtitle">un regard sur l'agrivoltaïsme français</p>
    </div>
    <div class="state-pill {state_cls}">3AYNE · {state_label}</div>
  </header>

  <section class="overview">
    {' · '.join(overview_parts)}
  </section>

  <h2>projets recensés</h2>
  <table>
    <thead><tr>
      <th>projet</th><th>commune</th><th>MWc</th><th>statut</th>
      <th>opérateur</th><th>sources</th>
    </tr></thead>
    <tbody>
      {_project_rows(result)}
    </tbody>
  </table>

  <h2>contestations documentées</h2>
  {_contest_list(result)}

  <h2>micro-signaux</h2>
  <section class="signals">
    {_signal_block(signals)}
  </section>

  <footer class="source-foot">
    rapport généré le {gen_now} · data panoptic {db_ver}<br>
    sources : ADEME Observatoire · projets-environnement.gouv.fr · MRAe · Coordination Nationale Photorévoltée<br>
    licence data <strong>CC-BY-SA</strong> · code AGPL-3.0 · <a href="https://panoptic.tawiza.fr">panoptic.tawiza.fr</a>
  </footer>
</body>
</html>"""


def write_html_report(
    result: SearchResult, signals: list[Signal], out_path: Path
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_html(result, signals), encoding="utf-8")
