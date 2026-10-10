"""Dialog and modal window implementations for Hololive Dreams UI.

Contains Settings dialog, Custom Parametric configuration dialog,
Simulation benchmark viewer and export, Settlement recovery prompt,
and Help/About modals.
"""

from __future__ import annotations

import csv
import json
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import TYPE_CHECKING, Any, Optional
import webbrowser

import localization
import auto_bot
from src.ui.platform import set_window_dark_titlebar
from src.ui.log_manager import clean_old_logs

if TYPE_CHECKING:
    import queue


def show_help_rules(app: Any):
    """Open online game rules and mechanics guide on GitHub in the default browser."""
    webbrowser.open("https://github.com/xAkai97/Hololive-Dreams-Auto-High-Low/blob/main/docs/strategies.md#game-rules")


def show_help_strategies(app: Any, num_strategies: int = 7):
    """Open online strategy catalog and modifier system guide on GitHub in the default browser."""
    webbrowser.open("https://github.com/xAkai97/Hololive-Dreams-Auto-High-Low/blob/main/docs/strategies.md#available-strategies")


def show_help_about(app: Any, num_strategies: int = 0):
    """Display application metadata, author acknowledgments, and repository link."""
    dialog = tk.Toplevel(app)
    dialog.title(localization.tr("menu_about", app.current_lang))
    dialog.resizable(False, False)
    dialog.transient(app)
    dialog.grab_set()

    is_dark = app.theme_palette.get("is_dark", True) if hasattr(app, "theme_palette") else True
    set_window_dark_titlebar(dialog, is_dark)
    bg_hex = app.theme_palette.get("bg_plain_hex", "#18181B") if hasattr(app, "theme_palette") else "#18181B"
    fg_hex = app.theme_palette.get("text_primary", "#F8FAFC") if hasattr(app, "theme_palette") else "#F8FAFC"
    sec_fg = app.theme_palette.get("text_secondary", "#E2E8F0") if hasattr(app, "theme_palette") else "#E2E8F0"
    dialog.configure(bg=bg_hex)

    frame = tk.Frame(dialog, bg=bg_hex, padx=24, pady=20)
    frame.pack(fill="both", expand=True)

    font_title = (app.font_family, 11, "bold")
    font_bold = (app.font_family, 9, "bold")
    font_text = (app.font_family, 9)

    # Title
    lbl_title = tk.Label(
        frame,
        text="Hololive Dreams Auto High-Low Bot",
        font=font_title,
        bg=bg_hex,
        fg=fg_hex,
    )
    lbl_title.pack(anchor="w", pady=(0, 14))

    # Credits Section Header
    lbl_credits_header = tk.Label(
        frame,
        text="Credits & Acknowledgments:",
        font=font_bold,
        bg=bg_hex,
        fg=fg_hex,
    )
    lbl_credits_header.pack(anchor="w", pady=(0, 6))

    credits_text = (
        "• Original Author: mwty-0415\n"
        "• Computer Vision Insights: harrykuang-dev\n"
        "• Poker Hand Solver: Oreki0504"
    )
    lbl_credits = tk.Label(
        frame,
        text=credits_text,
        font=font_text,
        bg=bg_hex,
        fg=sec_fg,
        justify="left",
    )
    lbl_credits.pack(anchor="w", pady=(0, 18))

    # Action buttons row: GitHub Link + OK button
    btn_frame = tk.Frame(frame, bg=bg_hex)
    btn_frame.pack(fill="x", pady=(4, 0))

    github_url = "https://github.com/xAkai97/Hololive-Dreams-Auto-High-Low"
    btn_github = ttk.Button(
        btn_frame,
        text="GitHub Repository",
        command=lambda: webbrowser.open(github_url),
        cursor="hand2",
    )
    btn_github.pack(side="left")

    btn_ok = ttk.Button(
        btn_frame,
        text="OK",
        command=dialog.destroy,
        width=8,
    )
    btn_ok.pack(side="right")

    dialog.update_idletasks()
    dw = dialog.winfo_reqwidth()
    dh = dialog.winfo_reqheight()
    px = app.winfo_rootx() + (app.winfo_width() - dw) // 2
    py = app.winfo_rooty() + (app.winfo_height() - dh) // 2
    dialog.geometry(f"+{max(0, px)}+{max(0, py)}")


