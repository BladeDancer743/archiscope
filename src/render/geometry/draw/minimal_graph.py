"""Minimal renderer — pure box-drawing graph with no subgraphs or colors."""

from ..draw.grid import CharGrid, Rect, str_width, pad_str
from ..verify.rules import VerifyContext


def render_minimal(ctx: VerifyContext) -> str:
    """Simple box-drawing graph: nodes + directed arrows. No subgraph, no color."""
    modules = ctx.modules
    edges = ctx.edges
    terminal_w = ctx.terminal_width

    module_list = [m for m in modules if modules[m].get("type") != "root"]
    if not module_list:
        return "No modules."

    n = len(module_list)
    grid = CharGrid(terminal_w, 60)
    boxes = {}
    label_w = max((str_width(modules[m].get("label", m)) for m in module_list), default=10)

    # Layout: 2 columns
    cols = max(1, (terminal_w - 4) // (label_w + 16))
    x, y = 4, 2
    col_w = label_w + 12

    for i, mid in enumerate(module_list):
        if i > 0 and i % cols == 0:
            x = 4
            y += 6
        label = modules[mid].get("label", mid)
        rect = grid.draw_rect(x, y, col_w, 4)
        grid.draw_label(x + 1, y + 2, col_w - 2, label)
        boxes[mid] = rect
        x += col_w + 3

    # Draw edges
    for edge in edges:
        fr, to = edge["from"], edge["to"]
        if fr in boxes and to in boxes:
            label = edge.get("label", "")
            r1, r2 = boxes[fr], boxes[to]
            my1 = r1.y + r1.h // 2
            my2 = r2.y + r2.h // 2
            if abs(r1.x - r2.x) < 10:
                grid.draw_arrow_v(r1.x + r1.w // 2, r1.bottom, r2.y)
            else:
                grid.draw_arrow_h(r1.right, r2.x, my1)
                if label:
                    grid.put_str(r1.right + 1, my1 - 1, label)

    return grid.render()
