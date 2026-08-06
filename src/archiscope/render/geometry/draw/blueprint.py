"""Blueprint renderer — orthogonal zones with a circuit-style data bus.

The diagram keeps the visual hierarchy separate from the exact topology:

* Explicit three-way groups communicate author-defined architectural roles.
* Ungrouped graphs use topology-neutral INBOUND / HUB / OUTBOUND labels.
* Numbered chip labels stay compact and CJK-safe.
* The zone connectors aggregate the *real* cross-zone edges (with xN counts
  and bidirectional markers), so the bus shows actual data flow instead of
  a template arrow.
* DATA FLOW names both endpoints of every real edge, avoiding a separate
  numeric legend while keeping dense graphs exact.
* Isolated modules remain visible on a dotted SUPPORT rail.
"""

from collections import Counter

from ..verify.rules import VerifyContext
from .grid import pad_str, str_width, truncate_str
from .layout import assign_layers

ZONE_GAP = 9  # width reserved for the cross-zone bus connectors
MIN_ZONE_WIDTH = 18


def render_blueprint(ctx: VerifyContext) -> str:
    """Render an architecture as blueprint zones plus an exact I/O bus."""
    modules = ctx.modules
    nodes = [mid for mid, mod in modules.items() if mod.get("type") != "root"]
    if not nodes:
        return "No modules."

    edges = [edge for edge in ctx.edges if edge["from"] in modules and edge["to"] in modules]
    explicit = _explicit_zones(ctx, nodes)
    if explicit:
        zone_titles, zone_nodes, support = explicit
    else:
        inbound, hub, outbound, support = _partition(nodes, edges, getattr(ctx, "focus", None))
        zone_titles = ["INBOUND", "HUB", "OUTBOUND"]
        zone_nodes = [inbound, [hub], outbound]

    ordered = [node for members in zone_nodes for node in members] + support
    digits = max(2, len(str(len(ordered))))
    refs = {node: str(index).zfill(digits) for index, node in enumerate(ordered, start=1)}

    terminal_w = max(
        MIN_ZONE_WIDTH * 3 + ZONE_GAP * 2,
        int(getattr(ctx, "terminal_width", 80)),
    )
    usable = terminal_w - ZONE_GAP * 2
    base = usable // 3
    zone_widths = (base, base, usable - base * 2)

    inbound_rows = [_node_row(node, refs, modules) for node in zone_nodes[0]]
    outbound_rows = [_node_row(node, refs, modules) for node in zone_nodes[2]]
    hub_rows = _core_rows(zone_nodes[1], refs, modules, zone_widths[1] - 2)
    body_h = max(3, len(inbound_rows), len(hub_rows), len(outbound_rows))

    blocks = [
        _zone(zone_titles[0], inbound_rows, zone_widths[0], body_h),
        _zone(zone_titles[1], hub_rows, zone_widths[1], body_h),
        _zone(zone_titles[2], outbound_rows, zone_widths[2], body_h),
    ]

    signal_row = 1 + body_h // 2
    zone_bus = _zone_bus(zone_nodes, edges)
    output = []
    for row in range(body_h + 2):
        to_hub = zone_bus["in->hub"] if row == signal_row else " " * ZONE_GAP
        to_outbound = zone_bus["hub->out"] if row == signal_row else " " * ZONE_GAP
        output.append(blocks[0][row] + to_hub + blocks[1][row] + to_outbound + blocks[2][row])

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


