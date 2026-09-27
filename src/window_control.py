"""Window detection, frame capture, DPI scaling, and input projection utilities."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import random
import time
from typing import Optional
import cv2
import mss
import numpy as np
import pydirectinput
import pygetwindow as gw

from localization import tr

GAME_TITLE = "hololive-Dreams"
REFERENCE_WIDTH = 1920
REFERENCE_HEIGHT = 1080


def init_dpi_awareness() -> None:
    """Align Win32 coordinates, PrintWindow output, and SendInput coordinates."""
    try:
        ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
    except Exception:
        pass


init_dpi_awareness()

_user32 = ctypes.windll.user32
_gdi32 = ctypes.windll.gdi32
_capture_context: Optional[dict] = None

# Configure Win32 signatures
_user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
_user32.GetClientRect.restype = wintypes.BOOL
_user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
_user32.ClientToScreen.restype = wintypes.BOOL
_user32.GetDC.argtypes = [wintypes.HWND]
_user32.GetDC.restype = wintypes.HDC
_user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
_user32.ReleaseDC.restype = ctypes.c_int
_user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
_user32.PrintWindow.restype = wintypes.BOOL
_user32.IsWindow.argtypes = [wintypes.HWND]
_user32.IsWindow.restype = wintypes.BOOL
_user32.ShowWindowAsync.argtypes = [wintypes.HWND, ctypes.c_int]
_user32.SetForegroundWindow.argtypes = [wintypes.HWND]
_user32.GetForegroundWindow.argtypes = []
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.BringWindowToTop.argtypes = [wintypes.HWND]
_user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
                                 ctypes.c_int, ctypes.c_int, wintypes.UINT]

_gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
_gdi32.CreateCompatibleDC.restype = wintypes.HDC
_gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
_gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
_gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
_gdi32.SelectObject.restype = wintypes.HGDIOBJ
_gdi32.GetBitmapBits.argtypes = [wintypes.HBITMAP, wintypes.LONG, wintypes.LPVOID]
_gdi32.GetBitmapBits.restype = wintypes.LONG
_gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
_gdi32.DeleteDC.argtypes = [wintypes.HDC]


def find_game_window(game_title: str = GAME_TITLE) -> Optional[gw.Win32Window]:
    """Return the real game window using an exact title match."""
    expected = game_title.casefold().strip()
    matches = [
        win for win in gw.getAllWindows()
        if win.title.casefold().strip() == expected and getattr(win, "_hWnd", None)
    ]
    if not matches:
        return None
    return max(matches, key=lambda win: max(0, win.width) * max(0, win.height))


def _get_client_geometry(hwnd: int) -> tuple[int, int, int, int]:
    rect = wintypes.RECT()
    origin = wintypes.POINT(0, 0)
    if not _user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise ctypes.WinError()
    if not _user32.ClientToScreen(hwnd, ctypes.byref(origin)):
        raise ctypes.WinError()
    return origin.x, origin.y, rect.right - rect.left, rect.bottom - rect.top


def _capture_client_with_printwindow(hwnd: int, width: int, height: int) -> np.ndarray:
    """Capture client area even when another window covers the game."""
    window_dc = _user32.GetDC(hwnd)
    memory_dc = bitmap = old_bitmap = None
    try:
        if not window_dc:
            raise ctypes.WinError()
        memory_dc = _gdi32.CreateCompatibleDC(window_dc)
        bitmap = _gdi32.CreateCompatibleBitmap(window_dc, width, height)
        if not memory_dc or not bitmap:
            raise ctypes.WinError()
        old_bitmap = _gdi32.SelectObject(memory_dc, bitmap)

        # PW_CLIENTONLY | PW_RENDERFULLCONTENT
        if not _user32.PrintWindow(hwnd, memory_dc, 0x00000001 | 0x00000002):
            raise RuntimeError("PrintWindow failed")

        byte_count = width * height * 4
        buffer = ctypes.create_string_buffer(byte_count)
        if _gdi32.GetBitmapBits(bitmap, byte_count, buffer) != byte_count:
            raise RuntimeError("GetBitmapBits returned an incomplete frame")
        frame = np.frombuffer(buffer, dtype=np.uint8).reshape(height, width, 4)
        frame = frame[:, :, :3].copy()
        if frame.size == 0 or float(frame.mean()) < 1.0:
            raise RuntimeError("PrintWindow returned a blank frame")
        return frame
    finally:
        if old_bitmap and memory_dc:
            _gdi32.SelectObject(memory_dc, old_bitmap)
        if bitmap:
            _gdi32.DeleteObject(bitmap)
        if memory_dc:
            _gdi32.DeleteDC(memory_dc)
        if window_dc:
            _user32.ReleaseDC(hwnd, window_dc)


def _bring_game_to_front(hwnd: int) -> bool:
    if not hwnd or not _user32.IsWindow(hwnd):
        return False
    _user32.ShowWindowAsync(hwnd, 9)  # SW_RESTORE
    _user32.BringWindowToTop(hwnd)
    _user32.SetForegroundWindow(hwnd)
    flags = 0x0001 | 0x0002 | 0x0040  # NOSIZE | NOMOVE | SHOWWINDOW
    _user32.SetWindowPos(hwnd, wintypes.HWND(-1), 0, 0, 0, 0, flags)
    _user32.SetWindowPos(hwnd, wintypes.HWND(-2), 0, 0, 0, 0, flags)
    return True


def capture_game_window(
    game_title: str = GAME_TITLE,
    ref_width: int = REFERENCE_WIDTH,
    ref_height: int = REFERENCE_HEIGHT,
) -> tuple[Optional[np.ndarray], int, int]:
    """Capture and normalize the game window client area to the reference size."""
    global _capture_context
    win = find_game_window(game_title)
    if win is None:
        _capture_context = None
        return None, 0, 0

    if win.isMinimized:
        win.restore()
        time.sleep(0.5)

    hwnd = win._hWnd
    try:
        left, top, width, height = _get_client_geometry(hwnd)
        if width < 640 or height < 360:
            raise RuntimeError(f"Unexpected game client area size: {width}x{height}")
        img = _capture_client_with_printwindow(hwnd, width, height)
    except Exception as exc:
        print(tr('warn_background_capture_fail', error=exc))
        _bring_game_to_front(hwnd)
        time.sleep(0.2)
        left, top, width, height = _get_client_geometry(hwnd)
        if width < 640 or height < 360:
            raise RuntimeError(f"Unexpected game client area size: {width}x{height}")
        monitor = {"top": top, "left": left, "width": width, "height": height}
        with mss.MSS() as sct:
            img = cv2.cvtColor(np.array(sct.grab(monitor)), cv2.COLOR_BGRA2BGR)

    _capture_context = {
        "hwnd": hwnd,
        "width": width,
        "height": height,
    }
    if (width, height) == (ref_width, ref_height):
        normalized = img
    elif width > ref_width and height > ref_height:
        normalized = cv2.resize(img, (ref_width, ref_height), interpolation=cv2.INTER_AREA)
    else:
        normalized = cv2.resize(img, (ref_width, ref_height), interpolation=cv2.INTER_LINEAR)
    return normalized, left, top


def safe_click(
    rel_x: int,
    rel_y: int,
    win_left: int = 0,
    win_top: int = 0,
    ref_width: int = REFERENCE_WIDTH,
    ref_height: int = REFERENCE_HEIGHT,
) -> bool:
    """Project normalized coordinates to client window and trigger humanized click."""
    if not _capture_context:
        print(tr('warn_no_window'))
        return False

    hwnd = _capture_context["hwnd"]
    if not _bring_game_to_front(hwnd):
        print(tr('warn_window_lost'))
        return False

    fg_hwnd = _user32.GetForegroundWindow()
    if fg_hwnd and fg_hwnd != hwnd:
        print(tr('warn_window_lost'))
        return False

    try:
        client_left, client_top, client_width, client_height = _get_client_geometry(hwnd)
    except Exception as exc:
        print(tr('warn_cannot_read_coords', error=exc))
        return False

    offset_x = random.randint(-4, 4)
    offset_y = random.randint(-4, 4)

    target_x = client_left + round(rel_x * client_width / ref_width) + offset_x
    target_y = client_top + round(rel_y * client_height / ref_height) + offset_y

    pydirectinput.moveTo(target_x, target_y)
    time.sleep(random.uniform(0.02, 0.05))

    pydirectinput.mouseDown()
    time.sleep(random.uniform(0.05, 0.08))
    pydirectinput.mouseUp()

    time.sleep(random.uniform(0.05, 0.1))
    return True
