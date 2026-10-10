"""Canvas and image rendering utilities for Hololive Dreams UI.

Provides dynamic background image discovery, glassmorphic alpha overlays,
and canvas card compositing helpers.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageDraw


def discover_backgrounds(app_dir: Path, resource_dir: Path) -> list[Path]:
    """Find all valid background images across local and bundled resource folders."""
    valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp"}
    found: list[Path] = []
    search_dirs = [app_dir / "backgrounds", resource_dir / "backgrounds"]
    for directory in search_dirs:
        if directory.exists() and directory.is_dir():
            for p in sorted(directory.iterdir()):
                if p.is_file() and p.suffix.lower() in valid_exts and p not in found:
                    found.append(p)
    legacy_bg = resource_dir / "background.png"
    if legacy_bg.exists() and legacy_bg not in found:
        found.append(legacy_bg)
    return found


def load_background_image(bg_path: Optional[Path], fallback_hex: str = "#0F172A") -> Tuple[Image.Image, bool]:
    """Load background image from file or generate a fallback solid canvas.

    Returns:
        (PIL Image, show_bg boolean flag)
    """
    if bg_path and bg_path.exists():
        try:
            return Image.open(bg_path), True
        except Exception as e:
            print(f"[Warning] Failed to open background image {bg_path}: {e}")
    return Image.new("RGB", (480, 850), color=fallback_hex), False


def draw_glass_card(
    img: Image.Image,
    bbox: Tuple[int, int, int, int],
    fill: Tuple[int, int, int, int],
    outline: Optional[Tuple[int, int, int, int]] = None,
    radius: int = 8,
) -> Image.Image:
    """Draw a rounded rectangle alpha composite card overlay over a PIL image."""
    x1, y1, x2, y2 = bbox
    if x2 <= x1 or y2 <= y1:
        return img
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        (x1, y1, x2, y2),
        radius=radius,
        fill=fill,
        outline=outline,
        width=1,
    )
    return Image.alpha_composite(img, overlay)
