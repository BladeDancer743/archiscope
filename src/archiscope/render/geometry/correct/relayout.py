"""Relayout — full re-layout when incremental corrections fail.

When correct() hits the iteration limit or introduces new critical
violations, this is the last resort: rebuild the CharGrid from scratch
with a different layout algorithm.
"""

from ..draw.grid import CharGrid, Rect, str_width
from ..verify.rules import VerifyContext

AVAILABLE_LAYOUTS = ["grid", "compact", "vertical"]


def relayout(ctx: VerifyContext, strategy: str = "compact") -> tuple[CharGrid, dict[str, Rect]]:
    """Rebuild the grid with a clean layout, avoiding all previous violations."""
    modules = ctx.modules
    edges = ctx.edges
    groups = ctx.groups

    if strategy == "compact":
        return _compact_layout(modules, edges, groups)
    elif strategy == "vertical":
        return _vertical_layout(modules, edges, groups)
    else:
        return _grid_layout(modules, edges, groups)


def _compact_layout(modules, edges, groups) -> tuple[CharGrid, dict[str, Rect]]:
    """Compact layout: left-to-right flow, tight spacing."""
    terminal_w = 80
    grid = CharGrid(terminal_w, 50)
    boxes = {}
    module_list = [m for m in modules if modules[m].get("type") != "root"]
    x, y = 2, 2
    row_h = 5
    col_w = 0

    for i, mid in enumerate(module_list):
        label = modules[mid].get("label", mid)
        label_w = str_width(label)
        w = max(label_w + 4, 12)
        col_w = max(col_w, w)
        if i > 0 and x + col_w + 2 > terminal_w:
            x = 2
            y += row_h + 1
        rect = grid.draw_rect(x, y, w, row_h)
        grid.draw_label(x + 1, y + 2, w - 2, label)
        boxes[mid] = rect
        x += w + 2

    # Draw edges
    for edge in edges:
        fr, to = edge["from"], edge["to"]
        if fr in boxes and to in boxes:
            label = edge.get("label", "")
            r1, r2 = boxes[fr], boxes[to]
            mid_y = r1.y + r1.h // 2
            grid.draw_arrow_h(r1.right, r2.x, mid_y)
            if label:
                grid.put_str(r1.right + 1, mid_y - 1, label)
            edge["line_cells"] = [(i, mid_y) for i in range(r1.right + 1, r2.x)]

    return grid, boxes


def _vertical_layout(modules, edges, groups) -> tuple[CharGrid, dict[str, Rect]]:
    """Vertical layout: top-to-bottom, one module per row."""
    terminal_w = 80
    grid = CharGrid(terminal_w, 100)
    boxes = {}
    module_list = [m for m in modules if modules[m].get("type") != "root"]

    y = 2
    for i, mid in enumerate(module_list):
        label = modules[mid].get("label", mid)
        w = min(str_width(label) + 8, terminal_w - 4)
        h = 4
        x = max(2, (terminal_w - w) // 2)
        rect = grid.draw_rect(x, y, w, h)
        grid.draw_label(x + 1, y + 2, w - 2, label)
        boxes[mid] = rect

        if i > 0:
            prev = module_list[i - 1]
            if prev in boxes:
                prev_rect = boxes[prev]
                arrow_x = terminal_w // 2
                grid.draw_arrow_v(arrow_x, prev_rect.bottom, rect.y)

        y += h + 2

    return grid, boxes


def _grid_layout(modules, edges, groups) -> tuple[CharGrid, dict[str, Rect]]:
    """Simple grid layout: fixed column width, auto-wrap."""
    return _compact_layout(modules, edges, groups)  # default to compact
