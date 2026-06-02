"""
strip.py — assemble the print-ready 2x6 inch photo strip.

Canvas is 600 x 1800 px (2" x 6" @ 300dpi). Layout, top to bottom:

    +------------------+  0     header band
    |   POSE 1 photo   |  170   (square, 600x600)   PHOTO_TOP_BOX
    |   verse + name   |  770   (300 tall)          VERSE_BOX
    |   POSE 2 photo   |  1070  (square, 600x600)   PHOTO_BOT_BOX
    +------------------+  1670  footer band
                          1800

TEMPLATE MODE (optional): drop a full-strip artwork at
`backend/strip_template.png` (any size, it's fit to 600x1800). If present it is
used as the base layer, and we just paste the two photos into the photo boxes
and draw the verse + name into the verse box. Design your template so those
three regions (see the *_BOX coordinates below) are left clear. If no template
exists, a clean built-in design is drawn instead.

Fonts: uses Kalice (serif) / Satoshi (sans) if you drop the files into
backend/fonts/ or frontend/fonts/, otherwise falls back to system fonts.
No em dashes, no URL (by request).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BACKEND_DIR = Path(__file__).resolve().parent
_FONT_DIRS = [BACKEND_DIR / "fonts", BACKEND_DIR.parent / "frontend" / "fonts"]
STRIP_TEMPLATE = BACKEND_DIR / "strip_template.png"

STRIP_W, STRIP_H = 600, 1800
HEADER_H = 170
PHOTO_H = 600
FOOTER_H = 130
VERSE_H = STRIP_H - HEADER_H - 2 * PHOTO_H - FOOTER_H  # = 300

# The three regions photos/text occupy (x, y, w, h). Match these in any template.
PHOTO_TOP_BOX = (0, HEADER_H, STRIP_W, PHOTO_H)
VERSE_BOX = (40, HEADER_H + PHOTO_H, STRIP_W - 80, VERSE_H)
PHOTO_BOT_BOX = (0, HEADER_H + PHOTO_H + VERSE_H, STRIP_W, PHOTO_H)

# Palette (black ground, neon-green accent, light text).
BLACK = (0, 0, 0)
PANEL = (12, 8, 20)
NEON = (185, 232, 79)
WHITE = (244, 241, 234)
MUTED = (185, 169, 214)


def _font(names, size, system_fallback):
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


def _serif(size):
    return _font(
        ["Kalice-Regular.otf", "Kalice-Regular.ttf", "Kalice.otf", "Kalice.ttf"],
        size,
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
    )


def _sans(size, bold=False):
    names = (
        ["Satoshi-Bold.otf", "Satoshi-Bold.ttf"]
        if bold
        else ["Satoshi-Regular.otf", "Satoshi-Regular.ttf", "Satoshi.ttf", "Satoshi-Variable.ttf"]
    )
    return _font(
        names,
        size,
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    )


def _center(draw, cx, y, text, font, fill):
    b = draw.textbbox((0, 0), text, font=font)
    draw.text((cx - (b[2] - b[0]) // 2, y), text, font=font, fill=fill)


def _fit_box(img, box):
    """Center-crop `img` to the box aspect and resize to fill the box exactly."""
    bx, by, bw, bh = box
    img = img.convert("RGB")
    w, h = img.size
    scale = max(bw / w, bh / h)
    nw, nh = int(w * scale), int(h * scale)
    img = img.resize((nw, nh), Image.LANCZOS)
    left, top = (nw - bw) // 2, (nh - bh) // 2
    return img.crop((left, top, left + bw, top + bh))


def _draw_builtin_base():
    """The default strip artwork when no template is supplied."""
    base = Image.new("RGB", (STRIP_W, STRIP_H), BLACK)
    draw = ImageDraw.Draw(base)
    cx = STRIP_W // 2

    # Header
    _center(draw, cx, 36, "HackerRank  x  ET HRWorld", _sans(20, bold=True), NEON)
    _center(draw, cx, 72, "Innovator Awards", _serif(50), WHITE)
    _center(draw, cx, 130, "Photobooth 2026", _sans(18, bold=True), MUTED)

    # Verse panel with neon hairlines top/bottom
    vy = HEADER_H + PHOTO_H
    draw.rectangle([0, vy, STRIP_W, vy + VERSE_H], fill=PANEL)
    draw.rectangle([0, vy, STRIP_W, vy + 3], fill=NEON)
    draw.rectangle([0, vy + VERSE_H - 3, STRIP_W, vy + VERSE_H], fill=NEON)
    return base


def _wrap(draw, text, font, max_w):
    """Greedy word-wrap `text` to fit `max_w` at the given font."""
    words, out, cur = text.split(), [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out


def _draw_verse(base, name, lines):
    """Draw the rhyming couplet + name attribution, wrapped and auto-fit so it
    always stays inside the verse box (never clips at the edges)."""
    draw = ImageDraw.Draw(base)
    bx, by, bw, bh = VERSE_BOX
    cx = bx + bw // 2
    max_w = bw - 24
    name_gap = 26
    name_h = 40
    lines = [ln for ln in lines if ln]

    # Find the largest size at which the wrapped couplet + name fits the box.
    verse_size = 52
    while verse_size >= 24:
        verse_font = _serif(verse_size)
        wrapped = []
        for ln in lines:
            wrapped += _wrap(draw, ln, verse_font, max_w)
        line_gap = int(verse_size * 1.2)
        block_h = len(wrapped) * line_gap + name_gap + name_h
        if block_h <= bh - 16:
            break
        verse_size -= 2

    name_font = _sans(30, bold=True)
    ty = by + max(12, (bh - block_h) // 2)
    for ln in wrapped:
        _center(draw, cx, ty, ln, verse_font, WHITE)
        ty += line_gap
    if name:
        _center(draw, cx, ty + name_gap, name, name_font, NEON)


def build_strip(pose1: Image.Image, pose2: Image.Image, name: str, lines: list[str]) -> Image.Image:
    """Compose the full strip. `lines` is the (3-line) verse."""
    if STRIP_TEMPLATE.exists():
        print("[strip] using template:", STRIP_TEMPLATE.name)
        base = Image.open(STRIP_TEMPLATE).convert("RGB").resize((STRIP_W, STRIP_H), Image.LANCZOS)
    else:
        base = _draw_builtin_base()

    # Paste the two photos into their boxes.
    base.paste(_fit_box(pose1, PHOTO_TOP_BOX), (PHOTO_TOP_BOX[0], PHOTO_TOP_BOX[1]))
    base.paste(_fit_box(pose2, PHOTO_BOT_BOX), (PHOTO_BOT_BOX[0], PHOTO_BOT_BOX[1]))

    # Draw the verse + name.
    _draw_verse(base, name, lines)
    return base
