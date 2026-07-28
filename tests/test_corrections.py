import unittest

from archiscope.render.geometry.correct.resize import apply_resize
from archiscope.render.geometry.correct.shift import apply_shift
from archiscope.render.geometry.draw.grid import CharGrid, Rect


class CorrectionTests(unittest.TestCase):
    def test_shift_grows_grid_to_fit_moved_box(self):
        grid = CharGrid(4, 4)
        boxes = {"module": Rect(1, 1, 2, 2)}

        apply_shift(
            grid,
            boxes,
            {"module": {"dx": 4, "dy": 3}},
        )

        rect = boxes["module"]
        self.assertGreaterEqual(grid.width, rect.right + 1)
        self.assertGreaterEqual(grid.height, rect.bottom + 1)

    def test_resize_grows_grid_to_fit_larger_box(self):
        grid = CharGrid(4, 4)
        boxes = {"module": Rect(1, 1, 2, 2)}

        apply_resize(
            grid,
            boxes,
            {"module": {"dw": 5, "dh": 4}},
        )

        rect = boxes["module"]
        self.assertGreaterEqual(grid.width, rect.right + 1)
        self.assertGreaterEqual(grid.height, rect.bottom + 1)
