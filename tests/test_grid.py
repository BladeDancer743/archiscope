import unittest

from archiscope.render.geometry.draw.grid import CharGrid, pad_str, str_width, truncate_str


class GridTests(unittest.TestCase):
    def test_cjk_cells_preserve_display_columns(self):
        grid = CharGrid(5, 1)
        grid.put_str(0, 0, "中A")
        self.assertEqual(grid.get(0, 0), "中")
        self.assertEqual(grid.get(1, 0), "")
        self.assertEqual(grid.get(2, 0), "A")
        self.assertEqual(str_width(grid.render().rstrip()), 3)

    def test_overwriting_wide_character_tail_clears_head(self):
        grid = CharGrid(5, 1)
        grid.put(0, 0, "中")
        grid.put(1, 0, "B")
        self.assertEqual(grid.get(0, 0), " ")
        self.assertEqual(grid.get(1, 0), "B")

    def test_left_facing_arrow_points_at_destination(self):
        grid = CharGrid(7, 1)
        grid.draw_arrow_h(6, 1, 0)
        self.assertEqual(grid.get(1, 0), "◀")
        self.assertNotEqual(grid.get(6, 0), "▶")

    def test_padding_never_exceeds_requested_display_width(self):
        value = pad_str("中文标签", 5)
        self.assertLessEqual(str_width(value), 5)

    def test_width_ignores_ansi_and_zero_width_combining_marks(self):
        self.assertEqual(str_width("e\N{COMBINING ACUTE ACCENT}"), 1)
        self.assertEqual(str_width("\x1b[38;5;33m中文\x1b[0m"), 4)

        grid = CharGrid(3, 1)
        grid.put_str(0, 0, "e\N{COMBINING ACUTE ACCENT}X")
        self.assertEqual(grid.get(0, 0), "e\N{COMBINING ACUTE ACCENT}")
        self.assertEqual(grid.get(1, 0), "X")
        self.assertEqual(str_width(grid.render()), 2)

    def test_zero_width_truncation_emits_no_suffix(self):
        self.assertEqual(truncate_str("中文", 0), "")

    def test_render_drops_trailing_blank_rows(self):
        grid = CharGrid(10, 8)
        grid.draw_rect(1, 0, 6, 3)
        rendered = grid.render()
        self.assertEqual(len(rendered.splitlines()), 3)  # only the box rows remain
        self.assertEqual(rendered.splitlines()[-1].strip(), "└────┘")


if __name__ == "__main__":
    unittest.main()
