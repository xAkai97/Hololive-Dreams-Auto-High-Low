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


if __name__ == "__main__":
    unittest.main()
