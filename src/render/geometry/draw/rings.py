"""Concentric rings renderer — onion_rings view.

Layers from outside-in: external deps → wrapper modules → kernel modules.
Rendered as concentric text rings using Unicode circles.
"""

from ..draw.grid import CharGrid, str_width, pad_str
from ..verify.rules import VerifyContext


def render_rings(ctx: VerifyContext) -> str:
    """Render modules in concentric rings based on dependency distance.

    Innermost ring = most depended-upon modules (kernel).
    Outer ring = modules with no incoming edges (external deps).
    """
    modules = ctx.modules
    edges = ctx.edges

    # Compute in-degree
    in_degree = {}
    for edge in edges:
        to_mod = edge["to"]
        in_degree[to_mod] = in_degree.get(to_mod, 0) + 1

    module_list = [m for m in modules if modules[m].get("type") != "root"]
    if not module_list:
        return "No modules."

    # Sort by in-degree → higher = inner ring
    sorted_modules = sorted(module_list, key=lambda m: -in_degree.get(m, 0))
    n = len(sorted_modules)

    rings = min(3, max(1, n // 3))
    per_ring = (n + rings - 1) // rings

    lines = []
    ring_names = {0: "内核 (被依赖最多)", 1: "外围模块", 2: "外部接口"}

    for r in range(rings):
        start = r * per_ring
        end = min(start + per_ring, n)
        ring_mods = sorted_modules[start:end]

        # Build ring box
        label = ring_names.get(r, f"Ring {r}")
        indent = (3 - r) * 4  # outer = more indent
        max_w = max((str_width(modules[m].get("label", m)) for m in ring_mods), default=10)
        box_w = max_w + 6

        lines.append("")
        top = "╔" + "═" * (box_w - 2) + "╗" if r == 0 else "┌" + "─" * (box_w - 2) + "┐"
        mid_line = "║" if r == 0 else "│"
        bottom = "╚" + "═" * (box_w - 2) + "╝" if r == 0 else "└" + "─" * (box_w - 2) + "┘"
        lines.append(" " * indent + top)
        lines.append(" " * indent + mid_line + " " + pad_str(label, box_w - 4) + " " + mid_line)
        lines.append(" " * indent + mid_line + " " * (box_w - 2) + " " + mid_line)

        for mod in ring_mods:
            ml = modules[mod].get("label", mod)
            deg = in_degree.get(mod, 0)
            bar = "◉" * min(deg, 5) if deg > 0 else "○"
            entry = f"{ml} {bar}"
            lines.append(" " * indent + mid_line + " " + pad_str(entry, box_w - 2) + " " + mid_line)

        lines.append(" " * indent + bottom)

    return "\n".join(lines)
