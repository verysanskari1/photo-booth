"""
strip.py — assemble the print-ready 2x6 inch photo strip (Phase 4).

Layout, top to bottom (600 x 1800 px @ 300dpi = 2" x 6"):

    +------------------+  0
    |   header / logo  |  170
    +------------------+
    |   POSE 1 photo   |  770   (600x600 square)
    +------------------+
    |  couplet + name  |  1070  (middle text block)
    +------------------+
    |   POSE 2 photo   |  1670  (600x600 square)
    +------------------+
    |   footer / url   |  1800
    +------------------+

build_strip() takes two already-composited square portraits (different poses),
the guest's name, and the two couplet lines, and returns the finished strip image.
Fonts: uses Kalice (serif) / Satoshi (sans) if present in frontend/fonts or
backend/fonts, otherwise falls back to bundled system fonts.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BACKEND_DIR = Path(__file__).resolve().parent
_FONT_DIRS = [BACKEND_DIR / "fonts", BACKEND_DIR.parent / "frontend" / "fonts"]

# Canvas + section heights (px).
STRIP_W, STRIP_H = 600, 1800
HEADER_H = 170
PHOTO_H = 600
FOOTER_H = 130
COUPLET_H = STRIP_H - HEADER_H - 2 * PHOTO_H - FOOTER_H  # = 300

# Palette (matches the booth).
INDIGO_DEEP = (20, 12, 40)
PANEL = (32, 18, 58)
NEON = (200, 255, 77)
WHITE = (245, 240, 255)
MUTED = (200, 180, 235)


def _font(names: list[str], size: int, system_fallback: str) -> ImageFont.FreeTypeFont:
    for d in _FONT_DIRS:
        for n in names:
            p = d / n
            if p.exists():
                try:
                    return ImageFont.truetype(str(p), size)
                except OSError:
                    pass
    try:
        return ImageFont.truetype(system_fallback, size)
    except OSError:
        return ImageFont.load_default()


def _serif(size: int) -> ImageFont.FreeTypeFont:
    return _font(
        ["Kalice.ttf", "Kalice-Regular.ttf"],
        size,
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf",
    )


def _sans(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return _font(
        ["Satoshi-Bold.ttf" if bold else "Satoshi.ttf"],
        size,
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    )


def _center(draw, cx, y, text, font, fill):
    b = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (b[2] - b[0]) // 2, y), text, font=font, fill=fill)


def _fit_square(img: Image.Image, size: int) -> Image.Image:
    """Center-crop `img` to a square and resize to size x size."""
    img = img.convert("RGB")
    w, h = img.size
    s = min(w, h)
    img = img.crop(((w - s) // 2, (h - s) // 2, (w - s) // 2 + s, (h - s) // 2 + s))
    return img.resize((size, size), Image.LANCZOS)


def build_strip(pose1: Image.Image, pose2: Image.Image, name: str, couplet: list[str]) -> Image.Image:
    """Compose the full strip. `couplet` is a list of (usually two) lines."""
    strip = Image.new("RGB", (STRIP_W, STRIP_H), INDIGO_DEEP)
    draw = ImageDraw.Draw(strip)
    cx = STRIP_W // 2

    # --- Header -------------------------------------------------------------
    _center(draw, cx, 34, "HACKERRANK  ×  ET HRWORLD", _sans(20, bold=True), NEON)
    _center(draw, cx, 70, "Innovator Awards", _serif(54), WHITE)
    _center(draw, cx, 132, "PHOTOBOOTH 2026", _sans(20, bold=True), MUTED)

    # --- Pose 1 -------------------------------------------------------------
    y1 = HEADER_H
    strip.paste(_fit_square(pose1, PHOTO_H), (0, y1))

    # --- Couplet block ------------------------------------------------------
    cy = HEADER_H + PHOTO_H
    draw.rectangle([0, cy, STRIP_W, cy + COUPLET_H], fill=PANEL)
    draw.rectangle([0, cy, STRIP_W, cy + 4], fill=NEON)                       # top rule
    draw.rectangle([0, cy + COUPLET_H - 4, STRIP_W, cy + COUPLET_H], fill=NEON)  # bottom rule

    line_font = _serif(34)
    lines = [ln for ln in couplet if ln]
    block_h = len(lines) * 46
    ty = cy + (COUPLET_H - block_h - 50) // 2  # leave room for the name line below
    for ln in lines:
        _center(draw, cx, ty, ln, line_font, WHITE)
        ty += 46
    _center(draw, cx, ty + 10, f"— {name}", _sans(26, bold=True), NEON)

    # --- Pose 2 -------------------------------------------------------------
    y2 = HEADER_H + PHOTO_H + COUPLET_H
    strip.paste(_fit_square(pose2, PHOTO_H), (0, y2))

    # --- Footer -------------------------------------------------------------
    fy = STRIP_H - FOOTER_H
    draw.rectangle([0, fy, STRIP_W, STRIP_H], fill=INDIGO_DEEP)
    _center(draw, cx, fy + 46, "www.hackerrank.com", _sans(28, bold=True), NEON)

    return strip
