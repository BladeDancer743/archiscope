import io
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from archiscope import __version__, cli
from tests.helpers import sample_archmap


class CliTests(unittest.TestCase):
    def _run(self, argv, data=None):
        stdout = io.StringIO()
        stderr = io.StringIO()
        load_patch = patch("archiscope.cli.load_archmap", return_value=data or sample_archmap())
        with (
            patch.object(sys, "argv", argv),
            patch.object(cli.sys, "platform", "test"),
            load_patch,
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            try:
                cli.main()
                code = 0
            except SystemExit as exc:
                code = exc.code
        return code, stdout.getvalue(), stderr.getvalue()

    def test_version(self):
        code, stdout, stderr = self._run(["archiscope", "--version"])
        self.assertEqual(code, 0)
        self.assertIn(__version__, stdout)
        self.assertEqual(stderr, "")

    def test_missing_module_returns_nonzero(self):
        code, stdout, stderr = self._run(["archiscope", "render", "missing", "--strategy", "flow"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Module 'missing' not found", stderr)

    def test_unknown_strategy_returns_nonzero(self):
        code, stdout, stderr = self._run(
            ["archiscope", "render", "engine", "--strategy", "unknown"]
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Strategy 'unknown' not found", stderr)


if __name__ == "__main__":
    unittest.main()
