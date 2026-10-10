"""Reusable canvas-backed widgets, tooltips, and I/O redirection."""
import tkinter as tk
import time


class DummyFrame:
    """Drop-in shim for deprecated modifier subframes."""
    def pack(self, *args, **kwargs): pass
    def pack_forget(self, *args, **kwargs): pass
    def columnconfigure(self, *args, **kwargs): pass
    def grid(self, *args, **kwargs): pass
    def update_idletasks(self): pass
    def winfo_reqheight(self): return 200


class CanvasHeaderLabel:
    """Header label rendered directly on tk.Canvas for 100% alpha transparency."""
    def __init__(self, canvas, text="", font=None, cursor="hand2", fill="#334155"):
        self.canvas = canvas
        self.text = text
        self.font = font or ("Segoe UI", 8, "bold")
        self.cursor = cursor
        self.fill = fill
        self._tag = f"clbl_{id(self)}"
        self._item = None
        self._x = 0
        self._y = 0
        self._bound_handlers = {}

    def place(self, x, y):
        self._x = x
        self._y = y
        self.redraw()

    def hide(self):
        if self._item:
            self.canvas.itemconfig(self._item, state="hidden")

    def redraw(self):
        if self._item:
            self.canvas.delete(self._item)
        self._item = self.canvas.create_text(
            int(self._x), int(self._y), text=self.text, font=self.font,
            fill=self.fill, anchor="w", tags=self._tag
        )
        for seq, funcs in self._bound_handlers.items():
            for f in funcs:
                self.canvas.tag_bind(self._item, seq, f)

    def configure(self, **kwargs):
        if "text" in kwargs:
            self.text = kwargs["text"]
        if "font" in kwargs:
            self.font = kwargs["font"]
        if "fill" in kwargs:
            self.fill = kwargs["fill"]
        self.redraw()

    def set_theme(self, fill: str):
        self.fill = fill
        self.redraw()

    def config(self, **kwargs):
        self.configure(**kwargs)

    def bind(self, seq, func, add="+"):
        if seq not in self._bound_handlers or add != "+":
            self._bound_handlers[seq] = []
        self._bound_handlers[seq].append(func)
        if self._item:
            self.canvas.tag_bind(self._item, seq, func)


