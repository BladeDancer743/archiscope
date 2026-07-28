"""Reroute correction — resolve pierce and crossing violations."""

from ..draw.grid import CharGrid, Rect
from ..verify.rules import Violation


def compute_reroute_vector(violations: list[Violation], boxes: dict[str, Rect],
                           edges: list[dict]) -> dict:
    """Compute path changes for pierce/crossing violations.
    
    Returns a dict of {edge_id: {new_path_cells: [(x,y),...]}} rather than box shifts.
    """
    vector = {}
    for v in violations:
        if v.rule_id not in ("G0c_pierce", "G0d_crossing"):
            continue
        detail = v.detail or {}
        edge_key = v.subject

        if v.rule_id == "G0c_pierce":
            obstacle = detail.get("box", "")
            if obstacle in boxes:
                rect = boxes[obstacle]
                # Route around the top of the obstacle
                vector[edge_key] = {
                    "reroute": "above",
                    "obstacle_rect": rect,
                }
        elif v.rule_id == "G0d_crossing":
            vector[edge_key] = {
                "reroute": "bundle",
            }
    return vector


def apply_reroute(grid: CharGrid, boxes: dict[str, Rect], edges: list[dict],
                  vector: dict):
    """Apply path rerouting. Currently marks edges for redraw; full reroute
    requires re-tracing lines around obstacles, deferred to full relayout.
    """
    for edge_key, reroute_info in vector.items():
        # Mark edge as needing path recalculation
        for edge in edges:
            eid = edge.get("label", f"{edge['from']}→{edge['to']}")
            if eid == edge_key or edge_key in (edge.get("from",""), edge.get("label","")):
                edge["needs_reroute"] = True
