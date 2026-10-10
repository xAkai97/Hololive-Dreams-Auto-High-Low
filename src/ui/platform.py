"""Platform-specific utilities, theming, and font detection."""
import ctypes


def is_windows_dark_mode() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            val, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return val == 0
    except Exception:
        return False


def set_window_dark_titlebar(window, dark: bool):
    try:
        window.update_idletasks()
        hwnd = ctypes.windll.user32.GetAncestor(ctypes.c_void_p(window.winfo_id()), 2)
        if not hwnd:
            hwnd = window.winfo_id()
        val = ctypes.c_int(1 if dark else 0)
        for attr in (20, 19):
            if ctypes.windll.dwmapi.DwmSetWindowAttribute(
                ctypes.c_void_p(hwnd),
                ctypes.c_uint(attr),
                ctypes.byref(val),
                ctypes.sizeof(val)
            ) == 0:
                break
        try:
            ctypes.windll.uxtheme[133](ctypes.c_void_p(hwnd), ctypes.c_bool(dark))
            ctypes.windll.uxtheme[135](2 if dark else 3)
            ctypes.windll.uxtheme[136]()
        except Exception:
            pass
    except Exception:
        pass


def get_locale_font_family(lang: str = "en") -> str:
    """Return the optimal system UI font family based on locale."""
    code = (lang or "en").lower().replace("-", "_")
    try:
        from tkinter import font as tkfont
        available = set(tkfont.families())
    except Exception:
        available = set()

    if code.startswith("ja"):
        for cand in ("Yu Gothic UI", "Meiryo UI", "Segoe UI"):
            if cand in available:
                return cand
    elif code.startswith("zh") or code.startswith("tw"):
        for cand in ("Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI"):
            if cand in available:
                return cand
    else:
        for cand in ("Segoe UI", "Tahoma", "Arial"):
            if cand in available:
                return cand

    return "Segoe UI" if "Segoe UI" in available else "TkDefaultFont"


THEME_PALETTES = {
    "light": {
        "name": "light",
        "is_dark": False,
        "bg_plain": (255, 255, 255, 255),
        "bg_plain_hex": "#FFFFFF",
        "card_fill_rgb": (255, 255, 255),
        "card_border": (226, 232, 240, 255),
        "text_primary": "#0F172A",
        "text_secondary": "#334155",
        "text_desc": "#334155",
        "header_fill": "#334155",
        "log_bg": "#FFFFFF",
        "log_fg": "#0F172A",
        "status_idle": "#0F172A",
        "status_running": "#16A34A",
        "status_stopping": "#D97706",
        "status_crashed": "#DC2626",
    },
    "dark": {
        "name": "dark",
        "is_dark": True,
        "bg_plain": (24, 24, 27, 255),
        "bg_plain_hex": "#18181B",
        "card_fill_rgb": (39, 39, 42),
        "card_border": (63, 63, 70, 255),
        "text_primary": "#F8FAFC",
        "text_secondary": "#E2E8F0",
        "text_desc": "#CBD5E1",
        "header_fill": "#93C5FD",
        "log_bg": "#18181B",
        "log_fg": "#E2E8F0",
        "status_idle": "#F8FAFC",
        "status_running": "#4ADE80",
        "status_stopping": "#FBBF24",
        "status_crashed": "#F87171",
    },
}
