"""
pipeline.py — the per-photo image pipeline for the Innovator Awards Photobooth.

This is where all the image work happens. It is intentionally framework-free
(no FastAPI in here) so it can be reused from both the web server (app.py) and
the command-line test mode (run `python app.py --test some_photo.jpg`).

The pipeline has three steps, run once per guest photo:

  1. STYLIZE         -> fal-ai/nano-banana-2/edit   (turns the photo into the
                        purple ASCII-halftone portrait on a flat dark-indigo bg)
  2. REMOVE BACKGROUND -> fal-ai/birefnet/v2        (cuts the person out, leaving
                        a transparent PNG)
  3. COMPOSITE       -> local Pillow work           (pastes the cutout onto our
                        fixed branded background, my_background.png)

Only steps 1 and 2 call fal.ai (and therefore cost money / need the API key).
Step 3 is 100% local.

The fal API key is read from the FAL_KEY environment variable by the fal-client
library automatically — we never hard-code it.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import fal_client
from PIL import Image, ImageDraw, ImageFilter, ImageFont


def _subscribe(model: str, arguments: dict, attempts: int = 3):
    """Call fal with a few retries so a transient hiccup doesn't fail a guest."""
    last = None
    for i in range(attempts):
        try:
            return fal_client.subscribe(model, arguments=arguments)
        except Exception as exc:  # noqa: BLE001
            last = exc
            wait = 2 * (i + 1)
            print(f"[fal] {model} attempt {i + 1}/{attempts} failed: {exc} (retrying in {wait}s)")
            time.sleep(wait)
    raise RuntimeError(f"fal call to {model} failed after {attempts} attempts: {last}")

# ---------------------------------------------------------------------------
# Configuration / constants
# ---------------------------------------------------------------------------

# fal.ai endpoint names. Pinned here so they are easy to find and change later.
STYLIZE_MODEL = "fal-ai/nano-banana-2/edit"
REMOVE_BG_MODEL = "fal-ai/birefnet/v2"

# The exact stylization prompt requested in the spec. Do not paraphrase — the
# look of every portrait depends on this wording.
STYLE_PROMPT = (
    "Transform this portrait into a high-end editorial halftone artwork. "
    "Regardless of the original camera angle, distance, lighting, or how the "
    "photo was taken (even a casual or unflattering snapshot), always produce a "
    "polished, professional corporate headshot: the subject looking directly "
    "into the camera, face fully visible and flattering, confident neutral "
    "expression. Recompose into a formal straight-on portrait: head facing "
    "forward, shoulders squared and level, chin level, centered, upright. "
    "Framed from "
    "mid-chest up, with both shoulders and the full upper chest comfortably "
    "inside the frame and a small even margin around the subject so nothing "
    "touches the edges. Do not crop the shoulders, arms, or head. "
    "Keep the person clearly recognizable, and fully clothed in their exact "
    "original outfit: never remove, open, undress, or change clothing, and keep "
    "the collar, chest and shoulders covered. "
    "FULLY and HEAVILY stylize the entire image: this must read as a bold graphic "
    "halftone artwork, NOT a lightly filtered photo. Commit completely to the "
    "texture across the whole face, hair, skin and clothing, with no photographic "
    "realism or natural skin texture left anywhere. Rendered as a varied "
    "ASCII-dither texture: dense crosshatched x and # in shadows, sparse o + e in "
    "midtones, fine dots in highlights, the dither clearly visible everywhere. "
    "Tight duotone: deep indigo shadows through magenta to pink-white highlights, "
    "strictly monochromatic purple, absolutely no natural skin tones. Dramatic "
    "directional key light, deep contrast, posterized tonal bands. Plain flat "
    "dark-indigo background, clean edges for cutout. Square composition, "
    "ultra-high detail, cohesive single style."
)