class CanvasCheckbutton:
    """Checkbutton rendered directly on tk.Canvas for 100% alpha transparency."""
    def __init__(self, canvas, variable, text="", command=None, font=None, style_tag=None):
        self.canvas = canvas
        self.var = variable
        self.text = text
        self.command = command
        self.font = font or ("Segoe UI", 9)
        self.state = "normal"
        self.theme_mode = "light"
        self._tag = f"cchk_{id(self)}"
        self._items = []
        self._x = 0
        self._y = 0
        self._w = 120
        self._h = 22
        self._visible = True
        self._bound_handlers = {}
        if self.var:
            self.var.trace_add("write", lambda *_: self.redraw())

    def set_theme(self, theme_name: str):
        if theme_name in ("light", "dark"):
            self.theme_mode = theme_name
            self.redraw()

    def place(self, x, y, width=120, height=22):
        self._x = x
        self._y = y
        self._w = width
        self._h = height
        self._visible = True
        self.redraw()

    def hide(self):
        self._visible = False
        for item in self._items:
            self.canvas.itemconfig(item, state="hidden")

    def redraw(self):
        for item in self._items:
            self.canvas.delete(item)
        self._items.clear()
        if not self._visible:
            return

        is_checked = bool(self.var.get()) if self.var else False
        is_disabled = (self.state == "disabled")

        box_x = int(self._x)
        box_y = int(self._y + (self._h - 14) // 2)

        if self.theme_mode == "dark":
            if is_disabled:
                box_fill = "#18181B" if is_checked else "#27272A"
                box_outline = "#3F3F46"
                text_fill = "#52525B"
                chk_color = "#52525B"
            elif is_checked:
                box_fill = "#3B82F6"
                box_outline = "#2563EB"
                text_fill = "#F1F5F9"
                chk_color = "#FFFFFF"
            else:
                box_fill = "#27272A"
                box_outline = "#71717A"
                text_fill = "#E2E8F0"
                chk_color = "#3B82F6"
        else:
            if is_disabled:
                box_fill = "#E2E8F0" if is_checked else "#F8FAFC"
                box_outline = "#CBD5E1"
                text_fill = "#94A3B8"
                chk_color = "#94A3B8"
            elif is_checked:
                box_fill = "#2563EB"
                box_outline = "#1D4ED8"
                text_fill = "#1E293B"
                chk_color = "#FFFFFF"
            else:
                box_fill = "#FFFFFF"
                box_outline = "#64748B"
                text_fill = "#1E293B"
                chk_color = "#2563EB"

        rect = self.canvas.create_rectangle(
            box_x, box_y, box_x + 14, box_y + 14,
            fill=box_fill, outline=box_outline, width=1.5, tags=self._tag
        )
        self._items.append(rect)

        if is_checked:
            f_name = self.font[0] if isinstance(self.font, (list, tuple)) else "Segoe UI"
            chk = self.canvas.create_text(
                box_x + 7, box_y + 7, text="✓", font=(f_name, 9, "bold"),
                fill=chk_color, tags=self._tag
            )
            self._items.append(chk)

        txt = self.canvas.create_text(
            box_x + 20, int(self._y + self._h // 2), text=self.text, font=self.font,
            fill=text_fill, anchor="w", tags=self._tag
        )
        self._items.append(txt)

        for item in self._items:
            self.canvas.tag_bind(item, "<Button-1>", self._on_click)
            for seq, funcs in self._bound_handlers.items():
                for f in funcs:
                    self.canvas.tag_bind(item, seq, f)

    def _on_click(self, event=None):
        if self.state == "disabled":
            return
        if self.var:
            self.var.set(not self.var.get())
        if self.command:
            self.command()

    def cget(self, key):
        if key == "state":
            return self.state
        if key == "text":
            return self.text
        return ""

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = str(kwargs["state"])
        if "text" in kwargs:
            self.text = kwargs["text"]
        if "font" in kwargs:
            self.font = kwargs["font"]
        if "command" in kwargs:
            self.command = kwargs["command"]
        self.redraw()

    def config(self, **kwargs):
        self.configure(**kwargs)

    def bind(self, seq, func, add="+"):
        if seq not in self._bound_handlers or add != "+":
            self._bound_handlers[seq] = []
        self._bound_handlers[seq].append(func)
        for item in self._items:
            self.canvas.tag_bind(item, seq, func)

    def winfo_rootx(self):
        return self.canvas.winfo_rootx() + int(self._x)

    def winfo_rooty(self):
        return self.canvas.winfo_rooty() + int(self._y)

    def winfo_height(self):
        return int(self._h) or 22

    def winfo_width(self):
        return int(self._w) or 100

    def after(self, ms, func):
        return self.canvas.after(ms, func)

    def after_cancel(self, aid):
        return self.canvas.after_cancel(aid)


class ToolTip:
    """Lightweight hover tooltip for Tkinter widgets."""

    def __init__(self, widget, text: str = "", delay_ms: int = 400):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._tip_window = None
        self._after_id = None

        if self.widget:
            self.widget.bind("<Enter>", self._on_enter, add="+")
            self.widget.bind("<Leave>", self._on_leave, add="+")
            self.widget.bind("<ButtonPress>", self._on_leave, add="+")

    def _on_enter(self, event=None):
        self._cancel()
        if self.text and self.widget:
            self._after_id = self.widget.after(self.delay_ms, self._show)

    def _on_leave(self, event=None):
        self._cancel()
        self._hide()

    def _cancel(self):
        if self._after_id and self.widget:
            try:
                self.widget.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None

    def _show(self):
        if self._tip_window or not self.text or not self.widget:
            return
        try:
            x = self.widget.winfo_rootx() + 15
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
            master = getattr(self.widget, "canvas", self.widget)
            self._tip_window = tw = tk.Toplevel(master)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            try:
                tw.wm_attributes("-topmost", True)
            except Exception:
                pass
            frame = tk.Frame(tw, background="#334155", borderwidth=1, relief="solid")
            frame.pack()
            lbl = tk.Label(
                frame,
                text=self.text,
                justify="left",
                background="#1E293B",
                foreground="#F8FAFC",
                font=("Segoe UI", 8),
                padx=6,
                pady=4,
                wraplength=320,
            )
            lbl.pack()
        except Exception:
            self._hide()

    def _hide(self):
        if self._tip_window:
            try:
                self._tip_window.destroy()
            except Exception:
                pass
            self._tip_window = None

    def update_text(self, text: str):
        self.text = text
        if self._tip_window:
            self._hide()


class RedirectText:
    """Output interceptor and virtual log buffer."""
    def __init__(self, ui):
        self.ui = ui
        self.raw_text = ""

    def write(self, string):
        if not string:
            return
        if hasattr(self.ui, "ui_queue"):
            self.ui.ui_queue.put(("log", string))
        else:
            self._write(string)

    def _write(self, string):
        if not string:
            return
        self.raw_text += string
        if len(self.raw_text) > 20000:
            self.raw_text = self.raw_text[-15000:]
        self.ui.append_log_text(string)

    def flush(self):
        pass

    def clear(self):
        self.raw_text = ""
        if hasattr(self.ui, "ui_queue"):
            self.ui.ui_queue.put(("clear_log", None))
        else:
            self.ui.clear_log_text()


class ModernMenu(tk.Menu):
    """Modern theme-aware popup menu with custom borders and hover states."""
    _active_popups: list[tk.Toplevel] = []
    _is_bound: bool = False
    _open_time: float = 0.0

    def __init__(self, master=None, **kwargs):
        super().__init__(master, **kwargs)
        self._popup_window: tk.Toplevel | None = None
        self._child_popup: "ModernMenu | None" = None
        self._parent_menu: "ModernMenu | None" = None

    @classmethod
    def close_all(cls):
        while cls._active_popups:
            popup = cls._active_popups.pop()
            try:
                popup.destroy()
            except Exception:
                pass
        try:
            import tkinter as _tk
            if hasattr(_tk, "_default_root") and _tk._default_root:
                if hasattr(_tk._default_root, "_active_menu_key"):
                    _tk._default_root._active_menu_key = None
        except Exception:
            pass

    def unpost(self):
        if self._child_popup:
            try:
                self._child_popup.unpost()
            except Exception:
                pass
            self._child_popup = None
        if self._popup_window:
            try:
                if self._popup_window in ModernMenu._active_popups:
                    ModernMenu._active_popups.remove(self._popup_window)
                self._popup_window.destroy()
            except Exception:
                pass
            self._popup_window = None

    def tk_popup(self, x, y, entry=""):
        self.post(x, y)

    def post(self, x, y):
        if not self._parent_menu:
            ModernMenu.close_all()

        ModernMenu._open_time = time.time()
        try:
            root = self.nametowidget(".")
        except Exception:
            root = self.winfo_toplevel()

        is_dark = True
        if hasattr(root, "get_active_theme"):
            is_dark = (root.get_active_theme() == "dark")
        elif hasattr(root, "theme_palette") and root.theme_palette:
            is_dark = root.theme_palette.get("is_dark", True)
        elif hasattr(root, "theme_mode"):
            if root.theme_mode == "system":
                from src.ui.platform import is_windows_dark_mode
                is_dark = is_windows_dark_mode()
            else:
                is_dark = (root.theme_mode == "dark")

        menu_bg = "#18181B" if is_dark else "#FFFFFF"
        menu_fg = "#F8FAFC" if is_dark else "#0F172A"
        active_bg = "#27272A" if is_dark else "#F1F5F9"
        border_col = "#3F3F46" if is_dark else "#CBD5E1"
        sep_col = "#27272A" if is_dark else "#E2E8F0"
        dim_fg = "#A1A1AA" if is_dark else "#64748B"
        accent_col = "#3B82F6" if is_dark else "#2563EB"
        font_family = getattr(root, "font_family", "Segoe UI")

        popup = tk.Toplevel(root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg=border_col)
        self._popup_window = popup
        ModernMenu._active_popups.append(popup)

        inner = tk.Frame(popup, bg=menu_bg, padx=3, pady=3)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        total_items = self.index("end")
        if total_items is None:
            return

        def handle_outside_click(event):
            # Guard against the opening click event bubbling to bind_all in the same click cycle
            if time.time() - ModernMenu._open_time < 0.15:
                return
            # If click was inside the top menubar or any of its buttons, let the button handler manage it
            try:
                if event.widget and hasattr(root, "menubar_frame"):
                    w = event.widget
                    while w:
                        if w == root.menubar_frame:
                            return
                        w = getattr(w, "master", None)
            except Exception:
                pass
            for p in list(ModernMenu._active_popups):
                try:
                    if not p.winfo_exists():
                        continue
                    px = p.winfo_rootx()
                    py = p.winfo_rooty()
                    pw = p.winfo_width()
                    ph = p.winfo_height()
                    if px <= event.x_root <= px + pw and py <= event.y_root <= py + ph:
                        return
                except Exception:
                    pass
            ModernMenu.close_all()

        if not ModernMenu._is_bound:
            root.bind_all("<Button-1>", handle_outside_click, add="+")
            root.bind_all("<Escape>", lambda e: ModernMenu.close_all(), add="+")
            ModernMenu._is_bound = True

        for i in range(total_items + 1):
            item_type = self.type(i)
            if item_type == "separator":
                sep = tk.Frame(inner, bg=sep_col, height=1)
                sep.pack(fill="x", padx=6, pady=4)
                continue

            raw_label = self.entrycget(i, "label") or ""
            lbl_text = raw_label.strip()

            indicator = ""
            if item_type == "radiobutton":
                try:
                    var_name = self.entrycget(i, "variable")
                    val = self.entrycget(i, "value")
                    curr = root.getvar(var_name) if var_name else None
                    if str(curr) == str(val):
                        indicator = "●"
                except Exception:
                    pass
            elif item_type == "checkbutton":
                try:
                    var_name = self.entrycget(i, "variable")
                    curr = root.getvar(var_name) if var_name else None
                    if curr in (1, "1", True, "true"):
                        indicator = "✓"
                except Exception:
                    pass

            accel = ""
            try:
                if "accelerator" in self.entryconfig(i):
                    accel = self.entrycget(i, "accelerator") or ""
            except Exception:
                pass
            if not accel and "(" in lbl_text and lbl_text.endswith(")"):
                parts = lbl_text.rsplit("(", 1)
                lbl_text = parts[0].strip()
                accel = "(" + parts[1]

            item_frame = tk.Frame(inner, bg=menu_bg, cursor="hand2")
            item_frame.pack(fill="x", pady=1)

            ind_lbl = tk.Label(
                item_frame,
                text=indicator,
                font=(font_family, 8),
                bg=menu_bg,
                fg=accent_col,
                width=2,
                anchor="center",
            )
            ind_lbl.pack(side="left", padx=(2, 4))

            text_lbl = tk.Label(
                item_frame,
                text=lbl_text,
                font=(font_family, 9),
                bg=menu_bg,
                fg=menu_fg,
                anchor="w",
            )
            text_lbl.pack(side="left", fill="x", expand=True, padx=(0, 16))

            right_text = "›" if item_type == "cascade" else accel
            right_lbl = tk.Label(
                item_frame,
                text=right_text,
                font=(font_family, 8),
                bg=menu_bg,
                fg=dim_fg,
                anchor="e",
            )
            right_lbl.pack(side="right", padx=(0, 6))

            all_widgets = [item_frame, ind_lbl, text_lbl, right_lbl]

            def on_enter(e, f=item_frame, widgets=all_widgets, idx=i, itype=item_type):
                for w in widgets:
                    w.configure(bg=active_bg)
                if itype == "cascade":
                    try:
                        submenu_name = self.entrycget(idx, "menu")
                        if submenu_name:
                            submenu = self.nametowidget(submenu_name)
                            if isinstance(submenu, ModernMenu):
                                if self._child_popup and self._child_popup != submenu:
                                    self._child_popup.unpost()
                                submenu._parent_menu = self
                                self._child_popup = submenu
                                popup.update_idletasks()
                                sub_x = popup.winfo_rootx() + popup.winfo_width() - 2
                                sub_y = f.winfo_rooty() - 3
                                submenu.post(sub_x, sub_y)
                    except Exception:
                        pass
                else:
                    if self._child_popup:
                        self._child_popup.unpost()
                        self._child_popup = None

            def on_leave(e, widgets=all_widgets):
                for w in widgets:
                    w.configure(bg=menu_bg)

            def on_click(e, idx=i, itype=item_type):
                if itype == "cascade":
                    return
                try:
                    if itype == "radiobutton":
                        var_name = self.entrycget(idx, "variable")
                        val = self.entrycget(idx, "value")
                        if var_name:
                            root.setvar(var_name, val)
                    elif itype == "checkbutton":
                        var_name = self.entrycget(idx, "variable")
                        if var_name:
                            curr = root.getvar(var_name)
                            new_val = 0 if curr in (1, "1", True) else 1
                            root.setvar(var_name, new_val)
                except Exception:
                    pass

                ModernMenu.close_all()
                try:
                    self.invoke(idx)
                except Exception:
                    pass

            for w in all_widgets:
                w.bind("<Enter>", on_enter)
                w.bind("<Leave>", on_leave)
                w.bind("<Button-1>", on_click)

        popup.update_idletasks()
        sw = popup.winfo_screenwidth()
        sh = popup.winfo_screenheight()
        pw = popup.winfo_reqwidth()
        ph = popup.winfo_reqheight()
        if x + pw > sw:
            x = sw - pw - 8
        if y + ph > sh:
            y = sh - ph - 8
        popup.geometry(f"+{max(0, x)}+{max(0, y)}")

