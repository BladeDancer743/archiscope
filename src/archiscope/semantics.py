"""Deterministic semantic decisions for architecture blueprints.

The renderer consumes only confirmed blueprint facts plus an optional, validated
preview overlay.  This module deliberately contains no name/path heuristics.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

import yaml

RELATION_FAMILIES = (
    "dependency",
    "data",
    "command",
    "authority",
    "event",
    "reference",
)
FEATURE_FAMILIES = (
    "orchestration",
    "compute",
    "data",
    "state",
    "authority",
    "boundary",
    "delivery",
    "assurance",
    "neutral",
)
CONFIDENCE_LEVELS = ("high", "medium", "low")

_OVERLAY_MODULE_FIELDS = frozenset({"feature", "evidence", "reason", "confidence"})
_OVERLAY_EDGE_FIELDS = frozenset(
    {"from", "to", "kind", "payload_type", "label", "evidence", "reason", "confidence"}
)


class SemanticError(ValueError):
    """Semantic configuration or preview overlay is invalid."""


def _semantic_section(data: Mapping[str, Any]) -> Mapping[str, Any]:
    section = data.get("semantics")
    return section if isinstance(section, Mapping) else {}


def _registry(data: Mapping[str, Any], name: str) -> Mapping[str, Any]:
    registry = _semantic_section(data).get(name)
    return registry if isinstance(registry, Mapping) else {}


def _family_from_registration(value: Any) -> Any:
    if isinstance(value, str):
        return value
    if isinstance(value, Mapping):
        return value.get("family")
    return None


def feature_family(data: Mapping[str, Any], token: str) -> str | None:
    """Map a confirmed feature token to its built-in visual family."""
    if token in FEATURE_FAMILIES:
        return token
    family = _family_from_registration(_registry(data, "features").get(token))
    return family if family in FEATURE_FAMILIES else None


def relation_family(data: Mapping[str, Any], token: str) -> str | None:
    """Map a confirmed relation token to its built-in visual family."""
    if token in RELATION_FAMILIES:
        return token
    family = _family_from_registration(_registry(data, "relation_kinds").get(token))
    return family if family in RELATION_FAMILIES else None


def semantic_schema_errors(data: Mapping[str, Any]) -> list[str]:
    """Validate semantic declarations embedded in an archmap."""
    errors: list[str] = []
    semantics = data.get("semantics")
    if semantics is not None and not isinstance(semantics, Mapping):
        return ["semantics must be a mapping"]

    if isinstance(semantics, Mapping):
        unknown = set(semantics) - {"features", "relation_kinds"}
        for key in sorted(unknown, key=str):
            errors.append(f"semantics: unknown field '{key}'")
        _validate_registry(
            semantics.get("features"),
            "semantics.features",
            FEATURE_FAMILIES,
            errors,
            require_extension_prefix=False,
        )
        _validate_registry(
            semantics.get("relation_kinds"),
            "semantics.relation_kinds",
            RELATION_FAMILIES,
            errors,
            require_extension_prefix=True,
        )

    modules = data.get("modules")
    if not isinstance(modules, Mapping):
        return errors

    seen_semantic_edges: set[tuple[str, str, str]] = set()
    for module_path, module in modules.items():
        if not isinstance(module, Mapping):
            continue
        if "feature" in module:
            feature = module.get("feature")
            if not isinstance(feature, str) or not feature:
                errors.append(f"{module_path}: feature must be a non-empty string")
            elif feature_family(data, feature) is None:
                errors.append(f"{module_path}: unknown feature token '{feature}'")

        edges = module.get("edges")
        if not isinstance(edges, list):
            continue
        for index, edge in enumerate(edges):
            if not isinstance(edge, Mapping):
                continue
            prefix = f"{module_path}: edges[{index}]"
            kind = edge.get("kind")
            if "kind" in edge:
                if not isinstance(kind, str) or not kind:
                    errors.append(f"{prefix}.kind must be a non-empty string")
                elif relation_family(data, kind) is None:
                    errors.append(f"{prefix}: unknown relation kind '{kind}'")
                else:
                    source, target = edge.get("from"), edge.get("to")
                    if isinstance(source, str) and isinstance(target, str):
                        identity = (source, target, kind)
                        if identity in seen_semantic_edges:
                            errors.append(
                                f"{prefix}: duplicate semantic edge "
                                f"'{source}' -> '{target}' kind '{kind}'"
                            )
                        seen_semantic_edges.add(identity)
            for field in ("payload_type", "label"):
                if field in edge and not isinstance(edge.get(field), str):
                    errors.append(f"{prefix}.{field} must be a string")
    return errors


def _validate_registry(
    registry: Any,
    path: str,
    families: tuple[str, ...],
    errors: list[str],
    *,
    require_extension_prefix: bool,
) -> None:
    if registry is None:
        return
    if not isinstance(registry, Mapping):
        errors.append(f"{path} must be a mapping")
        return
    for token, registration in registry.items():
        if not isinstance(token, str) or not token:
            errors.append(f"{path} tokens must be non-empty strings")
            continue
        if token in families:
            errors.append(f"{path}: built-in token '{token}' cannot be redefined")
        elif require_extension_prefix and (not token.startswith("x-") or len(token) == 2):
            errors.append(f"{path}: custom relation kind '{token}' must start with 'x-'")
        if isinstance(registration, Mapping):
            for field in sorted(set(registration) - {"family"}, key=str):
                errors.append(
                    f"{path}.{token}: unknown field '{field}'; visual styling is renderer-owned"
                )
        family = _family_from_registration(registration)
        if family not in families:
            errors.append(
                f"{path}.{token}: unknown family '{family}', must be one of {', '.join(families)}"
            )


def _iter_declared_edges(data: Mapping[str, Any]) -> Iterator[dict[str, Any]]:
    modules = data.get("modules")
    if not isinstance(modules, Mapping):
        return
    for owner, module in modules.items():
        if not isinstance(module, Mapping):
            continue
        edges = module.get("edges")
        if not isinstance(edges, list):
            continue
        for index, edge in enumerate(edges):
            if isinstance(edge, Mapping):
                record = dict(edge)
                record["_owner"] = owner
                record["_index"] = index
                yield record


def canonical_relation_pairs(data: Mapping[str, Any]) -> list[tuple[str, str]]:
    """Return canonical directed topology pairs in stable declaration order."""
    modules = data.get("modules")
    if not isinstance(modules, Mapping):
        return []
    pairs: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(source: Any, target: Any) -> None:
        pair = (source, target)
        if (
            isinstance(source, str)
            and isinstance(target, str)
            and source in modules
            and target in modules
            and pair not in seen
        ):
            seen.add(pair)
            pairs.append(pair)

    for module_path, module in modules.items():
        if not isinstance(module, Mapping):
            continue
        downstream = module.get("downstream")
        if isinstance(downstream, list):
            for target in downstream:
                add(module_path, target)
        upstream = module.get("upstream")
        if isinstance(upstream, list):
            for source in upstream:
                add(source, module_path)
    for edge in _iter_declared_edges(data):
        add(edge.get("from"), edge.get("to"))
    return pairs


def _overlay_modules(overlay: Mapping[str, Any] | None) -> Mapping[str, Any]:
    if not isinstance(overlay, Mapping):
        return {}
    modules = overlay.get("modules")
    return modules if isinstance(modules, Mapping) else {}


def _overlay_feature(proposal: Any) -> Any:
    if isinstance(proposal, str):
        return proposal
    if isinstance(proposal, Mapping):
        return proposal.get("feature")
    return None


def _overlay_edges(overlay: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(overlay, Mapping):
        return []
    edges = overlay.get("edges")
    if not isinstance(edges, list):
        return []
    return [edge for edge in edges if isinstance(edge, Mapping)]


def validate_semantic_overlay(data: Mapping[str, Any], overlay: Any) -> list[str]:
    """Reject overlay topology changes and conflicts with confirmed semantics."""
    if not isinstance(overlay, Mapping):
        return ["semantic overlay root must be a mapping"]
    errors: list[str] = []
    unknown_top = set(overlay) - {"schema", "modules", "edges"}
    for key in sorted(unknown_top, key=str):
        errors.append(f"semantic overlay: unknown field '{key}'")
    schema = overlay.get("schema")
    if schema is not None and schema != "archiscope/semantic-overlay/1.0":
        errors.append("semantic overlay schema must be 'archiscope/semantic-overlay/1.0'")

    modules = data.get("modules")
    modules = modules if isinstance(modules, Mapping) else {}
    overlay_modules = overlay.get("modules", {})
    if not isinstance(overlay_modules, Mapping):
        errors.append("semantic overlay modules must be a mapping")
    else:
        for module_path, proposal in overlay_modules.items():
            prefix = f"semantic overlay modules.{module_path}"
            if module_path not in modules:
                errors.append(f"{prefix}: module does not exist")
                continue
            confirmed_module = modules[module_path]
            if not isinstance(confirmed_module, Mapping):
                errors.append(f"{prefix}: confirmed module must be a mapping")
                continue
            if not isinstance(proposal, (str, Mapping)):
                errors.append(f"{prefix} must be a feature string or proposal mapping")
                continue
            if isinstance(proposal, Mapping):
                _validate_overlay_fields(proposal, _OVERLAY_MODULE_FIELDS, prefix, errors)
            feature = _overlay_feature(proposal)
            if not isinstance(feature, str) or not feature:
                errors.append(f"{prefix}.feature must be a non-empty string")
            elif feature_family(data, feature) is None:
                errors.append(f"{prefix}: unknown feature token '{feature}'")
            else:
                confirmed = confirmed_module.get("feature")
                if confirmed is not None and confirmed != feature:
                    errors.append(
                        f"{prefix}: feature '{feature}' conflicts with confirmed "
                        f"feature '{confirmed}'"
                    )
            if isinstance(proposal, Mapping):
                _validate_proposal_metadata(proposal, prefix, errors)

    canonical_pairs = set(canonical_relation_pairs(data))
    declared_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in _iter_declared_edges(data):
        source, target = edge.get("from"), edge.get("to")
        if isinstance(source, str) and isinstance(target, str):
            declared_by_pair.setdefault((source, target), []).append(edge)

    overlay_edges = overlay.get("edges", [])
    seen: set[tuple[str, str, str]] = set()
    if not isinstance(overlay_edges, list):
        errors.append("semantic overlay edges must be a list")
    else:
        for index, proposal in enumerate(overlay_edges):
            prefix = f"semantic overlay edges[{index}]"
            if not isinstance(proposal, Mapping):
                errors.append(f"{prefix} must be a mapping")
                continue
            _validate_overlay_fields(proposal, _OVERLAY_EDGE_FIELDS, prefix, errors)
            source, target, kind = (
                proposal.get("from"),
                proposal.get("to"),
                proposal.get("kind"),
            )
            if not isinstance(source, str) or not source:
                errors.append(f"{prefix}.from must be a non-empty string")
            if not isinstance(target, str) or not target:
                errors.append(f"{prefix}.to must be a non-empty string")
            if isinstance(source, str) and isinstance(target, str):
                if (source, target) not in canonical_pairs:
                    errors.append(
                        f"{prefix}: '{source}' -> '{target}' is not an existing canonical relation"
                    )
            if not isinstance(kind, str) or not kind:
                errors.append(f"{prefix}.kind must be a non-empty string")
            elif relation_family(data, kind) is None:
                errors.append(f"{prefix}: unknown relation kind '{kind}'")
            elif isinstance(source, str) and isinstance(target, str):
                identity = (source, target, kind)
                if identity in seen:
                    errors.append(
                        f"{prefix}: duplicate semantic edge '{source}' -> '{target}' kind '{kind}'"
                    )
                seen.add(identity)
                confirmed_edges = declared_by_pair.get((source, target), [])
                confirmed_kinds = {
                    kind_value
                    for edge in confirmed_edges
                    if isinstance((kind_value := edge.get("kind")), str) and kind_value
                }
                if confirmed_kinds and kind not in confirmed_kinds:
                    errors.append(
                        f"{prefix}: kind '{kind}' conflicts with confirmed "
                        f"kind(s) {sorted(confirmed_kinds)}"
                    )
                for confirmed_edge in confirmed_edges:
                    if confirmed_edge.get("kind") not in (None, kind):
                        continue
                    for field in ("payload_type", "label"):
                        confirmed = confirmed_edge.get(field)
                        candidate = proposal.get(field)
                        if (
                            confirmed is not None
                            and candidate is not None
                            and confirmed != candidate
                        ):
                            errors.append(
                                f"{prefix}.{field} '{candidate}' conflicts with confirmed "
                                f"value '{confirmed}'"
                            )
            for field in ("payload_type", "label"):
                if field in proposal and not isinstance(proposal.get(field), str):
                    errors.append(f"{prefix}.{field} must be a string")
            _validate_proposal_metadata(proposal, prefix, errors)
    return errors


def _validate_overlay_fields(
    proposal: Mapping[str, Any], allowed: frozenset[str], prefix: str, errors: list[str]
) -> None:
    for field in sorted(set(proposal) - allowed, key=str):
        errors.append(f"{prefix}: field '{field}' cannot be changed by a semantic overlay")


def _validate_proposal_metadata(
    proposal: Mapping[str, Any], prefix: str, errors: list[str]
) -> None:
    confidence = proposal.get("confidence")
    if confidence is not None and confidence not in CONFIDENCE_LEVELS:
        errors.append(
            f"{prefix}.confidence must be one of {', '.join(CONFIDENCE_LEVELS)}, got '{confidence}'"
        )
    for field in ("evidence", "reason"):
        value = proposal.get(field)
        if value is not None and not isinstance(value, (str, list)):
            errors.append(f"{prefix}.{field} must be a string or list")
        elif isinstance(value, list) and any(not isinstance(item, str) for item in value):
            errors.append(f"{prefix}.{field} list entries must be strings")


def load_semantic_overlay(path: Path | str, data: Mapping[str, Any]) -> dict[str, Any]:
    """Load and validate an overlay, raising one actionable CLI error."""
    overlay_path = Path(path)
    try:
        with open(overlay_path, "r", encoding="utf-8") as stream:
            overlay = yaml.safe_load(stream)
    except yaml.YAMLError as exc:
        raise SemanticError(f"semantic overlay YAML parse error: {exc}") from exc
    errors = validate_semantic_overlay(data, overlay)
    if errors:
        raise SemanticError("invalid semantic overlay:\n  - " + "\n  - ".join(errors))
    return dict(overlay)


def resolve_module_feature(
    data: Mapping[str, Any], module_path: str, overlay: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """Resolve feature using explicit > overlay > nearest ancestor > neutral."""
    modules = data.get("modules")
    if not isinstance(modules, Mapping) or module_path not in modules:
        raise SemanticError(f"module '{module_path}' does not exist")
    module = modules[module_path]
    if not isinstance(module, Mapping):
        raise SemanticError(f"module '{module_path}' must be a mapping")

    explicit = module.get("feature")
    if isinstance(explicit, str):
        return _feature_decision(data, explicit, "explicit")

    proposal = _overlay_modules(overlay).get(module_path)
    proposed_feature = _overlay_feature(proposal)
    if isinstance(proposed_feature, str):
        return _feature_decision(data, proposed_feature, "overlay")

    seen = {module_path}
    parent = module.get("parent")
    while isinstance(parent, str) and parent in modules and parent not in seen:
        seen.add(parent)
        ancestor = modules[parent]
        if not isinstance(ancestor, Mapping):
            break
        feature = ancestor.get("feature")
        if isinstance(feature, str):
            decision = _feature_decision(data, feature, "inherited")
            decision["inherited_from"] = parent
            return decision
        ancestor_proposal = _overlay_modules(overlay).get(parent)
        ancestor_feature = _overlay_feature(ancestor_proposal)
        if isinstance(ancestor_feature, str):
            decision = _feature_decision(data, ancestor_feature, "inherited")
            decision["inherited_from"] = parent
            decision["inherited_via"] = "overlay"
            return decision
        parent = ancestor.get("parent")
    return {"token": "neutral", "family": "neutral", "source": "fallback"}


def _feature_decision(data: Mapping[str, Any], token: str, source: str) -> dict[str, Any]:
    family = feature_family(data, token)
    if family is None:
        raise SemanticError(f"unknown feature token '{token}'")
    return {"token": token, "family": family, "source": source}


def resolve_edge_semantics(
    data: Mapping[str, Any],
    source: str,
    target: str,
    edge: Mapping[str, Any] | None = None,
    overlay: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve relation using explicit edge > overlay > dependency."""
    explicit = edge if isinstance(edge, Mapping) else None
    if explicit is None or not explicit.get("kind"):
        confirmed = next(
            (
                candidate
                for candidate in _iter_declared_edges(data)
                if candidate.get("from") == source
                and candidate.get("to") == target
                and candidate.get("kind")
            ),
            None,
        )
        if confirmed is not None:
            explicit = confirmed
        elif explicit is None:
            explicit = next(
                (
                    candidate
                    for candidate in _iter_declared_edges(data)
                    if candidate.get("from") == source and candidate.get("to") == target
                ),
                None,
            )
    kind = explicit.get("kind") if explicit else None
    proposal = None
    if not kind:
        proposal = next(
            (
                candidate
                for candidate in _overlay_edges(overlay)
                if candidate.get("from") == source and candidate.get("to") == target
            ),
            None,
        )
        kind = proposal.get("kind") if proposal else None

    provenance = (
        "explicit" if explicit and explicit.get("kind") else "overlay" if proposal else "default"
    )
    kind = kind or "dependency"
    family = relation_family(data, kind)
    if family is None:
        raise SemanticError(f"unknown relation kind '{kind}'")

    label = ""
    payload_type = ""
    for candidate in (explicit, proposal):
        if not candidate:
            continue
        if candidate.get("label") is not None:
            label = candidate["label"]
        if candidate.get("payload_type") is not None:
            payload_type = candidate["payload_type"]
    return {
        "kind": kind,
        "family": family,
        "label": label,
        "payload_type": payload_type,
        "source": provenance,
    }


