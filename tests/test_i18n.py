"""Tests for i18n localization and multilingual support."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import contextlib
import io

import i18n
import auto_bot as bot
from main_ui import RedirectText


class I18nTests(unittest.TestCase):
    def test_all_languages_have_identical_keys(self):
        languages = list(i18n.TRANSLATIONS.keys())
        self.assertIn("zh", languages)
        self.assertIn("tw", languages)
        self.assertIn("en", languages)
        self.assertIn("ja", languages)

        base_keys = set(i18n.TRANSLATIONS["zh"].keys())
        for lang in ("tw", "en", "ja"):
            lang_keys = set(i18n.TRANSLATIONS[lang].keys())
            missing = base_keys - lang_keys
            extra = lang_keys - base_keys
            self.assertEqual(missing, set(), f"{lang} missing keys: {missing}")
            self.assertEqual(extra, set(), f"{lang} unexpected extra keys: {extra}")

    def test_format_parameters_resolve_without_error(self):
        sample_params = {
            "coins": 12800,
            "fails": 3,
            "loss": 150,
            "profit": 12650,
            "earned": 400,
            "cashout": 6400,
            "reward": 12800,
            "total": 20400,
            "rate": 0.725,
            "stage": 2,
            "successes": 3,
            "goal": "4 wins",
            "action": "Cashout",
            "wins": 4,
            "rank": "A",
            "choice": "HIGH",
            "frame": 5,
            "error": "Timeout",
            "key": "F10",
            "name": "tpl_check.png",
            "score": 0.95,
            "threshold": 0.80,
            "path": "templates/icon.png",
        }
        for lang in ("zh", "tw", "en", "ja"):
            for key in i18n.TRANSLATIONS[lang]:
                rendered = i18n.tr(key, lang=lang, **sample_params)
                self.assertIsInstance(rendered, str)
                self.assertNotIn("KeyError", rendered)

    def test_language_switching(self):
        i18n.set_lang("en")
        self.assertEqual(i18n.get_lang(), "en")
        self.assertIn("Hololive Dreams Auto Bot", i18n.tr("title"))

        i18n.set_lang("ja")
        self.assertEqual(i18n.get_lang(), "ja")
        self.assertIn("Hololive Dreams 自動Bot", i18n.tr("title"))

        i18n.set_lang("zh")
        self.assertEqual(i18n.get_lang(), "zh")
        self.assertIn("Hololive Dreams 自动猜高低", i18n.tr("title"))

    def test_strategy_labels_exist_for_all_languages(self):
        for lang in ("zh", "tw", "en", "ja"):
            self.assertIn(lang, i18n.STRATEGY_LABELS)
            self.assertEqual(len(i18n.STRATEGY_LABELS[lang]), 2)

    def test_redirect_text_regex_matches_all_languages(self):
        class DummyUI:
            def __init__(self):
                self.current_coins = 0
                self.current_fails = 0
                self.current_profit = 0
                self.log_lines = []
                self.log_max_lines = 13
                self.log_view_start = 0

            def after(self, ms, func, *args):
                func(*args)

            def update_stats_display(self, coins=None, fails=None, profit=None):
                if coins is not None: self.current_coins = coins
                if fails is not None: self.current_fails = fails
                if profit is not None: self.current_profit = profit

            def update_log_view(self):
                pass

        test_cases = [
            ("zh", "💰 成功入账: 400 ! 当前总金币: 12800 | 累计失败: 2 次 | 今日净利润: 12700", 12800, 2, 12700),
            ("tw", "💰 成功入帳: 400 ! 當前總金幣: 13200 | 累計失敗: 3 次 | 今日淨利潤: 13050", 13200, 3, 13050),
            ("en", "💰 Credited: 400! Total coins: 15000 | Fails: 4 | Net profit: 14800", 15000, 4, 14800),
            ("ja", "💰 入金成功: 400! 現在のコイン: 16000 | 失敗: 5 回 | 純利益: 15750", 16000, 5, 15750),
        ]

        for lang, log_line, exp_coins, exp_fails, exp_profit in test_cases:
            ui = DummyUI()
            redirector = RedirectText(ui)
            redirector.write(log_line)
            self.assertEqual(ui.current_coins, exp_coins, f"Failed for {lang}")
            self.assertEqual(ui.current_fails, exp_fails, f"Failed for {lang}")
            self.assertEqual(ui.current_profit, exp_profit, f"Failed for {lang}")

    def test_bot_loop_stats_callback_and_language(self):
        stats_calls = []

        def on_stats(coins, fails, profit):
            stats_calls.append((coins, fails, profit))

        with patch.object(bot, 'load_daily_data', return_value=(500, 1)), \
             patch.object(bot, 'CardRecognizer', return_value=MagicMock()), \
             patch.object(bot, 'HighLowCounter', return_value=MagicMock()), \
             patch.object(bot, 'capture_game_window', return_value=(None, 0, 0)), \
             contextlib.redirect_stdout(io.StringIO()) as buf:
            bot.bot_running = False
            bot.auto_play_loop(mode='legacy', on_stats_update=on_stats, lang='en')

        self.assertEqual(i18n.get_lang(), 'en')
        self.assertEqual(stats_calls, [(500, 1, 450)])
        self.assertIn("Starting bot... Today's coins: 500 | Fails: 1 | Net profit: 450", buf.getvalue())

    def test_load_external_locales_from_directory(self):
        import tempfile
        import json
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            custom_locale = {
                "language_name": "Esperanto",
                "strategy_labels": ["1.0.1 Klasika", "3-Etapa Strategio"],
                "translations": {
                    "title": "Hololive Dreams Aŭtomata",
                    "start_bot": "Komencante roboton... Moneroj: {coins}",
                }
            }
            (tmp_path / "eo.json").write_text(json.dumps(custom_locale), encoding="utf-8")

            languages = i18n.load_external_locales(tmp_path)
            lang_codes = [code for code, _ in languages]
            self.assertIn("eo", lang_codes)
            self.assertEqual(i18n.LANGUAGE_NAMES.get("eo"), "Esperanto")

            i18n.set_lang("eo")
            self.assertEqual(i18n.tr("title"), "Hololive Dreams Aŭtomata")
            self.assertEqual(i18n.tr("start_bot", coins=100), "Komencante roboton... Moneroj: 100")
            # Fallback for untranslated keys
            self.assertEqual(i18n.tr("status_idle"), "Status: Idle")

    def test_logs_match_selected_display_language(self):
        for lang, expected_token in [
            ("zh", "开始自动挂机... 当日累计代币: 1000"),
            ("tw", "開始自動掛機... 當日累計代幣: 1000"),
            ("en", "Starting bot... Today's coins: 1000"),
            ("ja", "自動Botを開始... 本日の獲得コイン: 1000"),
        ]:
            with patch.object(bot, 'load_daily_data', return_value=(1000, 0)), \
                 patch.object(bot, 'CardRecognizer', return_value=MagicMock()), \
                 patch.object(bot, 'HighLowCounter', return_value=MagicMock()), \
                 patch.object(bot, 'capture_game_window', return_value=(None, 0, 0)), \
                 contextlib.redirect_stdout(io.StringIO()) as buf:
                bot.bot_running = False
                bot.auto_play_loop(mode='legacy', lang=lang)

            self.assertIn(expected_token, buf.getvalue(), f"Log output did not match {lang}")


if __name__ == '__main__':
    unittest.main()

