"""
generate_background.py — builds a default `my_background.png` for the composite.

This produces a branded backdrop in the Innovator Awards style: a white header
band up top with the event title, and a purple gradient lower section with a
faint ASCII-dither texture and a neon-green "www.hackerrank.com" pill — matching
the welcome standee artwork.

It is just a convenience so the booth works out of the box. You can replace
backend/my_background.png with the real event artwork at any time; the pipeline
only cares that the file exists. The guest cutout is composited on top of this,
scaled to ~0.95 of the height and anchored center-bottom.

Run it once:
    python generate_background.py

Fonts: this tries to use Kalice (serif) and Satoshi (sans) if you've installed
them, and falls back to bundled system fonts otherwise. To use the real brand
fonts, drop Kalice.ttf / Satoshi.ttf into a `fonts/` folder next to this script.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BACKEND_DIR = Path(__file__).resolve().parent
FONTS_DIR = BACKEND_DIR / "fonts"
OUTPUT = BACKEND_DIR / "my_background.png"

# Portrait canvas (3:4) — comfortable for a mid-chest-up composited portrait.
W, H = 1200, 1600

# Palette pulled from the standee.
WHITE = (255, 255, 255, 255)
INK = (17, 14, 28, 255)            # near-black for header text
INDIGO_DEEP = (38, 20, 64, 255)    # deep purple, top of gradient
INDIGO_MID = (96, 42, 140, 255)    # mid purple
MAGENTA = (150, 70, 165, 255)      # warm purple/magenta, bottom of gradient
NEON_GREEN = (197, 255, 79, 255)   # the accent pill colour

# ASCII-dither glyphs sprinkled faintly over the purple section.
GLYPHS = list("*+/=eo2|")


def _load_font(candidates: list[str], size: int) -> ImageFont.FreeTypeFont:
    """Return the first font that loads from the candidate paths, else default."""
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _serif(size: int) -> ImageFont.FreeTypeFont:
    # Kalice if available, otherwise a serif fallback.
    return _load_font(
        [
            str(FONTS_DIR / "Kalice.ttf"),
            str(FONTS_DIR / "Kalice-Regular.ttf"),
            "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        ],
        size,
    )


def _sans(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    # Satoshi if available, otherwise a sans fallback.
    name = "Satoshi-Bold.ttf" if bold else "Satoshi.ttf"
    fallback = (
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
    )
    return _load_font([str(FONTS_DIR / name), fallback], size)


def _draw_centered(draw: ImageDraw.ImageDraw, cx: int, y: int, text: str, font, fill):
    """Draw text horizontally centered on cx at vertical position y."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.text((cx - w // 2, y), text, font=font, fill=fill)


def build() -> Image.Image:
    img = Image.new("RGBA", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    # --- Purple gradient fills the lower ~62% of the canvas -----------------
    header_h = int(H * 0.38)
    grad_h = H - header_h
    for i in range(grad_h):
        t = i / grad_h  # 0 at top of gradient -> 1 at bottom
        # Two-stop blend: deep indigo -> mid -> magenta.
        if t < 0.5:
            tt = t / 0.5
            c = [int(INDIGO_DEEP[k] + (INDIGO_MID[k] - INDIGO_DEEP[k]) * tt) for k in range(3)]
        else:
            tt = (t - 0.5) / 0.5
            c = [int(INDIGO_MID[k] + (MAGENTA[k] - INDIGO_MID[k]) * tt) for k in range(3)]
        draw.line([(0, header_h + i), (W, header_h + i)], fill=(c[0], c[1], c[2], 255))

    # --- Faint ASCII-dither texture over the purple ------------------------
    random.seed(2026)
    glyph_font = _sans(22, bold=True)
    step = 34
    for gy in range(header_h + 10, H, step):
        for gx in range(10, W, step):
            ch = random.choice(GLYPHS)
            # Lighter near the top of the gradient, fading down — subtle.
            alpha = random.randint(18, 55)
            draw.text((gx, gy), ch, font=glyph_font, fill=(220, 200, 255, alpha))

    # --- Diagonal hatch strip marking the header/purple seam ----------------
    seam_y = header_h
    for x in range(-H, W, 16):
        draw.line([(x, seam_y), (x + 24, seam_y - 24)], fill=(180, 180, 180, 120), width=2)

    # --- Header text --------------------------------------------------------
    cx = W // 2
    brand = _sans(34, bold=True)
    _draw_centered(draw, cx, int(header_h * 0.10), "HackerRank   |   ET HRWorld", brand, INK)

    title = _serif(118)
    _draw_centered(draw, cx, int(header_h * 0.26), "Innovator", title, INK)
    _draw_centered(draw, cx, int(header_h * 0.26) + 120, "Awards", title, INK)

    sub = _sans(30, bold=True)
    _draw_centered(draw, cx, int(header_h * 0.82), "PHOTOBOOTH", sub, INK)

    # --- Big "2026" on the purple, like the standee ------------------------
    year = _sans(150, bold=True)
    _draw_centered(draw, cx, header_h + int(grad_h * 0.10), "2026", year, WHITE)

    # --- Neon-green URL pill near the bottom -------------------------------
    pill_font = _sans(40, bold=True)
    text = "www.hackerrank.com"
    tb = draw.textbbox((0, 0), text, font=pill_font)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    pad_x, pad_y = 50, 28
    pill_w, pill_h = tw + pad_x * 2, th + pad_y * 2
    px = (W - pill_w) // 2
    py = H - pill_h - 70
    draw.rounded_rectangle([px, py, px + pill_w, py + pill_h], radius=pill_h // 2, fill=NEON_GREEN)
    draw.text((px + pad_x, py + pad_y - tb[1]), text, font=pill_font, fill=INK)

    return img


if __name__ == "__main__":
    out = build()
    out.save(OUTPUT, "PNG")
    print(f"Wrote {OUTPUT} ({W}x{H})")