# Where files live. Resolved relative to this file so it works no matter what
# directory you launch the server from.
BACKEND_DIR = Path(__file__).resolve().parent
BACKGROUND_PATH = BACKEND_DIR / "my_background.png"
OUTPUT_DIR = BACKEND_DIR / "outputs"

# How tall the cut-out subject should be relative to the background height.
# 0.98 = the person fills almost the full height and sits flush at the bottom.
SUBJECT_HEIGHT_RATIO = 0.98

# ---- ASCII halftone rendering (local, deterministic) ----------------------
# Optional local pass that re-draws the subject as literal ASCII characters.
# DISABLED by default: the fal model already produces the editorial halftone
# look, and layering glyphs on top tends to muddy the portrait against a busy
# background. Flip to True only if you specifically want hard ASCII glyphs.
ASCII_RENDER = False         # set True to draw literal ASCII glyphs locally
ASCII_COLUMNS = 110          # how many glyph columns across the subject (fewer = bigger, more legible glyphs)

# Glyph ramp ordered LIGHTEST -> DARKEST (by ink coverage). Highlights get a
# space/dot, midtones get o + e, shadows get the dense x and #.
ASCII_RAMP = " .:-+=eo×x#@"

# Duotone colour stops used to tint each glyph by its brightness:
#   bright highlight -> pink-white, midtone -> magenta, shadow -> lit indigo.
# NOTE: the shadow colour is kept clearly lighter than a dark background so the
# darkest glyphs still read instead of vanishing.
ASCII_HI = (255, 214, 236)   # highlights (pink-white)
ASCII_MID = (198, 86, 178)   # midtones (magenta)
ASCII_LO = (92, 54, 134)     # shadows (lit indigo, still visible)

# A soft dark "plate" is drawn behind the subject so the ASCII glyphs pop off a
# busy/dark background instead of blending into it. Set SUBJECT_BACKING=False to
# disable, or tune the colour/opacity/softness.
SUBJECT_BACKING = True
BACKING_COLOR = (14, 8, 28)  # near-black indigo
BACKING_ALPHA = 175          # 0 = invisible, 255 = solid

# Monospace fonts to try (covers macOS + Linux); falls back to a bundled default.
_MONO_FONTS = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/Monaco.ttf",
    "/System/Library/Fonts/Courier.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf",
]


# ---------------------------------------------------------------------------
# Step 1 — Stylize the photo
# ---------------------------------------------------------------------------

def stylize(photo_path: str | Path, seed: int | None = None, extra_prompt: str = "") -> str:
    """Send the captured photo to nano-banana and get back a stylized portrait.

    Returns the URL of the stylized image (hosted by fal). We upload the local
    photo to fal first so it has a URL to feed into image_urls.

    `seed` and `extra_prompt` let the strip (Phase 4) run this twice for two
    different poses. Leaving seed None lets fal pick a random seed.
    """
    print("[1/3] Stylizing photo via", STYLIZE_MODEL, "...")

    # Upload the local file; fal returns a temporary public URL for it.
    image_url = fal_client.upload_file(str(photo_path))

    prompt = STYLE_PROMPT + ((" " + extra_prompt) if extra_prompt else "")
    arguments = {
        "prompt": prompt,
        "image_urls": [image_url],
        "aspect_ratio": "1:1",
        "num_images": 1,
    }
    if seed is not None:
        arguments["seed"] = seed

    result = _subscribe(STYLIZE_MODEL, arguments)
    stylized_url = result["images"][0]["url"]
    print("      -> stylized image:", stylized_url)
    return stylized_url


# ---------------------------------------------------------------------------
# Step 2 — Remove the background
# ---------------------------------------------------------------------------

def remove_background(image_url: str) -> str:
    """Send the stylized portrait to BiRefNet and get back a transparent cutout.

    Returns the URL of the PNG with a transparent background.
    """
    print("[2/3] Removing background via", REMOVE_BG_MODEL, "...")

    result = _subscribe(
        REMOVE_BG_MODEL,
        {
            "image_url": image_url,
            "model": "Portrait",
            "refine_foreground": True,
            "output_format": "png",
        },
    )
    cutout_url = result["image"]["url"]
    print("      -> cutout image:", cutout_url)
    return cutout_url


