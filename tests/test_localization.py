import sys
from pathlib import Path
SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

"""Tests for i18n localization and multilingual support."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import contextlib
import io

import localization

try:
    import auto_bot as bot
except ImportError:
    bot = None


class I18nTests(unittest.TestCase):
    def test_all_languages_have_identical_keys(self):
        languages = list(localization.TRANSLATIONS.keys())
        self.assertIn("zh", languages)
        self.assertIn("tw", languages)
        self.assertIn("en", languages)
        self.assertIn("ja", languages)

        base_keys = set(localization.TRANSLATIONS["zh"].keys())
        for lang in ("tw", "en", "ja"):
            lang_keys = set(localization.TRANSLATIONS[lang].keys())
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
            "mean": 35000,
            "std": 12000,
            "max": 520000,
            "cap": 99.5,
            "over30": 85.0,
            "over40": 42.0,
            "observed": 160015,
            "expected": 1600,
            "amount": 1600,
        }
        for lang in ("zh", "tw", "en", "ja"):
            for key in localization.TRANSLATIONS[lang]:
                rendered = localization.tr(key, lang=lang, **sample_params)
                self.assertIsInstance(rendered, str)
                self.assertNotIn("KeyError", rendered)

    def test_language_switching(self):
        localization.set_lang("en")
        self.assertEqual(localization.get_lang(), "en")
        self.assertIn("Hololive Dreams Auto Bot", localization.tr("title"))

        localization.set_lang("ja")
        self.assertEqual(localization.get_lang(), "ja")
        self.assertIn("Hololive Dreams 自動Bot", localization.tr("title"))

        localization.set_lang("zh")
        self.assertEqual(localization.get_lang(), "zh")
        self.assertIn("Hololive Dreams 自动猜高低", localization.tr("title"))

    def test_strategy_labels_exist_for_all_languages(self):
        for lang in ("zh", "tw", "en", "ja"):
            self.assertIn(lang, localization.STRATEGY_LABELS)
            self.assertEqual(len(localization.STRATEGY_LABELS[lang]), 9)


    @unittest.skipIf(bot is None, "auto_bot dependencies not installed")
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
            bot.auto_play_loop(mode='legacy_101', on_stats_update=on_stats, lang='en')

        self.assertEqual(localization.get_lang(), 'en')
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

            languages = localization.load_external_locales(tmp_path)
            lang_codes = [code for code, _ in languages]
            self.assertIn("eo", lang_codes)
            self.assertEqual(localization.LANGUAGE_NAMES.get("eo"), "Esperanto")

            localization.set_lang("eo")
            self.assertEqual(localization.tr("title"), "Hololive Dreams Aŭtomata")
            self.assertEqual(localization.tr("start_bot", coins=100), "Komencante roboton... Moneroj: 100")
            # Fallback for untranslated keys
            self.assertEqual(localization.tr("status_idle"), "Status: Idle")

    @unittest.skipIf(bot is None, "auto_bot dependencies not installed")
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
                bot.auto_play_loop(mode='legacy_101', lang=lang)

            self.assertIn(expected_token, buf.getvalue(), f"Log output did not match {lang}")

    def test_all_strategies_have_descriptions(self):
        from strategies import STRATEGY_REGISTRY
        for strat_key in STRATEGY_REGISTRY:
            desc_key = f"desc_{strat_key}"
            for lang in ("zh", "tw", "en", "ja"):
                desc = localization.tr(desc_key, lang=lang)
                self.assertNotEqual(desc, desc_key, f"Missing description for {strat_key} in {lang}")
                self.assertTrue(len(desc) > 5, f"Description too short for {strat_key} in {lang}")



if __name__ == '__main__':
    unittest.main()

