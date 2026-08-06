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
    strip_ansi,
)
from .geometry.draw.grid import char_width, str_width


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

    def render(self, use_color: bool) -> str:
        if not use_color:
            return self.value
        rendered: list[str] = []
        for span in self.spans:
            code = ANSI_COLORS.get(span.style or "")
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
) -> list[_Text]:
    """Pack one logical layer into stable, width-dependent physical rows."""

    if not paths:
        return []
    gap = 3
    minimum_box_width = 24
    per_row = max(1, (width + gap) // (minimum_box_width + gap))
    lines: list[_Text] = []
    for start in range(0, len(paths), per_row):
        chunk = paths[start : start + per_row]
        # A logical layer is 1..N nodes, never a fixed one- or two-column
        # template.  Use the whole available physical row so a lone CJK label
        # is not needlessly clipped; only the width-derived packing count may
        # change when the terminal is resized.
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
        for line_index in range(3):
            row = _Text.plain(" " * left_padding)
            for box_index, box in enumerate(rendered):
                if box_index:
                    row += _Text.plain(" " * gap)
                row += box[line_index].pad(box_width)
            lines.append(row.truncate(width))
    return lines


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
    for rank, layer in enumerate(layers):
        lines.append(_Text.styled(f"L{rank}", "heading"))
        lines.extend(
            _layer_box_rows(
                data,
                layer,
                charset,
                width,
                overlay,
                focus=scope.focus,
            )
        )
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
                lines.extend(
                    _route_lane(
                        data,
                        edge,
                        _route_class(edge, ranks),
                        ranks,
                        charset,
                        width,
                    )
                    for edge in role_edges
                )

    if isolated:
        lines.append(_rule("ISOLATED", width, charset))
        lines.extend(
            _layer_box_rows(
                data,
                isolated,
                charset,
                width,
                overlay,
                focus=scope.focus,
            )
        )
    return lines


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
    rendered = "\n".join(line.render(use_color) for line in lines)
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
