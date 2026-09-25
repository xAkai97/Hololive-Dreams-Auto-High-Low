import ctypes

# Configure DPI before Tk or any capture/input library creates a window. This
# keeps template coordinates aligned on scaled and multi-monitor desktops.
try:
    ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    pass

import tkinter as tk
from tkinter import ttk
import threading
import sys
import os
from pathlib import Path
import json
import time
import re
from PIL import Image, ImageTk
import keyboard

# Ensure src directory is accessible when running from source or bundle
SRC_DIR = Path(__file__).resolve().parent / "src"
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import auto_bot
import localization

# Must be executed before window creation: Notify Windows this is an independent app to bind its taskbar icon
try:
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("hololive.dreams.autobot.v1")
except Exception:
    pass

TRANSLATIONS = localization.TRANSLATIONS
STRATEGY_LABELS = localization.STRATEGY_LABELS


def load_saved_stats():
    if auto_bot.DATA_FILE.exists():
        try:
            with auto_bot.DATA_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
                if data.get("date") == time.strftime("%Y-%m-%d"):
                    c = data.get("coins", 0)
                    fl = data.get("fails", 0)
                    return c, fl, c - (fl * 50)
        except:
            pass
    return 0, 0, 0


get_local_data = load_saved_stats


# ================= Output Interceptor & Virtual Scrolling Engine =================
class RedirectText:
    def __init__(self, ui):
        self.ui = ui
        self.raw_text = ""

    def write(self, string):
        self.ui.after(0, self._write, string)

    def _write(self, string):
        if not string: return
        self.raw_text += string

        m_profit = re.search(r"(?:今日净利润|今日淨利潤|Net profit|Net|純利益):\s*([+-]?\d+)", string, re.I)
        m_fails = re.search(r"(?:累计失败|累計失敗|Fails|失敗):\s*(\d+)", string, re.I)
        m_coins = re.search(r"(?:当前总金币|當前總金幣|当日累计代币|當日累計代幣|Total coins|Coins|現在のコイン|獲得コイン):\s*(\d+)", string, re.I)

        if m_profit or m_fails or m_coins:
            coins = int(m_coins.group(1)) if m_coins else self.ui.current_coins
            fails = int(m_fails.group(1)) if m_fails else self.ui.current_fails
            profit = int(m_profit.group(1)) if m_profit else self.ui.current_profit

            self.ui.update_stats_display(coins, fails, profit)

        if len(self.raw_text) > 15000:
            self.raw_text = self.raw_text[-15000:]
            newline_idx = self.raw_text.find('\n')
            if newline_idx != -1:
                self.raw_text = self.raw_text[newline_idx + 1:]

        self.ui.log_lines = self.raw_text.split('\n')
        self.ui.log_view_start = max(0, len(self.ui.log_lines) - self.ui.log_max_lines)
        self.ui.update_log_view()

    def flush(self):
        pass

    def clear(self):
        self.raw_text = ""
        self.ui.log_lines = []
        self.ui.log_view_start = 0
        self.ui.update_log_view()


class HololiveBotUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.bot_thread = None
        self.is_running = False
        self.current_lang = localization.get_lang()
        self.show_bg = True

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

        self.geometry("450x800")
        self.minsize(360, 640)

        self.last_w = 0
        self.last_h = 0

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)

        self.bg_candidates = self._discover_backgrounds()
        self.bg_index = 0 if self.bg_candidates else -1
        self.original_bg = None
        self._load_current_bg()

        self.bg_id = self.canvas.create_image(0, 0, anchor="nw")

        font_title = ("Microsoft YaHei", 16, "bold")
        font_normal = ("Microsoft YaHei", 12, "bold")
        font_log = ("Microsoft YaHei", 12, "bold")

        self.title_id = self.canvas.create_text(0, 0, font=font_title, fill="#111111")

        self.lang_label_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")
        available_langs = localization.load_external_locales()
        self.lang_keys = [code for code, _ in available_langs]
        lang_values = [name for _, name in available_langs]
        self.combo_lang = ttk.Combobox(self, values=lang_values, state="readonly")
        initial_idx = self.lang_keys.index(self.current_lang) if self.current_lang in self.lang_keys else 0
        self.combo_lang.current(initial_idx)
        self.current_lang = self.lang_keys[initial_idx]
        localization.set_lang(self.current_lang)
        self.combo_lang.bind("<<ComboboxSelected>>", self.change_language)
        self.combo_window = self.canvas.create_window(0, 0, window=self.combo_lang, anchor="e")

        self.hotkey_label_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")
        self.current_hotkey = "INSERT"
        self.is_listening = False

        self.btn_hotkey = ttk.Button(self, text=self.current_hotkey, command=self.start_listen_hotkey)
        self.hotkey_window = self.canvas.create_window(0, 0, window=self.btn_hotkey, anchor="e")

        keyboard.add_hotkey(self.current_hotkey, lambda: self.after(0, self.stop_bot))

        self.status_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")

        # Row 1: Coins
        self.coins_label_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")
        self.entry_coins = ttk.Entry(self, width=8, justify="center", font=("Microsoft YaHei", 10, "bold"))
        self.entry_coins.insert(0, str(self.current_coins))
        self.entry_coins.bind("<FocusOut>", self.on_stats_manual_edit)
        self.entry_coins.bind("<Return>", self.on_stats_manual_edit)
        self.entry_coins_win = self.canvas.create_window(0, 0, window=self.entry_coins, anchor="w")
        self.coins_max_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w", text="/ 20000")

        # Row 2: Fails & Net Profit
        self.fails_label_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")
        self.entry_fails = ttk.Entry(self, width=5, justify="center", font=("Microsoft YaHei", 10, "bold"))
        self.entry_fails.insert(0, str(self.current_fails))
        self.entry_fails.bind("<FocusOut>", self.on_stats_manual_edit)
        self.entry_fails.bind("<Return>", self.on_stats_manual_edit)
        self.entry_fails_win = self.canvas.create_window(0, 0, window=self.entry_fails, anchor="w")
        self.profit_id = self.canvas.create_text(0, 0, font=font_normal, fill="#111111", anchor="w")

        self.log_text_id = self.canvas.create_text(0, 0, font=font_log, fill="#000000", anchor="nw", justify="left")
        self.log_lines = []
        # Long text wrapping takes 2 lines; adjust max lines slightly to prevent clipping
        self.log_max_lines = 13
        self.log_view_start = 0

        self.scrollbar = ttk.Scrollbar(self, orient="vertical", command=self.scroll_log)
        self.scrollbar_win = self.canvas.create_window(0, 0, window=self.scrollbar, anchor="ne")
        self.canvas.bind("<MouseWheel>", self.on_mouse_wheel)

        self.btn_start = ttk.Button(self, command=self.start_bot)
        self.btn_stop = ttk.Button(self, command=self.stop_bot, state="disabled")
        self.btn_bg = ttk.Button(self, command=self.toggle_bg)
        self.btn_exit = ttk.Button(self, command=self.destroy)

        self.btn_start_win = self.canvas.create_window(0, 0, window=self.btn_start)
        self.btn_stop_win = self.canvas.create_window(0, 0, window=self.btn_stop)
        self.btn_bg_win = self.canvas.create_window(0, 0, window=self.btn_bg)
        self.btn_exit_win = self.canvas.create_window(0, 0, window=self.btn_exit)

        self.combo_strategy = ttk.Combobox(self, state='readonly',
                                           values=STRATEGY_LABELS[self.current_lang])
        self.combo_strategy.current(0)
        self.strategy_window = self.canvas.create_window(0, 0, window=self.combo_strategy, anchor='nw')
        self.active_mode = 'legacy'

        self.sys_redirector = RedirectText(self)
        self.original_stdout = sys.stdout
        sys.stdout = self.sys_redirector

        self.canvas.bind("<Configure>", self.on_resize)
        self.resize_after_id = None

        self.refresh_texts()
        self.draw_ui(450, 800)

    def start_listen_hotkey(self):
        if self.is_listening or self.is_running:
            return

        self.is_listening = True
        self.btn_hotkey.configure(text=localization.tr("hotkey_listening", self.current_lang))
        print(localization.tr("hotkey_prompt", self.current_lang))

        threading.Thread(target=self._listen_worker, daemon=True).start()

    def _listen_worker(self):
        time.sleep(0.1)
        while True:
            event = keyboard.read_event()
            if event.event_type == keyboard.KEY_DOWN:
                key = event.name.upper()
                break

        self.after(0, self._apply_new_hotkey, key)

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

    def on_mouse_wheel(self, event):
        direction = -1 if event.delta > 0 else 1
        self.scroll_log('scroll', direction * 3)

    def scroll_log(self, *args):
        if not self.log_lines: return

        if args[0] == 'moveto':
            fraction = float(args[1])
            self.log_view_start = int(fraction * len(self.log_lines))
        elif args[0] == 'scroll':
            self.log_view_start += int(args[1])

        max_start = max(0, len(self.log_lines) - self.log_max_lines)
        self.log_view_start = max(0, min(self.log_view_start, max_start))
        self.update_log_view()

    def update_log_view(self):
        max_start = max(0, len(self.log_lines) - self.log_max_lines)
        if len(self.log_lines) == 0:
            self.scrollbar.set(0.0, 1.0)
            visible = []
        else:
            fraction = self.log_view_start / max(1, len(self.log_lines))
            fraction_end = (self.log_view_start + self.log_max_lines) / max(1, len(self.log_lines))
            self.scrollbar.set(fraction, fraction_end)
            visible = self.log_lines[self.log_view_start: self.log_view_start + self.log_max_lines]

        self.canvas.itemconfig(self.log_text_id, text='\n'.join(visible))

    def on_resize(self, event):
        if event.widget != self.canvas:
            return
        w, h = event.width, event.height
        if w <= 50 or h <= 50:
            return
        if w == self.last_w and h == self.last_h:
            return
        self.last_w, self.last_h = w, h

        if self.resize_after_id:
            self.after_cancel(self.resize_after_id)
        self.resize_after_id = self.after(10, lambda: self.draw_ui(w, h))

    def draw_ui(self, w, h):
        # 1. Background image
        if self.show_bg and self.original_bg:
            img = self.original_bg.resize((w, h), Image.Resampling.LANCZOS)
        else:
            img = Image.new('RGB', (w, h), color='#FFFFFF')

        self.bg_photo = ImageTk.PhotoImage(img)
        self.canvas.itemconfig(self.bg_id, image=self.bg_photo)

        # 2. Responsive layout dimensions
        pad_x = max(16, int(w * 0.06))
        content_w = w - 2 * pad_x

        # Title (centered at top)
        title_y = max(24, int(h * 0.04))
        self.canvas.coords(self.title_id, w / 2, title_y)

        # Row 1: Language
        row1_y = max(58, int(h * 0.09))
        combo_w = max(130, min(220, int(content_w * 0.42)))
        self.canvas.coords(self.lang_label_id, pad_x, row1_y)
        self.canvas.coords(self.combo_window, w - pad_x, row1_y)
        self.canvas.itemconfig(self.combo_window, width=combo_w)

        # Row 2: Hotkey
        row2_y = row1_y + max(34, int(h * 0.052))
        self.canvas.coords(self.hotkey_label_id, pad_x, row2_y)
        self.canvas.coords(self.hotkey_window, w - pad_x, row2_y)
        self.canvas.itemconfig(self.hotkey_window, width=combo_w)

        # Status & Coin Stats
        status_y = row2_y + max(34, int(h * 0.055))
        self.canvas.coords(self.status_id, pad_x, status_y)

        coins_y = status_y + max(26, int(h * 0.046))
        fails_y = coins_y + max(26, int(h * 0.044))
        field_h = max(22, min(28, int(h * 0.038)))

        # Position Coins Row
        self.canvas.coords(self.coins_label_id, pad_x, coins_y)
        coins_lbl_box = self.canvas.bbox(self.coins_label_id)
        coins_lbl_w = (coins_lbl_box[2] - coins_lbl_box[0]) if coins_lbl_box else 50
        entry_coins_x = pad_x + coins_lbl_w + 6
        self.canvas.coords(self.entry_coins_win, entry_coins_x, coins_y)
        self.canvas.itemconfig(self.entry_coins_win, width=76, height=field_h)
        self.canvas.coords(self.coins_max_id, entry_coins_x + 76 + 8, coins_y)

        # Position Fails & Net Profit Row
        self.canvas.coords(self.fails_label_id, pad_x, fails_y)
        fails_lbl_box = self.canvas.bbox(self.fails_label_id)
        fails_lbl_w = (fails_lbl_box[2] - fails_lbl_box[0]) if fails_lbl_box else 50
        entry_fails_x = pad_x + fails_lbl_w + 6
        self.canvas.coords(self.entry_fails_win, entry_fails_x, fails_y)
        self.canvas.itemconfig(self.entry_fails_win, width=50, height=field_h)
        self.canvas.coords(self.profit_id, entry_fails_x + 50 + 8, fails_y)

        # 2x2 Action Buttons
        btn_gap = 10
        btn_w = (content_w - btn_gap) / 2
        btn_h = max(28, min(40, int(h * 0.048)))

        btn_row1_y = fails_y + max(28, int(h * 0.052))
        btn_row2_y = btn_row1_y + btn_h + 8

        btn_left_center = pad_x + btn_w / 2
        btn_right_center = pad_x + btn_w + btn_gap + btn_w / 2

        self.canvas.coords(self.btn_start_win, btn_left_center, btn_row1_y)
        self.canvas.itemconfig(self.btn_start_win, width=btn_w, height=btn_h)

        self.canvas.coords(self.btn_stop_win, btn_right_center, btn_row1_y)
        self.canvas.itemconfig(self.btn_stop_win, width=btn_w, height=btn_h)

        self.canvas.coords(self.btn_bg_win, btn_left_center, btn_row2_y)
        self.canvas.itemconfig(self.btn_bg_win, width=btn_w, height=btn_h)

        self.canvas.coords(self.btn_exit_win, btn_right_center, btn_row2_y)
        self.canvas.itemconfig(self.btn_exit_win, width=btn_w, height=btn_h)

        # Strategy Dropdown (full width across content area)
        strategy_y = btn_row2_y + btn_h / 2 + 14
        self.canvas.coords(self.strategy_window, pad_x, strategy_y)
        self.canvas.itemconfig(self.strategy_window, width=content_w)

        # Log Text Box & Scrollbar (fills remaining vertical space)
        log_y = strategy_y + 36
        log_bottom = h - max(16, int(h * 0.025))
        log_h = max(70, log_bottom - log_y)
        scrollbar_w = 16

        self.canvas.coords(self.log_text_id, pad_x, log_y)
        self.canvas.itemconfig(self.log_text_id, width=content_w - scrollbar_w - 8)

        self.canvas.coords(self.scrollbar_win, w - pad_x, log_y)
        self.canvas.itemconfig(self.scrollbar_win, height=log_h)

        # Dynamically scale visible lines based on actual available log height
        line_height = 22
        self.log_max_lines = max(5, int(log_h / line_height))
        self.update_log_view()

    def _discover_backgrounds(self) -> list[Path]:
        valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
        found: list[Path] = []
        search_dirs = [auto_bot.APP_DIR / "backgrounds", auto_bot.RESOURCE_DIR / "backgrounds"]
        for directory in search_dirs:
            if directory.exists() and directory.is_dir():
                for p in sorted(directory.iterdir()):
                    if p.is_file() and p.suffix.lower() in valid_exts and p not in found:
                        found.append(p)
        legacy_bg = auto_bot.RESOURCE_DIR / "background.png"
        if legacy_bg.exists() and legacy_bg not in found:
            found.append(legacy_bg)
        return found

    def _load_current_bg(self):
        if 0 <= self.bg_index < len(self.bg_candidates):
            try:
                self.original_bg = Image.open(self.bg_candidates[self.bg_index])
                self.show_bg = True
                return
            except Exception as e:
                print(f"[Warning] Failed to open background image {self.bg_candidates[self.bg_index]}: {e}")
        self.original_bg = Image.new('RGB', (450, 800), color='#F0F0F0')
        self.show_bg = False

    def toggle_bg(self):
        if not self.bg_candidates:
            self.show_bg = not self.show_bg
        else:
            if not self.show_bg:
                if self.bg_index < 0:
                    self.bg_index = 0
                self._load_current_bg()
            elif len(self.bg_candidates) > 1:
                self.bg_index += 1
                if self.bg_index >= len(self.bg_candidates):
                    self.bg_index = -1
                    self.show_bg = False
                else:
                    self._load_current_bg()
            else:
                self.show_bg = not self.show_bg
        self.draw_ui(self.winfo_width(), self.winfo_height())

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
            self.current_profit = self.current_coins - (self.current_fails * 50)
            auto_bot.save_daily_data(self.current_coins, self.current_fails)
            self.update_stats_display()
        except ValueError:
            self.update_stats_display()

    def update_stats_display(self, coins=None, fails=None, profit=None):
        if coins is not None: self.current_coins = coins
        if fails is not None: self.current_fails = fails
        if profit is not None:
            self.current_profit = profit
        else:
            self.current_profit = self.current_coins - (self.current_fails * 50)

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

    def refresh_texts(self):
        selected_strategy = self.combo_strategy.current()
        self.combo_strategy.configure(values=localization.STRATEGY_LABELS[self.current_lang],
                                      state='disabled' if self.is_running else 'readonly')
        self.combo_strategy.current(max(0, selected_strategy))
        title = localization.tr("title", self.current_lang)
        self.title(title)
        self.canvas.itemconfig(self.title_id, text=title)
        self.canvas.itemconfig(self.lang_label_id, text=localization.tr("lang_label", self.current_lang))
        self.canvas.itemconfig(self.hotkey_label_id, text=localization.tr("hotkey_label", self.current_lang))
        self.canvas.itemconfig(self.coins_label_id, text=localization.tr("coins_label", self.current_lang))
        self.canvas.itemconfig(self.fails_label_id, text=localization.tr("fails_label", self.current_lang))

        self.btn_bg.configure(text=localization.tr("btn_bg", self.current_lang))
        self.btn_exit.configure(text=localization.tr("btn_exit", self.current_lang))

        self.update_stats_display()

        if not self.is_running:
            self.entry_coins.configure(state="normal")
            self.entry_fails.configure(state="normal")
            self.canvas.itemconfig(self.status_id, text=localization.tr("status_idle", self.current_lang), fill="#111111")
            self.btn_start.configure(text=localization.tr("btn_start", self.current_lang), state="normal")
            self.btn_stop.configure(text=localization.tr("btn_stop", self.current_lang), state="disabled")
            self.btn_hotkey.configure(state="normal")
        else:
            self.entry_coins.configure(state="disabled")
            self.entry_fails.configure(state="disabled")
            self.btn_start.configure(text=localization.tr("btn_running", self.current_lang), state="disabled")
            self.btn_stop.configure(text=localization.tr("btn_stop", self.current_lang), state="normal")
            self.btn_hotkey.configure(state="disabled")

    def change_language(self, event=None):
        idx = self.combo_lang.current()
        self.current_lang = self.lang_keys[idx]
        localization.set_lang(self.current_lang)
        self.refresh_texts()

    def start_bot(self):
        self.active_mode = 'phased' if self.combo_strategy.current() == 1 else 'legacy'
        self.is_running = True
        self.refresh_texts()
        self.canvas.itemconfig(self.status_id,
                               text=localization.tr("status_running", self.current_lang),
                               fill="green")

        self.sys_redirector.clear()

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
                               fill="orange")

    def run_bot(self):
        try:
            auto_bot.auto_play_loop(
                self.active_mode,
                on_stats_update=lambda c, f, p: self.after(0, self.update_stats_display, c, f, p),
                lang=self.current_lang,
            )
        except Exception as e:
            err_msg = localization.format_error(e, self.current_lang)
            print(localization.tr("system_crash", self.current_lang, error=err_msg))
            self.canvas.itemconfig(self.status_id, text=localization.tr("status_crashed", self.current_lang), fill="red")
        finally:
            self.is_running = False
            auto_bot.bot_running = False
            self.refresh_texts()
            print(localization.tr("system_stopped", self.current_lang))

    def destroy(self):
        self.is_running = False
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
