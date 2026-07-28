"""CLI entry point for archiscope."""

import argparse
import sys
from pathlib import Path

from . import __version__
from .render import (
    geometry_render,
    load_archmap,
    resolve_alias,
)
from .render import (
    render_legacy as render,
)
from .schema import validate
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
    render_cmd = sub.add_parser("render", help="Render a Mermaid architecture diagram")
    render_cmd.add_argument("path", help="Module path (e.g. demo.pipeline) or '全景'")
    render_cmd.add_argument(
        "--zoom",
        default="auto",
        choices=["auto", "panorama", "engine", "layer", "module", "function"],
        help="Override zoom level",
    )
    render_cmd.add_argument(
        "--strategy", default=None, help="Force a render strategy (e.g. swimlane, grouped, tree)"
    )
    # list-strategies
    sub.add_parser("list-strategies", help="List all available render strategies")

    # validate
    val_cmd = sub.add_parser("validate", help="Validate .archmap.yaml format")
    val_cmd.add_argument(
        "--path", default=None, help="Path to .archmap.yaml (auto-detect by default)"
    )

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
            actual = "root" if args.path in ("全景", "all") else resolve_alias(data, args.path)
            if actual not in modules:
                available = ", ".join(list(modules)[:10])
                raise UserInputError(f"Module '{args.path}' not found. Available: {available}")
            if args.strategy and args.strategy not in ALL_STRATEGY_NAMES:
                available = ", ".join(PUBLIC_STRATEGIES)
                raise UserInputError(
                    f"Strategy '{args.strategy}' not found. Available: {available}"
                )

            if args.strategy:
                output = geometry_render(data, args.path, args.strategy)
            else:
                output = render(data, args.path, args.zoom)
            print(output)
        except (FileNotFoundError, UserInputError) as exc:
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
    existing = target.read_text(encoding="utf-8") if target.exists() else ""

    if entry.get("append"):
        if content.rstrip() in existing:
            print(f"  {agent}: already installed at {target}")
            return True
        separator = "" if not existing else ("\n" if existing.endswith("\n") else "\n\n")
        with open(target, "a", encoding="utf-8") as f:
            f.write(separator + content)
    else:
        if existing == content:
            print(f"  {agent}: already installed at {target}")
            return True
        with open(target, "w", encoding="utf-8") as f:
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


STRATEGY_INFO = PUBLIC_STRATEGIES


def _list_strategies():
    print("可用渲染策略:\n")
    for key, (name, desc) in STRATEGY_INFO.items():
        print(f"  {key:16s} {name:8s}  {desc}")
