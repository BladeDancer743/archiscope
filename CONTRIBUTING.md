# Contributing to Archiscope

Thanks for helping make software architecture easier to inspect from an AI coding conversation.

## Good first contributions

- Add a focused regression test for a renderer edge case.
- Improve CJK alignment or terminal-width behavior.
- Expand a fictional example without introducing real project data.
- Improve Agent adapter instructions while keeping all reference copies synchronized.
- Propose a view only when its intended question is distinct from the existing 16 strategies.

For larger changes, open a feature request first so the data contract and renderer behavior can be agreed before implementation.

## Development setup

Archiscope supports Python 3.10–3.14.

```bash
git clone https://github.com/BladeDancer743/archiscope.git
cd archiscope
python -m venv .venv
```

Activate the environment, then install the package and development tools:

```bash
python -m pip install -e ".[dev]"
```

Run the quality gate:

```bash
ruff format --check src tests
ruff check src tests
mypy
python -m unittest discover -s tests -v
python -m build
```

Pre-commit hooks are also available:

```bash
pre-commit install
pre-commit install --hook-type pre-push
```

## Repository map

```text
src/archiscope/
├── cli.py          command routing and error semantics
├── schema.py       .archmap.yaml validation
├── strategies.py   public strategy registry and aliases
├── install.py      Agent detection and adapter installation
└── render/
    └── geometry/
        ├── draw/    renderers and CJK-safe character grid
        ├── verify/  geometry and semantic rules
        └── correct/ transactional correction passes
```

## Adding or changing a renderer

1. Start with the architectural question the view answers.
2. Reuse the character-grid primitives instead of calculating display width with `len()`.
3. Register the renderer and any aliases in the canonical strategy registry.
4. Document it in the README strategy table and the strategy gallery.
5. Add focused tests and keep the public strategy count intentional.
6. Smoke-test against `examples/medium.yaml`.

Terminal output is a compatibility surface. Preserve spacing, arrow direction, and CJK alignment deliberately.

## Agent adapter changes

`src/archiscope/install.py` contains generated adapter content. Reference copies under `agents/` must remain byte-for-byte synchronized; the test suite enforces this.

Examples and comments must remain fictional and must not reveal private project names, paths, topology, credentials, or organization-specific terminology.

## Pull requests

- Keep each PR focused on one coherent outcome.
- Explain the user-visible behavior, not only the implementation.
- Include tests for bug fixes.
- Update documentation when commands, output, schema, or public strategies change.
- Confirm the full quality gate passes locally.

By contributing, you agree that your contribution is licensed under the repository’s MIT License.
