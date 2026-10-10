"""UI components and modules for Hololive Dreams Auto Bot."""
from src.ui.platform import (
    is_windows_dark_mode,
    set_window_dark_titlebar,
    get_locale_font_family,
    THEME_PALETTES,
)
from src.ui.widgets import (
    DummyFrame,
    CanvasHeaderLabel,
    CanvasCheckbutton,
    ToolTip,
    RedirectText,
    ModernMenu,
)
from src.ui.log_manager import (
    is_trivial_log_content,
    clean_old_logs,
    rotate_previous_log,
    load_saved_stats,
)
from src.ui.canvas_renderer import (
    discover_backgrounds,
    load_background_image,
    draw_glass_card,
)
from src.ui.dialogs import (
    show_help_rules,
    show_help_strategies,
    show_help_about,
    open_settings_dialog,
    open_custom_parametric_dialog,
    show_benchmark_results_dialog,
    export_benchmark_csv,
    export_benchmark_json,
    show_settlement_modal,
)

__all__ = [
    "is_windows_dark_mode",
    "set_window_dark_titlebar",
    "get_locale_font_family",
    "THEME_PALETTES",
    "DummyFrame",
    "CanvasHeaderLabel",
    "CanvasCheckbutton",
    "ToolTip",
    "RedirectText",
    "ModernMenu",
    "is_trivial_log_content",
    "clean_old_logs",
    "rotate_previous_log",
    "load_saved_stats",
    "discover_backgrounds",
    "load_background_image",
    "draw_glass_card",
    "show_help_rules",
    "show_help_strategies",
    "show_help_about",
    "open_settings_dialog",
    "open_custom_parametric_dialog",
    "show_benchmark_results_dialog",
    "export_benchmark_csv",
    "export_benchmark_json",
    "show_settlement_modal",
]
