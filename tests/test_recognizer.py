"""Tests for CardRecognizer template loading, mask preprocessing, and scoring."""

import sys
import unittest
from pathlib import Path

import cv2
import numpy as np

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
ROOT_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = ROOT_DIR / "templates"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from recognizer import CardRecognizer


class TestRecognizerComprehensive(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = CardRecognizer(TEMPLATE_DIR)

    def test_border_noise_removal(self):
        # A mask with small noise at (0, 0) and main component in the center
        mask = np.zeros((64, 64), dtype=np.uint8)
        # Small component at (0, 0)
        mask[0:3, 0:3] = 255
        # Large component in center
        mask[20:50, 20:50] = 255
        cleaned = CardRecognizer._remove_top_left_border_noise(mask)
        self.assertEqual(cleaned[0, 0], 0)
        self.assertEqual(cleaned[30, 30], 255)

    def test_normalize(self):
        # Empty mask
        empty = np.zeros((64, 64), dtype=np.uint8)
        norm_empty = CardRecognizer._normalize(empty, size=64)
        self.assertEqual(norm_empty.shape, (64, 64))
        self.assertEqual(norm_empty.max(), 0)

        # Normal component
        box = np.zeros((30, 20), dtype=np.uint8)
        box[5:25, 5:15] = 255
        norm_box = CardRecognizer._normalize(box, size=64, largest_only=True)
        self.assertEqual(norm_box.shape, (64, 64))
        self.assertGreater(norm_box.max(), 0)

    def test_selection_phase_score_blank_and_purple(self):
        # Blank black screen
        blank = np.zeros((1080, 1920, 3), dtype=np.uint8)
        valid, score, _ = CardRecognizer.selection_phase_score(blank)
        self.assertFalse(valid)
        self.assertEqual(score, 0.0)

        # Draw a synthetic purple outlined action button
        h, w = 1080, 1920
        synthetic = np.zeros((h, w, 3), dtype=np.uint8)
        x0, x1 = int(0.39 * w), int(0.61 * w)
        y0, y1 = int(0.755 * h), int(0.855 * h)
        # BGR purple: (180, 50, 150)
        cv2.rectangle(synthetic, (x0 + 10, y0 + 10), (x1 - 10, y1 - 10), (180, 50, 150), -1)
        # White border
        cv2.rectangle(synthetic, (x0 + 5, y0 + 5), (x1 - 5, y1 - 5), (255, 255, 255), 4)

        valid, score, _details = CardRecognizer.selection_phase_score(synthetic)
        self.assertIsInstance(valid, (bool, np.bool_))
        self.assertIsInstance(score, float)

    def test_fallback_rects_and_hold_score(self):
        rects = CardRecognizer._fallback_rects(1920, 1080)
        self.assertEqual(len(rects), 5)

        # White face-up card screen vs black screen
        white_screen = np.full((1080, 1920, 3), 240, dtype=np.uint8)
        valid, avg, _scores = self.rec.hold_screen_score(white_screen, rects)
        self.assertTrue(valid)
        self.assertGreater(avg, 0.6)

    def test_find_card_rects(self):
        # On white screen fallback should succeed
        white_screen = np.full((1080, 1920, 3), 240, dtype=np.uint8)
        rects = self.rec.find_card_rects(white_screen)
        self.assertEqual(len(rects), 5)


if __name__ == "__main__":
    unittest.main()
