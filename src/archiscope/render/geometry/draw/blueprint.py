"""Blueprint renderer — orthogonal zones with a circuit-style data bus.

The diagram keeps the visual hierarchy separate from the exact topology:

* CONTROL / CORE / PROCESS zones communicate architectural role.
* Numbered chip labels stay compact and CJK-safe.
* DATA FLOW names both endpoints of every real edge, avoiding a separate
  numeric legend while keeping dense graphs exact.
* Isolated modules remain visible on a dotted SUPPORT rail.
"""

from ..verify.rules import VerifyContext
from .grid import pad_str, str_width, truncate_str
from .layout import assign_layers

ZONE_GAP = 3
MIN_ZONE_WIDTH = 18


def render_blueprint(ctx: VerifyContext) -> str:
    """Render an architecture as blueprint zones plus an exact I/O bus."""
    modules = ctx.modules
    nodes = [mid for mid, mod in modules.items() if mod.get("type") != "root"]
    if not nodes:
        return "No modules."

    edges = [edge for edge in ctx.edges if edge["from"] in modules and edge["to"] in modules]
    control, core, process, support = _partition(nodes, edges, getattr(ctx, "focus", None))

    ordered = control + [core] + process + support
    digits = max(2, len(str(len(ordered))))
    refs = {node: str(index).zfill(digits) for index, node in enumerate(ordered, start=1)}

    terminal_w = max(
        MIN_ZONE_WIDTH * 3 + ZONE_GAP * 2,
        int(getattr(ctx, "terminal_width", 80)),
    )
    usable = terminal_w - ZONE_GAP * 2
    base = usable // 3
    zone_widths = (base, base, usable - base * 2)

    control_rows = [_node_row(node, refs, modules) for node in control]
    process_rows = [_node_row(node, refs, modules) for node in process]
    core_rows = _core_rows(core, refs, modules, zone_widths[1] - 2)
    body_h = max(3, len(control_rows), len(core_rows), len(process_rows))

    blocks = [
        _zone("CONTROL", control_rows, zone_widths[0], body_h),
        _zone("CORE", core_rows, zone_widths[1], body_h),
        _zone("PROCESS", process_rows, zone_widths[2], body_h),
    ]

    signal_row = 1 + body_h // 2
    output = []
    for row in range(body_h + 2):
        to_core = "══▶" if control and row == signal_row else " " * ZONE_GAP
        to_process = "══▶" if process and row == signal_row else " " * ZONE_GAP
        output.append(blocks[0][row] + to_core + blocks[1][row] + to_process + blocks[2][row])

    output.append("")
    output.append(_rule_header("DATA FLOW / 实际数据流 ", terminal_w, "═"))
    if edges:
        output.extend(_flow_rows(edges, modules, terminal_w))
    else:
        output.append("  暂无连接")

    if support:
        output.append("")
        output.append(_rule_header("SUPPORT ", terminal_w, "·"))
        segments = [_node_row(node, refs, modules) for node in support]
        output.extend(_pack_segments("  · ", segments, terminal_w, "   ·   "))

    return "\n".join(output).rstrip()


def _partition(
    nodes: list[str],
    edges: list[dict],
    focus: str | None,
) -> tuple[list[str], str, list[str], list[str]]:
    """Infer CONTROL / CORE / PROCESS / SUPPORT roles from graph position."""
    position = {node: index for index, node in enumerate(nodes)}
    incoming = {node: [] for node in nodes}
    outgoing = {node: [] for node in nodes}
    for edge in edges:
        source, target = edge["from"], edge["to"]
        if source in outgoing and target in incoming:
            outgoing[source].append(target)
            incoming[target].append(source)

    connected = [node for node in nodes if incoming[node] or outgoing[node]]
    if focus in nodes:
        core = focus
    elif connected:
        core = max(
            connected,
            key=lambda node: (
                len(incoming[node]) + len(outgoing[node]),
                min(len(incoming[node]), len(outgoing[node])),
                len(outgoing[node]),
                -position[node],
            ),
        )
    else:
        core = nodes[0]

    layers = assign_layers(nodes, edges)
    core_layer = layers.get(core, 0)
    control = []
    process = []
    support = []

    for node in nodes:
        if node == core:
            continue
        if not incoming[node] and not outgoing[node]:
            support.append(node)
            continue

        layer = layers.get(node, core_layer)
        if core in outgoing[node] or layer < core_layer:
            control.append(node)
        elif core in incoming[node] or layer > core_layer:
            process.append(node)
        elif outgoing[node] and not incoming[node]:
            control.append(node)
        else:
            process.append(node)

    control.sort(key=lambda node: (layers.get(node, 0), position[node]))
    process.sort(key=lambda node: (layers.get(node, 0), position[node]))
    support.sort(key=position.__getitem__)
    return control, core, process, support


