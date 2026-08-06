"""Verify/correct geometry pipeline tests — rules and fixers.

Regression guards for the geometry quality loop:
- G4 frame closure must use inclusive corner cells (Rect.right/bottom are
  exclusive, one past the last cell).
- correct() must never destroy a healthy layout (it used to full-rebuild on
  false-critical violations and drop nested group frames).
"""

import unittest

from archiscope.render import geometry_render
from archiscope.render.ansi import ANSI_COLORS, THEMES, resolve_theme, strip_ansi
from archiscope.render.geometry.correct.engine import correct
from archiscope.render.geometry.draw.grid import CharGrid, str_width
from archiscope.render.geometry.verify.engine import verify
from archiscope.render.geometry.verify.rules import VerifyContext

from tests.helpers import sample_archmap


def _ctx(grid, boxes, edges=None, modules=None, groups=None, width=80):
    return VerifyContext(
        grid=grid,
        boxes=boxes,
        edges=edges or [],
        groups=groups or {},
        modules=modules or {},
        terminal_width=width,
        focus=None,
        group_labels={},
    )


class FrameClosureTests(unittest.TestCase):
    def test_intact_box_frames_are_not_flagged(self):
        """G4 checks corner characters at x+w-1/y+h-1, not the exclusive right/bottom."""
        grid = CharGrid(24, 8)
        grid.draw_rect(2, 1, 10, 4)
        boxes = {"a": grid.draw_rect(13, 1, 6, 4)}
        rule_ids = {v.rule_id for v in verify(_ctx(grid, boxes))}
        self.assertNotIn("G4_frame_closure", rule_ids)

    def test_broken_corner_is_flagged(self):
        grid = CharGrid(20, 8)
        rect = grid.draw_rect(2, 1, 10, 4)
        grid.put(rect.x, rect.y, " ")  # erase the top-left corner
        rule_ids = {v.rule_id for v in verify(_ctx(grid, {"a": rect}))}
        self.assertIn("G4_frame_closure", rule_ids)


class CorrectionPipelineTests(unittest.TestCase):
    def test_correct_is_noop_on_clean_layout(self):
        grid = CharGrid(30, 10)
        boxes = {
            "a": grid.draw_rect(2, 2, 8, 4),
            "b": grid.draw_rect(12, 2, 8, 4),
        }
        result = correct(_ctx(grid, boxes))
        self.assertEqual(result.applied, [])
        self.assertEqual(result.grid.render(), grid.render())

    def test_overlapping_boxes_trigger_full_relayout_rebuild(self):
        """G0_overlap is CRITICAL, so the shift fixer never sees it; the engine
        falls through to the relayout last resort, which rebuilds a clean layout."""
        grid = CharGrid(30, 10)
        boxes = {
            "a": grid.draw_rect(2, 2, 8, 4),
            "b": grid.draw_rect(6, 3, 8, 4),  # overlaps a
        }
        modules = {"a": {"label": "模块A"}, "b": {"label": "模块B"}}
        result = correct(_ctx(grid, boxes, modules=modules))
        self.assertEqual(result.applied, ["relayout: full rebuild"])
        self.assertFalse(result.needs_relayout)
        self.assertFalse(result.boxes["a"].overlaps(result.boxes["b"]))
        self.assertIn("模块A", result.grid.render())
        self.assertIn("模块B", result.grid.render())

    def test_grouped_render_keeps_group_frame(self):
        """The verify/correct loop must not destroy the nested group frame.

        Regression: G4 corner math used to flag every member box as a broken
        frame (CRITICAL), which sent correct() into the full-relayout path and
        rebuilt the diagram without its group boxes.
        """
        data = sample_archmap()
        output = geometry_render(data, "engine", "grouped")
        self.assertIn("╔", output)  # double-bordered group box survives
        for label in ("输入源", "处理核心", "结果库"):
            self.assertIn(label, output)


