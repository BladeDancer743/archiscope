"""Tree renderer — mindmap, tree view.

Uses box-drawing characters to render hierarchical structures:
  ├── child1
  │   ├── grandchild1
  │   └── grandchild2
  └── child2
"""

from ..verify.rules import VerifyContext


def render_tree(ctx: VerifyContext, style: str = "tree") -> str:
    """Render modules as a tree structure.

    style: "tree" (box-drawing lines), "mindmap" (indented outline)
    """
    modules = ctx.modules

    def _find_children(parent):
        return [m for m in modules if modules[m].get("parent") == parent]

    def _render_node(mid, depth, is_last, prefix):
        label = modules[mid].get("label", mid)
        desc = modules[mid].get("description", "")
        display = label
        if desc and style == "mindmap":
            display = f"{label} — {desc}"

        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{display}")

        children = _find_children(mid)
        for i, child in enumerate(children):
            is_last_child = i == len(children) - 1
            if is_last:
                new_prefix = prefix + "    "
            else:
                new_prefix = prefix + "│   "
            _render_node(child, depth + 1, is_last_child, new_prefix)

    lines = []
    root_nodes = [m for m in modules if modules[m].get("type") == "root"]
    engine_nodes = [m for m in modules if modules[m].get("type") == "engine"]

    if root_nodes:
        for root in root_nodes:
            label = modules[root].get("label", root)
            lines.append(label)
            children = _find_children(root)
            for i, child in enumerate(children):
                _render_node(child, 0, i == len(children) - 1, "")
    elif engine_nodes:
        lines.append("Engines")
        for i, eng in enumerate(engine_nodes):
            label = modules[eng].get("label", eng)
            lines.append(f"{'└── ' if i == len(engine_nodes) - 1 else '├── '}{label}")
            children = _find_children(eng)
            for j, child in enumerate(children):
                prefix = "    " if i == len(engine_nodes) - 1 else "│   "
                _render_node(child, 0, j == len(children) - 1, prefix)
    else:
        # Mid-level focus (e.g. a layer's modules): no root/engine in scope.
        # Treat every module whose parent is outside the scope as top-level.
        top_nodes = [m for m in modules if modules[m].get("parent") not in modules]
        for i, node in enumerate(top_nodes):
            label = modules[node].get("label", node)
            desc = modules[node].get("description", "")
            if desc and style == "mindmap":
                label = f"{label} — {desc}"
            lines.append(f"{'└── ' if i == len(top_nodes) - 1 else '├── '}{label}")
            children = _find_children(node)
            for j, child in enumerate(children):
                prefix = "    " if i == len(top_nodes) - 1 else "│   "
                _render_node(child, 0, j == len(children) - 1, prefix)

    return "\n".join(lines)
