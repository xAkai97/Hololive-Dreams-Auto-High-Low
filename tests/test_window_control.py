import sys
from pathlib import Path
SRC_DIR = Path(__file__).resolve().parents[1] / 'src'
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import unittest
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

try:
    import window_control
    HAVE_WINDOW_CONTROL = True
except ImportError:
    HAVE_WINDOW_CONTROL = False


@unittest.skipUnless(HAVE_WINDOW_CONTROL, 'Window control dependencies (cv2, pygetwindow, etc.) not installed')
class WindowControlTests(unittest.TestCase):
    def test_find_game_window_exact_match(self):
        w1 = SimpleNamespace(title="hololive-Dreams-Auto-High-Low", width=800, height=600, _hWnd=1)
        w2 = SimpleNamespace(title="hololive-Dreams", width=1920, height=1080, _hWnd=2)
        w3 = SimpleNamespace(title="hololive-dreams", width=1280, height=720, _hWnd=3)

        with patch("pygetwindow.getAllWindows", return_value=[w1, w2, w3]):
            matched = window_control.find_game_window()
            # Must match exact "hololive-Dreams" (case-insensitive) and pick largest
            self.assertEqual(matched._hWnd, 2)

    def test_find_game_window_none_found(self):
        w1 = SimpleNamespace(title="Not The Game", width=1000, height=800, _hWnd=1)
        with patch("pygetwindow.getAllWindows", return_value=[w1]):
            self.assertIsNone(window_control.find_game_window())

    def test_safe_click_coordinate_scaling(self):
        # Test coordinate mapping from 1920x1080 normalized frame to client window
        window_control._capture_context = {"hwnd": 12345, "width": 1280, "height": 720}

        with patch.object(window_control, "_bring_game_to_front", return_value=True), \
             patch.object(window_control._user32, "GetForegroundWindow", return_value=12345), \
             patch.object(window_control, "_get_client_geometry", return_value=(100, 200, 1280, 720)), \
             patch("random.randint", return_value=0), \
             patch("pydirectinput.moveTo") as mock_move, \
             patch("pydirectinput.mouseDown") as mock_down, \
             patch("pydirectinput.mouseUp") as mock_up:

            # (960, 540) in 1920x1080 should map to center of 1280x720: (640, 360) + origin (100, 200) = (740, 560)
            res = window_control.safe_click(960, 540)
            self.assertTrue(res)
            mock_move.assert_called_once_with(740, 560)
            mock_down.assert_called_once()
            mock_up.assert_called_once()

    def test_safe_click_aborts_when_not_foreground(self):
        window_control._capture_context = {"hwnd": 12345, "width": 1280, "height": 720}

        with patch.object(window_control, "_bring_game_to_front", return_value=True), \
             patch.object(window_control._user32, "GetForegroundWindow", return_value=99999), \
             patch("pydirectinput.mouseDown") as mock_down:

            res = window_control.safe_click(960, 540)
            self.assertFalse(res)
            mock_down.assert_not_called()


if __name__ == '__main__':
    unittest.main()
