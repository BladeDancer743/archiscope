"""Flow renderer — data bus / flow graph view.

Shows directed data flow between modules using Unicode arrows.
"""

from ..draw.grid import CharGrid, Rect, str_width, pad_str
from ..verify.rules import VerifyContext


def render_flow(ctx: VerifyContext) -> str:
    """Render a directed flow graph showing data movement between modules."""
    modules = ctx.modules
    edges = ctx.edges

    module_list = [m for m in modules if modules[m].get("type") != "root"]
    if not module_list:
        return "No modules."

    n = len(module_list)
    lines = []

    # Simple top-down flow layout
    # Find entry points (modules with no incoming edges)
    has_incoming = set()
    for edge in edges:
        has_incoming.add(edge["to"])

    entry_points = [m for m in module_list if m not in has_incoming]
    rest = [m for m in module_list if m not in entry_points]

    y = 0
    positions = {}  # module → (row, col)

    # Layout entry points
    for i, mod in enumerate(entry_points):
        positions[mod] = (y, i * 20)
    y += 3

    # Layout rest
    rest_ordered = sorted(rest, key=lambda m: len([e for e in edges if e["to"] == m]), reverse=True)
    for i, mod in enumerate(rest_ordered):
        positions[mod] = (y, i * (80 // max(len(rest_ordered), 1)))

    # Render nodes
    for mod, (row, col) in positions.items():
        label = modules[mod].get("label", mod)
        lines.append(f"  [{col:3d},{row:3d}] {pad_str(label, 20)}")

    # Render edges
    for edge in edges:
        fr, to = edge["from"], edge["to"]
        if fr in positions and to in positions:
            label = edge.get("label", "")
            fr_pos = positions[fr]
            to_pos = positions[to]
            arrow = "▼" if to_pos[0] > fr_pos[0] else "▲"
            lines.append(f"  {fr} ──{label}──{arrow} {to}")

    return "\n".join(lines)
