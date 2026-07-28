"""Resize correction — widen boxes for bleed/text overflow."""

from ..draw.grid import CharGrid, Rect, str_width, split_lines, pad_str
from ..verify.rules import Violation


def compute_resize_vector(violations: list[Violation], boxes: dict[str, Rect],
                          modules: dict) -> dict:
    """Compute dw/dh per box for text overflow violations."""
    vector = {}
    for v in violations:
        if v.rule_id not in ("G0b_bleed", "C1_cjk_width"):
            continue
        module_id = v.subject
        if module_id not in boxes:
            continue
        detail = v.detail or {}
        inner_w = detail.get("inner_width", 20)
        label_w = detail.get("label_width", detail.get("display_width", 0))
        needed = max(0, label_w - inner_w)
        if needed > 0:
            vector.setdefault(module_id, {"dw": 0, "dh": 0})
            vector[module_id]["dw"] = max(vector[module_id]["dw"], needed + 2)
    return vector


def apply_resize(grid: CharGrid, boxes: dict[str, Rect], vector: dict):
    """Apply width/height changes."""
    for module, delta in vector.items():
        if module not in boxes:
            continue
        rect = boxes[module]
        if delta.get("dw", 0) > 0:
            rect.w += delta["dw"]
            grid.ensure_width(rect.right + 1)
        if delta.get("dh", 0) > 0:
            rect.h += delta["dh"]
            grid.ensure_height(rect.bottom + 1)
