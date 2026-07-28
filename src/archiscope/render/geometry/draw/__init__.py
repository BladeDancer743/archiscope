"""Render geometry drawing primitives and renderer strategies."""

from ....strategies import STRATEGY_ALIASES

# Renderer modules
from . import (
    blueprint,
    cards,
    class_diagram,
    compact_table,
    hbar,
    heat_grid,
    layout,
    nested,
    rings,
    state_machine,
    tree,
)
from .grid import (
    BLOCK_DOT,
    BLOCK_FULL,
    BLOCK_LIGHT,
    BLOCK_MED,
    DASHED,
    DOUBLE,
    SINGLE,
    CharGrid,
    Rect,
    char_width,
    pad_str,
    split_lines,
    str_width,
    truncate_str,
)


def _hbar_data(ctx):
    """Build timing rows from modules' internal_flow steps.

    Bars are proportional to duration_ms when steps define it; without it every
    step gets an equal-width bar, so the view degrades to a step sequence.
    """
    data = []
    for path, mod in ctx.modules.items():
        for step in mod.get("internal_flow") or []:
            if isinstance(step, dict) and "step" in step:
                data.append(
                    {
                        "label": step["step"],
                        "value": step.get("duration_ms", 1),
                        "unit": "ms" if "duration_ms" in step else "",
                    }
                )
    return data


_PRIMARY_RENDERERS = {
    "flow": layout.render_topology,
    "minimal": lambda ctx: layout.render_topology(ctx, "minimal"),
    "blueprint": blueprint.render_blueprint,
    "grouped": nested.render_nested,
    "swimlane": lambda ctx: nested.render_nested(ctx, "swimlane"),
    "onion": rings.render_rings,
    "onion_rings": rings.render_rings,
    "heat_matrix": heat_grid.render_heat_matrix,
    "matrix": heat_grid.render_heat_matrix,
    "hbar_gantt": lambda ctx: hbar.render_hbar(ctx, _hbar_data(ctx), "gantt"),
    "waterfall": lambda ctx: hbar.render_hbar(ctx, _hbar_data(ctx), "waterfall"),
    "tree": tree.render_tree,
    "mindmap": lambda ctx: tree.render_tree(ctx, "mindmap"),
    "statemachine": state_machine.render_state_machine,
    "cards": cards.render_cards,
    "compact_table": compact_table.render_compact_table,
    "class_diagram": class_diagram.render_class_diagram,
}

RENDERERS = dict(_PRIMARY_RENDERERS)
for alias, target in STRATEGY_ALIASES.items():
    RENDERERS[alias] = _PRIMARY_RENDERERS[target]
