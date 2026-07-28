"""Horizontal bar renderer — gantt, waterfall, trace views.

All use the same primitive: label + █ block proportional to value.
"""

from ..draw.grid import BLOCK_FULL, BLOCK_LIGHT, pad_str, str_width
from ..verify.rules import VerifyContext


def render_hbar(
    ctx: VerifyContext, data: list[dict], style: str = "gantt", max_bar_chars: int = 40
) -> str:
    """Render horizontal bars.

    data: [{label, value, sub_items: [{label, value}]}]
    style: "gantt" (timeline), "waterfall" (call stack), "trace" (execution trace)
    """
    if not data:
        return "No timing data to render."

    max_label = max(str_width(d.get("label", "")) for d in data) if data else 10
    max_value = max(d.get("value", 1) for d in data) if data else 1

    lines = []

    for item in data:
        label = item.get("label", "")
        value = item.get("value", 1)
        unit = item.get("unit", "ms")
        depth = item.get("depth", 0)
        prefix = "  " * depth + ("├ " if item.get("is_child") else "")

        filled = int(value / max(max_value, 1) * max_bar_chars)
        bar = BLOCK_FULL * filled + BLOCK_LIGHT * (max_bar_chars - filled)

        line = f"{pad_str(prefix + label, max_label + len(prefix))} {bar} {value}{unit}"
        if item.get("note"):
            line += f" {item['note']}"
        lines.append(line)

        for sub in item.get("sub_items", []):
            sub_label = sub.get("label", "")
            sub_value = sub.get("value", 1)
            sub_filled = int(sub_value / max(max_value, 1) * max_bar_chars)
            sub_bar = BLOCK_FULL * sub_filled + BLOCK_LIGHT * (max_bar_chars - sub_filled)
            sub_prefix = "  " * (depth + 1) + "└ "
            sub_line = f"{pad_str(sub_prefix + sub_label, max_label + len(sub_prefix))} {sub_bar} {sub_value}{unit}"
            if sub.get("note"):
                sub_line += f" {sub['note']}"
            lines.append(sub_line)

    # Summary row
    total = sum(d.get("value", 0) for d in data)
    lines.append("─" * (max_label + max_bar_chars + 15))
    lines.append(f"总计: {total}{data[0].get('unit', '')}")

    return "\n".join(lines)
