"""Nested box renderer — grouped, swimlane, onion views.

All three strategies share the same underlying geometry: boxes inside boxes.
"""

from ...ansi import TYPE_COLOR, resolve_theme
from ..correct.engine import correct
from ..draw.grid import CharGrid, str_width
from ..verify.rules import VerifyContext


def _module_color(ctx: VerifyContext, mid: str) -> str | None:
    """Frame color for one module: focus highlight wins, then type color."""
    if mid == ctx.focus:
        return "focus"
    module_type = ctx.modules.get(mid, {}).get("type", "module")
    return TYPE_COLOR.get(module_type)


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
        label = ctx.group_labels.get(group_name, group_name)
        member_count = len(members)
        if member_count == 0:
            continue

        # Frame color follows the group's single module type when the members
        # share one (synthesized type-groups always do). Keeping the frame and
        # its members on one color run means every row is a single ANSI
        # segment — some terminal renderers mis-measure rows with three or
        # more color switches (CJK-aware width bugs).
        member_types = {modules.get(m, {}).get("type") for m in members}
        if len(member_types) == 1:
            group_color = TYPE_COLOR.get(next(iter(member_types)))
        else:
            group_color = "boundary"

        # Determine group box size
        member_w = max(str_width(modules.get(m, {}).get("label", m)) for m in members)
        box_w = member_w + 6
        col_count = min(member_count, max(1, (terminal_w - 6) // (box_w + 2)))
        row_count = (member_count + col_count - 1) // col_count
        group_w = col_count * (box_w + 2) + 2
        group_h = row_count * 6 + 4

        # Draw group box; the label goes one row inside the top border so
        # the frame stays closed (G4_frame_closure).  The label is anchored
        # to the frame's center column, rounding up so odd-width labels sit
        # consistently half a cell right instead of drifting left by one.
        box_style = "double" if style == "grouped" else "single"
        gr = grid.draw_rect(2, y, group_w, group_h, style=box_style, color=group_color)
        label_x = 2 + (group_w - str_width(label) + 1) // 2
        grid.draw_label(
            label_x, y + 1, group_w - label_x, label, align="left", color=group_color
        )
        group_boxes[group_name] = gr

        # Draw members inside
        for i, mid in enumerate(members):
            col = i % col_count
            row = i // col_count
            mx = 4 + col * (box_w + 2)
            my = y + 2 + row * 6
            ml = modules.get(mid, {}).get("label", mid)
            color = _module_color(ctx, mid)
            mr = grid.draw_rect(mx, my, box_w, 4, color=color)
            grid.draw_label(mx + 1, my + 2, box_w - 2, ml, color=color)
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
                grid.draw_arrow_v(
                    r1.x + r1.w // 2, r1.bottom, r2.y, color=_module_color(ctx, fr)
                )
            else:
                # Horizontal edge
                grid.draw_arrow_h(r1.right, r2.x, mid_y1, color=_module_color(ctx, fr))
                if label:
                    grid.put_str(
                        r1.right + 2, mid_y1 - 1, label, color=_module_color(ctx, fr)
                    )
            edge["line_cells"] = []

    # Run verify + correct. Only *declared* groups (from the archmap) are
    # verified — synthesized type-groups carry no YAML contract, so rules like
    # S4_group_orphan / G0e_misaligned would flag every member for free.
    vctx = VerifyContext(
        grid=grid,
        boxes=boxes,
        edges=edges,
        groups=ctx.groups,
        modules=modules,
        terminal_width=terminal_w,
        focus=ctx.focus,
        color=ctx.color,
    )
    result = correct(vctx)
    rendered = (
        result.grid.render_ansi(resolve_theme(ctx.theme).colors)
        if ctx.color
        else result.grid.render()
    )
    if ctx.group_labels:
        heading = "LANES / 泳道" if style == "swimlane" else "GROUPS / 分组"
        legend = [heading]
        for group_name, members in groups.items():
            label = ctx.group_labels.get(group_name, group_name)
            member_labels = [modules.get(member, {}).get("label", member) for member in members]
            legend.append(f"  {label}: {', '.join(member_labels)}")
        return "\n".join(legend) + "\n\n" + rendered
    return rendered
