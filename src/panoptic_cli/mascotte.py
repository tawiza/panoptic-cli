"""3AYNE — l'œil officiel Tawiza, aligné sur la charte panoptic.tawiza.fr.

Géométrie : pixel-art 30+miroir (60 chars) hérité du widget 3AYNE TUI.
Palette : alignée sur le favicon du site (iris ocre `#b45309`, cœur rouge
terre `#C1554D`) — pas la palette gold d'origine. Cohérence éditoriale
avec l'article et le favicon SVG.
Rendu via `bgcolor` sur espaces → pixels carrés, pas half-blocks.

Trois frames canoniques :
  CLOSED  (7 lignes)  — œil fermé
  HALF    (9 lignes)  — œil à moitié
  OPEN    (18 lignes) — œil grand ouvert

Quatre états panoptic mappés sur les frames + palette :
  DORMANT   → CLOSED (œil fermé, data périmée)
  ATTENTIF  → HALF   (œil attentif)
  EVEILLE   → OPEN   (œil ouvert, data fraîche)
  ALARME    → OPEN avec iris plus saturé rouge terre

On garde strictement la géométrie officielle — les états modulent uniquement
la palette. C'est la règle éditoriale : 3AYNE reste reconnaissable partout.
"""

from __future__ import annotations

from enum import Enum
from typing import NamedTuple

from rich.style import Style
from rich.text import Text


class EyeState(str, Enum):
    DORMANT = "dormant"
    ATTENTIF = "attentif"
    EVEILLE = "eveille"
    ALARME = "alarme"


class EyeRender(NamedTuple):
    rich_text: Text
    label: str
    caption: str
    accent_color: str


# ---------------------------------------------------------------------------
# Palette officielle Tawiza (port verbatim de tawiza-splash)
# ---------------------------------------------------------------------------

_PALETTE_DEFAULT: dict[str, str] = {
    # Palette alignée sur favicon.svg et article panoptic.tawiza.fr
    # Iris = ocre Tawiza #b45309, cœur = rouge terre #C1554D
    ".": "",
    "S": "#3a2a1a",  # shadow outer (cils)
    "s": "#4a3828",  # shadow mid
    "L": "#1a1612",  # eyelid deep (paupières site)
    "W": "#f3ebdd",  # sclera claire (site)
    "w": "#e4d9c5",  # sclera mid
    "B": "#6b2e05",  # iris ring (ocre sombre)
    "D": "#8a3e07",  # iris outer (ocre moyen)
    "I": "#a04a08",  # iris mid (ocre)
    "i": "#b45309",  # iris ocre Tawiza (signature site)
    "G": "#C1554D",  # cœur iris rouge terre Tawiza (signature site)
    "g": "#d06860",  # cœur iris highlight
    "P": "#1a1612",  # pupille (même noir que paupières)
    "R": "#faf5ef",  # reflection crème Tawiza
}


def _palette_for(state: EyeState) -> dict[str, str]:
    p = dict(_PALETTE_DEFAULT)
    if state is EyeState.DORMANT:
        # tout désaturé, comme un œil fermé endormi
        p.update({
            "S": "#2a2018", "s": "#3a2e22", "L": "#141008",
            "W": "#a89f92", "w": "#908678",
        })
    elif state is EyeState.ALARME:
        # tout l'iris bascule rouge terre saturé — signal visible
        p.update({
            "B": "#5a1408", "D": "#7a2410", "I": "#9a3420",
            "i": "#C1554D", "G": "#d8382a", "g": "#eb5f50",
        })
    return p


# ---------------------------------------------------------------------------
# Frames (verbatim tawiza-splash : chaque row = 30 chars, miroirés → 60)
# ---------------------------------------------------------------------------

_CLOSED_RAW = [
    "............SSSSSSSSSSSSSSSSSS",
    "........SSSS..................",
    ".....SSSsLLLLLLLLLLLLLLLLLLLLL",
    "......SSsLLLLLLLLLLLLLLLLLLLLL",
    ".....SSSsLLLLLLLLLLLLLLLLLLLLL",
    "........SSSS..................",
    "............SSSSSSSSSSSSSSSSSS",
]

