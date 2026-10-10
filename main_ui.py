import ctypes

# Configure DPI before Tk or any capture/input library creates a window. This
# keeps template coordinates aligned on scaled and multi-monitor desktops.
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass

try:
    # SetPreferredAppMode (ordinal 135): 2 = ForceDark
    # Instructs Windows 10/11 Desktop Window Manager to render Win32 popup
    # menus with dark backgrounds and text. Note: on Windows 10, the native
    # Win32 popup menu non-client border outline is still rendered white/light
    # by the OS DWM for TrackPopupMenu.
    ctypes.windll.uxtheme[135](2)
    ctypes.windll.uxtheme[136]()
except Exception:
    pass

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import sys
import os
import csv
from pathlib import Path
import json
import time
import datetime
import re
import queue
from PIL import Image, ImageTk, ImageDraw
import keyboard
import webbrowser

# Ensure src directory is accessible when running from source or bundle
SRC_DIR = Path(__file__).resolve().parent / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import auto_bot
import localization
from strategies import STRATEGY_REGISTRY

STRATEGY_KEYS: tuple[str, ...] = tuple(STRATEGY_REGISTRY.keys())

# Must be executed before window creation: Notify Windows this is an independent app to bind its taskbar icon
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("hololive.dreams.autobot.v1")
except Exception:
    pass

TRANSLATIONS = localization.TRANSLATIONS


from src.ui import (
    is_windows_dark_mode,
    set_window_dark_titlebar,
    get_locale_font_family,
    THEME_PALETTES,
    DummyFrame,
    CanvasHeaderLabel,
    CanvasCheckbutton,
    ToolTip,
    RedirectText,
    ModernMenu,
    is_trivial_log_content,
    clean_old_logs,
    rotate_previous_log,
    load_saved_stats,
    discover_backgrounds,
    load_background_image,
    draw_glass_card,
    show_help_rules as ui_show_help_rules,
    show_help_strategies as ui_show_help_strategies,
    show_help_about as ui_show_help_about,
    open_settings_dialog as ui_open_settings_dialog,
    open_custom_parametric_dialog as ui_open_custom_parametric_dialog,
    show_benchmark_results_dialog as ui_show_benchmark_results_dialog,
    export_benchmark_csv as ui_export_benchmark_csv,
    export_benchmark_json as ui_export_benchmark_json,
    show_settlement_modal as ui_show_settlement_modal,
)


