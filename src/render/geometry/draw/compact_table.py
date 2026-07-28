"""Compact table renderer — two-column layout for narrow terminals."""

from ..draw.grid import CharGrid, str_width, pad_str, truncate_str
from ..verify.rules import VerifyContext


def render_compact_table(ctx: VerifyContext) -> str:
    """Two-column layout: left=module name + core logic, right=upstream → downstream."""
    modules = ctx.modules
    edges = ctx.edges
    terminal_w = ctx.terminal_width

    module_list = [m for m in modules if modules[m].get("type") != "root"]
    if not module_list:
        return "No modules."

    left_w = min(40, terminal_w // 2)
    right_w = terminal_w - left_w - 3
    lines = []

    # Header
    lines.append(f"{'─' * left_w}┬{'─' * right_w}")
    lines.append(f"{pad_str('模块', left_w)}│{pad_str('数据流', right_w)}")
    lines.append(f"{'─' * left_w}┼{'─' * right_w}")

    for mid in module_list:
        module = modules[mid]
        label = module.get("label", mid)
        desc = module.get("description", "")
        upstream = module.get("upstream", [])
        downstream = module.get("downstream", [])

        # Left: module
        left = truncate_str(label, left_w - 2)

        # Right: flow
        in_str = ", ".join(upstream[:3])
        out_str = ", ".join(downstream[:3])
        flow = f"← {in_str}" if in_str else ""
        if out_str:
            flow += f"  → {out_str}"
        if not flow:
            flow = "—"

        right = truncate_str(flow, right_w - 2)
        lines.append(f"{pad_str(f' {left}', left_w)}│ {pad_str(right, right_w - 1)}")

        if desc:
            short = truncate_str(desc, terminal_w - 4)
            lines.append(f"  {short}")

    lines.append(f"{'─' * left_w}┴{'─' * right_w}")

    return "\n".join(lines)