# ---------------------------------------------------------------------------
# Step 2.5 — Re-render the subject as REAL ASCII glyphs (local, deterministic)
# ---------------------------------------------------------------------------

def _load_mono_font(size: int) -> ImageFont.FreeTypeFont:
    for path in _MONO_FONTS:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _duotone(brightness: float) -> tuple[int, int, int]:
    """Map a 0..1 brightness to the indigo -> magenta -> pink duotone."""
    if brightness < 0.5:
        t = brightness / 0.5
        a, b = ASCII_LO, ASCII_MID
    else:
        t = (brightness - 0.5) / 0.5
        a, b = ASCII_MID, ASCII_HI
    return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))


def asciify(cutout: Image.Image, columns: int = ASCII_COLUMNS) -> Image.Image:
    """Turn the transparent subject cutout into actual ASCII-character art.

    We sample the subject onto a low-res grid (one cell per glyph), then for each
    cell draw a monospace character whose ink-density matches the cell brightness
    and whose colour follows the purple duotone. Glyphs are only drawn where the
    subject is opaque, so the background stays transparent for compositing.
    """
    print("[2.5] Rendering ASCII glyphs (", columns, "columns )...")
    cutout = cutout.convert("RGBA")
    w, h = cutout.size

    # Cell size in source pixels, and the resulting grid dimensions.
    cell = max(4, w // columns)
    cols = max(1, w // cell)
    rows = max(1, h // cell)

    # Downsample once: average brightness + average alpha per cell (fast).
    lum_grid = cutout.convert("L").resize((cols, rows), Image.BILINEAR)
    alpha_grid = cutout.getchannel("A").resize((cols, rows), Image.BILINEAR)

    # Optional soft backing plate shaped like the subject silhouette, so the
    # glyphs read against a busy/dark background.
    if SUBJECT_BACKING:
        silhouette = cutout.getchannel("A")
        plate = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        solid = Image.new("RGBA", (w, h), BACKING_COLOR + (BACKING_ALPHA,))
        plate = Image.composite(solid, plate, silhouette)
        plate = plate.filter(ImageFilter.GaussianBlur(max(2, cell // 2)))
        canvas = plate
    else:
        canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))

    draw = ImageDraw.Draw(canvas)
    font = _load_mono_font(int(cell * 1.25))
    ramp_last = len(ASCII_RAMP) - 1

    for j in range(rows):
        for i in range(cols):
            a = alpha_grid.getpixel((i, j))
            if a < 60:                      # cell is (mostly) outside the subject
                continue
            lum = lum_grid.getpixel((i, j)) / 255.0
            darkness = 1.0 - lum
            glyph = ASCII_RAMP[round(darkness * ramp_last)]
            if glyph == " ":
                continue
            color = _duotone(lum) + (255,)
            draw.text((i * cell, j * cell), glyph, font=font, fill=color)

    return canvas


# ---------------------------------------------------------------------------
# Step 3 — Composite the cutout onto the fixed branded background (local)
# ---------------------------------------------------------------------------

def composite(cutout: Image.Image, background_path: str | Path = BACKGROUND_PATH) -> Image.Image:
    """Paste the transparent cutout onto the fixed background image.

    The subject is scaled to ~0.95 of the background height and anchored
    center-bottom. Uses true alpha compositing so soft/feathered edges blend
    cleanly.

    `cutout` is an already-loaded RGBA Pillow image (so this stays pure-local
    and easy to unit test).
    """
    print("[3/3] Compositing onto background:", background_path)

    background = Image.open(background_path).convert("RGBA")
    bg_w, bg_h = background.size

    cutout = cutout.convert("RGBA")

    # The AI leaves transparent padding around the subject (the prompt asks for
    # "empty space below the shoulders"). Crop that padding away using the alpha
    # channel's bounding box so the *actual person* is what we scale and place.
    # This is what makes the subject fill the frame and sit flush at the bottom
    # instead of floating with a gap below.
    alpha_bbox = cutout.getchannel("A").getbbox()
    if alpha_bbox:
        cutout = cutout.crop(alpha_bbox)

    cut_w, cut_h = cutout.size

    # Scale by height first.
    target_h = int(bg_h * SUBJECT_HEIGHT_RATIO)
    scale = target_h / cut_h
    target_w = int(cut_w * scale)

    # If that makes the subject wider than the background, scale by width instead
    # so the person always fits horizontally.
    if target_w > bg_w:
        scale = bg_w / cut_w
        target_w = bg_w
        target_h = int(cut_h * scale)

    cutout = cutout.resize((target_w, target_h), Image.LANCZOS)

    # Anchor center-bottom: horizontally centered, bottom edge on bg bottom.
    x = (bg_w - target_w) // 2
    y = bg_h - target_h

    # alpha_composite needs both layers the same size, so drop the cutout onto a
    # transparent layer the size of the background, then composite the two.
    layer = Image.new("RGBA", background.size, (0, 0, 0, 0))
    layer.paste(cutout, (x, y), cutout)
    final = Image.alpha_composite(background, layer)
    return final


# ---------------------------------------------------------------------------
# Full pipeline
# ---------------------------------------------------------------------------

def _download_image(url: str) -> Image.Image:
    """Download an image URL into a Pillow image (kept tiny + dependency-light)."""
    import io
    import urllib.request

    with urllib.request.urlopen(url) as resp:
        data = resp.read()
    return Image.open(io.BytesIO(data))


# Two pose hints appended to the prompt to give the strip's top and bottom
# photos a bit of variety. (nano-banana preserves pose somewhat, so these are
# gentle nudges rather than guarantees.)
POSE_VARIANTS = [
    "POSE A: a warm, approachable studio portrait. Straight-on, relaxed squared "
    "shoulders, genuine friendly smile, looking directly at the camera. Soft even "
    "key light, gentle contrast, inviting.",
    "POSE B: a distinctly different artistic editorial portrait. Turn the head and "
    "shoulders to a three-quarter / side-profile angle (about 35 to 50 degrees "
    "away from camera), chin slightly up, gaze toward the camera over the shoulder, "
    "dramatic side key light and deep shadow, fashion-magazine composition. This "
    "must clearly NOT be a straight-on shot.",
]


def generate_cutout(
    photo_path: str | Path, seed: int | None = None, extra_prompt: str = ""
) -> Image.Image:
    """Run stylize -> remove bg -> (ascii) and RETURN the transparent cutout,
    cropped tight to the subject. The strip pastes this onto a template so the
    template's artwork shows as the background behind the subject."""
    stylized_url = stylize(photo_path, seed=seed, extra_prompt=extra_prompt)
    cutout_url = remove_background(stylized_url)
    cutout = _download_image(cutout_url).convert("RGBA")
    if ASCII_RENDER:
        cutout = asciify(cutout)
    bbox = cutout.getchannel("A").getbbox()
    if bbox:
        cutout = cutout.crop(bbox)
    return cutout


def generate_portrait(
    photo_path: str | Path, seed: int | None = None, extra_prompt: str = ""
) -> Image.Image:
    """Cutout composited onto the fixed my_background.png (single-image endpoint)."""
    return composite(generate_cutout(photo_path, seed=seed, extra_prompt=extra_prompt))


def run_pipeline(photo_path: str | Path, output_path: str | Path, seed: int | None = None) -> Path:
    """Run the pipeline once and write the final PNG to `output_path`.

    Returns the path to the saved file. Used by the single-image endpoint + CLI.
    """
    final = generate_portrait(photo_path, seed=seed)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, "PNG")
    print("      -> saved final image:", output_path)
    return output_path
