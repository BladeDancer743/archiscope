"""Render package — main entry point delegates to geometry renderers."""

import re
from hashlib import sha256
from pathlib import Path
from typing import Optional

import yaml

from .ansi import color_enabled
from .geometry.correct.engine import correct
from .geometry.draw import RENDERERS
from .geometry.draw.grid import CharGrid, Rect
from .geometry.verify.engine import verify
from .geometry.verify.rules import VerifyContext
from .terminal import (
    TerminalEdge,
    TerminalRenderError,
    color_enabled,
    derive_terminal_edges,
    render_terminal,
    resolve_charset,
    strip_ansi,
)

PANORAMA_TOKENS = frozenset({"all", "全景"})


class RenderError(ValueError):
    """A malformed ownership graph cannot be rendered safely."""


def find_archmap() -> Path:
    current = Path.cwd()
    while current != current.parent:
        candidate = current / ".archmap.yaml"
        if candidate.exists():
            return current
        current = current.parent
    raise FileNotFoundError(".archmap.yaml not found in any parent directory")


def load_archmap(project_root: Optional[Path] = None) -> dict:
    root = project_root or find_archmap()
    path = root / ".archmap.yaml"
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_alias(data: dict, path: str) -> str:
    aliases = data.get("aliases", {})
    return aliases.get(path, path)


def find_root_module_path(data: dict) -> Optional[str]:
    """Return the configured root module without assuming its id is ``root``."""
    modules = data.get("modules", {})
    conventional = modules.get("root")
    if isinstance(conventional, dict) and conventional.get("type") == "root":
        return "root"

    for module_path, module in modules.items():
        if isinstance(module, dict) and module.get("type") == "root":
            return module_path
    return None


def resolve_module_path(data: dict, path: str) -> str:
    """Resolve aliases and portable panorama tokens to a concrete module id."""
    actual = resolve_alias(data, path)
    modules = data.get("modules", {})
    if path in PANORAMA_TOKENS:
        aliased = modules.get(actual)
        if isinstance(aliased, dict) and aliased.get("type") == "root":
            return actual
        return find_root_module_path(data) or actual
    return actual


def resolve_module(data: dict, path: str) -> Optional[dict]:
    actual = resolve_module_path(data, path)
    return data["modules"].get(actual)


def render_legacy(
    data: dict,
    module_path: str,
    zoom: str = "auto",
    depth: Optional[int] = None,
) -> str:
    """Original Mermaid renderer — kept for backward compatibility."""
    module_path = resolve_module_path(data, module_path)
    node = data["modules"].get(module_path)
    if not node:
        available = list(data.get("modules", {}).keys())
        return f"Module '{module_path}' not found. Available: {', '.join(available[:10])}"
    if node.get("type") == "root":
        panorama_depth = 1 if depth is None else max(0, depth)
        return _render_panorama(data, module_path, node, panorama_depth)
    return _render_engine_legacy(data, module_path, node)


def derive_edges(data: dict, scope: list[str]) -> list[dict]:
    """Build the edge list from module upstream/downstream declarations.

    This is what makes every geometric view show real topology without any
    extra YAML: `downstream: [b]` on module a becomes an a → b edge.
    """
    scope_set = set(scope)
    modules = data.get("modules", {})
    seen = set()
    edges = []

    def add(fr, to):
        if fr in scope_set and to in scope_set and fr != to and (fr, to) not in seen:
            seen.add((fr, to))
            edges.append({"from": fr, "to": to, "label": "", "line_cells": []})

    for m in scope:
        mod = modules.get(m, {})
        for d in mod.get("downstream") or []:
            add(m, d)
        for u in mod.get("upstream") or []:
            add(u, m)
    return edges