class ColorRenderTests(unittest.TestCase):
    def test_render_ansi_preserves_geometry(self):
        """ANSI colors are an overlay: stripping them yields the plain render."""
        grid = CharGrid(24, 8)
        grid.draw_rect(1, 0, 8, 4, color="engine")
        grid.draw_label(2, 1, 6, "处理核心", color="heading")
        grid.draw_arrow_h(11, 20, 2, color="edge")
        colored = grid.render_ansi(ANSI_COLORS)
        self.assertIn("\x1b[", colored)
        self.assertEqual(strip_ansi(colored), grid.render())

    def test_grouped_colored_output_matches_plain_geometry(self):
        data = sample_archmap()
        colored = geometry_render(data, "engine", "grouped", color="always")
        plain = geometry_render(data, "engine", "grouped", color="never")
        self.assertIn("\x1b[", colored)
        self.assertEqual(strip_ansi(colored), plain)

    def test_heat_matrix_hotspot_bars_are_colored(self):
        data = sample_archmap()
        colored = geometry_render(data, "engine", "heat_matrix", color="always")
        self.assertIn("\x1b[", colored)
        self.assertEqual(
            strip_ansi(colored),
            geometry_render(data, "engine", "heat_matrix", color="never"),
        )

    def test_every_theme_preserves_geometry(self):
        data = sample_archmap()
        plain = geometry_render(data, "engine", "grouped", color="never")
        for name in THEMES:
            with self.subTest(theme=name):
                colored = geometry_render(
                    data, "engine", "grouped", color="always", theme=name
                )
                self.assertIn("\x1b[", colored)
                self.assertEqual(strip_ansi(colored), plain)
                # themes differ from each other in at least the group frame
                if name != "default":
                    default = geometry_render(
                        data, "engine", "grouped", color="always", theme="default"
                    )
                    self.assertNotEqual(colored, default)

    def test_unknown_theme_raises(self):
        from archiscope.render.ansi import TerminalRenderError

        with self.assertRaises(TerminalRenderError):
            resolve_theme("no-such-theme")

    def test_grouped_rows_use_at_most_two_color_segments(self):
        """Rows with 3+ ANSI color switches mis-align in some terminal
        renderers (CJK-aware width bugs); grouped rows must stay compact —
        the group frame shares its members' color instead of alternating."""
        import re

        data = sample_archmap()
        colored = geometry_render(data, "engine", "grouped", color="always")
        for line in colored.splitlines():
            segments = len(re.findall(r"\x1b\[(?:1;)?38;5;\d+m", line))
            self.assertLessEqual(segments, 2, line[:80])


class MultiColumnAlignmentTests(unittest.TestCase):
    @staticmethod
    def _char_at_display_column(line: str, column: int) -> str | None:
        """The character occupying a display column (CJK occupies two)."""
        width = 0
        for ch in line:
            if width == column:
                return ch
            width += str_width(ch)
            if width > column:
                return None
        return None

    def test_cards_second_column_borders_align_with_cjk_labels(self):
        """Multi-column card layout must track display columns, not Python
        character counts — CJK labels are 2 cells per character."""
        data = sample_archmap()
        output = geometry_render(data, "engine", "cards")
        lines = output.splitlines()
        top = next(line for line in lines if line.count("┌") == 2)
        title = lines[lines.index(top) + 1]
        second_top = str_width(top[: top.find("┌", top.find("┌") + 1)])
        # the second card's left border must sit on the same display column
        # in the title row as in the top border row
        self.assertEqual(self._char_at_display_column(title, second_top), "│")

    def test_class_diagram_second_column_borders_align_with_cjk_labels(self):
        data = sample_archmap()
        output = geometry_render(data, "engine", "class_diagram")
        lines = output.splitlines()
        top = next(line for line in lines if line.count("┌") == 2)
        title = lines[lines.index(top) + 1]
        second_top = str_width(top[: top.find("┌", top.find("┌") + 1)])
        self.assertEqual(self._char_at_display_column(title, second_top), "│")


if __name__ == "__main__":
    unittest.main()
