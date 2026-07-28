"""Heat grid renderer — dependency matrix with Unicode heat blocks.

Rows = producers (from modules), Columns = consumers (to modules).
█ = high coupling (5+ edges), ▓ = medium (3-4), ▒ = low (2), ░ = trace (1), · = none.
"""

from ..draw.grid import CharGrid, Rect, str_width, pad_str, BLOCK_FULL, BLOCK_DARK, BLOCK_MED, BLOCK_LIGHT, BLOCK_DOT
from ..verify.rules import VerifyContext, Violation


def render_heat_matrix(ctx: VerifyContext) -> str:
    """Render a dependency heat matrix with hotspot ranking."""
    modules = ctx.modules
    edges = ctx.edges

    # Build adjacency count
    module_list = [m for m in modules if modules[m].get("type") != "root"]
    n = len(module_list)
    if n == 0:
        return "No modules to render."

    # Count dependencies
    adj = {}
    for edge in edges:
        fr, to = edge["from"], edge["to"]
        key = (fr, to)
        adj[key] = adj.get(key, 0) + 1

    # Column widths
    col_labels = [modules[m].get("label", m)[:12] for m in module_list]
    col_w = max(max(str_width(c) for c in col_labels), 8)

    # Row labels
    row_labels = [modules[m].get("label", m)[:12] for m in module_list]
    row_w = max(max(str_width(r) for r in row_labels), 8)

    # Hotspot stats
    in_degree = {m: 0 for m in module_list}
    out_degree = {m: 0 for m in module_list}
    for (fr, to), count in adj.items():
        out_degree[fr] = out_degree.get(fr, 0) + count
        in_degree[to] = in_degree.get(to, 0) + count

    # Build output
    lines = []
    lines.append(" " * row_w + " " + " ".join(pad_str(c, col_w) for c in col_labels))
    lines.append(" " * row_w + " " + " ".join("─" * col_w for _ in module_list))

    for i, row_mod in enumerate(module_list):
        row = [pad_str(row_labels[i], row_w) + " │"]
        for j, col_mod in enumerate(module_list):
            count = adj.get((row_mod, col_mod), 0)
            if count >= 5:
                ch = BLOCK_FULL * min(count, 4)
            elif count >= 3:
                ch = BLOCK_DARK * count
            elif count >= 2:
                ch = BLOCK_MED * count
            elif count >= 1:
                ch = BLOCK_LIGHT * count
            else:
                ch = BLOCK_DOT
            row.append(pad_str(ch, col_w))
        lines.append("".join(row))

    # Hotspot ranking
    lines.append("")
    lines.append("─" * (row_w + n * (col_w + 1)))
    lines.append("被依赖最多 (hotspot):")
    top_in = sorted(in_degree.items(), key=lambda x: -x[1])[:3]
    for m, cnt in top_in:
        label = modules[m].get("label", m)
        bar = "█" * min(cnt * 2, 20)
        lines.append(f"  {pad_str(label, row_w)} {bar} ({cnt})")

    lines.append("依赖最多 (fan-out):")
    top_out = sorted(out_degree.items(), key=lambda x: -x[1])[:3]
    for m, cnt in top_out:
        label = modules[m].get("label", m)
        bar = "█" * min(cnt * 2, 20)
        lines.append(f"  {pad_str(label, row_w)} {bar} ({cnt})")

    return "\n".join(lines)
