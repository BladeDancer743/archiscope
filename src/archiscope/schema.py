"""YAML schema validation for .archmap.yaml."""

from pathlib import Path
from typing import Optional

import yaml

from .semantics import semantic_schema_errors
from .strategies import ALL_STRATEGY_NAMES

VALID_TYPES = {"root", "engine", "layer", "module", "function", "rule"}


def validate(path: Optional[Path] = None) -> tuple[bool, list[str]]:
    yaml_path = _resolve_path(path)
    if not yaml_path:
        return False, [".archmap.yaml not found"]

    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        return False, [f"YAML parse error: {e}"]

    if not isinstance(data, dict):
        return False, ["Root must be a mapping"]

    if data.get("schema", "").split("/")[0] != "archiscope":
        return False, [
            f"schema must start with 'archiscope/', got: {data.get('schema', 'missing')}"
        ]

    modules = data.get("modules", {})
    if not isinstance(modules, dict):
        return False, ["modules must be a mapping"]
    if not modules:
        return False, ["modules section is empty"]

    errors = []

    aliases = data.get("aliases", {})
    if aliases is None:
        aliases = {}
    if not isinstance(aliases, dict):
        errors.append("aliases must be a mapping")
    else:
        for alias, target in aliases.items():
            if not isinstance(alias, str) or not isinstance(target, str):
                errors.append("aliases keys and values must be strings")
            elif target not in modules:
                errors.append(f"alias '{alias}' targets undefined module '{target}'")

    for module_path, module in modules.items():
        if not isinstance(module, dict):
            errors.append(f"{module_path}: must be a mapping")
            continue

        if "label" not in module:
            errors.append(f"{module_path}: missing 'label'")
        if "type" not in module:
            errors.append(f"{module_path}: missing 'type'")
        elif module["type"] not in VALID_TYPES:
            errors.append(
                f"{module_path}: invalid type '{module['type']}', must be one of {VALID_TYPES}"
            )

        if module.get("type") != "root" and "parent" not in module:
            errors.append(f"{module_path}: non-root modules must have 'parent'")

        parent = module.get("parent")
        if parent and parent not in modules:
            errors.append(f"{module_path}: parent '{parent}' not defined")

        for ref_field in ["children", "upstream", "downstream"]:
            refs = module.get(ref_field, [])
            if not isinstance(refs, list):
                errors.append(f"{module_path}: '{ref_field}' must be a list")
                continue
            if ref_field == "children" and len(refs) != len(set(refs)):
                errors.append(f"{module_path}: 'children' must not contain duplicates")
            for ref in refs:
                if ref not in modules:
                    errors.append(f"{module_path}: {ref_field} '{ref}' not defined in modules")

        internal_flow = module.get("internal_flow")
        if internal_flow and not isinstance(internal_flow, list):
            errors.append(f"{module_path}: 'internal_flow' must be a list")
        elif isinstance(internal_flow, list):
            for i, step in enumerate(internal_flow):
                if not isinstance(step, dict):
                    errors.append(f"{module_path}: internal_flow[{i}] must be a mapping")
                elif "step" not in step:
                    errors.append(f"{module_path}: internal_flow[{i}] missing 'step'")

        files = module.get("files")
        if files and not isinstance(files, list):
            errors.append(f"{module_path}: 'files' must be a list")

        # Validate groups
        groups = module.get("groups")
        if groups:
            if not isinstance(groups, dict):
                errors.append(f"{module_path}: 'groups' must be a mapping")
            else:
                grouped_members = set()
                for gname, gcfg in groups.items():
                    if not isinstance(gcfg, dict):
                        errors.append(f"{module_path}: groups.{gname} must be a mapping")
                        continue
                    if "label" not in gcfg:
                        errors.append(f"{module_path}: groups.{gname} missing 'label'")
                    gmods = gcfg.get("modules", [])
                    if not isinstance(gmods, list):
                        errors.append(f"{module_path}: groups.{gname}.modules must be a list")
                        continue
                    for member in gmods:
                        if member not in modules:
                            errors.append(
                                f"{module_path}: groups.{gname} member '{member}' not in modules"
                            )
                        elif member not in (module.get("children") or []):
                            errors.append(
                                f"{module_path}: groups.{gname} member '{member}' "
                                "must be a direct child"
                            )
                        if member in grouped_members:
                            errors.append(
                                f"{module_path}: group member '{member}' appears more than once"
                            )
                        grouped_members.add(member)

        # Validate lanes
        lanes = module.get("lanes")
        if lanes:
            if not isinstance(lanes, list):
                errors.append(f"{module_path}: 'lanes' must be a list")
            else:
                lane_ids = set()
                lane_members = set()
                for i, lane in enumerate(lanes):
                    if not isinstance(lane, dict):
                        errors.append(f"{module_path}: lanes[{i}] must be a mapping")
                        continue
                    if "id" not in lane and "label" not in lane:
                        errors.append(f"{module_path}: lanes[{i}] missing 'id' or 'label'")
                    lane_id = lane.get("id") or lane.get("label")
                    if lane_id in lane_ids:
                        errors.append(f"{module_path}: duplicate lane id '{lane_id}'")
                    lane_ids.add(lane_id)
                    lane_modules = lane.get("modules", [])
                    if not isinstance(lane_modules, list):
                        errors.append(f"{module_path}: lanes[{i}].modules must be a list")
                        continue
                    for member in lane_modules:
                        if member not in modules:
                            errors.append(
                                f"{module_path}: lanes[{i}] member '{member}' not in modules"
                            )
                        elif member not in (module.get("children") or []):
                            errors.append(
                                f"{module_path}: lanes[{i}] member '{member}' "
                                "must be a direct child"
                            )
                        if member in lane_members:
                            errors.append(
                                f"{module_path}: lane member '{member}' appears more than once"
                            )
                        lane_members.add(member)

        # Validate edges
        edges = module.get("edges")
        if edges:
            if not isinstance(edges, list):
                errors.append(f"{module_path}: 'edges' must be a list")
            else:
                for i, edge in enumerate(edges):
                    if not isinstance(edge, dict):
                        errors.append(f"{module_path}: edges[{i}] must be a mapping")
                        continue
                    if "from" not in edge:
                        errors.append(f"{module_path}: edges[{i}] missing 'from'")
                    if "to" not in edge:
                        errors.append(f"{module_path}: edges[{i}] missing 'to'")
                    fr, to = edge.get("from", ""), edge.get("to", "")
                    if fr and fr not in modules:
                        errors.append(f"{module_path}: edges[{i}].from '{fr}' not in modules")
                    if to and to not in modules:
                        errors.append(f"{module_path}: edges[{i}].to '{to}' not in modules")

        # Validate render_strategy
        strategy = module.get("render_strategy")
        if strategy and strategy not in ALL_STRATEGY_NAMES:
            errors.append(f"{module_path}: unknown render_strategy '{strategy}'")

        # Validate layout
        layout = module.get("layout")
        if layout and layout not in ("TB", "LR", "RL", "BT"):
            errors.append(f"{module_path}: layout must be TB/LR/RL/BT, got '{layout}'")

    errors.extend(semantic_schema_errors(data))

    roots = [
        path
        for path, module in modules.items()
        if isinstance(module, dict) and module.get("type") == "root"
    ]
    if not roots:
        errors.append("No module with type 'root' defined")
    elif len(roots) > 1:
        errors.append(f"Exactly one root module is required, found: {', '.join(roots)}")

    for module_path, module in modules.items():
        if not isinstance(module, dict):
            continue
        parent = module.get("parent")
        if parent in modules and isinstance(modules[parent], dict):
            if module_path not in (modules[parent].get("children") or []):
                errors.append(f"{module_path}: parent '{parent}' does not list it as a child")
        children = module.get("children")
        if not isinstance(children, list):
            continue
        for child_path in children:
            child = modules.get(child_path)
            if isinstance(child, dict) and child.get("parent") != module_path:
                errors.append(
                    f"{module_path}: child '{child_path}' declares parent '{child.get('parent')}'"
                )

    if len(roots) == 1:
        root = roots[0]
        reachable = set()
        active: list[str] = []
        complete = set()

        def visit(module_path: str) -> None:
            if module_path in active:
                cycle = " -> ".join(active[active.index(module_path) :] + [module_path])
                errors.append(f"ownership cycle detected: {cycle}")
                return
            if module_path in complete:
                return
            active.append(module_path)
            reachable.add(module_path)
            module = modules.get(module_path)
            if isinstance(module, dict):
                children = module.get("children")
                if isinstance(children, list):
                    for child_path in children:
                        if child_path in modules:
                            visit(child_path)
            active.pop()
            complete.add(module_path)

        visit(root)
        for module_path in modules:
            if module_path not in reachable:
                errors.append(f"{module_path}: not reachable from root '{root}'")

    return len(errors) == 0, errors


def _resolve_path(path: Optional[Path] = None) -> Optional[Path]:
    if path:
        return path
    current = Path.cwd()
    while current != current.parent:
        candidate = current / ".archmap.yaml"
        if candidate.exists():
            return candidate
        current = current.parent
    return None
