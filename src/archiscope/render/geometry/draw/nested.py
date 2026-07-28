"""Nested box renderer — grouped, swimlane, onion views.

All three strategies share the same underlying geometry: boxes inside boxes.
"""

from ..correct.engine import correct
from ..draw.grid import CharGrid, str_width
from ..verify.rules import VerifyContext


def render_nested(ctx: VerifyContext, style: str = "grouped") -> str:
    """Render modules in nested group boxes.

    style: "grouped" (color-coded groups), "swimlane" (horizontal lanes),
           "onion" (concentric layers)
    """
    modules = ctx.modules
    groups = ctx.groups
    edges = ctx.edges

    if not any(members for members in groups.values()):
        # No explicit `groups:` on the focus module — synthesize one group per
        # module type so these views render without extra YAML config.
        groups = {}
        for mid, mod in modules.items():
            groups.setdefault(mod.get("type", "module"), []).append(mid)

    terminal_w = ctx.terminal_width
    grid = CharGrid(terminal_w, 60)
    boxes = {}

    # Build layout
    y = 2
    group_boxes = {}

    for group_name, members in groups.items():
        group_cfg = modules.get(group_name, {})
        label = group_cfg.get("label", group_name)
        member_count = len(members)
        if member_count == 0:
            continue

        # Determine group box size
        member_w = max(str_width(modules.get(m, {}).get("label", m)) for m in members)
        box_w = member_w + 6
        col_count = min(member_count, max(1, (terminal_w - 6) // (box_w + 2)))
        row_count = (member_count + col_count - 1) // col_count
        group_w = col_count * (box_w + 2) + 2
        group_h = row_count * 6 + 4

        # Draw group box
        box_style = "double" if style == "grouped" else "single"
        gr = grid.draw_rect(2, y, group_w, group_h, style=box_style)
        grid.draw_label(4, y, group_w - 4, label)
        group_boxes[group_name] = gr

        # Draw members inside
        for i, mid in enumerate(members):
            col = i % col_count
            row = i // col_count
            mx = 4 + col * (box_w + 2)
            my = y + 2 + row * 6
            ml = modules.get(mid, {}).get("label", mid)
            mr = grid.draw_rect(mx, my, box_w, 4)
            grid.draw_label(mx + 1, my + 2, box_w - 2, ml)
            boxes[mid] = mr

        y += group_h + 2

    # Draw edges with labels
    for edge in edges:
        fr, to = edge["from"], edge["to"]
        if fr in boxes and to in boxes:
            label = edge.get("label", "")
            r1, r2 = boxes[fr], boxes[to]
            mid_y1 = r1.y + r1.h // 2
            r2.y + r2.h // 2
            if abs(r1.x - r2.x) < 10:
                # Vertical edge
                grid.draw_arrow_v(r1.x + r1.w // 2, r1.bottom, r2.y)
            else:
                # Horizontal edge
                grid.draw_arrow_h(r1.right, r2.x, mid_y1)
                if label:
                    grid.put_str(r1.right + 2, mid_y1 - 1, label)
            edge["line_cells"] = []

    # Run verify + correct
    vctx = VerifyContext(
        grid=grid,
        boxes=boxes,
        edges=edges,
        groups=groups,
        modules=modules,
        terminal_width=terminal_w,
    )
    result = correct(vctx)

    return result.grid.render()
