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


# ── Default theme — Tailwind 500-level palette rendered as truecolor.
#    One continuous hue wheel (blue → cyan → green → amber → orange →
#    red → violet), uniform saturation and lightness, every semantic role
#    a distinct color. Structural glyphs remain sufficient when colors
#    are removed.
DEFAULT_COLORS = {
    "data": "38;2;59;130;246",      # blue-500
    "command": "38;2;249;115;22",   # orange-500
    "authority": "38;2;139;92;246",  # violet-500
    "event": "38;2;16;185;129",     # emerald-500
    "reference": "38;2;148;163;184",  # slate-400
    "orchestration": "38;2;6;182;212",  # cyan-500
    "compute": "38;2;245;158;11",   # amber-500
    "state": "38;2;20;184;166",     # teal-500
    "boundary": "38;2;14;165;233",  # sky-500
    "delivery": "38;2;244;63;94",   # rose-500
    "assurance": "38;2;239;68;68",  # red-500 — violations
    "neutral": "38;2;100;116;139",  # slate-500 — unclassified
    "focus": "1;38;2;251;191;36",   # amber-400, bold
    "heading": "1;38;2;226;232;240",  # slate-200, bold
    "edge": "38;2;56;189;248",      # sky-400 — geometry relation lines
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
    "data": "38;2;120;222;232",
    "command": "38;2;252;152;103",
    "authority": "38;2;171;157;242",
    "event": "38;2;169;220;118",
    "reference": "38;2;117;113;94",
    "orchestration": "38;2;102;217;239",
    "compute": "38;2;255;216;102",
    "state": "38;2;166;226;46",
    "boundary": "38;2;94;217;225",
    "delivery": "38;2;255;97;136",
    "assurance": "38;2;249;38;114",
    "neutral": "38;2;128;125;116",
    "focus": "1;38;2;255;216;102",
    "heading": "1;38;2;252;252;250",
    "edge": "38;2;110;215;188",
}

# Solarized (dark background #002B36): low-contrast scientific palette.
SOLARIZED_COLORS = {
    "data": "38;2;38;139;210",
    "command": "38;2;203;75;22",
    "authority": "38;2;108;113;196",
    "event": "38;2;133;153;0",
    "reference": "38;2;147;161;161",
    "orchestration": "38;2;42;161;152",
    "compute": "38;2;181;137;0",
    "state": "38;2;84;171;158",
    "boundary": "38;2;42;160;181",
    "delivery": "38;2;211;54;130",
    "assurance": "38;2;220;50;47",
    "neutral": "38;2;101;123;131",
    "focus": "1;38;2;181;137;0",
    "heading": "1;38;2;238;232;213",
    "edge": "38;2;38;160;170",
}

# Dracula (background #282A36): purple/cyan/pink with high saturation.
DRACULA_COLORS = {
    "data": "38;2;139;233;253",
    "command": "38;2;255;184;108",
    "authority": "38;2;189;147;249",
    "event": "38;2;80;250;123",
    "reference": "38;2;98;114;164",
    "orchestration": "38;2;94;229;255",
    "compute": "38;2;241;250;140",
    "state": "38;2;61;224;160",
    "boundary": "38;2;123;224;240",
    "delivery": "38;2;255;121;198",
    "assurance": "38;2;255;85;85",
    "neutral": "38;2;68;71;90",
    "focus": "1;38;2;241;250;140",
    "heading": "1;38;2;248;248;242",
    "edge": "38;2;107;228;224",
}

# Nord (background #2E3440): cold blue/cyan palette, low glare.
NORD_COLORS = {
    "data": "38;2;129;161;193",
    "command": "38;2;208;135;112",
    "authority": "38;2;180;142;173",
    "event": "38;2;163;190;140",
    "reference": "38;2;216;222;233",
    "orchestration": "38;2;136;192;208",
    "compute": "38;2;235;203;139",
    "state": "38;2;150;184;160",
    "boundary": "38;2;143;188;187",
    "delivery": "38;2;217;139;95",
    "assurance": "38;2;191;97;106",
    "neutral": "38;2;76;86;106",
    "focus": "1;38;2;235;203;139",
    "heading": "1;38;2;236;239;244",
    "edge": "38;2;127;184;200",
}

# ── CRT phosphor themes — monochrome tubes, intensity instead of hue ──

