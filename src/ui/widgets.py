"""Reusable canvas-backed widgets, tooltips, and I/O redirection."""
import tkinter as tk
import time
from typing import Callable

try:
    from PIL import Image, ImageDraw, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


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
        self._visible = False
        self._bound_handlers = {}

    def place(self, x, y):
        self._x = x
        self._y = y
        self._visible = True
        self.redraw()

    def hide(self):
        self._visible = False
        if self._item:
            self.canvas.itemconfig(self._item, state="hidden")

    def redraw(self):
        if self._item:
            self.canvas.delete(self._item)
            self._item = None
        if not self._visible:
            return
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


_TOGGLE_IMAGE_CACHE: dict[tuple[str, bool, bool], "ImageTk.PhotoImage"] = {}


def _get_toggle_image(theme_mode: str, is_checked: bool, is_disabled: bool):
    """Generate and cache smooth 4x supersampled anti-aliased toggle switch images."""
    if not HAS_PIL:
        return None
    cache_key = (theme_mode, is_checked, is_disabled)
    if cache_key in _TOGGLE_IMAGE_CACHE:
        return _TOGGLE_IMAGE_CACHE[cache_key]

    if theme_mode == "dark":
        if is_disabled:
            track_border = "#1E3A2F" if is_checked else "#27272A"
            track_fill = "#164E2E" if is_checked else "#18181B"
            knob_fill = "#6B7280" if is_checked else "#3F3F46"
            knob_border = "#374151" if is_checked else "#27272A"
        elif is_checked:
            track_border = "#16A34A"
            track_fill = "#22C55E"
            knob_fill = "#FFFFFF"
            knob_border = "#DCFCE7"
        else:
            track_border = "#52525B"
            track_fill = "#3F3F46"
            knob_fill = "#E4E4E7"
            knob_border = "#A1A1AA"
    else:
        if is_disabled:
            track_border = "#86EFAC" if is_checked else "#E2E8F0"
            track_fill = "#BBF7D0" if is_checked else "#F1F5F9"
            knob_fill = "#E2E8F0" if is_checked else "#CBD5E1"
            knob_border = "#CBD5E1" if is_checked else "#E2E8F0"
        elif is_checked:
            track_border = "#16A34A"
            track_fill = "#22C55E"
            knob_fill = "#FFFFFF"
            knob_border = "#DCFCE7"
        else:
            track_border = "#CBD5E1"
            track_fill = "#E2E8F0"
            knob_fill = "#FFFFFF"
            knob_border = "#CBD5E1"

    scale = 4
    w, h = 28 * scale, 16 * scale
    radius = h / 2.0

    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Outer pill border
    draw.rounded_rectangle([0, 0, w - 1, h - 1], radius=radius, fill=track_border)
    # Inner pill fill
    draw.rounded_rectangle([scale, scale, w - 1 - scale, h - 1 - scale], radius=radius - scale, fill=track_fill)

    # Smooth circular knob
    knob_r = 5.5 * scale
    kx = (20 * scale) if is_checked else (8 * scale)
    ky = h / 2.0
    draw.ellipse([kx - knob_r, ky - knob_r, kx + knob_r, ky + knob_r], fill=knob_fill, outline=knob_border, width=scale)

    final_img = img.resize((28, 16), Image.Resampling.BICUBIC)
    photo = ImageTk.PhotoImage(final_img)
    _TOGGLE_IMAGE_CACHE[cache_key] = photo
    return photo


