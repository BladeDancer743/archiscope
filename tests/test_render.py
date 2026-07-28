import unittest

from src.render import derive_edges, geometry_render
from src.render.geometry.draw.grid import str_width
from src.strategies import PUBLIC_STRATEGIES
from tests.helpers import sample_archmap


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
        self.assertIn("CONTROL", output)
        self.assertIn("CORE", output)
        self.assertIn("PROCESS", output)
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


if __name__ == "__main__":
    unittest.main()