# P1 phosphor green (#33FF33 class).  Every semantic role is a green-family
# shade; brightness and weight carry the distinction like a real terminal.
CRT_GREEN_COLORS = {
    "data": "38;2;0;255;135",
    "command": "38;2;0;255;95",
    "authority": "38;2;135;215;0",
    "event": "38;2;175;255;0",
    "reference": "38;2;0;215;95",
    "orchestration": "38;2;51;255;102",
    "compute": "38;2;215;255;0",
    "state": "38;2;102;255;51",
    "boundary": "38;2;0;230;118",
    "delivery": "38;2;0;255;150",
    "assurance": "38;2;135;255;0",
    "neutral": "38;2;0;180;80",
    "focus": "1;38;2;0;255;60",
    "heading": "1;38;2;0;255;0",
    "edge": "38;2;0;255;118",
}

# Amber phosphor (#FFB000 class) — the classic radar/terminal amber.
CRT_AMBER_COLORS = {
    "data": "38;2;255;175;0",
    "command": "38;2;255;215;0",
    "authority": "38;2;215;175;0",
    "event": "38;2;255;255;135",
    "reference": "38;2;215;135;0",
    "orchestration": "38;2;255;190;64",
    "compute": "38;2;255;215;95",
    "state": "38;2;240;200;64",
    "boundary": "38;2;255;160;0",
    "delivery": "38;2;255;220;130",
    "assurance": "38;2;255;95;0",
    "neutral": "38;2;180;120;20",
    "focus": "1;38;2;255;215;95",
    "heading": "1;38;2;255;228;181",
    "edge": "38;2;255;185;40",
}

# Synthwave — neon magenta/cyan/purple on a deep blue-black tube.
SYNTHWAVE_COLORS = {
    "data": "38;2;0;215;255",
    "command": "38;2;255;95;175",
    "authority": "38;2;175;135;255",
    "event": "38;2;135;255;255",
    "reference": "38;2;135;135;255",
    "orchestration": "38;2;1;205;254",
    "compute": "38;2;255;215;95",
    "state": "38;2;5;255;161",
    "boundary": "38;2;1;190;255",
    "delivery": "38;2;255;113;206",
    "assurance": "38;2;255;0;255",
    "neutral": "38;2;100;90;160",
    "focus": "1;38;2;255;113;206",
    "heading": "1;38;2;0;255;255",
    "edge": "38;2;0;224;255",
}

# Gruvbox dark (#282828) — warm, low-glare palette.
GRUVBOX_COLORS = {
    "data": "38;2;131;165;152",
    "command": "38;2;254;128;25",
    "authority": "38;2;211;134;155",
    "event": "38;2;184;187;38",
    "reference": "38;2;146;131;116",
    "orchestration": "38;2;142;192;124",
    "compute": "38;2;250;189;47",
    "state": "38;2;152;196;86",
    "boundary": "38;2;102;172;150",
    "delivery": "38;2;251;73;52",
    "assurance": "38;2;204;36;29",
    "neutral": "38;2;124;111;100",
    "focus": "1;38;2;250;189;47",
    "heading": "1;38;2;235;219;178",
    "edge": "38;2;156;192;138",
}

# Tokyo Night (#1A1B26) — cool blue-violet, high clarity.
TOKYONIGHT_COLORS = {
    "data": "38;2;122;162;247",
    "command": "38;2;255;158;100",
    "authority": "38;2;187;154;247",
    "event": "38;2;158;206;106",
    "reference": "38;2;169;177;214",
    "orchestration": "38;2;125;207;255",
    "compute": "38;2;224;175;104",
    "state": "38;2;110;218;120",
    "boundary": "38;2;112;196;255",
    "delivery": "38;2;247;118;142",
    "assurance": "38;2;255;0;124",
    "neutral": "38;2;59;66;82",
    "focus": "1;38;2;224;175;104",
    "heading": "1;38;2;192;202;245",
    "edge": "38;2;122;197;255",
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


def heat_style(count: int) -> str | None:
    """Style key for a coupling level: hot modules stand out."""
    if count >= 5:
        return "assurance"
    if count >= 3:
        return "command"
    if count >= 2:
        return "compute"
    if count >= 1:
        return "reference"
    return None


# Backward-compatible module-level exports — the default theme's tables.
ANSI_COLORS = DEFAULT_COLORS
TYPE_COLOR = DEFAULT_TYPE_COLORS