def derive_panorama_edges(data: dict, root_path: str) -> list[dict]:
    """Collapse curated root-level links to cross-domain edges."""
    modules = data.get("modules", {})
    root = modules.get(root_path, {})
    children = [child for child in (root.get("children") or []) if child in modules]
    child_set = set(children)
    owner_cache: dict[str, Optional[str]] = {}

    def owner(module_path: str) -> Optional[str]:
        if module_path in owner_cache:
            return owner_cache[module_path]
        current = module_path
        seen = set()
        while current in modules and current not in seen:
            seen.add(current)
            if current in child_set:
                owner_cache[module_path] = current
                return current
            parent = modules[current].get("parent")
            if parent == root_path or not parent:
                break
            current = parent
        owner_cache[module_path] = None
        return None

    edges: list[dict] = []
    by_pair: dict[tuple[str, str], dict] = {}

    def add(source_path: str, target_path: str, label: str = "") -> None:
        source = owner(source_path)
        target = owner(target_path)
        if not source or not target or source == target:
            return
        pair = (source, target)
        if pair in by_pair:
            edge = by_pair[pair]
            origin = (source_path, target_path)
            if origin not in edge["origins"]:
                edge["origins"].add(origin)
                edge["count"] += 1
            if label and label not in edge["labels"]:
                edge["labels"].append(label)
            edge["exact"] = edge["exact"] or origin == pair
            return
        edge = {
            "from": source,
            "to": target,
            "count": 1,
            "exact": (source_path, target_path) == pair,
            "origins": {(source_path, target_path)},
            "labels": [label] if label else [],
            "line_cells": [],
        }
        by_pair[pair] = edge
        edges.append(edge)

    # Root children are the curated abstraction boundary for a panorama.
    # Descendant edges are intentionally not aggregated by default: doing so
    # turns cross-cutting contracts and shared infrastructure into a hairball.
    for module_path in children:
        module = modules[module_path]
        for downstream in module.get("downstream") or []:
            add(module_path, downstream)
        for upstream in module.get("upstream") or []:
            add(upstream, module_path)

    for edge in root.get("edges") or []:
        if isinstance(edge, dict):
            add(edge.get("from", ""), edge.get("to", ""), edge.get("label", ""))

    for edge in edges:
        labels = edge.pop("labels")
        edge.pop("origins")
        label = labels[0] if len(labels) == 1 else ""
        if edge["count"] > 1:
            label = f"{label} x{edge['count']}".strip()
        edge["label"] = label
    return edges


def derive_visible_internal_edges(
    data: dict,
    root_path: str,
    visible_paths: list[str],
) -> list[dict]:
    """Project exact same-domain relationships onto the visible ownership depth.

    Ownership remains a nested-box concern. Only declared upstream/downstream or
    explicit edges become arrows. When several deeper relationships collapse to
    the same visible pair, ``count`` records the aggregation instead of emitting
    duplicate lines.
    """
    modules = data.get("modules", {})
    root = modules.get(root_path, {})
    domains = [child for child in (root.get("children") or []) if child in modules]
    domain_set = set(domains)
    visible_set = set(visible_paths)
    owner_cache: dict[str, Optional[str]] = {}
    representative_cache: dict[str, Optional[str]] = {}

    def owner(module_path: str) -> Optional[str]:
        if module_path in owner_cache:
            return owner_cache[module_path]
        current = module_path
        seen = set()
        while current in modules and current not in seen:
            seen.add(current)
            if current in domain_set:
                owner_cache[module_path] = current
                return current
            current = modules[current].get("parent")
        owner_cache[module_path] = None
        return None

    def representative(module_path: str) -> Optional[str]:
        if module_path in representative_cache:
            return representative_cache[module_path]
        current = module_path
        seen = set()
        while current in modules and current not in seen:
            seen.add(current)
            if current in visible_set:
                representative_cache[module_path] = current
                return current
            current = modules[current].get("parent")
        representative_cache[module_path] = None
        return None

    declared: dict[tuple[str, str], str] = {}

    def declare(source: str, target: str, label: str = "") -> None:
        if source not in modules or target not in modules or source == target:
            return
        pair = (source, target)
        if pair not in declared or label:
            declared[pair] = label

    for module_path, module in modules.items():
        for target in module.get("downstream") or []:
            declare(module_path, target)
        for source in module.get("upstream") or []:
            declare(source, module_path)
        for edge in module.get("edges") or []:
            if isinstance(edge, dict):
                declare(edge.get("from", ""), edge.get("to", ""), edge.get("label", ""))

    projected: dict[tuple[str, str], dict] = {}
    for (source, target), label in declared.items():
        source_owner = owner(source)
        target_owner = owner(target)
        if not source_owner or source_owner != target_owner:
            continue
        visible_source = representative(source)
        visible_target = representative(target)
        if (
            not visible_source
            or not visible_target
            or visible_source == visible_target
            or visible_source == source_owner
            or visible_target == target_owner
        ):
            continue

        pair = (visible_source, visible_target)
        entry = projected.setdefault(
            pair,
            {
                "from": visible_source,
                "to": visible_target,
                "count": 0,
                "collapsed": False,
                "exact": False,
                "labels": [],
                "line_cells": [],
            },
        )
        entry["count"] += 1
        entry["collapsed"] = entry["collapsed"] or pair != (source, target)
        entry["exact"] = entry["exact"] or pair == (source, target)
        if label and label not in entry["labels"]:
            entry["labels"].append(label)

    edges = []
    for entry in projected.values():
        labels = entry.pop("labels")
        label = labels[0] if len(labels) == 1 else ""
        if entry["count"] > 1:
            label = f"{label} x{entry['count']}".strip()
        entry["label"] = label
        edges.append(entry)
    return edges


