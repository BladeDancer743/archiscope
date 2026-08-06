"""Correction engine — transaction-based batch fix with rollback.

Delegates to individual corrector modules: shift, resize, reroute, collapse, relayout.
"""

from copy import deepcopy
from dataclasses import dataclass

from ..draw.grid import CharGrid, Rect
from ..verify.engine import has_critical, verify
from ..verify.rules import Severity, VerifyContext, Violation
from . import collapse, relayout, reroute, resize, shift


class CorrectionError(Exception):
    pass


class CorrectionLoopError(CorrectionError):
    pass


@dataclass
class CorrectionResult:
    original_violations: list[Violation]
    applied: list[str]
    remaining_violations: list[Violation]
    grid: CharGrid
    boxes: dict[str, Rect]
    needs_relayout: bool = False


MAX_ITERATIONS = 5


def correct(ctx: VerifyContext, max_iterations: int = MAX_ITERATIONS) -> CorrectionResult:
    """Transaction-based correction pipeline."""
    original_violations = verify(ctx)
    if not original_violations:
        return CorrectionResult(
            original_violations=[],
            applied=[],
            remaining_violations=[],
            grid=ctx.grid,
            boxes=ctx.boxes,
        )

    applied_fixes = []
    current_grid = deepcopy(ctx.grid)
    current_boxes = {k: deepcopy(v) for k, v in ctx.boxes.items()}
    current_edges = [dict(e) for e in ctx.edges]

    for iteration in range(max_iterations):
        current_ctx = _make_ctx(current_grid, current_boxes, current_edges, ctx)
        violations = verify(current_ctx)

        if not violations:
            break

        # Separate fixable from critical
        fixable = [v for v in violations if v.severity != Severity.CRITICAL]
        critical = [v for v in violations if v.severity == Severity.CRITICAL]

        if not fixable:
            if critical:
                return CorrectionResult(
                    original_violations=original_violations,
                    applied=applied_fixes,
                    remaining_violations=violations,
                    grid=current_grid,
                    boxes=current_boxes,
                    needs_relayout=True,
                )
            break

        # Save snapshot for potential rollback
        snapshot_grid = deepcopy(current_grid)
        snapshot_boxes = {k: deepcopy(v) for k, v in current_boxes.items()}

        # Apply corrections via individual correctors
        fix_count = 0

        # 1. Shift (overlap, edge share)
        v_shift = shift.compute_shift_vector(fixable, current_boxes)
        if v_shift:
            shift.apply_shift(current_grid, current_boxes, v_shift)
            fix_count += len(v_shift)

        # 2. Resize (bleed, CJK width)
        v_resize = resize.compute_resize_vector(fixable, current_boxes, ctx.modules)
        if v_resize:
            resize.apply_resize(current_grid, current_boxes, v_resize)
            fix_count += len(v_resize)

        # 3. Reroute (pierce, crossing)
        v_reroute = reroute.compute_reroute_vector(fixable, current_boxes, current_edges)
        if v_reroute:
            reroute.apply_reroute(current_grid, current_boxes, current_edges, v_reroute)
            fix_count += len(v_reroute)

        # 4. Collapse (sparse)
        v_collapse = collapse.compute_collapse_vector(fixable, current_boxes)
        if v_collapse:
            collapse.apply_collapse(current_grid, current_boxes, v_collapse)
            fix_count += len(v_collapse)

        if fix_count == 0:
            break

        applied_fixes.append(
            f"iter_{iteration}: {fix_count} fixes via shift/resize/reroute/collapse"
        )

        # Re-verify
        new_ctx = _make_ctx(current_grid, current_boxes, current_edges, ctx)
        new_violations = verify(new_ctx)

        # Check for new critical violations
        old_critical_ids = {v.rule_id for v in violations if v.severity == Severity.CRITICAL}
        new_critical_ids = {v.rule_id for v in new_violations if v.severity == Severity.CRITICAL}
        if new_critical_ids - old_critical_ids:
            # Rollback
            current_grid = snapshot_grid
            current_boxes = snapshot_boxes
            break

    final_ctx = _make_ctx(current_grid, current_boxes, current_edges, ctx)
    final_violations = verify(final_ctx)

    if has_critical(final_violations):
        # Try full relayout as last resort — but only adopt it when it
        # actually reduces the violations. A rebuild that still pierces
        # boxes (e.g. compact layout drawing edges across rows) is worse
        # than the original diagram, so the last good grid is kept.
        try:
            new_grid, new_boxes = relayout.relayout(final_ctx)
            new_ctx = _make_ctx(new_grid, new_boxes, current_edges, ctx)
            new_violations = verify(new_ctx)
            if len(new_violations) < len(final_violations):
                current_grid, current_boxes = new_grid, new_boxes
                final_ctx = new_ctx
                final_violations = new_violations
                applied_fixes.append("relayout: full rebuild")
        except Exception:
            pass

    return CorrectionResult(
        original_violations=original_violations,
        applied=applied_fixes,
        remaining_violations=final_violations,
        grid=current_grid,
        boxes=current_boxes,
        needs_relayout=has_critical(final_violations),
    )


def _make_ctx(grid, boxes, edges, parent_ctx):
    return VerifyContext(
        grid=grid,
        boxes=boxes,
        edges=edges,
        groups=parent_ctx.groups,
        modules=parent_ctx.modules,
        terminal_width=parent_ctx.terminal_width,
    )
