"""Cards renderer — each module as a compact ASCII card, arranged horizontally.

Fits more modules on screen than the nested layout.
"""

from ..draw.grid import CharGrid, Rect, str_width, pad_str, truncate_str, BLOCK_FULL
from ..verify.rules import VerifyContext


def render_cards(ctx: VerifyContext) -> str:
    """Render each module as a compact card."""
    modules = ctx.modules
    edges = ctx.edges
    terminal_w = ctx.terminal_width

    module_list = [m for m in modules if modules[m].get("type") != "root"]
    if not module_list:
        return "No modules."

    n = len(module_list)
    card_w = min(30, (terminal_w - 4) // max(2, min(3, n // 2 + 1)))
    cols = max(1, (terminal_w - 2) // (card_w + 2))
    lines = []

    for i, mid in enumerate(module_list):
        module = modules[mid]
        label = module.get("label", mid)
        desc = module.get("description", "")
        upstream = module.get("upstream", [])
        downstream = module.get("downstream", [])

        col = i % cols
        row_start = i // cols * 8

        # Expand lines array
        while len(lines) <= row_start + 7:
            lines.append("")

        x0 = col * (card_w + 2)

        # Top border
        top = " " * x0 + "┌" + "─" * (card_w - 2) + "┐"
        _set_line(lines, row_start, x0, top)

        # Title
        title = " " * x0 + "│ " + pad_str(truncate_str(label, card_w - 4), card_w - 4) + " │"
        _set_line(lines, row_start + 1, x0, title)

        # Separator
        sep = " " * x0 + "├" + "─" * (card_w - 2) + "┤"
        _set_line(lines, row_start + 2, x0, sep)

        # Upstream count
        in_count = len(upstream)
        in_label = f"in:  {in_count}"
        in_line = " " * x0 + "│ " + pad_str(in_label, card_w - 4) + " │"
        _set_line(lines, row_start + 3, x0, in_line)

        # Downstream count
        out_count = len(downstream)
        out_label = f"out: {out_count}"
        out_line = " " * x0 + "│ " + pad_str(out_label, card_w - 4) + " │"
        _set_line(lines, row_start + 4, x0, out_line)

        # Description (truncated)
        if desc:
            short_desc = truncate_str(desc, card_w - 4)
            desc_line = " " * x0 + "│ " + pad_str(short_desc, card_w - 4) + " │"
            _set_line(lines, row_start + 5, x0, desc_line)

        # Bottom border
        bottom = " " * x0 + "└" + "─" * (card_w - 2) + "┘"
        _set_line(lines, row_start + 6, x0, bottom)

    return "\n".join(lines).rstrip()


def _set_line(lines: list, idx: int, x0: int, content: str):
    """Set content at line index, extending or padding as needed."""
    while len(lines) <= idx:
        lines.append("")
    existing = lines[idx]
    if len(existing) < x0:
        existing = existing.ljust(x0)
    lines[idx] = existing + content[x0:] if len(existing) >= x0 else content
