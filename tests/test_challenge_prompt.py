"""Regress Japanese initial prompt disambiguation and challenge screen detection."""

import unittest
from pathlib import Path

import cv2
import numpy as np

import auto_bot as bot


class ChallengePromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_path = Path(__file__).parent / "fixtures" / "challenge-ja-1600.png"
        cls.frame = cv2.imread(str(fixture_path))
        if cls.frame is None:
            raise AssertionError(f"Missing Japanese challenge screenshot: {fixture_path}")

    def setUp(self):
        bot._TEMPLATE_ROI_CACHE.clear()

    def tearDown(self):
        bot._TEMPLATE_ROI_CACHE.clear()

    def test_initial_japanese_caption_beats_overlapping_success_text(self):
        template = cv2.imread(bot.resource_path("templates", "icons", "ja", "success_ja.png"), 0)
        gray = cv2.cvtColor(self.frame, cv2.COLOR_BGR2GRAY)
        old_score = cv2.minMaxLoc(cv2.matchTemplate(gray, template, cv2.TM_CCOEFF_NORMED))[1]
        self.assertGreaterEqual(old_score, 0.85)
        self.assertEqual(bot.detect_game_state(self.frame), "ASK_CHALLENGE")
        self.assertFalse(bot.is_success_prompt(self.frame))

    def test_next_reward_is_1600(self):
        self.assertEqual(bot.read_challenge_payout(self.frame, bot.REWARD_ZONE), 1600)

    def test_initial_and_success_caption_competition_in_existing_game_languages(self):
        # Composite crops exercise text overlap across all bundled alphabets.
        for language in ("en", "tw", "ja", "zh"):
            for kind in ("chance", "success"):
                with self.subTest(language=language, kind=kind):
                    bot._TEMPLATE_ROI_CACHE.clear()
                    frame = np.full((1080, 1920, 3), (220, 145, 190), np.uint8)
                    template = cv2.imread(bot.resource_path("templates", "icons", language, f"{kind}_{language}.png"))
                    h, w = template.shape[:2]
                    frame[350 : 350 + h, 500 : 500 + w] = template
                    self.assertEqual(bot.is_success_prompt(frame), kind == "success")


if __name__ == "__main__":
    unittest.main()