class HololiveBotUI(tk.Tk):
    def __init__(self):
        saved_config = auto_bot.load_config()
        self.current_lang = saved_config.get("language", localization.get_lang())
        localization.set_lang(self.current_lang)

        self.log_retention_days = int(saved_config.get("log_retention_days", 14))
        self.log_max_size_mb = int(saved_config.get("log_max_size_mb", 20))
        self.settlement_recovery_mode = str(saved_config.get("settlement_recovery_mode", "auto"))
        self.settlement_ocr_timeout = float(saved_config.get("settlement_ocr_timeout", 8.0))

        rotate_previous_log(max_days=self.log_retention_days, max_size_mb=self.log_max_size_mb, lang=self.current_lang)
        try:
            log_file = auto_bot.APP_DIR / "log.txt"
            start_time_str = time.strftime("%Y-%m-%d %H:%M:%S")
            if log_file.exists() and log_file.stat().st_size > 0:
                with open(log_file, "a", encoding="utf-8", errors="replace") as f:
                    f.write(f"\n=== UI Session Resumed: {start_time_str} ===\n")
            else:
                log_file.write_text(f"=== UI Session Started: {start_time_str} ===\n", encoding="utf-8")
        except Exception:
            pass

        super().__init__()

        self.bot_thread = None
        self.is_running = False
        self.font_family = get_locale_font_family(self.current_lang)
        self.show_bg = False

        self.current_coins, self.current_fails, self.current_profit = load_saved_stats()

        self.title(TRANSLATIONS.get(self.current_lang, {}).get("title", "Hololive Dreams Auto Bot"))
        # Prefer PNG icon so taskbar icon never falls back to blank placeholder
        try:
            icon_candidates = [
                auto_bot.RESOURCE_DIR / "assets" / "icons" / "icon_transparent.png",
                auto_bot.RESOURCE_DIR / "icon_transparent.png",
                auto_bot.RESOURCE_DIR / "assets" / "icons" / "icon.png",
                auto_bot.RESOURCE_DIR / "icon.png",
                auto_bot.RESOURCE_DIR / "assets" / "icons" / "icon.ico",
                auto_bot.RESOURCE_DIR / "icon.ico",
            ]
            for candidate in icon_candidates:
                if candidate.exists():
                    if candidate.suffix.lower() == ".ico":
                        self.iconbitmap(str(candidate))
                    else:
                        self._app_icon = ImageTk.PhotoImage(file=str(candidate))
                        self.iconphoto(True, self._app_icon)
                    break
        except Exception as e:
            print(f"[Warning] Failed to load application icon: {e}")

        self.geometry("480x850")
        self.minsize(420, 680)
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.last_w = 0
        self.last_h = 0

        self.menubar_frame = tk.Frame(self, bg="#18181B")
        self.menubar_frame.pack(side="top", fill="x")

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.bg_candidates = self._discover_backgrounds()
        saved_bg = saved_config.get("background_index", -1)
        self.bg_index = saved_bg if (-1 <= saved_bg < len(self.bg_candidates)) else -1
        self.theme_mode = saved_config.get("theme_mode", "system")
        if self.theme_mode not in ("system", "light", "dark"):
            self.theme_mode = "system"
        self.theme_var = tk.StringVar(value=self.theme_mode)
        self.field_box_opacity = max(0, min(100, int(saved_config.get("field_box_opacity", 30))))
        self.show_log = bool(saved_config.get("show_log", False))
        self.var_show_log = tk.BooleanVar(value=self.show_log)
        self.original_bg = None
        self._load_current_bg()

        self.bg_id = self.canvas.create_image(0, 0, anchor="nw")
        self.stats_card_id = self.canvas.create_rectangle(0, 0, 0, 0, fill="#FFFFFF", outline="#E2E8F0", width=1)
        self.settings_card_id = self.canvas.create_rectangle(0, 0, 0, 0, fill="#FFFFFF", outline="#E2E8F0", width=1)

        self.style = ttk.Style(self)
        for theme_name in ("vista", "clam"):
            try:
                self.style.theme_use(theme_name)
                break
            except Exception:
                pass
        self.style.configure("TButton", font=(self.font_family, 9, "bold"), padding=(6, 3))
        self.style.configure("Hotkey.TButton", font=(self.font_family, 10, "bold"), padding=(8, 2))
        self.style.configure("Tab.TButton", font=(self.font_family, 9, "bold"), padding=(4, 3))
        self.style.configure("ActiveTab.TButton", font=(self.font_family, 9, "bold"), padding=(4, 3))
        self.style.configure("Config.TButton", font=(self.font_family, 9, "bold"), padding=(4, 2))
        self.style.configure("ModifierDrawer.TButton", font=(self.font_family, 9, "bold"), padding=(8, 4))
        self.style.configure("ModifierCard.TFrame", background="#FFFFFF")
        self.style.configure("ModifierCard.TLabel", background="#FFFFFF")
        self.style.configure("ModifierCard.TCheckbutton", background="#FFFFFF")

        font_normal = (self.font_family, 12, "bold")
        font_log = (self.font_family, 12, "bold")

        self.title_id = self.canvas.create_text(0, 0, text="", state="hidden")

        self.lang_label_id = self.canvas.create_text(0, 0, text="", state="hidden")
        available_langs = localization.load_external_locales()
        self.lang_keys = [code for code, _ in available_langs]
        lang_values = [name for _, name in available_langs]
        self.combo_lang = ttk.Combobox(self, values=lang_values, state="readonly")
        initial_idx = self.lang_keys.index(self.current_lang) if self.current_lang in self.lang_keys else 0
        self.combo_lang.current(initial_idx)
        self.current_lang = self.lang_keys[initial_idx]
        localization.set_lang(self.current_lang)
        self.combo_lang.bind("<<ComboboxSelected>>", self.change_language)
        self.combo_window = self.canvas.create_window(0, 0, window=self.combo_lang, anchor="e", state="hidden")

        self.lbl_setting_bg_id = self.canvas.create_text(0, 0, text="", state="hidden")
        self.combo_bg = ttk.Combobox(self, state="readonly")
        self.combo_bg.bind("<<ComboboxSelected>>", self.on_bg_combo_change)
        self.combo_bg_win = self.canvas.create_window(0, 0, window=self.combo_bg, anchor="e", state="hidden")

        self.bg_var = tk.IntVar(value=self._get_bg_var_value())
        self.lang_var = tk.StringVar(value=self.current_lang)

        self.hotkey_label_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")
        saved_hotkey = saved_config.get("hotkey", "INSERT")
        self.current_hotkey = saved_hotkey if saved_hotkey else "INSERT"
        self.is_listening = False

        self.btn_hotkey = ttk.Button(self, text=self.current_hotkey, command=self.start_listen_hotkey, style="Hotkey.TButton")
        self.hotkey_window = self.canvas.create_window(0, 0, window=self.btn_hotkey, anchor="e")

        keyboard.add_hotkey(self.current_hotkey, lambda: self.after(0, self.stop_bot))

        # Persistent user settings
        saved_target = saved_config.get("target_limit")
        self.target_limit = 20000 if (saved_target is None or saved_target == 19800) else int(saved_target)
        self.ticket_cost = int(saved_config.get("ticket_cost", 50))
        self.param_min_win_rate = int(saved_config.get("param_min_win_rate", 60))
        saved_cushion = saved_config.get("param_cushion_target")
        self.param_cushion_target = 19800 if (saved_cushion is None or saved_cushion == 20000) else int(saved_cushion)
        self.param_sprint_target = int(saved_config.get("param_sprint_target", 10000))
        self.param_max_doubles = int(saved_config.get("param_max_doubles", 10))
        self.param_drop_seven_eight = bool(saved_config.get("param_drop_seven_eight", False))
        self.modifiers_expanded = bool(saved_config.get("modifiers_expanded", True))
        self.cat_cards_expanded = bool(saved_config.get("mod_cat_cards_expanded", True))
        self.cat_bail_expanded = bool(saved_config.get("mod_cat_bail_expanded", True))
        self.cat_prog_expanded = bool(saved_config.get("mod_cat_prog_expanded", True))
        self.mod_fast_build = bool(saved_config.get("mod_fast_build", False))
        self.mod_drop_78 = bool(saved_config.get("mod_drop_78", self.param_drop_seven_eight))
        self.mod_drop_6789 = bool(saved_config.get("mod_drop_6789", False))
        self.mod_drop_8 = bool(saved_config.get("mod_drop_8", False))
        self.mod_free_roll = bool(saved_config.get("mod_free_roll", False))
        self.mod_sprint_floor = bool(saved_config.get("mod_sprint_floor", False))
        self.mod_mega_sprint = bool(saved_config.get("mod_mega_sprint", False))
        self.var_mod_fast_build = tk.BooleanVar(value=self.mod_fast_build)
        self.var_mod_drop_78 = tk.BooleanVar(value=self.mod_drop_78)
        self.var_mod_drop_6789 = tk.BooleanVar(value=self.mod_drop_6789)
        self.var_mod_drop_8 = tk.BooleanVar(value=self.mod_drop_8)
        self.var_mod_free_roll = tk.BooleanVar(value=self.mod_free_roll)
        self.var_mod_sprint_floor = tk.BooleanVar(value=self.mod_sprint_floor)
        self.var_mod_mega_sprint = tk.BooleanVar(value=self.mod_mega_sprint)
        self.debug_logging = bool(saved_config.get("debug_logging", False))
        self.var_debug_logging = tk.BooleanVar(value=self.debug_logging)
        default_a2 = saved_config.get("opp_a2", True)
        default_3k = saved_config.get("opp_3k", False)
        default_4q = saved_config.get("opp_4q", False)
        default_5j = saved_config.get("opp_5j", False)
        default_610 = saved_config.get("opp_610", False)
        default_79 = saved_config.get("opp_79", False)
        default_8 = saved_config.get("opp_8", False)
        self.var_opp_a2 = tk.BooleanVar(value=bool(default_a2))
        self.var_opp_3k = tk.BooleanVar(value=bool(default_3k))
        self.var_opp_4q = tk.BooleanVar(value=bool(default_4q))
        self.var_opp_5j = tk.BooleanVar(value=bool(default_5j))
        self.var_opp_610 = tk.BooleanVar(value=bool(default_610))
        self.var_opp_79 = tk.BooleanVar(value=bool(default_79))
        self.var_opp_8 = tk.BooleanVar(value=bool(default_8))

        self.last_benchmark_results: list[dict] = []
        self.is_simulating = False
        self.tooltips: dict[str, ToolTip] = {}

        # --- Top Menu Bar ---
        self.menubar = ModernMenu(self)
        self.file_menu = ModernMenu(self.menubar, tearoff=0)
        self.open_folders_menu = ModernMenu(self.file_menu, tearoff=0)
        self.logs_menu = ModernMenu(self.menubar, tearoff=0)
        self.settings_menu = ModernMenu(self.menubar, tearoff=0)
        self.bg_menu = ModernMenu(self.menubar, tearoff=0)
        self.lang_menu = ModernMenu(self.menubar, tearoff=0)
        self.sim_menu = ModernMenu(self.menubar, tearoff=0)
        self.help_menu = ModernMenu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="File", menu=self.file_menu)
        self.menubar.add_cascade(label="Logs", menu=self.logs_menu)
        self.menubar.add_cascade(label="Settings", menu=self.settings_menu)
        self.menubar.add_cascade(label="Background", menu=self.bg_menu)
        self.menubar.add_cascade(label="Language", menu=self.lang_menu)
        self.menubar.add_cascade(label="Help", menu=self.help_menu)

        self._active_menu_key: str | None = None
        self.menu_buttons: dict[str, tk.Label] = {}
        self.menu_targets: dict[str, tk.Menu] = {
            "file": self.file_menu,
            "logs": self.logs_menu,
            "settings": self.settings_menu,
            "bg": self.bg_menu,
            "lang": self.lang_menu,
            "help": self.help_menu,
        }
        for key, default_lbl in (
            ("file", "File"),
            ("logs", "Logs"),
            ("settings", "Settings"),
            ("bg", "Background"),
            ("lang", "Language"),
            ("help", "Help"),
        ):
            lbl = tk.Label(
                self.menubar_frame,
                text=default_lbl,
                bg="#18181B",
                fg="#F8FAFC",
                font=(self.font_family, 9),
                padx=8,
                pady=2,
                cursor="hand2",
            )
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, k=key: self._on_menu_button_click(k))
            lbl.bind("<Enter>", lambda e, k=key: self._on_menu_button_enter(k))
            lbl.bind("<Leave>", lambda e, k=key: self._on_menu_button_leave(k))
            self.menu_buttons[key] = lbl

        # --- Tab Switcher Buttons (Auto Bot & Simulation) ---
        self.current_tab = "bot"
        self.tab_btn_bot = ttk.Button(self, command=lambda: self.switch_tab("bot"))
        self.tab_btn_sim = ttk.Button(self, command=lambda: self.switch_tab("sim"))
        self.tab_btn_settings = ttk.Button(self, command=lambda: self.switch_tab("settings"))
        self.tab_win_bot = self.canvas.create_window(0, 0, window=self.tab_btn_bot)
        self.tab_win_sim = self.canvas.create_window(0, 0, window=self.tab_btn_sim)
        self.tab_win_settings = self.canvas.create_window(0, 0, window=self.tab_btn_settings, state="hidden")

        # --- Bot Tab Widgets ---
        self.status_id = self.canvas.create_text(0, 0, font=font_normal, fill=self.theme_palette.get("status_idle", "#0F172A"), anchor="w")

        # Row 1: Coins
        self.coins_label_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")
        self.entry_coins = ttk.Entry(self, width=8, justify="center", font=(self.font_family, 10, "bold"))
        self.entry_coins.insert(0, str(self.current_coins))
        self.entry_coins.bind("<FocusOut>", self.on_stats_manual_edit)
        self.entry_coins.bind("<Return>", self.on_stats_manual_edit)
        self.entry_coins_win = self.canvas.create_window(0, 0, window=self.entry_coins, anchor="w")
        self.coins_max_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w", text=f"/ {self.target_limit}")

        # Row 2: Fails & Net Profit
        self.fails_label_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")
        self.entry_fails = ttk.Entry(self, width=5, justify="center", font=(self.font_family, 10, "bold"))
        self.entry_fails.insert(0, str(self.current_fails))
        self.entry_fails.bind("<FocusOut>", self.on_stats_manual_edit)
        self.entry_fails.bind("<Return>", self.on_stats_manual_edit)
        self.entry_fails_win = self.canvas.create_window(0, 0, window=self.entry_fails, anchor="w")
        self.profit_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")

        self.btn_start = ttk.Button(self, command=self.start_bot)
        self.btn_stop = ttk.Button(self, command=self.stop_bot, state="disabled")
        self.btn_bg = ttk.Button(self, command=self.toggle_bg)
        self.btn_exit = ttk.Button(self, command=self.destroy)

        self.btn_start_win = self.canvas.create_window(0, 0, window=self.btn_start)
        self.btn_stop_win = self.canvas.create_window(0, 0, window=self.btn_stop)
        self.btn_bg_win = self.canvas.create_window(0, 0, window=self.btn_bg, state="hidden")
        self.btn_exit_win = self.canvas.create_window(0, 0, window=self.btn_exit, state="hidden")

        self.combo_strategy = ttk.Combobox(self, state='readonly',
                                           values=localization.get_strategy_labels(self.current_lang))
        saved_strat = saved_config.get("strategy_index", 0)
        saved_key = saved_config.get("strategy_key")
        if saved_key in STRATEGY_KEYS:
            initial_strat = STRATEGY_KEYS.index(saved_key)
        else:
            try:
                initial_strat = max(0, min(len(STRATEGY_KEYS) - 1, int(saved_strat)))
            except (ValueError, TypeError):
                initial_strat = 0
        self.combo_strategy.current(initial_strat)
        self.combo_strategy.bind("<<ComboboxSelected>>", self.on_strategy_change)
        self.strategy_window = self.canvas.create_window(0, 0, window=self.combo_strategy, anchor='nw')
        self.active_mode = STRATEGY_KEYS[initial_strat]

        self.btn_config_strat = ttk.Button(self, command=self.open_custom_parametric_dialog, style="Config.TButton")
        self.btn_config_strat_win = self.canvas.create_window(0, 0, window=self.btn_config_strat, anchor='nw')

        font_desc = (self.font_family, 9)
        self.strategy_desc_id = self.canvas.create_text(0, 0, font=font_desc, fill="#222222", anchor="nw")

        # Strategy Modifiers Drawer on Auto Bot Tab
        self.btn_toggle_modifiers = ttk.Button(
            self,
            text="",
            command=self.toggle_modifiers_drawer,
            style="ModifierDrawer.TButton",
            takefocus=False,
        )
        self.btn_toggle_modifiers_win = self.canvas.create_window(0, 0, window=self.btn_toggle_modifiers, anchor="nw")

        self.opp_frame = ttk.Frame(self)
        self.sec_cards_frame = DummyFrame()
        self.frame_cards_grid = DummyFrame()
        self.frame_cards1 = self.frame_cards_grid
        self.frame_cards2 = self.frame_cards_grid
        self.frame_cards = self.frame_cards_grid

        self.lbl_sec_cards = CanvasHeaderLabel(self.canvas)
        self.lbl_sec_cards.bind("<Button-1>", lambda e: self.toggle_mod_cat("cards"))

        self.chk_opp_a2 = CanvasCheckbutton(self.canvas, variable=self.var_opp_a2, command=self.on_opp_toggle)
        self.chk_opp_3k = CanvasCheckbutton(self.canvas, variable=self.var_opp_3k, command=self.on_opp_toggle)
        self.chk_opp_4q = CanvasCheckbutton(self.canvas, variable=self.var_opp_4q, command=self.on_opp_toggle)
        self.chk_opp_5j = CanvasCheckbutton(self.canvas, variable=self.var_opp_5j, command=self.on_opp_toggle)
        self.chk_opp_610 = CanvasCheckbutton(self.canvas, variable=self.var_opp_610, command=self.on_opp_toggle)
        self.chk_opp_79 = CanvasCheckbutton(self.canvas, variable=self.var_opp_79, command=self.on_opp_toggle)
        self.chk_opp_8 = CanvasCheckbutton(self.canvas, variable=self.var_opp_8, command=self.on_opp_toggle)

        # --- Section 2: Defensive Bailouts ---
        self.sec_bail_frame = DummyFrame()
        self.frame_bail_grid = DummyFrame()
        self.frame_bail = self.frame_bail_grid
        self.frame_mods = self.frame_bail_grid

        self.lbl_sec_bail = CanvasHeaderLabel(self.canvas)
        self.lbl_sec_bail.bind("<Button-1>", lambda e: self.toggle_mod_cat("bail"))

        self.chk_mod_drop_78 = CanvasCheckbutton(self.canvas, variable=self.var_mod_drop_78, command=self.on_modifier_toggle)
        self.chk_mod_drop_6789 = CanvasCheckbutton(self.canvas, variable=self.var_mod_drop_6789, command=self.on_modifier_toggle)
        self.chk_mod_drop_8 = CanvasCheckbutton(self.canvas, variable=self.var_mod_drop_8, command=self.on_modifier_toggle)

        # --- Section 3: Progression & Sprint Phase ---
        self.sec_prog_frame = DummyFrame()
        self.frame_prog_grid = DummyFrame()
        self.frame_prog1 = self.frame_prog_grid
        self.frame_prog2 = self.frame_prog_grid

        self.lbl_sec_prog = CanvasHeaderLabel(self.canvas)
        self.lbl_sec_prog.bind("<Button-1>", lambda e: self.toggle_mod_cat("prog"))

        self.chk_mod_fast_build = CanvasCheckbutton(self.canvas, variable=self.var_mod_fast_build, command=self.on_modifier_toggle)
        self.chk_mod_free_roll = CanvasCheckbutton(self.canvas, variable=self.var_mod_free_roll, command=self.on_modifier_toggle)
        self.chk_mod_sprint_floor = CanvasCheckbutton(self.canvas, variable=self.var_mod_sprint_floor, command=self.on_modifier_toggle)
        self.chk_mod_mega_sprint = CanvasCheckbutton(self.canvas, variable=self.var_mod_mega_sprint, command=self.on_modifier_toggle)

        self._mod_canvas_widgets = [
            self.lbl_sec_cards,
            self.chk_opp_a2, self.chk_opp_3k, self.chk_opp_4q,
            self.chk_opp_5j, self.chk_opp_610, self.chk_opp_79, self.chk_opp_8,
            self.lbl_sec_bail,
            self.chk_mod_drop_78, self.chk_mod_drop_6789, self.chk_mod_drop_8,
            self.lbl_sec_prog,
            self.chk_mod_fast_build, self.chk_mod_free_roll,
            self.chk_mod_sprint_floor, self.chk_mod_mega_sprint,
        ]

        self.opp_frame_win = self.canvas.create_window(0, 0, window=self.opp_frame, anchor="nw")
        self.canvas.itemconfig(self.opp_frame_win, state="hidden")

        # --- Simulation Tab Specific Widgets ---
        font_setting = (self.font_family, 9, "bold")
        self.sim_days_label_id = self.canvas.create_text(0, 0, font=font_setting, fill="#111111", anchor="w")
        self.spin_sim_days = ttk.Spinbox(self, from_=10, to=2000, increment=50, width=8, justify="center")
        self.spin_sim_days.set("100")
        self.spin_sim_days_win = self.canvas.create_window(0, 0, window=self.spin_sim_days, anchor="w")

        self.btn_sim_run = ttk.Button(self, command=self.start_simulation)
        self.btn_sim_run_win = self.canvas.create_window(0, 0, window=self.btn_sim_run)
        self.btn_simulate = self.btn_sim_run
        self.btn_sim_compare = ttk.Button(self, command=self.start_full_benchmark)
        self.btn_sim_compare_win = self.canvas.create_window(0, 0, window=self.btn_sim_compare)
        self.btn_sim_export_csv = ttk.Button(self, command=self.export_benchmark_csv)
        self.btn_sim_export_csv_win = self.canvas.create_window(0, 0, window=self.btn_sim_export_csv, state="hidden")
        self.btn_sim_export_json = ttk.Button(self, command=self.export_benchmark_json)
        self.btn_sim_export_json_win = self.canvas.create_window(0, 0, window=self.btn_sim_export_json, state="hidden")
        self.btn_clear_logs = ttk.Button(self, command=self.clear_logs)
        self.btn_clear_logs_win = self.canvas.create_window(0, 0, window=self.btn_clear_logs, state="hidden")

        # --- Settings Tab Specific Widgets (Global Settings Only) ---
        font_setting = (self.font_family, 9, "bold")
        self.lbl_setting_title_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")

        self.lbl_setting_target_id = self.canvas.create_text(0, 0, font=font_setting, fill="#222222", anchor="w")
        self.entry_setting_target = ttk.Entry(self, width=12, justify="center")
        self.entry_setting_target.insert(0, str(self.target_limit))
        self.entry_setting_target_win = self.canvas.create_window(0, 0, window=self.entry_setting_target, anchor="e")

        self.lbl_setting_ticket_id = self.canvas.create_text(0, 0, font=font_setting, fill="#222222", anchor="w")
        self.entry_setting_ticket = ttk.Entry(self, width=12, justify="center")
        self.entry_setting_ticket.insert(0, str(self.ticket_cost))
        self.entry_setting_ticket_win = self.canvas.create_window(0, 0, window=self.entry_setting_ticket, anchor="e")

        self.lbl_setting_opacity_id = self.canvas.create_text(0, 0, font=font_setting, fill="#222222", anchor="w")
        self.frame_setting_opacity = ttk.Frame(self)
        self.scale_setting_opacity = ttk.Scale(
            self.frame_setting_opacity,
            from_=0,
            to=100,
            value=self.field_box_opacity,
            command=self._on_opacity_scale_change,
        )
        self.scale_setting_opacity.bind("<ButtonRelease-1>", self._on_opacity_scale_release)
        self.scale_setting_opacity.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.lbl_setting_opacity_val = ttk.Label(self.frame_setting_opacity, text=f"{self.field_box_opacity}%", width=5, font=font_setting)
        self.lbl_setting_opacity_val.pack(side="right")
        self.scale_setting_opacity_win = self.canvas.create_window(0, 0, window=self.frame_setting_opacity, anchor="e")

        self.btn_open_custom_dialog = ttk.Button(self, command=self.open_custom_parametric_dialog)
        self.btn_open_custom_dialog_win = self.canvas.create_window(0, 0, window=self.btn_open_custom_dialog, state="hidden")

        self.chk_setting_show_log = ttk.Checkbutton(
            self,
            variable=self.var_show_log,
            command=self.toggle_log_console,
        )
        self.chk_setting_show_log_win = self.canvas.create_window(0, 0, window=self.chk_setting_show_log, anchor="w")

        self.chk_setting_debug_log = ttk.Checkbutton(
            self,
            variable=self.var_debug_logging,
            command=self.on_debug_logging_toggle,
        )
        self.chk_setting_debug_log_win = self.canvas.create_window(0, 0, window=self.chk_setting_debug_log, anchor="w")

        self.btn_save_settings = ttk.Button(self, command=self.save_user_settings)
        self.btn_save_settings_win = self.canvas.create_window(0, 0, window=self.btn_save_settings)
        self.btn_restore_defaults = ttk.Button(self, command=self.restore_default_settings)
        self.btn_restore_defaults_win = self.canvas.create_window(0, 0, window=self.btn_restore_defaults)
        self.btn_back_to_bot = ttk.Button(self, command=lambda: self.switch_tab("bot"))
        self.btn_back_to_bot_win = self.canvas.create_window(0, 0, window=self.btn_back_to_bot)
        self.settings_feedback_id = self.canvas.create_text(0, 0, font=font_setting, fill="#007700", anchor="center")

        # --- Shared Log Console & Scrollbar ---
        self.log_lines = []
        self.log_max_lines = 13
        self.log_view_start = 0
        self.canvas_log_lines = []
        self.canvas_log_offset = None
        self._current_log_h = 120
        self._current_log_w = 400

        self.log_canvas_text_id = self.canvas.create_text(0, 0, font=font_log, fill="#111827", anchor="nw", state="hidden")

        self.log_text = tk.Text(
            self,
            font=font_log,
            wrap="word",
            relief="flat",
            bd=0,
            highlightthickness=0,
            bg="#FFFFFF",
            fg="#111827",
            padx=8,
            pady=6,
            selectbackground="#2563EB",
            selectforeground="#FFFFFF",
            state="disabled",
            cursor="xterm",
        )
        self.log_text_win = self.canvas.create_window(0, 0, window=self.log_text, anchor="nw")
        self.log_text_id = self.log_text_win

        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self._on_log_scroll)
        self.log_text.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar_win = self.canvas.create_window(0, 0, window=self.scrollbar, anchor="nw")

        def _select_all_log(e=None):
            self.log_text.tag_add("sel", "1.0", "end")
            return "break"

        def _copy_log_selection(e=None):
            try:
                selected = self.log_text.get("sel.first", "sel.last")
            except tk.TclError:
                selected = self.log_text.get("1.0", "end-1c")
            if not selected and hasattr(self, "canvas_log_lines") and self.canvas_log_lines:
                selected = "\n".join(self.canvas_log_lines)
            if selected:
                self.clipboard_clear()
                self.clipboard_append(selected)
            return "break"

        def _show_log_context_menu(e):
            menu = ModernMenu(self, tearoff=0)
            copy_label = localization.tr("menu_copy", self.current_lang) if hasattr(localization, "tr") else "Copy"
            sel_all_label = localization.tr("menu_select_all", self.current_lang) if hasattr(localization, "tr") else "Select All"
            save_label = localization.tr("menu_save_logs", self.current_lang) if hasattr(localization, "tr") else "Save Log to File..."
            clear_label = localization.tr("menu_clear_logs", self.current_lang) if hasattr(localization, "tr") else "Clear Logs"
            menu.add_command(label=f"{copy_label} (Ctrl+C)", command=_copy_log_selection)
            menu.add_command(label=f"{sel_all_label} (Ctrl+A)", command=_select_all_log)
            menu.add_separator()
            menu.add_command(label=save_label, command=self.save_logs_to_file)
            menu.add_command(label=clear_label, command=self.clear_logs)
            menu.tk_popup(e.x_root, e.y_root)

        self.log_text.bind("<Control-a>", _select_all_log)
        self.log_text.bind("<Control-A>", _select_all_log)
        self.log_text.bind("<Control-c>", _copy_log_selection)
        self.log_text.bind("<Control-C>", _copy_log_selection)
        self.log_text.bind("<Button-3>", _show_log_context_menu)
        self.canvas.tag_bind(self.log_canvas_text_id, "<Button-3>", _show_log_context_menu)
        self.canvas.tag_bind(self.log_canvas_text_id, "<Double-Button-1>", lambda e: _copy_log_selection())
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)
        self.bind("<Control-l>", lambda e: self.toggle_log_console())
        self.bind("<Control-L>", lambda e: self.toggle_log_console())

        # Tab widget membership lists for clean visibility switching
        self._bot_items = [
            self.hotkey_label_id,
            self.hotkey_window,
            self.stats_card_id,
            self.status_id,
            self.coins_label_id,
            self.entry_coins_win,
            self.coins_max_id,
            self.fails_label_id,
            self.entry_fails_win,
            self.profit_id,
            self.btn_start_win,
            self.btn_stop_win,
            self.btn_config_strat_win,
            self.btn_toggle_modifiers_win,
            self.opp_frame_win,
        ]

        self._sim_items = [
            self.btn_toggle_modifiers_win,
            self.opp_frame_win,
            self.sim_days_label_id,
            self.spin_sim_days_win,
            self.btn_sim_run_win,
            self.btn_sim_compare_win,
        ]

        self._settings_items = [
            self.settings_card_id,
            self.lbl_setting_title_id,
            self.lang_label_id,
            self.combo_window,
            self.lbl_setting_bg_id,
            self.combo_bg_win,
            self.lbl_setting_target_id,
            self.entry_setting_target_win,
            self.lbl_setting_ticket_id,
            self.entry_setting_ticket_win,
            self.lbl_setting_opacity_id,
            self.scale_setting_opacity_win,
            self.chk_setting_show_log_win,
            self.chk_setting_debug_log_win,
            self.btn_save_settings_win,
            self.btn_restore_defaults_win,
            self.btn_back_to_bot_win,
            self.settings_feedback_id,
        ]

        self.ui_queue = queue.Queue()
        self._is_destroyed = False
        self.last_game_date = auto_bot.get_game_date()
        self._process_ui_queue()

        self.sys_redirector = RedirectText(self)
        self.original_stdout = sys.stdout
        sys.stdout = self.sys_redirector

        try:
            log_file = auto_bot.APP_DIR / "log.txt"
            if log_file.exists() and log_file.stat().st_size > 0:
                existing_text = log_file.read_text(encoding="utf-8", errors="replace")
                if not is_trivial_log_content(existing_text):
                    self._load_existing_daily_log(existing_text)
        except Exception:
            pass

        self.canvas.bind("<Configure>", self.on_resize)
        self.resize_after_id = None

        # Register widget hover tooltips
        self.tooltips["opp_a2"] = ToolTip(self.chk_opp_a2)
        self.tooltips["opp_3k"] = ToolTip(self.chk_opp_3k)
        self.tooltips["opp_4q"] = ToolTip(self.chk_opp_4q)
        self.tooltips["opp_5j"] = ToolTip(self.chk_opp_5j)
        self.tooltips["opp_610"] = ToolTip(self.chk_opp_610)
        self.tooltips["opp_79"] = ToolTip(self.chk_opp_79)
        self.tooltips["opp_8"] = ToolTip(self.chk_opp_8)
        self.tooltips["mod_drop_78"] = ToolTip(self.chk_mod_drop_78)
        self.tooltips["mod_drop_6789"] = ToolTip(self.chk_mod_drop_6789)
        self.tooltips["mod_drop_8"] = ToolTip(self.chk_mod_drop_8)
        self.tooltips["mod_fast_build"] = ToolTip(self.chk_mod_fast_build)
        self.tooltips["mod_free_roll"] = ToolTip(self.chk_mod_free_roll)
        self.tooltips["mod_sprint_floor"] = ToolTip(self.chk_mod_sprint_floor)
        self.tooltips["mod_mega_sprint"] = ToolTip(self.chk_mod_mega_sprint)
        self.tooltips["btn_toggle_modifiers"] = ToolTip(self.btn_toggle_modifiers)
        self.tooltips["btn_config_strat"] = ToolTip(self.btn_config_strat)
        self.tooltips["field_box_opacity"] = ToolTip(self.scale_setting_opacity)
        self.tooltips["show_log"] = ToolTip(self.chk_setting_show_log)
        self.tooltips["debug_log"] = ToolTip(self.chk_setting_debug_log)

        self.apply_theme()
        self.refresh_texts()
        self.draw_ui(480, 850)
        threading.Thread(target=self._warm_up_engine, daemon=True).start()

    def _warm_up_engine(self):
        try:
            import poker_core
            poker_core.warm_up()
            auto_bot.preload_templates()
        except Exception:
            pass

    def _process_ui_queue(self):
        if getattr(self, "_is_destroyed", False):
            return

        current_game_date = auto_bot.get_game_date()
        if getattr(self, "last_game_date", None) != current_game_date:
            self.last_game_date = current_game_date
            if not self.is_running:
                self.current_coins, self.current_fails, self.current_profit = load_saved_stats()
                self.update_stats_display()

        try:
            for _ in range(100):
                item = self.ui_queue.get_nowait()
                msg_type, payload = item
                if msg_type == "log":
                    self.sys_redirector._write(payload)
                elif msg_type == "clear_log":
                    self.clear_log_text()
                elif msg_type == "stats":
                    c, f, p = payload
                    self.update_stats_display(c, f, p)
                elif msg_type == "callback":
                    payload()
                self.ui_queue.task_done()
        except queue.Empty:
            pass
        except Exception:
            pass
        finally:
            if not getattr(self, "_is_destroyed", False):
                self.after(30, self._process_ui_queue)

    def start_listen_hotkey(self):
        if self.is_running:
            return
        if self.is_listening:
            self._cancel_listen_hotkey()
            return

        self.is_listening = True
        self.btn_hotkey.configure(text=localization.tr("hotkey_listening", self.current_lang))
        print(localization.tr("hotkey_prompt", self.current_lang))

        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        time.sleep(0.1)
        q = queue.Queue(maxsize=1)
        hooked = keyboard.hook(q.put)
        key = None
        start_time = time.time()
        timeout = 10.0
        try:
            while self.is_listening and (time.time() - start_time < timeout):
                try:
                    event = q.get(timeout=0.2)
                    if event.event_type == keyboard.KEY_DOWN:
                        key = event.name.upper()
                        break
                except queue.Empty:
                    continue
        finally:
            try:
                keyboard.unhook(hooked)
            except Exception:
                pass

        if key:
            self.ui_queue.put(("callback", lambda: self._apply_new_hotkey(key)))
        else:
            self.ui_queue.put(("callback", self._cancel_listen_hotkey))

    def _cancel_listen_hotkey(self):
        self.is_listening = False
        try:
            self.btn_hotkey.configure(text=self.current_hotkey)
        except Exception:
            pass

    def _apply_new_hotkey(self, new_key):
        self.is_listening = False
        try:
            keyboard.remove_hotkey(self.current_hotkey)
        except:
            pass

        self.current_hotkey = new_key
        try:
            keyboard.add_hotkey(self.current_hotkey, lambda: self.after(0, self.stop_bot))
            self.btn_hotkey.configure(text=self.current_hotkey)
            print(localization.tr("hotkey_success", self.current_lang, key=self.current_hotkey))
        except Exception as e:
            print(localization.tr("hotkey_fallback", self.current_lang, key=new_key))
            self.current_hotkey = "F11"
            keyboard.add_hotkey(self.current_hotkey, lambda: self.after(0, self.stop_bot))
            self.btn_hotkey.configure(text=self.current_hotkey)
        self.save_settings()

    def _is_canvas_log_active(self) -> bool:
        return bool(self.show_bg and self.original_bg and 0 <= self.bg_index < len(self.bg_candidates) and self.field_box_opacity < 100)

    def _update_canvas_log_display(self, log_h: int = None):
        if not hasattr(self, "log_canvas_text_id"):
            return
        if not hasattr(self, "canvas_log_lines") or not self.canvas_log_lines:
            self.canvas.itemconfig(self.log_canvas_text_id, text="")
            if hasattr(self, "scrollbar"):
                self.scrollbar.set(0.0, 1.0)
            return

        if log_h is None:
            log_h = getattr(self, "_current_log_h", 120)
        line_h = 20
        visible_count = max(3, int((log_h - 16) / line_h))
        total = len(self.canvas_log_lines)

        if total <= visible_count:
            visible_lines = self.canvas_log_lines
            if hasattr(self, "scrollbar"):
                self.scrollbar.set(0.0, 1.0)
        else:
            max_offset = total - visible_count
            offset = getattr(self, "canvas_log_offset", None)
            if offset is None:
                offset = max_offset
            else:
                offset = max(0, min(max_offset, offset))
            visible_lines = self.canvas_log_lines[offset : offset + visible_count]
            if hasattr(self, "scrollbar"):
                first = offset / float(total)
                last = (offset + visible_count) / float(total)
                self.scrollbar.set(first, last)

        self.canvas.itemconfig(self.log_canvas_text_id, text="\n".join(visible_lines))

    def _on_log_scroll(self, action, *args):
        if self._is_canvas_log_active():
            total = len(getattr(self, "canvas_log_lines", []))
            log_h = getattr(self, "_current_log_h", 120)
            visible_count = max(3, int((log_h - 16) / 20))
            max_offset = max(0, total - visible_count)
            curr = getattr(self, "canvas_log_offset", None)
            if curr is None:
                curr = max_offset
            if action == "moveto" and args:
                try:
                    fraction = float(args[0])
                    self.canvas_log_offset = int(fraction * max_offset)
                except Exception:
                    pass
            elif action == "scroll" and len(args) >= 2:
                try:
                    count = int(args[0])
                    unit = args[1]
                    step = visible_count if unit == "pages" else 2
                    self.canvas_log_offset = max(0, min(max_offset, curr + count * step))
                except Exception:
                    pass
            self._update_canvas_log_display()
        elif hasattr(self, "log_text"):
            self.log_text.yview(action, *args)

    def _load_existing_daily_log(self, text: str):
        if hasattr(self, "log_text"):
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text)
            total_lines = int(self.log_text.index("end-1c").split(".")[0])
            if total_lines > 500:
                self.log_text.delete("1.0", f"{total_lines - 400}.0")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")
        if not hasattr(self, "canvas_log_lines"):
            self.canvas_log_lines = []
        for line in text.splitlines():
            if line.strip() or not self.canvas_log_lines or self.canvas_log_lines[-1] != "":
                self.canvas_log_lines.append(line)
        if len(self.canvas_log_lines) > 500:
            self.canvas_log_lines = self.canvas_log_lines[-400:]
        self.canvas_log_offset = None
        self._update_canvas_log_display()

    def append_log_text(self, text):
        if hasattr(self, "log_text"):
            self.log_text.configure(state="normal")
            self.log_text.insert("end", text)
            total_lines = int(self.log_text.index("end-1c").split(".")[0])
            if total_lines > 500:
                self.log_text.delete("1.0", f"{total_lines - 400}.0")
            self.log_text.see("end")
            self.log_text.configure(state="disabled")

        if not hasattr(self, "canvas_log_lines"):
            self.canvas_log_lines = []
        for line in text.splitlines():
            if line.strip() or not self.canvas_log_lines or self.canvas_log_lines[-1] != "":
                self.canvas_log_lines.append(line)
        if len(self.canvas_log_lines) > 500:
            self.canvas_log_lines = self.canvas_log_lines[-400:]
        self.canvas_log_offset = None
        self._update_canvas_log_display()

        try:
            log_file = auto_bot.APP_DIR / "log.txt"
            with open(log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(text)
        except Exception:
            pass

    def clear_log_text(self, clear_file: bool = False):
        if hasattr(self, "log_text"):
            self.log_text.configure(state="normal")
            self.log_text.delete("1.0", "end")
            self.log_text.configure(state="disabled")
        if hasattr(self, "canvas_log_lines"):
            self.canvas_log_lines.clear()
        self.canvas_log_offset = 0
        self._update_canvas_log_display()
        if clear_file:
            try:
                log_file = auto_bot.APP_DIR / "log.txt"
                if log_file.exists():
                    log_file.write_text("", encoding="utf-8")
            except Exception:
                pass

    def save_logs_to_file(self):
        if not hasattr(self, "log_text"):
            return
        text = self.log_text.get("1.0", "end-1c")
        if not text.strip() and hasattr(self, "canvas_log_lines") and self.canvas_log_lines:
            text = "\n".join(self.canvas_log_lines)
        if not text.strip():
            print(localization.tr("log_empty_save", self.current_lang))
            return

        file_path = filedialog.asksaveasfilename(
            parent=self,
            title=localization.tr("menu_save_logs", self.current_lang),
            initialdir=str(auto_bot.APP_DIR),
            initialfile="log.txt",
            filetypes=[("Text Files (*.txt)", "*.txt"), ("All Files (*.*)", "*.*")],
            defaultextension=".txt",
        )
        if file_path:
            try:
                Path(file_path).write_text(text, encoding="utf-8")
                print(localization.tr("log_saved_success", self.current_lang, path=file_path))
            except Exception as e:
                print(f"[Error] Failed to save log: {e}")

    def on_mouse_wheel(self, event):
        if self._is_canvas_log_active():
            direction = -1 if event.delta > 0 else 1
            total = len(getattr(self, "canvas_log_lines", []))
            log_h = getattr(self, "_current_log_h", 120)
            visible_count = max(3, int((log_h - 16) / 20))
            max_offset = max(0, total - visible_count)
            curr = getattr(self, "canvas_log_offset", None)
            if curr is None:
                curr = max_offset
            self.canvas_log_offset = max(0, min(max_offset, curr + direction * 2))
            self._update_canvas_log_display()
        elif hasattr(self, "log_text"):
            direction = -1 if event.delta > 0 else 1
            self.log_text.yview_scroll(direction * 3, "units")

    def on_resize(self, event):
        if event.widget != self.canvas:
            return
        w, h = event.width, event.height
        if w <= 50 or h <= 50:
            return
        if w == self.last_w and h == self.last_h:
            return
        self.last_w, self.last_h = w, h
        if getattr(self, "resize_after_id", None):
            try:
                self.after_cancel(self.resize_after_id)
            except Exception:
                pass
        self.resize_after_id = self.after(50, lambda: self._debounced_resize(w, h))

    def _debounced_resize(self, w, h):
        self.resize_after_id = None
        self.draw_ui(w, h)

    def _hide_mod_widgets(self):
        for w in getattr(self, "_mod_canvas_widgets", []):
            try:
                w.hide()
            except Exception:
                pass

    def _draw_modifiers_drawer(self, pad_x, content_w, mod_btn_y, mod_btn_h, w, img, card_fill, card_border):
        if self.modifiers_expanded:
            opp_y1 = mod_btn_y + mod_btn_h + 6
            curr_y = opp_y1 + 14
            inner_pad_x = pad_x + 8
            inner_w = content_w - 16
            col3_w = inner_w / 3.0
            col2_w = inner_w / 2.0
            row_h = 22

            # Section 1: Cards
            self.lbl_sec_cards.place(inner_pad_x, curr_y)
            curr_y += 18
            if self.cat_cards_expanded:
                self.chk_opp_a2.place(inner_pad_x, curr_y, width=col3_w, height=row_h)
                self.chk_opp_3k.place(inner_pad_x + col3_w, curr_y, width=col3_w, height=row_h)
                self.chk_opp_4q.place(inner_pad_x + 2 * col3_w, curr_y, width=col3_w, height=row_h)
                curr_y += row_h + 2
                self.chk_opp_5j.place(inner_pad_x, curr_y, width=col3_w, height=row_h)
                self.chk_opp_610.place(inner_pad_x + col3_w, curr_y, width=col3_w, height=row_h)
                self.chk_opp_79.place(inner_pad_x + 2 * col3_w, curr_y, width=col3_w, height=row_h)
                curr_y += row_h + 2
                self.chk_opp_8.place(inner_pad_x, curr_y, width=col3_w, height=row_h)
                curr_y += row_h + 14
            else:
                curr_y += 14
                for c in (self.chk_opp_a2, self.chk_opp_3k, self.chk_opp_4q, self.chk_opp_5j, self.chk_opp_610, self.chk_opp_79, self.chk_opp_8):
                    c.hide()

            # Section 2: Bailouts
            self.lbl_sec_bail.place(inner_pad_x, curr_y)
            curr_y += 18
            if self.cat_bail_expanded:
                self.chk_mod_drop_78.place(inner_pad_x, curr_y, width=col2_w, height=row_h)
                self.chk_mod_drop_6789.place(inner_pad_x + col2_w, curr_y, width=col2_w, height=row_h)
                curr_y += row_h + 2
                self.chk_mod_drop_8.place(inner_pad_x, curr_y, width=col2_w, height=row_h)
                curr_y += row_h + 14
            else:
                curr_y += 14
                for c in (self.chk_mod_drop_78, self.chk_mod_drop_6789, self.chk_mod_drop_8):
                    c.hide()

            # Section 3: Progression & Sprint
            self.lbl_sec_prog.place(inner_pad_x, curr_y)
            curr_y += 18
            if self.cat_prog_expanded:
                self.chk_mod_fast_build.place(inner_pad_x, curr_y, width=col2_w, height=row_h)
                self.chk_mod_free_roll.place(inner_pad_x + col2_w, curr_y, width=col2_w, height=row_h)
                curr_y += row_h + 2
                self.chk_mod_sprint_floor.place(inner_pad_x, curr_y, width=col2_w, height=row_h)
                self.chk_mod_mega_sprint.place(inner_pad_x + col2_w, curr_y, width=col2_w, height=row_h)
                curr_y += row_h + 10
            else:
                curr_y += 10
                for c in (self.chk_mod_fast_build, self.chk_mod_free_roll, self.chk_mod_sprint_floor, self.chk_mod_mega_sprint):
                    c.hide()

            opp_x1 = pad_x - 4
            opp_x2 = w - pad_x + 4
            opp_y2 = curr_y + 4
            img = draw_glass_card(img, (opp_x1, opp_y1, opp_x2, opp_y2), fill=card_fill, outline=card_border, radius=8)
            self.canvas.itemconfig(self.opp_frame_win, state="hidden")
            return (opp_y2 + 8), img
        else:
            self._hide_mod_widgets()
            self.canvas.itemconfig(self.opp_frame_win, state="hidden")
            return (mod_btn_y + mod_btn_h + 8), img

    def _draw_log_box(self, pad_x, content_w, log_y, h, w, img, card_fill, card_border):
        log_bottom = h - max(16, int(h * 0.025))
        log_h = max(60, log_bottom - log_y)
        scrollbar_w = 16
        log_w = content_w - scrollbar_w - 4
        self._current_log_h = log_h
        self._current_log_w = log_w

        if self.show_log:
            log_card_x1 = pad_x - 4
            log_card_y1 = log_y - 4
            log_card_x2 = pad_x + log_w + scrollbar_w + 8
            log_card_y2 = log_y + log_h + 4
            img = draw_glass_card(img, (log_card_x1, log_card_y1, log_card_x2, log_card_y2), fill=card_fill, outline=card_border, radius=8)

            self.canvas.coords(self.scrollbar_win, pad_x + log_w + 4, log_y)
            self.canvas.itemconfig(self.scrollbar_win, width=scrollbar_w, height=log_h, state="normal")

            if self._is_canvas_log_active():
                self.canvas.itemconfig(self.log_text_win, state="hidden")
                self.canvas.coords(self.log_canvas_text_id, pad_x + 6, log_y + 4)
                self.canvas.itemconfig(self.log_canvas_text_id, width=log_w - 8, state="normal")
                self._update_canvas_log_display(log_h)
            else:
                self.canvas.itemconfig(self.log_canvas_text_id, state="hidden")
                self.canvas.coords(self.log_text_win, pad_x, log_y)
                self.canvas.itemconfig(self.log_text_win, width=log_w, height=log_h, state="normal")
                self.log_text.configure(bg=self.theme_palette["log_bg"], fg=self.theme_palette["log_fg"])
        else:
            self.canvas.itemconfig(self.log_text_win, state="hidden")
            self.canvas.itemconfig(self.log_canvas_text_id, state="hidden")
            self.canvas.itemconfig(self.scrollbar_win, state="hidden")
        return img

    def draw_ui(self, w, h):
        if w <= 50 or h <= 50:
            return
        # 1. Background image (Plain neutral background if no custom background selected)
        bg_img = None
        palette = self.theme_palette
        if self.show_bg and self.original_bg and 0 <= self.bg_index < len(self.bg_candidates):
            bg_img = self.original_bg.resize((w, h), Image.Resampling.LANCZOS).convert("RGB")
            img = bg_img.convert("RGBA")
            card_border = None
        else:
            img = Image.new("RGBA", (w, h), color=palette["bg_plain"])
            card_border = palette["card_border"]

        # Dynamic opacity values & card fill color
        op_ratio = self.field_box_opacity / 100.0
        alpha = int(255 * op_ratio)
        card_fill = (*palette["card_fill_rgb"], alpha) if self.field_box_opacity > 0 else (*palette["card_fill_rgb"], 0)

        # 2. Responsive layout dimensions
        pad_x = max(16, int(w * 0.06))
        content_w = w - 2 * pad_x

        # Top 2-Tab Bar (Auto Bot & Simulation only)
        tab_btn_h = max(34, min(40, int(h * 0.046)))
        tab_y = max(24, int(h * 0.038))
        tab_gap = 8
        tab_btn_w = (content_w - tab_gap) / 2

        self.canvas.coords(self.tab_win_bot, pad_x + tab_btn_w / 2, tab_y)
        self.canvas.coords(self.tab_win_sim, pad_x + tab_btn_w + tab_gap + tab_btn_w / 2, tab_y)
        self.canvas.itemconfig(self.tab_win_bot, width=tab_btn_w, height=tab_btn_h, state="normal")
        self.canvas.itemconfig(self.tab_win_sim, width=tab_btn_w, height=tab_btn_h, state="normal")
        self.canvas.itemconfig(self.tab_win_settings, state="hidden")

        scrollbar_w = 16
        field_h = max(28, min(32, int(h * 0.040)))

        if self.current_tab == "bot":
            self._set_items_visible(self._bot_items, True)
            self._set_items_visible(self._sim_items, False)
            self._set_items_visible(self._settings_items, False)

            # Ensure widgets moved to File menu remain hidden on canvas
            self.canvas.itemconfig(self.lang_label_id, state="hidden")
            self.canvas.itemconfig(self.combo_window, state="hidden")
            self.canvas.itemconfig(self.lbl_setting_bg_id, state="hidden")
            self.canvas.itemconfig(self.combo_bg_win, state="hidden")
            self.canvas.itemconfig(self.btn_bg_win, state="hidden")
            self.canvas.itemconfig(self.btn_clear_logs_win, state="hidden")
            self.canvas.itemconfig(self.btn_open_custom_dialog_win, state="hidden")

            # Combined Top Stats Card (Hotkey Row + Status + Coins + Fails)
            tab_bottom = tab_y + tab_btn_h / 2
            stats_card_top = tab_bottom + 12
            card_inner_x = pad_x + 8
            hotkey_btn_h = 30
            hotkey_row_y = stats_card_top + 25
            hotkey_btn_w = max(110, min(150, int(content_w * 0.35)))

            self.canvas.coords(self.hotkey_label_id, card_inner_x, hotkey_row_y)
            self.canvas.coords(self.hotkey_window, w - pad_x - 8, hotkey_row_y)
            self.canvas.itemconfig(self.hotkey_window, width=hotkey_btn_w, height=hotkey_btn_h, state="normal")

            status_y = hotkey_row_y + 30
            coins_y = status_y + 28
            fails_y = coins_y + 28
            stats_card_bottom = fails_y + 16

            sc_x1 = pad_x - 4
            sc_y1 = stats_card_top
            sc_x2 = w - pad_x + 4
            sc_y2 = stats_card_bottom

            self.canvas.itemconfig(self.stats_card_id, state="hidden")
            if sc_x2 > sc_x1 and sc_y2 > sc_y1:
                overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
                draw = ImageDraw.Draw(overlay)
                draw.rounded_rectangle(
                    (sc_x1, sc_y1, sc_x2, sc_y2),
                    radius=8,
                    fill=card_fill,
                    outline=card_border,
                    width=1,
                )
                img = Image.alpha_composite(img, overlay)

            self.canvas.coords(self.status_id, card_inner_x, status_y)

            # Position Coins Row
            self.canvas.coords(self.coins_label_id, card_inner_x, coins_y)
            coins_lbl_box = self.canvas.bbox(self.coins_label_id)
            coins_lbl_w = (coins_lbl_box[2] - coins_lbl_box[0]) if coins_lbl_box else 50
            entry_coins_x = card_inner_x + coins_lbl_w + 8
            self.canvas.coords(self.entry_coins_win, entry_coins_x, coins_y)
            self.canvas.itemconfig(self.entry_coins_win, width=76, height=28)
            self.canvas.coords(self.coins_max_id, entry_coins_x + 76 + 10, coins_y)

            # Position Fails & Net Profit Row
            self.canvas.coords(self.fails_label_id, card_inner_x, fails_y)
            fails_lbl_box = self.canvas.bbox(self.fails_label_id)
            fails_lbl_w = (fails_lbl_box[2] - fails_lbl_box[0]) if fails_lbl_box else 50
            entry_fails_x = card_inner_x + fails_lbl_w + 8
            self.canvas.coords(self.entry_fails_win, entry_fails_x, fails_y)
            self.canvas.itemconfig(self.entry_fails_win, width=54, height=28)
            self.canvas.coords(self.profit_id, entry_fails_x + 54 + 10, fails_y)

            # 1-Row Action Buttons: Start Bot & Stop Bot (50/50 balanced split)
            btn_gap = 14
            btn_h = 38
            btn_row_top = stats_card_bottom + 12
            btn_row_y = btn_row_top + btn_h / 2
            btn_w = (content_w - btn_gap) / 2

            self.canvas.coords(self.btn_start_win, pad_x + btn_w / 2, btn_row_y)
            self.canvas.itemconfig(self.btn_start_win, width=btn_w, height=btn_h)

            self.canvas.coords(self.btn_stop_win, pad_x + btn_w + btn_gap + btn_w / 2, btn_row_y)
            self.canvas.itemconfig(self.btn_stop_win, width=btn_w, height=btn_h)

            self.canvas.itemconfig(self.btn_exit_win, state="hidden")

            # Strategy Row (full width dropdown or with config button if custom parametric)
            strat_top = btn_row_top + btn_h + 10
            strat_field_h = 30
            is_custom = (self.active_mode == "custom_parametric")
            if is_custom:
                config_btn_w = max(100, min(120, int(content_w * 0.28)))
                combo_strat_w = content_w - config_btn_w - 8
                self.canvas.coords(self.strategy_window, pad_x, strat_top)
                self.canvas.itemconfig(self.strategy_window, width=combo_strat_w, height=strat_field_h, state="normal")
                self.canvas.coords(self.btn_config_strat_win, pad_x + combo_strat_w + 8, strat_top)
                self.canvas.itemconfig(self.btn_config_strat_win, width=config_btn_w, height=strat_field_h, state="normal")
            else:
                self.canvas.coords(self.strategy_window, pad_x, strat_top)
                self.canvas.itemconfig(self.strategy_window, width=content_w, height=strat_field_h, state="normal")
                self.canvas.itemconfig(self.btn_config_strat_win, state="hidden")

            # Strategy Description (with clear guidance)
            desc_y = strat_top + strat_field_h + 8
            self.canvas.coords(self.strategy_desc_id, pad_x + 6, desc_y)
            self.canvas.itemconfig(self.strategy_desc_id, width=content_w - 12, state="normal")

            desc_bbox = self.canvas.bbox(self.strategy_desc_id)
            desc_bottom = desc_bbox[3] if (desc_bbox and desc_bbox[3] > desc_y) else (desc_y + 26)

            if desc_bbox and (desc_bottom + 4) > (strat_top + strat_field_h + 4):
                d_x1 = pad_x - 4
                d_y1 = strat_top + strat_field_h + 4
                d_x2 = w - pad_x + 4
                d_y2 = desc_bottom + 4
                overlay_desc = Image.new("RGBA", img.size, (0, 0, 0, 0))
                draw_desc = ImageDraw.Draw(overlay_desc)
                draw_desc.rounded_rectangle(
                    (d_x1, d_y1, d_x2, d_y2),
                    radius=6,
                    fill=card_fill,
                    outline=card_border,
                    width=1,
                )
                img = Image.alpha_composite(img, overlay_desc)

            # Strategy Modifiers Drawer on Auto Bot Tab
            mod_btn_y = desc_bottom + 8
            mod_btn_h = 30
            self.canvas.coords(self.btn_toggle_modifiers_win, pad_x, mod_btn_y)
            self.canvas.itemconfig(self.btn_toggle_modifiers_win, width=content_w, height=mod_btn_h, state="normal")

            log_y, img = self._draw_modifiers_drawer(pad_x, content_w, mod_btn_y, mod_btn_h, w, img, card_fill, card_border)
            img = self._draw_log_box(pad_x, content_w, log_y, h, w, img, card_fill, card_border)

        elif self.current_tab == "sim":
            self._set_items_visible(self._bot_items, False)
            self._set_items_visible(self._sim_items, True)
            self._set_items_visible(self._settings_items, False)

            self.canvas.itemconfig(self.lang_label_id, state="hidden")
            self.canvas.itemconfig(self.combo_window, state="hidden")
            self.canvas.itemconfig(self.lbl_setting_bg_id, state="hidden")
            self.canvas.itemconfig(self.combo_bg_win, state="hidden")
            self.canvas.itemconfig(self.btn_bg_win, state="hidden")
            self.canvas.itemconfig(self.btn_clear_logs_win, state="hidden")
            self.canvas.itemconfig(self.btn_open_custom_dialog_win, state="hidden")

            # Strategy Row (full width or with config button if custom parametric)
            strat_top = tab_y + tab_btn_h / 2 + 10
            strat_field_h = 30
            is_custom = (self.active_mode == "custom_parametric")
            if is_custom:
                config_btn_w = max(100, min(120, int(content_w * 0.28)))
                combo_strat_w = content_w - config_btn_w - 8
                self.canvas.coords(self.strategy_window, pad_x, strat_top)
                self.canvas.itemconfig(self.strategy_window, width=combo_strat_w, height=strat_field_h, state="normal")
                self.canvas.coords(self.btn_config_strat_win, pad_x + combo_strat_w + 8, strat_top)
                self.canvas.itemconfig(self.btn_config_strat_win, width=config_btn_w, height=strat_field_h, state="normal")
            else:
                self.canvas.coords(self.strategy_window, pad_x, strat_top)
                self.canvas.itemconfig(self.strategy_window, width=content_w, height=strat_field_h, state="normal")
                self.canvas.itemconfig(self.btn_config_strat_win, state="hidden")

            # Strategy Description
            desc_y = strat_top + strat_field_h + 6
            self.canvas.coords(self.strategy_desc_id, pad_x, desc_y)
            self.canvas.itemconfig(self.strategy_desc_id, width=content_w, state="normal")

            # Dynamic spacing to guarantee no overlap with description text
            desc_bbox = self.canvas.bbox(self.strategy_desc_id)
            desc_bottom = desc_bbox[3] if (desc_bbox and desc_bbox[3] > desc_y) else (desc_y + 30)

            # Strategy Modifiers Drawer on Simulation Tab
            mod_btn_y = desc_bottom + 8
            mod_btn_h = 30
            self.canvas.coords(self.btn_toggle_modifiers_win, pad_x, mod_btn_y)
            self.canvas.itemconfig(self.btn_toggle_modifiers_win, width=content_w, height=mod_btn_h, state="normal")

            days_row_top, img = self._draw_modifiers_drawer(pad_x, content_w, mod_btn_y, mod_btn_h, w, img, card_fill, card_border)

            # Days input row (Sim Days + Spinbox on left, Clear Logs on right)
            days_row_h = 30
            days_y = days_row_top + days_row_h / 2
            self.canvas.coords(self.sim_days_label_id, pad_x, days_y)

            lbl_bbox = self.canvas.bbox(self.sim_days_label_id)
            spin_x = (lbl_bbox[2] + 8) if lbl_bbox else (pad_x + 90)
            self.canvas.coords(self.spin_sim_days_win, spin_x, days_y)
            self.canvas.itemconfig(self.spin_sim_days_win, width=76, height=days_row_h)
            self.canvas.itemconfig(self.btn_clear_logs_win, state="hidden")

            # Action Buttons: Run Simulation & Compare All
            btn_row1_top = days_row_top + days_row_h + 14
            btn_row1_h = 36
            btn_row1_y = btn_row1_top + btn_row1_h / 2
            action_gap = 10
            sim_btn_w = (content_w - action_gap) / 2
            self.canvas.coords(self.btn_sim_run_win, pad_x + sim_btn_w / 2, btn_row1_y)
            self.canvas.coords(self.btn_sim_compare_win, pad_x + sim_btn_w + action_gap + sim_btn_w / 2, btn_row1_y)
            self.canvas.itemconfig(self.btn_sim_run_win, width=sim_btn_w, height=btn_row1_h)
            self.canvas.itemconfig(self.btn_sim_compare_win, width=sim_btn_w, height=btn_row1_h)

            self.canvas.itemconfig(self.btn_sim_export_csv_win, state="hidden")
            self.canvas.itemconfig(self.btn_sim_export_json_win, state="hidden")

            # Log Box filling remainder (gains extra vertical height without redundant export buttons)
            sim_log_y = btn_row1_top + btn_row1_h + 16
            img = self._draw_log_box(pad_x, content_w, sim_log_y, h, w, img, card_fill, card_border)

        elif self.current_tab == "settings":
            self._set_items_visible(self._bot_items, False)
            self._set_items_visible(self._sim_items, False)
            self._set_items_visible(self._settings_items, True)
            self._hide_mod_widgets()

            self.canvas.itemconfig(self.log_text_win, state="hidden")
            self.canvas.itemconfig(self.log_canvas_text_id, state="hidden")
            self.canvas.itemconfig(self.scrollbar_win, state="hidden")
            self.canvas.itemconfig(self.strategy_window, state="hidden")
            self.canvas.itemconfig(self.strategy_desc_id, state="hidden")
            self.canvas.itemconfig(self.btn_config_strat_win, state="hidden")
            self.canvas.itemconfig(self.btn_open_custom_dialog_win, state="hidden")

            sett_start_y = tab_y + tab_btn_h / 2 + 18
            self.canvas.coords(self.lbl_setting_title_id, pad_x, sett_start_y)

            row_gap = 36
            input_w = max(130, min(160, int(content_w * 0.44)))

            # Row 1: Language
            r1_y = sett_start_y + row_gap
            self.canvas.coords(self.lang_label_id, pad_x, r1_y)
            self.canvas.coords(self.combo_window, w - pad_x, r1_y)
            self.canvas.itemconfig(self.combo_window, width=input_w, height=field_h, state="normal")

            # Row 2: Background
            r2_y = r1_y + row_gap
            self.canvas.coords(self.lbl_setting_bg_id, pad_x, r2_y)
            self.canvas.coords(self.combo_bg_win, w - pad_x, r2_y)
            self.canvas.itemconfig(self.combo_bg_win, width=input_w, height=field_h, state="normal")

            # Row 3: Field Box Opacity
            r3_y = r2_y + row_gap
            self.canvas.coords(self.lbl_setting_opacity_id, pad_x, r3_y)
            self.canvas.coords(self.scale_setting_opacity_win, w - pad_x, r3_y)
            self.canvas.itemconfig(self.scale_setting_opacity_win, width=input_w, height=field_h, state="normal")

            # Row 4: Target limit
            r4_y = r3_y + row_gap
            self.canvas.coords(self.lbl_setting_target_id, pad_x, r4_y)
            self.canvas.coords(self.entry_setting_target_win, w - pad_x, r4_y)
            self.canvas.itemconfig(self.entry_setting_target_win, width=input_w, height=field_h, state="normal")

            # Row 5: Ticket Cost
            r5_y = r4_y + row_gap
            self.canvas.coords(self.lbl_setting_ticket_id, pad_x, r5_y)
            self.canvas.coords(self.entry_setting_ticket_win, w - pad_x, r5_y)
            self.canvas.itemconfig(self.entry_setting_ticket_win, width=input_w, height=field_h, state="normal")

            # Row 6: Log Console & Debug Logging Toggles
            r6_y = r5_y + row_gap
            chk_col_w = (content_w - 8) / 2
            self.canvas.coords(self.chk_setting_show_log_win, pad_x, r6_y)
            self.canvas.itemconfig(self.chk_setting_show_log_win, width=chk_col_w, height=field_h, state="normal")
            self.canvas.coords(self.chk_setting_debug_log_win, pad_x + chk_col_w + 8, r6_y)
            self.canvas.itemconfig(self.chk_setting_debug_log_win, width=chk_col_w, height=field_h, state="normal")

            # Row 7: Buttons: Save & Restore
            btn_sett_y = r6_y + row_gap + 10
            btn_sett_w = (content_w - 8) / 2
            btn_sett_h = 36
            self.canvas.coords(self.btn_save_settings_win, pad_x + btn_sett_w / 2, btn_sett_y)
            self.canvas.coords(self.btn_restore_defaults_win, pad_x + btn_sett_w + 8 + btn_sett_w / 2, btn_sett_y)
            self.canvas.itemconfig(self.btn_save_settings_win, width=btn_sett_w, height=btn_sett_h, state="normal")
            self.canvas.itemconfig(self.btn_restore_defaults_win, width=btn_sett_w, height=btn_sett_h, state="normal")

            # Row 7: Return to Auto Bot
            btn_back_y = btn_sett_y + btn_sett_h + 12
            self.canvas.coords(self.btn_back_to_bot_win, pad_x + content_w / 2, btn_back_y)
            self.canvas.itemconfig(self.btn_back_to_bot_win, width=content_w, height=36, state="normal")

            # Position card behind settings rows
            sett_x1 = pad_x - 8
            sett_y1 = sett_start_y - 12
            sett_x2 = w - pad_x + 8
            sett_y2 = btn_back_y + btn_sett_h / 2 + 12

            self.canvas.itemconfig(self.settings_card_id, state="hidden")
            img = draw_glass_card(img, (sett_x1, sett_y1, sett_x2, sett_y2), fill=card_fill, outline=card_border, radius=8)

            # Feedback label
            self.canvas.coords(self.settings_feedback_id, w / 2, btn_back_y + btn_sett_h / 2 + 20)

        # 3. Final background PhotoImage update (including any composited cards)
        self.bg_photo = ImageTk.PhotoImage(img)
        self.canvas.itemconfig(self.bg_id, image=self.bg_photo)

    def _discover_backgrounds(self) -> list[Path]:
        return discover_backgrounds(auto_bot.APP_DIR, auto_bot.RESOURCE_DIR)

    def _load_current_bg(self):
        palette = self.theme_palette if hasattr(self, "theme_palette") else THEME_PALETTES["light"]
        bg_path = self.bg_candidates[self.bg_index] if (0 <= self.bg_index < len(self.bg_candidates)) else None
        self.original_bg, self.show_bg = load_background_image(bg_path, fallback_hex=palette["bg_plain_hex"])

    def get_active_theme(self) -> str:
        if getattr(self, "theme_mode", "system") == "system":
            return "dark" if is_windows_dark_mode() else "light"
        return getattr(self, "theme_mode", "light")

    @property
    def theme_palette(self) -> dict:
        return THEME_PALETTES.get(self.get_active_theme(), THEME_PALETTES["light"])

    def apply_theme(self, theme_mode: str = None):
        if theme_mode is not None and theme_mode in ("system", "light", "dark"):
            self.theme_mode = theme_mode
            if hasattr(self, "theme_var"):
                self.theme_var.set(theme_mode)

        palette = self.theme_palette
        is_dark = palette["is_dark"]
        set_window_dark_titlebar(self, is_dark)

        if is_dark:
            try:
                self.style.theme_use("clam")
            except Exception:
                pass
            font_button = (self.font_family, 9, "bold")
            font_hotkey = (self.font_family, 10, "bold")
            self.style.configure("TButton", font=font_button, background="#27272A", foreground="#F8FAFC", bordercolor="#3F3F46", lightcolor="#27272A", darkcolor="#27272A", padding=(6, 3))
            self.style.map("TButton", background=[("active", "#3F3F46"), ("disabled", "#18181B")], foreground=[("disabled", "#71717A")])
            self.style.configure("Hotkey.TButton", font=font_hotkey, background="#27272A", foreground="#F8FAFC", bordercolor="#3F3F46", lightcolor="#27272A", darkcolor="#27272A", padding=(8, 2))
            self.style.map("Hotkey.TButton", background=[("active", "#3F3F46"), ("disabled", "#18181B")], foreground=[("disabled", "#71717A")])
            self.style.configure("Tab.TButton", font=font_button, background="#27272A", foreground="#CBD5E1", bordercolor="#3F3F46", lightcolor="#27272A", darkcolor="#27272A", padding=(4, 3))
            self.style.configure("ActiveTab.TButton", font=font_button, background="#2563EB", foreground="#FFFFFF", bordercolor="#1D4ED8", lightcolor="#2563EB", darkcolor="#2563EB", padding=(4, 3))
            self.style.configure("Config.TButton", font=font_button, background="#27272A", foreground="#F8FAFC", bordercolor="#3F3F46", lightcolor="#27272A", darkcolor="#27272A", padding=(4, 2))
            self.style.configure("ModifierDrawer.TButton", font=font_button, background="#27272A", foreground="#F8FAFC", bordercolor="#3F3F46", lightcolor="#27272A", darkcolor="#27272A", padding=(8, 4))
            self.style.configure("ModifierCard.TFrame", background="#27272A")
            self.style.configure("ModifierCard.TLabel", background="#27272A", foreground="#F8FAFC")
            self.style.configure("ModifierCard.TCheckbutton", background="#27272A", foreground="#F8FAFC")
            self.style.configure("TCombobox", fieldbackground="#27272A", background="#27272A", foreground="#F8FAFC", arrowcolor="#F8FAFC", bordercolor="#3F3F46")
            self.style.map(
                "TCombobox",
                fieldbackground=[
                    ("readonly", "focus", "#27272A"),
                    ("readonly", "#27272A"),
                    ("disabled", "#18181B"),
                ],
                foreground=[
                    ("disabled", "#71717A"),
                    ("readonly", "focus", "#F8FAFC"),
                    ("readonly", "#F8FAFC"),
                ],
                background=[
                    ("active", "#3F3F46"),
                    ("pressed", "#3F3F46"),
                    ("readonly", "#27272A"),
                ],
                bordercolor=[
                    ("focus", "#3B82F6"),
                    ("!focus", "#3F3F46"),
                ],
                arrowcolor=[
                    ("disabled", "#71717A"),
                    ("!disabled", "#F8FAFC"),
                ],
                selectbackground=[
                    ("readonly", "#3F3F46"),
                ],
                selectforeground=[
                    ("readonly", "#F8FAFC"),
                ],
            )
            self.style.configure("TEntry", fieldbackground="#27272A", foreground="#F8FAFC", bordercolor="#3F3F46", insertcolor="#F8FAFC")
            self.style.map("TEntry", fieldbackground=[("readonly", "#27272A"), ("disabled", "#18181B")], foreground=[("disabled", "#71717A")])
            self.style.configure("TSpinbox", fieldbackground="#27272A", background="#27272A", foreground="#F8FAFC", arrowcolor="#F8FAFC", bordercolor="#3F3F46")
            self.style.map(
                "TSpinbox",
                fieldbackground=[("readonly", "#27272A"), ("disabled", "#18181B")],
                background=[("readonly", "#27272A")],
                foreground=[("disabled", "#71717A")],
                arrowcolor=[("disabled", "#71717A"), ("!disabled", "#F8FAFC")],
            )
            self.style.configure("TScrollbar", background="#3F3F46", troughcolor="#18181B", arrowcolor="#F8FAFC", bordercolor="#27272A", lightcolor="#3F3F46", darkcolor="#3F3F46")
            self.style.map("TScrollbar", background=[("active", "#52525B"), ("disabled", "#18181B")])
            self.style.configure("Vertical.TScrollbar", background="#3F3F46", troughcolor="#18181B", arrowcolor="#F8FAFC", bordercolor="#27272A", lightcolor="#3F3F46", darkcolor="#3F3F46")
            self.style.map("Vertical.TScrollbar", background=[("active", "#52525B"), ("disabled", "#18181B")])
            self.style.configure("TLabel", background="#27272A", foreground="#F8FAFC")
            self.style.configure("TFrame", background="#27272A")
            self.style.configure("TLabelframe", background="#27272A", bordercolor="#3F3F46")
            self.style.configure("TLabelframe.Label", background="#27272A", foreground="#F8FAFC")
            self.style.configure("Treeview", background="#27272A", foreground="#F8FAFC", fieldbackground="#27272A", bordercolor="#3F3F46")
            self.style.configure("Treeview.Heading", background="#18181B", foreground="#F8FAFC", bordercolor="#3F3F46")
            self.style.map("Treeview", background=[("selected", "#2563EB")], foreground=[("selected", "#FFFFFF")])
            self.option_add('*TCombobox*Listbox.background', '#27272A')
            self.option_add('*TCombobox*Listbox.foreground', '#F8FAFC')
            self.option_add('*TCombobox*Listbox.selectBackground', '#2563EB')
            self.option_add('*TCombobox*Listbox.selectForeground', '#FFFFFF')
        else:
            for theme_name in ("vista", "clam"):
                try:
                    self.style.theme_use(theme_name)
                    break
                except Exception:
                    pass
            font_button = (self.font_family, 9, "bold")
            font_hotkey = (self.font_family, 10, "bold")
            self.style.configure("TButton", font=font_button, padding=(6, 3))
            self.style.configure("Hotkey.TButton", font=font_hotkey, padding=(8, 2))
            self.style.configure("Tab.TButton", font=font_button, padding=(4, 3))
            self.style.configure("ActiveTab.TButton", font=font_button, padding=(4, 3))
            self.style.configure("Config.TButton", font=font_button, padding=(4, 2))
            self.style.configure("ModifierDrawer.TButton", font=font_button, padding=(8, 4))
            self.style.configure("ModifierCard.TFrame", background="#FFFFFF")
            self.style.configure("ModifierCard.TLabel", background="#FFFFFF")
            self.style.configure("ModifierCard.TCheckbutton", background="#FFFFFF")
            self.style.configure("TCombobox", fieldbackground="#FFFFFF", background="#FFFFFF", foreground="#0F172A", arrowcolor="#0F172A", bordercolor="#CBD5E1")
            self.style.map(
                "TCombobox",
                fieldbackground=[
                    ("readonly", "focus", "#FFFFFF"),
                    ("readonly", "#FFFFFF"),
                    ("disabled", "#F1F5F9"),
                ],
                foreground=[
                    ("disabled", "#94A3B8"),
                    ("readonly", "focus", "#0F172A"),
                    ("readonly", "#0F172A"),
                ],
                background=[
                    ("active", "#E2E8F0"),
                    ("pressed", "#CBD5E1"),
                    ("readonly", "#FFFFFF"),
                ],
                bordercolor=[
                    ("focus", "#2563EB"),
                    ("!focus", "#CBD5E1"),
                ],
                arrowcolor=[
                    ("disabled", "#94A3B8"),
                    ("!disabled", "#0F172A"),
                ],
                selectbackground=[
                    ("readonly", "#2563EB"),
                ],
                selectforeground=[
                    ("readonly", "#FFFFFF"),
                ],
            )
            self.style.configure("TEntry", fieldbackground="#FFFFFF", foreground="#0F172A", bordercolor="#CBD5E1", insertcolor="#0F172A")
            self.style.map("TEntry", fieldbackground=[("readonly", "#FFFFFF"), ("disabled", "#F1F5F9")], foreground=[("disabled", "#94A3B8")])
            self.style.configure("TSpinbox", fieldbackground="#FFFFFF", background="#FFFFFF", foreground="#0F172A", arrowcolor="#0F172A", bordercolor="#CBD5E1")
            self.style.map(
                "TSpinbox",
                fieldbackground=[("readonly", "#FFFFFF"), ("disabled", "#F1F5F9")],
                background=[("readonly", "#FFFFFF")],
                foreground=[("disabled", "#94A3B8")],
                arrowcolor=[("disabled", "#94A3B8"), ("!disabled", "#0F172A")],
            )
            self.style.configure("TScrollbar", background="#E2E8F0", troughcolor="#F1F5F9", arrowcolor="#0F172A", bordercolor="#CBD5E1")
            self.style.configure("Vertical.TScrollbar", background="#E2E8F0", troughcolor="#F1F5F9", arrowcolor="#0F172A", bordercolor="#CBD5E1")
            self.style.configure("TLabel", background="#FFFFFF", foreground="#0F172A")
            self.style.configure("TFrame", background="#FFFFFF")
            self.style.configure("TLabelframe", background="#FFFFFF")
            self.style.configure("TLabelframe.Label", background="#FFFFFF", foreground="#0F172A")
            self.style.configure("Treeview", background="#FFFFFF", foreground="#0F172A", fieldbackground="#FFFFFF")
            self.style.configure("Treeview.Heading", background="#F1F5F9", foreground="#0F172A")
            self.option_add('*TCombobox*Listbox.background', '#FFFFFF')
            self.option_add('*TCombobox*Listbox.foreground', '#0F172A')
            self.option_add('*TCombobox*Listbox.selectBackground', '#2563EB')
            self.option_add('*TCombobox*Listbox.selectForeground', '#FFFFFF')

        menu_bg = "#27272A" if is_dark else "#FFFFFF"
        menu_fg = "#F8FAFC" if is_dark else "#0F172A"
        menu_active_bg = "#3F3F46" if is_dark else "#E2E8F0"
        menu_active_fg = "#FFFFFF" if is_dark else "#0F172A"
        bar_bg = "#18181B" if is_dark else "#F8FAFC"
        bar_fg = "#F8FAFC" if is_dark else "#0F172A"
        bar_hover = "#27272A" if is_dark else "#E2E8F0"

        all_menus = [
            getattr(self, "file_menu", None),
            getattr(self, "open_folders_menu", None),
            getattr(self, "logs_menu", None),
            getattr(self, "settings_menu", None),
            getattr(self, "bg_menu", None),
            getattr(self, "opacity_menu", None),
            getattr(self, "lang_menu", None),
            getattr(self, "sim_menu", None),
            getattr(self, "help_menu", None),
        ]
        for m in all_menus:
            if m:
                try:
                    m.configure(
                        bg=menu_bg,
                        fg=menu_fg,
                        activebackground=menu_active_bg,
                        activeforeground=menu_active_fg,
                        selectcolor="#3B82F6" if is_dark else "#2563EB",
                        bd=0,
                        activeborderwidth=0,
                        relief="flat",
                    )
                except Exception:
                    pass

        if hasattr(self, "menubar_frame"):
            self.menubar_frame.configure(bg=bar_bg)
            for btn in getattr(self, "menu_buttons", {}).values():
                btn.configure(bg=bar_bg, fg=bar_fg)

        try:
            self.configure(bg=palette["bg_plain_hex"])
            self.canvas.configure(bg=palette["bg_plain_hex"])
        except Exception:
            pass

        text_primary_items = [
            getattr(self, "hotkey_label_id", None),
            getattr(self, "coins_label_id", None),
            getattr(self, "coins_max_id", None),
            getattr(self, "fails_label_id", None),
            getattr(self, "profit_id", None),
            getattr(self, "sim_days_label_id", None),
            getattr(self, "lbl_setting_title_id", None),
        ]
        for it in text_primary_items:
            if it:
                try:
                    self.canvas.itemconfig(it, fill=palette["text_primary"])
                except Exception:
                    pass

        text_sec_items = [
            getattr(self, "strategy_desc_id", None),
            getattr(self, "lbl_setting_target_id", None),
            getattr(self, "lbl_setting_ticket_id", None),
            getattr(self, "lbl_setting_opacity_id", None),
        ]
        for it in text_sec_items:
            if it:
                try:
                    self.canvas.itemconfig(it, fill=palette["text_secondary"])
                except Exception:
                    pass

        if getattr(self, "status_id", None):
            try:
                if getattr(self, "is_running", False):
                    self.canvas.itemconfig(self.status_id, fill=palette["status_running"])
                else:
                    self.canvas.itemconfig(self.status_id, fill=palette["status_idle"])
            except Exception:
                pass

        if getattr(self, "log_canvas_text_id", None):
            try:
                self.canvas.itemconfig(self.log_canvas_text_id, fill=palette["log_fg"])
            except Exception:
                pass

        if getattr(self, "log_text", None):
            try:
                self.log_text.configure(bg=palette["log_bg"], fg=palette["log_fg"])
            except Exception:
                pass

        for w in getattr(self, "_mod_canvas_widgets", []):
            if hasattr(w, "set_theme"):
                if isinstance(w, CanvasHeaderLabel):
                    w.set_theme(palette["header_fill"])
                elif isinstance(w, CanvasCheckbutton):
                    w.set_theme(palette["name"])

        if not self.show_bg:
            self.original_bg = Image.new('RGB', (480, 850), color=palette["bg_plain_hex"])

        w = self.last_w if (getattr(self, "last_w", 0) and self.last_w > 50) else (self.winfo_width() if self.winfo_width() > 50 else 480)
        h = self.last_h if (getattr(self, "last_h", 0) and self.last_h > 50) else (self.winfo_height() if self.winfo_height() > 50 else 850)
        if hasattr(self, "draw_ui"):
            self.draw_ui(w, h)

    def _get_bg_var_value(self) -> int:
        if self.show_bg and 0 <= self.bg_index < len(self.bg_candidates):
            return self.bg_index
        return -1

    def set_theme_mode(self, mode: str):
        if mode in ("system", "light", "dark"):
            self.theme_mode = mode
            if hasattr(self, "theme_var"):
                self.theme_var.set(mode)
            self.apply_theme()
            w = self.last_w if (getattr(self, "last_w", 0) and self.last_w > 50) else self.winfo_width()
            h = self.last_h if (getattr(self, "last_h", 0) and self.last_h > 50) else self.winfo_height()
            if hasattr(self, "draw_ui") and w > 50 and h > 50:
                self.draw_ui(w, h)
            self._update_combo_bg_values()
            self.save_settings()

    def select_theme(self, mode: str):
        self.set_theme_mode(mode)

    def select_theme_background(self, mode: str):
        self.set_theme_mode(mode)
        self.select_background(-1)

    def select_background(self, idx: int):
        self.bg_index = idx
        if hasattr(self, "bg_var"):
            self.bg_var.set(idx)
        if idx < 0:
            self.show_bg = False
            self._load_current_bg()
            self.apply_theme()
        else:
            self.show_bg = True
            self._load_current_bg()
            w = self.last_w if self.last_w else self.winfo_width()
            h = self.last_h if self.last_h else self.winfo_height()
            self.draw_ui(w, h)
        self._update_combo_bg_values()
        self.save_settings()

    def set_field_box_opacity(self, opacity: int, save: bool = True):
        self.field_box_opacity = max(0, min(100, int(opacity)))
        if hasattr(self, "opacity_var"):
            try:
                self.opacity_var.set(self.field_box_opacity)
            except Exception:
                pass
        if hasattr(self, "scale_setting_opacity") and not getattr(self, "_in_opacity_callback", False):
            try:
                curr = int(float(self.scale_setting_opacity.get()))
                if abs(curr - self.field_box_opacity) >= 1:
                    self.scale_setting_opacity.set(self.field_box_opacity)
            except Exception:
                pass
        if hasattr(self, "lbl_setting_opacity_val"):
            try:
                self.lbl_setting_opacity_val.configure(text=f"{self.field_box_opacity}%")
            except Exception:
                pass
        w = self.last_w if (self.last_w and self.last_w > 50) else (self.winfo_width() if self.winfo_width() > 50 else 480)
        h = self.last_h if (self.last_h and self.last_h > 50) else (self.winfo_height() if self.winfo_height() > 50 else 850)
        self.draw_ui(w, h)
        if save:
            self.save_settings()

    def _on_opacity_scale_change(self, val):
        self._in_opacity_callback = True
        try:
            v = int(float(val))
        except (ValueError, TypeError):
            v = 80
        if hasattr(self, "lbl_setting_opacity_val"):
            try:
                self.lbl_setting_opacity_val.configure(text=f"{v}%")
            except Exception:
                pass
        try:
            self.set_field_box_opacity(v, save=False)
        finally:
            self._in_opacity_callback = False

    def _on_opacity_scale_release(self, event=None):
        self.save_settings()

    def toggle_log_console(self):
        self.show_log = not self.show_log
        if hasattr(self, "var_show_log"):
            self.var_show_log.set(self.show_log)
        w = self.last_w if self.last_w else self.winfo_width()
        h = self.last_h if self.last_h else self.winfo_height()
        self.draw_ui(w, h)
        self.save_settings()

    def _update_combo_bg_values(self):
        if not hasattr(self, "combo_bg"):
            return
        bg_names = [
            localization.tr("theme_system", self.current_lang),
            localization.tr("theme_light", self.current_lang),
            localization.tr("theme_dark", self.current_lang),
        ]
        for i, cand in enumerate(self.bg_candidates):
            bg_label = "Minato Aqua" if cand.stem.lower() in ("default", "minato_aqua") else cand.stem.replace('_', ' ').title()
            bg_names.append(f"{i + 1}. {bg_label}")
        self.combo_bg.configure(values=bg_names)
        if self.show_bg and 0 <= self.bg_index < len(self.bg_candidates):
            current_sel = 3 + self.bg_index
        elif self.theme_mode == "light":
            current_sel = 1
        elif self.theme_mode == "dark":
            current_sel = 2
        else:
            current_sel = 0
        if 0 <= current_sel < len(bg_names):
            self.combo_bg.current(current_sel)

    def on_bg_combo_change(self, event=None):
        idx = self.combo_bg.current()
        if idx == 0:
            self.select_theme_background("system")
        elif idx == 1:
            self.select_theme_background("light")
        elif idx == 2:
            self.select_theme_background("dark")
        elif idx >= 3:
            self.select_background(idx - 3)

    def toggle_bg(self):
        if not self.show_bg:
            if self.theme_mode == "system":
                self.select_theme_background("light")
            elif self.theme_mode == "light":
                self.select_theme_background("dark")
            elif self.theme_mode == "dark":
                if self.bg_candidates:
                    self.select_background(0)
                else:
                    self.select_theme_background("system")
        else:
            if self.bg_index + 1 < len(self.bg_candidates):
                self.select_background(self.bg_index + 1)
            else:
                self.select_theme_background("system")
        self.save_settings()

    def select_language(self, lang_code: str):
        self.current_lang = lang_code
        self.lang_var.set(lang_code)
        if self.current_lang in self.lang_keys:
            idx = self.lang_keys.index(self.current_lang)
            self.combo_lang.current(idx)
        localization.set_lang(self.current_lang)
        self.refresh_texts()
        self.save_settings()

    def _set_items_visible(self, items: list, visible: bool):
        state = "normal" if visible else "hidden"
        for item in items:
            self.canvas.itemconfigure(item, state=state)

    def switch_tab(self, tab: str):
        if tab not in ("bot", "sim", "settings"):
            return
        self.current_tab = tab
        self.refresh_texts()
        w = self.last_w if self.last_w else 480
        h = self.last_h if self.last_h else 850
        self.draw_ui(w, h)

    def _safe_open_path(self, path: Path):
        try:
            path.mkdir(parents=True, exist_ok=True)
            if hasattr(os, "startfile"):
                os.startfile(path)
            else:
                import subprocess
                subprocess.run(["xdg-open", str(path)])
        except Exception as e:
            print(f"[Warning] Unable to open path {path}: {e}")

    def _setup_menus(self):

        # File Menu
        self.file_menu.delete(0, "end")
        self.file_menu.add_command(
            label=localization.tr("menu_reset_stats", self.current_lang),
            command=self.menu_reset_stats,
        )
        self.file_menu.add_separator()

        # Open Folders Submenu
        self.open_folders_menu.delete(0, "end")
        self.open_folders_menu.add_command(
            label=localization.tr("menu_open_config_dir", self.current_lang),
            command=lambda: self._safe_open_path(auto_bot.APP_DIR),
        )
        self.open_folders_menu.add_command(
            label=localization.tr("menu_open_logs_dir", self.current_lang),
            command=lambda: self._safe_open_path(auto_bot.LOGS_DIR),
        )
        self.open_folders_menu.add_command(
            label=localization.tr("menu_open_bg_dir", self.current_lang),
            command=lambda: self._safe_open_path(auto_bot.BACKGROUNDS_DIR if auto_bot.BACKGROUNDS_DIR.exists() else auto_bot.APP_DIR),
        )
        self.open_folders_menu.add_command(
            label=localization.tr("menu_open_debug_dir", self.current_lang),
            command=lambda: self._safe_open_path(auto_bot.DEBUG_DIR),
        )
        self.file_menu.add_cascade(
            label=localization.tr("menu_open_folders", self.current_lang),
            menu=self.open_folders_menu,
        )
        self.file_menu.add_separator()
        self.file_menu.add_command(
            label=localization.tr("menu_exit", self.current_lang),
            command=self.destroy,
        )

        # Logs Menu (Dedicated top-level menu)
        self.logs_menu.delete(0, "end")
        self.logs_menu.add_command(
            label=localization.tr("menu_save_logs", self.current_lang),
            command=self.save_logs_to_file,
        )
        self.logs_menu.add_command(
            label=localization.tr("menu_clear_logs", self.current_lang),
            command=self.clear_logs,
        )
        self.logs_menu.add_separator()
        self.logs_menu.add_command(
            label=localization.tr("menu_clean_old_logs", self.current_lang),
            command=self.menu_clean_old_logs,
        )
        self.logs_menu.add_command(
            label=localization.tr("menu_open_logs_dir", self.current_lang),
            command=lambda: self._safe_open_path(auto_bot.LOGS_DIR),
        )
        self.logs_menu.add_command(
            label=localization.tr("menu_open_debug_log", self.current_lang),
            command=self.open_debug_log,
        )
        self.logs_menu.add_separator()
        self.logs_menu.add_checkbutton(
            label=f"    {localization.tr('menu_toggle_log', self.current_lang)} (Ctrl+L)",
            variable=self.var_show_log,
            command=self.toggle_log_console,
        )
        self.logs_menu.add_checkbutton(
            label=f"    {localization.tr('menu_enable_debug_log', self.current_lang)}",
            variable=self.var_debug_logging,
            command=self.on_debug_logging_toggle,
        )

        # Background & Theme Menu (Top-level in menubar)
        self.bg_menu.delete(0, "end")
        self.bg_menu.add_radiobutton(
            label=f"    {localization.tr('theme_system', self.current_lang)}",
            variable=self.theme_var,
            value="system",
            command=lambda: self.select_theme("system"),
        )
        self.bg_menu.add_radiobutton(
            label=f"    {localization.tr('theme_light', self.current_lang)}",
            variable=self.theme_var,
            value="light",
            command=lambda: self.select_theme("light"),
        )
        self.bg_menu.add_radiobutton(
            label=f"    {localization.tr('theme_dark', self.current_lang)}",
            variable=self.theme_var,
            value="dark",
            command=lambda: self.select_theme("dark"),
        )
        self.bg_menu.add_separator()
        self.bg_menu.add_radiobutton(
            label=f"    {localization.tr('menu_bg_disabled', self.current_lang)}",
            variable=self.bg_var,
            value=-1,
            command=lambda: self.select_background(-1),
        )
        if self.bg_candidates:
            for i, cand in enumerate(self.bg_candidates):
                label_text = "Minato Aqua" if cand.stem.lower() in ("default", "minato_aqua") else cand.stem.replace("_", " ").title()
                self.bg_menu.add_radiobutton(
                    label=f"    {i + 1}. {label_text}",
                    variable=self.bg_var,
                    value=i,
                    command=lambda idx=i: self.select_background(idx),
                )

        # Field Box Opacity Submenu
        self.opacity_menu = ModernMenu(self.bg_menu, tearoff=0)
        self.opacity_var = tk.IntVar(value=self.field_box_opacity)
        presets = [
            (100, localization.tr("opacity_100", self.current_lang)),
            (85, localization.tr("opacity_85", self.current_lang)),
            (70, localization.tr("opacity_70", self.current_lang)),
            (50, localization.tr("opacity_50", self.current_lang)),
            (30, localization.tr("opacity_30", self.current_lang)),
            (0, localization.tr("opacity_0", self.current_lang)),
        ]
        for val, label in presets:
            self.opacity_menu.add_radiobutton(
                label=f"    {label}",
                variable=self.opacity_var,
                value=val,
                command=lambda v=val: self.set_field_box_opacity(v),
            )
        self.bg_menu.add_separator()
        self.bg_menu.add_cascade(
            label=localization.tr("menu_field_box_opacity", self.current_lang),
            menu=self.opacity_menu,
        )

        # Language Menu (Top-level in menubar)
        self.lang_menu.delete(0, "end")
        available_langs = localization.load_external_locales()
        for code, name in available_langs:
            self.lang_menu.add_radiobutton(
                label=f"    {name}",
                variable=self.lang_var,
                value=code,
                command=lambda c=code: self.select_language(c),
            )

        # Settings Menu (Top-level in menubar)
        self.settings_menu.delete(0, "end")
        self.settings_menu.add_command(
            label=localization.tr("menu_open_settings", self.current_lang),
            command=self.open_settings_dialog,
        )
        self.settings_menu.add_separator()
        self.settings_menu.add_command(
            label=localization.tr("menu_reset_defaults", self.current_lang),
            command=self.restore_default_settings,
        )

        # Simulation Menu
        self.sim_menu.delete(0, "end")
        self.sim_menu.add_command(
            label=localization.tr("menu_run_sim", self.current_lang),
            command=self.start_simulation,
        )
        self.sim_menu.add_command(
            label=localization.tr("menu_compare_all", self.current_lang),
            command=self.start_full_benchmark,
        )
        self.sim_menu.add_separator()
        self.sim_menu.add_command(
            label=localization.tr("menu_export_csv", self.current_lang),
            command=self.export_benchmark_csv,
        )
        self.sim_menu.add_command(
            label=localization.tr("menu_export_json", self.current_lang),
            command=self.export_benchmark_json,
        )
        self.sim_menu.add_separator()
        self.sim_menu.add_command(
            label=localization.tr("menu_clear_logs", self.current_lang),
            command=self.clear_logs,
        )

        # Help Menu
        self.help_menu.delete(0, "end")
        self.help_menu.add_command(
            label=localization.tr("menu_rules_guide", self.current_lang),
            command=self.show_help_rules,
        )
        self.help_menu.add_command(
            label=localization.tr("menu_strategy_guide", self.current_lang),
            command=self.show_help_strategies,
        )
        self.help_menu.add_separator()
        self.help_menu.add_command(
            label=localization.tr("menu_online_docs", self.current_lang),
            command=lambda: webbrowser.open("https://github.com/xAkai97/Hololive-Dreams-Auto-High-Low#readme"),
        )
        self.help_menu.add_separator()
        self.help_menu.add_command(
            label=localization.tr("menu_about", self.current_lang),
            command=self.show_help_about,
        )

        # Update top cascade headers (0-indexed)
        self.menubar.entryconfig(0, label=localization.tr("menu_file", self.current_lang))
        self.menubar.entryconfig(1, label=localization.tr("menu_logs", self.current_lang))
        self.menubar.entryconfig(2, label=localization.tr("menu_settings", self.current_lang))
        self.menubar.entryconfig(3, label=localization.tr("menu_background", self.current_lang))
        self.menubar.entryconfig(4, label=localization.tr("menu_language", self.current_lang))
        self.menubar.entryconfig(5, label=localization.tr("menu_help", self.current_lang))

        if hasattr(self, "menu_buttons"):
            self.menu_buttons["file"].configure(text=localization.tr("menu_file", self.current_lang))
            self.menu_buttons["logs"].configure(text=localization.tr("menu_logs", self.current_lang))
            self.menu_buttons["settings"].configure(text=localization.tr("menu_settings", self.current_lang))
            self.menu_buttons["bg"].configure(text=localization.tr("menu_background", self.current_lang))
            self.menu_buttons["lang"].configure(text=localization.tr("menu_language", self.current_lang))
            self.menu_buttons["help"].configure(text=localization.tr("menu_help", self.current_lang))

    def _on_menu_button_click(self, key: str):
        if getattr(self, "_active_menu_key", None) == key and ModernMenu._active_popups:
            ModernMenu.close_all()
            self._active_menu_key = None
            return
        self._open_menu(key)

    def _open_menu(self, key: str):
        btn = getattr(self, "menu_buttons", {}).get(key)
        menu = getattr(self, "menu_targets", {}).get(key)
        if btn and menu:
            self._active_menu_key = key
            try:
                x = btn.winfo_rootx()
                y = btn.winfo_rooty() + btn.winfo_height()
                menu.post(x, y)
            except Exception:
                pass

    def _on_menu_button_enter(self, key: str):
        btn = getattr(self, "menu_buttons", {}).get(key)
        if btn:
            is_dark = self.theme_palette.get("is_dark", True)
            hover_bg = "#27272A" if is_dark else "#E2E8F0"
            btn.configure(bg=hover_bg)
            if ModernMenu._active_popups and getattr(self, "_active_menu_key", None) != key:
                self._open_menu(key)

    def _on_menu_button_leave(self, key: str):
        btn = getattr(self, "menu_buttons", {}).get(key)
        if btn:
            is_dark = self.theme_palette.get("is_dark", True)
            normal_bg = "#18181B" if is_dark else "#F8FAFC"
            btn.configure(bg=normal_bg)

    def _open_debug_dir(self):
        self._safe_open_path(auto_bot.DEBUG_DIR)

    def clear_logs(self):
        self.sys_redirector.clear()
        try:
            log_file = auto_bot.APP_DIR / "log.txt"
            if log_file.exists():
                log_file.write_text("", encoding="utf-8")
            debug_file = auto_bot.DEBUG_LOG_FILE
            if debug_file.exists():
                debug_file.write_text("", encoding="utf-8")
        except Exception:
            pass

    def show_help_rules(self):
        ui_show_help_rules(self)

    def show_help_strategies(self):
        ui_show_help_strategies(self, len(STRATEGY_KEYS))

    def show_help_about(self):
        ui_show_help_about(self, len(STRATEGY_KEYS))

    def menu_reset_stats(self):
        if self.is_running:
            return
        confirm = messagebox.askyesno(
            localization.tr("menu_reset_stats", self.current_lang),
            localization.tr("stats_reset_confirm", self.current_lang),
        )
        if not confirm:
            return
        self.current_coins = 0
        self.current_fails = 0
        self.current_profit = 0
        self.save_settings(rounds=0)
        self.update_stats_display()
        print(localization.tr("stats_reset_done", self.current_lang))

    def open_settings_dialog(self):
        """Open an interactive popup dialog for configuring global settings."""
        ui_open_settings_dialog(self)

    def open_custom_parametric_dialog(self):
        """Open an interactive popup dialog for fine-tuning custom strategy parameters."""
        ui_open_custom_parametric_dialog(self)

    def menu_clean_old_logs(self):
        count, freed_mb = clean_old_logs(max_days=self.log_retention_days, max_size_mb=self.log_max_size_mb, lang=self.current_lang)
        if count == 0:
            print(localization.tr("log_cleanup_none", self.current_lang))

    def save_user_settings(self):
        try:
            self.target_limit = max(1000, min(50000, int(self.entry_setting_target.get().strip())))
            self.ticket_cost = max(0, min(1000, int(self.entry_setting_ticket.get().strip())))
            strat_idx = STRATEGY_KEYS.index(self.active_mode) if (hasattr(self, "active_mode") and self.active_mode in STRATEGY_KEYS) else (
                self.combo_strategy.current() if 0 <= self.combo_strategy.current() < len(STRATEGY_KEYS) else 0
            )

            auto_bot.save_daily_data(
                self.current_coins,
                self.current_fails,
                language=self.current_lang,
                hotkey=self.current_hotkey,
                background_index=self.bg_index,
                strategy_key=self.active_mode,
                strategy_index=strat_idx,
                target_limit=self.target_limit,
                ticket_cost=self.ticket_cost,
                log_retention_days=self.log_retention_days,
                log_max_size_mb=self.log_max_size_mb,
                opp_a2=bool(self.var_opp_a2.get()),
                opp_3k=bool(self.var_opp_3k.get()),
                opp_4q=bool(self.var_opp_4q.get()),
                opp_5j=bool(self.var_opp_5j.get()),
                opp_610=bool(self.var_opp_610.get()),
                opp_79=bool(self.var_opp_79.get()),
                opp_8=bool(self.var_opp_8.get()),
                modifiers_expanded=getattr(self, "modifiers_expanded", True),
                mod_cat_cards_expanded=getattr(self, "cat_cards_expanded", True),
                mod_cat_bail_expanded=getattr(self, "cat_bail_expanded", True),
                mod_cat_prog_expanded=getattr(self, "cat_prog_expanded", True),
                mod_fast_build=bool(self.var_mod_fast_build.get()),
                mod_drop_78=bool(self.var_mod_drop_78.get()),
                mod_drop_6789=bool(self.var_mod_drop_6789.get()),
                mod_drop_8=bool(self.var_mod_drop_8.get()),
                mod_free_roll=bool(self.var_mod_free_roll.get()),
                mod_sprint_floor=bool(self.var_mod_sprint_floor.get()),
                mod_mega_sprint=bool(self.var_mod_mega_sprint.get()),
                debug_logging=bool(self.var_debug_logging.get()),
                param_min_win_rate=self.param_min_win_rate,
                param_cushion_target=self.param_cushion_target,
                param_sprint_target=self.param_sprint_target,
                param_max_doubles=self.param_max_doubles,
                param_drop_seven_eight=self.param_drop_seven_eight,
                field_box_opacity=self.field_box_opacity,
                show_log=self.show_log,
                theme_mode=self.theme_mode,
                settlement_recovery_mode=self.settlement_recovery_mode,
                settlement_ocr_timeout=self.settlement_ocr_timeout,
            )
            auto_bot.TARGET_LIMIT = self.target_limit
            self.current_profit = self.current_coins - (self.current_fails * self.ticket_cost)
            self.update_stats_display()
            self.canvas.itemconfig(self.coins_max_id, text=f"/ {self.target_limit}")
            self.canvas.itemconfig(self.settings_feedback_id, text=localization.tr("settings_saved_msg", self.current_lang))
            self.after(3000, lambda: self.canvas.itemconfig(self.settings_feedback_id, text=""))
            print(f"[Settings] {localization.tr('settings_saved_msg', self.current_lang)}")
        except Exception as e:
            messagebox.showerror("Settings Error", f"Invalid setting value: {e}")

    def restore_default_settings(self):
        self.entry_setting_target.delete(0, "end")
        self.entry_setting_target.insert(0, "20000")
        self.entry_setting_ticket.delete(0, "end")
        self.entry_setting_ticket.insert(0, "50")
        self.log_retention_days = 14
        self.log_max_size_mb = 20
        self.settlement_recovery_mode = "auto"
        self.settlement_ocr_timeout = 8.0
        self.theme_mode = "system"
        if hasattr(self, "theme_var"):
            self.theme_var.set("system")
        self.apply_theme()
        self.var_opp_a2.set(True)
        self.var_opp_3k.set(False)
        self.var_opp_4q.set(False)
        self.var_opp_5j.set(False)
        self.var_opp_610.set(False)
        self.var_opp_79.set(False)
        self.var_opp_8.set(False)
        self.var_mod_fast_build.set(False)
        self.var_mod_drop_78.set(False)
        self.var_mod_drop_6789.set(False)
        self.var_mod_drop_8.set(False)
        self.var_mod_free_roll.set(False)
        self.var_mod_sprint_floor.set(False)
        self.var_mod_mega_sprint.set(False)
        self.var_debug_logging.set(False)
        self.show_log = False
        self.var_show_log.set(False)
        self.refresh_modifiers_ui()
        self.param_min_win_rate = 60
        self.param_cushion_target = 19800
        self.param_sprint_target = 10000
        self.param_max_doubles = 10
        self.param_drop_seven_eight = False
        self.field_box_opacity = 30
        if hasattr(self, "scale_setting_opacity"):
            self.scale_setting_opacity.set(30)
        if hasattr(self, "lbl_setting_opacity_val"):
            self.lbl_setting_opacity_val.configure(text="30%")
        if hasattr(self, "opacity_var"):
            self.opacity_var.set(30)
        self.select_background(-1)
        self.save_user_settings()

    def _set_sim_buttons_state(self, state: str):
        try:
            self.btn_sim_run.configure(state=state)
            self.btn_sim_compare.configure(state=state)
            self.btn_simulate.configure(state=state)
        except Exception:
            pass

    def start_full_benchmark(self):
        if self.is_running or self.is_simulating:
            return
        self.is_simulating = True
        self._set_sim_buttons_state("disabled")
        threading.Thread(target=self._full_benchmark_worker, daemon=True).start()

    def _full_benchmark_worker(self):
        try:
            import simulation
            sim = simulation.HighLowSimulator(
                num_decks=1,
                tie_loses=False,
                opp_a2=bool(self.var_opp_a2.get()),
                opp_3k=bool(self.var_opp_3k.get()),
                opp_4q=bool(self.var_opp_4q.get()),
                opp_5j=bool(self.var_opp_5j.get()),
                opp_610=bool(self.var_opp_610.get()),
                opp_79=bool(self.var_opp_79.get()),
                opp_8=bool(self.var_opp_8.get()),
                mod_fast_build=bool(self.var_mod_fast_build.get()),
                mod_drop_78=bool(self.var_mod_drop_78.get()),
                mod_drop_6789=bool(self.var_mod_drop_6789.get()),
                mod_drop_8=bool(self.var_mod_drop_8.get()),
                mod_free_roll=bool(self.var_mod_free_roll.get()),
                mod_sprint_floor=bool(self.var_mod_sprint_floor.get()),
                mod_mega_sprint=bool(self.var_mod_mega_sprint.get()),
                cushion_target=int(self.param_cushion_target),
            )
            try:
                days = max(10, int(self.spin_sim_days.get().strip()))
            except ValueError:
                days = 100

            print(f"\n[Benchmark] Comparing all {len(STRATEGY_KEYS)} strategies ({days} days each)...")
            results = sim.run_comparison(days=days, target_limit=self.target_limit)
            self.last_benchmark_results = [
                {
                    "Strategy": r.strategy_name,
                    "Days": r.days,
                    "MeanCoins": r.mean_coins,
                    "StdCoins": r.std_coins,
                    "MeanFails": r.mean_fails,
                    "HitCapPct": r.pct_hit_cap,
                    "Overflow30kPct": r.pct_overflow_30k,
                    "Overflow40kPct": r.pct_overflow_40k,
                    "MaxCoins": r.max_coins,
                }
                for r in results
            ]

            print(f"\n{'=' * 56}")
            print(f"📊 Strategy Benchmark Comparison ({days} Days Each)")
            print(f"{'=' * 56}")
            print(f"{'Rank':<5} {'Strategy':<26} {'Avg Coins':>11} {'Cap%':>7}")
            print(f"{'-' * 56}")
            sorted_res = sorted(self.last_benchmark_results, key=lambda x: x['MeanCoins'], reverse=True)
            for rank, r in enumerate(sorted_res, 1):
                clean_name = re.sub(r'^[^\w\s]+\s*', '', r['Strategy'])
                print(f"#{rank:<4} {clean_name[:25]:<26} {r['MeanCoins']:>11,.0f} {r['HitCapPct']:>6.1f}%")
            print(f"{'=' * 56}\n")

            self.ui_queue.put(("callback", lambda: self.show_benchmark_results_dialog(self.last_benchmark_results)))
        except Exception as e:
            print(f"[Benchmark Error] {e}")
        finally:
            self.is_simulating = False
            self.ui_queue.put(("callback", lambda: self._set_sim_buttons_state("normal")))

    def show_benchmark_results_dialog(self, results):
        """Display comparative benchmark results in a clean, human-friendly GUI table window."""
        ui_show_benchmark_results_dialog(self, results)

    def export_benchmark_csv(self):
        ui_export_benchmark_csv(self, self.last_benchmark_results)

    def export_benchmark_json(self):
        ui_export_benchmark_json(self, self.last_benchmark_results)

    def on_strategy_change(self, event=None):
        idx = self.combo_strategy.current()
        if isinstance(idx, int) and 0 <= idx < len(STRATEGY_KEYS):
            self.active_mode = STRATEGY_KEYS[idx]
        self.update_strategy_description()
        self.save_settings()
        w = self.last_w if self.last_w else 480
        h = self.last_h if self.last_h else 850
        self.draw_ui(w, h)

    def apply_strategy_preset(self, key: str):
        if self.is_running:
            return
        if key in STRATEGY_KEYS:
            idx = STRATEGY_KEYS.index(key)
            self.combo_strategy.current(idx)
            self.active_mode = key
            self.update_strategy_description()
            self.save_settings()
            w = self.last_w if self.last_w else 480
            h = self.last_h if self.last_h else 850
            self.draw_ui(w, h)

    def _update_preset_styles(self):
        pass

    def _sync_modifier_states(self):
        fast_build = bool(self.var_mod_fast_build.get())
        drop_6789 = bool(self.var_mod_drop_6789.get())
        drop_78 = bool(self.var_mod_drop_78.get())
        drop_8 = bool(self.var_mod_drop_8.get())

        opp_610 = bool(self.var_opp_610.get())
        opp_79 = bool(self.var_opp_79.get())
        opp_8 = bool(self.var_opp_8.get())

        sprint_floor = bool(self.var_mod_sprint_floor.get())
        mega_sprint = bool(self.var_mod_mega_sprint.get())

        if fast_build:
            # Fast Build forces doubling on all cards under cushion,
            # superseding Card Overrides and Defensive Bailouts.
            state_drop_6789 = "disabled"
            state_drop_78 = "disabled"
            state_drop_8 = "disabled"
            state_opp_a2 = "disabled"
            state_opp_3k = "disabled"
            state_opp_4q = "disabled"
            state_opp_5j = "disabled"
            state_opp_610 = "disabled"
            state_opp_79 = "disabled"
            state_opp_8 = "disabled"
        else:
            state_drop_6789 = "normal"
            state_drop_78 = "normal"
            state_drop_8 = "normal"
            state_opp_a2 = "normal"
            state_opp_3k = "normal"
            state_opp_4q = "normal"
            state_opp_5j = "normal"
            state_opp_610 = "normal"
            state_opp_79 = "normal"
            state_opp_8 = "normal"

            if drop_6789:
                state_drop_78 = "disabled"
                state_drop_8 = "disabled"
                state_opp_610 = "disabled"
                state_opp_79 = "disabled"
                state_opp_8 = "disabled"
            elif drop_78:
                state_drop_6789 = "disabled"
                state_drop_8 = "disabled"
                state_opp_79 = "disabled"
                state_opp_8 = "disabled"
            elif drop_8:
                state_drop_6789 = "disabled"
                state_drop_78 = "disabled"
                state_opp_8 = "disabled"
            else:
                if opp_8:
                    state_drop_6789 = "disabled"
                    state_drop_78 = "disabled"
                    state_drop_8 = "disabled"
                elif opp_79:
                    state_drop_6789 = "disabled"
                    state_drop_78 = "disabled"
                elif opp_610:
                    state_drop_6789 = "disabled"

        state_sprint_floor = "disabled" if mega_sprint else "normal"
        state_mega_sprint = "disabled" if sprint_floor else "normal"

        for widget, state in (
            (getattr(self, "chk_opp_a2", None), state_opp_a2),
            (getattr(self, "chk_opp_3k", None), state_opp_3k),
            (getattr(self, "chk_opp_4q", None), state_opp_4q),
            (getattr(self, "chk_opp_5j", None), state_opp_5j),
            (getattr(self, "chk_opp_610", None), state_opp_610),
            (getattr(self, "chk_opp_79", None), state_opp_79),
            (getattr(self, "chk_opp_8", None), state_opp_8),
            (getattr(self, "chk_mod_drop_6789", None), state_drop_6789),
            (getattr(self, "chk_mod_drop_78", None), state_drop_78),
            (getattr(self, "chk_mod_drop_8", None), state_drop_8),
            (getattr(self, "chk_mod_sprint_floor", None), state_sprint_floor),
            (getattr(self, "chk_mod_mega_sprint", None), state_mega_sprint),
        ):
            if widget:
                try:
                    widget.configure(state=state)
                except Exception:
                    pass

    def on_opp_toggle(self):
        if bool(self.var_opp_8.get()):
            self.var_mod_drop_8.set(False)
            self.var_mod_drop_78.set(False)
            self.var_mod_drop_6789.set(False)
            self.mod_drop_8 = False
            self.mod_drop_78 = False
            self.mod_drop_6789 = False
            self.param_drop_seven_eight = False
        if bool(self.var_opp_79.get()):
            self.var_mod_drop_78.set(False)
            self.var_mod_drop_6789.set(False)
            self.mod_drop_78 = False
            self.mod_drop_6789 = False
            self.param_drop_seven_eight = False
        if bool(self.var_opp_610.get()):
            self.var_mod_drop_6789.set(False)
            self.mod_drop_6789 = False

        self._sync_modifier_states()
        self.save_settings()
        self.refresh_modifiers_ui()

    def toggle_modifiers_drawer(self):
        self.modifiers_expanded = not self.modifiers_expanded
        self.save_settings()
        self.refresh_modifiers_ui()
        w = self.last_w if self.last_w else 480
        h = self.last_h if self.last_h else 850
        self.draw_ui(w, h)

    def toggle_mod_cat(self, cat: str):
        if cat == "cards":
            self.cat_cards_expanded = not self.cat_cards_expanded
        elif cat == "bail":
            self.cat_bail_expanded = not self.cat_bail_expanded
        elif cat == "prog":
            self.cat_prog_expanded = not self.cat_prog_expanded
        self._update_mod_category_headers()
        self.save_settings()
        w = self.last_w if self.last_w else 480
        h = self.last_h if self.last_h else 850
        self.draw_ui(w, h)

    def _update_mod_category_headers(self):
        arrow_cards = "▼" if getattr(self, "cat_cards_expanded", True) else "▶"
        arrow_bail = "▼" if getattr(self, "cat_bail_expanded", True) else "▶"
        arrow_prog = "▼" if getattr(self, "cat_prog_expanded", True) else "▶"

        if hasattr(self, "lbl_sec_cards"):
            self.lbl_sec_cards.configure(text=f"{arrow_cards} {localization.tr('sec_card_overrides', self.current_lang)}")
        if hasattr(self, "lbl_sec_bail"):
            self.lbl_sec_bail.configure(text=f"{arrow_bail} {localization.tr('sec_defensive_bailouts', self.current_lang)}")
        if hasattr(self, "lbl_sec_prog"):
            self.lbl_sec_prog.configure(text=f"{arrow_prog} {localization.tr('sec_progression_sprint', self.current_lang)}")

    def on_modifier_toggle(self):
        curr_6789 = bool(self.var_mod_drop_6789.get())
        curr_78 = bool(self.var_mod_drop_78.get())
        curr_8 = bool(self.var_mod_drop_8.get())

        if curr_6789 and (not self.mod_drop_6789 or curr_78 or curr_8):
            self.var_mod_drop_78.set(False)
            self.var_mod_drop_8.set(False)
            self.var_opp_610.set(False)
            self.var_opp_79.set(False)
            self.var_opp_8.set(False)
        elif curr_78 and (not self.mod_drop_78 or curr_6789 or curr_8):
            self.var_mod_drop_6789.set(False)
            self.var_mod_drop_8.set(False)
            self.var_opp_79.set(False)
            self.var_opp_8.set(False)
        elif curr_8 and (not self.mod_drop_8 or curr_6789 or curr_78):
            self.var_mod_drop_6789.set(False)
            self.var_mod_drop_78.set(False)
            self.var_opp_8.set(False)

        curr_mega = bool(self.var_mod_mega_sprint.get())
        curr_sprint = bool(self.var_mod_sprint_floor.get())
        if curr_mega and curr_sprint:
            if not self.mod_mega_sprint:
                self.var_mod_sprint_floor.set(False)
            else:
                self.var_mod_mega_sprint.set(False)

        self._sync_modifier_states()

        self.mod_fast_build = bool(self.var_mod_fast_build.get())
        self.mod_drop_78 = bool(self.var_mod_drop_78.get())
        self.mod_drop_6789 = bool(self.var_mod_drop_6789.get())
        self.mod_drop_8 = bool(self.var_mod_drop_8.get())
        self.mod_free_roll = bool(self.var_mod_free_roll.get())
        self.mod_sprint_floor = bool(self.var_mod_sprint_floor.get())
        self.mod_mega_sprint = bool(self.var_mod_mega_sprint.get())
        self.param_drop_seven_eight = self.mod_drop_78
        self.save_settings()
        self.refresh_modifiers_ui()

    def on_debug_logging_toggle(self):
        self.debug_logging = bool(self.var_debug_logging.get())
        self.save_settings()

    def open_debug_log(self):
        debug_file = auto_bot.DEBUG_LOG_FILE
        if not debug_file.exists():
            debug_file.write_text(f"=== Hololive Dreams Debug Log ({time.strftime('%Y-%m-%d %H:%M:%S')}) ===\n", encoding="utf-8")
        self._safe_open_path(debug_file)

    def refresh_modifiers_ui(self):
        self._sync_modifier_states()
        fast_build = bool(self.var_mod_fast_build.get())
        if fast_build:
            active_list = [
                fast_build,
                bool(self.var_mod_free_roll.get()),
                bool(self.var_mod_sprint_floor.get()),
                bool(self.var_mod_mega_sprint.get()),
            ]
        else:
            active_list = [
                bool(self.var_opp_a2.get()),
                bool(self.var_opp_3k.get()),
                bool(self.var_opp_4q.get()),
                bool(self.var_opp_5j.get()),
                bool(self.var_opp_610.get()),
                bool(self.var_opp_79.get()),
                bool(self.var_opp_8.get()),
                bool(self.var_mod_drop_78.get()),
                bool(self.var_mod_drop_6789.get()),
                bool(self.var_mod_drop_8.get()),
                bool(self.var_mod_free_roll.get()),
                bool(self.var_mod_sprint_floor.get()),
                bool(self.var_mod_mega_sprint.get()),
            ]
        active = sum(active_list)
        arrow = "▼" if getattr(self, "modifiers_expanded", True) else "▶"
        header_text = f"{arrow} {localization.tr('lbl_modifiers_header', self.current_lang, active=active)}"
        if hasattr(self, "btn_toggle_modifiers"):
            self.btn_toggle_modifiers.configure(text=header_text)

    def save_settings(self, rounds: Optional[int] = None):
        strat_idx = STRATEGY_KEYS.index(self.active_mode) if (hasattr(self, "active_mode") and self.active_mode in STRATEGY_KEYS) else (
            self.combo_strategy.current() if 0 <= self.combo_strategy.current() < len(STRATEGY_KEYS) else 0
        )
        auto_bot.save_daily_data(
            self.current_coins,
            self.current_fails,
            rounds=rounds,
            language=self.current_lang,
            hotkey=self.current_hotkey,
            background_index=self.bg_index,
            strategy_key=self.active_mode,
            strategy_index=strat_idx,
            target_limit=self.target_limit,
            ticket_cost=self.ticket_cost,
            opp_a2=bool(self.var_opp_a2.get()),
            opp_3k=bool(self.var_opp_3k.get()),
            opp_4q=bool(self.var_opp_4q.get()),
            opp_5j=bool(self.var_opp_5j.get()),
            opp_610=bool(self.var_opp_610.get()),
            opp_79=bool(self.var_opp_79.get()),
            opp_8=bool(self.var_opp_8.get()),
            modifiers_expanded=self.modifiers_expanded,
            mod_cat_cards_expanded=getattr(self, "cat_cards_expanded", True),
            mod_cat_bail_expanded=getattr(self, "cat_bail_expanded", True),
            mod_cat_prog_expanded=getattr(self, "cat_prog_expanded", True),
            mod_fast_build=bool(self.var_mod_fast_build.get()),
            mod_drop_78=bool(self.var_mod_drop_78.get()),
            mod_drop_6789=bool(self.var_mod_drop_6789.get()),
            mod_drop_8=bool(self.var_mod_drop_8.get()),
            mod_free_roll=bool(self.var_mod_free_roll.get()),
            mod_sprint_floor=bool(self.var_mod_sprint_floor.get()),
            mod_mega_sprint=bool(self.var_mod_mega_sprint.get()),
            debug_logging=bool(self.var_debug_logging.get()),
            param_min_win_rate=self.param_min_win_rate,
            param_cushion_target=self.param_cushion_target,
            param_sprint_target=self.param_sprint_target,
            param_max_doubles=self.param_max_doubles,
            param_drop_seven_eight=self.param_drop_seven_eight,
            field_box_opacity=self.field_box_opacity,
            show_log=self.show_log,
            theme_mode=self.theme_mode,
        )

    def on_stats_manual_edit(self, event=None):
        if self.is_running:
            return
        try:
            raw_coins = self.entry_coins.get().strip()
            raw_fails = self.entry_fails.get().strip()
            new_coins = max(0, int(raw_coins)) if raw_coins else 0
            new_fails = max(0, int(raw_fails)) if raw_fails else 0
            self.current_coins = new_coins
            self.current_fails = new_fails
            self.current_profit = self.current_coins - (self.current_fails * self.ticket_cost)
            self.save_settings()
            self.update_stats_display()
        except ValueError:
            self.update_stats_display()

    def update_stats_display(self, coins=None, fails=None, profit=None):
        if coins is not None: self.current_coins = coins
        if fails is not None: self.current_fails = fails
        if profit is not None:
            self.current_profit = profit
        else:
            self.current_profit = self.current_coins - (self.current_fails * self.ticket_cost)

        coins_str = str(self.current_coins)
        if self.entry_coins.get() != coins_str:
            prev_state = str(self.entry_coins.cget("state"))
            if prev_state == "disabled":
                self.entry_coins.configure(state="normal")
            self.entry_coins.delete(0, "end")
            self.entry_coins.insert(0, coins_str)
            if prev_state == "disabled":
                self.entry_coins.configure(state="disabled")

        fails_str = str(self.current_fails)
        if self.entry_fails.get() != fails_str:
            prev_state = str(self.entry_fails.cget("state"))
            if prev_state == "disabled":
                self.entry_fails.configure(state="normal")
            self.entry_fails.delete(0, "end")
            self.entry_fails.insert(0, fails_str)
            if prev_state == "disabled":
                self.entry_fails.configure(state="disabled")

        profit_text = localization.tr("net_profit_prefix", self.current_lang, profit=self.current_profit)
        self.canvas.itemconfig(self.profit_id, text=f"|  {profit_text}")

    def _apply_locale_fonts(self):
        family = get_locale_font_family(self.current_lang)
        self.font_family = family

        font_button = (family, 9, "bold")
        font_hotkey = (family, 10, "bold")
        font_normal = (family, 12, "bold")
        font_small_bold = (family, 9, "bold")
        font_desc = (family, 9)
        font_entry = (family, 10, "bold")

        self.style.configure("TButton", font=font_button)
        self.style.configure("Hotkey.TButton", font=font_hotkey)
        self.style.configure("Tab.TButton", font=font_button)
        self.style.configure("ActiveTab.TButton", font=font_button)
        self.style.configure("Config.TButton", font=font_button)
        self.style.configure("ModifierDrawer.TButton", font=font_button, padding=(8, 4))

        for item_id in (
            getattr(self, "hotkey_label_id", None),
            getattr(self, "status_id", None),
            getattr(self, "coins_label_id", None),
            getattr(self, "coins_max_id", None),
            getattr(self, "fails_label_id", None),
            getattr(self, "profit_id", None),
            getattr(self, "lbl_setting_title_id", None),
        ):
            if item_id:
                try:
                    self.canvas.itemconfig(item_id, font=font_normal)
                except Exception:
                    pass

        if getattr(self, "strategy_desc_id", None):
            self.canvas.itemconfig(self.strategy_desc_id, font=font_desc)
        if getattr(self, "sim_days_label_id", None):
            self.canvas.itemconfig(self.sim_days_label_id, font=font_small_bold)
        if getattr(self, "lang_label_id", None):
            self.canvas.itemconfig(self.lang_label_id, font=font_small_bold)
        if getattr(self, "lbl_setting_bg_id", None):
            self.canvas.itemconfig(self.lbl_setting_bg_id, font=font_small_bold)
        if getattr(self, "lbl_setting_target_id", None):
            self.canvas.itemconfig(self.lbl_setting_target_id, font=font_small_bold)
        if getattr(self, "lbl_setting_ticket_id", None):
            self.canvas.itemconfig(self.lbl_setting_ticket_id, font=font_small_bold)
        if getattr(self, "settings_feedback_id", None):
            self.canvas.itemconfig(self.settings_feedback_id, font=font_small_bold)
        font_section = (family, 8, "bold")
        for lbl in (
            getattr(self, "lbl_sec_cards", None),
            getattr(self, "lbl_sec_bail", None),
            getattr(self, "lbl_sec_prog", None),
        ):
            if lbl:
                try:
                    lbl.configure(font=font_section)
                except Exception:
                    pass
        for chk in (
            getattr(self, "chk_opp_a2", None),
            getattr(self, "chk_opp_3k", None),
            getattr(self, "chk_opp_4q", None),
            getattr(self, "chk_opp_5j", None),
            getattr(self, "chk_opp_610", None),
            getattr(self, "chk_opp_79", None),
            getattr(self, "chk_opp_8", None),
            getattr(self, "chk_mod_fast_build", None),
            getattr(self, "chk_mod_drop_78", None),
            getattr(self, "chk_mod_drop_6789", None),
            getattr(self, "chk_mod_drop_8", None),
            getattr(self, "chk_mod_free_roll", None),
            getattr(self, "chk_mod_sprint_floor", None),
            getattr(self, "chk_mod_mega_sprint", None),
        ):
            if chk:
                try:
                    chk.configure(font=font_small_bold)
                except Exception:
                    pass
        if getattr(self, "log_text", None):
            self.log_text.configure(font=(self.font_family, 11, "bold"))

        for widget in (
            getattr(self, "entry_coins", None),
            getattr(self, "entry_fails", None),
            getattr(self, "spin_sim_days", None),
            getattr(self, "entry_setting_target", None),
            getattr(self, "entry_setting_ticket", None),
        ):
            if widget:
                try:
                    widget.configure(font=font_entry)
                except Exception:
                    pass

    def refresh_texts(self):
        self._apply_locale_fonts()
        labels = localization.get_strategy_labels(self.current_lang)
        self.combo_strategy.configure(values=labels,
                                      state='disabled' if self.is_running else 'readonly')
        if labels:
            if hasattr(self, "active_mode") and self.active_mode in STRATEGY_KEYS:
                valid_idx = STRATEGY_KEYS.index(self.active_mode)
            else:
                selected_strategy = self.combo_strategy.current()
                valid_idx = min(max(0, selected_strategy), len(labels) - 1)
                self.active_mode = STRATEGY_KEYS[valid_idx] if valid_idx < len(STRATEGY_KEYS) else 'max_profit'
            self.combo_strategy.current(valid_idx)
        title = localization.tr("title", self.current_lang)
        self.title(title)
        self.canvas.itemconfig(self.title_id, text="", state="hidden")
        self.canvas.itemconfig(self.lang_label_id, text=localization.tr("lang_label", self.current_lang))
        self.canvas.itemconfig(self.lbl_setting_bg_id, text=localization.tr("menu_background", self.current_lang))
        self.canvas.itemconfig(self.hotkey_label_id, text=localization.tr("hotkey_label", self.current_lang))
        self.canvas.itemconfig(self.coins_label_id, text=localization.tr("coins_label", self.current_lang))
        self.canvas.itemconfig(self.fails_label_id, text=localization.tr("fails_label", self.current_lang))
        self.canvas.itemconfig(self.coins_max_id, text=f"/ {self.target_limit}")
        self.bg_var.set(self._get_bg_var_value())
        self.lang_var.set(self.current_lang)
        self._update_combo_bg_values()

        # Tab button titles & styles
        bot_prefix = "● " if self.current_tab == "bot" else ""
        sim_prefix = "● " if self.current_tab == "sim" else ""
        self.tab_btn_bot.configure(
            text=f"{bot_prefix}{localization.tr('tab_bot', self.current_lang)}",
            style="ActiveTab.TButton" if self.current_tab == "bot" else "Tab.TButton",
        )
        self.tab_btn_sim.configure(
            text=f"{sim_prefix}{localization.tr('tab_simulation', self.current_lang)}",
            style="ActiveTab.TButton" if self.current_tab == "sim" else "Tab.TButton",
        )

        # Bot tab buttons
        self.btn_bg.configure(text=localization.tr("btn_bg", self.current_lang))
        self.btn_exit.configure(text=localization.tr("btn_exit", self.current_lang))
        self.btn_config_strat.configure(text=localization.tr("btn_config_params", self.current_lang))
        self._update_mod_category_headers()
        self.chk_opp_a2.configure(text=localization.tr("chk_opp_a2", self.current_lang))
        self.chk_opp_3k.configure(text=localization.tr("chk_opp_3k", self.current_lang))
        self.chk_opp_4q.configure(text=localization.tr("chk_opp_4q", self.current_lang))
        self.chk_opp_5j.configure(text=localization.tr("chk_opp_5j", self.current_lang))
        self.chk_opp_610.configure(text=localization.tr("chk_opp_610", self.current_lang))
        self.chk_opp_79.configure(text=localization.tr("chk_opp_79", self.current_lang))
        self.chk_opp_8.configure(text=localization.tr("chk_opp_8", self.current_lang))
        self.chk_mod_drop_78.configure(text=localization.tr("lbl_mod_drop_78", self.current_lang))
        self.chk_mod_drop_6789.configure(text=localization.tr("lbl_mod_drop_6789", self.current_lang))
        self.chk_mod_drop_8.configure(text=localization.tr("lbl_mod_drop_8", self.current_lang))
        self.chk_mod_fast_build.configure(text=localization.tr("lbl_mod_fast_build", self.current_lang))
        self.chk_mod_free_roll.configure(text=localization.tr("lbl_mod_free_roll", self.current_lang))
        self.chk_mod_sprint_floor.configure(text=localization.tr("lbl_mod_sprint_floor", self.current_lang))
        self.chk_mod_mega_sprint.configure(text=localization.tr("lbl_mod_mega_sprint", self.current_lang))
        self.refresh_modifiers_ui()
        self.update_strategy_description()
        self._update_preset_styles()

        # Update localized hover tooltips
        for key, tip in getattr(self, "tooltips", {}).items():
            tip.update_text(localization.tr(f"tip_{key}", self.current_lang))

        # Simulation tab widgets
        self.canvas.itemconfig(self.sim_days_label_id, text=localization.tr("sim_days_label", self.current_lang))
        self.btn_sim_run.configure(text=localization.tr("btn_run_sim", self.current_lang),
                                   state='disabled' if (self.is_running or self.is_simulating) else 'normal')
        self.btn_sim_compare.configure(text=localization.tr("btn_compare_all", self.current_lang),
                                       state='disabled' if (self.is_running or self.is_simulating) else 'normal')
        self.btn_sim_export_csv.configure(text=localization.tr("btn_export_csv", self.current_lang))
        self.btn_sim_export_json.configure(text=localization.tr("btn_export_json", self.current_lang))
        self.btn_clear_logs.configure(text=localization.tr("btn_clear_logs", self.current_lang))

        # Settings tab widgets (Global Settings & Custom Params Launcher)
        self.canvas.itemconfig(self.lbl_setting_title_id, text=localization.tr("settings_title", self.current_lang))
        self.canvas.itemconfig(self.lbl_setting_target_id, text=localization.tr("target_limit_label", self.current_lang))
        self.canvas.itemconfig(self.lbl_setting_ticket_id, text=localization.tr("ticket_cost_label", self.current_lang))
        self.canvas.itemconfig(self.lbl_setting_opacity_id, text=localization.tr("field_box_opacity_label", self.current_lang))
        self.btn_open_custom_dialog.configure(text=localization.tr("btn_custom_strategy_config", self.current_lang))
        self.chk_setting_show_log.configure(text=localization.tr("menu_toggle_log", self.current_lang))
        self.chk_setting_debug_log.configure(text=localization.tr("debug_logging_label", self.current_lang))
        self.btn_save_settings.configure(text=localization.tr("btn_save_settings", self.current_lang))
        self.btn_restore_defaults.configure(text=localization.tr("btn_restore_defaults", self.current_lang))
        self.btn_back_to_bot.configure(text=localization.tr("btn_back_to_bot", self.current_lang, default="← Back to Auto Bot"))

        self._setup_menus()
        self.update_stats_display()

        if not self.is_running:
            self.entry_coins.configure(state="normal")
            self.entry_fails.configure(state="normal")
            idle_color = self.theme_palette.get("status_idle", "#0F172A")
            self.canvas.itemconfig(self.status_id, text=localization.tr("status_idle", self.current_lang), fill=idle_color)
            self.btn_start.configure(text=localization.tr("btn_start", self.current_lang), state="normal")
            self.btn_stop.configure(text=localization.tr("btn_stop", self.current_lang), state="disabled")
            self.btn_hotkey.configure(state="normal")
        else:
            self.entry_coins.configure(state="disabled")
            self.entry_fails.configure(state="disabled")
            running_color = self.theme_palette.get("status_running", "#16A34A")
            self.canvas.itemconfig(self.status_id, fill=running_color)
            self.btn_start.configure(text=localization.tr("btn_running", self.current_lang), state="disabled")
            self.btn_stop.configure(text=localization.tr("btn_stop", self.current_lang), state="normal")
            self.btn_hotkey.configure(state="disabled")

    def update_strategy_description(self):
        desc_key = f"desc_{self.active_mode}"
        desc_text = localization.tr(desc_key, self.current_lang)
        self.canvas.itemconfig(self.strategy_desc_id, text=desc_text)

    def start_simulation(self):
        if self.is_running or self.is_simulating:
            return
        self.is_simulating = True
        self._set_sim_buttons_state("disabled")
        threading.Thread(target=self._simulation_worker, daemon=True).start()

    def _simulation_worker(self):
        try:
            import simulation
            from strategies import strategy_kwargs_from_config
            idx = self.combo_strategy.current()
            key = STRATEGY_KEYS[idx] if (isinstance(idx, int) and 0 <= idx < len(STRATEGY_KEYS)) else 'max_profit'
            labels = localization.get_strategy_labels(self.current_lang)
            strat_name = labels[idx] if (0 <= idx < len(labels)) else key
            try:
                days = max(10, int(self.spin_sim_days.get().strip()))
            except (ValueError, AttributeError):
                days = 100

            print(localization.tr("sim_running", self.current_lang, name=strat_name))
            sim = simulation.HighLowSimulator(
                num_decks=1,
                tie_loses=False,
                opp_a2=bool(self.var_opp_a2.get()),
                opp_3k=bool(self.var_opp_3k.get()),
                opp_4q=bool(self.var_opp_4q.get()),
                opp_5j=bool(self.var_opp_5j.get()),
                opp_610=bool(self.var_opp_610.get()),
                opp_79=bool(self.var_opp_79.get()),
                opp_8=bool(self.var_opp_8.get()),
                mod_fast_build=bool(self.var_mod_fast_build.get()),
                mod_drop_78=bool(self.var_mod_drop_78.get()),
                mod_drop_6789=bool(self.var_mod_drop_6789.get()),
                mod_drop_8=bool(self.var_mod_drop_8.get()),
                mod_free_roll=bool(self.var_mod_free_roll.get()),
                mod_sprint_floor=bool(self.var_mod_sprint_floor.get()),
                mod_mega_sprint=bool(self.var_mod_mega_sprint.get()),
                cushion_target=int(self.param_cushion_target),
            )
            strat = STRATEGY_REGISTRY[key]
            strat_kwargs = strategy_kwargs_from_config(key, {
                "param_min_win_rate": self.param_min_win_rate,
                "param_cushion_target": self.param_cushion_target,
                "param_sprint_target": self.param_sprint_target,
                "param_max_doubles": self.param_max_doubles,
                "param_drop_seven_eight": self.param_drop_seven_eight,
            }) or None
            res = sim.run_monte_carlo(strat, strategy_kwargs=strat_kwargs, days=days, target_limit=self.target_limit)

            self.last_benchmark_results = [{
                "Strategy": res.strategy_name,
                "Days": res.days,
                "MeanCoins": res.mean_coins,
                "StdCoins": res.std_coins,
                "MeanFails": res.mean_fails,
                "HitCapPct": res.pct_hit_cap,
                "Overflow30kPct": res.pct_overflow_30k,
                "Overflow40kPct": res.pct_overflow_40k,
                "MaxCoins": res.max_coins,
            }]

            print(localization.tr("sim_header", self.current_lang, name=strat_name))
            print(localization.tr("sim_metric_coins", self.current_lang, mean=res.mean_coins, std=res.std_coins, max=res.max_coins))
            print(localization.tr("sim_metric_fails", self.current_lang, fails=res.mean_fails))
            print(localization.tr("sim_metric_cap", self.current_lang, cap=res.pct_hit_cap))
            print(localization.tr("sim_metric_overflow", self.current_lang, over30=res.pct_overflow_30k, over40=res.pct_overflow_40k))
            print(localization.tr("sim_footer", self.current_lang))
        except Exception as e:
            print(f"[Simulation Error] {e}")
        finally:
            self.is_simulating = False
            self.ui_queue.put(("callback", lambda: self._set_sim_buttons_state("normal" if not self.is_running else "disabled")))

    def change_language(self, event=None):
        idx = self.combo_lang.current()
        self.current_lang = self.lang_keys[idx]
        localization.set_lang(self.current_lang)
        self.refresh_texts()
        self.save_settings()

    def start_bot(self):
        if self.is_running or self.is_simulating:
            return
        idx = self.combo_strategy.current()
        self.active_mode = STRATEGY_KEYS[idx] if (isinstance(idx, int) and 0 <= idx < len(STRATEGY_KEYS)) else 'max_profit'
        self.save_settings()
        self.is_running = True
        self._set_sim_buttons_state("disabled")
        self.refresh_texts()
        self.canvas.itemconfig(self.status_id,
                               text=localization.tr("status_running", self.current_lang),
                               fill=self.theme_palette.get("status_running", "#16A34A"))

        self.sys_redirector.clear()
        try:
            log_file = auto_bot.APP_DIR / "log.txt"
            with open(log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(f"\n--- {localization.tr('bot_started_status', self.current_lang, time=time.strftime('%Y-%m-%d %H:%M:%S'))} ---\n")
        except Exception:
            pass

        auto_bot.bot_running = True
        self.bot_thread = threading.Thread(target=self.run_bot, daemon=True)
        self.bot_thread.start()

    def stop_bot(self):
        if not self.is_running: return

        print(localization.tr("system_stopping", self.current_lang))
        auto_bot.bot_running = False
        self.btn_stop.configure(state="disabled")
        self.canvas.itemconfig(self.status_id,
                               text=localization.tr("status_stopping", self.current_lang),
                               fill=self.theme_palette.get("status_stopping", "#D97706"))

    def _on_bot_crashed(self, err_msg):
        self.canvas.itemconfig(self.status_id,
                               text=localization.tr("status_crashed", self.current_lang),
                               fill=self.theme_palette.get("status_crashed", "#DC2626"))

    def _on_bot_finished(self):
        self.is_running = False
        self._set_sim_buttons_state("normal")
        self.refresh_texts()

    def prompt_settlement_dialog(self, expected, observed):
        res_queue = queue.Queue()
        self.after(0, self._show_settlement_modal, expected, observed, res_queue)
        return res_queue.get()

    def _show_settlement_modal(self, expected, observed, res_queue):
        ui_show_settlement_modal(self, expected, observed, res_queue)

    def run_bot(self):
        try:
            auto_bot.auto_play_loop(
                self.active_mode,
                on_stats_update=lambda c, f, p: self.ui_queue.put(("stats", (c, f, p))),
                lang=self.current_lang,
                on_prompt_settlement=self.prompt_settlement_dialog,
            )
        except Exception as e:
            err_msg = localization.format_error(e, self.current_lang)
            print(localization.tr("system_crash", self.current_lang, error=err_msg))
            self.ui_queue.put(("callback", lambda msg=err_msg: self._on_bot_crashed(msg)))
        finally:
            auto_bot.bot_running = False
            self.ui_queue.put(("callback", self._on_bot_finished))
            print(localization.tr("system_stopped", self.current_lang))

    def destroy(self):
        self._is_destroyed = True
        try:
            self.save_settings()
        except Exception:
            pass
        try:
            log_file = auto_bot.APP_DIR / "log.txt"
            with open(log_file, "a", encoding="utf-8", errors="replace") as f:
                f.write(f"\n=== UI Session Closed: {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
        except Exception:
            pass
        self.is_listening = False
        self.is_running = False
        self.is_simulating = False
        auto_bot.bot_running = False
        sys.stdout = self.original_stdout
        try:
            keyboard.unhook_all()
        except Exception:
            pass
        super().destroy()


if __name__ == "__main__":
    app = HololiveBotUI()
    app.mainloop()
