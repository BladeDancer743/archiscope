"""Render geometry drawing primitives and renderer strategies."""

from .grid import CharGrid, Rect, str_width, pad_str, truncate_str, split_lines, char_width
from .grid import SINGLE, DOUBLE, DASHED, BLOCK_FULL, BLOCK_MED, BLOCK_LIGHT, BLOCK_DOT

# Renderer modules
from . import nested
from . import heat_grid
from . import hbar
from . import rings
from . import tree
from . import state_machine
from . import cards
from . import compact_table
from . import class_diagram
from . import layout
from . import blueprint
from ....strategies import STRATEGY_ALIASES

def _hbar_data(ctx):
    """Build timing rows from modules' internal_flow steps.

    Bars are proportional to duration_ms when steps define it; without it every
    step gets an equal-width bar, so the view degrades to a step sequence.
    """
    data = []
    for path, mod in ctx.modules.items():
        for step in mod.get("internal_flow") or []:
            if isinstance(step, dict) and "step" in step:
                data.append({
                    "label": step["step"],
                    "value": step.get("duration_ms", 1),
                    "unit": "ms" if "duration_ms" in step else "",
                })
    return data


_PRIMARY_RENDERERS = {
    "flow":          layout.render_topology,
    "minimal":       lambda ctx: layout.render_topology(ctx, "minimal"),
    "blueprint":     blueprint.render_blueprint,
    "grouped":       nested.render_nested,
    "swimlane":      lambda ctx: nested.render_nested(ctx, "swimlane"),
    "onion":         rings.render_rings,
    "onion_rings":   rings.render_rings,
    "heat_matrix":   heat_grid.render_heat_matrix,
    "matrix":        heat_grid.render_heat_matrix,
    "hbar_gantt":    lambda ctx: hbar.render_hbar(ctx, _hbar_data(ctx), "gantt"),
    "waterfall":     lambda ctx: hbar.render_hbar(ctx, _hbar_data(ctx), "waterfall"),
    "tree":          tree.render_tree,
    "mindmap":       lambda ctx: tree.render_tree(ctx, "mindmap"),
    "statemachine":  state_machine.render_state_machine,
    "cards":         cards.render_cards,
    "compact_table": compact_table.render_compact_table,
    "class_diagram": class_diagram.render_class_diagram,
}

RENDERERS = dict(_PRIMARY_RENDERERS)
for alias, target in STRATEGY_ALIASES.items():
    RENDERERS[alias] = _PRIMARY_RENDERERS[target]
