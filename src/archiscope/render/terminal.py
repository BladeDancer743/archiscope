"""Semantic, terminal-native architecture overview rendering.

The renderer deliberately separates layout from styling: every line is built
from plain-text spans first and ANSI foreground colors are injected only when
the final geometry is complete.  This keeps display-width calculations stable
for CJK labels and makes color a strictly optional information channel.
"""

from __future__ import annotations

import shutil
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TextIO

from ..semantics import (
    FEATURE_FAMILIES,
    RELATION_FAMILIES,
    SemanticError,
    iter_canonical_relations,
    relation_family,
    resolve_module_feature,
    validate_semantic_overlay,
)
from .ansi import (
    ANSI_COLORS,
    TerminalRenderError,
    color_enabled,
    resolve_theme,
    strip_ansi,
)
from .geometry.draw.grid import char_width, str_width, truncate_str


@dataclass(frozen=True)
class _Span:
    text: str
    style: str | None = None


@dataclass(frozen=True)
class _Text:
    """Plain-layout text with optional foreground-color annotations."""

    spans: tuple[_Span, ...] = ()

    @classmethod
    def plain(cls, value: object = "") -> "_Text":
        return cls((_Span(str(value)),)) if value != "" else cls()

    @classmethod
    def styled(cls, value: object, style: str) -> "_Text":
        return cls((_Span(str(value), style),)) if value != "" else cls()

    @property
    def value(self) -> str:
        return "".join(span.text for span in self.spans)

    @property
    def width(self) -> int:
        return str_width(self.value)

    def __add__(self, other: "_Text") -> "_Text":
        return _Text(self.spans + other.spans)

    def truncate(self, width: int, suffix: str = "...") -> "_Text":
        if width <= 0:
            return _Text()
        if self.width <= width:
            return self
        if str_width(suffix) > width:
            suffix = ""
        target = width - str_width(suffix)
        result: list[_Span] = []
        used = 0
        for span in self.spans:
            chars: list[str] = []
            for character in span.text:
                cell_width = char_width(character)
                if used + cell_width > target:
                    break
                chars.append(character)
                used += cell_width
            if chars:
                result.append(_Span("".join(chars), span.style))
            if used >= target or len(chars) != len(span.text):
                break
        if suffix:
            result.append(_Span(suffix))
        return _Text(tuple(result))

    def pad(self, width: int) -> "_Text":
        value = self.truncate(width)
        return value + _Text.plain(" " * max(0, width - value.width))

    def render(self, use_color: bool, color_map: Mapping[str, str] | None = None) -> str:
        if not use_color:
            return self.value
        palette = ANSI_COLORS if color_map is None else color_map
        rendered: list[str] = []
        for span in self.spans:
            code = palette.get(span.style or "")
            if code and span.text:
                rendered.append(f"\x1b[{code}m{span.text}\x1b[0m")
            else:
                rendered.append(span.text)
        return "".join(rendered)


def _join(parts: Iterable[_Text], separator: str = "") -> _Text:
    result = _Text()
    for index, part in enumerate(parts):
        if index:
            result += _Text.plain(separator)
        result += part
    return result


RELATION_TAGS = {
    "dependency": "DEP",
    "data": "DAT",
    "command": "CMD",
    "authority": "AUTH",
    "event": "EVT",
    "reference": "REF",
}

# ColorBrewer/Okabe-Ito-inspired foreground-only colors.  Structural glyphs
# and textual tags remain sufficient when these colors are removed.
@dataclass(frozen=True)
class ModuleSemantic:
    token: str
    family: str
    source: str


@dataclass
class TerminalEdge:
    """One visible semantic relation, possibly aggregating canonical edges."""

    source: str
    target: str
    kind: str
    family: str
    projected: bool
    count: int = 1
    labels: list[str] = field(default_factory=list)
    payload_types: list[str] = field(default_factory=list)
    bidirectional: bool = False
    reverse_count: int = 0

    @property
    def canonical_count(self) -> int:
        return self.count + self.reverse_count


@dataclass(frozen=True)
class _RawEdge:
    source: str
    target: str
    kind: str | None = None
    label: str = ""
    payload_type: str = ""
    container: str = ""
    explicit: bool = False


@dataclass(frozen=True)
class _ViewScope:
    focus: str
    visible: tuple[str, ...]
    top_level: tuple[str, ...]
    leaf: bool


def resolve_charset(mode: str, stream: TextIO | None = None) -> str:
    """Resolve ``auto|unicode|ascii`` against the output stream encoding."""

    if mode in {"unicode", "ascii"}:
        return mode
    if mode != "auto":
        raise TerminalRenderError(f"Unknown charset '{mode}'")
    encoding = getattr(stream or sys.stdout, "encoding", None) or "utf-8"
    try:
        "╔─▶●◆◇○▾".encode(encoding)
    except (LookupError, UnicodeEncodeError):
        return "ascii"
    return "unicode"


def resolve_module_semantic(
    data: Mapping,
    module_path: str,
    overlay: Mapping | None = None,
) -> ModuleSemantic:
    """Apply the shared deterministic semantic decision for one module."""

    try:
        decision = resolve_module_feature(data, module_path, overlay)
    except SemanticError as exc:
        raise TerminalRenderError(str(exc)) from exc
    return ModuleSemantic(
        str(decision["token"]),
        str(decision["family"]),
        str(decision["source"]),
    )


def _kind_family(data: Mapping, kind: str) -> str:
    family = relation_family(data, kind)
    if family is None:
        raise TerminalRenderError(f"Relation kind '{kind}' has no valid visual family")
    return str(family)


def _collect_raw_edges(data: Mapping, overlay: Mapping | None = None) -> list[_RawEdge]:
    """Consume the shared semantic resolver without inventing topology."""

    modules = data.get("modules") or {}
    owners: dict[tuple[str, str, str | None], list[str]] = {}
    for owner, module in modules.items():
        if not isinstance(module, Mapping):
            continue
        for edge in module.get("edges") or []:
            if not isinstance(edge, Mapping):
                continue
            source, target = edge.get("from"), edge.get("to")
            if isinstance(source, str) and isinstance(target, str):
                owners.setdefault((source, target, edge.get("kind")), []).append(str(owner))

    try:
        relations = iter_canonical_relations(data, overlay)
    except SemanticError as exc:
        raise TerminalRenderError(str(exc)) from exc
    result: list[_RawEdge] = []
    for relation in relations:
        source = str(relation["from"])
        target = str(relation["to"])
        kind = str(relation.get("kind") or "dependency")
        possible_owners = owners.get((source, target, kind), []) or owners.get(
            (source, target, None), []
        )
        # Prefer the root declaration when a pair is repeated as both a module
        # fact and a curated cross-domain relation.
        container = next(
            (
                owner
                for owner in possible_owners
                if isinstance(modules.get(owner), Mapping) and modules[owner].get("type") == "root"
            ),
            possible_owners[0] if possible_owners else "",
        )
        result.append(
            _RawEdge(
                source,
                target,
                kind,
                str(relation.get("label") or ""),
                str(relation.get("payload_type") or ""),
                container,
                relation.get("source") == "explicit",
            )
        )
    return result


def _parents(modules: Mapping, path: str) -> Iterable[str]:
    current: object = path
    seen: set[str] = set()
    while isinstance(current, str) and current in modules and current not in seen:
        seen.add(current)
        yield current
        module = modules[current]
        current = module.get("parent") if isinstance(module, Mapping) else None


def _is_descendant(modules: Mapping, path: str, ancestor: str) -> bool:
    return ancestor in _parents(modules, path)


def _collect_visible(
    modules: Mapping,
    roots: Sequence[str],
    depth: int,
) -> tuple[str, ...]:
    visible: list[str] = []
    seen: set[str] = set()

    def visit(path: str, remaining: int, active: tuple[str, ...]) -> None:
        if path in active:
            cycle = " -> ".join(active[active.index(path) :] + (path,))
            raise TerminalRenderError(f"Ownership cycle detected while rendering: {cycle}")
        if path in seen:
            raise TerminalRenderError(f"Module '{path}' appears more than once in ownership")
        if path not in modules:
            return
        seen.add(path)
        visible.append(path)
        if remaining <= 0:
            return
        module = modules[path]
        for child in module.get("children") or []:
            visit(str(child), remaining - 1, active + (path,))

    for root in roots:
        visit(root, depth, ())
    return tuple(visible)


