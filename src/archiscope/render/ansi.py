"""Shared ANSI color infrastructure for terminal and geometry renderers.

Both renderers emit box-drawing characters plus optional ANSI foreground
colors. The color map lives here so the terminal overview and the geometry
strategies stay visually consistent.
"""

import os
import re
import sys
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


# Semantic foreground colors, shared by the terminal overview and the
# geometry strategies. Keys are style names; values are ANSI SGR codes.
ANSI_COLORS = {
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

# Module type → color key, used by the geometry strategies. ``None`` keeps
# the default terminal foreground.
TYPE_COLOR = {
    "root": "heading",
    "engine": "compute",
    "layer": "data",
    "module": "event",
    "rule": "authority",
    "function": "orchestration",
}
