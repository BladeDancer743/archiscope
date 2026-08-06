"""Class diagram renderer — each module as a UML-style class box with methods."""

from ..draw.grid import pad_str, str_width, truncate_str
from ..verify.rules import VerifyContext


def render_class_diagram(ctx: VerifyContext) -> str:
    """UML-style render: class name, fields (upstream), methods (functions)."""
    modules = ctx.modules
    terminal_w = ctx.terminal_width

    module_list = [m for m in modules if modules[m].get("type") != "root"]
    if not module_list:
        return "No modules."

    n = len(module_list)
    box_w = min(40, (terminal_w - 6) // max(2, min(3, n)))
    cols = max(1, (terminal_w - 4) // (box_w + 3))
    lines = []

    for i, mid in enumerate(module_list):
        module = modules[mid]
        label = module.get("label", mid)
        upstream = module.get("upstream", [])
        downstream = module.get("downstream", [])
        functions = module.get("functions", [])
        module.get("files", [])

        col = i % cols
        row_start = i // cols * 10
        while len(lines) <= row_start + 9:
            lines.append("")
        x0 = col * (box_w + 3)

        # Top: class name
        top = " " * x0 + "┌" + "─" * (box_w - 2) + "┐"
        _put_at(lines, row_start, x0, top)

        name = " " * x0 + "│ " + pad_str(truncate_str(label, box_w - 4), box_w - 4) + " │"
        _put_at(lines, row_start + 1, x0, name)

        # Fields: upstream
        sep1 = " " * x0 + "├" + "─" * (box_w - 2) + "┤"
        _put_at(lines, row_start + 2, x0, sep1)

        in_str = truncate_str("in: " + ", ".join(upstream[:3]), box_w - 4)
        field = " " * x0 + "│ " + pad_str(in_str, box_w - 4) + " │"
        _put_at(lines, row_start + 3, x0, field)

        # Methods
        sep2 = " " * x0 + "├" + "─" * (box_w - 2) + "┤"
        _put_at(lines, row_start + 4, x0, sep2)

        out_str = truncate_str("out: " + ", ".join(downstream[:3]), box_w - 4)
        method = " " * x0 + "│ " + pad_str(out_str, box_w - 4) + " │"
        _put_at(lines, row_start + 5, x0, method)

        for j, fn in enumerate(functions[:2]):
            if isinstance(fn, dict):
                fn_name = fn.get("name", fn.get("label", f"fn_{j}"))
            else:
                fn_name = str(fn)
            fn_str = truncate_str(f"  {fn_name}", box_w - 4)
            fn_line = " " * x0 + "│ " + pad_str(fn_str, box_w - 4) + " │"
            _put_at(lines, row_start + 6 + j, x0, fn_line)

        # Bottom
        bottom = " " * x0 + "└" + "─" * (box_w - 2) + "┘"
        _put_at(lines, row_start + 8, x0, bottom)

    return "\n".join(lines).rstrip()


def _put_at(lines, idx, x0, content):
    while len(lines) <= idx:
        lines.append("")
    existing = lines[idx]
    existing_w = str_width(existing)
    if existing_w < x0:
        existing += " " * (x0 - existing_w)
    lines[idx] = existing + content[x0:]
