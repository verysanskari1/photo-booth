"""
app.py — the FastAPI server for the Innovator Awards Photobooth.

This server holds the fal.ai API key (via the FAL_KEY env var) and runs the
image pipeline. The iPad frontend POSTs a photo here and gets back a JSON
{"image_url": "..."} pointing at the finished, composited PNG.

The frontend NEVER talks to fal.ai directly — that would leak the API key into
the browser. Everything secret stays on this side.

Two ways to run it:

  WEB SERVER (for the event):
      export FAL_KEY=...           # your fal.ai key
      export PUBLIC_HOST=https://your-backend.ngrok.app   # see README
      uvicorn app:app --host 0.0.0.0 --port 8000

  CLI TEST MODE (no frontend needed — just try the pipeline on a local file):
      export FAL_KEY=...
      python app.py --test path/to/photo.jpg
  ...which writes outputs/test_result.png so you can eyeball the result.
"""

from __future__ import annotations

import argparse
import os
import sys
import uuid
from pathlib import Path

# Load environment variables from a local .env file (FAL_KEY, OPENROUTER_API_KEY,
# PUBLIC_HOST, ...) so you set them once instead of exporting every session.
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001 - dotenv is optional
    pass

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

import couplet
import delivery
import faces
import printing
import strip as strip_module

import pipeline

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Base URL the *browser* should use to reach finished images. During the event
# the backend is exposed over https (e.g. via ngrok), so set PUBLIC_HOST to that
# https URL. Defaults to localhost for development on the same machine.
PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "http://localhost:8000").rstrip("/")

OUTPUT_DIR = pipeline.OUTPUT_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Where temporarily-uploaded guest photos land before stylization.
UPLOAD_DIR = pipeline.BACKEND_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# The frontend lives in ../frontend. We serve it from this same server so local
# testing is one command: run uvicorn, open the page, camera + /generate all
# work same-origin (no CORS or tunnel needed on localhost).
FRONTEND_DIR = pipeline.BACKEND_DIR.parent / "frontend"

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(title="Innovator Awards Photobooth")

# The frontend is served from a different origin (its own ngrok tunnel / file),
# so allow cross-origin requests. For a closed event booth this is fine; tighten
# allow_origins if you want to lock it to a specific frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve finished images at /outputs/<file>.png so the frontend can display them.
app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# Serve frontend assets (e.g. dropped-in fonts) at /static if the folder exists.
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/health")
def health():
    """Tiny health check so you can confirm the server is up."""
    return {"status": "ok", "service": "Innovator Awards Photobooth"}


@app.get("/")
def index():
    """Serve the photobooth frontend page (falls back to health if missing)."""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file))
    return JSONResponse({"status": "ok", "service": "Innovator Awards Photobooth"})


@app.post("/generate")
async def generate(photo: UploadFile = File(...)):
    """Main endpoint: accept one uploaded photo, run the pipeline, return a URL.

    The frontend POSTs multipart/form-data with a single field named `photo`.
    """
    if not pipeline.BACKGROUND_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=(
                f"Background image not found at {pipeline.BACKGROUND_PATH}. "
                "Generate one with `python generate_background.py` or drop your "
                "own my_background.png in the backend folder."
            ),
        )

    # Unique id per guest so files never clash.
    job_id = uuid.uuid4().hex[:12]

    # Save the upload to disk (fal-client uploads from a file path).
    suffix = Path(photo.filename or "photo.jpg").suffix or ".jpg"
    upload_path = UPLOAD_DIR / f"{job_id}{suffix}"
    upload_path.write_bytes(await photo.read())

    output_path = OUTPUT_DIR / f"{job_id}.png"

    try:
        pipeline.run_pipeline(upload_path, output_path)
    except Exception as exc:  # noqa: BLE001 - surface a clean error to the UI
        # Print the full traceback to the server log, return a short message.
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {exc}") from exc

    image_url = f"{PUBLIC_HOST}/outputs/{output_path.name}"
    return JSONResponse({"image_url": image_url})


async def _save_upload(photo: UploadFile) -> tuple[str, Path]:
    """Persist an uploaded photo and return (job_id, path)."""
    job_id = uuid.uuid4().hex[:12]
    suffix = Path(photo.filename or "photo.jpg").suffix or ".jpg"
    path = UPLOAD_DIR / f"{job_id}{suffix}"
    path.write_bytes(await photo.read())
    return job_id, path


