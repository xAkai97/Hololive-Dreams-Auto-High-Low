"""UI components and modules for Hololive Dreams Auto Bot."""
from src.ui.canvas_renderer import (
    discover_backgrounds,
    draw_glass_card,
    load_background_image,
)
from src.ui.dialogs import (
    export_benchmark_csv,
    export_benchmark_json,
    open_custom_parametric_dialog,
    open_settings_dialog,
    show_benchmark_results_dialog,
    show_help_about,
    show_help_rules,
    show_help_strategies,
    show_settlement_modal,
)
from src.ui.log_manager import (
    clean_old_logs,
    is_trivial_log_content,
    load_saved_stats,
    rotate_previous_log,
)
from src.ui.platform import (
    THEME_PALETTES,
    get_available_ui_font_families,
    get_locale_font_family,
    get_monitor_work_area,
    is_windows_dark_mode,
    set_window_dark_titlebar,
)
from src.ui.widgets import (
    CanvasCheckbutton,
    CanvasHeaderLabel,
    CanvasSegmentedPill,
    DummyFrame,
    ModernMenu,
    RedirectText,
    SegmentProxy,
    ToolTip,
)

__all__ = [
    "THEME_PALETTES",
    "CanvasCheckbutton",
    "CanvasHeaderLabel",
    "CanvasSegmentedPill",
    "DummyFrame",
    "ModernMenu",
    "RedirectText",
    "SegmentProxy",
    "ToolTip",
    "clean_old_logs",
    "discover_backgrounds",
    "draw_glass_card",
    "export_benchmark_csv",
    "export_benchmark_json",
    "get_available_ui_font_families",
    "get_locale_font_family",
    "get_monitor_work_area",
    "is_trivial_log_content",
    "is_windows_dark_mode",
    "load_background_image",
    "load_saved_stats",
    "open_custom_parametric_dialog",
    "open_settings_dialog",
    "rotate_previous_log",
    "set_window_dark_titlebar",
    "show_benchmark_results_dialog",
    "show_help_about",
    "show_help_rules",
    "show_help_strategies",
    "show_settlement_modal",
]