_HALF_RAW = [
    "............SSSSSSSSSSSSSSSSSS",
    ".......SSSSSssLLLLLLLLLLLLLLL.",
    ".....SSsLLwWWWWWWWWWWWWWWWWWW.",
    "..SSsLLwWWWWWWWWWBDIiGGGGGGGGG",
    "..SSsLLwWWWWWWWWWBDIiggRPPPPPP",
    "..SSsLLwWWWWWWWWWWBDIiGGGGGGGG",
    ".....SSsLLwWWWWWWWWWWWWWWWWWW.",
    ".......SSSSSssLLLLLLLLLLLLLLL.",
    "............SSSSSSSSSSSSSSSSSS",
]

_OPEN_RAW = [
    "............SSSSSSSSSSSSSSSSSS",
    ".......SSSSSssLLLLLLLLLLLLLLL.",
    "....SSSSssLLLLLLLLLLLLLLLLLLLL",
    "...SSSsLLLwwwwwwwwwwwwwwwwwwww",
    "..SSSsLLwWWWWWWWWWWWWWWWWWWWWW",
    ".SSsLLwWWWWWWWWWWWBBBBBBBBBBBB",
    ".SSsLLwWWWWWWWWBDDIIIIIIIIIIII",
    "SSsLLwWWWWWWWBDIiiGGGGGGGGGGGG",
    "SSsLLwWWWWWWWBDIiiiggRPPPPPPPP",
    "SSsLLwWWWWWWWBDIiiigggPPPPPPPP",
    "SSsLLwWWWWWWWBDIiiGGGGGGGGGGGG",
    ".SSsLLwWWWWWWWWBDDIIIIIIIIIIII",
    ".SSsLLwWWWWWWWWWWWBBBBBBBBBBBB",
    "..SSSsLLwWWWWWWWWWWWWWWWWWWWWW",
    "...SSSsLLLwwwwwwwwwwwwwwwwwwww",
    "....SSSSssLLLLLLLLLLLLLLLLLLLL",
    ".......SSSSSssLLLLLLLLLLLLLLL.",
    "............SSSSSSSSSSSSSSSSSS",
]


def _mirror(left: str) -> str:
    assert len(left) == 30, f"expected 30 chars, got {len(left)}: {left!r}"
    return left + left[::-1]


CLOSED: tuple[str, ...] = tuple(_mirror(r) for r in _CLOSED_RAW)
HALF: tuple[str, ...] = tuple(_mirror(r) for r in _HALF_RAW)
OPEN: tuple[str, ...] = tuple(_mirror(r) for r in _OPEN_RAW)


# ---------------------------------------------------------------------------
# Rendering (bgcolor sur espaces → pixels carrés)
# ---------------------------------------------------------------------------


def _frame_to_text(frame: tuple[str, ...], palette: dict[str, str]) -> Text:
    out = Text()
    for row in frame:
        for ch in row:
            bg = palette.get(ch, "")
            if bg:
                out.append(" ", style=Style(bgcolor=bg))
            else:
                out.append(" ")
        out.append("\n")
    # enlever \n final
    if out.plain.endswith("\n"):
        out = out[:-1]
    return out


_STATE_FRAME: dict[EyeState, tuple[str, ...]] = {
    EyeState.DORMANT: CLOSED,
    EyeState.ATTENTIF: HALF,
    EyeState.EVEILLE: OPEN,
    EyeState.ALARME: OPEN,
}


_CAPTIONS: dict[EyeState, tuple[str, str, str]] = {
    # (label, caption, couleur accent rich)
    EyeState.DORMANT:  ("dormant",  "data périmée, tape `panoptic update`",   "grey50"),
    EyeState.ATTENTIF: ("attentif", "data raisonnable",                         "yellow3"),
    EyeState.EVEILLE:  ("éveillé",  "data fraîche",                             "#b45309"),
    EyeState.ALARME:   ("alarmé",   "micro-signal détecté",                     "red3"),
}


def render(state: EyeState) -> EyeRender:
    frame = _STATE_FRAME[state]
    palette = _palette_for(state)
    label, caption, color = _CAPTIONS[state]
    return EyeRender(
        rich_text=_frame_to_text(frame, palette),
        label=label,
        caption=caption,
        accent_color=color,
    )
