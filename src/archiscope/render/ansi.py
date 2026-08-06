"""Shared ANSI color infrastructure for terminal and geometry renderers.

Both renderers emit box-drawing characters plus optional ANSI foreground
colors. Color *style names* stay stable across themes — the semantic
vocabulary (data/command/authority/…, module types) — while each theme maps
those names to concrete ANSI SGR codes, so the terminal overview and the
geometry strategies stay visually consistent and switchable together.
"""

import os
import re
import sys
from dataclasses import dataclass, field
from typing import Mapping, TextIO

ANSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


class TerminalRenderError(ValueError):
    """The requested view cannot be rendered safely."""


def strip_ansi(value: str) -> str:
    """Remove ANSI control sequences from a rendered view."""

    return ANSI_RE.sub("", value)


def color_enabled(
    mode: str,
    *,
    stream: TextIO | None = None,
    isatty: bool | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    """Resolve ``auto|always|never`` without letting env override explicit modes."""

    if mode == "always":
        return True
    if mode == "never":
        return False
    if mode != "auto":
        raise TerminalRenderError(f"Unknown color mode '{mode}'")

    environment = os.environ if env is None else env
    if "NO_COLOR" in environment or environment.get("TERM", "").lower() == "dumb":
        return False
    output = stream or sys.stdout
    tty = bool(output.isatty()) if isatty is None else isatty
    return tty


@dataclass(frozen=True)
class Theme:
    """One color scheme: semantic style names → ANSI SGR codes.

    ``type_colors`` maps module types to *style names* (resolved through
    ``colors``), so themes can recolour both relation lines and module frames
    with a single table.
    """

    name: str
    description: str
    colors: Mapping[str, str] = field(default_factory=dict)
    type_colors: Mapping[str, str | None] = field(default_factory=dict)


# ── Default theme — Okabe-Ito-inspired foreground-only colors. Structural
#    glyphs and textual tags remain sufficient when colors are removed.
DEFAULT_COLORS = {
    "data": "38;5;33",
    "command": "38;5;208",
    "authority": "38;5;129",
    "event": "38;5;35",
    "reference": "38;5;245",
    "orchestration": "38;5;37",
    "compute": "38;5;220",
    "state": "38;5;35",
    "boundary": "38;5;44",
    "delivery": "38;5;208",
    "assurance": "38;5;162",
    "neutral": "38;5;245",
    "focus": "1;38;5;220",
    "heading": "1;38;5;250",
    "edge": "38;5;37",  # geometry relation lines
}

DEFAULT_TYPE_COLORS = {
    "root": "heading",
    "engine": "compute",
    "layer": "data",
    "module": "event",
    "rule": "authority",
    "function": "orchestration",
}

# ── Additional themes ──

# Monokai (background #272822): saturated orange/pink/green/cyan palette.
MONOKAI_COLORS = {
    "data": "38;5;81",       # cyan #66D9EF
    "command": "38;5;208",   # orange #FD971F
    "authority": "38;5;141",  # purple #AE81FF
    "event": "38;5;148",     # green #A6E22E
    "reference": "38;5;242",  # gray #75715E
    "orchestration": "38;5;81",
    "compute": "38;5;186",   # yellow #E6DB74
    "state": "38;5;148",
    "boundary": "38;5;81",
    "delivery": "38;5;208",
    "assurance": "38;5;161",  # pink #F92672
    "neutral": "38;5;242",
    "focus": "1;38;5;186",
    "heading": "1;38;5;248",
    "edge": "38;5;81",
}

# Solarized (dark background #002B36): low-contrast scientific palette.
SOLARIZED_COLORS = {
    "data": "38;5;68",       # blue #268BD2
    "command": "38;5;167",   # orange #CB4B16
    "authority": "38;5;62",  # violet #6C71C4
    "event": "38;5;100",     # green #859900
    "reference": "38;5;109",  # base0 #839496
    "orchestration": "38;5;37",  # cyan #2AA198
    "compute": "38;5;136",   # yellow #B58900
    "state": "38;5;100",
    "boundary": "38;5;37",
    "delivery": "38;5;167",
    "assurance": "38;5;160",  # red #DC322F
    "neutral": "38;5;109",
    "focus": "1;38;5;136",
    "heading": "1;38;5;245",
    "edge": "38;5;37",
}

# Dracula (background #282A36): purple/cyan/pink with high saturation.
DRACULA_COLORS = {
    "data": "38;5;117",      # cyan #8BE9FD
    "command": "38;5;212",   # pink #FF79C6
    "authority": "38;5;141",  # purple #BD93F9
    "event": "38;5;84",      # green #50FA7B
    "reference": "38;5;62",  # blue-gray #6272A4
    "orchestration": "38;5;117",
    "compute": "38;5;228",   # yellow #F1FA8C
    "state": "38;5;84",
    "boundary": "38;5;117",
    "delivery": "38;5;212",
    "assurance": "38;5;212",
    "neutral": "38;5;62",
    "focus": "1;38;5;228",
    "heading": "1;38;5;252",
    "edge": "38;5;117",
}

# Nord (background #2E3440): cold blue/cyan palette, low glare.
NORD_COLORS = {
    "data": "38;5;109",      # blue #81A1C1
    "command": "38;5;173",   # orange #D08770
    "authority": "38;5;139",  # purple #B48EAD
    "event": "38;5;108",     # green #A3BE8C
    "reference": "38;5;145",  # gray #D8DEE9
    "orchestration": "38;5;110",  # cyan #88C0D0
    "compute": "38;5;179",   # yellow #EBCB8B
    "state": "38;5;108",
    "boundary": "38;5;110",
    "delivery": "38;5;173",
    "assurance": "38;5;139",
    "neutral": "38;5;145",
    "focus": "1;38;5;179",
    "heading": "1;38;5;255",
    "edge": "38;5;110",
}

THEMES: dict[str, Theme] = {
    "default": Theme(
        "default",
        "Okabe-Ito 启发的前景色，深色终端默认",
        DEFAULT_COLORS,
        DEFAULT_TYPE_COLORS,
    ),
    "monokai": Theme(
        "monokai",
        "Monokai 风格（#272822 背景），饱和橙/粉/绿/青",
        MONOKAI_COLORS,
        DEFAULT_TYPE_COLORS,
    ),
    "solarized": Theme(
        "solarized",
        "Solarized 暗色（#002B36 背景），低对比科学配色",
        SOLARIZED_COLORS,
        DEFAULT_TYPE_COLORS,
    ),
    "dracula": Theme(
        "dracula",
        "Dracula 风格（#282A36 背景），紫/青/粉高饱和",
        DRACULA_COLORS,
        DEFAULT_TYPE_COLORS,
    ),
    "nord": Theme(
        "nord",
        "Nord 冷色（#2E3440 背景），蓝青为主低眩光",
        NORD_COLORS,
        DEFAULT_TYPE_COLORS,
    ),
}


def resolve_theme(name: str) -> Theme:
    """Look up a theme by name, raising for unknown names."""
    theme = THEMES.get(name)
    if theme is None:
        available = ", ".join(THEMES)
        raise TerminalRenderError(f"Unknown theme '{name}'. Available: {available}")
    return theme


# Backward-compatible module-level exports — the default theme's tables.
ANSI_COLORS = DEFAULT_COLORS
TYPE_COLOR = DEFAULT_TYPE_COLORS