def iter_canonical_relations(
    data: Mapping[str, Any], overlay: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    """Resolve one record per semantic line without inventing topology."""
    declared_by_pair: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for edge in _iter_declared_edges(data):
        source, target = edge.get("from"), edge.get("to")
        if isinstance(source, str) and isinstance(target, str):
            declared_by_pair.setdefault((source, target), []).append(edge)
    overlay_by_pair: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for proposal in _overlay_edges(overlay):
        source, target = proposal.get("from"), proposal.get("to")
        if isinstance(source, str) and isinstance(target, str):
            overlay_by_pair.setdefault((source, target), []).append(proposal)

    resolved: list[dict[str, Any]] = []
    for source, target in canonical_relation_pairs(data):
        declared = declared_by_pair.get((source, target), [])
        semantic_edges = [edge for edge in declared if edge.get("kind")]
        candidates: list[tuple[Mapping[str, Any] | None, bool]]
        if semantic_edges:
            candidates = [(edge, False) for edge in semantic_edges]
        elif overlay_by_pair.get((source, target)):
            candidates = [(proposal, True) for proposal in overlay_by_pair[(source, target)]]
        else:
            candidates = [(declared[0] if declared else None, False)]
        for candidate, from_overlay in candidates:
            if from_overlay:
                decision = resolve_edge_semantics(
                    data, source, target, edge=None, overlay={"edges": [candidate]}
                )
            else:
                decision = resolve_edge_semantics(
                    data, source, target, edge=candidate, overlay=None
                )
            resolved.append({"from": source, "to": target, **decision})
    return resolved


def audit_semantics(data: Mapping[str, Any]) -> dict[str, Any]:
    """Report semantics that still rely on neutral/dependency fallbacks."""
    schema_errors = semantic_schema_errors(data)
    if schema_errors:
        raise SemanticError("invalid archmap semantics:\n  - " + "\n  - ".join(schema_errors))
    modules = data.get("modules")
    modules = modules if isinstance(modules, Mapping) else {}
    module_items: list[dict[str, Any]] = []
    inherited = 0
    for module_path, module in modules.items():
        decision = resolve_module_feature(data, module_path)
        if decision["source"] == "inherited":
            inherited += 1
        if decision["source"] == "fallback":
            module_items.append(
                {
                    "path": module_path,
                    "label": module.get("label", "") if isinstance(module, Mapping) else "",
                    "type": module.get("type", "") if isinstance(module, Mapping) else "",
                }
            )

    pairs = canonical_relation_pairs(data)
    classified_pairs = {
        (edge.get("from"), edge.get("to"))
        for edge in _iter_declared_edges(data)
        if edge.get("kind")
    }
    relation_items = [
        {"from": source, "to": target, "default": "dependency"}
        for source, target in pairs
        if (source, target) not in classified_pairs
    ]
    semantic_lines = len(iter_canonical_relations(data))
    return {
        "modules": {
            "total": len(modules),
            "classified": len(modules) - len(module_items),
            "inherited": inherited,
            "unclassified": module_items,
        },
        "relations": {
            "total": len(pairs),
            "semantic_lines": semantic_lines,
            "classified": len(pairs) - len(relation_items),
            "unclassified": relation_items,
        },
    }