def _view_scope(data: Mapping, focus: str, depth: int) -> _ViewScope:
    modules = data.get("modules") or {}
    node = modules[focus]
    children = tuple(child for child in (node.get("children") or []) if child in modules)
    if children:
        visible = _collect_visible(modules, children, depth)
        return _ViewScope(focus, visible, children, False)

    raw_edges = _collect_raw_edges(data)
    upstream = sorted({edge.source for edge in raw_edges if edge.target == focus})
    downstream = sorted({edge.target for edge in raw_edges if edge.source == focus})
    visible = tuple(dict.fromkeys(upstream + [focus] + downstream))
    return _ViewScope(focus, visible, visible, True)


def _representative(modules: Mapping, path: str, visible: set[str]) -> str | None:
    for candidate in _parents(modules, path):
        if candidate in visible:
            return candidate
    return None


def _curated_cross_domain_pairs(
    data: Mapping,
    root_path: str,
) -> tuple[set[tuple[str, str]], dict[str, str]]:
    """Return the root abstraction's exact curated origins and domain owners.

    This mirrors the legacy panorama contract: only direct root-child
    upstream/downstream declarations plus root ``edges`` opt a cross-domain
    relation into the overview.  Arbitrary descendant coupling is intentionally
    excluded.
    """

    modules = data.get("modules") or {}
    root = modules[root_path]
    domains = [path for path in (root.get("children") or []) if path in modules]
    domain_set = set(domains)
    owner_by_path: dict[str, str] = {}

    def owner(path: str) -> str | None:
        if path in owner_by_path:
            return owner_by_path[path]
        for candidate in _parents(modules, path):
            if candidate in domain_set:
                owner_by_path[path] = candidate
                return candidate
        return None

    candidates: list[tuple[str, str]] = []
    for domain in domains:
        module = modules[domain]
        candidates.extend((domain, str(target)) for target in module.get("downstream") or [])
        candidates.extend((str(source), domain) for source in module.get("upstream") or [])
    for edge in root.get("edges") or []:
        if isinstance(edge, Mapping):
            source, target = edge.get("from"), edge.get("to")
            if isinstance(source, str) and isinstance(target, str):
                candidates.append((source, target))

    curated: set[tuple[str, str]] = set()
    for source, target in candidates:
        source_owner = owner(source)
        target_owner = owner(target)
        if source_owner and target_owner and source_owner != target_owner:
            curated.add((source, target))
    # Prime the cache so uncurated descendant cross-links can be rejected too.
    for module_path in modules:
        owner(str(module_path))
    return curated, owner_by_path


def derive_terminal_edges(
    data: Mapping,
    focus: str,
    visible: Sequence[str],
    *,
    overlay: Mapping | None = None,
    leaf: bool = False,
) -> list[TerminalEdge]:
    """Project canonical relations without merging kind or projection status."""

    modules = data.get("modules") or {}
    focus_node = modules[focus]
    raw_edges = _collect_raw_edges(data, overlay)
    visible_set = set(visible)
    is_root_view = focus_node.get("type") == "root"
    curated_pairs: set[tuple[str, str]] = set()
    root_owners: dict[str, str] = {}
    if is_root_view:
        curated_pairs, root_owners = _curated_cross_domain_pairs(data, focus)

    expanded: list[_RawEdge] = []
    for raw in raw_edges:
        if leaf:
            if raw.source not in visible_set or raw.target not in visible_set:
                continue
        elif not (
            _is_descendant(modules, raw.source, focus)
            and _is_descendant(modules, raw.target, focus)
        ):
            continue
        elif is_root_view:
            source_owner = root_owners.get(raw.source)
            target_owner = root_owners.get(raw.target)
            # Cross-domain topology is curated only at the root abstraction.
            if source_owner != target_owner and (raw.source, raw.target) not in curated_pairs:
                continue

        expanded.append(raw)

    grouped: dict[tuple[str, str, str, bool], TerminalEdge] = {}
    for raw in expanded:
        source: str | None
        target: str | None
        if leaf:
            source, target = raw.source, raw.target
        elif is_root_view and root_owners.get(raw.source) != root_owners.get(raw.target):
            source, target = root_owners.get(raw.source), root_owners.get(raw.target)
        else:
            source = _representative(modules, raw.source, visible_set)
            target = _representative(modules, raw.target, visible_set)
        if not source or not target or source == target:
            continue
        projected = (source, target) != (raw.source, raw.target)
        kind = raw.kind or "dependency"
        family = _kind_family(data, kind)
        key = (source, target, kind, projected)
        edge = grouped.get(key)
        if edge is None:
            edge = TerminalEdge(source, target, kind, family, projected, count=0)
            grouped[key] = edge
        edge.count += 1
        if raw.label and raw.label not in edge.labels:
            edge.labels.append(raw.label)
        if raw.payload_type and raw.payload_type not in edge.payload_types:
            edge.payload_types.append(raw.payload_type)

    # Merge directions only when both semantic kind and projection status match.
    merged: list[TerminalEdge] = []
    consumed: set[tuple[str, str, str, bool]] = set()
    for key in sorted(grouped):
        if key in consumed:
            continue
        edge = grouped[key]
        reverse_key = (edge.target, edge.source, edge.kind, edge.projected)
        reverse = grouped.get(reverse_key)
        if reverse is not None and reverse_key != key:
            edge.bidirectional = True
            edge.reverse_count = reverse.count
            for label in reverse.labels:
                if label not in edge.labels:
                    edge.labels.append(label)
            for payload in reverse.payload_types:
                if payload not in edge.payload_types:
                    edge.payload_types.append(payload)
            consumed.add(reverse_key)
        consumed.add(key)
        merged.append(edge)
    return merged


_RANK_FAMILY_PRIORITY = {
    "authority": 0,
    "command": 1,
    "data": 2,
    "event": 3,
    "reference": 4,
    "dependency": 5,
}


def _logical_layers(
    nodes: Sequence[str],
    edges: Sequence[TerminalEdge],
) -> tuple[tuple[tuple[str, ...], ...], tuple[str, ...], dict[str, int]]:
    """Build width-independent ranks for the vertical layered-bus view.

    The ranking graph is deliberately not the rendered graph.  Cyclic
    constraints are retained as feedback routes; no visible relation is
    deleted and no single longest path is promoted to a visual main chain.
    """

    order = {path: index for index, path in enumerate(nodes)}
    node_set = set(nodes)
    incident: dict[str, set[str]] = {path: set() for path in nodes}
    visible_edges = [edge for edge in edges if edge.source in node_set and edge.target in node_set]
    for edge in visible_edges:
        incident[edge.source].add(edge.target)
        incident[edge.target].add(edge.source)

    isolated = tuple(path for path in nodes if not incident[path])
    connected = [path for path in nodes if incident[path]]
    components: list[tuple[str, ...]] = []
    unseen = set(connected)
    for start in connected:
        if start not in unseen:
            continue
        stack = [start]
        unseen.remove(start)
        members: list[str] = []
        while stack:
            current = stack.pop()
            members.append(current)
            for target in sorted(incident[current], key=order.__getitem__, reverse=True):
                if target in unseen:
                    unseen.remove(target)
                    stack.append(target)
        components.append(tuple(sorted(members, key=order.__getitem__)))

    ranks: dict[str, int] = {}
    for component in components:
        component_set = set(component)
        component_edges = [
            edge
            for edge in visible_edges
            if not edge.bidirectional
            and edge.source in component_set
            and edge.target in component_set
        ]
        core_families = {"authority", "command", "data"}
        rank_edges = [edge for edge in component_edges if edge.family in core_families]
        if not rank_edges:
            rank_edges = component_edges

        best_by_pair: dict[tuple[str, str], TerminalEdge] = {}
        for edge in rank_edges:
            pair = (edge.source, edge.target)
            key = (
                _RANK_FAMILY_PRIORITY[edge.family],
                int(edge.projected),
                order[edge.source],
                order[edge.target],
                edge.kind,
            )
            current = best_by_pair.get(pair)
            if current is None:
                best_by_pair[pair] = edge
                continue
            current_key = (
                _RANK_FAMILY_PRIORITY[current.family],
                int(current.projected),
                order[current.source],
                order[current.target],
                current.kind,
            )
            if key < current_key:
                best_by_pair[pair] = edge

        constraints = sorted(
            best_by_pair.values(),
            key=lambda edge: (
                _RANK_FAMILY_PRIORITY[edge.family],
                int(edge.projected),
                order[edge.source],
                order[edge.target],
                edge.kind,
            ),
        )
        adjacency: dict[str, set[str]] = {path: set() for path in component}

        def reaches(start: str, wanted: str) -> bool:
            pending = [start]
            seen: set[str] = set()
            while pending:
                current = pending.pop()
                if current == wanted:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(adjacency[current] - seen)
            return False

        for edge in constraints:
            if edge.source == edge.target or reaches(edge.target, edge.source):
                continue
            adjacency[edge.source].add(edge.target)

        indegree = {path: 0 for path in component}
        for targets in adjacency.values():
            for target in targets:
                indegree[target] += 1
        ready = sorted(
            (path for path in component if indegree[path] == 0),
            key=order.__getitem__,
        )
        component_rank = {path: 0 for path in component}
        while ready:
            source = ready.pop(0)
            for target in sorted(adjacency[source], key=order.__getitem__):
                component_rank[target] = max(component_rank[target], component_rank[source] + 1)
                indegree[target] -= 1
                if indegree[target] == 0:
                    ready.append(target)
                    ready.sort(key=order.__getitem__)
        ranks.update(component_rank)

    used_ranks = sorted(set(ranks.values()))
    compact_rank = {rank: index for index, rank in enumerate(used_ranks)}
    ranks = {path: compact_rank[rank] for path, rank in ranks.items()}
    layers = tuple(
        tuple(path for path in nodes if ranks.get(path) == rank) for rank in range(len(used_ranks))
    )
    return layers, isolated, ranks


