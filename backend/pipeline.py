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
from pathlib import Path

import fal_client
from PIL import Image

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
    "Recompose into a formal straight-on portrait: head facing forward, "
    "shoulders squared and level, chin level, centered, upright. Framed from "
    "mid-chest up, full shoulders and upper chest visible, empty space below "
    "the shoulders, leave margin on all sides, do not crop shoulders or head. "
    "Keep the person clearly recognizable. Rendered as a varied ASCII-dither "
    "texture: dense crosshatched x and # in shadows, sparse o + e in midtones, "
    "fine dots in highlights. Tight duotone: deep indigo shadows through magenta "
    "to pink-white highlights, monochromatic purple, no natural skin tones. "
    "Dramatic directional key light, deep contrast. Plain flat dark-indigo "
    "background, clean edges for cutout. Vertical, ultra-high detail, cohesive "
    "single style."
)

# Where files live. Resolved relative to this file so it works no matter what
# directory you launch the server from.
BACKEND_DIR = Path(__file__).resolve().parent
BACKGROUND_PATH = BACKEND_DIR / "my_background.png"
OUTPUT_DIR = BACKEND_DIR / "outputs"

# How tall the cut-out subject should be relative to the background height.
SUBJECT_HEIGHT_RATIO = 0.95


# ---------------------------------------------------------------------------
# Step 1 — Stylize the photo
# ---------------------------------------------------------------------------

def stylize(photo_path: str | Path, seed: int | None = None) -> str:
    """Send the captured photo to nano-banana and get back a stylized portrait.

    Returns the URL of the stylized image (hosted by fal). We upload the local
    photo to fal first so it has a URL to feed into image_urls.

    `seed` is optional and only used later (Phase 4 runs this twice with
    different seeds to make two variations for the print strip). Leaving it None
    lets fal pick a random seed.
    """
    print("[1/3] Stylizing photo via", STYLIZE_MODEL, "...")

    # Upload the local file; fal returns a temporary public URL for it.
    image_url = fal_client.upload_file(str(photo_path))

    arguments = {
        "prompt": STYLE_PROMPT,
        "image_urls": [image_url],
        "aspect_ratio": "3:4",
        "num_images": 1,
    }
    if seed is not None:
        arguments["seed"] = seed

    result = fal_client.subscribe(STYLIZE_MODEL, arguments=arguments)
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

    result = fal_client.subscribe(
        REMOVE_BG_MODEL,
        arguments={
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


def run_pipeline(photo_path: str | Path, output_path: str | Path, seed: int | None = None) -> Path:
    """Run all three steps and write the final PNG to `output_path`.

    Returns the path to the saved file. This is the single function the web
    server and the CLI both call.
    """
    stylized_url = stylize(photo_path, seed=seed)
    cutout_url = remove_background(stylized_url)
    cutout = _download_image(cutout_url)
    final = composite(cutout)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.save(output_path, "PNG")
    print("      -> saved final image:", output_path)
    return output_path
