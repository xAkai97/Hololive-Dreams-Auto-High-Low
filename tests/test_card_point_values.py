"""Tests for get_card_point_value rank normalization and unparseable values (B12)."""
import sys
from pathlib import Path
import unittest
from types import SimpleNamespace

SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    import numpy
    import cv2
    from auto_bot import get_card_point_value, JOKER_ID
    HAVE_DEPS = True
except ImportError:
    HAVE_DEPS = False
    get_card_point_value = None
    JOKER_ID = 99


class TestGetCardPointValue(unittest.TestCase):
    def setUp(self):
        if not HAVE_DEPS:
            self.skipTest("numpy / cv2 / ddddocr not installed")
    def test_joker_returns_zero(self):
        card = SimpleNamespace(card_id=JOKER_ID, rank="JOKER")
        self.assertEqual(get_card_point_value(card), 0)

    def test_numeric_ranks(self):
        for num in range(2, 11):
            card = SimpleNamespace(card_id=1, rank=str(num))
            self.assertEqual(get_card_point_value(card), num)

    def test_face_cards_and_aces(self):
        mapping = {
            "J": 11, "JACK": 11,
            "Q": 12, "QUEEN": 12,
            "K": 13, "KING": 13,
            "A": 14, "ACE": 14, "1": 14,
        }
        for rank_str, expected in mapping.items():
            card = SimpleNamespace(card_id=1, rank=rank_str)
            self.assertEqual(get_card_point_value(card), expected)

    def test_dotted_rank_strings(self):
        card = SimpleNamespace(card_id=1, rank="Rank.ACE")
        self.assertEqual(get_card_point_value(card), 14)
        card2 = SimpleNamespace(card_id=1, rank="Card.TEN")
        self.assertEqual(get_card_point_value(card2), 10)

    def test_unparseable_rank_returns_none(self):
        for invalid in ["UNKNOWN", "??", "XYZ", "", "99"]:
            card = SimpleNamespace(card_id=99, rank=invalid)
            self.assertIsNone(get_card_point_value(card))


class TestPokerEngine(unittest.TestCase):
    def test_verify_engine(self):
        try:
            import poker_core
            poker_core.verify_engine()
        except ImportError:
            self.skipTest("poker_core / numba not installed in this environment")


class TestGameDateReset(unittest.TestCase):
    def test_eastern_rollover_boundaries(self):
        if not HAVE_DEPS:
            self.skipTest("auto_bot dependencies not installed")
        import datetime
        from auto_bot import get_game_date

        # EDT (Daylight Saving Time, UTC-4)
        # 15:59:59 EDT -> belongs to previous game day
        t1 = datetime.datetime(2026, 10, 3, 19, 59, 59, tzinfo=datetime.timezone.utc)
        self.assertEqual(get_game_date(t1), "2026-10-02")

        # 16:00:00 EDT -> new day starts at 4:00 PM EST
        t2 = datetime.datetime(2026, 10, 3, 20, 0, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(get_game_date(t2), "2026-10-03")

        # EST (Standard Time, UTC-5)
        # 15:59:59 EST -> belongs to previous game day
        t3 = datetime.datetime(2026, 1, 15, 20, 59, 59, tzinfo=datetime.timezone.utc)
        self.assertEqual(get_game_date(t3), "2026-01-14")

        # 16:00:00 EST -> new day starts
        t4 = datetime.datetime(2026, 1, 15, 21, 0, 0, tzinfo=datetime.timezone.utc)
        self.assertEqual(get_game_date(t4), "2026-01-15")

    def test_auto_play_loop_start_bet_date_handling(self):
        import auto_bot
        import contextlib
        import io
        from unittest.mock import patch
        with patch.object(auto_bot, "capture_game_window") as mock_cap, \
             patch.object(auto_bot, "detect_game_state") as mock_state, \
             patch.object(auto_bot, "find_and_click_icon", return_value=False), \
             patch.object(auto_bot, "load_config", return_value={"debug_logging": False}), \
             patch.object(auto_bot, "load_daily_data", return_value=(0, 0)), \
             contextlib.redirect_stdout(io.StringIO()):

            mock_cap.return_value = (numpy.zeros((100, 100, 3), dtype=numpy.uint8), 0, 0)
            def fake_state(img):
                auto_bot.bot_running = False
                return "START_BET"

            mock_state.side_effect = fake_state
            auto_bot.bot_running = True
            try:
                auto_bot.auto_play_loop()
            except UnboundLocalError:
                self.fail("auto_play_loop raised UnboundLocalError on current_game_date")
            finally:
                auto_bot.bot_running = False
                auto_bot._debug_logging_enabled = None


if __name__ == "__main__":
    unittest.main()
