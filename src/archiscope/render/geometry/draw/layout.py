"""Layered topology layout — the geometric core for architecture diagrams.

Sugiyama-style pipeline: longest-path layering → barycenter ordering →
box placement (left-to-right, one column per layer) → orthogonal edge
routing with per-gap lanes. Long edges pass through corridor rows in the
intermediate columns, so lines never pierce boxes.
"""

from ...ansi import TYPE_COLOR, heat_style, resolve_theme
from ..verify.rules import VerifyContext
from .grid import ARROW_RIGHT, CharGrid, split_lines, str_width, truncate_str

MAX_LABEL_W = 24  # max display columns for a label line before wrapping
MAX_PER_COL = 5  # a layer with more nodes spills into an extra column
BOX_SPACING = 2  # blank rows between boxes in a column


def assign_layers(nodes: list[str], edges: list[dict]) -> dict[str, int]:
    """Longest-path layering. Back edges of cycles are ignored."""
    outgoing = {n: [] for n in nodes}
    for e in edges:
        if e["from"] in outgoing and e["to"] in outgoing:
            outgoing[e["from"]].append(e["to"])

    layer = {}
    state = {}  # 0=unvisited, 1=in stack, 2=done

    def visit(n, depth=0):
        if depth > len(nodes) + 1:
            return 0
        state[n] = 1
        best = 0
        for m in outgoing[n]:
            if state.get(m) == 1:
                continue  # back edge — skip to break the cycle
            if state.get(m) != 2:
                visit(m, depth + 1)
            best = max(best, layer.get(m, 0) + 1)
        layer[n] = max(layer.get(n, 0), best)
        state[n] = 2
        return layer[n]

    for n in nodes:
        if state.get(n) != 2:
            visit(n)

    # Longest-path puts sinks at 0; flip so sources sit on the left.
    max_l = max(layer.values(), default=0)
    return {node: max_l - level for node, level in layer.items()}


def order_within_layers(
    layers: list[list[str]], edges: list[dict], passes: int = 3
) -> list[list[str]]:
    """Barycenter ordering to reduce edge crossings."""
    pos = {}
    for col in layers:
        for i, n in enumerate(col):
            pos[n] = i

    neighbors_in = {}
    neighbors_out = {}
    for e in edges:
        neighbors_in.setdefault(e["to"], []).append(e["from"])
        neighbors_out.setdefault(e["from"], []).append(e["to"])

    def sweep(cols, neigh):
        for col in cols:

            def bary(n):
                ns = [pos[m] for m in neigh.get(n, []) if m in pos]
                return sum(ns) / len(ns) if ns else pos[n]

            col.sort(key=bary)
            for i, n in enumerate(col):
                pos[n] = i

    for _ in range(passes):
        sweep(layers[1:], neighbors_in)  # left-to-right
        sweep(layers[-2::-1], neighbors_out)  # right-to-left
    return layers


def _module_color(ctx: VerifyContext, mid: str) -> str | None:
    """Frame color: focus, then rule violations (assurance), then the
    selected design view (type/feature/heat); unclassified semantics stay
    gray in the type view."""
    if mid == ctx.focus:
        return "focus"
    if ctx.issues.get(mid):
        return "assurance"
    if ctx.color_by == "feature":
        return ctx.feature_families.get(mid, "neutral")
    if ctx.color_by == "heat":
        return heat_style(ctx.degrees.get(mid, 0))
    # The type view keeps the structural color; unclassified semantics are
    # signalled by the dashed frame instead.
    return TYPE_COLOR.get(ctx.modules.get(mid, {}).get("type", "module"))


def _module_frame(ctx: VerifyContext, mid: str) -> str:
    """Box style: dashed marks violations and unclassified semantics."""
    if ctx.issues.get(mid):
        return "dashed"
    if ctx.color_by == "type" and ctx.feature_families.get(mid) == "neutral":
        return "dashed"
    return "single"


