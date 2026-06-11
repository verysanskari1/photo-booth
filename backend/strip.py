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

from PIL import Image, ImageDraw, ImageFont, ImageOps

BACKEND_DIR = Path(__file__).resolve().parent
_FONT_DIRS = [BACKEND_DIR / "fonts", BACKEND_DIR.parent / "frontend" / "fonts"]

# Strip background artwork. The 4x6 holds TWO variations side by side:
#   A (left): colored subject on template A's background
#   B (right): the SAME subject desaturated (b/w) on template B's background
# Drop your two designs at these paths (600x1800 each). A single strip_template.png
# is used for both if the _a/_b files are absent; built-in art if none exist.
STRIP_TEMPLATE = BACKEND_DIR / "strip_template.png"
STRIP_TEMPLATE_A = BACKEND_DIR / "strip_template_a.png"
STRIP_TEMPLATE_B = BACKEND_DIR / "strip_template_b.png"

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


def _place_cutout(base, cutout, box, desaturate=False, zoom=1.0):
    """Paste a transparent subject cutout into `box`, top-anchored and centered
    horizontally, so the template's artwork shows around it.

    `desaturate` renders the subject in black and white. `zoom` > 1 scales the
    subject larger than the box (cropping the lower body) for a tighter close-up.
    """
    bx, by, bw, bh = box
    cut = cutout.convert("RGBA")
    bbox = cut.getchannel("A").getbbox()
    if bbox:
        cut = cut.crop(bbox)

    if desaturate:
        r, g, b, a = cut.split()
        gray = ImageOps.grayscale(cut)            # L
        cut = Image.merge("RGBA", (gray, gray, gray, a))

    cw, ch = cut.size
    nh = int(bh * zoom)
    scale = nh / ch
    nw = max(1, int(cw * scale))
    cut = cut.resize((nw, nh), Image.LANCZOS)

    x = bx + (bw - nw) // 2                        # center; may overflow box width
    y = by                                         # top-anchored (keeps the head)

    # Clip to the box so a zoomed-in subject doesn't spill past the photo cell.
    region = base.crop((bx, by, bx + bw, by + bh)).convert("RGBA")
    region.alpha_composite(cut, (x - bx, y - by))
    base.paste(region.convert("RGB"), (bx, by))


# How much tighter the bottom photo is cropped vs the top (visual variety even
# if the AI keeps a similar pose).
BOTTOM_ZOOM = 1.3


def _build_one_strip(template_path, cut1, cut2, name, lines, desaturate=False):
    """Build a single 600x1800 strip on the given background template."""
    if template_path and Path(template_path).exists():
        base = Image.open(template_path).convert("RGB").resize((STRIP_W, STRIP_H), Image.LANCZOS)
    else:
        base = _draw_builtin_base()
    _place_cutout(base, cut1, PHOTO_TOP_BOX, desaturate)
    _place_cutout(base, cut2, PHOTO_BOT_BOX, desaturate, zoom=BOTTOM_ZOOM)
    _draw_verse(base, name, lines)
    return base


def _pick(*candidates):
    for c in candidates:
        if c and Path(c).exists():
            return c
    return None


def _colorfulness(path) -> float:
    """Mean saturation of a template (0=grayscale ... 255=vivid)."""
    im = Image.open(path).convert("RGB").resize((60, 180)).convert("HSV")
    s = im.split()[1]
    data = list(s.getdata())
    return sum(data) / max(1, len(data))


def build_print(cut1: Image.Image, cut2: Image.Image, name: str, lines: list[str]) -> Image.Image:
    """Assemble the 4x6 (1200x1800): two strip variations side by side, flush so a
    2-inch cutter splits them cleanly.

    For contrast we cross subject and background: the COLORED background gets the
    B/W subject, and the B/W background gets the COLORED subject. Which template
    is which is detected automatically (by saturation), so filenames don't matter.
    Left strip = colored subject on b/w bg; right strip = b/w subject on colored bg.
    """
    ta = _pick(STRIP_TEMPLATE_A, STRIP_TEMPLATE)
    tb = _pick(STRIP_TEMPLATE_B, STRIP_TEMPLATE)

    if ta and tb and ta != tb:
        # Decide which template is the colorful one and which is grayscale.
        if _colorfulness(ta) >= _colorfulness(tb):
            color_t, bw_t = ta, tb
        else:
            color_t, bw_t = tb, ta
        left = _build_one_strip(bw_t, cut1, cut2, name, lines, desaturate=False)    # colored subj / b&w bg
        right = _build_one_strip(color_t, cut1, cut2, name, lines, desaturate=True)  # b&w subj / colored bg
    else:
        # Single (or no) template: keep one colored + one desaturated.
        left = _build_one_strip(ta, cut1, cut2, name, lines, desaturate=False)
        right = _build_one_strip(tb, cut1, cut2, name, lines, desaturate=True)

    sheet = Image.new("RGB", (STRIP_W * 2, STRIP_H), BLACK)
    sheet.paste(left, (0, 0))
    sheet.paste(right, (STRIP_W, 0))
    return sheet
