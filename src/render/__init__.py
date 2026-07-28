"""Render package — main entry point delegates to geometry renderers."""

from .geometry.draw import RENDERERS
from .geometry.verify.rules import VerifyContext
from .geometry.verify.engine import verify
from .geometry.correct.engine import correct
from .geometry.draw.grid import CharGrid, Rect

import yaml
from pathlib import Path
from typing import Optional


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


def resolve_module(data: dict, path: str) -> Optional[dict]:
    if path in ("全景", "all"):
        return data["modules"].get("root")
    actual = resolve_alias(data, path)
    return data["modules"].get(actual)


def render_legacy(data: dict, module_path: str, zoom: str = "auto") -> str:
    """Original Mermaid renderer — kept for backward compatibility."""
    module_path = resolve_alias(data, module_path)
    if module_path in ("全景", "all"):
        node = data["modules"].get("root")
        if not node:
            return "root module not found in .archmap.yaml"
        return _render_panorama(data, node)
    node = data["modules"].get(module_path)
    if not node:
        available = list(data.get("modules", {}).keys())
        return f"Module '{module_path}' not found. Available: {', '.join(available[:10])}"
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


def geometry_render(data: dict, module_path: str, strategy: str = None) -> str:
    """Render a geometric architecture view.

    Scope: the focus module's children when it has any; for a leaf module,
    its upstream + itself + downstream (context diagram, focus emphasized).
    """
    modules = data.get("modules", {})
    actual = "root" if module_path in ("全景", "all") else resolve_alias(data, module_path)
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

    edges = derive_edges(data, scope)
    by_pair = {(e["from"], e["to"]): e for e in edges}
    for e in node.get("edges") or []:  # explicit edges add labels / extra links
        fr, to = e.get("from", ""), e.get("to", "")
        if (fr, to) in by_pair:
            by_pair[(fr, to)]["label"] = e.get("label", "")
        elif fr in modules and to in modules and fr in scope and to in scope:
            edges.append({"from": fr, "to": to,
                          "label": e.get("label", ""), "line_cells": []})

    group_lists = {gname: gcfg.get("modules", [])
                   for gname, gcfg in (node.get("groups") or {}).items()}

    terminal_w = 80
    ctx = VerifyContext(
        grid=CharGrid(terminal_w, 40), boxes={}, edges=edges, groups=group_lists,
        modules={m: modules[m] for m in scope},
        terminal_width=terminal_w, focus=focus,
    )

    strategy = strategy or node.get("render_strategy") or "auto"
    renderer = RENDERERS.get(strategy)
    if renderer:
        return renderer(ctx)
    return f"Strategy '{strategy}' not found. Available: {', '.join(sorted(RENDERERS.keys()))}"


def _render_panorama(data: dict, root: dict) -> str:
    lines = ["graph TD"]
    children = root.get("children", [])
    for child_path in children:
        child = data["modules"].get(child_path)
        if child:
            label = child.get("label", child_path)
            lines.append(f'  {_sanitize(child_path)}["{label}"]')
    for child_path in children:
        child = data["modules"].get(child_path)
        if child:
            for down in child.get("downstream", []):
                lines.append(f"  {_sanitize(child_path)} -->|data| {_sanitize(down)}")
    return "\n".join(lines)


def _render_engine_legacy(data: dict, path: str, node: dict) -> str:
    lines = ["graph TD"]
    label = node.get("label", path)
    lines.append(f'  subgraph "{label}"')
    children = node.get("children", [])
    for child_path in children:
        child = data["modules"].get(child_path)
        if child:
            cid = _sanitize(child_path)
            clabel = child.get("label", child_path)
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