def _node_row(node: str, refs: dict[str, str], modules: dict) -> str:
    return f"[{refs[node]}] {modules[node].get('label', node)}"


def _core_rows(
    core: str,
    refs: dict[str, str],
    modules: dict,
    inner_width: int,
) -> list[str]:
    """Draw the inferred center node as a double-framed chip."""
    chip_w = max(12, inner_width - 2)
    label = truncate_str(_node_row(core, refs, modules), chip_w - 2)
    return [
        " " + "╔" + "═" * (chip_w - 2) + "╗",
        " " + "║" + pad_str(label, chip_w - 2, "center") + "║",
        " " + "╚" + "═" * (chip_w - 2) + "╝",
    ]


def _zone(title: str, rows: list[str], width: int, body_h: int) -> list[str]:
    inner = width - 2
    title_text = truncate_str(f"═ {title} ", inner)
    top = "╔" + title_text + "═" * (inner - str_width(title_text)) + "╗"
    body = []
    for index in range(body_h):
        text = rows[index] if index < len(rows) else ""
        body.append("║" + pad_str(truncate_str(text, inner), inner) + "║")
    return [top, *body, "╚" + "═" * inner + "╝"]


def _rule_header(label: str, width: int, fill: str) -> str:
    label = truncate_str(label, width)
    return label + fill * max(0, width - str_width(label))


def _flow_rows(edges: list[dict], modules: dict, width: int) -> list[str]:
    """List exact edges with human-readable endpoints and aligned arrows."""
    prefix = "  "
    labels = {
        node: str(modules[node].get("label", node))
        for edge in edges
        for node in (edge["from"], edge["to"])
    }
    position = {node: index for index, node in enumerate(modules)}
    layers = assign_layers(list(modules), edges)
    ordered_edges = sorted(
        edges,
        key=lambda edge: (
            layers.get(edge["from"], 0),
            layers.get(edge["to"], 0),
            position.get(edge["from"], 0),
            position.get(edge["to"], 0),
        ),
    )
    source_width = min(
        max(str_width(labels[edge["from"]]) for edge in edges),
        max(10, width // 3),
    )
    rows = []
    for edge in ordered_edges:
        source = truncate_str(labels[edge["from"]], source_width)
        edge_label = str(edge.get("label") or "").strip()
        connector = f" ──[{edge_label}]──▶ " if edge_label else " ─────▶ "
        target_width = max(
            1,
            width - str_width(prefix) - source_width - str_width(connector),
        )
        target = truncate_str(labels[edge["to"]], target_width)
        row = prefix + pad_str(source, source_width) + connector + target
        rows.append(truncate_str(row, width).rstrip())
    return rows


def _pack_segments(
    prefix: str,
    segments: list[str],
    width: int,
    separator: str,
) -> list[str]:
    """Pack bus/support tokens without exceeding the display width."""
    lines = []
    continuation = " " * str_width(prefix)
    current = prefix
    for segment in segments:
        segment = truncate_str(segment, width - str_width(prefix))
        candidate = segment if current == prefix else separator + segment
        if current != prefix and str_width(current + candidate) > width:
            lines.append(current.rstrip())
            current = continuation + segment
        else:
            current += candidate
    if current.strip():
        lines.append(current.rstrip())
    return lines