def _zone_bus(
    zone_nodes: list[list[str]],
    edges: list[dict],
) -> dict[str, str]:
    """Aggregate the real cross-zone edges into bus connectors.

    Returns the fixed-width connector text for ``in->hub`` and ``hub->out``
    gaps: forward arrows with xN counts, back arrows for reverse flow, and
    a bidirectional marker when both directions exist. Blank when the zones
    are empty or no edge crosses the gap.
    """
    zone_of: dict[str, int] = {}
    for node in zone_nodes[0]:
        zone_of[node] = 0  # INBOUND
    for node in zone_nodes[1]:
        zone_of[node] = 1  # HUB
    for node in zone_nodes[2]:
        zone_of[node] = 2  # OUTBOUND

    counts: Counter[tuple[int, int]] = Counter()
    for edge in edges:
        if edge["from"] in zone_of and edge["to"] in zone_of:
            counts[(zone_of[edge["from"]], zone_of[edge["to"]])] += edge.get("count", 1)

    def connector(fr_zone: int, to_zone: int) -> str:
        forward = counts.get((fr_zone, to_zone), 0)
        backward = counts.get((to_zone, fr_zone), 0)
        fwd = f"═x{forward}═▶" if forward > 1 else "════▶"
        back = f"◀═x{backward}═" if backward > 1 else "◀════"
        if forward and backward:
            return f"◀x{backward}╡x{forward}▶"[:ZONE_GAP]
        if forward:
            return fwd.ljust(ZONE_GAP, "═")
        if backward:
            return back.rjust(ZONE_GAP, "═")
        return " " * ZONE_GAP

    return {
        "in->hub": connector(0, 1) if zone_nodes[0] and zone_nodes[1] else " " * ZONE_GAP,
        "hub->out": connector(1, 2) if zone_nodes[1] and zone_nodes[2] else " " * ZONE_GAP,
    }


def _explicit_zones(
    ctx: VerifyContext,
    nodes: list[str],
) -> tuple[list[str], list[list[str]], list[str]] | None:
    """Use three declared groups as semantic zones instead of graph inference."""
    configured = [(name, members) for name, members in ctx.groups.items() if members]
    if len(configured) != 3:
        return None

    available = set(nodes)
    seen = set()
    titles = []
    zones = []
    for name, members in configured:
        zone = [node for node in members if node in available and node not in seen]
        if not zone:
            return None
        seen.update(zone)
        zones.append(zone)
        titles.append(ctx.group_labels.get(name, name).upper())

    support = [node for node in nodes if node not in seen]
    return titles, zones, support


def _partition(
    nodes: list[str],
    edges: list[dict],
    focus: str | None,
) -> tuple[list[str], str, list[str], list[str]]:
    """Infer topology-neutral inbound / hub / outbound / support positions."""
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
        hub = focus
    elif connected:
        hub = max(
            connected,
            key=lambda node: (
                len(incoming[node]) + len(outgoing[node]),
                min(len(incoming[node]), len(outgoing[node])),
                len(outgoing[node]),
                -position[node],
            ),
        )
    else:
        hub = nodes[0]

    layers = assign_layers(nodes, edges)
    hub_layer = layers.get(hub, 0)
    inbound = []
    outbound = []
    support = []

    for node in nodes:
        if node == hub:
            continue
        if not incoming[node] and not outgoing[node]:
            support.append(node)
            continue

        layer = layers.get(node, hub_layer)
        if hub in outgoing[node] or layer < hub_layer:
            inbound.append(node)
        elif hub in incoming[node] or layer > hub_layer:
            outbound.append(node)
        elif outgoing[node] and not incoming[node]:
            inbound.append(node)
        else:
            outbound.append(node)

    inbound.sort(key=lambda node: (layers.get(node, 0), position[node]))
    outbound.sort(key=lambda node: (layers.get(node, 0), position[node]))
    support.sort(key=position.__getitem__)
    return inbound, hub, outbound, support


def _node_row(node: str, refs: dict[str, str], modules: dict) -> str:
    return f"[{refs[node]}] {modules[node].get('label', node)}"


def _core_rows(
    cores: list[str],
    refs: dict[str, str],
    modules: dict,
    inner_width: int,
) -> list[str]:
    """Draw the center zone as one or more double-framed chips."""
    chip_w = max(12, inner_width - 2)
    rows = []
    for index, core in enumerate(cores):
        if index:
            rows.append("")
        label = truncate_str(_node_row(core, refs, modules), chip_w - 2)
        rows.extend(
            [
                " " + "╔" + "═" * (chip_w - 2) + "╗",
                " " + "║" + pad_str(label, chip_w - 2, "center") + "║",
                " " + "╚" + "═" * (chip_w - 2) + "╝",
            ]
        )
    return rows


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
