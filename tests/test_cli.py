import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

import yaml

from archiscope import __version__, cli
from tests.helpers import sample_archmap, sample_archmap_with_custom_root


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

    def test_panorama_selectors_support_a_nonstandard_root_id(self):
        data = sample_archmap_with_custom_root()
        outputs = []
        for selector in ("all", "全景", "平台", "platform"):
            with self.subTest(selector=selector):
                code, stdout, stderr = self._run(["archiscope", "render", selector], data)
                self.assertEqual(code, 0)
                self.assertEqual(stderr, "")
                self.assertIn("Test Engine", stdout)
                outputs.append(stdout)
        self.assertTrue(all(output == outputs[0] for output in outputs))

    def test_explicit_mermaid_depth_zero_restores_the_compact_view(self):
        data = sample_archmap_with_custom_root()
        code, stdout, stderr = self._run(
            ["archiscope", "render", "all", "--format", "mermaid", "--depth", "0"],
            data,
        )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn('m_engine["Test Engine"]', stdout)
        self.assertNotIn("m_engine_source", stdout)

    def test_negative_depth_is_rejected(self):
        code, stdout, stderr = self._run(["archiscope", "render", "all", "--depth", "-1"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Depth must be zero or greater", stderr)

    def test_depth_cannot_be_combined_with_a_terminal_strategy(self):
        code, stdout, stderr = self._run(
            ["archiscope", "render", "all", "--strategy", "tree", "--depth", "1"]
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("--depth is only available", stderr)

    def test_legacy_terminal_strategy_keeps_compatible_defaults(self):
        code, stdout, stderr = self._run(["archiscope", "render", "engine", "--strategy", "tree"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertTrue(stdout.strip())

    def test_legacy_terminal_strategy_rejects_ignored_terminal_options(self):
        cases = (
            (["--charset", "ascii"], "--charset only apply"),
            (["--width", "100"], "--width only apply"),
        )
        for options, expected in cases:
            with self.subTest(options=options):
                code, stdout, stderr = self._run(
                    ["archiscope", "render", "engine", "--strategy", "tree", *options]
                )
                self.assertEqual(code, 2)
                self.assertEqual(stdout, "")
                self.assertIn(expected, stderr)
                self.assertIn("uses fixed output settings", stderr)

    def test_geometry_strategy_accepts_color_option(self):
        code, stdout, stderr = self._run(
            ["archiscope", "render", "engine", "--strategy", "grouped", "--color", "always"]
        )
        self.assertEqual(code, 0, stderr)
        self.assertIn("\x1b[", stdout)
        code, stdout, stderr = self._run(
            ["archiscope", "render", "engine", "--strategy", "grouped", "--color", "never"]
        )
        self.assertEqual(code, 0, stderr)
        self.assertNotIn("\x1b[", stdout)

    def test_legacy_terminal_strategy_rejects_semantic_overlay(self):
        code, stdout, stderr = self._run(
            [
                "archiscope",
                "render",
                "engine",
                "--strategy",
                "tree",
                "--semantic-overlay",
                "unused.yaml",
            ]
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("only available with terminal overview", stderr)

    def test_depth_is_supported_for_a_non_root_container(self):
        code, stdout, stderr = self._run(["archiscope", "render", "engine", "--depth", "1"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Test Engine", stdout)
        self.assertIn("OWNERSHIP TREE", stdout)

    def test_render_defaults_to_terminal_overview_and_mermaid_is_explicit(self):
        code, terminal, stderr = self._run(
            ["archiscope", "render", "all", "--color", "never", "--width", "100"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("ARCHISCOPE", terminal)
        self.assertIn("LEGEND", terminal)
        self.assertNotIn("graph ", terminal)

        code, mermaid, stderr = self._run(
            ["archiscope", "render", "all", "--format", "mermaid", "--color", "always"]
        )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("graph ", mermaid)
        self.assertNotIn("\x1b", mermaid)

    def test_terminal_overlay_is_loaded_validated_and_previewed(self):
        overlay = {
            "schema": "archiscope/semantic-overlay/1.0",
            "modules": {"engine.source": "boundary"},
            "edges": [
                {
                    "from": "engine.source",
                    "to": "engine.worker",
                    "kind": "data",
                    "confidence": "high",
                    "evidence": "Payload contract",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            overlay_path = Path(tmp) / "preview.yaml"
            overlay_path.write_text(
                yaml.safe_dump(overlay, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
            code, stdout, stderr = self._run(
                [
                    "archiscope",
                    "render",
                    "all",
                    "--color",
                    "never",
                    "--width",
                    "120",
                    "--semantic-overlay",
                    str(overlay_path),
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("[BOUNDARY]", stdout)
        self.assertIn("[DAT]", stdout)

    def test_terminal_overlay_rejects_topology_changes(self):
        overlay = {"edges": [{"from": "engine.source", "to": "engine.sink", "kind": "data"}]}
        with tempfile.TemporaryDirectory() as tmp:
            overlay_path = Path(tmp) / "invalid.yaml"
            overlay_path.write_text(yaml.safe_dump(overlay), encoding="utf-8")
            code, stdout, stderr = self._run(
                ["archiscope", "render", "all", "--semantic-overlay", str(overlay_path)]
            )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("not an existing canonical relation", stderr)

    def test_semantic_overlay_is_rejected_for_mermaid_output(self):
        code, stdout, stderr = self._run(
            [
                "archiscope",
                "render",
                "all",
                "--format",
                "mermaid",
                "--semantic-overlay",
                "unused.yaml",
            ]
        )
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("only available with terminal overview", stderr)

    def test_nonpositive_width_is_rejected(self):
        code, stdout, stderr = self._run(["archiscope", "render", "all", "--width", "0"])
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("Width must be greater than zero", stderr)

    def test_semantics_audit_reports_fallback_modules_and_exact_relations(self):
        code, stdout, stderr = self._run(["archiscope", "semantics", "audit"])
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        self.assertIn("Modules: 0/5 classified", stdout)
        self.assertIn("Relations: 0/2 classified", stdout)
        self.assertIn("[neutral] engine.worker", stdout)
        self.assertIn("[dependency] engine.source -> engine.worker", stdout)

    def test_semantics_audit_json_distinguishes_inherited_and_confirmed(self):
        data = sample_archmap()
        data["modules"]["engine"]["feature"] = "orchestration"
        data["modules"]["engine"]["edges"] = [
            {"from": "engine.source", "to": "engine.worker", "kind": "data"}
        ]
        code, stdout, stderr = self._run(["archiscope", "semantics", "audit", "--json"], data)
        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")
        report = json.loads(stdout)
        self.assertEqual(report["modules"]["classified"], 4)
        self.assertEqual(report["modules"]["inherited"], 3)
        self.assertEqual(report["relations"]["classified"], 1)
        self.assertEqual(
            report["relations"]["unclassified"],
            [{"from": "engine.worker", "to": "engine.sink", "default": "dependency"}],
        )

    def test_semantics_audit_rejects_invalid_confirmed_semantics(self):
        data = sample_archmap()
        data["modules"]["engine"]["feature"] = "unregistered-feature"
        code, stdout, stderr = self._run(["archiscope", "semantics", "audit"], data)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("unknown feature token", stderr)


if __name__ == "__main__":
    unittest.main()
