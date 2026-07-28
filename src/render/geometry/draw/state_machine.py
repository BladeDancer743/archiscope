"""State machine renderer — statemachine / decision tree view."""

from ..draw.grid import CharGrid, Rect, str_width, pad_str
from ..verify.rules import VerifyContext


def _as_list(value) -> list:
    """Normalize scalar YAML endpoints without splitting strings by character."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def render_state_machine(ctx: VerifyContext, style: str = "statemachine") -> str:
    """Render module states and transitions as a state diagram.

    Uses internal_flow or function data from .archmap.yaml.
    """
    modules = ctx.modules
    lines = []

    for mid, module in modules.items():
        internal_flow = module.get("internal_flow")
        if not internal_flow:
            continue

        label = module.get("label", mid)
        lines.append(f"[{label}]")
        lines.append("")

        prev_state = None
        for i, step in enumerate(internal_flow):
            step_label = step.get("step", f"Step {i}")
            detail = step.get("description", "")
            from_list = _as_list(step.get("from"))
            to_list = _as_list(step.get("to"))

            box_w = max(40, str_width(step_label) + 4)
            lines.append(f"  ┌{'─' * box_w}┐")
            lines.append(f"  │ {pad_str(step_label, box_w - 2)} │")
            if detail:
                for dl in [detail[i:i+box_w-2] for i in range(0, len(detail), box_w-2)]:
                    lines.append(f"  │ {pad_str(dl, box_w - 2)} │")
            lines.append(f"  └{'─' * (box_w // 2)}┬{'─' * (box_w // 2 - 1)}┘")

            for src in from_list:
                if isinstance(src, str):
                    lines.append(f"                 ▲")
                    lines.append(f"                 │")
                    lines.append(f"            [{src}]")

            for dst in to_list:
                if isinstance(dst, str):
                    lines.append(f"                 │")
                    lines.append(f"                 ▼")
                    lines.append(f"            [{dst}]")

            if i > 0:
                lines.append(f"                 │")
                lines.append(f"            (next step)")
                lines.append("")

        lines.append("─" * 60)

    return "\n".join(lines) if lines else "No state machine definitions found."