class CanvasCheckbutton:
    """Modern Pill Toggle Switch rendered directly on tk.Canvas with alpha transparency."""
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
        self._photo = None
        self._x = 0
        self._y = 0
        self._w = 120
        self._h = 22
        self._visible = False
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

        track_w = 28
        track_h = 16
        r = track_h / 2.0
        track_x = int(self._x)
        cy = int(self._y + self._h // 2)
        x1 = track_x + r
        x2 = track_x + track_w - r

        if self.theme_mode == "dark":
            if is_disabled:
                track_border = "#1E3A2F" if is_checked else "#27272A"
                track_fill = "#164E2E" if is_checked else "#18181B"
                knob_fill = "#6B7280" if is_checked else "#3F3F46"
                knob_border = "#374151" if is_checked else "#27272A"
                text_fill = "#52525B"
            elif is_checked:
                track_border = "#16A34A"
                track_fill = "#22C55E"
                knob_fill = "#FFFFFF"
                knob_border = "#DCFCE7"
                text_fill = "#F1F5F9"
            else:
                track_border = "#52525B"
                track_fill = "#3F3F46"
                knob_fill = "#E4E4E7"
                knob_border = "#A1A1AA"
                text_fill = "#E2E8F0"
        else:
            if is_disabled:
                track_border = "#86EFAC" if is_checked else "#E2E8F0"
                track_fill = "#BBF7D0" if is_checked else "#F1F5F9"
                knob_fill = "#E2E8F0" if is_checked else "#CBD5E1"
                knob_border = "#CBD5E1" if is_checked else "#E2E8F0"
                text_fill = "#94A3B8"
            elif is_checked:
                track_border = "#16A34A"
                track_fill = "#22C55E"
                knob_fill = "#FFFFFF"
                knob_border = "#DCFCE7"
                text_fill = "#0F172A"
            else:
                track_border = "#CBD5E1"
                track_fill = "#E2E8F0"
                knob_fill = "#FFFFFF"
                knob_border = "#CBD5E1"
                text_fill = "#1E293B"

        photo = _get_toggle_image(self.theme_mode, is_checked, is_disabled)
        if photo:
            self._photo = photo
            img_item = self.canvas.create_image(
                track_x, cy, image=photo, anchor="w", tags=self._tag
            )
            self._items.append(img_item)
        else:
            # Native fallback if PIL is unavailable
            t_out = self.canvas.create_line(
                x1, cy, x2, cy,
                width=track_h, capstyle="round", fill=track_border, tags=self._tag
            )
            self._items.append(t_out)

            t_in = self.canvas.create_line(
                x1, cy, x2, cy,
                width=track_h - 2, capstyle="round", fill=track_fill, tags=self._tag
            )
            self._items.append(t_in)

            knob_r = 5
            kx = int(x2 if is_checked else x1)
            knob = self.canvas.create_oval(
                kx - knob_r, cy - knob_r, kx + knob_r, cy + knob_r,
                fill=knob_fill, outline="", width=0, tags=self._tag
            )
            self._items.append(knob)

        # Text label to the right of toggle
        txt = self.canvas.create_text(
            track_x + track_w + 8, cy,
            text=self.text, font=self.font,
            fill=text_fill, anchor="w", tags=self._tag
        )
        self._items.append(txt)

        # Transparent hit box for click target
        hit = self.canvas.create_rectangle(
            self._x, self._y, self._x + self._w, self._y + self._h,
            fill="", outline="", tags=self._tag
        )
        self._items.append(hit)

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


class CanvasSegmentedPill:
    """Segmented pill selector rendered directly on tk.Canvas with smooth active highlight."""
    def __init__(self, canvas, segments, initial_key="default", command=None, font=None, theme_mode="dark"):
        self.canvas = canvas
        self.segments = list(segments)
        self.selected_key = initial_key
        self.command = command
        self.font = font or ("Segoe UI", 9)
        self.theme_mode = theme_mode
        self._x = 0
        self._y = 0
        self._w = 100
        self._h = 28
        self._visible = False
        self._items = []
        self._tag = f"cseg_{id(self)}"
        self._segment_handlers = {k: {} for k, _ in self.segments}

    def set_theme(self, theme_name: str):
        if theme_name in ("light", "dark"):
            self.theme_mode = theme_name
            self.redraw()

    def place(self, x, y, width=100, height=28):
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
        if not self._visible or not self.segments:
            return

        x, y, w, h = int(self._x), int(self._y), int(self._w), int(self._h)
        r = h / 2.0
        n = len(self.segments)
        seg_w = w / float(n)

        is_dark = (self.theme_mode == "dark")
        bg_border = "#3F3F46" if is_dark else "#CBD5E1"
        bg_fill = "#1E1E24" if is_dark else "#F1F5F9"
        active_fill = "#0284C7" if is_dark else "#2563EB"
        active_border = "#0369A1" if is_dark else "#1D4ED8"
        active_text = "#FFFFFF"
        inactive_text = "#94A3B8" if is_dark else "#64748B"

        # Outer track container
        c1 = self.canvas.create_line(x + r, y + r, x + w - r, y + r, width=h, capstyle="round", fill=bg_border, tags=self._tag)
        c2 = self.canvas.create_line(x + r, y + r, x + w - r, y + r, width=h - 2, capstyle="round", fill=bg_fill, tags=self._tag)
        self._items.extend([c1, c2])

        # Active highlight index
        active_idx = None
        for i, (k, _) in enumerate(self.segments):
            if k == self.selected_key:
                active_idx = i
                break

        # Subtle vertical dividers between unselected segments
        for i in range(1, n):
            if active_idx is None or (i != active_idx and i != (active_idx + 1)):
                div_x = int(x + i * seg_w)
                div = self.canvas.create_line(div_x, y + 6, div_x, y + h - 6, fill=bg_border, width=1, tags=self._tag)
                self._items.append(div)

        # Active highlight pill
        if active_idx is not None:
            pad = 2
            sh = h - 2 * pad
            sr = sh / 2.0
            sx1 = x + active_idx * seg_w + pad
            sx2 = x + (active_idx + 1) * seg_w - pad
            sy = y + pad + sr
            act_out = self.canvas.create_line(sx1 + sr, sy, sx2 - sr, sy, width=sh, capstyle="round", fill=active_border, tags=self._tag)
            act_in = self.canvas.create_line(sx1 + sr, sy, sx2 - sr, sy, width=sh - 2, capstyle="round", fill=active_fill, tags=self._tag)
            self._items.extend([act_out, act_in])

        # Segment texts & hitboxes
        f_name = self.font[0] if isinstance(self.font, (list, tuple)) else "Segoe UI"
        f_size = self.font[1] if isinstance(self.font, (list, tuple)) and len(self.font) > 1 else 9

        for i, (k, label) in enumerate(self.segments):
            tx = x + (i + 0.5) * seg_w
            ty = y + r
            is_active = (k == self.selected_key)
            color = active_text if is_active else inactive_text
            weight = "bold" if is_active else "normal"

            txt = self.canvas.create_text(
                tx, ty, text=label, fill=color,
                font=(f_name, f_size, weight), anchor="center", tags=(self._tag, f"{self._tag}_{k}")
            )
            self._items.append(txt)

            hit = self.canvas.create_rectangle(
                int(x + i * seg_w), y, int(x + (i + 1) * seg_w), y + h,
                fill="", outline="", tags=(self._tag, f"{self._tag}_{k}")
            )
            self._items.append(hit)

            self.canvas.tag_bind(hit, "<Button-1>", lambda e, key=k: self._on_segment_click(key))
            self.canvas.tag_bind(txt, "<Button-1>", lambda e, key=k: self._on_segment_click(key))

            for seq, funcs in self._segment_handlers.get(k, {}).items():
                for f in funcs:
                    self.canvas.tag_bind(hit, seq, f)
                    self.canvas.tag_bind(txt, seq, f)

    def _on_segment_click(self, key):
        if self.selected_key != key:
            self.selected_key = key
            self.redraw()
            if self.command:
                self.command(key)

    def set_selected(self, key):
        if self.selected_key != key:
            self.selected_key = key
            self.redraw()

    def update_segment_text(self, key, text):
        new_segs = []
        for k, lbl in self.segments:
            if k == key:
                new_segs.append((k, text))
            else:
                new_segs.append((k, lbl))
        self.segments = new_segs
        self.redraw()

    def get_segment_coords(self, key):
        n = len(self.segments)
        seg_w = self._w / float(n) if n else self._w
        for i, (k, _) in enumerate(self.segments):
            if k == key:
                return (self._x + i * seg_w, self._y)
        return (self._x, self._y)

    def get_segment_width(self):
        n = len(self.segments)
        return (self._w / float(n)) if n else self._w

    def bind_segment(self, key, seq, func, add="+"):
        if key not in self._segment_handlers:
            self._segment_handlers[key] = {}
        if seq not in self._segment_handlers[key] or add != "+":
            self._segment_handlers[key][seq] = []
        self._segment_handlers[key][seq].append(func)
        for item in self.canvas.find_withtag(f"{self._tag}_{key}"):
            self.canvas.tag_bind(item, seq, func)


class SegmentProxy:
    """Proxy providing backward compatibility for tests and ToolTip attachments to a segment."""
    def __init__(self, pill: CanvasSegmentedPill, key: str, text: str):
        self.pill = pill
        self.key = key
        self._text = text
        self.state = "normal"
        self._tag = f"{pill._tag}_{key}"

    @property
    def canvas(self):
        return self.pill.canvas

    @property
    def text(self):
        for k, lbl in self.pill.segments:
            if k == self.key:
                return lbl
        return self._text

    @text.setter
    def text(self, val):
        val_str = str(val)
        if val_str.startswith("● "):
            val_str = val_str[2:]
        self._text = val_str
        self.pill.update_segment_text(self.key, self._text)

    def cget(self, key):
        if key == "text":
            return self.text
        if key == "state":
            return self.state
        return ""

    def configure(self, **kwargs):
        if "text" in kwargs:
            raw_text = str(kwargs["text"])
            if raw_text.startswith("● "):
                raw_text = raw_text[2:]
            self.text = raw_text
        if "font" in kwargs:
            self.pill.font = kwargs["font"]
            self.pill.redraw()
        if "state" in kwargs:
            self.state = str(kwargs["state"])
            self.pill.redraw()

    def config(self, **kwargs):
        self.configure(**kwargs)

    def set_theme(self, theme_name: str):
        self.pill.set_theme(theme_name)

    def place(self, *args, **kwargs):
        pass

    def hide(self):
        pass

    def bind(self, seq, func, add="+"):
        self.pill.bind_segment(self.key, seq, func, add=add)

    def winfo_rootx(self):
        seg_x, _ = self.pill.get_segment_coords(self.key)
        return self.pill.canvas.winfo_rootx() + int(seg_x)

    def winfo_rooty(self):
        return self.pill.canvas.winfo_rooty() + int(self.pill._y)

    def winfo_width(self):
        return int(self.pill.get_segment_width())

    def winfo_height(self):
        return int(self.pill._h)

    def after(self, ms, func):
        return self.pill.canvas.after(ms, func)

    def after_cancel(self, aid):
        return self.pill.canvas.after_cancel(aid)


class ToolTip:
    """Lightweight hover tooltip for Tkinter widgets."""

    def __init__(self, widget, text: str | Callable[[], str] = "", delay_ms: int = 400):
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
        resolved_text = self.text() if callable(self.text) else self.text
        if self._tip_window or not resolved_text or not self.widget:
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
                text=resolved_text,
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

    def update_text(self, text: str | Callable[[], str]):
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
        pw = popup.winfo_reqwidth()
        ph = popup.winfo_reqheight()

        from src.ui.platform import get_monitor_work_area
        work_area = get_monitor_work_area(x, y)
        if work_area:
            mon_left, mon_top, mon_right, mon_bottom = work_area
            if self._parent_menu and (x + pw > mon_right):
                parent_win = getattr(self._parent_menu, "_popup_window", None)
                if parent_win:
                    x = parent_win.winfo_rootx() - pw + 2
            if x + pw > mon_right:
                x = mon_right - pw - 8
            if x < mon_left:
                x = mon_left + 4
            if y + ph > mon_bottom:
                y = mon_bottom - ph - 8
            if y < mon_top:
                y = mon_top + 4
        else:
            sw = popup.winfo_screenwidth()
            sh = popup.winfo_screenheight()
            if x + pw > sw:
                x = max(0, sw - pw - 8)
            if y + ph > sh:
                y = max(0, sh - ph - 8)
            x = max(0, x)
            y = max(0, y)
        popup.geometry(f"+{x}+{y}")
        popup.update_idletasks()