def open_settings_dialog(app: Any):
    """Open an interactive popup dialog for configuring global settings."""
    dialog = tk.Toplevel(app)
    dialog.title(localization.tr("settings_title", app.current_lang))
    dialog.resizable(False, False)
    dialog.transient(app)
    dialog.grab_set()
    is_dark = app.theme_palette["is_dark"]
    set_window_dark_titlebar(dialog, is_dark)
    dialog.configure(bg=app.theme_palette["bg_plain_hex"])

    frame = ttk.Frame(dialog, padding=(20, 16))
    frame.pack(fill="both", expand=True)

    font_label = (app.font_family, 9, "bold")

    # --- Section 1: Game & Doubling Rules ---
    lf_game = ttk.LabelFrame(frame, text=f" {localization.tr('section_game_rules', app.current_lang)} ", padding=(14, 10))
    lf_game.pack(fill="x", expand=True, pady=(0, 10))
    lf_game.columnconfigure(0, weight=1)
    lf_game.columnconfigure(1, weight=0)

    ttk.Label(lf_game, text=localization.tr("target_limit_label", app.current_lang), font=font_label).grid(row=0, column=0, sticky="w", pady=6)
    ent_target = ttk.Entry(lf_game, width=14, justify="center")
    ent_target.insert(0, str(app.target_limit))
    ent_target.grid(row=0, column=1, sticky="e", pady=6)

    ttk.Label(lf_game, text=localization.tr("ticket_cost_label", app.current_lang), font=font_label).grid(row=1, column=0, sticky="w", pady=6)
    ent_ticket = ttk.Entry(lf_game, width=14, justify="center")
    ent_ticket.insert(0, str(app.ticket_cost))
    ent_ticket.grid(row=1, column=1, sticky="e", pady=6)

    # --- Section 2: Log Maintenance & Archival ---
    lf_logs = ttk.LabelFrame(frame, text=f" {localization.tr('section_log_maintenance', app.current_lang)} ", padding=(14, 10))
    lf_logs.pack(fill="x", expand=True, pady=(0, 10))
    lf_logs.columnconfigure(0, weight=1)
    lf_logs.columnconfigure(1, weight=0)

    ttk.Label(lf_logs, text=localization.tr("log_retention_days_label", app.current_lang), font=font_label).grid(row=0, column=0, sticky="w", pady=6)
    ent_retention = ttk.Entry(lf_logs, width=14, justify="center")
    ent_retention.insert(0, str(app.log_retention_days))
    ent_retention.grid(row=0, column=1, sticky="e", pady=6)

    ttk.Label(lf_logs, text=localization.tr("log_max_size_mb_label", app.current_lang), font=font_label).grid(row=1, column=0, sticky="w", pady=6)
    ent_size = ttk.Entry(lf_logs, width=14, justify="center")
    ent_size.insert(0, str(app.log_max_size_mb))
    ent_size.grid(row=1, column=1, sticky="e", pady=6)

    chk_dlg_show_log = ttk.Checkbutton(
        lf_logs,
        text=f"{localization.tr('menu_toggle_log', app.current_lang)} (Ctrl+L)",
        variable=app.var_show_log,
        command=app.toggle_log_console,
    )
    chk_dlg_show_log.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 2))

    # --- Section 3: Settlement Verification & OCR Recovery ---
    lf_settle = ttk.LabelFrame(frame, text=f" {localization.tr('section_settlement_recovery', app.current_lang)} ", padding=(14, 10))
    lf_settle.pack(fill="x", expand=True, pady=(0, 10))
    lf_settle.columnconfigure(0, weight=1)
    lf_settle.columnconfigure(1, weight=0)

    ttk.Label(lf_settle, text=localization.tr("settlement_recovery_label", app.current_lang), font=font_label).grid(row=0, column=0, sticky="w", pady=6)
    recovery_options = [
        ("auto", localization.tr("recovery_mode_auto", app.current_lang)),
        ("manual", localization.tr("recovery_mode_manual", app.current_lang)),
        ("strict", localization.tr("recovery_mode_strict", app.current_lang)),
    ]
    rec_keys = [k for k, _ in recovery_options]
    rec_labels = [lbl for _, lbl in recovery_options]
    combo_recovery = ttk.Combobox(lf_settle, values=rec_labels, state="readonly", width=34)
    rec_idx = rec_keys.index(app.settlement_recovery_mode) if app.settlement_recovery_mode in rec_keys else 0
    combo_recovery.current(rec_idx)
    combo_recovery.grid(row=0, column=1, sticky="e", pady=6)

    ttk.Label(lf_settle, text=localization.tr("settlement_timeout_label", app.current_lang), font=font_label).grid(row=1, column=0, sticky="w", pady=6)
    ent_settle_timeout = ttk.Entry(lf_settle, width=14, justify="center")
    ent_settle_timeout.insert(0, str(int(app.settlement_ocr_timeout)))
    ent_settle_timeout.grid(row=1, column=1, sticky="e", pady=6)

    lbl_status = ttk.Label(frame, text="", font=(app.font_family, 9), foreground="#007700")
    lbl_status.pack(pady=(0, 6))

    btn_box = ttk.Frame(frame)
    btn_box.pack(pady=(0, 4))

    def on_save():
        try:
            target = int(ent_target.get().strip())
            ticket = int(ent_ticket.get().strip())
            retention = int(ent_retention.get().strip())
            size_mb = int(ent_size.get().strip())
            app.target_limit = max(1000, target)
            app.ticket_cost = max(0, ticket)
            app.log_retention_days = max(0, retention)
            app.log_max_size_mb = max(0, size_mb)
            selected_rec_idx = combo_recovery.current()
            if 0 <= selected_rec_idx < len(rec_keys):
                app.settlement_recovery_mode = rec_keys[selected_rec_idx]
            try:
                to_val = float(ent_settle_timeout.get().strip())
                app.settlement_ocr_timeout = max(3.0, min(60.0, to_val))
            except (ValueError, TypeError):
                app.settlement_ocr_timeout = 8.0
            app.entry_setting_target.delete(0, "end")
            app.entry_setting_target.insert(0, str(app.target_limit))
            app.entry_setting_ticket.delete(0, "end")
            app.entry_setting_ticket.insert(0, str(app.ticket_cost))
            app.save_user_settings()
            clean_old_logs(max_days=app.log_retention_days, max_size_mb=app.log_max_size_mb, lang=app.current_lang)
            lbl_status.configure(text=localization.tr("settings_saved_msg", app.current_lang))
            dialog.after(600, dialog.destroy)
        except ValueError:
            lbl_status.configure(text="Invalid numbers", foreground="red")

    def on_restore():
        app.restore_default_settings()
        ent_target.delete(0, "end")
        ent_target.insert(0, str(app.target_limit))
        ent_ticket.delete(0, "end")
        ent_ticket.insert(0, str(app.ticket_cost))
        ent_retention.delete(0, "end")
        ent_retention.insert(0, str(app.log_retention_days))
        ent_size.delete(0, "end")
        ent_size.insert(0, str(app.log_max_size_mb))
        combo_recovery.current(0)
        ent_settle_timeout.delete(0, "end")
        ent_settle_timeout.insert(0, "8")
        app.set_field_box_opacity(30, save=True)
        lbl_status.configure(text=localization.tr("settings_saved_msg", app.current_lang))

    ttk.Button(btn_box, text=localization.tr("btn_save_settings", app.current_lang), command=on_save).pack(side="left", padx=5)
    ttk.Button(btn_box, text=localization.tr("btn_restore_defaults", app.current_lang), command=on_restore).pack(side="left", padx=5)
    ttk.Button(btn_box, text=localization.tr("btn_cancel", app.current_lang, default="Cancel"), command=dialog.destroy).pack(side="left", padx=5)

    dialog.update_idletasks()
    req_w = max(560, dialog.winfo_reqwidth() + 30)
    req_h = max(420, dialog.winfo_reqheight() + 15)
    x = app.winfo_x() + max(0, (app.winfo_width() - req_w) // 2)
    y = app.winfo_y() + max(0, (app.winfo_height() - req_h) // 2)
    dialog.geometry(f"{req_w}x{req_h}+{x}+{y}")


def open_custom_parametric_dialog(app: Any):
    """Open an interactive popup dialog for fine-tuning custom strategy parameters."""
    dialog = tk.Toplevel(app)
    dialog.title(localization.tr("custom_param_dialog_title", app.current_lang))
    dialog.geometry("380x360")
    dialog.resizable(False, False)
    dialog.transient(app)
    dialog.grab_set()
    is_dark = app.theme_palette["is_dark"]
    set_window_dark_titlebar(dialog, is_dark)
    dialog.configure(bg=app.theme_palette["bg_plain_hex"])

    x = app.winfo_x() + max(0, (app.winfo_width() - 380) // 2)
    y = app.winfo_y() + max(0, (app.winfo_height() - 360) // 2)
    dialog.geometry(f"+{x}+{y}")

    frame = ttk.Frame(dialog, padding=16)
    frame.pack(fill="both", expand=True)

    font_label = (app.font_family, 9, "bold")

    ttk.Label(frame, text=localization.tr("min_win_rate_label", app.current_lang), font=font_label).grid(row=0, column=0, sticky="w", pady=6)
    ent_winrate = ttk.Entry(frame, width=10, justify="center")
    ent_winrate.insert(0, str(app.param_min_win_rate))
    ent_winrate.grid(row=0, column=1, sticky="e", pady=6)

    ttk.Label(frame, text=localization.tr("cushion_target_label", app.current_lang), font=font_label).grid(row=1, column=0, sticky="w", pady=6)
    ent_cushion = ttk.Entry(frame, width=10, justify="center")
    ent_cushion.insert(0, str(app.param_cushion_target))
    ent_cushion.grid(row=1, column=1, sticky="e", pady=6)

    ttk.Label(frame, text=localization.tr("sprint_target_label", app.current_lang), font=font_label).grid(row=2, column=0, sticky="w", pady=6)
    ent_sprint = ttk.Entry(frame, width=10, justify="center")
    ent_sprint.insert(0, str(app.param_sprint_target))
    ent_sprint.grid(row=2, column=1, sticky="e", pady=6)

    ttk.Label(frame, text=localization.tr("max_doubles_label", app.current_lang), font=font_label).grid(row=3, column=0, sticky="w", pady=6)
    ent_doubles = ttk.Entry(frame, width=10, justify="center")
    ent_doubles.insert(0, str(app.param_max_doubles))
    ent_doubles.grid(row=3, column=1, sticky="e", pady=6)

    ttk.Label(frame, text=localization.tr("drop_seven_eight_label", app.current_lang), font=font_label).grid(row=4, column=0, sticky="w", pady=6)
    var_drop = tk.BooleanVar(value=bool(app.param_drop_seven_eight))
    chk_drop = ttk.Checkbutton(frame, variable=var_drop)
    chk_drop.grid(row=4, column=1, sticky="e", pady=6)

    lbl_status = ttk.Label(frame, text="", font=(app.font_family, 9), foreground="#007700")
    lbl_status.grid(row=5, column=0, columnspan=2, pady=6)

    btn_box = ttk.Frame(frame)
    btn_box.grid(row=6, column=0, columnspan=2, pady=10)

    def on_save():
        try:
            wr = max(10, min(95, int(ent_winrate.get().strip())))
            cush = max(1000, min(50000, int(ent_cushion.get().strip())))
            sp = max(1000, min(100000, int(ent_sprint.get().strip())))
            md = max(1, min(20, int(ent_doubles.get().strip())))
            dp = bool(var_drop.get())

            app.param_min_win_rate = wr
            app.param_cushion_target = cush
            app.param_sprint_target = sp
            app.param_max_doubles = md
            app.param_drop_seven_eight = dp

            app.save_settings()
            print(f"[Settings] Custom parametric parameters updated: WinRate={wr}%, Cushion={cush}, Sprint={sp}, MaxDoubles={md}, Drop78={dp}")
            dialog.destroy()
        except Exception as e:
            lbl_status.configure(text=f"Error: {e}", foreground="#cc0000")

    btn_save = ttk.Button(btn_box, text=localization.tr("btn_save_settings", app.current_lang), command=on_save)
    btn_save.pack(side="left", padx=6)
    btn_cancel = ttk.Button(btn_box, text=localization.tr("btn_cancel", app.current_lang), command=dialog.destroy)
    btn_cancel.pack(side="left", padx=6)


def show_benchmark_results_dialog(app: Any, results: list[dict]):
    """Display comparative benchmark results in a clean, human-friendly GUI table window."""
    if not results:
        return
    dialog = tk.Toplevel(app)
    dialog.title(localization.tr("menu_compare_all", app.current_lang))
    dialog.transient(app)
    dialog.resizable(True, True)
    is_dark = app.theme_palette["is_dark"]
    set_window_dark_titlebar(dialog, is_dark)
    dialog.configure(bg=app.theme_palette["bg_plain_hex"])

    frame = ttk.Frame(dialog, padding=(16, 14))
    frame.pack(fill="both", expand=True)

    days_val = results[0].get("Days", 100)
    header_lbl = ttk.Label(
        frame,
        text=f"📊 Strategy Comparison Benchmark ({days_val} Days Simulated Each)",
        font=(app.font_family, 10, "bold"),
    )
    header_lbl.pack(anchor="w", pady=(0, 10))

    cols = ("Rank", "Strategy", "AvgCoins", "Fails", "HitCap", "MaxCoins")
    tree = ttk.Treeview(frame, columns=cols, show="headings", height=min(12, len(results)))
    tree.heading("Rank", text="Rank")
    tree.heading("Strategy", text="Strategy")
    tree.heading("AvgCoins", text="Avg Coins / Day")
    tree.heading("Fails", text="Avg Fails")
    tree.heading("HitCap", text="Hit Cap (20k)")
    tree.heading("MaxCoins", text="Max Recorded")

    tree.column("Rank", width=50, anchor="center")
    tree.column("Strategy", width=260, anchor="w")
    tree.column("AvgCoins", width=120, anchor="e")
    tree.column("Fails", width=75, anchor="center")
    tree.column("HitCap", width=95, anchor="center")
    tree.column("MaxCoins", width=105, anchor="e")

    scrollbar = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)

    tree.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    sorted_results = sorted(results, key=lambda r: r.get("MeanCoins", 0), reverse=True)
    for rank, r in enumerate(sorted_results, 1):
        tree.insert(
            "",
            "end",
            values=(
                f"#{rank}",
                r.get("Strategy", ""),
                f"{r.get('MeanCoins', 0):,.0f}",
                f"{r.get('MeanFails', 0):.1f}",
                f"{r.get('HitCapPct', 0):.1f}%",
                f"{r.get('MaxCoins', 0):,.0f}",
            ),
        )

    btn_bar = ttk.Frame(dialog, padding=(16, 10))
    btn_bar.pack(fill="x", side="bottom")

    ttk.Button(btn_bar, text="Close", command=dialog.destroy).pack(side="right", padx=4)
    ttk.Button(btn_bar, text="💾 Export CSV", command=lambda: export_benchmark_csv(app, results)).pack(side="right", padx=4)

    dialog.update_idletasks()
    req_w = max(730, dialog.winfo_reqwidth() + 30)
    req_h = max(390, dialog.winfo_reqheight() + 20)
    x = app.winfo_x() + max(0, (app.winfo_width() - req_w) // 2)
    y = app.winfo_y() + max(0, (app.winfo_height() - req_h) // 2)
    dialog.geometry(f"{req_w}x{req_h}+{x}+{y}")


def export_benchmark_csv(app: Any, results: list[dict]):
    """Export benchmark results to a user-specified CSV file."""
    if not results:
        messagebox.showinfo("Export CSV", "No simulation benchmark data available yet. Please run a simulation first!")
        return
    path = filedialog.asksaveasfilename(
        parent=app,
        defaultextension=".csv",
        filetypes=[("CSV Files", "*.csv"), ("All Files", "*.*")],
        initialfile="simulation_benchmark.csv",
    )
    if not path:
        return
    try:
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(results[0].keys()))
            writer.writeheader()
            writer.writerows(results)
        print(f"[Export] Benchmark exported to CSV: {path}")
        messagebox.showinfo("Export CSV", f"Successfully exported benchmark results to:\n{path}")
    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export CSV: {e}")


def export_benchmark_json(app: Any, results: list[dict]):
    """Export benchmark results to a user-specified JSON file."""
    if not results:
        messagebox.showinfo("Export JSON", "No simulation benchmark data available yet. Please run a simulation first!")
        return
    path = filedialog.asksaveasfilename(
        parent=app,
        defaultextension=".json",
        filetypes=[("JSON Files", "*.json"), ("All Files", "*.*")],
        initialfile="simulation_benchmark.json",
    )
    if not path:
        return
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"[Export] Benchmark exported to JSON: {path}")
        messagebox.showinfo("Export JSON", f"Successfully exported benchmark results to:\n{path}")
    except Exception as e:
        messagebox.showerror("Export Error", f"Failed to export JSON: {e}")


def show_settlement_modal(app: Any, expected: Optional[int], observed: Optional[str], res_queue: queue.Queue):
    """Display interactive settlement payout verification modal."""
    dialog = tk.Toplevel(app)
    dialog.title(localization.tr("settlement_prompt_title", app.current_lang))
    dialog.resizable(False, False)
    dialog.transient(app)
    dialog.grab_set()
    is_dark = app.theme_palette["is_dark"]
    set_window_dark_titlebar(dialog, is_dark)
    dialog.configure(bg=app.theme_palette["bg_plain_hex"])

    frame = ttk.Frame(dialog, padding=(20, 16))
    frame.pack(fill="both", expand=True)

    font_label = (app.font_family, 9, "bold")
    msg = localization.tr(
        "settlement_prompt_msg",
        app.current_lang,
        observed=observed if observed else "None",
        expected=expected if expected else "Unknown",
    )
    ttk.Label(frame, text=msg, font=(app.font_family, 9), justify="left").pack(anchor="w", pady=(0, 12))

    entry_frame = ttk.Frame(frame)
    entry_frame.pack(fill="x", pady=(0, 14))
    ttk.Label(entry_frame, text=localization.tr("custom_amount_label", app.current_lang), font=font_label).pack(side="left")
    custom_ent = ttk.Entry(entry_frame, width=12, justify="center")
    custom_ent.insert(0, str(expected if expected else ""))
    custom_ent.pack(side="right")

    btn_box = ttk.Frame(frame)
    btn_box.pack(fill="x")

    def choose(val):
        try:
            dialog.destroy()
        except Exception:
            pass
        res_queue.put(val)

    def on_custom():
        try:
            v = int(custom_ent.get().strip())
            if auto_bot.is_valid_settlement_amount(v):
                choose(v)
            else:
                messagebox.showerror(
                    localization.tr("settlement_prompt_title", app.current_lang),
                    localization.tr("settlement_invalid_rejected", app.current_lang, amount=v),
                    parent=dialog,
                )
        except ValueError:
            pass

    if expected and expected > 0:
        btn_exp = ttk.Button(
            btn_box,
            text=localization.tr("btn_use_expected", app.current_lang, expected=expected),
            command=lambda: choose(expected),
        )
        btn_exp.pack(fill="x", pady=2)

    btn_custom = ttk.Button(
        btn_box,
        text=localization.tr("btn_confirm_custom", app.current_lang),
        command=on_custom,
    )
    btn_custom.pack(fill="x", pady=2)

    btn_skip = ttk.Button(
        btn_box,
        text=localization.tr("btn_skip_zero", app.current_lang),
        command=lambda: choose(0),
    )
    btn_skip.pack(fill="x", pady=2)

    btn_stop = ttk.Button(
        btn_box,
        text=localization.tr("btn_stop_bot", app.current_lang),
        command=lambda: choose(None),
    )
    btn_stop.pack(fill="x", pady=2)

    dialog.protocol("WM_DELETE_WINDOW", lambda: choose(None))
