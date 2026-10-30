import unittest
from unittest.mock import MagicMock, patch
import contextlib
import io
import numpy as np

import auto_bot
from auto_bot import (
    BotSessionState,
    STATE_HANDLERS,
    handle_tap_to_proceed,
    handle_start_bet,
    handle_hold_cards,
)


class TestStateMachineHandlers(unittest.TestCase):
    def setUp(self):
        self._patchers = [
            patch.object(auto_bot, "save_daily_data"),
            patch.object(auto_bot, "save_pending_cashout"),
            patch.object(auto_bot, "clear_pending_cashout"),
        ]
        self.mock_save_daily = self._patchers[0].start()
        self._patchers[1].start()
        self._patchers[2].start()

        self.mock_strategy = MagicMock()
        self.mock_counter = MagicMock()
        self.mock_card_rec = MagicMock()
        self.mock_card_rec.recognize.return_value = ([], [])
        self.mock_reward_reader = MagicMock()
        self.mock_settlement_mgr = MagicMock()

        self.ctx = BotSessionState(
            mode="max_profit",
            strat_name="Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=500,
            daily_fails=2,
            round_count=5,
            net_profit=400,
            strategy=self.mock_strategy,
            counter=self.mock_counter,
            card_rec=self.mock_card_rec,
            reward_reader=self.mock_reward_reader,
            settlement_mgr=self.mock_settlement_mgr,
            on_stats_update=None,
            on_prompt_settlement=None,
        )

    def tearDown(self):
        for p in self._patchers:
            p.stop()

    def test_state_handlers_registered(self):
        expected_states = {
            "START_BET",
            "HOLD_CARDS",
            "TAP_TO_PROCEED",
            "ASK_CHALLENGE",
            "HIGH_LOW",
            "FAIL",
            "RESULT",
        }
        self.assertTrue(expected_states.issubset(set(STATE_HANDLERS.keys())))
        for state, handler in STATE_HANDLERS.items():
            self.assertTrue(callable(handler), f"Handler for {state} should be callable")

    def test_flicker_guards_reset_accounting(self):
        self.ctx.has_recorded_fail = True
        self.ctx.update_state_flicker_guards("START_BET")
        self.mock_settlement_mgr.reset_round.assert_called_with(self.mock_strategy)
        self.mock_reward_reader.reset_round.assert_called_once()
        self.assertFalse(self.ctx.has_recorded_fail)

    def test_flicker_guards_reset_prompt(self):
        self.ctx.poker_deal_solved = True
        self.ctx.has_recorded_fail = True
        self.ctx.update_state_flicker_guards("HIGH_LOW")
        self.mock_reward_reader.reset_prompt.assert_called_once()
        self.assertFalse(self.ctx.poker_deal_solved)
        self.assertFalse(self.ctx.has_recorded_fail)

    @patch("auto_bot.safe_click")
    def test_handle_tap_to_proceed(self, mock_click):
        mock_img = np.zeros((720, 1280, 3), dtype=np.uint8)
        handle_tap_to_proceed(self.ctx, mock_img, win_left=100, win_top=50)
        mock_click.assert_called_once_with(640, 360, 100, 50)

    @patch("auto_bot.find_and_click_icon", return_value=True)
    def test_handle_start_bet_starts_round(self, mock_click):
        import contextlib
        import io
        mock_img = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.ctx.in_round = False
        initial_rounds = self.ctx.round_count
        with contextlib.redirect_stdout(io.StringIO()):
            handle_start_bet(self.ctx, mock_img, win_left=0, win_top=0)
        self.assertTrue(self.ctx.in_round)
        self.assertEqual(self.ctx.round_count, initial_rounds + 1)
        self.mock_save_daily.assert_called_once()

    @patch("auto_bot.time.sleep")
    @patch("auto_bot.find_and_click_icon")
    @patch("auto_bot.safe_click")
    @patch("auto_bot.get_currently_held_indices")
    def test_handle_hold_cards_verifies_before_replace_and_resyncs_on_miss(
        self, mock_get_held, mock_safe_click, mock_find_click, mock_sleep
    ):
        from src.recognizer import RecognizedCard

        # Mock 5 dealt cards
        cards = [
            RecognizedCard(0, "2", "C", 0.95, 0.90, 0.5),
            RecognizedCard(4, "3", "C", 0.95, 0.90, 0.5),
            RecognizedCard(8, "4", "C", 0.95, 0.90, 0.5),
            RecognizedCard(12, "5", "C", 0.95, 0.90, 0.5),
            RecognizedCard(16, "6", "C", 0.95, 0.90, 0.5),
        ]
        rects = [(100 + 100 * i, 300, 80, 120) for i in range(5)]
        self.mock_card_rec.recognize.return_value = (cards, rects)

        mock_img = np.zeros((720, 1280, 3), dtype=np.uint8)

        # 1. First invocation: solver chooses target holds (e.g. slots 0, 1, 2).
        # Currently none are held.
        mock_get_held.return_value = set()
        with contextlib.redirect_stdout(io.StringIO()):
            handle_hold_cards(self.ctx, mock_img, win_left=10, win_top=20)

        # Verify cards to toggle were clicked
        self.assertEqual(mock_safe_click.call_count, len(self.ctx.target_held_indices))
        self.assertTrue(self.ctx.has_done_initial_hold)
        # MUST NOT have clicked replace yet because hold state is unverified
        mock_find_click.assert_not_called()

        # 2. Second invocation: Simulate cursor moved away during click, missing slot 1.
        # Screen shows only slots {0, 2} are actually held. Target is {0, 1, 2}.
        target_slots = set(self.ctx.target_held_indices)
        mock_safe_click.reset_mock()
        mock_find_click.reset_mock()
        mock_get_held.return_value = target_slots - {1}

        with contextlib.redirect_stdout(io.StringIO()):
            handle_hold_cards(self.ctx, mock_img, win_left=10, win_top=20)

        # Verify only missing slot 1 was re-clicked (resync)
        self.assertEqual(mock_safe_click.call_count, 1)
        expected_x = rects[1][0] + rects[1][2] // 2
        expected_y = rects[1][1] + rects[1][3] // 2
        mock_safe_click.assert_called_once_with(expected_x, expected_y, 10, 20)
        # Still unverified, so replace must NOT be clicked
        mock_find_click.assert_not_called()

        # 3. Third invocation: All target slots {0, 1, 2} are now verified on screen
        mock_safe_click.reset_mock()
        mock_find_click.reset_mock()
        mock_get_held.return_value = target_slots

        with contextlib.redirect_stdout(io.StringIO()):
            handle_hold_cards(self.ctx, mock_img, win_left=10, win_top=20)

        # No cards needed re-clicking
        mock_safe_click.assert_not_called()
        # Hold state verified: Replace button click is finally authorized
        self.assertTrue(mock_find_click.called)

    def test_dynamic_icon_templates_discovery(self):
        import tempfile
        from pathlib import Path
        from auto_bot import _build_icon_templates

        with tempfile.TemporaryDirectory() as tmpdir:
            icons_dir = Path(tmpdir) / "templates" / "icons"
            icons_dir.mkdir(parents=True)
            (icons_dir / "tpl_replace.png").touch()
            (icons_dir / "tpl_high.png").touch()

            for lk in ("ko", "id"):
                ld = icons_dir / lk
                ld.mkdir()
                (ld / f"start_{lk}.png").touch()
                (ld / f"full_{lk}.png").touch()
                (ld / f"proceed_{lk}.png").touch()
                (ld / f"result_{lk}.png").touch()
                (ld / f"fail_{lk}.png").touch()
                (ld / f"toobad_{lk}.png").touch()
                (ld / f"chance_{lk}.png").touch()
                (ld / f"success_{lk}.png").touch()

            with patch("auto_bot.resource_path", side_effect=lambda *parts: str(Path(tmpdir).joinpath(*parts))):
                icons, langs, ok_as_is = _build_icon_templates()

            self.assertIn("ko", langs)
            self.assertIn("id", langs)
            self.assertEqual(len(langs["ko"]), 8)
            self.assertEqual(len(langs["id"]), 8)
            self.assertEqual(len(icons["START_BET"]), 2)
            self.assertEqual(len(ok_as_is), 2)


if __name__ == "__main__":
    unittest.main()