def geometry_render(
    data: dict,
    module_path: str,
    strategy: str | None = None,
    color: str = "auto",
) -> str:
    """Render a geometric architecture view.

    Scope: the focus module's children when it has any; for a leaf module,
    its upstream + itself + downstream (context diagram, focus emphasized).

    ``color`` follows the same ``auto|always|never`` policy as the terminal
    overview; ``auto`` disables colors for non-TTY output.
    """
    modules = data.get("modules", {})
    actual = resolve_module_path(data, module_path)
    node = modules.get(actual)
    if not node:
        available = list(modules.keys())
        return f"Module '{module_path}' not found. Available: {', '.join(available[:10])}"

    children = [c for c in (node.get("children") or []) if c in modules]
    if children:
        scope = children
        focus = None
    else:
        ups = [u for u in (node.get("upstream") or []) if u in modules]
        downs = [d for d in (node.get("downstream") or []) if d in modules]
        scope = ups + [actual] + downs
        focus = actual

    edges = (
        derive_panorama_edges(data, actual)
        if node.get("type") == "root"
        else derive_edges(data, scope)
    )
    if node.get("type") != "root":
        by_pair = {(e["from"], e["to"]): e for e in edges}
        for e in node.get("edges") or []:  # explicit edges add labels / extra links
            fr, to = e.get("from", ""), e.get("to", "")
            if (fr, to) in by_pair:
                by_pair[(fr, to)]["label"] = e.get("label", "")
            elif fr in modules and to in modules and fr in scope and to in scope:
                edges.append({"from": fr, "to": to, "label": e.get("label", ""), "line_cells": []})

    effective_strategy = strategy or node.get("render_strategy") or "auto"
    group_configs = node.get("groups") or {}
    if effective_strategy == "swimlane" and node.get("lanes"):
        group_configs = {str(lane.get("id") or lane.get("label")): lane for lane in node["lanes"]}
    group_lists = {gname: gcfg.get("modules", []) for gname, gcfg in group_configs.items()}
    group_labels = {gname: str(gcfg.get("label", gname)) for gname, gcfg in group_configs.items()}

    terminal_w = 80
    ctx = VerifyContext(
        grid=CharGrid(terminal_w, 40),
        boxes={},
        edges=edges,
        groups=group_lists,
        modules={m: modules[m] for m in scope},
        terminal_width=terminal_w,
        focus=focus,
        group_labels=group_labels,
        color=color_enabled(color),
    )

    renderer = RENDERERS.get(effective_strategy)
    if renderer:
        return renderer(ctx)
    return (
        f"Strategy '{effective_strategy}' not found. "
        f"Available: {', '.join(sorted(RENDERERS.keys()))}"
    )


def _render_panorama(data: dict, root_path: str, root: dict, depth: int = 1) -> str:
    lines = [f"graph {root.get('layout', 'TD')}"]
    modules = data.get("modules", {})
    children = [child for child in (root.get("children") or []) if child in modules]
    groups = root.get("groups") or {}
    visible = _collect_hierarchy_paths(modules, children, depth)
    ids = _build_panorama_ids(modules, children, depth, groups)
    assigned = set()
    rendered = set()

    for group_name, group in groups.items():
        members = [member for member in (group.get("modules") or []) if member in children]
        if not members:
            continue
        label = group.get("label", group_name)
        group_id = ids[("group", str(group_name))]
        lines.append(f'  subgraph {group_id}["{_escape_mermaid_label(label)}"]')
        for child_path in members:
            _render_hierarchy(lines, modules, ids, child_path, depth, "    ", [], rendered)
            assigned.add(child_path)
        lines.append("  end")

    for child_path in children:
        if child_path not in assigned:
            _render_hierarchy(lines, modules, ids, child_path, depth, "  ", [], rendered)

    for edge in derive_visible_internal_edges(data, root_path, visible):
        source = ids[("module", edge["from"])]
        target = ids[("module", edge["to"])]
        label = _escape_mermaid_label(edge.get("label", ""), edge=True)
        connector = _mermaid_connector(label, exact=edge.get("exact", True))
        lines.append(f"  {source} {connector} {target}")

    for edge in derive_panorama_edges(data, root_path):
        source = ids[("module", edge["from"])]
        target = ids[("module", edge["to"])]
        label = _escape_mermaid_label(edge.get("label", ""), edge=True)
        connector = _mermaid_connector(label, exact=edge.get("exact", True))
        lines.append(f"  {source} {connector} {target}")
    return "\n".join(lines)


