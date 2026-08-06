"""CLI entry point for archiscope."""

import argparse
import json
import sys
from pathlib import Path

import yaml

from . import __version__
from .render import (
    RenderError,
    TerminalRenderError,
    geometry_render,
    load_archmap,
    render_terminal,
    resolve_module_path,
)
from .render import (
    render_legacy as render,
)
from .schema import validate
from .semantics import (
    SemanticError,
    audit_semantics,
    load_semantic_overlay,
    semantic_schema_errors,
)
from .strategies import ALL_STRATEGY_NAMES, PUBLIC_STRATEGIES


class UserInputError(Exception):
    """A recoverable CLI input/configuration error."""


def main():
    # Force UTF-8 on Windows
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        prog="archiscope",
        description="Portable architecture zoom lens for AI coding agents",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # render
    render_cmd = sub.add_parser("render", help="Render a terminal architecture overview")
    render_cmd.add_argument("path", help="Module path (e.g. demo.pipeline) or 'all' for panorama")
    render_cmd.add_argument(
        "--zoom",
        default="auto",
        choices=["auto", "panorama", "engine", "layer", "module", "function"],
        help=argparse.SUPPRESS,
    )
    render_cmd.add_argument(
        "--format",
        choices=["terminal", "mermaid"],
        default="terminal",
        help="Output format (default: terminal; use mermaid for the legacy diagram)",
    )
    render_cmd.add_argument(
        "--strategy",
        default="overview",
        help="Terminal render strategy (default: overview; e.g. tree, flow, grouped)",
    )
    render_cmd.add_argument(
        "--depth",
        type=int,
        default=None,
        help="Ownership expansion depth (default: 1)",
    )
    render_cmd.add_argument(
        "--color",
        choices=["auto", "always", "never"],
        default=None,
        help="ANSI foreground color policy (default: auto)",
    )
    render_cmd.add_argument(
        "--charset",
        choices=["auto", "unicode", "ascii"],
        default=None,
        help="Terminal character set (default: auto)",
    )
    render_cmd.add_argument(
        "--width",
        type=int,
        default=None,
        help="Terminal layout width (default: detected terminal width)",
    )
    render_cmd.add_argument(
        "--semantic-overlay",
        default=None,
        metavar="FILE",
        help="Validated semantic preview overlay; never changes the blueprint",
    )
    render_cmd.add_argument(
        "--theme",
        default="default",
        help="Color theme (default: default; run 'archiscope list-themes')",
    )
    # list-strategies
    sub.add_parser("list-strategies", help="List all available render strategies")

    # list-themes
    sub.add_parser("list-themes", help="List all available color themes")

    # validate
    val_cmd = sub.add_parser("validate", help="Validate .archmap.yaml format")
    val_cmd.add_argument(
        "--path", default=None, help="Path to .archmap.yaml (auto-detect by default)"
    )

    # semantics
    semantics_cmd = sub.add_parser("semantics", help="Inspect confirmed visual semantics")
    semantics_sub = semantics_cmd.add_subparsers(dest="semantics_command", required=True)
    audit_cmd = semantics_sub.add_parser(
        "audit", help="List modules and canonical relations still using fallback semantics"
    )
    audit_cmd.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Project directory or .archmap.yaml path (auto-detect by default)",
    )
    audit_cmd.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    # install
    inst_cmd = sub.add_parser("install", help="Install agent-specific adapters")
    inst_cmd.add_argument("--detect", action="store_true", help="Auto-detect available agents")
    inst_cmd.add_argument(
        "--agents",
        nargs="+",
        choices=["claude-code", "opencode", "codex", "cursor", "copilot"],
        help="Specific agents to install for",
    )

    args = parser.parse_args()

    if args.command == "render":
        try:
            data = load_archmap()
            modules = data.get("modules", {})
            actual = resolve_module_path(data, args.path)
            if actual not in modules:
                available = ", ".join(list(modules)[:10])
                raise UserInputError(f"Module '{args.path}' not found. Available: {available}")
            if args.strategy != "overview" and args.strategy not in ALL_STRATEGY_NAMES:
                available = ", ".join(("overview", *PUBLIC_STRATEGIES))
                raise UserInputError(
                    f"Strategy '{args.strategy}' not found. Available: {available}"
                )
            if args.depth is not None and args.depth < 0:
                raise UserInputError("Depth must be zero or greater")
            if args.width is not None and args.width <= 0:
                raise UserInputError("Width must be greater than zero")
            if args.strategy != "overview" and args.depth is not None:
                raise UserInputError("--depth is only available with the overview strategy")
            if args.format == "mermaid" and args.strategy != "overview":
                raise UserInputError("Mermaid output only supports the overview strategy")
            if args.format == "terminal" and args.zoom != "auto":
                raise UserInputError("--zoom is only available with --format mermaid")
            if args.format == "terminal" and args.strategy != "overview":
                unsupported = [
                    option
                    for option, supplied in (
                        ("--charset", args.charset is not None),
                        ("--width", args.width is not None),
                    )
                    if supplied
                ]
                if unsupported:
                    names = ", ".join(unsupported)
                    raise UserInputError(
                        f"{names} only apply to --strategy overview; "
                        f"geometry strategy '{args.strategy}' uses fixed output settings"
                    )
            if args.semantic_overlay is not None and (
                args.format != "terminal" or args.strategy != "overview"
            ):
                raise UserInputError(
                    "--semantic-overlay is only available with terminal overview output"
                )

            semantic_errors = semantic_schema_errors(data)
            if semantic_errors:
                raise SemanticError(
                    "invalid archmap semantics:\n  - " + "\n  - ".join(semantic_errors)
                )
            overlay = (
                load_semantic_overlay(args.semantic_overlay, data)
                if args.semantic_overlay is not None
                else None
            )
            depth = 1 if args.depth is None else args.depth
            if args.format == "mermaid":
                output = render(data, args.path, args.zoom, depth)
            elif args.strategy != "overview":
                output = geometry_render(
                    data,
                    args.path,
                    args.strategy,
                    color=args.color or "auto",
                    theme=args.theme,
                )
            else:
                output = render_terminal(
                    data,
                    args.path,
                    strategy=args.strategy,
                    depth=depth,
                    color=args.color or "auto",
                    charset=args.charset or "auto",
                    width=args.width,
                    semantic_overlay=overlay,
                    theme=args.theme,
                    stream=sys.stdout,
                )
            print(output)
        except (
            FileNotFoundError,
            OSError,
            RenderError,
            SemanticError,
            TerminalRenderError,
            UnicodeError,
            UserInputError,
            yaml.YAMLError,
        ) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(2)

    elif args.command == "validate":
        try:
            ok, errors = validate(Path(args.path) if args.path else None)
            if ok:
                print(".archmap.yaml is valid")
            else:
                print("Validation errors:")
                for error in errors:
                    print(f"  - {error}")
                sys.exit(1)
        except FileNotFoundError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "list-strategies":
        _list_strategies()

    elif args.command == "list-themes":
        _list_themes()

    elif args.command == "semantics" and args.semantics_command == "audit":
        try:
            data = _load_archmap_at(args.path)
            report = audit_semantics(data)
            if args.json:
                print(json.dumps(report, ensure_ascii=False, indent=2))
            else:
                _print_semantic_audit(report)
        except (FileNotFoundError, OSError, SemanticError, UnicodeError, yaml.YAMLError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(2)

    elif args.command == "install":
        if args.detect:
            print("Detecting agents...")
            _install_detect()
        elif args.agents:
            for agent in args.agents:
                _install_agent(agent)
        else:
            print("Use --detect or --agents {names}", file=sys.stderr)
            sys.exit(1)


def _install_agent(agent: str):
    from .install import INSTALL_MAP, find_project

    root = find_project()
    if not root:
        print("Not in a project directory")
        return False

    entry = INSTALL_MAP.get(agent)
    if not entry:
        print(f"Unknown agent: {agent}")
        return False

    target = root / entry["target"]
    target.parent.mkdir(parents=True, exist_ok=True)
    content = entry["content"]
    existing = target.read_bytes().decode("utf-8") if target.exists() else ""

    if entry.get("append"):
        normalized_existing = existing.replace("\r\n", "\n")
        if content.rstrip() in normalized_existing:
            print(f"  {agent}: already installed at {target}")
            return True
        separator = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
        with open(target, "a", encoding="utf-8", newline="") as f:
            f.write(separator + content)
    else:
        if existing == content:
            print(f"  {agent}: already installed at {target}")
            return True
        with open(target, "w", encoding="utf-8", newline="") as f:
            f.write(content)
    print(f"  {agent}: installed to {target}")
    return True


def _install_detect():
    from .install import detect_agents, find_project

    root = find_project()
    if not root:
        print("Not in a project directory")
        return

    detected = detect_agents(root)
    for agent in detected:
        _install_agent(agent)
    if not detected:
        print("No supported agents detected in this project")


STRATEGY_INFO = {
    "overview": ("语义总览", "默认彩色终端拓扑，含关系语义、ownership tree 与图例"),
    **PUBLIC_STRATEGIES,
}


def _list_strategies():
    print("可用渲染策略:\n")
    for key, (name, desc) in STRATEGY_INFO.items():
        print(f"  {key:16s} {name:8s}  {desc}")


def _list_themes():
    from .render.ansi import THEMES

    print("可用配色主题:\n")
    for name, theme in THEMES.items():
        print(f"  {name:12s} {theme.description}")


def _load_archmap_at(path: str | None) -> dict:
    if path is None:
        data = load_archmap()
    else:
        yaml_path = Path(path)
        if yaml_path.is_dir():
            yaml_path /= ".archmap.yaml"
        with open(yaml_path, "r", encoding="utf-8") as stream:
            data = yaml.safe_load(stream)
    if not isinstance(data, dict):
        raise SemanticError("archmap root must be a mapping")
    return data


def _print_semantic_audit(report: dict) -> None:
    modules = report["modules"]
    relations = report["relations"]
    print("Semantic audit")
    print(
        f"Modules: {modules['classified']}/{modules['total']} classified "
        f"({modules['inherited']} inherited), {len(modules['unclassified'])} unclassified"
    )
    for module in modules["unclassified"]:
        print(f"  [neutral] {module['path']} ({module['type']}: {module['label']})")
    print(
        f"Relations: {relations['classified']}/{relations['total']} classified, "
        f"{len(relations['unclassified'])} unclassified, "
        f"{relations['semantic_lines']} semantic lines"
    )
    for relation in relations["unclassified"]:
        print(f"  [dependency] {relation['from']} -> {relation['to']}")
