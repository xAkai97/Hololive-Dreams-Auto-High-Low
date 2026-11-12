"""Tests for Log management, retention, and rotation."""

import os
import shutil
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import auto_bot
from ui.log_manager import (
    clean_old_logs,
    is_trivial_log_content,
    load_saved_stats,
    rotate_previous_log,
)


class TestLogManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.app_dir = Path(self.temp_dir)
        self.logs_dir = self.app_dir / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)

        self.patch_app = patch.object(auto_bot, "APP_DIR", self.app_dir)
        self.patch_logs = patch.object(auto_bot, "LOGS_DIR", self.logs_dir)
        self.patch_app.start()
        self.patch_logs.start()

    def tearDown(self):
        self.patch_logs.stop()
        self.patch_app.stop()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_saved_stats(self):
        with (
            patch.object(auto_bot, "load_daily_data", return_value=(2000, 3)),
            patch.object(auto_bot, "load_config", return_value={"ticket_cost": 50}),
        ):
            c, fl, net = load_saved_stats()
            self.assertEqual(c, 2000)
            self.assertEqual(fl, 3)
            self.assertEqual(net, 2000 - (3 * 50))

    def test_is_trivial_log_content(self):
        self.assertTrue(is_trivial_log_content(""))
        self.assertTrue(is_trivial_log_content("   \n\n  "))
        trivial = (
            "=== UI Session Started: 2026-11-11 10:00:00 ===\n"
            "[Settings] Updated config\n"
            "=== UI Session Closed: 2026-11-11 10:01:00 ===\n"
        )
        self.assertTrue(is_trivial_log_content(trivial))

        meaningful = "=== UI Session Started: 2026-11-11 10:00:00 ===\n🃏 Hand Dealt: [♠A ♥A ♠K ♥K ♠Q]\n"
        self.assertFalse(is_trivial_log_content(meaningful))

    def test_clean_old_logs(self):
        # Empty dir
        d, mb = clean_old_logs(max_days=14, max_size_mb=20)
        self.assertEqual(d, 0)
        self.assertEqual(mb, 0.0)

        # 1. Trivial file cleanup
        trivial_file = self.logs_dir / "trivial.txt"
        trivial_file.write_text("=== UI Session Started: 2026-11-11 10:00:00 ===", encoding="utf-8")
        self.assertTrue(trivial_file.exists())
        clean_old_logs(max_days=14, max_size_mb=20)
        self.assertFalse(trivial_file.exists())

        # 2. Age-based pruning
        old_file = self.logs_dir / "old_log.txt"
        old_file.write_text(
            "Real content here that is very important and long enough to exceed small threshold" * 10, encoding="utf-8"
        )
        # Set mtime to 30 days ago
        old_time = time.time() - (30 * 86400)
        os.utime(old_file, (old_time, old_time))

        deleted, _freed = clean_old_logs(max_days=14, max_size_mb=20)
        self.assertEqual(deleted, 1)
        self.assertFalse(old_file.exists())

        # 3. Size-based pruning
        f1 = self.logs_dir / "size1.log"
        f2 = self.logs_dir / "size2.log"
        f1.write_text("A" * 600 * 1024, encoding="utf-8")  # 600KB
        f2.write_text("B" * 600 * 1024, encoding="utf-8")  # 600KB
        os.utime(f1, (time.time() - 100, time.time() - 100))
        os.utime(f2, (time.time(), time.time()))

        # Max size 1 MB -> total is 1.2 MB -> oldest f1 pruned
        deleted, _freed = clean_old_logs(max_days=0, max_size_mb=1)
        self.assertEqual(deleted, 1)
        self.assertFalse(f1.exists())
        self.assertTrue(f2.exists())

    def test_rotate_previous_log_trivial(self):
        log_file = self.app_dir / "log.txt"
        log_file.write_text("=== UI Session Closed: 2026-11-11 10:00:00 ===", encoding="utf-8")
        rotate_previous_log(force=False)
        self.assertFalse(log_file.exists())

    def test_rotate_previous_log_meaningful_and_force(self):
        log_file = self.app_dir / "log.txt"
        meaningful = "=== UI Session Started: 2026-11-10 10:00:00 ===\nHand dealt and game played with big wins!\n"
        log_file.write_text(meaningful, encoding="utf-8")

        debug_file = self.app_dir / "debug_log.txt"
        debug_file.write_text("=== Hololive Dreams Debug Log (2026-11-10 10:00:00) ===\nDebug traces", encoding="utf-8")

        with (
            patch.object(
                auto_bot, "get_game_date", side_effect=["2026-11-10", "2026-11-11", "2026-11-10", "2026-11-11"]
            ),
            patch.object(auto_bot, "load_config", return_value={"coins": 0, "target_limit": 20000}),
        ):
            rotate_previous_log(force=False)

        self.assertFalse(log_file.exists())
        self.assertFalse(debug_file.exists())
        archived_logs = list(self.logs_dir.glob("log_*.txt"))
        self.assertEqual(len(archived_logs), 1)
        archived_debug = list(self.logs_dir.glob("debug_log_*.txt"))
        self.assertEqual(len(archived_debug), 1)

        # Rotate again to test collision counter (_1)
        log_file.write_text(meaningful, encoding="utf-8")
        with patch.object(auto_bot, "load_config", return_value={"coins": 0, "target_limit": 20000}):
            rotate_previous_log(force=True)
        archived_logs_after = list(self.logs_dir.glob("log_*.txt"))
        self.assertEqual(len(archived_logs_after), 2)


if __name__ == "__main__":
    unittest.main()
