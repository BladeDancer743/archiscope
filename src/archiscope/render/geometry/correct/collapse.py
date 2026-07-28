"""Collapse correction — compress gaps between boxes."""

from ..draw.grid import CharGrid, Rect
from ..verify.rules import Violation


def compute_collapse_vector(violations: list[Violation], boxes: dict[str, Rect]) -> dict:
    """Compute compression vector: negative dx to close gaps."""
    vector = {}
    for v in violations:
        if v.rule_id not in ("G0h_sparse",):
            continue
        detail = v.detail or {}
        gap = detail.get("gap", 0)
        max_gap = detail.get("max", 40)
        subject = v.subject

        if gap > max_gap and subject:
            # Try to find the right-side box by the edge label
            parts = subject.split(",")
            if len(parts) >= 1:
                matching = [m for m in boxes if parts[-1] in subject or subject in m]
                shift = min(gap - max_gap, 20)  # cap compression at 20 cols
                for m in matching:
                    if m in boxes:
                        vector.setdefault(m, {"dx": 0})
                        vector[m]["dx"] -= shift
                if not matching:
                    # Apply to all downstream boxes
                    for mid, rect in boxes.items():
                        vector.setdefault(mid, {"dx": 0})
    return vector


def apply_collapse(grid: CharGrid, boxes: dict[str, Rect], vector: dict):
    """Apply negative dx to compact boxes. Minimum x is 0."""
    for module, delta in vector.items():
        if module not in boxes:
            continue
        rect = boxes[module]
        dx = delta.get("dx", 0)
        if dx < 0:
            rect.x = max(0, rect.x + dx)
