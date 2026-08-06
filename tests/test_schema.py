import tempfile
import unittest
from pathlib import Path

import yaml

from archiscope.schema import validate
from archiscope.semantics import (
    audit_semantics,
    canonical_relation_pairs,
    iter_canonical_relations,
    resolve_module_feature,
    validate_semantic_overlay,
)
from tests.helpers import sample_archmap, sample_archmap_with_custom_root


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

    def test_nonstandard_single_root_id_is_valid(self):
        ok, errors = self._validate_data(sample_archmap_with_custom_root())
        self.assertTrue(ok, errors)

    def test_multiple_roots_are_rejected(self):
        data = sample_archmap()
        data["modules"]["other_root"] = {
            "label": "Other Root",
            "type": "root",
            "children": [],
        }
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(any("Exactly one root" in error for error in errors), errors)

    def test_alias_target_must_exist(self):
        data = sample_archmap()
        data["aliases"]["missing"] = "does.not.exist"
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(any("targets undefined module" in error for error in errors), errors)

    def test_group_members_must_be_unique_direct_children(self):
        data = sample_archmap()
        data["modules"]["engine"]["groups"] = {
            "first": {"label": "First", "modules": ["engine.source"]},
            "second": {"label": "Second", "modules": ["engine.source"]},
        }
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(any("appears more than once" in error for error in errors), errors)

    def test_lane_ids_and_members_must_be_unique(self):
        data = sample_archmap()
        data["modules"]["engine"]["lanes"] = [
            {"id": "run", "label": "First", "modules": ["engine.source"]},
            {"id": "run", "label": "Second", "modules": ["engine.source"]},
        ]
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(any("duplicate lane id" in error for error in errors), errors)
        self.assertTrue(any("appears more than once" in error for error in errors), errors)

    def test_ownership_children_must_be_unique(self):
        data = sample_archmap()
        data["modules"]["engine"]["children"].append("engine.source")
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(any("children' must not contain duplicates" in error for error in errors))

    def test_parent_and_children_must_be_symmetric(self):
        data = sample_archmap()
        data["modules"]["engine.source"]["parent"] = "root"
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(any("declares parent 'root'" in error for error in errors), errors)
        self.assertTrue(any("does not list it as a child" in error for error in errors), errors)

    def test_ownership_cycles_and_unreachable_modules_are_rejected(self):
        data = sample_archmap()
        data["modules"]["engine.source"]["children"] = ["engine"]
        data["modules"]["engine"]["parent"] = "engine.source"
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(any("ownership cycle detected" in error for error in errors), errors)

        data = sample_archmap()
        data["modules"]["orphan"] = {
            "label": "Orphan",
            "type": "module",
            "parent": "root",
        }
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(any("not reachable from root" in error for error in errors), errors)

    def test_registered_feature_and_relation_extensions_are_valid(self):
        data = sample_archmap()
        data["semantics"] = {
            "features": {"pipeline-control": "orchestration"},
            "relation_kinds": {"x-record-stream": {"family": "data"}},
        }
        data["modules"]["engine"]["feature"] = "pipeline-control"
        data["modules"]["engine"]["edges"] = [
            {
                "from": "engine.source",
                "to": "engine.worker",
                "kind": "x-record-stream",
                "payload_type": "NormalizedRecord",
            }
        ]
        ok, errors = self._validate_data(data)
        self.assertTrue(ok, errors)

    def test_unknown_family_and_unregistered_tokens_are_rejected(self):
        data = sample_archmap()
        data["semantics"] = {
            "features": {
                "pipeline-control": "made-up",
                "styled": {"family": "data", "color": "#00f"},
            },
            "relation_kinds": {"stream": "data"},
        }
        data["modules"]["engine"]["feature"] = "pipeline-control"
        data["modules"]["engine"]["edges"] = [
            {"from": "engine.source", "to": "engine.worker", "kind": "x-unregistered"}
        ]
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(any("unknown family" in error for error in errors), errors)
        self.assertTrue(
            any("visual styling is renderer-owned" in error for error in errors), errors
        )
        self.assertTrue(any("must start with 'x-'" in error for error in errors), errors)
        self.assertTrue(any("unknown feature token" in error for error in errors), errors)
        self.assertTrue(any("unknown relation kind" in error for error in errors), errors)

    def test_duplicate_semantic_edges_are_rejected_but_parallel_kinds_are_valid(self):
        data = sample_archmap()
        data["modules"]["engine"]["edges"] = [
            {"from": "engine.source", "to": "engine.worker", "kind": "data"},
            {"from": "engine.source", "to": "engine.worker", "kind": "command"},
        ]
        ok, errors = self._validate_data(data)
        self.assertTrue(ok, errors)
        relations = [
            relation
            for relation in iter_canonical_relations(data)
            if relation["from"] == "engine.source" and relation["to"] == "engine.worker"
        ]
        self.assertEqual([relation["kind"] for relation in relations], ["data", "command"])
        self.assertEqual(audit_semantics(data)["relations"]["semantic_lines"], 3)

        data["modules"]["engine"]["edges"].append(
            {"from": "engine.source", "to": "engine.worker", "kind": "data"}
        )
        ok, errors = self._validate_data(data)
        self.assertFalse(ok)
        self.assertTrue(any("duplicate semantic edge" in error for error in errors), errors)

    def test_feature_decision_uses_explicit_overlay_inheritance_then_neutral(self):
        data = sample_archmap()
        data["modules"]["engine"]["feature"] = "orchestration"
        data["modules"]["engine.worker"]["feature"] = "compute"
        overlay = {"modules": {"engine.source": "data", "engine.worker": "assurance"}}

        inherited = resolve_module_feature(data, "engine.sink")
        self.assertEqual((inherited["family"], inherited["source"]), ("orchestration", "inherited"))
        preview = resolve_module_feature(data, "engine.source", overlay)
        self.assertEqual((preview["family"], preview["source"]), ("data", "overlay"))
        explicit = resolve_module_feature(data, "engine.worker", overlay)
        self.assertEqual((explicit["family"], explicit["source"]), ("compute", "explicit"))
        root = resolve_module_feature(data, "root")
        self.assertEqual((root["family"], root["source"]), ("neutral", "fallback"))

        preview_data = sample_archmap()
        inherited_preview = resolve_module_feature(
            preview_data, "engine.sink", {"modules": {"engine": "data"}}
        )
        self.assertEqual(
            (
                inherited_preview["family"],
                inherited_preview["source"],
                inherited_preview["inherited_via"],
            ),
            ("data", "inherited", "overlay"),
        )

    def test_overlay_cannot_change_topology_or_conflict_with_confirmed_semantics(self):
        data = sample_archmap()
        data["modules"]["engine.worker"]["feature"] = "compute"
        data["modules"]["engine"]["edges"] = [
            {
                "from": "engine.source",
                "to": "engine.worker",
                "kind": "data",
                "payload_type": "Record",
            }
        ]
        overlay = {
            "modules": {
                "engine.worker": {
                    "feature": "assurance",
                    "confidence": "high",
                    "evidence": "explicit contract",
                },
                "missing": "data",
            },
            "edges": [
                {
                    "from": "engine.source",
                    "to": "engine.worker",
                    "kind": "command",
                    "payload_type": "Command",
                    "confidence": "medium",
                    "evidence": ["contract.py"],
                },
                {"from": "engine.source", "to": "engine.sink", "kind": "data"},
            ],
        }
        errors = validate_semantic_overlay(data, overlay)
        self.assertTrue(any("module does not exist" in error for error in errors), errors)
        self.assertTrue(
            any("conflicts with confirmed feature" in error for error in errors), errors
        )
        self.assertTrue(any("conflicts with confirmed kind" in error for error in errors), errors)
        self.assertTrue(
            any("not an existing canonical relation" in error for error in errors), errors
        )

    def test_overlay_accepts_exact_canonical_pairs_and_distinct_parallel_kinds(self):
        data = sample_archmap()
        data["modules"]["engine"]["edges"] = [
            {
                "from": "engine.source",
                "to": "engine.worker",
                "label": "normalized records",
            }
        ]
        overlay = {
            "schema": "archiscope/semantic-overlay/1.0",
            "modules": {"engine.source": "boundary"},
            "edges": [
                {
                    "from": "engine.source",
                    "to": "engine.worker",
                    "kind": "data",
                    "confidence": "high",
                    "evidence": "payload contract",
                },
                {
                    "from": "engine.source",
                    "to": "engine.worker",
                    "kind": "event",
                    "confidence": "low",
                    "reason": "directory evidence only",
                },
            ],
        }
        self.assertEqual(validate_semantic_overlay(data, overlay), [])
        self.assertIn(("engine.source", "engine.worker"), canonical_relation_pairs(data))
        relations = [
            relation
            for relation in iter_canonical_relations(data, overlay)
            if relation["from"] == "engine.source" and relation["to"] == "engine.worker"
        ]
        self.assertEqual([relation["kind"] for relation in relations], ["data", "event"])
        self.assertEqual(
            [relation["label"] for relation in relations],
            ["normalized records", "normalized records"],
        )

    def test_overlay_targets_exact_relations_not_projected_domain_directions(self):
        data = sample_archmap()
        data["modules"]["root"]["children"].append("delivery")
        data["modules"]["delivery"] = {
            "label": "Delivery",
            "type": "engine",
            "parent": "root",
            "children": ["delivery.writer"],
        }
        data["modules"]["delivery.writer"] = {
            "label": "Writer",
            "type": "module",
            "parent": "delivery",
        }
        data["modules"]["engine.source"]["downstream"].append("delivery.writer")

        exact = {"edges": [{"from": "engine.source", "to": "delivery.writer", "kind": "data"}]}
        projected = {"edges": [{"from": "engine", "to": "delivery", "kind": "data"}]}
        self.assertEqual(validate_semantic_overlay(data, exact), [])
        errors = validate_semantic_overlay(data, projected)
        self.assertTrue(any("not an existing canonical relation" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
