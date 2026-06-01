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

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

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


@app.get("/")
def health():
    """Tiny health check so you can confirm the server is up in a browser."""
    return {"status": "ok", "service": "Innovator Awards Photobooth"}


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
