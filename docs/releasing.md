# Release Guide

This guide is for Archiscope maintainers. User installation currently targets GitHub; PyPI publishing remains intentionally disabled until trusted publishing is configured.

## Release checklist

1. Start from a clean `master` synchronized with `origin/master`.
2. Update the version in both:
   - `pyproject.toml`
   - `src/archiscope/__init__.py`
3. Move relevant entries from `Unreleased` into a dated section in `CHANGELOG.md`.
4. Run the full local gate:

   ```bash
   python -m pip install -e ".[dev]"
   ruff format --check src tests
   ruff check src tests
   mypy
   python -m unittest discover -s tests -v
   python -m build
   ```

5. Inspect the wheel and confirm its top-level package is `archiscope`, never `src`.
6. Install the wheel into a new virtual environment and verify:

   ```bash
   archiscope --version
   python -m archiscope --version
   ```

7. Push the release commit and wait for every CI matrix job to pass.
8. Create a signed `vX.Y.Z` tag.
9. Create a GitHub Release from the changelog section and attach the sdist and wheel.

## PyPI readiness

Before the first PyPI release:

- Reserve and verify the `archiscope` project name.
- Configure PyPI trusted publishing for this repository.
- Add a tag-triggered publish workflow with a protected environment.
- Test the workflow against TestPyPI.
- Replace the Git installation command in the README only after the public package is available.

Never place a long-lived PyPI API token in repository secrets when trusted publishing is available.