def _build_panorama_ids(
    modules: dict,
    children: list[str],
    depth: int,
    groups: dict,
) -> dict[tuple[str, str], str]:
    """Build one collision-safe Mermaid symbol table for nodes and groups."""
    visible = _collect_hierarchy_paths(modules, children, depth)
    desired: dict[tuple[str, str], str] = {
        ("module", module_path): f"m_{_mermaid_slug(module_path)}" for module_path in visible
    }
    child_set = set(children)
    for group_name, group in groups.items():
        if any(member in child_set for member in (group.get("modules") or [])):
            group_key = str(group_name)
            desired[("group", group_key)] = f"g_{_mermaid_slug(group_key)}"

    counts: dict[str, int] = {}
    for base in desired.values():
        counts[base] = counts.get(base, 0) + 1

    result = {}
    for key, base in desired.items():
        if counts[base] == 1:
            result[key] = base
            continue
        kind, raw = key
        digest = sha256(f"{kind}\0{raw}".encode()).hexdigest()[:8]
        result[key] = f"{base}_{digest}"
    return result


def _collect_hierarchy_paths(
    modules: dict,
    roots: list[str],
    depth: int,
) -> list[str]:
    visible: list[str] = []
    seen = set()

    def visit(module_path: str, remaining: int, active: list[str]) -> None:
        if module_path in active:
            cycle = " -> ".join(active[active.index(module_path) :] + [module_path])
            raise RenderError(f"Ownership cycle detected while rendering: {cycle}")
        if module_path in seen:
            raise RenderError(f"Module '{module_path}' appears more than once in ownership")
        seen.add(module_path)
        visible.append(module_path)
        if remaining <= 0:
            return
        next_active = active + [module_path]
        for child_path in modules[module_path].get("children") or []:
            if child_path in modules:
                visit(child_path, remaining - 1, next_active)

    for root in roots:
        visit(root, depth, [])
    return visible


def _render_hierarchy(
    lines: list[str],
    modules: dict,
    ids: dict[tuple[str, str], str],
    module_path: str,
    depth: int,
    indent: str,
    active: list[str],
    rendered: set[str],
) -> None:
    """Render ownership as nested subgraphs without inventing containment edges."""
    if module_path in active:
        cycle = " -> ".join(active[active.index(module_path) :] + [module_path])
        raise RenderError(f"Ownership cycle detected while rendering: {cycle}")
    if module_path in rendered:
        raise RenderError(f"Module '{module_path}' appears more than once in ownership")
    rendered.add(module_path)
    module = modules[module_path]
    label = _escape_mermaid_label(module.get("label", module_path))
    children = [child for child in (module.get("children") or []) if child in modules]
    module_id = ids[("module", module_path)]

    if depth > 0 and children:
        lines.append(f'{indent}subgraph {module_id}["{label}"]')
        lines.append(f"{indent}  direction {module.get('layout', 'TB')}")
        next_active = active + [module_path]
        for child_path in children:
            _render_hierarchy(
                lines,
                modules,
                ids,
                child_path,
                depth - 1,
                indent + "  ",
                next_active,
                rendered,
            )
        lines.append(f"{indent}end")
        return

    lines.append(f'{indent}{module_id}["{label}"]')


def _render_engine_legacy(data: dict, path: str, node: dict) -> str:
    lines = [f"graph {node.get('layout', 'TD')}"]
    label = _escape_mermaid_label(node.get("label", path))
    lines.append(f'  subgraph "{label}"')
    children = node.get("children", [])
    for child_path in children:
        child = data["modules"].get(child_path)
        if child:
            cid = _sanitize(child_path)
            clabel = _escape_mermaid_label(child.get("label", child_path))
            ct = child.get("type", "module")
            lines.append(f"    {cid}[{clabel}]" if ct != "layer" else f"    {cid}([{clabel}])")
    for child_path in children:
        child = data["modules"].get(child_path)
        if child:
            cid = _sanitize(child_path)
            for gc_path in child.get("children", []):
                lines.append(f"    {cid} --> {_sanitize(gc_path)}")
    lines.append("  end")
    for child_path in children:
        child = data["modules"].get(child_path)
        if child:
            cid = _sanitize(child_path)
            for down in child.get("downstream", []):
                lines.append(f"  {cid} -->|data| {_sanitize(down)}")
    return "\n".join(lines)


def _sanitize(path: str) -> str:
    return path.replace(".", "_").replace("-", "_").replace("/", "_")


def _mermaid_slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_]+", "_", str(value)).strip("_")
    return slug or "node"


def _escape_mermaid_label(value: object, *, edge: bool = False) -> str:
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("\n", "<br/>")
    )
    return text.replace("|", "&#124;") if edge else text


def _mermaid_connector(label: str, *, exact: bool) -> str:
    if exact:
        return f"-->|{label}|" if label else "-->"
    if not label:
        return "-.->"
    dotted_label = label.replace(".", "#46;").replace("-", "#45;")
    return f"-. {dotted_label} .->"
