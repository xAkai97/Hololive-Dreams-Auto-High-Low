"""Tests for dialogs and UI export/modal helpers."""

import json
import os
import queue
import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ui import dialogs


class DummyApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.withdraw()
        self.current_lang = "en"
        self.font_family = "Segoe UI"
        self.theme_palette = {
            "is_dark": True,
            "bg_plain_hex": "#18181B",
            "text_primary": "#F8FAFC",
            "text_secondary": "#E2E8F0",
        }
        self.target_limit = 20000
        self.ticket_cost = 50
        self.log_retention_days = 14
        self.log_max_size_mb = 20
        self.settlement_recovery_mode = "auto"
        self.settlement_ocr_timeout = 8.0
        self.custom_font_family = "auto"
        self.font_scale = 100
        self.param_min_win_rate = 60
        self.param_cushion_target = 3000
        self.param_sprint_target = 10000
        self.param_max_doubles = 10
        self.hunt_14k_attempts = 0
        self.param_drop_seven_eight = False
        self.saved_settings_called = False

    def save_settings(self):
        self.saved_settings_called = True

    def save_user_settings(self):
        self.saved_settings_called = True

    def restore_default_settings(self):
        self.target_limit = 20000
        self.ticket_cost = 50

    def set_field_box_opacity(self, val, save=False):
        pass


class TestDialogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = DummyApp()

    @classmethod
    def tearDownClass(cls):
        cls.app.destroy()

    def tearDown(self):
        for w in list(self.app.winfo_children()):
            if isinstance(w, tk.Toplevel):
                w.destroy()
        self.app.update_idletasks()

    def test_show_help_rules_and_strategies(self):
        with patch("webbrowser.open") as mock_open:
            dialogs.show_help_rules(self.app)
            self.assertTrue(mock_open.called)

        with patch("webbrowser.open") as mock_open:
            dialogs.show_help_strategies(self.app)
            self.assertTrue(mock_open.called)

    def test_show_help_about(self):
        with (
            patch.object(self.app, "winfo_rootx", return_value=100),
            patch.object(self.app, "winfo_rooty", return_value=100),
            patch.object(self.app, "winfo_width", return_value=500),
            patch.object(self.app, "winfo_height", return_value=400),
        ):
            dialogs.show_help_about(self.app)
            self.app.update()

    def test_benchmark_results_dialog_and_exports(self):
        # Empty results check
        dialogs.show_benchmark_results_dialog(self.app, [])

        sample_results = [
            {
                "Days": 50,
                "Rank": 1,
                "Strategy": "Adaptive Max Profit",
                "MeanCoins": 31200.0,
                "MeanFails": 2.1,
                "HitCapPct": 98.0,
                "MaxCoins": 33400.0,
            }
        ]

        with (
            patch.object(self.app, "winfo_x", return_value=50),
            patch.object(self.app, "winfo_y", return_value=50),
            patch.object(self.app, "winfo_width", return_value=600),
            patch.object(self.app, "winfo_height", return_value=500),
        ):
            dialogs.show_benchmark_results_dialog(self.app, sample_results)
            self.app.update()

        # CSV Export
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            csv_path = f.name
        try:
            with (
                patch("tkinter.filedialog.asksaveasfilename", return_value=csv_path),
                patch("tkinter.messagebox.showinfo"),
            ):
                dialogs.export_benchmark_csv(self.app, sample_results)
            self.assertTrue(os.path.exists(csv_path))
            self.assertGreater(os.path.getsize(csv_path), 0)
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)

        # JSON Export
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            json_path = f.name
        try:
            with (
                patch("tkinter.filedialog.asksaveasfilename", return_value=json_path),
                patch("tkinter.messagebox.showinfo"),
            ):
                dialogs.export_benchmark_json(self.app, sample_results)
            self.assertTrue(os.path.exists(json_path))
            with open(json_path, "r", encoding="utf-8") as jf:
                loaded = json.load(jf)
                self.assertEqual(loaded[0]["Strategy"], "Adaptive Max Profit")
        finally:
            if os.path.exists(json_path):
                os.remove(json_path)

    def test_show_settlement_modal(self):
        res_q = queue.Queue()
        with patch.object(self.app, "winfo_x", return_value=10), patch.object(self.app, "winfo_y", return_value=10):
            dialogs.show_settlement_modal(self.app, expected=400, observed="400", res_queue=res_q)
            self.app.update()

    def test_open_custom_parametric_dialog(self):
        with patch.object(self.app, "winfo_x", return_value=10), patch.object(self.app, "winfo_y", return_value=10):
            dialogs.open_custom_parametric_dialog(self.app)
            self.app.update()


if __name__ == "__main__":
    unittest.main()
