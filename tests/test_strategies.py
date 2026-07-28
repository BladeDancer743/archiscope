import unittest
import re
from pathlib import Path

from src import __version__
from src.render.geometry.draw import RENDERERS
from src.strategies import (
    ALL_STRATEGY_NAMES,
    PUBLIC_STRATEGIES,
    STRATEGY_ALIASES,
)


class StrategyRegistryTests(unittest.TestCase):
    def test_public_strategy_count_is_stable(self):
        self.assertEqual(len(PUBLIC_STRATEGIES), 16)

    def test_renderer_registry_matches_accepted_names(self):
        self.assertEqual(set(RENDERERS), set(ALL_STRATEGY_NAMES))

    def test_aliases_resolve_to_same_renderer(self):
        for alias, target in STRATEGY_ALIASES.items():
            self.assertIs(RENDERERS[alias], RENDERERS[target])

    def test_readme_strategy_table_matches_registry(self):
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        section = readme.split("## 可用视图（16 种）", 1)[1].split("\n## ", 1)[0]
        documented = set(re.findall(r"^\| `([^`]+)`", section, re.MULTILINE))
        self.assertEqual(documented, set(PUBLIC_STRATEGIES))

    def test_package_versions_match(self):
        root = Path(__file__).resolve().parents[1]
        pyproject = (root / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn(f'version = "{__version__}"', pyproject)


if __name__ == "__main__":
    unittest.main()
