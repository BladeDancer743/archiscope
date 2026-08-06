# Changelog

All notable changes to Archiscope are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Color themes: `--theme NAME` and `archiscope list-themes` with ten truecolor (24-bit) palettes — `default` (Tailwind 500-level), `monokai`, `solarized`, `dracula`, `nord`, `crt-green`, `crt-amber`, `synthwave`, `gruvbox`, `tokyonight`. Every semantic role has a distinct color; themes are shared by the terminal overview and all geometry strategies.
- Design-assistance coloring via `--color-by type|feature|heat`: structure, semantic responsibility family (gray for unclassified), or coupling heat. Semantic rule violations (cycles, asymmetry, contract drift, type inversion, dead edges) always override with the assurance color and dashed frames, so architecture problems stand out immediately.
- Chain-row layout: graphs whose layers each hold ≤2 modules with direct cross-layer edges and no skipping render as one compact horizontal row with arrows and dotted projected markers instead of stacked full-width frames.
- Nested engine frames (`--depth ≥ 2`): child modules render inside the engine frame with complete single-line labels (width sized by the widest child), internal relations drawn between blocks, and same-layer cross-frame child links drawn as connectors through the box gap.
- Blueprint cross-zone bus: the INBOUND→HUB→OUTBOUND connectors aggregate real cross-zone edges with `xN` counts and bidirectional markers instead of template arrows.
- Per-agent terminal channel adaptation in installed skills (color/width recommendations per host).

### Changed

- Frames never truncate or wrap labels: all width budgets account for the `● [FAMILY] ` semantic prefix and the `▾N` expansion marker — multi-module rows, lone-module frames, chain rows and nested blocks are all covered.
- The geometry verify/correct pipeline only adopts a relayout when it strictly reduces violations; `flow`/`minimal` render their own deliberate routing without destructive incremental fixes.
- Geometry edge routing: vertical arrowheads stop above the target frame, same-row edges stay in inter-box gaps, and non-adjacent rows detour through the gap row — no line pierces a box.
- The terminal overview draws route-lane connectors (tee on the target frame top/bottom) and keeps every row within the requested width.

### Fixed

- G4 frame-closure corner math (Rect `right`/`bottom` are exclusive), which previously flagged every intact box as broken and sent `correct()` into a destructive full relayout.
- CJK display-width handling across cards/class_diagram multi-column layouts, chain-row arrows, child block padding and balanced line breaks.
- Trailing blank rows from fixed-height char grids; ANSI color runs compressed to at most two segments per row for renderers that mis-measure three-plus switches.

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
