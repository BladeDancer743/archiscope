# Changelog

All notable changes to Archiscope are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2026-08-04

### Added

- Terminal-native `overview` renderer with the width-safe Vertical Layered Bus Topology: `1..N` nodes per logical layer, same-canvas fan-out/mesh/feedback lanes, an explicit isolated zone, and stable physical reflow; a current-depth ownership tree and compact legend are always included.
- Deterministic module feature families (`orchestration`, `compute`, `data`, `state`, `authority`, `boundary`, `delivery`, `assurance`, and `neutral`).
- Deterministic relation families (`dependency`, `data`, `command`, `authority`, `event`, and `reference`) with textual tags and Unicode/ASCII markers.
- Project semantic registries, module `feature`, and edge `kind`, `payload_type`, and `label` fields.
- `archiscope semantics audit [PATH] [--json]`, including separate canonical-pair and semantic-line counts.
- Validated semantic preview overlays with evidence, reason, and `high / medium / low` confidence metadata.
- `--format`, `--color`, `--charset`, `--width`, and `--semantic-overlay` render controls.
- Active `lanes` and `layout` compatibility rendering with schema checks for unique direct members.
- Regression coverage for semantic inheritance and overrides, multiple kinds per pair, overlay conflicts, ANSI invariants, CJK alignment, strict-ASCII framing, layered-bus width reflow, and dense projected topology.

### Changed

- **Breaking default:** `archiscope render PATH` now emits `terminal / overview`; use `--format mermaid` to preserve the 0.5.x output.
- Ownership depth defaults to one. `--depth 0` gives a compact domain view and `--depth 2+` continues expansion.
- Projection aggregation now keys on source, target, semantic kind, and direct/projected state. Different kinds and projection states remain separate; opposite directions merge only when both match.
- `xN` continues to count represented canonical architecture relations, never traffic or call volume.
- Color is foreground-only and injected after layout. `auto` requires a TTY, no `NO_COLOR`, and `TERM != dumb`; explicit `always / never` wins.
- Agent adapters now default to terminal overview, require `--charset ascii` for architecture-diagram/ASCII requests, and enforce the audit → evidence/confidence proposal → overlay preview → explicit user confirmation workflow before semantic write-back.
- Inferred blueprint zones use `INBOUND / HUB / OUTBOUND`; onion rings report in-degree bands instead of inferred architectural roles.

### Fixed

- Non-TTY, `NO_COLOR`, and `TERM=dumb` auto output cannot leak ANSI; Mermaid never receives ANSI.
- ANSI spans reset immediately and do not affect padding, CJK width, routing, or geometry.
- Semantic overlays cannot create topology, target missing modules or relations, duplicate a `from/to/kind` line, or conflict with confirmed semantics.
- Unknown visual families and unregistered extension kinds are rejected; custom relation kinds require an `x-` prefix.
- `all`, `全景`, root aliases, and direct root ids now resolve the unique configured root instead of assuming its id is `root`.
- Panorama Mermaid IDs are disambiguated deterministically, and invalid duplicate or cyclic ownership is rejected.
- Panorama IDs are safely prefixed and labels are escaped for Mermaid node and edge contexts.
- Swimlane rendering now consumes declared lanes and preserves their labels.

### Migration

- Change existing Mermaid consumers from `archiscope render PATH` to `archiscope render PATH --format mermaid`.
- Terminal output may contain ANSI only when color resolves to enabled. Use `--color never` for stable snapshots and `--charset ascii` for strict ASCII consumers.

## [0.5.1] - 2026-07-28

### Added

- Standard `src/archiscope` package layout.
- `python -m archiscope` module entry point.
- Linux, macOS, and Windows CI across Python 3.10–3.14.
- Ruff, mypy, pre-commit, sdist, and wheel quality gates.
- Isolated wheel installation verification.
- Regression tests for correction-pass grid growth.

### Changed

- CLI entry point now targets `archiscope.cli:main`.
- Development and package metadata were expanded for public distribution.
- Source and tests now use a consistent formatter and import order.

### Fixed

- CJK truncation verification now imports the display-width primitive it calls.
- Shift and resize correction passes now use the real grid-resize API.
- README navigation no longer links to a missing English section.

## [0.5.0] - 2026-07-27

### Added

- Sanitized public repository history.
- Sixteen public terminal rendering strategies.
- Focused Mermaid rendering and `.archmap.yaml` validation.
- Agent adapters for Claude Code, OpenCode, Codex, Cursor, and GitHub Copilot.
- Twenty-five geometry, CJK, and semantic verification rules.

[Unreleased]: https://github.com/BladeDancer743/archiscope/compare/v0.6.0...HEAD
[0.6.0]: https://github.com/BladeDancer743/archiscope/compare/89a6da945892ba05515dac672b80662cc492dd4c...v0.6.0
[0.5.1]: https://github.com/BladeDancer743/archiscope/commit/89a6da945892ba05515dac672b80662cc492dd4c
[0.5.0]: https://github.com/BladeDancer743/archiscope/commit/7e4ea2ed9a2f22906094fbec82223379b01566cf
