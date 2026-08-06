import unittest
from io import StringIO

from archiscope.render import (
    RenderError,
    TerminalRenderError,
    derive_edges,
    derive_panorama_edges,
    derive_terminal_edges,
    derive_visible_internal_edges,
    geometry_render,
    render_legacy,
    render_terminal,
    strip_ansi,
)
from archiscope.render.geometry.draw.grid import str_width
from archiscope.strategies import PUBLIC_STRATEGIES
from tests.helpers import sample_archmap, sample_archmap_with_custom_root


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.data = sample_archmap()

    def test_derive_edges_deduplicates_symmetric_declarations(self):
        scope = ["engine.source", "engine.worker", "engine.sink"]
        edges = derive_edges(self.data, scope)
        pairs = {(edge["from"], edge["to"]) for edge in edges}
        self.assertEqual(
            pairs,
            {
                ("engine.source", "engine.worker"),
                ("engine.worker", "engine.sink"),
            },
        )
        self.assertEqual(len(edges), len(pairs))

    def test_all_public_strategies_render_nonempty_output(self):
        for strategy in PUBLIC_STRATEGIES:
            with self.subTest(strategy=strategy):
                output = geometry_render(self.data, "engine", strategy)
                self.assertTrue(output.strip())
                self.assertNotIn("not found", output.lower())

    def test_alias_resolves_before_rendering(self):
        output = geometry_render(self.data, "处理流程", "tree")
        self.assertIn("输入源", output)
        self.assertIn("处理核心", output)

    def test_leaf_focus_uses_context_and_double_border(self):
        output = geometry_render(self.data, "engine.worker", "minimal")
        self.assertIn("输入源", output)
        self.assertIn("处理核心", output)
        self.assertIn("结果库", output)
        self.assertIn("╔", output)

    def test_state_machine_keeps_scalar_endpoints_whole(self):
        output = geometry_render(self.data, "engine", "statemachine")
        self.assertIn("[raw_input]", output)
        self.assertIn("[parsed]", output)
        self.assertNotIn("[r]\n", output)

    def test_timing_strategies_use_duration_ms(self):
        for strategy in ("hbar_gantt", "waterfall"):
            with self.subTest(strategy=strategy):
                output = geometry_render(self.data, "engine", strategy)
                self.assertIn("10ms", output)
                self.assertIn("20ms", output)
                self.assertIn("总计: 30ms", output)

    def test_blueprint_has_zones_ports_and_exact_edges(self):
        output = geometry_render(self.data, "engine", "blueprint")
        self.assertIn("INBOUND", output)
        self.assertIn("HUB", output)
        self.assertIn("OUTBOUND", output)
        self.assertIn("DATA FLOW / 实际数据流", output)
        self.assertIn("输入源", output)
        self.assertIn("处理核心", output)
        self.assertIn("结果库", output)
        flow_section = output.split("DATA FLOW / 实际数据流", 1)[1]
        flow_lines = [line for line in flow_section.splitlines() if "▶" in line]
        self.assertEqual(len(flow_lines), 2)
        self.assertIn("输入源", flow_lines[0])
        self.assertIn("处理核心", flow_lines[0])
        self.assertIn("处理核心", flow_lines[1])
        self.assertIn("结果库", flow_lines[1])
        self.assertNotIn(".OUT", output)
        self.assertTrue(all(str_width(line) <= 80 for line in output.splitlines()))

    def test_blueprint_prefers_three_explicit_semantic_groups(self):
        self.data["modules"]["engine"]["groups"] = {
            "commands": {"label": "Commands", "modules": ["engine.source"]},
            "authority": {"label": "Authority", "modules": ["engine.worker"]},
            "delivery": {"label": "Delivery", "modules": ["engine.sink"]},
        }
        output = geometry_render(self.data, "engine", "blueprint")
        self.assertIn("COMMANDS", output)
        self.assertIn("AUTHORITY", output)
        self.assertIn("DELIVERY", output)
        self.assertNotIn("INBOUND", output)

    def test_swimlane_uses_lane_labels_from_default_strategy(self):
        engine = self.data["modules"]["engine"]
        engine["render_strategy"] = "swimlane"
        engine["lanes"] = [
            {"id": "pre", "label": "Preflight", "modules": ["engine.source"]},
            {"id": "run", "label": "Execution", "modules": ["engine.worker"]},
            {"id": "post", "label": "Postflight", "modules": ["engine.sink"]},
        ]
        output = geometry_render(self.data, "engine")
        self.assertIn("Preflight", output)
        self.assertIn("Execution", output)
        self.assertIn("Postflight", output)

    def test_panorama_collapses_curated_deep_targets_without_aggregating_descendants(self):
        data = sample_archmap_with_custom_root()
        modules = data["modules"]
        modules["platform"]["children"] = ["domain_a", "domain_b"]
        modules["domain_a"] = {
            "label": "Domain A",
            "type": "engine",
            "parent": "platform",
            "children": ["domain_a.worker"],
            "downstream": ["domain_b.worker"],
        }
        modules["domain_a.worker"] = {
            "label": "A Worker",
            "type": "module",
            "parent": "domain_a",
        }
        modules["domain_b"] = {
            "label": "Domain B",
            "type": "engine",
            "parent": "platform",
            "children": ["domain_b.worker"],
        }
        modules["domain_b.worker"] = {
            "label": "B Worker",
            "type": "module",
            "parent": "domain_b",
            "downstream": ["domain_a.worker"],
        }
        modules["platform"]["edges"] = [
            {
                "from": "domain_a.worker",
                "to": "domain_b.worker",
                "label": "handoff",
            }
        ]

        edges = derive_panorama_edges(data, "platform")
        self.assertEqual(
            [(edge["from"], edge["to"]) for edge in edges],
            [("domain_a", "domain_b")],
        )
        self.assertEqual(edges[0]["count"], 2)
        self.assertFalse(edges[0]["exact"])
        self.assertEqual(edges[0]["label"], "handoff x2")
        output = render_legacy(data, "all")
        self.assertIn('subgraph m_domain_a["Domain A"]', output)
        self.assertIn('m_domain_a_worker["A Worker"]', output)
        self.assertIn('subgraph m_domain_b["Domain B"]', output)
        self.assertIn('m_domain_b_worker["B Worker"]', output)
        self.assertIn("m_domain_a -. handoff x2 .-> m_domain_b", output)
        self.assertNotIn("m_domain_b_worker -->", output)

        compact = render_legacy(data, "all", depth=0)
        self.assertNotIn("m_domain_a_worker", compact)
        self.assertNotIn("m_domain_b_worker", compact)
        self.assertIn('m_domain_a["Domain A"]', compact)

    def test_panorama_depth_progressively_expands_ownership(self):
        data = sample_archmap_with_custom_root()
        modules = data["modules"]
        modules["engine.source"]["children"] = ["engine.source.parser"]
        modules["engine.source.parser"] = {
            "label": "Parser",
            "type": "function",
            "parent": "engine.source",
        }

        default = render_legacy(data, "all")
        self.assertIn('subgraph m_engine["Test Engine"]', default)
        self.assertIn('m_engine_source["输入源"]', default)
        self.assertNotIn("m_engine_source_parser", default)

        expanded = render_legacy(data, "all", depth=2)
        self.assertIn('subgraph m_engine_source["输入源"]', expanded)
        self.assertIn('m_engine_source_parser["Parser"]', expanded)

    def test_panorama_default_renders_visible_boxes_with_internal_topology(self):
        data = sample_archmap_with_custom_root()
        output = render_legacy(data, "all")
        self.assertIn("m_engine_source --> m_engine_worker", output)
        self.assertIn("m_engine_worker --> m_engine_sink", output)

    def test_internal_topology_projects_deep_edges_and_reports_aggregation(self):
        data = sample_archmap_with_custom_root()
        modules = data["modules"]
        modules["engine.source"]["children"] = [
            "engine.source.parser",
            "engine.source.normalizer",
        ]
        modules["engine.worker"]["children"] = ["engine.worker.rule"]
        modules["engine.source.parser"] = {
            "label": "Parser",
            "type": "function",
            "parent": "engine.source",
            "downstream": ["engine.worker.rule"],
        }
        modules["engine.source.normalizer"] = {
            "label": "Normalizer",
            "type": "function",
            "parent": "engine.source",
            "downstream": ["engine.worker.rule"],
        }
        modules["engine.worker.rule"] = {
            "label": "Rule",
            "type": "function",
            "parent": "engine.worker",
            "upstream": ["engine.source.parser", "engine.source.normalizer"],
        }
        modules["engine"]["edges"] = [
            {
                "from": "engine.source",
                "to": "engine.worker",
                "label": "handoff",
            }
        ]

        visible = ["engine", "engine.source", "engine.worker", "engine.sink"]
        edges = derive_visible_internal_edges(data, "platform", visible)
        projected = next(
            edge
            for edge in edges
            if (edge["from"], edge["to"]) == ("engine.source", "engine.worker")
        )
        self.assertEqual(projected["count"], 3)
        self.assertTrue(projected["collapsed"])
        self.assertTrue(projected["exact"])
        self.assertEqual(projected["label"], "handoff x3")

        output = render_legacy(data, "all")
        self.assertIn("m_engine_source -->|handoff x3| m_engine_worker", output)

        expanded = render_legacy(data, "all", depth=2)
        self.assertIn("m_engine_source -->|handoff| m_engine_worker", expanded)
        self.assertIn("m_engine_source_parser --> m_engine_worker_rule", expanded)
        self.assertIn("m_engine_source_normalizer --> m_engine_worker_rule", expanded)
        self.assertNotIn("handoff x3", expanded)

    def test_internal_topology_preserves_opposite_directions(self):
        data = sample_archmap_with_custom_root()
        data["modules"]["engine.worker"]["downstream"] = [
            "engine.sink",
            "engine.source",
        ]
        data["modules"]["engine.source"]["upstream"] = ["engine.worker"]

        output = render_legacy(data, "all")
        self.assertIn("m_engine_source --> m_engine_worker", output)
        self.assertIn("m_engine_worker --> m_engine_source", output)

    def test_deep_only_projection_uses_a_dotted_edge(self):
        data = sample_archmap_with_custom_root()
        modules = data["modules"]
        modules["engine.source"]["children"] = ["engine.source.parser"]
        modules["engine.sink"]["children"] = ["engine.sink.writer"]
        modules["engine.source.parser"] = {
            "label": "Parser",
            "type": "function",
            "parent": "engine.source",
            "downstream": ["engine.sink.writer"],
        }
        modules["engine.sink.writer"] = {
            "label": "Writer",
            "type": "function",
            "parent": "engine.sink",
            "upstream": ["engine.source.parser"],
        }

        output = render_legacy(data, "all")
        self.assertIn("m_engine_source -.-> m_engine_sink", output)

    def test_internal_topology_drops_same_box_and_cross_domain_relations(self):
        data = sample_archmap_with_custom_root()
        modules = data["modules"]
        modules["platform"]["children"] = ["domain_a", "domain_b"]
        modules["domain_a"] = {
            "label": "Domain A",
            "type": "engine",
            "parent": "platform",
            "children": ["domain_a.one", "domain_a.two"],
        }
        modules["domain_a.one"] = {
            "label": "A One",
            "type": "module",
            "parent": "domain_a",
            "children": ["domain_a.one.deep"],
        }
        modules["domain_a.one.deep"] = {
            "label": "A Deep",
            "type": "function",
            "parent": "domain_a.one",
            "downstream": ["domain_a.one", "domain_b.worker"],
        }
        modules["domain_a.two"] = {
            "label": "A Two",
            "type": "module",
            "parent": "domain_a",
        }
        modules["domain_b"] = {
            "label": "Domain B",
            "type": "engine",
            "parent": "platform",
            "children": ["domain_b.worker"],
        }
        modules["domain_b.worker"] = {
            "label": "B Worker",
            "type": "module",
            "parent": "domain_b",
        }

        visible = [
            "domain_a",
            "domain_a.one",
            "domain_a.two",
            "domain_b",
            "domain_b.worker",
        ]
        self.assertEqual(
            derive_visible_internal_edges(data, "platform", visible),
            [],
        )

    def test_panorama_honors_layout_and_explicit_groups(self):
        data = sample_archmap_with_custom_root()
        root = data["modules"]["platform"]
        root["layout"] = "LR"
        root["groups"] = {
            "execution": {"label": "Execution", "modules": ["engine"]},
        }
        output = render_legacy(data, "platform")
        self.assertTrue(output.startswith("graph LR\n"))
        self.assertIn('subgraph g_execution["Execution"]', output)

    def test_panorama_escapes_labels_and_uses_safe_prefixed_ids(self):
        data = sample_archmap_with_custom_root()
        modules = data["modules"]
        modules["engine.source"]["label"] = 'Input "quoted" <raw>\nnext'
        modules["platform"]["edges"] = [
            {
                "from": "engine.source",
                "to": "engine.worker",
                "label": "raw|safe<&",
            }
        ]

        output = render_legacy(data, "all")
        self.assertIn('m_engine_source["Input &quot;quoted&quot; &lt;raw&gt;<br/>next"]', output)
        self.assertIn("raw&#124;safe&lt;&amp;", output)

    def test_panorama_disambiguates_colliding_mermaid_ids(self):
        data = sample_archmap_with_custom_root()
        modules = data["modules"]
        modules["platform"]["children"] = ["a.b", "a-b"]
        modules["a.b"] = {
            "label": "Dot",
            "type": "module",
            "parent": "platform",
            "downstream": ["a-b"],
        }
        modules["a-b"] = {
            "label": "Dash",
            "type": "module",
            "parent": "platform",
            "upstream": ["a.b"],
        }

        output = render_legacy(data, "all")
        dot_line = next(line for line in output.splitlines() if '["Dot"]' in line)
        dash_line = next(line for line in output.splitlines() if '["Dash"]' in line)
        dot_id = dot_line.strip().split("[", 1)[0]
        dash_id = dash_line.strip().split("[", 1)[0]
        self.assertNotEqual(dot_id, dash_id)
        self.assertIn(f"{dot_id} --> {dash_id}", output)

    def test_panorama_rejects_an_ownership_cycle_during_render(self):
        data = sample_archmap_with_custom_root()
        data["modules"]["engine.source"]["children"] = ["engine"]
        with self.assertRaisesRegex(RenderError, "Ownership cycle"):
            render_legacy(data, "all", depth=2)

    def test_onion_uses_graph_metric_labels_not_architectural_claims(self):
        output = geometry_render(self.data, "engine", "onion")
        self.assertIn("高入度", output)
        self.assertNotIn("内核", output)

    def test_blueprint_preserves_isolated_modules_on_support_rail(self):
        self.data["modules"]["engine"]["children"].append("engine.monitor")
        self.data["modules"]["engine.monitor"] = {
            "label": "健康探针",
            "type": "module",
            "parent": "engine",
        }
        output = geometry_render(self.data, "engine", "blueprint")
        self.assertIn("SUPPORT", output)
        self.assertIn("健康探针", output)

    def test_terminal_overview_fits_any_requested_width(self):
        data = sample_archmap_with_custom_root()
        for width in (80, 99, 100, 120, 135, 136, 160):
            with self.subTest(width=width):
                output = render_terminal(
                    data,
                    "all",
                    width=width,
                    color="never",
                    charset="unicode",
                )
                self.assertIn("VERTICAL LAYERED BUS TOPOLOGY", output)
                self.assertIn("ISOLATED", output)
                self.assertNotIn("L0", output)  # no inter-domain routes at depth 1
                self.assertIn("OWNERSHIP TREE", output)
                self.assertIn("LEGEND", output)
                self.assertIn("▾N=expandable", output)
                self.assertIn("╔═ ═╗ engine", output)
                self.assertIn("输入源", output)
                self.assertTrue(output.splitlines()[1].endswith("╗"), output.splitlines()[1])
                self.assertTrue(
                    all(str_width(line) <= width for line in output.splitlines()),
                    output,
                )

    def test_terminal_ascii_uses_structural_fallbacks_and_leaf_context(self):
        output = render_terminal(
            self.data,
            "engine.worker",
            width=80,
            color="never",
            charset="ascii",
        )
        self.assertIn("VERTICAL LAYERED BUS TOPOLOGY", output)
        self.assertIn("[DEP]", output)
        self.assertIn("+--[DEP]", output)
        self.assertIn("v", output)
        self.assertIn("+----------------", output)
        for unicode_glyph in "╔╗┏┓┌┐◇╌─┄▶◀●◆○▾·…→▼│┆↕":
            self.assertNotIn(unicode_glyph, output)

    def test_lane_connectors_terminate_on_target_frames(self):
        """Route lanes drop a vertical connector onto the target frame —
        the arrow column must not hang in the void."""
        data = {
            "schema": "archiscope/1.0",
            "modules": {
                "root": {"label": "R", "type": "root", "children": ["a", "b"]},
                "a": {"label": "甲", "type": "module", "parent": "root", "downstream": ["b"]},
                "b": {"label": "乙", "type": "module", "parent": "root", "upstream": ["a"]},
            },
        }
        output = render_terminal(data, "all", width=80, color="never", charset="unicode")
        lines = output.splitlines()
        lane = next(line for line in lines if "▼" in line)
        idx = lines.index(lane)
        # connector runs through the target layer label row and terminates
        # on the frame top with a tee
        self.assertIn("│", lines[idx + 1])
        self.assertIn("┴", lines[idx + 2])

    def test_terminal_ansi_is_a_post_layout_invariant(self):
        data = sample_archmap_with_custom_root()
        plain = render_terminal(
            data,
            "all",
            width=100,
            color="never",
            charset="unicode",
        )
        colored = render_terminal(
            data,
            "all",
            width=100,
            color="always",
            charset="unicode",
            env={"NO_COLOR": "1", "TERM": "dumb"},
        )
        self.assertIn("\x1b[", colored)
        self.assertEqual(strip_ansi(colored), plain)
        self.assertEqual(colored.count("\x1b["), 2 * colored.count("\x1b[0m"))

        auto_cases = (
            ({"NO_COLOR": ""}, True),
            ({"TERM": "dumb"}, True),
            ({"TERM": "xterm-256color"}, False),
        )
        for environment, tty in auto_cases:
            with self.subTest(environment=environment, tty=tty):
                auto = render_terminal(
                    data,
                    "all",
                    width=80,
                    color="auto",
                    charset="unicode",
                    stream=StringIO(),
                    isatty=tty,
                    env=environment,
                )
                self.assertNotIn("\x1b", auto)

        tty_auto = render_terminal(
            data,
            "all",
            width=80,
            color="auto",
            charset="unicode",
            stream=StringIO(),
            isatty=True,
            env={"TERM": "xterm-256color"},
        )
        self.assertIn("\x1b[", tty_auto)

    def test_terminal_parallel_kinds_projection_and_bidirectional_merge(self):
        data = sample_archmap_with_custom_root()
        modules = data["modules"]
        modules["engine.source"]["children"] = ["engine.source.parser"]
        modules["engine.worker"]["children"] = ["engine.worker.rule"]
        modules["engine.source.parser"] = {
            "label": "Parser",
            "type": "function",
            "parent": "engine.source",
            "downstream": ["engine.worker.rule"],
        }
        modules["engine.worker.rule"] = {
            "label": "Rule",
            "type": "rule",
            "parent": "engine.worker",
            "downstream": ["engine.source.parser"],
        }
        modules["engine"]["edges"] = [
            {"from": "engine.source", "to": "engine.worker", "kind": "data"},
            {"from": "engine.source", "to": "engine.worker", "kind": "command"},
            {"from": "engine.worker", "to": "engine.source", "kind": "data"},
            {
                "from": "engine.source.parser",
                "to": "engine.worker.rule",
                "kind": "data",
            },
            {
                "from": "engine.worker.rule",
                "to": "engine.source.parser",
                "kind": "command",
            },
        ]

        visible = [
            "engine",
            "engine.source",
            "engine.worker",
            "engine.sink",
        ]
        edges = derive_terminal_edges(data, "platform", visible)
        pair_edges = [
            edge
            for edge in edges
            if {edge.source, edge.target} == {"engine.source", "engine.worker"}
        ]
        direct_data = next(
            edge for edge in pair_edges if edge.kind == "data" and not edge.projected
        )
        projected_data = next(edge for edge in pair_edges if edge.kind == "data" and edge.projected)
        direct_command = next(
            edge for edge in pair_edges if edge.kind == "command" and not edge.projected
        )
        projected_command = next(
            edge for edge in pair_edges if edge.kind == "command" and edge.projected
        )
        self.assertTrue(direct_data.bidirectional)
        self.assertFalse(projected_data.bidirectional)
        self.assertFalse(direct_command.bidirectional)
        self.assertFalse(projected_command.bidirectional)

    def test_terminal_root_cross_domain_relations_use_only_curated_origins(self):
        data = {
            "schema": "archiscope/1.0",
            "modules": {
                "root": {
                    "label": "Root",
                    "type": "root",
                    "children": ["a", "b", "c"],
                },
                "a": {
                    "label": "A",
                    "type": "engine",
                    "parent": "root",
                    "children": ["a.worker"],
                    "downstream": ["b", "b.deep"],
                },
                "a.worker": {
                    "label": "A Worker",
                    "type": "module",
                    "parent": "a",
                    "downstream": ["c.worker"],
                },
                "b": {
                    "label": "B",
                    "type": "engine",
                    "parent": "root",
                    "children": ["b.deep"],
                    "upstream": ["a"],
                    "downstream": ["c"],
                },
                "b.deep": {
                    "label": "B Deep",
                    "type": "module",
                    "parent": "b",
                },
                "c": {
                    "label": "C",
                    "type": "engine",
                    "parent": "root",
                    "children": ["c.worker"],
                    "upstream": ["b"],
                },
                "c.worker": {
                    "label": "C Worker",
                    "type": "module",
                    "parent": "c",
                    "upstream": ["a.worker"],
                },
            },
        }
        visible = ["a", "a.worker", "b", "b.deep", "c", "c.worker"]
        overlay = {
            "modules": {},
            "edges": [
                {
                    "from": "a",
                    "to": "b.deep",
                    "kind": "data",
                }
            ],
        }
        edges = derive_terminal_edges(data, "root", visible, overlay=overlay)
        domains = {"a", "b", "c"}
        cross = [edge for edge in edges if edge.source in domains and edge.target in domains]
        directions = {(edge.source, edge.target) for edge in cross}
        directions.update((edge.target, edge.source) for edge in cross if edge.bidirectional)
        self.assertEqual(directions, {("a", "b"), ("b", "c")})
        self.assertEqual(sum(edge.canonical_count for edge in cross), 3)
        self.assertNotIn(("a", "c"), directions)
        projected_data = next(edge for edge in cross if edge.kind == "data")
        self.assertTrue(projected_data.projected)
        self.assertEqual(projected_data.canonical_count, 1)

    def test_terminal_overlay_cannot_change_topology(self):
        overlay = {
            "modules": {},
            "edges": [
                {
                    "from": "engine.source",
                    "to": "engine.sink",
                    "kind": "data",
                }
            ],
        }
        with self.assertRaisesRegex(TerminalRenderError, "not an existing canonical relation"):
            render_terminal(
                self.data,
                "root",
                semantic_overlay=overlay,
                width=80,
                color="never",
                charset="unicode",
            )

    def test_terminal_project_extensions_keep_their_token_and_use_registered_family(self):
        self.data["semantics"] = {
            "features": {"ingestion": {"family": "boundary"}},
            "relation_kinds": {"x-snapshot": {"family": "reference"}},
        }
        self.data["modules"]["engine.source"]["feature"] = "ingestion"
        self.data["modules"]["engine"]["edges"] = [
            {
                "from": "engine.source",
                "to": "engine.worker",
                "kind": "x-snapshot",
                "payload_type": "Snapshot",
            }
        ]
        output = render_terminal(
            self.data,
            "engine",
            width=100,
            color="never",
            charset="unicode",
        )
        self.assertIn("[INGESTION]", output)
        self.assertIn("[REF]", output)
        self.assertIn("x-snapshot", output)
        self.assertIn("Snapshot", output)


if __name__ == "__main__":
    unittest.main()
