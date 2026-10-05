import sys
import os
import json
import csv
import tempfile
import time
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
ROOT_DIR = Path(__file__).resolve().parents[1]
for p in (str(SRC_DIR), str(ROOT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import auto_bot
    import localization
    from main_ui import HololiveBotUI, STRATEGY_KEYS
    HAVE_GUI = True
except (ImportError, Exception):
    HAVE_GUI = False


@unittest.skipUnless(HAVE_GUI, 'GUI dependencies (Pillow, cv2, numpy, keyboard) not installed')
class TestGUISettingsAndMenus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Create a single hidden UI instance for fast tests
        with patch("keyboard.add_hotkey"), patch("keyboard.hook"):
            cls.app = HololiveBotUI()
            cls.app.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.app.destroy()
        except Exception:
            pass

    def test_tab_switching(self):
        # Test switching to all 3 tabs and invalid tab guard
        self.app.switch_tab("sim")
        self.assertEqual(self.app.current_tab, "sim")
        self.assertEqual(self.app.canvas.itemcget(self.app.btn_toggle_modifiers_win, "state"), "normal")

        self.app.switch_tab("settings")
        self.assertEqual(self.app.current_tab, "settings")
        self.assertEqual(self.app.canvas.itemcget(self.app.btn_toggle_modifiers_win, "state"), "hidden")

        self.app.switch_tab("bot")
        self.assertEqual(self.app.current_tab, "bot")
        self.assertEqual(self.app.canvas.itemcget(self.app.btn_toggle_modifiers_win, "state"), "normal")

        # Invalid tab should be ignored
        self.app.switch_tab("nonexistent")
        self.assertEqual(self.app.current_tab, "bot")

    def test_save_user_settings(self):
        self.app.entry_setting_target.delete(0, "end")
        self.app.entry_setting_target.insert(0, "18500")

        self.app.entry_setting_ticket.delete(0, "end")
        self.app.entry_setting_ticket.insert(0, "60")

        with patch("auto_bot.save_daily_data") as mock_save:
            self.app.save_user_settings()
            mock_save.assert_called_once()
            _, kwargs = mock_save.call_args
            self.assertEqual(kwargs.get("target_limit"), 18500)
            self.assertEqual(kwargs.get("ticket_cost"), 60)

        self.assertEqual(self.app.target_limit, 18500)
        self.assertEqual(self.app.ticket_cost, 60)

    def test_restore_default_settings(self):
        with patch.object(self.app, "save_user_settings") as mock_save:
            self.app.restore_default_settings()
            self.assertEqual(self.app.entry_setting_target.get(), "20000")
            self.assertEqual(self.app.entry_setting_ticket.get(), "50")
            self.assertEqual(self.app.param_min_win_rate, 60)
            self.assertEqual(self.app.param_cushion_target, 19800)
            self.assertEqual(self.app.param_sprint_target, 10000)
            self.assertEqual(self.app.param_max_doubles, 10)
            self.assertFalse(self.app.param_drop_seven_eight)
            mock_save.assert_called_once()

    def test_open_custom_parametric_dialog(self):
        with patch.object(self.app, "save_settings") as mock_save:
            # Call dialog generator and test dialog interaction
            with patch("tkinter.Toplevel.grab_set"):
                self.app.open_custom_parametric_dialog()

            # Find the opened Toplevel child
            toplevel = None
            for child in self.app.winfo_children():
                if isinstance(child, type(self.app)) or child.__class__.__name__ == "Toplevel":
                    toplevel = child
                    break

            self.assertIsNotNone(toplevel)
            # Destroy after test
            toplevel.destroy()

    def test_menu_reset_stats_confirmed(self):
        self.app.current_coins = 15000
        self.app.current_fails = 5
        self.app.current_profit = 14750

        with patch("tkinter.messagebox.askyesno", return_value=True), \
             patch.object(self.app, "save_settings") as mock_save, \
             patch.object(self.app, "update_stats_display") as mock_update:
            self.app.menu_reset_stats()
            self.assertEqual(self.app.current_coins, 0)
            self.assertEqual(self.app.current_fails, 0)
            self.assertEqual(self.app.current_profit, 0)
            mock_save.assert_called_once()
            mock_update.assert_called_once()

    def test_menu_reset_stats_cancelled(self):
        self.app.current_coins = 9000
        with patch("tkinter.messagebox.askyesno", return_value=False), \
             patch.object(self.app, "save_settings") as mock_save:
            self.app.menu_reset_stats()
            self.assertEqual(self.app.current_coins, 9000)
            mock_save.assert_not_called()

    def test_export_benchmark_csv_and_json(self):
        sample_results = [
            {
                "Strategy": "1.0.1 Legacy",
                "Days": 100,
                "MeanCoins": 31900.0,
                "StdCoins": 4200.0,
                "MeanFails": 2.1,
                "HitCapPct": 98.0,
                "Overflow30kPct": 65.0,
                "Overflow40kPct": 22.0,
                "MaxCoins": 48500,
            }
        ]
        self.app.last_benchmark_results = sample_results

        with tempfile.TemporaryDirectory() as tmpdir:
            csv_path = Path(tmpdir) / "test_benchmark.csv"
            json_path = Path(tmpdir) / "test_benchmark.json"

            # Test CSV Export
            with patch("tkinter.filedialog.asksaveasfilename", return_value=str(csv_path)), \
                 patch("tkinter.messagebox.showinfo"):
                self.app.export_benchmark_csv()

            self.assertTrue(csv_path.exists())
            with open(csv_path, "r", encoding="utf-8-sig") as f:
                reader = list(csv.DictReader(f))
                self.assertEqual(len(reader), 1)
                self.assertEqual(reader[0]["Strategy"], "1.0.1 Legacy")
                self.assertEqual(float(reader[0]["MeanCoins"]), 31900.0)

            # Test JSON Export
            with patch("tkinter.filedialog.asksaveasfilename", return_value=str(json_path)), \
                 patch("tkinter.messagebox.showinfo"):
                self.app.export_benchmark_json()

            self.assertTrue(json_path.exists())
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.assertEqual(len(data), 1)
                self.assertEqual(data[0]["Strategy"], "1.0.1 Legacy")

    def test_safe_open_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target_path = Path(tmpdir) / "sub_folder"
            with patch("os.startfile", create=True) as mock_start:
                self.app._safe_open_path(target_path)
                self.assertTrue(target_path.exists())
                mock_start.assert_called_once_with(target_path)

    def test_quick_strategy_presets(self):
        with patch.object(self.app, "save_settings"):
            # Test 1: Fastest preset
            self.app.apply_strategy_preset("fastest_clear")
            self.assertEqual(self.app.active_mode, "fastest_clear")
            self.assertEqual(self.app.btn_preset_fast.cget("style"), "ActiveTab.TButton")

            # Test 2: Balanced preset
            self.app.apply_strategy_preset("balanced")
            self.assertEqual(self.app.active_mode, "balanced")
            self.assertEqual(self.app.btn_preset_balanced.cget("style"), "ActiveTab.TButton")

            # Test 3: Profit preset
            self.app.apply_strategy_preset("max_profit")
            self.assertEqual(self.app.active_mode, "max_profit")
            self.assertEqual(self.app.btn_preset_profit.cget("style"), "ActiveTab.TButton")

    def test_select_background_menu(self):
        with patch.object(self.app, "save_settings"):
            # Disable background
            self.app.select_background(-1)
            self.assertEqual(self.app.bg_index, -1)
            self.assertFalse(self.app.show_bg)
            self.assertEqual(self.app.bg_var.get(), -1)

            # Re-enable if candidates exist
            if self.app.bg_candidates:
                self.app.select_background(0)
                self.assertEqual(self.app.bg_index, 0)
                self.assertTrue(self.app.show_bg)
                self.assertEqual(self.app.bg_var.get(), 0)

    def test_select_language_menu(self):
        with patch.object(self.app, "save_settings"):
            original_lang = self.app.current_lang

            # Switch to zh
            self.app.select_language("zh")
            self.assertEqual(self.app.current_lang, "zh")
            self.assertEqual(self.app.lang_var.get(), "zh")

            # Switch back to original
            self.app.select_language(original_lang)
            self.assertEqual(self.app.current_lang, original_lang)
            self.assertEqual(self.app.lang_var.get(), original_lang)

    def test_config_strat_button_visibility_on_strategy_change(self):
        with patch.object(self.app, "save_settings"):
            self.app.switch_tab("bot")
            # Select non-custom strategy (e.g. max_profit)
            max_profit_idx = STRATEGY_KEYS.index("max_profit")
            self.app.combo_strategy.current(max_profit_idx)
            self.app.on_strategy_change()
            self.assertEqual(self.app.canvas.itemcget(self.app.btn_config_strat_win, "state"), "hidden")

            # Select custom_parametric
            custom_idx = STRATEGY_KEYS.index("custom_parametric")
            self.app.combo_strategy.current(custom_idx)
            self.app.on_strategy_change()
            self.assertEqual(self.app.canvas.itemcget(self.app.btn_config_strat_win, "state"), "normal")

            # Select back to fastest_clear
            fast_idx = STRATEGY_KEYS.index("fastest_clear")
            self.app.combo_strategy.current(fast_idx)
            self.app.on_strategy_change()
            self.assertEqual(self.app.canvas.itemcget(self.app.btn_config_strat_win, "state"), "hidden")

    def test_modifiers_drawer_toggle(self):
        initial_state = self.app.modifiers_expanded
        with patch.object(self.app, "save_settings") as mock_save:
            self.app.toggle_modifiers_drawer()
            self.assertEqual(self.app.modifiers_expanded, not initial_state)
            mock_save.assert_called_once()

        # Toggle back
        with patch.object(self.app, "save_settings") as mock_save:
            self.app.toggle_modifiers_drawer()
            self.assertEqual(self.app.modifiers_expanded, initial_state)

    def test_modifiers_checkbuttons(self):
        self.app.var_mod_fast_build.set(True)
        self.app.var_mod_drop_78.set(True)
        self.app.var_mod_sprint_floor.set(True)
        with patch.object(self.app, "save_settings") as mock_save:
            self.app.on_modifier_toggle()
            self.assertTrue(self.app.mod_fast_build)
            self.assertTrue(self.app.mod_drop_78)
            self.assertTrue(self.app.mod_sprint_floor)
            self.assertTrue(self.app.param_drop_seven_eight)
            mock_save.assert_called_once()

    def test_file_menu_has_clear_logs(self):
        menubar_labels = [self.app.menubar.entrycget(i, "label") for i in range(self.app.menubar.index("end") + 1)]
        self.assertIn(localization.tr("menu_file", self.app.current_lang), menubar_labels)
        self.assertIn(localization.tr("menu_logs", self.app.current_lang), menubar_labels)
        self.assertIn(localization.tr("menu_background", self.app.current_lang), menubar_labels)
        self.assertIn(localization.tr("menu_language", self.app.current_lang), menubar_labels)
        self.assertIn(localization.tr("menu_settings", self.app.current_lang), menubar_labels)
        self.assertIn(localization.tr("menu_help", self.app.current_lang), menubar_labels)

        file_menu_labels = [self.app.file_menu.entrycget(i, "label") for i in range(self.app.file_menu.index("end") + 1)
                            if self.app.file_menu.type(i) != "separator"]
        self.assertIn(localization.tr("menu_reset_stats", self.app.current_lang), file_menu_labels)
        self.assertIn(localization.tr("menu_open_folders", self.app.current_lang), file_menu_labels)

        logs_menu_labels = [self.app.logs_menu.entrycget(i, "label") for i in range(self.app.logs_menu.index("end") + 1)
                            if self.app.logs_menu.type(i) != "separator"]
        self.assertIn(localization.tr("menu_clear_logs", self.app.current_lang), logs_menu_labels)
        self.assertIn(localization.tr("menu_save_logs", self.app.current_lang), logs_menu_labels)
        self.assertIn(localization.tr("menu_clean_old_logs", self.app.current_lang), logs_menu_labels)

        folder_labels = [self.app.open_folders_menu.entrycget(i, "label") for i in range(self.app.open_folders_menu.index("end") + 1)]
        self.assertIn(localization.tr("menu_open_config_dir", self.app.current_lang), folder_labels)
        self.assertIn(localization.tr("menu_open_logs_dir", self.app.current_lang), folder_labels)

    def test_open_settings_dialog(self):
        with patch.object(self.app, "save_user_settings") as mock_save, \
             patch("tkinter.Toplevel.grab_set"):
            self.app.open_settings_dialog()
            # Find the opened Toplevel child
            toplevel = None
            for child in self.app.winfo_children():
                if child.__class__.__name__ == "Toplevel":
                    toplevel = child
                    break
            self.assertIsNotNone(toplevel)
            toplevel.destroy()

    def test_settings_tab_and_sim_clear_logs_hidden(self):
        # In bot tab, clear logs and custom dialog launcher must be hidden
        self.app.switch_tab("bot")
        self.assertEqual(self.app.canvas.itemcget(self.app.btn_clear_logs_win, "state"), "hidden")
        self.assertEqual(self.app.canvas.itemcget(self.app.btn_open_custom_dialog_win, "state"), "hidden")

        # In simulation tab, clear logs button should be hidden
        self.app.switch_tab("sim")
        self.assertEqual(self.app.canvas.itemcget(self.app.btn_clear_logs_win, "state"), "hidden")
        self.assertEqual(self.app.canvas.itemcget(self.app.btn_open_custom_dialog_win, "state"), "hidden")

        # In settings tab, background and language combo widgets should be present and normal
        self.app.switch_tab("settings")
        self.assertEqual(self.app.canvas.itemcget(self.app.combo_window, "state"), "normal")
        self.assertEqual(self.app.canvas.itemcget(self.app.combo_bg_win, "state"), "normal")
        self.assertEqual(self.app.canvas.itemcget(self.app.btn_open_custom_dialog_win, "state"), "hidden")

    def test_selectable_log_widget(self):
        import tkinter as tk
        self.assertIsInstance(self.app.log_text, tk.Text)
        self.assertEqual(self.app.log_text.cget("state"), "disabled")

        # Test appending logs
        self.app.append_log_text("Test Log Entry 1\nTest Log Entry 2\n")
        content = self.app.log_text.get("1.0", "end-1c")
        self.assertIn("Test Log Entry 1", content)
        self.assertIn("Test Log Entry 2", content)
        self.assertEqual(self.app.log_text.cget("state"), "disabled")

        # Test text selectability
        self.app.log_text.tag_add("sel", "1.0", "end")
        selected = self.app.log_text.get("sel.first", "sel.last")
        self.assertIn("Test Log Entry 1", selected)

        # Test clearing logs
        self.app.clear_log_text()
        cleared_content = self.app.log_text.get("1.0", "end-1c").strip()
        self.assertEqual(cleared_content, "")
        self.assertEqual(self.app.log_text.cget("state"), "disabled")

    def test_field_box_opacity_and_log_toggle(self):
        # 1. Opacity adjustment
        self.app.set_field_box_opacity(85)
        self.assertEqual(self.app.field_box_opacity, 85)
        self.assertEqual(int(float(self.app.scale_setting_opacity.get())), 85)

        self.app.set_field_box_opacity(0)
        self.assertEqual(self.app.field_box_opacity, 0)

        # Clamping
        self.app.set_field_box_opacity(150)
        self.assertEqual(self.app.field_box_opacity, 100)
        self.app.set_field_box_opacity(-20)
        self.assertEqual(self.app.field_box_opacity, 0)

        # Reset to 80
        self.app.set_field_box_opacity(80)

        # 2. Log Console Toggle
        initial_log_state = self.app.show_log
        self.app.toggle_log_console()
        self.assertEqual(self.app.show_log, not initial_log_state)
        self.app.toggle_log_console()
        self.assertEqual(self.app.show_log, initial_log_state)

    def test_rotate_previous_log(self):
        from main_ui import rotate_previous_log
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            with patch("auto_bot.APP_DIR", tmppath), patch("auto_bot.LOGS_DIR", tmppath / "logs"):
                test_log = tmppath / "log.txt"
                test_log.write_text("Previous session log content\n", encoding="utf-8")
                rotate_previous_log()
                self.assertFalse(test_log.exists())
                archived = list((tmppath / "logs").glob("log_*.txt"))
                self.assertEqual(len(archived), 1)
                self.assertIn("Previous session log content", archived[0].read_text(encoding="utf-8"))

    def test_clean_old_logs_by_age(self):
        from main_ui import clean_old_logs
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            logs_dir = tmppath / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            with patch("auto_bot.LOGS_DIR", logs_dir):
                old_log = logs_dir / "log_2026-01-01_12-00-00.txt"
                old_log.write_text("old", encoding="utf-8")
                # Set mtime to 30 days ago
                thirty_days_ago = time.time() - (30 * 86400)
                os.utime(old_log, (thirty_days_ago, thirty_days_ago))

                fresh_log = logs_dir / "log_2026-09-26_12-00-00.txt"
                fresh_log.write_text("fresh", encoding="utf-8")

                deleted, _ = clean_old_logs(max_days=7, max_size_mb=0)
                self.assertEqual(deleted, 1)
                self.assertFalse(old_log.exists())
                self.assertTrue(fresh_log.exists())

    def test_clean_old_logs_by_size(self):
        from main_ui import clean_old_logs
        with tempfile.TemporaryDirectory() as tmpdir:
            logs_dir = Path(tmpdir) / "logs"
            logs_dir.mkdir(parents=True, exist_ok=True)
            with patch("auto_bot.LOGS_DIR", logs_dir):
                # Create 3 files of 1 MB each
                now = time.time()
                for i in range(3):
                    f = logs_dir / f"log_2026-09-2{i}_00-00-00.txt"
                    f.write_bytes(b"x" * (1024 * 1024))
                    mtime = now - ((3 - i) * 3600)
                    os.utime(f, (mtime, mtime))

                # Limit to 1.5 MB -> should delete oldest files until <= 1.5MB (deletes 2 files)
                deleted, freed_mb = clean_old_logs(max_days=0, max_size_mb=1)
                self.assertEqual(deleted, 2)
                remaining = list(logs_dir.glob("log_*.txt"))
                self.assertEqual(len(remaining), 1)
                self.assertEqual(remaining[0].name, "log_2026-09-22_00-00-00.txt")

    def test_tooltips_registered_and_localized(self):
        self.assertIn("opp_a2", self.app.tooltips)
        self.assertIn("mod_drop_6789", self.app.tooltips)
        self.assertIn("mod_free_roll", self.app.tooltips)
        self.assertIn("mod_mega_sprint", self.app.tooltips)

        # In English:
        self.app.current_lang = "en"
        self.app.refresh_texts()
        self.assertIn("94.1%", self.app.tooltips["opp_a2"].text)
        self.assertIn("6/7/8/9", self.app.tooltips["mod_drop_6789"].text)

        # In Japanese:
        self.app.current_lang = "ja"
        self.app.refresh_texts()
        self.assertIn("94.1%", self.app.tooltips["opp_a2"].text)
        self.assertIn("クッション", self.app.tooltips["mod_drop_6789"].text)

        # In Simplified Chinese:
        self.app.current_lang = "zh"
        self.app.refresh_texts()
        self.assertIn("垫刀", self.app.tooltips["mod_drop_6789"].text)

        # In Traditional Chinese:
        self.app.current_lang = "tw"
        self.app.refresh_texts()
        self.assertIn("墊刀", self.app.tooltips["mod_drop_6789"].text)

        # Reset to English
        self.app.current_lang = "en"
        self.app.refresh_texts()


@unittest.skipUnless(HAVE_GUI, 'GUI dependencies not installed')
class TestAppDirResolution(unittest.TestCase):
    def test_resolve_app_dir_writable(self):
        import auto_bot
        # Under normal conditions, workspace is writable
        res = auto_bot._resolve_app_dir()
        self.assertTrue(res.exists())

    def test_resolve_app_dir_fallback_on_permission_error(self):
        import auto_bot
        with tempfile.TemporaryDirectory() as fake_appdata:
            with patch.dict(os.environ, {"APPDATA": fake_appdata}):
                with patch.object(Path, "touch", side_effect=PermissionError("Read-only")):
                    res = auto_bot._resolve_app_dir()
                    self.assertEqual(res, Path(fake_appdata) / "HololiveDreamsAuto")
                    self.assertTrue(res.exists())


class TestToolTip(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
            self.root.withdraw()
        except Exception:
            self.skipTest("Tkinter display not available")

    def tearDown(self):
        if hasattr(self, "root"):
            try:
                self.root.destroy()
            except Exception:
                pass

    def test_tooltip_lifecycle(self):
        from main_ui import ToolTip
        btn = ttk.Button(self.root, text="Test")
        btn.pack()
        tip = ToolTip(btn, text="Initial Tooltip", delay_ms=10)
        self.assertEqual(tip.text, "Initial Tooltip")

        # Test show
        tip._show()
        self.assertIsNotNone(tip._tip_window)
        self.assertTrue(tip._tip_window.winfo_exists())

        # Test update_text
        tip.update_text("Updated Tooltip")
        self.assertEqual(tip.text, "Updated Tooltip")
        self.assertIsNone(tip._tip_window)

        # Test hide
        tip._show()
        self.assertIsNotNone(tip._tip_window)
        tip._hide()
        self.assertIsNone(tip._tip_window)

    def test_fast_build_disables_card_overrides_in_gui(self):
        # Enable Fast Build
        self.app.var_mod_fast_build.set(True)
        self.app._sync_modifier_states()

        # All card overrides and bailouts should be disabled
        self.assertEqual(str(self.app.chk_opp_a2.cget("state")), "disabled")
        self.assertEqual(str(self.app.chk_opp_3k.cget("state")), "disabled")
        self.assertEqual(str(self.app.chk_opp_4q.cget("state")), "disabled")
        self.assertEqual(str(self.app.chk_mod_drop_78.cget("state")), "disabled")
        self.assertEqual(str(self.app.chk_mod_drop_8.cget("state")), "disabled")

        # Disable Fast Build -> should return to normal
        self.app.var_mod_fast_build.set(False)
        self.app._sync_modifier_states()
        self.assertEqual(str(self.app.chk_opp_a2.cget("state")), "normal")
        self.assertEqual(str(self.app.chk_opp_3k.cget("state")), "normal")
        self.assertEqual(str(self.app.chk_opp_4q.cget("state")), "normal")


if __name__ == "__main__":
    unittest.main()




