# Changelog

All notable changes to Archiscope are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned

- Dynamic terminal-width detection and adaptive layouts.
- PyPI trusted publishing.
- HTML and SVG export experiments.

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

[Unreleased]: https://github.com/BladeDancer743/archiscope/compare/89a6da945892ba05515dac672b80662cc492dd4c...HEAD
[0.5.1]: https://github.com/BladeDancer743/archiscope/commit/89a6da945892ba05515dac672b80662cc492dd4c
[0.5.0]: https://github.com/BladeDancer743/archiscope/commit/7e4ea2ed9a2f22906094fbec82223379b01566cf
