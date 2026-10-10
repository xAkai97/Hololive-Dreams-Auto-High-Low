import unittest
import numpy as np
from src.auto_bot import get_currently_held_indices


class TestHoldDetection(unittest.TestCase):
    def setUp(self):
        # 5 standard reference card boxes across 1080p width
        # (x, y, w, h)
        self.baseline_y = 350
        self.rects = [
            (210, self.baseline_y, 250, 360),
            (510, self.baseline_y, 250, 360),
            (810, self.baseline_y, 250, 360),
            (1110, self.baseline_y, 250, 360),
            (1410, self.baseline_y, 250, 360),
        ]

    def test_all_cards_unheld_at_baseline(self):
        held = get_currently_held_indices(self.rects, screen_height=1080, img=None)
        self.assertEqual(held, set())

    def test_downward_displacement_held_indices(self):
        # Slots 1 and 3 shifted downward by 35px
        shifted_rects = list(self.rects)
        shifted_rects[1] = (510, self.baseline_y + 35, 250, 360)
        shifted_rects[3] = (1110, self.baseline_y + 35, 250, 360)

        held = get_currently_held_indices(shifted_rects, screen_height=1080, img=None)
        self.assertEqual(held, {1, 3})

    def test_all_cards_shifted_downward(self):
        # All 5 cards shifted downward (e.g. 5-card hold)
        shifted_rects = [(x, self.baseline_y + 35, w, h) for (x, _, w, h) in self.rects]
        held = get_currently_held_indices(shifted_rects, screen_height=1080, img=None)
        self.assertEqual(held, {0, 1, 2, 3, 4})

    def test_720p_scaled_displacement(self):
        # Scale to 720p height: baseline_y = 233, gap = ~23px
        base_720 = int(350 * 720 / 1080)
        rects_720 = [(int(x * 720 / 1080), base_720, 166, 240) for (x, _, _, _) in self.rects]
        # Shift slots 0 and 4 down by 25px
        rects_720[0] = (rects_720[0][0], base_720 + 25, 166, 240)
        rects_720[4] = (rects_720[4][0], base_720 + 25, 166, 240)

        held = get_currently_held_indices(rects_720, screen_height=720, img=None)
        self.assertEqual(held, {0, 4})


if __name__ == "__main__":
    unittest.main()