@app.post("/identify")
async def identify(photo: UploadFile = File(...)):
    """Run face recognition on the captured photo (Phase 5).

    Returns {name, company, confidence, matched}. `matched` is True only when the
    face confidently matches an attendee. The frontend uses this to pre-fill the
    confirm screen; if not matched, the guest just types their name.
    """
    _, upload_path = await _save_upload(photo)
    try:
        return JSONResponse(faces.identify(upload_path))
    except Exception as exc:  # noqa: BLE001 - never block the booth on recognition
        import traceback

        traceback.print_exc()
        return JSONResponse({"name": "", "company": "", "confidence": 0.0, "matched": False})


@app.post("/generate_strip")
async def generate_strip(
    photo: UploadFile = File(...),
    name: str = Form(""),
    company: str = Form(""),
):
    """Build the print-ready photo strip (Phases 4 + 6).

    Two stylized poses (top + bottom) + a personalized couplet block with the
    guest's name in the middle. Returns {image_url, name, couplet}.
    """
    job_id, upload_path = await _save_upload(photo)
    output_path = OUTPUT_DIR / f"{job_id}_strip.png"

    try:
        # Two poses as transparent cutouts (the template provides the background).
        cut1 = pipeline.generate_cutout(upload_path, seed=1, extra_prompt=pipeline.POSE_VARIANTS[0])
        cut2 = pipeline.generate_cutout(upload_path, seed=2, extra_prompt=pipeline.POSE_VARIANTS[1])
        couplet_lines = couplet.make_couplet(name, company or None)
        display_name = (name or "").strip() or "Innovator"
        # 4x6 = two strip variations (colored + b/w) side by side.
        strip_img = strip_module.build_print(cut1, cut2, display_name, couplet_lines)
        strip_img.save(output_path, "PNG")
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Strip generation failed: {exc}") from exc

    return JSONResponse({
        "image_url": f"{PUBLIC_HOST}/outputs/{output_path.name}",
        "name": display_name,
        "couplet": couplet_lines,
    })


@app.get("/printers")
def printers():
    """Diagnostics: what print queues are visible and how printing is configured."""
    return JSONResponse(printing.list_printers())


@app.post("/print")
async def print_strip(filename: str = Form(...), name: str = Form("")):
    """Send a finished strip to the printer.

    Two delivery paths, both attempted:
      1. Copy into the synced DRIVE_FOLDER, so a remote/offsite printer can pick
         it up (the main path for an offsite printer).
      2. Print on a locally-attached printer via CUPS, if one is configured.

    Returns ok=True if either worked. If neither is set up, ok=False and the
    frontend falls back to the browser print dialog.
    """
    fname = Path(filename).name  # strip path components for safety
    target = OUTPUT_DIR / fname
    if not target.exists():
        raise HTTPException(status_code=404, detail=f"No such output: {fname}")

    result = {"ok": False, "drive": None, "job": None, "errors": []}

    # 1. Drop into the synced drive folder for the remote printer.
    try:
        dest = delivery.deliver(target, name)
        if dest:
            result["drive"] = dest
            result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"drive: {exc}")

    # 2. Also try a locally-attached printer, if configured/available.
    try:
        result["job"] = printing.print_image(target)
        result["ok"] = True
    except Exception as exc:  # noqa: BLE001
        result["errors"].append(f"printer: {exc}")

    return JSONResponse(result)


# ---------------------------------------------------------------------------
# CLI test mode
# ---------------------------------------------------------------------------

def _cli():
    parser = argparse.ArgumentParser(description="Photobooth pipeline test runner")
    parser.add_argument("--test", metavar="IMAGE", help="run the pipeline on a local image file")
    parser.add_argument(
        "--out",
        metavar="PATH",
        default=str(OUTPUT_DIR / "test_result.png"),
        help="where to write the result (default: outputs/test_result.png)",
    )
    parser.add_argument("--seed", type=int, default=None, help="optional stylize seed")
    args = parser.parse_args()

    if not args.test:
        parser.print_help()
        sys.exit(0)

    if not os.environ.get("FAL_KEY"):
        print("ERROR: FAL_KEY environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    if not Path(args.test).exists():
        print(f"ERROR: image not found: {args.test}", file=sys.stderr)
        sys.exit(1)

    out = pipeline.run_pipeline(args.test, args.out, seed=args.seed)
    print(f"\nDone. Open {out} to see the result.")


if __name__ == "__main__":
    _cli()
