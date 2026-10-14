import unittest
import tkinter as tk
from src.ui.widgets import ModernMenu


class TestModernMenu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.root = tk.Tk()
            cls.root.withdraw()
            cls.root.theme_mode = "dark"
            cls.root.theme_palette = {"is_dark": True}
        except tk.TclError:
            cls.root = None

    @classmethod
    def tearDownClass(cls):
        if cls.root:
            cls.root.destroy()

    def setUp(self):
        if not self.root:
            self.skipTest("Tkinter display not available")

    def test_modern_menu_api_compatibility(self):
        menubar = ModernMenu(self.root)
        menu = ModernMenu(menubar, tearoff=0)
        menu.add_command(label="Test Command")
        menu.add_separator()
        menu.add_checkbutton(label="Test Check")
        menu.add_radiobutton(label="Test Radio", value=1)

        self.assertEqual(menu.index("end"), 3)
        self.assertEqual(menu.type(0), "command")
        self.assertEqual(menu.type(1), "separator")
        self.assertEqual(menu.type(2), "checkbutton")
        self.assertEqual(menu.type(3), "radiobutton")
        self.assertEqual(menu.entrycget(0, "label"), "Test Command")

    def test_modern_menu_post_unpost(self):
        menu = ModernMenu(self.root, tearoff=0)
        invoked = []
        menu.add_command(label="Action", command=lambda: invoked.append(True))
        
        menu.post(50, 50)
        self.assertIsNotNone(menu._popup_window)
        self.assertIn(menu._popup_window, ModernMenu._active_popups)

        # Unpost
        menu.unpost()
        self.assertIsNone(menu._popup_window)
        self.assertNotIn(menu._popup_window, ModernMenu._active_popups)

    def test_modern_menu_multimonitor_work_area_clamping(self):
        from unittest.mock import patch
        menu = ModernMenu(self.root, tearoff=0)
        menu.add_command(label="Multi-Monitor Item")

        # Simulate secondary monitor to the right: [2560, 0, 5120, 1440]
        with patch("src.ui.platform.get_monitor_work_area", return_value=(2560, 0, 5120, 1440)):
            menu.post(2700, 100)
            self.assertIsNotNone(menu._popup_window)
            self.assertGreaterEqual(menu._popup_window.winfo_x(), 2560)
            menu.unpost()

        # Simulate secondary monitor to the left: [-1920, 0, 0, 1080]
        with patch("src.ui.platform.get_monitor_work_area", return_value=(-1920, 0, 0, 1080)):
            menu.post(-1500, 100)
            self.assertIsNotNone(menu._popup_window)
            self.assertLess(menu._popup_window.winfo_x(), 0)
            menu.unpost()

    def test_get_monitor_work_area_query(self):
        from src.ui.platform import get_monitor_work_area
        area = get_monitor_work_area(100, 100)
        self.assertIsNotNone(area)
        self.assertEqual(len(area), 4)
        left, top, right, bottom = area
        self.assertLess(left, right)
        self.assertLess(top, bottom)

    def test_modern_menu_checkbutton_toggle_click(self):
        menu = ModernMenu(self.root, tearoff=0)
        var = tk.BooleanVar(value=False)
        invoked_values = []
        menu.add_checkbutton(
            label="Toggle Debug",
            variable=var,
            command=lambda: invoked_values.append(var.get()),
        )

        menu.post(50, 50)
        popup = menu._popup_window
        popup.update()
        item_frame = popup.winfo_children()[0].winfo_children()[0]
        item_frame.event_generate("<Button-1>", x=5, y=5)
        popup.update()

        self.assertTrue(var.get())
        self.assertEqual(invoked_values, [True])

        # Second click should toggle back to False
        menu.post(50, 50)
        popup = menu._popup_window
        popup.update()
        item_frame = popup.winfo_children()[0].winfo_children()[0]
        item_frame.event_generate("<Button-1>", x=5, y=5)
        popup.update()

        self.assertFalse(var.get())
        self.assertEqual(invoked_values, [True, False])

    def test_modern_menu_radiobutton_select_click(self):
        menu = ModernMenu(self.root, tearoff=0)
        var = tk.StringVar(value="opt1")
        invoked_values = []
        menu.add_radiobutton(label="Opt 1", variable=var, value="opt1", command=lambda: invoked_values.append(var.get()))
        menu.add_radiobutton(label="Opt 2", variable=var, value="opt2", command=lambda: invoked_values.append(var.get()))

        menu.post(50, 50)
        popup = menu._popup_window
        popup.update()
        item_frame2 = popup.winfo_children()[0].winfo_children()[1]
        item_frame2.event_generate("<Button-1>", x=5, y=5)
        popup.update()

        self.assertEqual(var.get(), "opt2")
        self.assertEqual(invoked_values, ["opt2"])


if __name__ == "__main__":
    unittest.main()
