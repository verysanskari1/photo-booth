"""
delivery.py — drop each finished strip into a "drive" folder for remote printing.

The simplest, most reliable pipeline for a printer that lives somewhere else:
point DRIVE_FOLDER at a local folder that Google Drive for Desktop (or Dropbox /
OneDrive) keeps synced. We copy each finished strip there; it syncs to the cloud
automatically, and the remote print station prints from that same folder.

    DRIVE_FOLDER   absolute path to the synced folder (empty = delivery off).

No API keys, no credentials — it's just a file copy into a synced directory.
"""

from __future__ import annotations

import datetime
import os
import re
import shutil
from pathlib import Path

DRIVE_FOLDER = os.environ.get("DRIVE_FOLDER", "").strip()


def enabled() -> bool:
    return bool(DRIVE_FOLDER)


def deliver(src_path: str | Path, name: str = "") -> str | None:
    """Copy the strip into the synced folder under a readable filename.

    Returns the destination path, or None if DRIVE_FOLDER isn't configured.
    Raises on a real copy failure so the caller can report it.
    """
    if not DRIVE_FOLDER:
        return None

    dest_dir = Path(DRIVE_FOLDER).expanduser()
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_") or "guest"
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"{safe}_{stamp}.png"

    shutil.copy2(src_path, dest)
    print("[delivery] copied strip to drive folder:", dest)
    return str(dest)
