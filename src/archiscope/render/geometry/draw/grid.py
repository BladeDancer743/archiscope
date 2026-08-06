"""Character grid system — the foundation for all geometry rendering.

Every rendered diagram is a CharGrid: a 2D array of characters with
coordinated placement of boxes, lines, labels, and arrows.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Mapping

ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def char_width(ch: str) -> int:
    """Return terminal-cell width for one Unicode code point."""
    if not ch or ch in {"\n", "\r"}:
        return 0
    if len(ch) > 1:
        return sum(char_width(character) for character in ch)
    category = unicodedata.category(ch)
    if unicodedata.combining(ch) or category in {"Cc", "Cf", "Mn", "Me"}:
        return 0
    ea = unicodedata.east_asian_width(ch)
    return 2 if ea in ("F", "W") else 1


def str_width(s: str) -> int:
    """Total display width, ignoring ANSI styling and zero-width marks."""
    return sum(char_width(c) for c in ANSI_ESCAPE_RE.sub("", s))


def pad_str(s: str, target_width: int, align: str = "left") -> str:
    """Pad a string to target display width, accounting for CJK."""
    current = str_width(s)
    if current > target_width:
        s = truncate_str(s, target_width)
        current = str_width(s)
    if current == target_width:
        return s
    padding = target_width - current
    if align == "center":
        left = padding // 2
        right = padding - left
        return " " * left + s + " " * right
    elif align == "right":
        return " " * padding + s
    return s + " " * padding


def truncate_str(s: str, max_width: int, suffix: str = "…") -> str:
    """Truncate to max_width display cells, appending suffix."""
    if max_width <= 0:
        return ""
    if str_width(s) <= max_width:
        return s
    if str_width(suffix) > max_width:
        suffix = ""
    target = max_width - str_width(suffix)
    result = ""
    w = 0
    for ch in s:
        cw = char_width(ch)
        if w + cw > target:
            break
        result += ch
        w += cw
    return result + suffix


def split_lines(s: str, max_width: int) -> list[str]:
    """Split string into lines, each ≤ max_width display cells."""
    lines = []
    current = ""
    current_w = 0
    for word in s.split():
        word_w = str_width(word)
        if current_w + word_w + (1 if current else 0) <= max_width:
            current += (" " if current else "") + word
            current_w += word_w + (1 if current else 0)
        else:
            if current:
                lines.append(current)
            current = word
            current_w = word_w
    if current:
        lines.append(current)
    return lines if lines else [""]


#  ── Box Drawing Constants ──

SINGLE = {
    "tl": "┌",
    "tr": "┐",
    "bl": "└",
    "br": "┘",
    "h": "─",
    "v": "│",
    "t": "┬",
    "b": "┴",
    "l": "├",
    "r": "┤",
    "x": "┼",
}
DOUBLE = {
    "tl": "╔",
    "tr": "╗",
    "bl": "╚",
    "br": "╝",
    "h": "═",
    "v": "║",
    "t": "╦",
    "b": "╩",
    "l": "╠",
    "r": "╣",
    "x": "╬",
}
DASHED = {
    "tl": "┌",
    "tr": "┐",
    "bl": "└",
    "br": "┘",
    "h": "╌",
    "v": "┊",
    "t": "┬",
    "b": "┴",
    "l": "├",
    "r": "┤",
    "x": "┼",
}

ARROW_RIGHT = "▶"
ARROW_LEFT = "◀"
ARROW_DOWN = "▼"
ARROW_UP = "▲"

# Continuation sentinel: the second display column of a wide (CJK) character.
# Contributes nothing when the grid is rendered, so column indexes always
# equal terminal display columns.
CONT = ""
BLOCK_FULL = "█"
BLOCK_DARK = "▓"
BLOCK_MED = "▒"
BLOCK_LIGHT = "░"
BLOCK_DOT = "·"


@dataclass
class Rect:
    """A rectangular region in the character grid."""

    x: int
    y: int
    w: int = 0
    h: int = 0

    @property
    def right(self) -> int:
        return self.x + self.w

    @property
    def bottom(self) -> int:
        return self.y + self.h

    @property
    def inner_width(self) -> int:
        return max(0, self.w - 2)

    @property
    def inner_height(self) -> int:
        return max(0, self.h - 2)

    def overlaps(self, other: "Rect") -> bool:
        return (
            self.x < other.right
            and self.right > other.x
            and self.y < other.bottom
            and self.bottom > other.y
        )

    def contains_point(self, px: int, py: int) -> bool:
        return self.x <= px <= self.right and self.y <= py <= self.bottom

    def contains_rect(self, other: "Rect") -> bool:
        return (
            self.x <= other.x
            and self.right >= other.right
            and self.y <= other.y
            and self.bottom >= other.bottom
        )


@dataclass
class CharGrid:
    """2D character canvas with width/height bounds.

    Each cell carries an optional style name (parallel to ``cells``) so the
    geometry can be rendered in color afterwards. ``render()`` stays plain
    text — verify/correct rules read characters only — while ``render_ansi()``
    injects ANSI foreground codes without changing the geometry.
    """

    width: int
    height: int
    cells: list[list[str]] = field(default_factory=list)
    styles: list[list[str | None]] = field(default_factory=list)

    def __post_init__(self):
        self.cells = [[" " for _ in range(self.width)] for _ in range(self.height)]
        self.styles = [[None for _ in range(self.width)] for _ in range(self.height)]

    def _clear_cell(self, x: int, y: int):
        """Clear one display column, splitting any wide char that covers it."""
        cur = self.cells[y][x]
        if cur is CONT or cur == CONT:
            # x is the tail half of a wide char starting at x-1
            if x - 1 >= 0:
                self.cells[y][x - 1] = " "
                self.styles[y][x - 1] = None
        elif char_width(cur) == 2:
            # x is the head of a wide char whose tail sits at x+1
            if x + 1 < self.width:
                self.cells[y][x + 1] = " "
                self.styles[y][x + 1] = None
        self.cells[y][x] = " "
        self.styles[y][x] = None

    def put(self, x: int, y: int, ch: str, color: str | None = None):
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        cell_width = char_width(ch)
        if cell_width == 0:
            previous = x - 1
            if previous >= 0 and self.cells[y][previous] == CONT:
                previous -= 1
            if previous >= 0 and self.cells[y][previous] not in {" ", CONT}:
                self.cells[y][previous] += ch
            return
        if cell_width == 2:
            if x + 1 >= self.width:
                return  # wide char doesn't fit at the right edge
            self._clear_cell(x, y)
            self._clear_cell(x + 1, y)
            self.cells[y][x] = ch
            self.cells[y][x + 1] = CONT
            self.styles[y][x] = color
            self.styles[y][x + 1] = color
        else:
            self._clear_cell(x, y)
            self.cells[y][x] = ch
            self.styles[y][x] = color

    def put_str(self, x: int, y: int, s: str, color: str | None = None):
        cursor = x
        for ch in s:
            self.put(cursor, y, ch, color)
            cursor += char_width(ch)

    def get(self, x: int, y: int) -> str:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.cells[y][x]
        return " "

    # ── Drawing ──

    def draw_rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        style: str = "single",
        color: str | None = None,
    ):
        cs = SINGLE if style == "single" else (DOUBLE if style == "double" else DASHED)
        if w < 2 or h < 2:
            return Rect(x, y, w, h)
        self.put_str(x, y, cs["tl"] + cs["h"] * (w - 2) + cs["tr"], color)
        for row in range(1, h - 1):
            self.put(x, y + row, cs["v"], color)
            self.put(x + w - 1, y + row, cs["v"], color)
        self.put_str(x, y + h - 1, cs["bl"] + cs["h"] * (w - 2) + cs["br"], color)
        return Rect(x, y, w, h)

    def draw_label(
        self,
        x: int,
        y: int,
        w: int,
        label: str,
        align: str = "center",
        color: str | None = None,
    ):
        """Draw label inside a box at (x,y) with inner width w."""
        padded = pad_str(label, w, align)
        self.put_str(x, y, padded, color)

    def draw_hbar(
        self,
        x: int,
        y: int,
        width_chars: int,
        fill: float = 1.0,
        color: str | None = None,
    ):
        """Draw a horizontal bar: █ filled, ░ unfilled."""
        filled_cells = int(width_chars * fill)
        for i in range(width_chars):
            ch = BLOCK_FULL if i < filled_cells else BLOCK_LIGHT
            self.put(x + i, y, ch, color)

    def draw_arrow_h(self, x1: int, x2: int, y: int, color: str | None = None):
        """Draw a horizontal arrow from x1 to x2 at row y (head at x2)."""
        if x2 > x1:
            self.put_str(x1, y, "─" * (x2 - x1), color)
            self.put(x2, y, ARROW_RIGHT, color)
        elif x2 < x1:
            self.put_str(x2 + 1, y, "─" * (x1 - x2), color)
            self.put(x2, y, ARROW_LEFT, color)

    def draw_arrow_v(self, x: int, y1: int, y2: int, color: str | None = None):
        """Draw a vertical arrow from y1 to y2 at column x."""
        if y2 > y1:
            for i in range(y1, y2):
                self.put(x, i, "│", color)
            self.put(x, y2, ARROW_DOWN, color)
        elif y2 < y1:
            for i in range(y2, y1):
                self.put(x, i, "│", color)
            self.put(x, y2, ARROW_UP, color)

    def draw_tree_line(
        self,
        x: int,
        y: int,
        depth: int,
        is_last: bool,
        label: str,
        color: str | None = None,
    ):
        """Draw a tree node line: │  ├── label  or │  └── label."""
        for d in range(depth - 1):
            self.put(x + d * 2, y, "│", color)
        if depth > 0:
            self.put(x + (depth - 1) * 2, y, "└" if is_last else "├", color)
            self.put(x + (depth - 1) * 2 + 1, y, "─", color)
        self.put_str(x + depth * 2, y, label, color)

    # ── Resize ──

    def ensure_size(self, width: int, height: int):
        if width > self.width:
            for row in self.cells:
                row.extend([" "] * (width - self.width))
            for row in self.styles:
                row.extend([None] * (width - self.width))
            self.width = width
        if height > self.height:
            for _ in range(height - self.height):
                self.cells.append([" "] * self.width)
                self.styles.append([None] * self.width)
            self.height = height

    def shift_right(self, from_column: int, distance: int):
        """Shift all content right of from_column by distance cells."""
        new_width = self.width + distance
        for row in self.cells:
            row[from_column + distance : from_column + distance] = row[from_column:from_column]
            for _ in range(distance):
                row.insert(from_column, " ")
        for row in self.styles:
            row[from_column + distance : from_column + distance] = row[from_column:from_column]
            for _ in range(distance):
                row.insert(from_column, None)
        self.width = new_width

    # ── Render ──

    def render(self) -> str:
        lines = []
        for row in self.cells:
            # Trim trailing spaces per line
            line = "".join(row).rstrip()
            lines.append(line)
        # Drop trailing blank rows: grids are allocated with headroom
        # (e.g. nested.py uses a fixed 60-row canvas), and blank tail rows
        # are never meaningful content.
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines)

    def render_ansi(self, color_map: Mapping[str, str]) -> str:
        """Render with ANSI foreground colors, preserving the exact geometry.

        Runs of the same style merge into one escape sequence. Invariant:
        ``strip_ansi(render_ansi(color_map)) == render()``.
        """
        lines = []
        for y in range(self.height):
            pairs = [(self.cells[y][x], self.styles[y][x]) for x in range(self.width)]
            while pairs and pairs[-1][0] in (" ", ""):
                pairs.pop()
            parts: list[str] = []
            current: str | None = None
            for ch, style in pairs:
                if ch == CONT:
                    continue  # tail half of a wide char, printed with its head
                if style != current:
                    code = color_map.get(style) if style else None
                    if code:
                        parts.append(f"\x1b[{code}m")
                    elif current:
                        parts.append("\x1b[0m")
                    current = style if code else None
                parts.append(ch)
            if current:
                parts.append("\x1b[0m")
            lines.append("".join(parts))
        while lines and lines[-1] == "":
            lines.pop()
        return "\n".join(lines)

    def __str__(self) -> str:
        return self.render()
