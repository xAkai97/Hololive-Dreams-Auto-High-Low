import unittest
from unittest.mock import MagicMock, patch
import numpy as np

from src.auto_bot import (
    BotSessionState,
    STATE_HANDLERS,
    handle_tap_to_proceed,
    handle_start_bet,
)


class TestStateMachineHandlers(unittest.TestCase):
    def setUp(self):
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

    @patch("src.auto_bot.safe_click")
    def test_handle_tap_to_proceed(self, mock_click):
        mock_img = np.zeros((720, 1280, 3), dtype=np.uint8)
        handle_tap_to_proceed(self.ctx, mock_img, win_left=100, win_top=50)
        mock_click.assert_called_once_with(640, 360, 100, 50)

    @patch("src.auto_bot.find_and_click_icon", return_value=True)
    @patch("src.auto_bot.save_daily_data")
    def test_handle_start_bet_starts_round(self, mock_save, mock_click):
        mock_img = np.zeros((720, 1280, 3), dtype=np.uint8)
        self.ctx.in_round = False
        initial_rounds = self.ctx.round_count
        handle_start_bet(self.ctx, mock_img, win_left=0, win_top=0)
        self.assertTrue(self.ctx.in_round)
        self.assertEqual(self.ctx.round_count, initial_rounds + 1)
        mock_save.assert_called_once()


if __name__ == "__main__":
    unittest.main()
