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

# ── CRT phosphor themes — monochrome tubes, intensity instead of hue ──

# P1 phosphor green (#33FF33 class).  Every semantic role is a green-family
# shade; brightness and weight carry the distinction like a real terminal.
CRT_GREEN_COLORS = {
    "data": "38;5;48",       # phosphor green #00FF87
    "command": "38;5;82",    # bright green #00FF5F
    "authority": "38;5;112",  # yellow-green #87D700
    "event": "38;5;154",     # lime #AFFF00
    "reference": "38;5;41",  # dim green #00D75F
    "orchestration": "38;5;48",
    "compute": "38;5;190",   # pale yellow-green #D7FF00
    "state": "38;5;154",
    "boundary": "38;5;48",
    "delivery": "38;5;82",
    "assurance": "38;5;118",  # hot lime #87FF00
    "neutral": "38;5;41",
    "focus": "1;38;5;46",    # burning green, bold
    "heading": "1;38;5;46",
    "edge": "38;5;48",
}

# Amber phosphor (#FFB000 class) — the classic radar/terminal amber.
CRT_AMBER_COLORS = {
    "data": "38;5;214",      # amber #FFAF00
    "command": "38;5;220",   # bright amber #FFD700
    "authority": "38;5;178",  # mustard #D7AF00
    "event": "38;5;228",     # pale amber #FFFF87
    "reference": "38;5;172",  # dim amber #D78700
    "orchestration": "38;5;214",
    "compute": "38;5;221",   # light amber #FFD75F
    "state": "38;5;228",
    "boundary": "38;5;214",
    "delivery": "38;5;220",
    "assurance": "38;5;202",  # hot orange #FF5F00
    "neutral": "38;5;172",
    "focus": "1;38;5;221",
    "heading": "1;38;5;228",
    "edge": "38;5;214",
}

# Synthwave — neon magenta/cyan/purple on a deep blue-black tube.
SYNTHWAVE_COLORS = {
    "data": "38;5;45",       # neon cyan #00D7FF
    "command": "38;5;207",   # hot pink #FF5FAF
    "authority": "38;5;141",  # neon purple #AF87FF
    "event": "38;5;123",     # electric cyan #87FFFF
    "reference": "38;5;105",  # blue-violet #8787FF
    "orchestration": "38;5;45",
    "compute": "38;5;221",   # sunset yellow #FFD75F
    "state": "38;5;123",
    "boundary": "38;5;45",
    "delivery": "38;5;207",
    "assurance": "38;5;201",  # magenta #FF00FF
    "neutral": "38;5;105",
    "focus": "1;38;5;207",
    "heading": "1;38;5;51",  # white-cyan #00FFFF
    "edge": "38;5;45",
}

# Gruvbox dark (#282828) — warm, low-glare palette.
GRUVBOX_COLORS = {
    "data": "38;5;110",      # blue #83A598
    "command": "38;5;208",   # orange #FE8019
    "authority": "38;5;175",  # purple #D3869B
    "event": "38;5;142",     # green #B8BB26
    "reference": "38;5;244",  # gray #928374
    "orchestration": "38;5;108",  # aqua #8EC07C
    "compute": "38;5;214",   # yellow #FABD2F
    "state": "38;5;142",
    "boundary": "38;5;108",
    "delivery": "38;5;208",
    "assurance": "38;5;209",  # red #FB4934
    "neutral": "38;5;244",
    "focus": "1;38;5;214",
    "heading": "1;38;5;251",
    "edge": "38;5;108",
}

# Tokyo Night (#1A1B26) — cool blue-violet, high clarity.
TOKYONIGHT_COLORS = {
    "data": "38;5;69",       # blue #7AA2F7
    "command": "38;5;209",   # orange-pink #FF9E64
    "authority": "38;5;141",  # purple #BB9AF7
    "event": "38;5;150",     # green #9ECE6A
    "reference": "38;5;146",  # gray-blue #A9B1D6
    "orchestration": "38;5;75",  # cyan #7DCFFF
    "compute": "38;5;180",   # yellow #E0AF68
    "state": "38;5;150",
    "boundary": "38;5;75",
    "delivery": "38;5;209",
    "assurance": "38;5;204",  # pink #F7768E
    "neutral": "38;5;146",
    "focus": "1;38;5;180",
    "heading": "1;38;5;254",
    "edge": "38;5;75",
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
    "crt-green": Theme(
        "crt-green",
        "CRT 磷光绿（P1 phosphor），单色管亮度分级",
        CRT_GREEN_COLORS,
        DEFAULT_TYPE_COLORS,
    ),
    "crt-amber": Theme(
        "crt-amber",
        "CRT 琥珀磷光（#FFB000 类），雷达/终端经典琥珀",
        CRT_AMBER_COLORS,
        DEFAULT_TYPE_COLORS,
    ),
    "synthwave": Theme(
        "synthwave",
        "Synthwave 霓虹（深蓝黑底），品红/青/紫",
        SYNTHWAVE_COLORS,
        DEFAULT_TYPE_COLORS,
    ),
    "gruvbox": Theme(
        "gruvbox",
        "Gruvbox 暗色（#282828），暖调低眩光",
        GRUVBOX_COLORS,
        DEFAULT_TYPE_COLORS,
    ),
    "tokyonight": Theme(
        "tokyonight",
        "Tokyo Night（#1A1B26），冷蓝紫高清晰",
        TOKYONIGHT_COLORS,
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