def render_topology(ctx: VerifyContext, style: str = "flow") -> str:
    """Render modules as a layered left-to-right topology diagram.

    style: "flow" (edge labels as a numbered legend) or "minimal" (bare).
    The focus module (ctx.focus) gets a double border.
    """
    modules = ctx.modules
    nodes = [m for m in modules if modules[m].get("type") != "root"]
    if not nodes:
        return "No modules."
    edges = [e for e in ctx.edges if e["from"] in modules and e["to"] in modules]

    focus = getattr(ctx, "focus", None)

    # ── 1. Layering ──
    layer_of = assign_layers(nodes, edges)
    n_layers = max(layer_of.values(), default=0) + 1
    layers = [[] for _ in range(n_layers)]
    for n in nodes:
        layers[layer_of[n]].append(n)

    # Spill oversized layers into extra columns (same layer, adjacent column).
    columns = []  # list of lists of node ids
    col_layer = []  # column index → logical layer
    for li, col in enumerate(layers):
        for i in range(0, len(col), MAX_PER_COL):
            columns.append(col[i : i + MAX_PER_COL])
            col_layer.append(li)

    columns = order_within_layers(columns, edges)

    # ── 2. Box geometry per column ──
    col_meta = []  # (width, [(node, label_lines)...])
    for col in columns:
        entries = []
        wmax = 8
        for n in col:
            label = modules[n].get("label", n)
            lines = split_lines(label, MAX_LABEL_W) if str_width(label) > MAX_LABEL_W else [label]
            lines = [truncate_str(line, MAX_LABEL_W) for line in lines[:2]]
            wmax = max(wmax, max(str_width(line) for line in lines))
            entries.append((n, lines))
        col_meta.append((wmax + 4, entries))

    # Lane demand per gap decides gap width.
    gap_edges = [[] for _ in range(len(columns) + 1)]
    col_index = {n: ci for ci, col in enumerate(columns) for n in col}
    for e in edges:
        c1, c2 = col_index[e["from"]], col_index[e["to"]]
        lo, hi = (c1, c2) if c1 <= c2 else (c2, c1)
        for g in range(lo + 1, hi + 1):
            gap_edges[g].append(e)
    gap_w = [max(4, min(len(g) + 3, 10)) for g in gap_edges]

    # Column x positions
    col_x = []
    x = 1
    for ci, (w, _) in enumerate(col_meta):
        x += gap_w[ci]
        col_x.append(x)
        x += w
    total_w = x + gap_w[-1] + 1

    # Column heights → vertical centering
    col_h = []
    for _, entries in col_meta:
        h = sum(len(lines) + 2 for _, lines in entries)
        h += BOX_SPACING * max(0, len(entries) - 1)
        col_h.append(h)
    max_h = max(col_h)
    total_h = max_h + 4

    grid = CharGrid(max(total_w, 20), total_h)
    boxes = {}

    # ── 3. Draw boxes ──
    for ci, (w, entries) in enumerate(col_meta):
        y = 1 + (max_h - col_h[ci]) // 2
        for n, lines in entries:
            h = len(lines) + 2
            box_style = (
                "double" if n == focus else _module_frame(ctx, n)
            )
            color = _module_color(ctx, n)
            rect = grid.draw_rect(col_x[ci], y, w, h, style=box_style, color=color)
            for r, line in enumerate(lines):
                grid.draw_label(col_x[ci] + 1, y + 1 + r, w - 2, line, color=color)
            boxes[n] = rect
            y += h + BOX_SPACING

    # ── 4. Route edges ──
    legend = []
    lane_used = [0] * len(gap_edges)

    def gap_span(g):
        left = col_x[g - 1] + col_meta[g - 1][0] if g > 0 else 0
        right = col_x[g] if g < len(columns) else grid.width - 1
        return left, right

    for e in sorted(edges, key=lambda e: abs(col_index[e["to"]] - col_index[e["from"]])):
        fr, to = e["from"], e["to"]
        edge_color = (
            "assurance"
            if (fr, to) in ctx.edge_issues
            else _module_color(ctx, fr)
        )
        c1, c2 = col_index[fr], col_index[to]
        r1, r2 = boxes[fr], boxes[to]
        sy = r1.y + r1.h // 2
        ty = r2.y + r2.h // 2
        cells = []

        if c1 == c2:
            # Same column — hook around the right side of the column.
            left, right = gap_span(c1 + 1)
            lane = left + 1 + (lane_used[c1 + 1] % max(1, right - left - 2))
            lane_used[c1 + 1] += 1
            for xx in range(r1.right, lane + 1):
                grid.put(xx, sy, "─", edge_color)
                cells.append((xx, sy))
            lo, hi = sorted((sy, ty))
            for yy in range(lo, hi + 1):
                grid.put(lane, yy, "│", edge_color)
                cells.append((lane, yy))
            grid.put(lane, sy, "┐" if ty > sy else "┘", edge_color)
            grid.put(lane, ty, "└" if ty > sy else "┌", edge_color)
            for xx in range(r2.right + 1, lane):
                grid.put(xx, ty, "─", edge_color)
                cells.append((xx, ty))
            grid.put(r2.right, ty, "◀", edge_color)
        else:
            step = 1 if c2 > c1 else -1
            cur_y = sy
            start_x = r1.right if step == 1 else r1.x - 1
            for seg_c in range(c1, c2, step):
                g = seg_c + 1 if step == 1 else seg_c
                left, right = gap_span(g)
                span = max(1, right - left - 2)
                lane = left + 1 + (lane_used[g] % span)
                lane_used[g] += 1
                # target row for this segment: ty on the last segment,
                # else pass through the corridor at cur_y
                last = seg_c + step == c2
                nxt_y = ty if last else cur_y
                # horizontal from current x to lane
                x_from, x_to = (start_x, lane) if step == 1 else (lane, start_x)
                for xx in range(min(x_from, x_to), max(x_from, x_to) + 1):
                    if grid.get(xx, cur_y) == " ":
                        grid.put(xx, cur_y, "─", edge_color)
                    cells.append((xx, cur_y))
                # vertical on the lane
                if nxt_y != cur_y:
                    grid.put(lane, cur_y, "┐" if step == 1 else "┌", edge_color)
                    lo, hi = sorted((cur_y, nxt_y))
                    for yy in range(lo + 1, hi):
                        grid.put(lane, yy, "│", edge_color)
                        cells.append((lane, yy))
                    grid.put(lane, nxt_y, "└" if nxt_y > cur_y else "┌", edge_color)
                    if step == -1:
                        grid.put(lane, cur_y, "┘" if nxt_y < cur_y else "┐", edge_color)
                        grid.put(lane, nxt_y, "└" if nxt_y < cur_y else "┌", edge_color)
                cur_y = nxt_y
                # continue from the lane across the next column corridor
                if not last:
                    nc = seg_c + step
                    ncx, ncw = col_x[nc], col_meta[nc][0]
                    x_from, x_to = (lane + 1, ncx + ncw - 1) if step == 1 else (ncx, lane - 1)
                    # corridor: only draw across free cells (between boxes)
                    for xx in range(x_from, x_to + 1):
                        if grid.get(xx, cur_y) == " ":
                            grid.put(xx, cur_y, "─", edge_color)
                        cells.append((xx, cur_y))
                    start_x = ncx + ncw if step == 1 else ncx - 1
                else:
                    # final approach into the target box
                    if step == 1:
                        for xx in range(lane + 1, r2.x - 1):
                            grid.put(xx, ty, "─", edge_color)
                            cells.append((xx, ty))
                        grid.put(r2.x - 1, ty, ARROW_RIGHT, edge_color)
                    else:
                        for xx in range(r2.right + 1, lane):
                            grid.put(xx, ty, "─", edge_color)
                            cells.append((xx, ty))
                        grid.put(r2.right, ty, "◀", edge_color)

        e["line_cells"] = cells
        if style == "flow" and e.get("label"):
            marker = str(len(legend) + 1)
            mx, my = cells[len(cells) // 2] if cells else (0, 0)
            grid.put(mx, my, marker, edge_color)
            legend.append(f"  {marker}. {e['label']}")

    # No verify/correct here: the Sugiyama routing is already deliberate,
    # and correct()'s incremental fixes (shift/resize/reroute) redraw boxes
    # without labels, destroying the diagram on dense graphs. The
    # design-assistance rules still run in geometry_render for coloring.
    out = (
        grid.render_ansi(resolve_theme(ctx.theme).colors)
        if ctx.color
        else grid.render()
    )
    if legend:
        out += "\n" + "\n".join(legend)
    return out
