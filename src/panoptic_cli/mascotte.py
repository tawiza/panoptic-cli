"""3AYNE — l'œil officiel Tawiza, porté depuis `tawiza-splash` / 3AYNE TUI.

Source officielle : `/opt/tawiza-cli/3ayne/src/ayne/tui/mascot.py`.
Palette 14 couleurs, iris or `#D4A843` signature Tawiza.
Chaque ligne = 30 chars côté gauche + miroir (60 chars total).
Rendu via `bgcolor` sur espaces → pixels carrés, pas half-blocks.

Trois frames canoniques :
  CLOSED  (7 lignes)  — œil fermé
  HALF    (9 lignes)  — œil à moitié
  OPEN    (18 lignes) — œil grand ouvert

Quatre états panoptic mappés sur les frames + palette :
  DORMANT   → CLOSED (œil fermé, data périmée)
  ATTENTIF  → HALF   (œil attentif)
  EVEILLE   → OPEN   (œil ouvert, data fraîche)
  ALARME    → OPEN avec iris or → rouge terre `#C1554D`

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
    ".": "",
    "S": "#3a2a1a",  # shadow outer
    "s": "#4a3828",  # shadow mid
    "L": "#1e120a",  # eyelid deep
    "W": "#e8e2d8",  # sclera light
    "w": "#d0c8bc",  # sclera mid
    "B": "#2a1808",  # iris dark ring
    "D": "#705010",  # iris outer
    "I": "#a07820",  # iris mid
    "i": "#c8a030",  # iris bright
    "G": "#D4A843",  # iris gold (signature)
    "g": "#e8c860",  # iris highlight
    "P": "#060402",  # pupil
    "R": "#f0ece8",  # reflection
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
        # iris or → rouge terre, alertes coloriales visibles
        p.update({
            "B": "#3a1008", "D": "#80301a", "I": "#a04030",
            "i": "#c85040", "G": "#C1554D", "g": "#e87060",
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
    EyeState.EVEILLE:  ("éveillé",  "data fraîche",                             "#D4A843"),
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