def _route_class(edge: TerminalEdge, ranks: Mapping[str, int]) -> str:
    if edge.bidirectional:
        return "bidirectional"
    source_rank = ranks[edge.source]
    target_rank = ranks[edge.target]
    if source_rank == target_rank:
        return "lateral"
    return "forward" if source_rank < target_rank else "feedback"


def _type_frame(module_type: str, charset: str) -> tuple[str, str, str]:
    if charset == "ascii":
        return {
            "root": ("[[", "]]", "="),
            "engine": ("[[", "]]", "="),
            "layer": ("##", "##", "#"),
            "module": ("[", "]", "-"),
            "rule": ("<.", ".>", "."),
            "function": ("(", ")", "-"),
        }.get(module_type, ("[", "]", "-"))
    return {
        "root": ("╔═", "═╗", "═"),
        "engine": ("╔═", "═╗", "═"),
        "layer": ("┏━", "━┓", "━"),
        "module": ("┌─", "─┐", "─"),
        "rule": ("◇╌", "╌◇", "╌"),
        "function": ("(", ")", "─"),
    }.get(module_type, ("┌─", "─┐", "─"))


def _module_chip(
    data: Mapping,
    path: str,
    charset: str,
    overlay: Mapping | None,
    *,
    focus: bool = False,
) -> _Text:
    module = data["modules"][path]
    semantic = resolve_module_semantic(data, path, overlay)
    left, right, _ = _type_frame(str(module.get("type") or "module"), charset)
    dot = "*" if charset == "ascii" else "●"
    children = [child for child in (module.get("children") or []) if child in data["modules"]]
    expansion = (
        (f"v{len(children)}" if charset == "ascii" else f"▾{len(children)}")
        if children
        else ("*" if charset == "ascii" else "•")
    )
    frame_left = _Text.styled(left + " ", "focus") if focus else _Text.plain(left + " ")
    frame_right = _Text.styled(right, "focus") if focus else _Text.plain(right)
    return (
        frame_left
        + _Text.styled(dot, semantic.family)
        + _Text.plain(" ")
        + _Text.styled(f"[{semantic.token.upper()}]", semantic.family)
        + _Text.plain(f" {module.get('label', path)} {expansion} ")
        + frame_right
    )


def _relation_connector(edge: TerminalEdge, charset: str) -> _Text:
    family = edge.family
    if charset == "ascii":
        marker = {
            "dependency": "-",
            "data": "o",
            "command": "!",
            "authority": "*",
            "event": "o",
            "reference": ":",
        }[family]
        if edge.projected:
            shaft = f".{marker}.."
        else:
            shaft = f"-{marker}--"
        value = f"<{shaft}>" if edge.bidirectional else f"{shaft}>"
    else:
        marker = {
            "dependency": "─",
            "data": "●",
            "command": "!",
            "authority": "◆",
            "event": "○",
            "reference": "◇",
        }[family]
        line = "┄" if edge.projected else "─"
        shaft = f"{line}{marker}{line * 3}"
        value = f"◀{shaft}▶" if edge.bidirectional else f"{shaft}▶"
    return _Text.styled(value, family)


def _edge_line(data: Mapping, edge: TerminalEdge, charset: str) -> _Text:
    modules = data["modules"]
    tag = f"[{RELATION_TAGS[edge.family]}]"
    source = str(modules[edge.source].get("label", edge.source))
    target = str(modules[edge.target].get("label", edge.target))
    count = f" x{edge.canonical_count}" if edge.canonical_count > 1 else ""
    details: list[str] = []
    if edge.kind != edge.family:
        details.append(edge.kind)
    details.extend(edge.payload_types)
    details.extend(edge.labels)
    detail = f" ({'; '.join(details)})" if details else ""
    status = " projected" if edge.projected else ""
    return (
        _Text.styled(tag, edge.family)
        + _Text.plain(f" {source} ")
        + _relation_connector(edge, charset)
        + _Text.plain(f" {target}{count}{status}{detail}")
    )


def _pack(items: Sequence[_Text], width: int, gap: str = "   ") -> list[_Text]:
    if not items:
        return []
    lines: list[_Text] = []
    current = _Text()
    gap_width = str_width(gap)
    for item in items:
        item = item.truncate(width)
        if current.width and current.width + gap_width + item.width > width:
            lines.append(current)
            current = item
        else:
            current = item if not current.width else current + _Text.plain(gap) + item
    if current.width:
        lines.append(current)
    return lines


def _rule(label: str, width: int, charset: str) -> _Text:
    fill = "-" if charset == "ascii" else "─"
    prefix = f" {label} "
    return _Text.styled(prefix + fill * max(0, width - str_width(prefix)), "heading").truncate(
        width
    )


def _ownership_lines(
    data: Mapping,
    scope: _ViewScope,
    charset: str,
    width: int,
    overlay: Mapping | None,
) -> list[_Text]:
    modules = data["modules"]
    visible = set(scope.visible)
    branch = (
        {"mid": "+-", "last": "`-", "pipe": "| "}
        if charset == "ascii"
        else {
            "mid": "├─",
            "last": "└─",
            "pipe": "│ ",
        }
    )
    lines: list[_Text] = []

    def visit(path: str, prefix: str, last: bool) -> None:
        connector = branch["last" if last else "mid"]
        line = _Text.plain(prefix + connector) + _module_chip(data, path, charset, overlay)
        lines.append(line.truncate(width, "..." if charset == "ascii" else "…"))
        children = [child for child in (modules[path].get("children") or []) if child in visible]
        next_prefix = prefix + ("  " if last else branch["pipe"])
        for index, child in enumerate(children):
            visit(child, next_prefix, index == len(children) - 1)

    roots = list(scope.top_level)
    for index, path in enumerate(roots):
        visit(path, "", index == len(roots) - 1)
    return lines


