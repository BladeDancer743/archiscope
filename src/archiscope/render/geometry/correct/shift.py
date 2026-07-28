"""Shift correction — move boxes to resolve overlaps and edge sharing."""

from ..draw.grid import CharGrid, Rect
from ..verify.rules import Violation


def compute_shift_vector(violations: list[Violation], boxes: dict[str, Rect]) -> dict:
    """Compute dx/dy shift per box to fix overlap and edge-share violations."""
    vector = {}
    for v in violations:
        if v.rule_id not in ("G0_overlap", "G1_edge_share"):
            continue
        detail = v.detail or {}
        box_b = detail.get("box_b", "")
        if not box_b or box_b not in boxes:
            continue
        vector.setdefault(box_b, {"dx": 0, "dy": 0})
        vector[box_b]["dx"] += 3 if v.rule_id == "G0_overlap" else 2
    return vector


def apply_shift(grid: CharGrid, boxes: dict[str, Rect], vector: dict):
    """Apply shift deltas to grid and boxes. Ensure grid size."""
    for module, delta in vector.items():
        if module not in boxes:
            continue
        rect = boxes[module]
        dx = delta.get("dx", 0)
        dy = delta.get("dy", 0)
        if dx:
            rect.x += dx
            grid.ensure_size(rect.right + 1, grid.height)
        if dy:
            rect.y += dy
            grid.ensure_size(grid.width, rect.bottom + 1)
