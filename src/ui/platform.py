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


def get_available_ui_font_families() -> list[str]:
    """Return an ordered list of clean UI font families available on the system."""
    try:
        from tkinter import font as tkfont
        raw_families = sorted(set(tkfont.families()))
    except Exception:
        raw_families = []

    priority = [
        "Segoe UI",
        "Microsoft YaHei UI",
        "Microsoft YaHei",
        "Yu Gothic UI",
        "Meiryo UI",
        "Malgun Gothic",
        "Arial",
        "Tahoma",
        "Verdana",
        "Calibri",
        "Consolas",
    ]
    seen = set()
    result = []
    avail = set(raw_families)
    for p in priority:
        if p in avail and p not in seen:
            seen.add(p)
            result.append(p)
    for f in raw_families:
        if not f.startswith("@") and f not in seen:
            seen.add(f)
            result.append(f)
    return result


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
        "badge_idle_bg": "#F1F5F9",
        "badge_idle_border": "#CBD5E1",
        "badge_idle_fg": "#475569",
        "badge_idle_dot": "#64748B",
        "badge_running_bg": "#DCFCE7",
        "badge_running_border": "#86EFAC",
        "badge_running_fg": "#15803D",
        "badge_running_dot": "#16A34A",
        "badge_stopping_bg": "#FEF3C7",
        "badge_stopping_border": "#FCD34D",
        "badge_stopping_fg": "#B45309",
        "badge_stopping_dot": "#D97706",
        "badge_crashed_bg": "#FEE2E2",
        "badge_crashed_border": "#FCA5A5",
        "badge_crashed_fg": "#B91C1C",
        "badge_crashed_dot": "#DC2626",
        "profit_pos": "#15803D",
        "profit_neg": "#DC2626",
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
        "badge_idle_bg": "#1E293B",
        "badge_idle_border": "#334155",
        "badge_idle_fg": "#CBD5E1",
        "badge_idle_dot": "#94A3B8",
        "badge_running_bg": "#064E3B",
        "badge_running_border": "#059669",
        "badge_running_fg": "#4ADE80",
        "badge_running_dot": "#22C55E",
        "badge_stopping_bg": "#451A03",
        "badge_stopping_border": "#B45309",
        "badge_stopping_fg": "#FBBF24",
        "badge_stopping_dot": "#F59E0B",
        "badge_crashed_bg": "#450A0A",
        "badge_crashed_border": "#DC2626",
        "badge_crashed_fg": "#F87171",
        "badge_crashed_dot": "#EF4444",
        "profit_pos": "#10B981",
        "profit_neg": "#EF4444",
    },
}


def get_monitor_work_area(x: int, y: int) -> tuple[int, int, int, int] | None:
    """Return the work area (left, top, right, bottom) of the monitor containing (x, y).

    Returns None if unable to query or on non-Windows platforms.
    """
    try:
        from ctypes import wintypes

        class POINT(ctypes.Structure):
            _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

        class RECT(ctypes.Structure):
            _fields_ = [
                ("left", wintypes.LONG),
                ("top", wintypes.LONG),
                ("right", wintypes.LONG),
                ("bottom", wintypes.LONG),
            ]

        class MONITORINFO(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", RECT),
                ("rcWork", RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        pt = POINT(int(x), int(y))
        # MONITOR_DEFAULTTONEAREST = 2
        hmon = ctypes.windll.user32.MonitorFromPoint(pt, 2)
        if hmon:
            mi = MONITORINFO()
            mi.cbSize = ctypes.sizeof(MONITORINFO)
            if ctypes.windll.user32.GetMonitorInfoW(hmon, ctypes.byref(mi)):
                return (
                    int(mi.rcWork.left),
                    int(mi.rcWork.top),
                    int(mi.rcWork.right),
                    int(mi.rcWork.bottom),
                )
    except Exception:
        pass
    return None