def _focus_frame(
    data: Mapping,
    focus: str,
    charset: str,
    width: int,
    overlay: Mapping | None,
) -> tuple[_Text, _Text]:
    module = data["modules"][focus]
    left, right, fill = _type_frame(str(module.get("type") or "module"), charset)
    chip = _module_chip(data, focus, charset, overlay, focus=True)
    label = _Text.plain(left + " OWNERSHIP ") + chip + _Text.plain(" ")
    right_width = str_width(right)
    top = label.truncate(max(0, width - right_width))
    top += _Text.plain(fill * max(0, width - top.width - right_width) + right)
    bottom_left = {
        "╔═": "╚═",
        "┏━": "┗━",
        "┌─": "└─",
        "◇╌": "◇╌",
        "[[": "[[",
        "##": "##",
        "[": "[",
        "<.": "<.",
        "(": "(",
    }.get(left, left)
    bottom_right = {
        "═╗": "═╝",
        "━┓": "━┛",
        "─┐": "─┘",
        "╌◇": "╌◇",
        "]]": "]]",
        "##": "##",
        "]": "]",
        ".>": ".>",
        ")": ")",
    }.get(right, right)
    bottom = _Text.plain(
        bottom_left
        + fill * max(0, width - str_width(bottom_left) - str_width(bottom_right))
        + bottom_right
    ).truncate(width)
    return top, bottom


def _legend(charset: str, width: int) -> list[_Text]:
    items: list[_Text] = []
    for family in RELATION_FAMILIES:
        example = TerminalEdge("", "", family, family, False)
        items.append(
            _Text.styled(f"[{RELATION_TAGS[family]}]", family)
            + _Text.plain(" ")
            + _relation_connector(example, charset)
        )
    direct = "direct=- projected=." if charset == "ascii" else "direct=─ projected=┄"
    items.append(_Text.plain(direct))
    items.append(_Text.plain("xN=canonical relations"))
    if charset == "ascii":
        module_items = (
            _Text.styled("* [FEATURE]", "neutral") + _Text.plain(" feature"),
            _Text.plain("[[ ]] engine"),
            _Text.plain("## ## layer"),
            _Text.plain("[ ] module"),
            _Text.plain("<. .> rule"),
            _Text.plain("( ) function"),
            _Text.plain("vN=expandable"),
            _Text.plain("*=leaf"),
        )
    else:
        module_items = (
            _Text.styled("● [FEATURE]", "neutral") + _Text.plain(" feature"),
            _Text.plain("╔═ ═╗ engine"),
            _Text.plain("┏━ ━┓ layer"),
            _Text.plain("┌─ ─┐ module"),
            _Text.plain("◇╌ ╌◇ rule"),
            _Text.plain("( ) function"),
            _Text.plain("▾N=expandable"),
            _Text.plain("•=leaf"),
        )
    items.extend(module_items)
    return _pack(items, width, "  ")


def _boxed_frame(module_type: str, charset: str) -> tuple[str, str, str, str, str, str]:
    """Return top fill, top corners, side walls, and bottom corners for a node."""

    if charset == "ascii":
        return {
            "root": ("=", "+", "+", "||", "+", "+"),
            "engine": ("=", "+", "+", "||", "+", "+"),
            "layer": ("#", "+", "+", "#", "+", "+"),
            "module": ("-", "+", "+", "|", "+", "+"),
            "rule": (".", "<", ">", ":", "<", ">"),
            "function": ("-", "(", ")", "(", "(", ")"),
        }.get(module_type, ("-", "+", "+", "|", "+", "+"))
    return {
        "root": ("═", "╔", "╗", "║", "╚", "╝"),
        "engine": ("═", "╔", "╗", "║", "╚", "╝"),
        "layer": ("━", "┏", "┓", "┃", "┗", "┛"),
        "module": ("─", "┌", "┐", "│", "└", "┘"),
        "rule": ("╌", "◇", "◇", "┊", "◇", "◇"),
        "function": ("─", "(", ")", "(", "(", ")"),
    }.get(module_type, ("─", "┌", "┐", "│", "└", "┘"))


def _module_box_content(
    data: Mapping,
    path: str,
    charset: str,
    overlay: Mapping | None,
) -> _Text:
    module = data["modules"][path]
    semantic = resolve_module_semantic(data, path, overlay)
    dot = "*" if charset == "ascii" else "●"
    children = [child for child in (module.get("children") or []) if child in data["modules"]]
    expansion = (
        (f"v{len(children)}" if charset == "ascii" else f"▾{len(children)}")
        if children
        else ("*" if charset == "ascii" else "•")
    )
    return (
        _Text.styled(dot, semantic.family)
        + _Text.plain(" ")
        + _Text.styled(f"[{semantic.token.upper()}]", semantic.family)
        + _Text.plain(f" {module.get('label', path)} {expansion}")
    )


