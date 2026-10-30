import unittest
from unittest.mock import MagicMock, patch
import numpy as np

import auto_bot
from auto_bot import (
    BotSessionState,
    set_scan_mode,
    toggle_scan_mode,
    get_scan_mode,
    safe_click,
    find_and_click_icon,
    handle_start_bet,
    handle_hold_cards,
    handle_tap_to_proceed,
    handle_ask_challenge,
    handle_high_low,
    handle_fail,
    handle_result,
    HighLowCounter,
)
from challenge_reward import ChallengeRewardReader
from settlement import SettlementManager, SettlementReader


class TestCompanionMode(unittest.TestCase):
    def setUp(self):
        auto_bot.scan_mode = False
        auto_bot._active_session_ctx = None
        self._patchers = [
            patch.object(auto_bot, "save_daily_data"),
            patch.object(auto_bot, "save_pending_cashout"),
            patch.object(auto_bot, "clear_pending_cashout"),
        ]
        for p in self._patchers:
            p.start()

    def tearDown(self):
        for p in self._patchers:
            p.stop()
        auto_bot.scan_mode = False
        auto_bot._active_session_ctx = None

    def test_mode_getters_and_toggles(self):
        self.assertFalse(get_scan_mode())
        set_scan_mode(True)
        self.assertTrue(get_scan_mode())

        toggled = toggle_scan_mode()
        self.assertFalse(toggled)
        self.assertFalse(get_scan_mode())

        toggled = toggle_scan_mode()
        self.assertTrue(toggled)
        self.assertTrue(get_scan_mode())

    def test_session_state_mode_sync_and_callback(self):
        callback_mock = MagicMock()
        ctx = BotSessionState(
            mode="max_profit",
            strat_name="Adaptive Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=5000,
            daily_fails=2,
            round_count=10,
            net_profit=4900,
            strategy=MagicMock(),
            counter=HighLowCounter(),
            card_rec=MagicMock(),
            reward_reader=ChallengeRewardReader(),
            settlement_mgr=None,
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=False,
            on_mode_change=callback_mock,
        )
        auto_bot._active_session_ctx = ctx

        set_scan_mode(True)
        self.assertTrue(ctx.scan_mode)
        callback_mock.assert_called_with(True)

        toggle_scan_mode()
        self.assertFalse(ctx.scan_mode)
        callback_mock.assert_called_with(False)

    def test_zero_click_guarantee(self):
        set_scan_mode(True)
        with patch("auto_bot._win_safe_click") as mock_click:
            res = safe_click(100, 200, 0, 0)
            self.assertFalse(res)
            mock_click.assert_not_called()

        dummy_img = np.zeros((200, 200, 3), dtype=np.uint8)
        res_icon = find_and_click_icon(dummy_img, "dummy.png", 0, 0)
        self.assertFalse(res_icon)

    def test_handle_start_bet_zero_clicks_in_scan_mode(self):
        set_scan_mode(True)
        ctx = BotSessionState(
            mode="max_profit",
            strat_name="Adaptive Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=5000,
            daily_fails=2,
            round_count=10,
            net_profit=4900,
            strategy=MagicMock(),
            counter=HighLowCounter(),
            card_rec=MagicMock(),
            reward_reader=ChallengeRewardReader(),
            settlement_mgr=None,
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=True,
        )
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        with patch("auto_bot.find_and_click_icon") as mock_icon_click:
            handle_start_bet(ctx, dummy_img, 0, 0)
            mock_icon_click.assert_not_called()

    def test_handle_tap_to_proceed_zero_clicks_in_scan_mode(self):
        set_scan_mode(True)
        mock_rec = MagicMock()
        mock_rec.recognize.return_value = ([], [])
        ctx = BotSessionState(
            mode="max_profit",
            strat_name="Adaptive Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=5000,
            daily_fails=2,
            round_count=10,
            net_profit=4900,
            strategy=MagicMock(),
            counter=HighLowCounter(),
            card_rec=mock_rec,
            reward_reader=ChallengeRewardReader(),
            settlement_mgr=None,
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=True,
        )
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        with patch("auto_bot.safe_click") as mock_click:
            handle_tap_to_proceed(ctx, dummy_img, 0, 0)
            mock_click.assert_not_called()

    def test_handle_fail_and_result_zero_clicks_in_scan_mode(self):
        set_scan_mode(True)
        mock_strategy = MagicMock()
        mock_settle = MagicMock()
        mock_settle.process_result.return_value = (5200, True)
        mock_rec = MagicMock()
        mock_rec.recognize.return_value = ([], [])

        ctx = BotSessionState(
            mode="max_profit",
            strat_name="Adaptive Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=5000,
            daily_fails=2,
            round_count=10,
            net_profit=4900,
            strategy=mock_strategy,
            counter=HighLowCounter(),
            card_rec=mock_rec,
            reward_reader=ChallengeRewardReader(),
            settlement_mgr=mock_settle,
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=True,
        )
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch("auto_bot.find_and_click_icon") as mock_icon_click:
            handle_fail(ctx, dummy_img, 0, 0)
            mock_icon_click.assert_not_called()
            self.assertEqual(ctx.daily_fails, 3)

        with patch("auto_bot.find_and_click_icon") as mock_icon_click:
            with patch("auto_bot.read_settlement_payout", return_value=200):
                handle_result(ctx, dummy_img, 0, 0)
                mock_icon_click.assert_not_called()

    def test_seamless_mode_switch_preserves_session_state(self):
        set_scan_mode(True)
        ctx = BotSessionState(
            mode="max_profit",
            strat_name="Adaptive Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=19850,
            daily_fails=4,
            round_count=45,
            net_profit=19650,
            strategy=MagicMock(),
            counter=HighLowCounter(),
            card_rec=MagicMock(),
            reward_reader=ChallengeRewardReader(),
            settlement_mgr=None,
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=True,
        )
        auto_bot._active_session_ctx = ctx

        # Remove cards during companion play
        ctx.counter.remove_cards([2, 3, 4, 14])
        self.assertEqual(ctx.counter.total_cards, 48)

        # Switch live to auto mode via hotkey toggle
        toggle_scan_mode()
        self.assertFalse(ctx.scan_mode)
        self.assertFalse(get_scan_mode())

        # Session accounting and counter state intact
        self.assertEqual(ctx.daily_coins, 19850)
        self.assertEqual(ctx.daily_fails, 4)
        self.assertEqual(ctx.round_count, 45)
        self.assertEqual(ctx.counter.total_cards, 48)

    def test_ocr_timeout_relaxation_in_scan_mode(self):
        mock_rec = MagicMock()
        mock_rec.recognize.return_value = ([], [])
        mock_strat = MagicMock()
        mock_strat.cushion_target = 19800
        mock_strat.expected_cash = 200
        mock_strat.base_cash = None
        mock_strat.decide.return_value = "cashout"
        ctx = BotSessionState(
            mode="max_profit",
            strat_name="Adaptive Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=5000,
            daily_fails=0,
            round_count=1,
            net_profit=5000,
            strategy=mock_strat,
            counter=HighLowCounter(),
            card_rec=mock_rec,
            reward_reader=MagicMock(),
            settlement_mgr=MagicMock(),
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=True,
        )
        ctx.ocr_timeout = 6.5
        ctx.reward_reader.observe.return_value = 400
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

        # In scan mode, handle_ask_challenge passes timeout=None to observe
        with patch("auto_bot.is_success_prompt", return_value=False):
            with patch("auto_bot.read_challenge_payout", return_value=400):
                ctx.strategy.base_cash = None
                handle_ask_challenge(ctx, dummy_img, 0, 0)
                ctx.reward_reader.observe.assert_called_with(400, unittest.mock.ANY, timeout=None)

        # Switch to auto bot (clicks enabled): timeout is now 6.5s
        ctx.scan_mode = False
        with patch("auto_bot.is_success_prompt", return_value=False):
            with patch("auto_bot.read_challenge_payout", return_value=400):
                ctx.strategy.base_cash = None
                handle_ask_challenge(ctx, dummy_img, 0, 0)
                ctx.reward_reader.observe.assert_called_with(400, unittest.mock.ANY, timeout=6.5)

    def test_advisor_deduplication_in_companion_mode(self):
        mock_rec = MagicMock()
        mock_rec.recognize.return_value = ([], [])
        mock_strat = MagicMock()
        mock_strat.cushion_target = 19800
        mock_strat.base_cash = 200
        mock_strat.expected_cash = 400
        mock_strat.decide.return_value = "cashout"
        ctx = BotSessionState(
            mode="max_profit",
            strat_name="Adaptive Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=5000,
            daily_fails=0,
            round_count=1,
            net_profit=5000,
            strategy=mock_strat,
            counter=HighLowCounter(),
            card_rec=mock_rec,
            reward_reader=MagicMock(),
            settlement_mgr=None,
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=True,
        )
        ctx.upcoming_card_val = 8
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

        with patch("auto_bot.read_challenge_payout", return_value=800):
            with patch("auto_bot.print") as mock_print:
                ctx.reward_reader.observe.return_value = 800
                handle_ask_challenge(ctx, dummy_img, 0, 0)
                first_call_count = mock_print.call_count
                self.assertGreater(first_call_count, 0)

                # Subsequent call with the exact same challenge state should be deduplicated
                handle_ask_challenge(ctx, dummy_img, 0, 0)
                self.assertEqual(mock_print.call_count, first_call_count)

    def test_companion_mode_consecutive_doubles_deplete_deck(self):
        from types import SimpleNamespace
        counter = HighLowCounter()
        self.assertEqual(counter.total_cards, 52)

        mock_rec = MagicMock()
        mock_rec.recognize.return_value = ([], [])

        card_k = SimpleNamespace(card_id=12, rank="K", suit="♠", rank_score=0.95, rank_margin=0.30)
        card_7 = SimpleNamespace(card_id=6, rank="7", suit="♥", rank_score=0.95, rank_margin=0.30)
        card_a = SimpleNamespace(card_id=13, rank="A", suit="♦", rank_score=0.95, rank_margin=0.30)

        mock_strat = MagicMock()
        mock_strat.cushion_target = 19800
        mock_strat.base_cash = 200
        mock_strat.expected_cash = 400
        mock_strat.decide.return_value = "challenge"

        ctx = BotSessionState(
            mode="max_profit",
            strat_name="Adaptive Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=5000,
            daily_fails=0,
            round_count=1,
            net_profit=5000,
            strategy=mock_strat,
            counter=counter,
            card_rec=mock_rec,
            reward_reader=MagicMock(),
            settlement_mgr=None,
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=True,
        )
        ctx.ocr_timeout = 8.0
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

        # 1. First base card King at x=300
        rect_k = (300, 100, 80, 120)
        with patch("auto_bot.find_all_card_rects", return_value=[rect_k]):
            mock_rec.recognize_card.return_value = card_k
            with patch("auto_bot.get_card_point_value", return_value=13):
                handle_high_low(ctx, dummy_img, 0, 0)
                self.assertEqual(ctx.counter.total_cards, 51)
                self.assertEqual(ctx.last_removed_card_x, 300)

                # Repeated frames in HIGH_LOW do not double-remove
                handle_high_low(ctx, dummy_img, 0, 0)
                self.assertEqual(ctx.counter.total_cards, 51)

        # 2. Challenge prompt after winning: new card 7 at x=420
        rect_7 = (420, 100, 80, 120)
        ctx.upcoming_card_val = None
        with patch("auto_bot.find_all_card_rects", return_value=[rect_k, rect_7]):
            mock_rec.recognize_card.return_value = card_7
            with patch("auto_bot.get_card_point_value", return_value=7):
                with patch("auto_bot.read_challenge_payout", return_value=800):
                    ctx.reward_reader.observe.return_value = 800
                    handle_ask_challenge(ctx, dummy_img, 0, 0)
                    self.assertEqual(ctx.counter.total_cards, 50)
                    self.assertEqual(ctx.last_removed_card_x, 420)
                    self.assertEqual(ctx.upcoming_card_val, 7)

                    # Repeated frames in ASK_CHALLENGE do not double-remove
                    handle_ask_challenge(ctx, dummy_img, 0, 0)
                    self.assertEqual(ctx.counter.total_cards, 50)

        # 3. Next double in HIGH_LOW with 7 at x=420 as base card
        with patch("auto_bot.find_all_card_rects", return_value=[rect_k, rect_7]):
            mock_rec.recognize_card.return_value = card_7
            with patch("auto_bot.get_card_point_value", return_value=7):
                handle_high_low(ctx, dummy_img, 0, 0)
                # Must still be 50 cards (already removed in challenge step)
                self.assertEqual(ctx.counter.total_cards, 50)
                self.assertEqual(ctx.last_removed_card_x, 420)

        # 4. Next double wins, Ace at x=540 revealed
        rect_a = (540, 100, 80, 120)
        ctx.upcoming_card_val = None
        with patch("auto_bot.find_all_card_rects", return_value=[rect_k, rect_7, rect_a]):
            mock_rec.recognize_card.return_value = card_a
            with patch("auto_bot.get_card_point_value", return_value=14):
                with patch("auto_bot.read_challenge_payout", return_value=1600):
                    ctx.reward_reader.observe.return_value = 1600
                    handle_ask_challenge(ctx, dummy_img, 0, 0)
                    self.assertEqual(ctx.counter.total_cards, 49)
                    self.assertEqual(ctx.last_removed_card_x, 540)
                    self.assertEqual(ctx.upcoming_card_val, 14)

    def test_challenge_reward_power_of_two_skip_and_fast_mode(self):
        reader = ChallengeRewardReader()
        # In Observer Mode (timeout=None), initial 400 confirms on 1st sample
        self.assertEqual(reader.observe(400, 1.0, timeout=None), 400)
        reader.reset_prompt()
        # User clicks fast through 800, lands on 1600 -> confirms immediately without deadlock
        self.assertEqual(reader.observe(1600, 2.0, timeout=None), 1600)
        reader.reset_prompt()
        # User clicks fast through 3200, lands on 6400 -> confirms immediately
        self.assertEqual(reader.observe(6400, 3.0, timeout=None), 6400)
        reader.reset_prompt()
        # Impossible non-power-of-two jump (e.g. 6400 -> 7000) is still rejected
        self.assertIsNone(reader.observe(7000, 4.0, timeout=None))

    def test_fast_click_through_result_credits_payout_on_next_round_transition(self):
        from strategies.max_profit import MaxProfitStrategy

        strat = MaxProfitStrategy()
        reader = ChallengeRewardReader()
        settle_mgr = SettlementManager(
            SettlementReader(timeout=8.0),
            save_data_fn=lambda c, f: None,
        )
        mock_rec = MagicMock()
        mock_rec.recognize.return_value = ([], [])

        ctx = BotSessionState(
            mode="max_profit",
            strat_name=strat.name,
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=16400,
            daily_fails=25,
            round_count=29,
            net_profit=15150,
            strategy=strat,
            counter=HighLowCounter(),
            card_rec=mock_rec,
            reward_reader=reader,
            settlement_mgr=settle_mgr,
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=True,
        )
        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)

        # 1. Initial ASK_CHALLENGE at 1500 -> 3000
        ctx.update_state_flicker_guards("ASK_CHALLENGE")
        ctx.last_state = "ASK_CHALLENGE"
        with patch("auto_bot.is_success_prompt", return_value=False), \
             patch("auto_bot.read_challenge_payout", return_value=3000):
            handle_ask_challenge(ctx, dummy_img, 0, 0)
        self.assertEqual(ctx.last_known_cashout, 1500)
        self.assertEqual(ctx.last_known_next_reward, 3000)

        # 2. Ongoing ASK_CHALLENGE at 3000 -> 6000 where strategy advises CASHOUT (3000)
        ctx.update_state_flicker_guards("ASK_CHALLENGE")
        with patch("auto_bot.is_success_prompt", return_value=True), \
             patch("auto_bot.read_challenge_payout", return_value=6000):
            handle_ask_challenge(ctx, dummy_img, 0, 0)
        self.assertEqual(ctx.settlement_mgr.expected_cashout, 3000)

        # 3. User ignores CASHOUT and clicks Double Up into HIGH_LOW (Spade 2)
        from types import SimpleNamespace
        card_2 = SimpleNamespace(card_id=0, rank="2", suit="♠", rank_score=0.90, rank_margin=0.25)
        ctx.update_state_flicker_guards("HIGH_LOW")
        ctx.last_state = "HIGH_LOW"
        self.assertIsNone(ctx.settlement_mgr.expected_cashout)
        with patch("auto_bot.find_all_card_rects", return_value=[(99, 365, 274, 390)]):
            mock_rec.recognize_card.return_value = card_2
            with patch("auto_bot.get_card_point_value", return_value=2):
                handle_high_low(ctx, dummy_img, 0, 0)
        self.assertTrue(ctx.hl_awaiting_challenge)

        # 4. User wins 6000 and clicks through RESULT in 1 frame while OCR still reads 0 (count-up start)
        ctx.update_state_flicker_guards("RESULT")
        ctx.last_state = "RESULT"
        self.assertEqual(ctx.last_known_cashout, 6000)
        with patch("auto_bot.read_settlement_payout", return_value=0):
            handle_result(ctx, dummy_img, 0, 0)
        self.assertFalse(ctx.settlement_mgr.has_tallied)

        # 5. Next frame is START_BET: fast click recovery credits 6000 before resetting settlement_mgr
        ctx.update_state_flicker_guards("START_BET")
        self.assertEqual(ctx.daily_coins, 22400)
        self.assertEqual(ctx.net_profit, 21150)

    def test_flipped_right_card_in_high_low_not_double_counted_as_step(self):
        from types import SimpleNamespace

        mock_rec = MagicMock()
        mock_rec.recognize.return_value = ([], [])
        card_j = SimpleNamespace(card_id=36, rank="J", suit="♠", rank_score=0.88, rank_margin=0.30)
        card_8 = SimpleNamespace(card_id=25, rank="8", suit="♥", rank_score=0.85, rank_margin=0.20)
        card_k = SimpleNamespace(card_id=47, rank="K", suit="♣", rank_score=0.70, rank_margin=0.20)

        ctx = BotSessionState(
            mode="max_profit",
            strat_name="Adaptive Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=3600,
            daily_fails=0,
            round_count=1,
            net_profit=3600,
            strategy=MagicMock(base_cash=None, cushion_target=19800, expected_cash=200, decide=MagicMock(return_value="challenge")),
            counter=HighLowCounter(),
            card_rec=mock_rec,
            reward_reader=ChallengeRewardReader(),
            settlement_mgr=None,
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=True,
        )
        frame_1080p = np.zeros((1080, 1920, 3), dtype=np.uint8)

        # Step 0 ASK_CHALLENGE with a single dialog contour at x=261 must NOT recover phantom King
        with patch("auto_bot.is_success_prompt", return_value=False), \
             patch("auto_bot.read_challenge_payout", return_value=400), \
             patch("auto_bot.find_all_card_rects", return_value=[(261, 365, 275, 390)]):
            mock_rec.recognize_card.return_value = card_k
            handle_ask_challenge(ctx, frame_1080p, 0, 0)
        self.assertIsNone(ctx.upcoming_card_val)
        self.assertEqual(ctx.counter.total_cards, 52)

        # Step 1 HIGH_LOW base card at x=54
        frame_1080p[0, 0] = [255, 255, 255]
        with patch("auto_bot.find_all_card_rects", return_value=[(54, 365, 276, 390)]):
            mock_rec.recognize_card.return_value = card_j
            with patch("auto_bot.get_card_point_value", return_value=11):
                handle_high_low(ctx, frame_1080p, 0, 0)
        self.assertEqual(ctx.step_count, 1)
        self.assertEqual(ctx.counter.total_cards, 51)

        # Right-hand card flips at x=381 (>= 54 + 200) before ASK_CHALLENGE:
        # Must record upcoming_card_val=8 and remove from deck once, WITHOUT incrementing step_count
        frame_1080p[10:200, 10:200] = 255
        with patch("auto_bot.find_all_card_rects", return_value=[(54, 365, 276, 390), (381, 365, 274, 390)]):
            mock_rec.recognize_card.return_value = card_8
            with patch("auto_bot.get_card_point_value", return_value=8):
                handle_high_low(ctx, frame_1080p, 0, 0)
        self.assertEqual(ctx.step_count, 1)
        self.assertEqual(ctx.upcoming_card_val, 8)
        self.assertEqual(ctx.counter.total_cards, 50)

        # After ASK_CHALLENGE, card_8 slides left to x=99 as Step #2 base card:
        # Increments step_count to 2, clears upcoming_card_val, and does NOT double-remove card_8
        ctx.hl_awaiting_challenge = False
        frame_1080p[200:400, 200:400] = 128
        with patch("auto_bot.find_all_card_rects", return_value=[(99, 365, 274, 390)]):
            mock_rec.recognize_card.return_value = card_8
            with patch("auto_bot.get_card_point_value", return_value=8):
                handle_high_low(ctx, frame_1080p, 0, 0)
        self.assertEqual(ctx.step_count, 2)
        self.assertIsNone(ctx.upcoming_card_val)
        self.assertEqual(ctx.counter.total_cards, 50)

    def test_new_round_in_hold_cards_resets_deck_and_final_hand_flag(self):
        from types import SimpleNamespace

        cards = [
            SimpleNamespace(card_id=0, rank="2", suit="♠", rank_score=0.90, rank_margin=0.30),
            SimpleNamespace(card_id=1, rank="2", suit="♥", rank_score=0.90, rank_margin=0.30),
            SimpleNamespace(card_id=4, rank="3", suit="♠", rank_score=0.90, rank_margin=0.30),
            SimpleNamespace(card_id=5, rank="3", suit="♥", rank_score=0.90, rank_margin=0.30),
            SimpleNamespace(card_id=8, rank="4", suit="♠", rank_score=0.90, rank_margin=0.30),
        ]
        rects = [(100 * i, 300, 80, 120) for i in range(5)]
        mock_rec = MagicMock()
        mock_rec.recognize.return_value = (cards, rects)

        ctx = BotSessionState(
            mode="max_profit",
            strat_name="Adaptive Max Profit",
            target_limit=20000,
            cushion_val=19800,
            ticket_cost=50,
            daily_coins=3600,
            daily_fails=5,
            round_count=10,
            net_profit=3350,
            strategy=MagicMock(),
            counter=HighLowCounter(),
            card_rec=mock_rec,
            reward_reader=ChallengeRewardReader(),
            settlement_mgr=None,
            on_stats_update=None,
            on_prompt_settlement=None,
            scan_mode=True,
        )
        # Simulate leftover state from previous round when START_BET was clicked through fast
        ctx.in_round = False
        ctx.has_logged_final_hand = True
        ctx.upcoming_card_val = 13
        ctx.counter.remove_cards([2, 3, 4, 5, 6, 7, 8, 9, 10])
        self.assertEqual(ctx.counter.total_cards, 43)

        dummy_img = np.zeros((100, 100, 3), dtype=np.uint8)
        handle_hold_cards(ctx, dummy_img, 0, 0)

        self.assertTrue(ctx.in_round)
        self.assertTrue(ctx.poker_deal_solved)
        self.assertFalse(ctx.has_logged_final_hand)
        self.assertIsNone(ctx.upcoming_card_val)
        # Counter was reset to 52 and then 5 dealt cards removed -> 47 remaining
        self.assertEqual(ctx.counter.total_cards, 47)
        self.assertEqual(ctx.hand_base_prize, 200)

    def test_template_roi_cache_and_language_pinning(self):
        auto_bot._TEMPLATE_ROI_CACHE.clear()
        auto_bot._DETECTED_GAME_LANG = None
        screen = np.zeros((200, 300, 3), dtype=np.uint8)
        tpl_en = np.zeros((24, 32), dtype=np.uint8)
        tpl_en[4:20, 4:28] = 255
        tpl_replace = np.zeros((24, 32), dtype=np.uint8)
        tpl_replace[2:22, 8:24] = 200
        screen[80:80 + 24, 120:120 + 32, :] = tpl_en[:, :, None]

        fake_lang_map = {
            "en": [("FAIL", "fake_fail_en.png")],
            "ja": [("FAIL", "fake_fail_ja.png")],
            "other": [("HOLD_CARDS", "fake_replace.png")],
        }

        def fake_get_tpl(p):
            if "en" in p:
                return tpl_en
            if "replace" in p:
                return tpl_replace
            return np.zeros((24, 32), dtype=np.uint8)

        with patch.object(auto_bot, "_LANG_TEMPLATES", fake_lang_map), \
             patch.object(auto_bot, "get_template", side_effect=fake_get_tpl):
            state1 = auto_bot.detect_game_state(screen)
            self.assertEqual(state1, "FAIL")
            self.assertEqual(auto_bot._DETECTED_GAME_LANG, "en")
            self.assertIn(("fake_fail_en.png", 200, 300), auto_bot._TEMPLATE_ROI_CACHE)

            # Universal template in 'other' (HOLD_CARDS) must still be detected immediately when pinned to 'en',
            # and must NOT overwrite _DETECTED_GAME_LANG to 'other'
            screen_hold = np.zeros((200, 300, 3), dtype=np.uint8)
            screen_hold[40:40 + 24, 60:60 + 32, :] = tpl_replace[:, :, None]
            state2 = auto_bot.detect_game_state(screen_hold)
            self.assertEqual(state2, "HOLD_CARDS")
            self.assertEqual(auto_bot._DETECTED_GAME_LANG, "en")

        auto_bot._TEMPLATE_ROI_CACHE.clear()
        auto_bot._DETECTED_GAME_LANG = None


if __name__ == "__main__":
    unittest.main()
