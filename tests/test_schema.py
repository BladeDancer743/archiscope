import tempfile
import unittest
from pathlib import Path

import yaml

from src.schema import validate
from tests.helpers import sample_archmap


class SchemaTests(unittest.TestCase):
    def _validate_data(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ".archmap.yaml"
            path.write_text(
                yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            return validate(path)

    def test_sample_is_valid(self):
        ok, errors = self._validate_data(sample_archmap())
        self.assertTrue(ok, errors)

    def test_strategy_aliases_are_valid_configuration(self):
        for strategy in ("auto", "matrix"):
            with self.subTest(strategy=strategy):
                data = sample_archmap()
                data["modules"]["engine"]["render_strategy"] = strategy
                ok, errors = self._validate_data(data)
                self.assertTrue(ok, errors)

    def test_unknown_strategy_is_rejected(self):
        data = sample_archmap()
        data["modules"]["engine"]["render_strategy"] = "does_not_exist"
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(
            any("unknown render_strategy" in error for error in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
