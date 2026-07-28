import unittest

from archiscope.render.geometry.draw.grid import CharGrid, pad_str, str_width


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


if __name__ == "__main__":
    unittest.main()