def _centered(value: _Text, width: int) -> _Text:
    return _Text.plain(" " * max(0, (width - value.width) // 2)) + value


def _module_box(
    data: Mapping,
    path: str,
    charset: str,
    canvas_width: int,
    box_width: int,
    overlay: Mapping | None,
    *,
    focus: bool = False,
) -> list[_Text]:
    module_type = str(data["modules"][path].get("type") or "module")
    fill, top_left, top_right, side, bottom_left, bottom_right = _boxed_frame(module_type, charset)
    right_side = ")" if module_type == "function" else side
    content = _module_box_content(data, path, charset, overlay)
    inner_width = max(1, box_width - str_width(side) - str_width(right_side))
    top_fill = fill * max(0, box_width - str_width(top_left) - str_width(top_right))
    bottom_fill = fill * max(0, box_width - str_width(bottom_left) - str_width(bottom_right))
    border_style = "focus" if focus else None

    def border(value: str) -> _Text:
        return _Text.styled(value, border_style) if border_style else _Text.plain(value)

    top = border(top_left + top_fill + top_right)
    middle = border(side) + content.truncate(inner_width).pad(inner_width) + border(right_side)
    bottom = border(bottom_left + bottom_fill + bottom_right)
    return [_centered(line, canvas_width) for line in (top, middle, bottom)]


def _primary_vertical_path(nodes: Sequence[str], edges: Sequence[TerminalEdge]) -> tuple[str, ...]:
    """Choose a stable, real, forward-only path without inventing topology."""

    if not nodes:
        return ()
    order = {path: index for index, path in enumerate(nodes)}
    adjacency: dict[str, set[str]] = {path: set() for path in nodes}
    for edge in edges:
        if edge.source not in order or edge.target not in order:
            continue
        source, target = edge.source, edge.target
        if edge.bidirectional and order[source] > order[target]:
            source, target = target, source
        if order[source] < order[target]:
            adjacency[source].add(target)

    best_from: dict[str, tuple[str, ...]] = {}
    for source in reversed(nodes):
        candidates = [
            (source, *best_from[target])
            for target in sorted(adjacency[source], key=order.__getitem__)
        ]
        best_from[source] = max(
            candidates or [(source,)],
            key=lambda path: (len(path), tuple(-order[item] for item in path)),
        )
    return max(
        (best_from[path] for path in nodes),
        key=lambda path: (len(path), tuple(-order[item] for item in path)),
    )


def _edge_connects_path_step(edge: TerminalEdge, source: str, target: str) -> bool:
    if edge.source == source and edge.target == target:
        return True
    return edge.bidirectional and edge.source == target and edge.target == source


def _vertical_edge_label(edge: TerminalEdge, charset: str, width: int) -> _Text:
    shaft = (
        ":"
        if charset == "ascii" and edge.projected
        else "|"
        if charset == "ascii"
        else "┆"
        if edge.projected
        else "│"
    )
    if edge.bidirectional:
        shaft = "^v" if charset == "ascii" else "↕"
    marker = {
        "dependency": "-" if charset == "ascii" else "─",
        "data": "o" if charset == "ascii" else "●",
        "command": "!",
        "authority": "*" if charset == "ascii" else "◆",
        "event": "o" if charset == "ascii" else "○",
        "reference": ":" if charset == "ascii" else "◇",
    }[edge.family]
    count = f" x{edge.canonical_count}" if edge.canonical_count > 1 else ""
    status = " projected" if edge.projected else ""
    details: list[str] = []
    if edge.kind != edge.family:
        details.append(edge.kind)
    details.extend(edge.payload_types)
    details.extend(edge.labels)
    detail = f" ({'; '.join(details)})" if details else ""
    value = (
        _Text.styled(shaft, edge.family)
        + _Text.plain(" ")
        + _Text.styled(f"[{RELATION_TAGS[edge.family]}]", edge.family)
        + _Text.plain(" ")
        + _Text.styled(marker, edge.family)
        + _Text.plain(f"{count}{status}{detail}")
    )
    return value.truncate(width, "..." if charset == "ascii" else "…")


def _compact_node_ref(
    data: Mapping,
    path: str,
    charset: str,
    width: int,
    overlay: Mapping | None,
) -> _Text:
    module = data["modules"][path]
    semantic = resolve_module_semantic(data, path, overlay)
    left, right = "[", "]"
    dot = "*" if charset == "ascii" else "●"
    inner_width = max(1, width - str_width(left) - str_width(right) - 2)
    content = (
        _Text.styled(dot, semantic.family)
        + _Text.plain(" ")
        + _Text.plain(str(module.get("label", path)))
    ).truncate(inner_width, "..." if charset == "ascii" else "…")
    return _Text.plain(left + " ") + content.pad(inner_width) + _Text.plain(" " + right)


def _boxed_cross_link(
    data: Mapping,
    edge: TerminalEdge,
    charset: str,
    width: int,
    overlay: Mapping | None,
) -> _Text:
    tag = _Text.styled(f"[{RELATION_TAGS[edge.family]}]", edge.family)
    connector = _relation_connector(edge, charset)
    count = f" x{edge.canonical_count}" if edge.canonical_count > 1 else ""
    status = " projected" if edge.projected else ""
    fixed = tag.width + connector.width + str_width(count + status) + 4
    endpoint_width = max(8, (width - fixed) // 2)
    source = _compact_node_ref(data, edge.source, charset, endpoint_width, overlay)
    target = _compact_node_ref(data, edge.target, charset, endpoint_width, overlay)
    line = (
        source
        + _Text.plain(" ")
        + tag
        + _Text.plain(" ")
        + connector
        + _Text.plain(" ")
        + target
        + _Text.plain(count + status)
    )
    return line.truncate(width, "..." if charset == "ascii" else "…")


def _layer_box_rows(
    data: Mapping,
    paths: Sequence[str],
    charset: str,
    width: int,
    overlay: Mapping | None,
    *,
    focus: str,
) -> tuple[list[_Text], dict[str, tuple[int, int]]]:
    """Pack one logical layer into stable, width-dependent physical rows.

    Returns the rows plus per-path display-column spans (inclusive, both
    borders), which the route lanes use to terminate their vertical
    connector lines on the correct frame.
    """

    if not paths:
        return [], {}
    gap = 3
    minimum_box_width = 24
    per_row = max(1, (width + gap) // (minimum_box_width + gap))
    lines: list[_Text] = []
    spans: dict[str, tuple[int, int]] = {}
    for start in range(0, len(paths), per_row):
        chunk = paths[start : start + per_row]
        # A logical layer is 1..N nodes, never a fixed one- or two-column
        # template.  A lone module gets a content-sized, centered frame
        # instead of a full-width bar; multi-module rows share the width.
        if len(chunk) == 1:
            label = data["modules"][chunk[0]].get("label", chunk[0])
            semantic_prefix = 12  # "● [FAMILY] " inside the frame
            box_width = min(
                max(str_width(label) + semantic_prefix + 4, 20), width - 4
            )
        else:
            box_width = max(16, (width - gap * (len(chunk) - 1)) // len(chunk))
        rendered = [
            _module_box(
                data,
                path,
                charset,
                box_width,
                box_width,
                overlay,
                focus=path == focus,
            )
            for path in chunk
        ]
        group_width = box_width * len(chunk) + gap * (len(chunk) - 1)
        left_padding = max(0, (width - group_width) // 2)
        for box_index, box in enumerate(rendered):
            path = chunk[box_index]
            x0 = left_padding + box_index * (box_width + gap)
            spans[path] = (x0, x0 + box_width - 1)
        for line_index in range(3):
            row = _Text.plain(" " * left_padding)
            for box_index, box in enumerate(rendered):
                if box_index:
                    row += _Text.plain(" " * gap)
                row += box[line_index].pad(box_width)
            lines.append(row.truncate(width))
    return lines, spans


def _char_at_column(text: _Text, column: int) -> str:
    """The character occupying a display column (wide chars span two)."""
    used = 0
    for span in text.spans:
        for character in span.text:
            width = char_width(character)
            if used == column:
                return character
            used += width
            if used > column:
                return character
    return " "


def _overlay_column(text: _Text, column: int, ch: str) -> _Text:
    """Replace the character at a display column, keeping all other spans.

    When the column lies beyond the current text, the text is padded with
    spaces up to it so the overlay character still lands at the right
    display column (route lanes may target shorter lines such as the ``L1``
    label row).
    """
    spans = list(text.spans)
    out: list[_Span] = []
    used = 0
    for index, span in enumerate(spans):
        width = str_width(span.text)
        if used + width <= column:
            out.append(span)
            used += width
            continue
        head: list[str] = []
        tail: list[str] = []
        for character in span.text:
            cw = char_width(character)
            if used + cw <= column:
                head.append(character)
                used += cw
            elif used == column:
                # The character starts at the target column — drop it; the
                # overlay character replaces it (same cell width).
                used += cw
            elif used < column:
                # A wide char straddles the column — drop it and pad with
                # spaces so the display width is preserved.
                used += cw
                tail.append(" " * cw)
            else:
                tail.append(character)
                used += cw
        if head:
            out.append(_Span("".join(head), span.style))
        out.append(_Span(ch))
        if tail:
            out.append(_Span("".join(tail), span.style))
        out.extend(spans[index + 1 :])
        return _Text(tuple(out))
    # Column beyond every span — pad up to it, then place the character.
    out.append(_Span(" " * (column - used) + ch))
    return _Text(tuple(out))


def _route_lane(
    data: Mapping,
    edge: TerminalEdge,
    route_class: str,
    ranks: Mapping[str, int],
    charset: str,
    width: int,
) -> _Text:
    modules = data["modules"]
    tag = _Text.styled(f"[{RELATION_TAGS[edge.family]}]", edge.family)
    marker = {
        "dependency": "-" if charset == "ascii" else "─",
        "data": "o" if charset == "ascii" else "●",
        "command": "!",
        "authority": "*" if charset == "ascii" else "◆",
        "event": "o" if charset == "ascii" else "○",
        "reference": ":" if charset == "ascii" else "◇",
    }[edge.family]
    shaft = (
        ("." if charset == "ascii" else "┄")
        if edge.projected
        else ("-" if charset == "ascii" else "─")
    )
    branch = "+" if charset == "ascii" else "├"
    arrow = {
        "forward": "v" if charset == "ascii" else "▼",
        "lateral": ">" if charset == "ascii" else "▶",
        "feedback": "^" if charset == "ascii" else "▲",
        "bidirectional": "^v" if charset == "ascii" else "↕",
    }[route_class]
    target = str(modules[edge.target].get("label", edge.target))
    count = f" x{edge.canonical_count}" if edge.canonical_count > 1 else ""
    details: list[str] = []
    if edge.kind != edge.family:
        details.append(edge.kind)
    details.extend(edge.payload_types)
    details.extend(edge.labels)
    detail = f" ({'; '.join(details)})" if details else ""
    status = " projected" if edge.projected else ""
    lane = (
        _Text.plain(f"    {branch}{shaft * 2}")
        + tag
        + _Text.styled(f"{shaft}{marker}{shaft * 2}{arrow}", edge.family)
        + _Text.plain(f" L{ranks[edge.target]} {target}{count}{status}{detail}")
    )
    return lane.truncate(width, "..." if charset == "ascii" else "…")


def _route_role(
    data: Mapping,
    source: str,
    edge: TerminalEdge,
    ranks: Mapping[str, int],
) -> str:
    """Classify one lane without guessing from module names or descriptions."""

    modules = data["modules"]
    source_module = modules[source]
    target_module = modules[edge.target]
    route_class = _route_class(edge, ranks)
    if (
        source_module.get("type") == "engine"
        and target_module.get("type") == "engine"
        and edge.family in {"data", "command"}
        and not edge.projected
    ):
        return "ENGINE MESH"
    if route_class == "forward" and edge.family in {"authority", "command"}:
        return "CONTROL FAN-OUT BUS"
    if route_class in {"feedback", "bidirectional"}:
        return "OUTER FEEDBACK BUS"
    return "ROUTE BUS"


def _render_vertical_layered_topology(
    data: Mapping,
    scope: _ViewScope,
    edges: Sequence[TerminalEdge],
    charset: str,
    width: int,
    overlay: Mapping | None,
    depth: int = 1,
) -> list[_Text]:
    """Render all visible nodes and routes as one top-to-bottom bus canvas."""

    nodes = tuple(scope.top_level)
    node_set = set(nodes)
    topology_edges = [edge for edge in edges if edge.source in node_set and edge.target in node_set]
    layers, isolated, ranks = _logical_layers(nodes, topology_edges)
    order = {path: index for index, path in enumerate(nodes)}
    edges_by_source: dict[str, list[TerminalEdge]] = {path: [] for path in nodes}
    for edge in topology_edges:
        edges_by_source[edge.source].append(edge)
    for source_edges in edges_by_source.values():
        source_edges.sort(
            key=lambda edge: (
                ranks[edge.target],
                order[edge.target],
                _RANK_FAMILY_PRIORITY[edge.family],
                edge.kind,
                edge.projected,
            )
        )

    heading = (
        "VERTICAL LAYERED BUS TOPOLOGY"
        if charset == "ascii"
        else "VERTICAL LAYERED BUS TOPOLOGY / 纵向分层总线拓扑"
    )
    lines = [_rule(heading, width, charset)]

    # Full-chain graphs (every layer holds exactly one module and adjacent
    # layers are directly connected, e.g. Probe→Forge→Reach→…) render as one
    # compact horizontal row with arrows instead of six full-width frames —
    # the vertical stack of single boxes was low-density and hard to read.
    # Chain-row mode is only for strict pipelines: every layer holds ≤2
    # modules, adjacent layers are directly connected, and — crucially — no
    # edge skips a layer. A mesh (each module talking to several others
    # across layers, e.g. the six-engine graph) must not be flattened into
    # a line; it keeps the vertical layout with lanes and connectors.
    chain_ok = (
        len(layers) > 1
        and all(len(layer) <= 2 for layer in layers)
        and all(
            any(
                (a, b) in {(edge.source, edge.target) for edge in topology_edges}
                for a in layers[rank]
                for b in layers[rank + 1]
            )
            for rank in range(len(layers) - 1)
        )
        and not any(
            abs(ranks.get(edge.source, 0) - ranks.get(edge.target, 0)) > 1
            for edge in topology_edges
        )
    )
    if chain_ok:
        chain_layers = layers
        lines.append(_Text.styled(f"L0-L{len(chain_layers) - 1} 链式流", "heading"))
        lines.extend(
            _render_chain_row(
                data,
                chain_layers,
                topology_edges,
                charset,
                width,
                overlay,
                scope.focus,
                depth,
            )
        )
        cross_links = _cross_engine_child_links(data, chain_layers)
        for source_label, target_label, family, count in cross_links:
            lines.append(
                _Text.plain("  子模块链接: ")
                + _Text.styled(f"{source_label} ─▶ {target_label}", family)
                + (_Text.plain(f" x{count}") if count > 1 else _Text.plain(""))
            )
        feedback: dict[tuple[str, str], int] = {}
        for edge in topology_edges:
            if ranks.get(edge.target, 0) < ranks.get(edge.source, 0):
                feedback[(edge.source, edge.target)] = (
                    feedback.get((edge.source, edge.target), 0) + edge.canonical_count
                )
        for (source_path, target_path), count in sorted(feedback.items()):
            source = data["modules"][source_path].get("label", source_path)
            target = data["modules"][target_path].get("label", target_path)
            count_text = f" x{count}" if count > 1 else ""
            lines.append(
                _Text.plain("  OUTER FEEDBACK BUS: ")
                + _Text.styled(f"{source} ▲ {target}{count_text}", "assurance")
            )
        if isolated:
            lines.append(_rule("ISOLATED", width, charset))
            isolated_rows, _ = _layer_box_rows(
                data,
                isolated,
                charset,
                width,
                overlay,
                focus=scope.focus,
            )
            lines.extend(isolated_rows)
        return lines

    layer_top_line: dict[int, int] = {}
    layer_spans: dict[int, dict[str, tuple[int, int]]] = {}
    lane_infos: list[tuple[int, TerminalEdge, str]] = []

    for rank, layer in enumerate(layers):
        lines.append(_Text.styled(f"L{rank}", "heading"))
        layer_top_line[rank] = len(lines)
        box_rows, spans = _layer_box_rows(
            data,
            layer,
            charset,
            width,
            overlay,
            focus=scope.focus,
        )
        lines.extend(box_rows)
        layer_spans[rank] = spans
        for source in layer:
            source_edges = edges_by_source[source]
            if not source_edges:
                continue
            role_groups: dict[str, list[TerminalEdge]] = {}
            for edge in source_edges:
                role_groups.setdefault(_route_role(data, source, edge, ranks), []).append(edge)
            source_label = data["modules"][source].get("label", source)
            for role, role_edges in role_groups.items():
                lines.append(
                    _Text.plain("  ") + _Text.styled(f"{source_label} :: {role}", "heading")
                )
                for edge in role_edges:
                    lane_infos.append((len(lines), edge, _route_class(edge, ranks)))
                    lines.append(
                        _route_lane(
                            data,
                            edge,
                            _route_class(edge, ranks),
                            ranks,
                            charset,
                            width,
                        )
                    )

    if isolated:
        lines.append(_rule("ISOLATED", width, charset))
        isolated_rows, _ = _layer_box_rows(
            data,
            isolated,
            charset,
            width,
            overlay,
            focus=scope.focus,
        )
        lines.extend(isolated_rows)

    _draw_lane_connectors(lines, lane_infos, layer_top_line, layer_spans, ranks, charset)
    return lines


def _cross_engine_child_links(
    data: Mapping,
    chain_layers: Sequence[Sequence[str]],
) -> list[tuple[str, str, str, int]]:
    """Child-level links between different engines' descendants.

    Returns aggregated (source label, target label, family, count) pairs
    for declared downstream/upstream references that leave one engine and
    land inside another.
    """
    modules = data["modules"]
    chain = {engine for layer in chain_layers for engine in layer}

    def engine_of(path: str) -> str | None:
        current = path
        seen = set()
        while current in modules and current not in seen:
            seen.add(current)
            if current in chain:
                return current
            current = modules[current].get("parent")
        return None

    counts: dict[tuple[str, str], tuple[str, int]] = {}
    for layer in chain_layers:
        for engine in layer:
            for child in modules[engine].get("children") or []:
                if child not in modules:
                    continue
                for target in modules[child].get("downstream") or []:
                    owner = engine_of(target)
                    if owner and owner != engine and target in modules:
                        key = (child, target)
                        label, count = counts.get(key, ("", 0))
                        counts[key] = (label, count + 1)
    result = []
    for (source, target), (_, count) in counts.items():
        family = relation_family(data, "dependency")
        source_label = modules[source].get("label", source)
        target_label = modules[target].get("label", target)
        result.append((source_label, target_label, str(family), count))
    return result


def _nested_engine_box(
    data: Mapping,
    path: str,
    charset: str,
    inner_width: int,
    overlay: Mapping | None,
) -> tuple[list[_Text], int]:
    """Engine frame with its child modules nested inside.

    Returns the box lines and its height (4 + child rows), so chain-row
    boxes of different child counts stay column-aligned.
    """
    module = data["modules"][path]
    semantic = resolve_module_semantic(data, path, overlay)
    children = [
        child
        for child in (module.get("children") or [])
        if child in data["modules"]
    ]
    child_edges = {
        (child, target)
        for child in children
        for target in (data["modules"][child].get("downstream") or [])
        if target in children
    }
    dot = "*" if charset == "ascii" else "●"
    title = (
        _Text.styled(dot, semantic.family)
        + _Text.plain(" ")
        + _Text.styled(f"[{semantic.token.upper()}]", semantic.family)
        + _Text.plain(f" {module.get('label', path)}")
    )
    child_box_w = max(8, (inner_width - 4) // max(1, min(len(children), 3)))
    per_row = max(1, inner_width // (child_box_w + 1))
    child_rows = [
        children[index : index + per_row]
        for index in range(0, len(children), per_row)
    ] or [[]]
    height = 4 + 3 * len(child_rows)

    def child_box(child: str) -> list[_Text]:
        """Three rows: top border, label, bottom border."""
        label = truncate_str(data["modules"][child].get("label", child), child_box_w - 2)
        label = label.ljust(child_box_w - 2)
        if charset == "ascii":
            return [
                _Text.plain("+" + "-" * (child_box_w - 2) + "+"),
                _Text.plain("|" + label + "|"),
                _Text.plain("+" + "-" * (child_box_w - 2) + "+"),
            ]
        return [
            _Text.plain("┌" + "─" * (child_box_w - 2) + "┐"),
            _Text.plain("│" + label + "│"),
            _Text.plain("└" + "─" * (child_box_w - 2) + "┘"),
        ]

    # top frame + title row
    if charset == "ascii":
        lines = [
            _Text.plain("+" + "-" * inner_width + "+"),
            _Text.plain("|") + title.pad(inner_width) + _Text.plain("|"),
        ]
    else:
        lines = [
            _Text.plain("┏" + "━" * inner_width + "┓"),
            _Text.plain("┃") + title.pad(inner_width) + _Text.plain("┃"),
        ]
    # child rows, three lines each (top border / label / bottom border)
    for row in child_rows:
        for sub_line in range(3):
            cells: list[_Text] = []
            for index, child in enumerate(row):
                if index:
                    cells.append(
                        _Text.plain("─▶")
                        if sub_line == 1 and (row[index - 1], child) in child_edges
                        else _Text.plain("  ")
                    )
                cells.append(child_box(child)[sub_line])
            content = _Text.plain("")
            for cell in cells:
                content += cell
            if charset == "ascii":
                lines.append(_Text.plain("|") + content.pad(inner_width) + _Text.plain("|"))
            else:
                lines.append(_Text.plain("┃") + content.pad(inner_width) + _Text.plain("┃"))
    if charset == "ascii":
        lines.append(_Text.plain("+" + "-" * inner_width + "+"))
    else:
        lines.append(_Text.plain("┗" + "━" * inner_width + "┛"))
    # Block-row map: child → (row index of its middle line, 0-based on the
    # full box including the top frame and title), used by cross-engine
    # child links to anchor their connectors.
    block_rows: dict[str, int] = {}
    for row_index, row in enumerate(child_rows):
        for child in row:
            # row 0 = frame top, row 1 = title, row 2 = first child's top
            # border → its label line is row 3 + 3*row_index.
            block_rows[child] = 3 + 3 * row_index
    return lines, height, block_rows


def _render_chain_row(
    data: Mapping,
    chain_layers: Sequence[Sequence[str]],
    edges: Sequence[TerminalEdge],
    charset: str,
    width: int,
    overlay: Mapping | None,
    focus: str,
    depth: int = 1,
) -> list[_Text]:
    """Render a chain as one horizontal row of boxes and arrows.

    Each layer holds one or two boxes side by side; the arrows between
    layers carry the relation tag (``─[DEP]▶``, dotted for projected edges)
    so the chain keeps its semantic labels. With ``depth >= 2`` engine
    frames nest their child modules.
    """
    modules = data["modules"]
    total_boxes = sum(len(layer) for layer in chain_layers)
    labels = [modules[p].get("label", p) for layer in chain_layers for p in layer]
    label_w = max(str_width(label) for label in labels)
    edge_by_pair = {(edge.source, edge.target): edge for edge in edges}
    arrow_w = 3  # "─▶" plus one gap cell; custom-kind tags may overflow
    gaps = (len(chain_layers) - 1) * arrow_w + (total_boxes - len(chain_layers))
    semantic_prefix = 9  # "● [FAMILY] " inside each frame
    box_w = min(
        max(label_w + semantic_prefix + 6, 20),
        max(20, (width - 4 - gaps) // total_boxes),
    )

    # With depth >= 2, engine frames nest their children so child-level
    # relations stay visible; the child rows double as anchor rows for
    # cross-engine child links drawn through the gaps.
    engine_boxes: list[list[list[_Text]]] = []
    heights: list[int] = []
    block_rows: dict[tuple[int, int], dict[str, int]] = {}  # (layer, box) → child → row
    for layer_index, layer in enumerate(chain_layers):
        layer_boxes: list[list[_Text]] = []
        for box_index, path in enumerate(layer):
            if depth >= 2 and modules[path].get("children"):
                box, box_height, rows = _nested_engine_box(
                    data, path, charset, max(18, box_w - 2), overlay
                )
                block_rows[(layer_index, box_index)] = rows
                layer_boxes.append(box)
                heights.append(box_height)
            else:
                layer_boxes.append(
                    _module_box(data, path, charset, box_w, box_w, overlay, focus=path == focus)
                )
                heights.append(3)
        engine_boxes.append(layer_boxes)
    height = max(heights) if heights else 3

    # Cross-engine child links anchored to block rows: for every gap,
    # (source box, source row) → (target box, target row).
    cross_links: dict[tuple[int, int], list[tuple[int, int, str]]] = {}
    chain_engines = [path for layer in chain_layers for path in layer]

    def engine_of(path: str) -> str | None:
        current = path
        seen = set()
        while current in modules and current not in seen:
            seen.add(current)
            if current in chain_engines:
                return current
            current = modules[current].get("parent")
        return None

    for layer_index, layer in enumerate(chain_layers):
        for box_index, engine in enumerate(layer):
            rows = block_rows.get((layer_index, box_index), {})
            for child, child_row in rows.items():
                for target in modules[child].get("downstream") or []:
                    owner = engine_of(target)
                    if not owner or owner == engine or target not in modules:
                        continue
                    for other_index, other_layer in enumerate(chain_layers):
                        for other_box, other_engine in enumerate(other_layer):
                            if other_engine == owner and other_index > layer_index:
                                target_rows = block_rows.get((other_index, other_box), {})
                                target_row = target_rows.get(target)
                                if target_row is None:
                                    target_row = 1  # nested deeper — anchor to title row
                                cross_links.setdefault((layer_index, box_index), []).append(
                                    (other_index, other_box, target_row, child_row)
                                )
                                break

    def chain_arrow(source: str, target: str) -> _Text:
        edge = edge_by_pair.get((source, target))
        if edge is None:
            return _Text.styled("─▶" if charset == "unicode" else "->", "edge")
        shaft = "┄" if edge.projected else ("-" if charset == "ascii" else "─")
        arrow = ">" if charset == "ascii" else "▶"
        if edge.kind != edge.family:
            # custom kinds keep their exact token; plain families rely on
            # the legend and the edge color
            return _Text.styled(f"{shaft}[{edge.kind}]{shaft}{arrow}", edge.family)
        return _Text.styled(f"{shaft}{arrow}", edge.family)

    # Box x positions: (layer, box) → left column, so cross-engine child
    # links can anchor their connectors on the actual frame borders.
    box_x: dict[tuple[int, int], int] = {}
    x = 2
    for layer_index, layer in enumerate(chain_layers):
        for box_index in range(len(layer)):
            box_x[(layer_index, box_index)] = x
            x += box_w
        x += 3  # gap between layers

    lines: list[_Text] = []
    for line_index in range(height):
        row = _Text.plain(" " * 2)
        for layer_index, layer in enumerate(chain_layers):
            if layer_index:
                previous = chain_layers[layer_index - 1]
                arrow_edge = next(
                    (
                        edge
                        for edge in edges
                        if edge.source in previous and edge.target in layer
                    ),
                    None,
                )
                gap = (
                    chain_arrow(arrow_edge.source, arrow_edge.target).value
                    if arrow_edge and line_index == 1
                    else " " * 3
                )
                row += _Text.plain(gap)
            for box_index, path in enumerate(layer):
                box = engine_boxes[layer_index][box_index]
                row += box[line_index].pad(box_w) if line_index < len(box) else _Text.plain(" " * box_w)
        lines.append(row)

    # Cross-engine child links, drawn in the short form: a vertical drop
    # inside the frame gap from the source child row to the target child
    # row, then a horizontal arrow into the target frame. No long detours —
    # the vertical is bounded by the two child rows, so the path reads
    # source → down → right into target.
    lane = 0
    for (src_layer, src_box), links in cross_links.items():
        src_right = box_x[(src_layer, src_box)] + box_w - 1
        for target_layer, target_box, target_row, source_row in links:
            if target_layer <= src_layer:
                continue
            tgt_left = box_x[(target_layer, target_box)]
            column = src_right + 1 + (lane % 2)
            lane += 1
            lo, hi = sorted((source_row, target_row))
            # vertical run inside the gap
            for row_index in range(lo + 1, hi):
                if _char_at_column(lines[row_index], column) == " ":
                    lines[row_index] = _overlay_column(lines[row_index], column, "│")
            # source row: leave the frame
            if _char_at_column(lines[source_row], column) in (" ", "┃"):
                lines[source_row] = _overlay_column(lines[source_row], column, "─")
            # target row: elbow then horizontal arrow into the frame
            corner = "└" if target_row >= source_row else "┌"
            if _char_at_column(lines[target_row], column) in (" ", "┃"):
                lines[target_row] = _overlay_column(lines[target_row], column, corner)
            for column_x in range(column + 1, tgt_left):
                if _char_at_column(lines[target_row], column_x) == " ":
                    lines[target_row] = _overlay_column(lines[target_row], column_x, "─")
            if _char_at_column(lines[target_row], tgt_left - 1) in (" ", "┃"):
                lines[target_row] = _overlay_column(lines[target_row], tgt_left - 1, "▶")
    return lines


def _draw_lane_connectors(
    lines: list[_Text],
    lane_infos: list[tuple[int, TerminalEdge, str]],
    layer_top_line: Mapping[int, int],
    layer_spans: Mapping[int, Mapping[str, tuple[int, int]]],
    ranks: Mapping[str, int],
    charset: str,
) -> None:
    """Extend each route lane with a vertical connector onto the target frame.

    The lane itself is a semantic annotation (``├──[DEP]──▼ L1 label``); its
    arrow column used to hang in the void.  A connector line now drops from
    that column to the target layer's frame — the frame top for forward
    edges (┴), the frame bottom for feedback/bidirectional edges (┬) — and
    bridges horizontally along the frame line when the column sits outside
    the frame's span.
    """

    vertical = "|" if charset == "ascii" else "│"
    hchar = "-" if charset == "ascii" else "─"
    tee_top = "+" if charset == "ascii" else "┴"  # joins a frame top line
    tee_bottom = "+" if charset == "ascii" else "┬"  # joins a frame bottom line
    # ``    ├──[TAG]──marker──arrow`` — the arrow column is fixed by layout.
    arrow_col = 4 + 3 + 5 + 4

    def drop(from_idx: int, to_idx: int) -> None:
        step = 1 if to_idx > from_idx else -1
        for i in range(from_idx, to_idx, step):
            if _char_at_column(lines[i], arrow_col) == " ":
                lines[i] = _overlay_column(lines[i], arrow_col, vertical)

    def terminate(line_idx: int, span: tuple[int, int], tee: str) -> None:
        x0, x1 = span
        if x0 < arrow_col < x1:
            lines[line_idx] = _overlay_column(lines[line_idx], arrow_col, tee)
            return
        if arrow_col <= x0:
            for c in range(arrow_col + 1, x0 + 1):
                if _char_at_column(lines[line_idx], c) == " ":
                    lines[line_idx] = _overlay_column(lines[line_idx], c, hchar)
            lines[line_idx] = _overlay_column(lines[line_idx], x0 + 1, tee)
        else:
            for c in range(x1 - 1, arrow_col):
                if _char_at_column(lines[line_idx], c) == " ":
                    lines[line_idx] = _overlay_column(lines[line_idx], c, hchar)
            lines[line_idx] = _overlay_column(lines[line_idx], x1 - 1, tee)

    for lane_idx, edge, route_class in lane_infos:
        source_rank = ranks.get(edge.source)
        target_rank = ranks.get(edge.target)
        if source_rank is None or target_rank is None:
            continue
        span = layer_spans.get(target_rank, {}).get(edge.target)
        if span is None:
            continue

        if route_class == "forward":
            # ▼ — drop onto the target frame's top line (adjacent layers only).
            if target_rank - source_rank != 1:
                continue
            top_idx = layer_top_line[target_rank]
            drop(lane_idx + 1, top_idx)
            terminate(top_idx, span, tee_top)
        elif route_class in {"feedback", "bidirectional"} and target_rank == source_rank:
            # ▲ / ↕ — same layer: the target frame's bottom line sits above
            # the lane, so the connector rises onto it.
            bottom_idx = layer_top_line[target_rank] + 2
            drop(lane_idx - 1, bottom_idx)
            terminate(bottom_idx, span, tee_bottom)
        # lateral (▶) and cross-layer feedback keep the bare annotation.


def render_terminal(
    data: Mapping,
    module_path: str,
    *,
    strategy: str = "overview",
    depth: int = 1,
    color: str = "auto",
    charset: str = "auto",
    width: int | None = None,
    semantic_overlay: Mapping | None = None,
    theme: str = "default",
    stream: TextIO | None = None,
    isatty: bool | None = None,
    env: Mapping[str, str] | None = None,
) -> str:
    """Render the deterministic, semantic overview as terminal text."""

    if strategy != "overview":
        raise TerminalRenderError(f"Terminal renderer does not implement strategy '{strategy}'")
    if depth < 0:
        raise TerminalRenderError("Depth must be zero or greater")
    if width is not None and width <= 0:
        raise TerminalRenderError("Width must be greater than zero")
    modules = data.get("modules") or {}
    aliases = data.get("aliases") or {}
    actual = aliases.get(module_path, module_path) if isinstance(aliases, Mapping) else module_path
    if module_path in {"all", "全景"} and actual not in modules:
        actual = next(
            (path for path, module in modules.items() if module.get("type") == "root"),
            actual,
        )
    if actual not in modules:
        available = ", ".join(list(modules)[:10])
        raise TerminalRenderError(f"Module '{module_path}' not found. Available: {available}")

    if semantic_overlay is not None:
        overlay_errors = validate_semantic_overlay(data, semantic_overlay)
        if overlay_errors:
            raise TerminalRenderError(
                "invalid semantic overlay:\n  - " + "\n  - ".join(overlay_errors)
            )

    detected_width = shutil.get_terminal_size(fallback=(120, 24)).columns
    resolved_width = max(40, int(detected_width if width is None else width))
    resolved_charset = resolve_charset(charset, stream)
    use_color = color_enabled(color, stream=stream, isatty=isatty, env=env)
    scope = _view_scope(data, str(actual), depth)
    topology_edges = derive_terminal_edges(
        data,
        str(actual),
        scope.top_level,
        overlay=semantic_overlay,
        leaf=scope.leaf,
    )

    title = str(modules[actual].get("label", actual))
    separator = " | " if resolved_charset == "ascii" else " · "
    header = _Text.styled("ARCHISCOPE", "heading") + _Text.plain(
        f"  {title}  overview{separator}depth={depth}{separator}width={resolved_width}"
    )
    lines: list[_Text] = [header.truncate(resolved_width)]
    top_frame, bottom_frame = _focus_frame(
        data, str(actual), resolved_charset, resolved_width, semantic_overlay
    )
    lines.append(top_frame)
    lines.extend(
        _render_vertical_layered_topology(
            data,
            scope,
            topology_edges,
            resolved_charset,
            resolved_width,
            semantic_overlay,
            depth,
        )
    )
    lines.append(bottom_frame)
    lines.append(_rule("OWNERSHIP TREE", resolved_width, resolved_charset))
    lines.extend(
        _ownership_lines(
            data,
            scope,
            resolved_charset,
            resolved_width,
            semantic_overlay,
        )
    )
    lines.append(_rule("LEGEND", resolved_width, resolved_charset))
    lines.extend(_legend(resolved_charset, resolved_width))

    plain = "\n".join(line.value for line in lines)
    if any(str_width(line) > resolved_width for line in plain.splitlines()):
        raise TerminalRenderError("Terminal layout exceeded the requested width")
    theme_colors = resolve_theme(theme).colors
    rendered = "\n".join(line.render(use_color, theme_colors) for line in lines)
    if use_color and strip_ansi(rendered) != plain:
        raise TerminalRenderError("ANSI styling changed terminal geometry")
    return rendered


__all__ = [
    "FEATURE_FAMILIES",
    "RELATION_FAMILIES",
    "ModuleSemantic",
    "TerminalEdge",
    "TerminalRenderError",
    "color_enabled",
    "derive_terminal_edges",
    "render_terminal",
    "resolve_charset",
    "resolve_module_semantic",
    "strip_ansi",
]
